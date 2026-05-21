#!/usr/bin/env python3
"""
RepoHub webhook receiver — listens for GitHub push events and triggers deploy.
Runs as a systemd user service on port 9000 (localhost-only + Tailscale).
"""
import os, json, hmac, hashlib, subprocess, logging, secrets
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO_DIR = "/home/samedsemihs/github-repo-explorer"
DEPLOY_SCRIPT = os.path.join(REPO_DIR, "deploy.sh")
SECRET_FILE = os.path.join(REPO_DIR, ".webhook_secret")
HOST = "127.0.0.1"
PORT = 9000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(REPO_DIR, "webhook.log")),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("webhook")

# Load or generate webhook secret
def get_secret():
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(secret + "\n")
    os.chmod(SECRET_FILE, 0o600)
    log.info(f"Generated new webhook secret: {secret}")
    return secret

SECRET = get_secret()


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        # Verify signature
        sig_header = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            log.warning("Invalid signature — rejecting")
            self.send_error(403, "Invalid signature")
            return

        # Parse event
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            log.info(f"Ignored event type: {event}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignored")
            return

        # Verify it's our repo
        try:
            payload = json.loads(body)
            repo = payload.get("repository", {}).get("full_name", "")
            ref = payload.get("ref", "")
            log.info(f"Push event: {repo} ref:{ref}")
        except Exception as e:
            log.error(f"Parse error: {e}")
            self.send_error(400, "Invalid payload")
            return

        # Trigger deploy
        log.info("Triggering deploy...")
        result = subprocess.run(
            ["bash", DEPLOY_SCRIPT],
            capture_output=True, text=True, timeout=60
        )
        log.info(f"Deploy exit: {result.returncode}")
        for line in result.stdout.strip().split("\n"):
            log.info(f"  {line}")
        for line in result.stderr.strip().split("\n"):
            if line:
                log.warning(f"  {line}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "exit_code": result.returncode
        }).encode())

    def log_message(self, fmt, *args):
        log.info(f"{self.client_address[0]} - {fmt % args}")


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), WebhookHandler)
    log.info(f"Webhook receiver listening on {HOST}:{PORT}")
    log.info(f"Webhook secret: {SECRET}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        log.info("Shutdown")
