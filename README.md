<div align="center">
  <h1>
    <img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" width="32" style="vertical-align: middle; margin-right: 8px;" alt=""/>
    RepoHub
  </h1>
  <p><strong>Discover top GitHub repositories, organized by category. <br/>Dark-themed, dynamic, and always fresh.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/repos-405+-brightgreen" alt="405+ repos"/>
    <img src="https://img.shields.io/badge/categories-9-blue" alt="9 categories"/>
    <img src="https://img.shields.io/badge/data-SQLite%20%2B%20JSON-orange" alt="SQLite + JSON"/>
    <img src="https://img.shields.io/badge/frontend-Chart.js-ff6384" alt="Chart.js"/>
    <img src="https://img.shields.io/github/actions/workflow/status/samedsemihs/repohub/ci.yml?label=CI" alt="CI"/>
  </p>
</div>

---

## Overview

RepoHub is a self-hosted GitHub repository explorer that discovers **the most-starred repositories** across 9 major categories using the GitHub Search API. The data updates automatically every 3 hours via a cron-driven pipeline.

### 🌟 Live Demo

Accessible on the local network via Tailscale:

```
http://repohub-server:8080
```

Or browse the source on GitHub: [samedsemihs/repohub](https://github.com/samedsemihs/repohub)

---

## Categories

| # | Category | Icon | Focus |
|---|----------|------|-------|
| 1 | **LLM & Language** | 🤖 | Large language models, NLP, transformers |
| 2 | **Computer Vision** | 👁️ | Object detection, image generation, CV |
| 3 | **Audio & Speech** | 🎵 | TTS, ASR, audio processing |
| 4 | **Dev Tools** | 🛠️ | CLI tools, developer tooling, terminal apps |
| 5 | **Frameworks** | 🧩 | Deep learning, ML, neural networks |
| 6 | **MLOps & Infra** | ⚡ | DevOps, monitoring, Kubernetes |
| 7 | **Web Dev** | 🌐 | React, Vue, frontend, CSS |
| 8 | **Databases** | 🗄️ | SQL, NoSQL, data stores |
| 9 | **Creative & Design** | 🎨 | Design systems, visualization, creative coding |

Each category searches GitHub with **3–4 curated queries**, pulling **12–15 repos per query**. Duplicates are deduplicated in the database. Only repos with **1,000+ stars** appear in the final output.

---

## 🏗 Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  GitHub      │     │  fetch_repos.py     │     │  index.html      │
│  Search API  │────▶│  (cron: every 3h)   │────▶│  (static site)   │
│  (REST v3)   │     │                     │     │                  │
└──────────────┘     │  ┌───────────────┐  │     │  Chart.js        │
                     │  │   repohub.db  │  │     │  Dark theme      │
                     │  │   (SQLite)    │  │     │  Responsive      │
                     │  └───────┬───────┘  │     └──────────────────┘
                     │          │          │
                     │  ┌───────▼───────┐  │
                     │  │ repodata.json │  │
                     │  │ (static JSON) │  │
                     │  └───────────────┘  │
                     └─────────────────────┘
```

### Data Pipeline

1. **`fetch_repos.py`** runs every 3 hours via systemd timer
2. Each run picks **1 category** to refresh (round-robin across 9)
3. Queries the **GitHub Search API** with category-specific queries
4. Stores results in **SQLite** (`repohub.db`) with deduplication
5. Exports to **`repodata.json`** — the static file the frontend reads
6. Full cycle completes in **~27 hours**

### Frontend

- **Single-file static HTML** — no build step, no framework
- **Chart.js** for visualizations (language distribution, star trends)
- **Geist font** by Vercel
- **Dark theme** with purple accent palette
- Fully responsive, mobile-friendly

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/samedsemihs/repohub.git
cd repohub

# 2. Set your GitHub token (required for API access)
export GITHUB_TOKEN="ghp_your_token_here"

# 3. Run the data fetcher
python3 fetch_repos.py

# 4. Serve the site
python3 -m http.server 8080

# → Open http://localhost:8080
```

### Configuration

Edit `fetch_repos.py` to customize:

- **Categories**: Add/remove entries in the `CATEGORIES` list
- **Star thresholds**: Change `MIN_STARS_EXPORT` (default: 1000)
- **Refresh rate**: Adjust the cron schedule in `repohub-fetch.timer`

---

## 📊 Data

405 repos across 9 categories, storing for each repo:

| Field | Description |
|-------|-------------|
| `name` | Repository name |
| `owner` | Owner (user or organization) |
| `description` | Project description |
| `stars` | Star count |
| `forks` | Fork count |
| `language` | Primary programming language |
| `topics` | GitHub topics |
| `license` | License type |
| `html_url` | GitHub URL |

---

## ⚙️ CI/CD

| Stage | System | What it does |
|-------|--------|-------------|
| **CI** | GitHub Actions (`.github/workflows/ci.yml`) | Validates Python syntax, JSON structure, HTML integrity on every push/PR |
| **Data refresh** | systemd timer (`repohub-fetch.timer`) | Runs `fetch_repos.py` every 3 hours |
| **Auto-deploy** | systemd timer (`repohub-deploy.timer`) | Polls GitHub every 2 minutes, pulls on new commits |

### Self-Hosted Deployment

```bash
# Systemd services (for Linux servers)
cp repohub-web.service repohub-webhook.service repohub-deploy.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now repohub-web.service repohub-deploy.timer
```

> ⚠️ Server-specific files (deploy scripts, webhook receiver) are kept local — they are not pushed to this public repository.

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3 — `urllib`, `sqlite3` |
| **Database** | SQLite (WAL mode) |
| **Frontend** | Vanilla HTML/CSS/JS |
| **Visualization** | Chart.js 4 |
| **Font** | Geist (Vercel) |
| **API** | GitHub REST API v3 |
| **Serving** | Python `http.server` / systemd |
| **CI** | GitHub Actions |
| **CD** | systemd timer + deploy hook |

---

## 📄 License

MIT — feel free to fork, modify, and use.

---

<div align="center">
  <sub>Built with ❤️ and a lot of API calls.</sub>
</div>
