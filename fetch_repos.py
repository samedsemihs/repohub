#!/usr/bin/env python3
"""
RepoHub v2 — GitHub Search API backed repo discovery.
Each cron run: picks 1 category, searches GitHub for top-starred repos,
updates SQLite, exports repodata.json for the frontend.

Categories cycle: 9 categories × 20 repos = 180 repos total.
Cron runs every 3 hours → full refresh in ~27 hours.
Only repos above star thresholds are shown.
"""

import json, time, os, sqlite3
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR, 'repohub.db')
JSON_PATH = os.path.join(DIR, 'repodata.json')
LOG_FILE = os.path.join(DIR, 'fetch.log')
API = 'https://api.github.com'
TOKEN = (os.environ.get('GITHUB_TOKEN')
         or os.environ.get('GH_TOKEN')
         or '')
if not TOKEN:
    # Fallback: read from ~/.hermes/.env or ~/.bashrc
    for env_path in [os.path.expanduser('~/.hermes/.env'),
                     os.path.expanduser('~/.bashrc'),
                     os.path.expanduser('~/.profile')]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GITHUB_TOKEN=') or line.startswith('export GITHUB_TOKEN='):
                        TOKEN = line.split('=', 1)[1].strip('"').strip("'")
                        break
        if TOKEN:
            break

# ===== CATEGORIES with search queries =====
# Each entry: (id, label, icon, [search_queries], max_per_query, min_stars)
# Multiple queries per category → more results, deduplicated in DB
CATEGORIES = [
    ("llm", "LLM & Language", "🤖",
     ["topic:llm+stars:>5000", "topic:nlp+stars:>10000", "topic:large-language-model+stars:>5000"], 15, 3000),
    ("vision", "Computer Vision", "👁️",
     ["topic:computer-vision+stars:>5000", "topic:object-detection+stars:>5000", "topic:image-generation+stars:>5000"], 15, 3000),
    ("audio", "Audio & Speech", "🎵",
     ["topic:audio+stars:>3000", "topic:text-to-speech+stars:>2000", "topic:speech-recognition+stars:>3000"], 12, 2000),
    ("devtools", "Dev Tools", "🛠️",
     ["topic:cli+stars:>5000", "topic:developer-tools+stars:>3000", "topic:terminal+stars:>3000"], 15, 2000),
    ("frameworks", "Frameworks", "🧩",
     ["topic:deep-learning+stars:>5000", "topic:machine-learning+stars:>10000", "topic:neural-network+stars:>5000"], 15, 3000),
    ("mlops", "MLOps & Infra", "⚡",
     ["topic:devops+stars:>5000", "topic:monitoring+stars:>3000", "topic:kubernetes+stars:>5000"], 15, 3000),
    ("web", "Web Dev", "🌐",
     ["topic:react+stars:>10000", "topic:vue+stars:>5000", "topic:frontend+stars:>5000", "topic:css+stars:>5000"], 15, 3000),
    ("databases", "Databases", "🗄️",
     ["topic:database+stars:>5000", "topic:sql+stars:>3000", "topic:nosql+stars:>3000"], 15, 2000),
    ("creative", "Creative & Design", "🎨",
     ["topic:design+stars:>3000", "topic:visualization+stars:>3000", "topic:creative-coding+stars:>2000", "topic:animation+stars:>3000"], 12, 2000),
]

# Hard floor — repos below this won't be exported to JSON
MIN_STARS_EXPORT = 1000

