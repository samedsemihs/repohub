#!/usr/bin/env bash
# RepoHub auto-deploy script
# Called by webhook receiver on push events.
set -euo pipefail

REPO_DIR="/home/samedsemihs/github-repo-explorer"
LOG_FILE="/home/samedsemihs/github-repo-explorer/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Deploy started ==="

cd "$REPO_DIR"

# Fetch latest from GitHub
if ! git fetch origin main 2>/dev/null; then
    log "ERROR: git fetch failed"
    exit 1
fi

# Check if there are new commits
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date. Nothing to deploy."
    exit 0
fi

# Pull changes
log "Pulling new commits: $LOCAL -> $REMOTE"
if ! git pull origin main; then
    log "ERROR: git pull failed"
    exit 1
fi

log "Deploy complete. New HEAD: $(git rev-parse HEAD)"

# Restart the http server if running
if systemctl --user is-active --quiet repohub-web; then
    systemctl --user restart repohub-web
    log "repohub-web service restarted"
fi

log "=== Deploy finished ==="