# ===== DB =====

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            stars INTEGER DEFAULT 0,
            forks INTEGER DEFAULT 0,
            open_issues INTEGER DEFAULT 0,
            language TEXT,
            topics TEXT DEFAULT '[]',
            html_url TEXT DEFAULT '',
            updated_at TEXT,
            pushed_at TEXT,
            license TEXT,
            watchers INTEGER DEFAULT 0,
            size INTEGER DEFAULT 0,
            created_at TEXT,
            default_branch TEXT DEFAULT 'main',
            last_fetched TEXT
        );
        CREATE TABLE IF NOT EXISTS contributors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id TEXT NOT NULL,
            login TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            contributions INTEGER DEFAULT 0,
            FOREIGN KEY (repo_id) REFERENCES repos(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_repos_category ON repos(category);
        CREATE INDEX IF NOT EXISTS idx_repos_stars ON repos(stars DESC);
        CREATE INDEX IF NOT EXISTS idx_contributors_repo ON contributors(repo_id);
    """)
    # Ensure meta table has last_category
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('last_category', '-1')")
    conn.commit()
    return conn

def get_next_category(conn):
    """Get the next category to fetch. Cycles through all 9."""
    row = conn.execute("SELECT value FROM meta WHERE key='last_category'").fetchone()
    idx = (int(row['value']) + 1) % len(CATEGORIES)
    conn.execute("UPDATE meta SET value=? WHERE key='last_category'", (str(idx),))
    cat_id, cat_label, cat_icon, queries, limit, min_stars = CATEGORIES[idx]
    return idx, (cat_id, cat_label, cat_icon, queries, limit, min_stars)

# ===== GITHUB API =====

def log(m):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {m}')
    with open(LOG_FILE, 'a') as f: f.write(f'[{ts}] {m}\n')

def gh_get(url):
    """GET from GitHub API. Returns parsed JSON, None (404), or 'RATE' (403)."""
    headers = {'User-Agent': 'RepoHub/2.0', 'Accept': 'application/vnd.github.v3+json'}
    if TOKEN: headers['Authorization'] = f'token {TOKEN}'
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        if e.code in (403, 429):
            reset = e.headers.get('X-RateLimit-Reset', '?')
            log(f'  ⛔ Rate limited! Reset at {reset}')
            return 'RATE'
        if e.code == 404: return None
        log(f'  HTTP {e.code} on {url}')
        return None
    except Exception as e:
        log(f'  Error: {e}')
        return None

def search_repos(query, per_page=25, sort='stars', order='desc'):
    """Search GitHub repos. Returns list of repo dicts or 'RATE'."""
    url = f'{API}/search/repositories?q={query}&sort={sort}&order={order}&per_page={per_page}'
    data = gh_get(url)
    if data == 'RATE': return 'RATE'
    if not data or 'items' not in data: return []
    return data['items']

def safe_get(d, *keys, default=None):
    """Safely traverse nested dict."""
    for k in keys:
        if not isinstance(d, dict): return default
        d = d.get(k, None)
        if d is None: return default
    return d

# ===== FETCH & STORE =====

def fetch_and_store(conn, cat_id, cat_label, items):
    """Store search results in DB. Returns count of new/updated repos."""
    count = 0
    for item in items:
        stars = item.get('stargazers_count', 0)
        if stars < MIN_STARS_EXPORT:
            continue  # Skip repos below threshold

        rid = item.get('full_name') or f"{item['owner']['login']}/{item['name']}"
        owner = item['owner']['login']
        name = item['name']
        desc = item.get('description') or f'A popular open-source project.'
        topics = item.get('topics', [])
        license_spdx = safe_get(item, 'license', 'spdx_id')

        conn.execute("""
            INSERT OR REPLACE INTO repos
            (id, owner, name, category, description, stars, forks, open_issues,
             language, topics, html_url, updated_at, pushed_at, license,
             watchers, size, created_at, default_branch, last_fetched)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rid, owner, name, cat_id,
            desc, stars, item.get('forks_count', 0),
            item.get('open_issues_count', 0), item.get('language'),
            json.dumps(topics, ensure_ascii=False),
            item.get('html_url'), item.get('updated_at'),
            item.get('pushed_at'),            license_spdx if license_spdx else None,
            item.get('watchers_count', stars), item.get('size', 0),
            item.get('created_at'), item.get('default_branch', 'main'),
            datetime.now(timezone.utc).isoformat()
        ))

        # Fetch contributors (top 3)
        time.sleep(0.2)
        contribs = gh_get(f'{API}/repos/{rid}/contributors?per_page=3')
        if contribs and contribs != 'RATE' and isinstance(contribs, list):
            conn.execute("DELETE FROM contributors WHERE repo_id=?", (rid,))
            for c in contribs[:3]:
                conn.execute(
                    "INSERT INTO contributors (repo_id, login, avatar, contributions) VALUES (?,?,?,?)",
                    (rid, c['login'], c['avatar_url'], c['contributions'])
                )

        conn.commit()
        lang = item.get('language') or '?'
        log(f'  ✓ {rid} — {stars}★ {lang}')
        count += 1

    return count

# ===== EXPORT JSON =====

def export_json(conn):
    """Export all repos from DB → repodata.json, sorted by stars."""
    rows = conn.execute("""
        SELECT * FROM repos WHERE stars >= ? ORDER BY stars DESC
    """, (MIN_STARS_EXPORT,)).fetchall()

    repos_out = []
    for r in rows:
        contribs = conn.execute(
            "SELECT login, avatar, contributions FROM contributors WHERE repo_id=? ORDER BY contributions DESC",
            (r['id'],)
        ).fetchall()

        repos_out.append({
            'id': r['id'],
            'name': r['name'],
            'full_name': r['id'],
            'owner': r['owner'],
            'description': r['description'],
            'stars': r['stars'],
            'forks': r['forks'],
            'open_issues': r['open_issues'],
            'language': r['language'],
            'topics': json.loads(r['topics'] or '[]'),
            'category': r['category'],
            'html_url': r['html_url'],
            'updated_at': r['updated_at'],
            'pushed_at': r['pushed_at'],
            'license': r['license'],
            'watchers': r['watchers'],
            'size': r['size'],
            'contributors': [{
                'login': c['login'],
                'avatar': c['avatar'],
                'contributions': c['contributions']
            } for c in contribs],
            'created_at': r['created_at'],
            'default_branch': r['default_branch'],
        })

    output = {
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'total': len(repos_out),
        'total_categories': len(CATEGORIES),
        'repos': repos_out
    }
    with open(JSON_PATH, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    return len(repos_out)

# ===== MAIN =====

def main():
    conn = init_db()

    # Pick next category
    idx, (cat_id, cat_label, cat_icon, queries, limit, cat_min_stars) = get_next_category(conn)
    auth_str = '(authenticated)' if TOKEN else '(unauthenticated — 60/h limit)'

    log(f'[{cat_icon} {cat_label}] Searching ({len(queries)} queries) {auth_str}')

    all_items = []
    seen_ids = set()
    hit_rate_limit = False

    for qi, query in enumerate(queries):
        if hit_rate_limit:
            break

        log(f'  Query {qi+1}/{len(queries)}: {query}')
        items = search_repos(query, per_page=limit)

        if items == 'RATE':
            log(f'  ⛔ Rate limited on query {qi+1}! Stopping.')
            hit_rate_limit = True
            break

        if not items:
            log(f'  ⚠️ No results for this query')
            continue

        # Deduplicate across queries
        new_count = 0
        for item in items:
            rid = item.get('full_name') or f"{item['owner']['login']}/{item['name']}"
            if rid not in seen_ids:
                # Check against category min_stars
                stars = item.get('stargazers_count', 0)
                if stars >= cat_min_stars:
                    seen_ids.add(rid)
                    all_items.append(item)
                    new_count += 1

        log(f'  → {new_count} new repos (of {len(items)} total)')

    if not hit_rate_limit and not all_items:
        log(f'  ⚠️ No repos found for this category')
        stored = 0
    elif all_items:
        log(f'  Total unique repos: {len(all_items)}, fetching details & contributors...')
        stored = fetch_and_store(conn, cat_id, cat_label, all_items)
        log(f'  Stored {stored} repos in DB')
    else:
        stored = 0

    # Export JSON
    total_exported = export_json(conn)
    conn.close()

    status = 'RATE' if hit_rate_limit else 'OK'
    log(f'Done — [{cat_icon} {cat_label}] refreshed. DB has repos across {len(CATEGORIES)} categories.')
    log(f'JSON export: {total_exported} repos (min {MIN_STARS_EXPORT}★)')
    print(f'{status}:{cat_id}:{stored}:{total_exported}')

if __name__ == '__main__':
    main()
