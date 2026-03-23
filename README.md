<p align="center">
  <img src="assets/logo.svg" alt="PageVault" width="380"/>
</p>

<p align="center">
  <strong>A self-hosted, local Goodreads alternative.</strong><br/>
  Scan ISBN barcodes with your phone · Fetch covers & metadata automatically · Keep your reading life private.
</p>

<p align="center"><strong>Latest release:</strong> v1.5.0</p>

<br/>

<p align="center">
  <a href="https://github.com/ChristianAbele02/PageVault/actions/workflows/ci.yml">
    <img src="https://github.com/ChristianAbele02/PageVault/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  &nbsp;
  <a href="https://github.com/ChristianAbele02/PageVault/releases">
    <img src="https://img.shields.io/github/v/tag/ChristianAbele02/PageVault?sort=semver&color=c8913a&label=release" alt="Release"/>
  </a>
  &nbsp;
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Flask-3.x-black?logo=flask" alt="Flask"/>
  &nbsp;
  <img src="https://img.shields.io/badge/database-SQLite-blue?logo=sqlite" alt="SQLite"/>
  &nbsp;
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
  </a>
</p>

---

## What is PageVault?

PageVault is a lightweight, **100% local** book catalog that runs on your own machine. Point your phone camera at any ISBN barcode — the app fetches the title, author, cover, and metadata instantly, and stores everything in a single SQLite file that never leaves your device.

Think Goodreads, but yours.

Made with love for my wife Emili. ❤️

---

## Features

**📷 Scan any book in seconds**
Open PageVault on your phone browser, tap the scan button, and point at the barcode. No app install. No account.

**📚 Automatic metadata**
Title, author, cover image, publisher, year, and page count — fetched with a multi-provider fallback chain: [Open Library Books API](https://openlibrary.org/dev/docs/api/books) → [Google Books API](https://developers.google.com/books) → [Open Library Search API](https://openlibrary.org/dev/docs/api/search) → [Crossref API](https://api.crossref.org) + [Open Library Covers API](https://openlibrary.org/dev/docs/api/covers) for cover rescue.

**⭐ Ratings, reviews & quotes**
Give each book a half-star rating (0.5–5.0), add written notes, and save favourite quotes with page numbers. Build up a reading journal over time.

**📖 Reading progress (current page)**
Save page progress together with each review entry and see a live progress bar on the library grid.

**🔖 Reading status**
Track every book as *Want to Read*, *Currently Reading*, *Read*, or *Did Not Finish (DNF)*.

**🗂️ Custom shelves / lists**
Create as many named shelves as you want, attach an optional logo URL, and place books in multiple shelves.

**🏷️ Genre tags**
Attach multiple genre tags to each book for cleaner categorization and better discovery.
Tags are managed as interactive chips (add/remove individually), with duplicate protection and a max of 10 tags.

**🌗 Day/Night library themes**
Dark mode (default) uses a candlelit library look; light mode switches to a daylight library style.
Theme preference is remembered locally.

**🔍 Search & filter**
Filter by status, author, genre tag, shelf, and text search.

**📊 Advanced stats dashboard with Plotly**
Open `/stats` for 20+ interactive analytics charts: books/pages by status (including DNF), top genres/authors, rating distribution, monthly activity, format breakdown, decade distribution, publisher insights, community vs personal ratings, daily reading pace, library growth, reading activity heatmap (GitHub-style), rating trend over time, genre trends by year, time-to-finish distribution, reading speed per book, shelf breakdown, longest unread shelf, and active loans tracker.
Includes preset + custom date range filters, format and language filters, and automatic dark/light theme inheritance.

**🎯 Annual goals & reading sessions**
Set yearly targets for books/pages, log reading sessions with start/end pages and time, and track pace, streak, and speed metrics directly in analytics.

**📚 Series, reading history & book metadata**
Track series name and number, log re-reads with start/finish dates, record book format (physical/ebook/audiobook), community ratings from Google Books, and owned/wishlist status.

**🧪 Import mapping preview + dry-run**
Preview CSV imports with optional column mapping before writing data, then run a safe dry-run to verify import/update counts.

**🛠️ Metadata repair jobs**
Run repair jobs for missing metadata fields and inspect job history/status from the dashboard.

**🧯 One-click backup/restore workflow**
Download a ZIP backup, validate restore archives, and apply restores from inside the app.

**📱 PWA-ready baseline**
Manifest + service worker support enables install-friendly behavior and caching for core pages.

**🔄 Metadata refresh**
Reload metadata for all saved books without touching your reviews, star ratings, shelves, or manual tags.

**📤📥 CSV export/import**
Export your full library to CSV and import CSV files back into PageVault. Goodreads CSV export files are supported.

**💾 Fully private, fully local**
Your entire library lives in one file: `pagevault.db`. Back it up by copying it. Restore by pasting it back.

**🐳 Docker ready**
One command to run, persistent volume for your data.

---

## Quick Start

### Python (recommended)

> Requires Python 3.10 or newer.

```bash
git clone https://github.com/ChristianAbele02/PageVault.git
cd pagevault
pip install .
python app.py

```

Open **http://localhost:5000** in your browser.

### Docker

```bash
git clone https://github.com/ChristianAbele02/PageVault.git
cd pagevault
docker compose up -d
```

PageVault starts at **http://localhost:5000**. Data persists in a named Docker volume.

---

## Admin Panel

- Visit **`/admin/login`**.
- A random one-time password is printed to the console on startup when `PAGEVAULT_ADMIN_PASSWORD` is not set.
- Set `PAGEVAULT_ADMIN_PASSWORD` in your environment or `.env` to make it permanent.

## Core Files Explained

### Coverage Files (`.coverage`, `coverage.xml`)

- Generated by `pytest-cov` during test runs.
- `.coverage` stores raw coverage data.
- `coverage.xml` is used by CI/reporting tools (for example Codecov) to show test coverage in pull requests.

### `pagevault.db`

- Main SQLite database file for your actual library data.
- Contains books, reviews, shelves, tags, goals, sessions, jobs, and related metadata.
- Back this file up regularly (or use built-in backup/restore endpoints).

---

## Accessing from your phone

Find your computer's local IP, then open `http://YOUR-IP:5000` on your phone (same Wi-Fi network).

```bash
# macOS
ipconfig getifaddr en0

# Windows (in PowerShell)
ipconfig

# Linux
hostname -I
```

> **Safari on iOS?** Apple requires HTTPS for camera access on non-localhost addresses. See the [HTTPS setup guide](#https-setup-for-ios-safari) below.

---

## Usage

### Adding a book

| Step | Action |
|------|--------|
| 1 | Tap **+** (bottom right) |
| 2 | Tap **Scan ISBN Barcode** and allow camera access |
| 3 | Point at the barcode on the back cover |
| 4 | Confirm the fetched details and tap **Add to My Shelf** |

Can't scan? Type the ISBN manually and tap **Look up**. If the book isn't in Open Library, fill in the title and author yourself.

### Rating a book

Tap any book → pick a star rating → write an optional note → **Save Review**. Add as many notes as you like over time.

Review timestamps are displayed in `DD.MM.YYYY HH:MM` format.

### Theme switching

- Use the **Light/Dark** toggle in the header.
- Dark mode is the default appearance.
- The selected theme is persisted in your browser.

### Stats dashboard

- Open **http://localhost:5000/stats** from the main **Stats** link in the header.
- Use quick presets (30/90/180/365 days, YTD) or a custom date range.
- Charts are powered by Plotly and update from `/api/stats/analysis`.
- The stats page follows your saved Light/Dark theme automatically.
- Saved views persist locally and can be shared via range URL parameters.

### Goal, session, and operations panel

- Use the dashboard operation cards to set annual goals and log reading sessions.
- Run metadata repair jobs for incomplete book metadata and inspect latest job status.
- Use the CSV wizard controls to preview mapping, dry-run, then import.
- Use backup/restore controls to download backup ZIPs and validate/apply restore archives.

### Genre tag chips

- Add tags with **Enter**, **comma (,)**, or **Tab**.
- Remove tags with the **✕** on each chip.
- Duplicate tags are prevented and show an inline message.
- Max 10 tags per book, with a live counter (`x/10`).

### Exporting your library

```bash
curl http://localhost:5000/api/export > my_library.json
```

### Exporting / importing CSV

- Use the floating **⇩** button next to **+** to export CSV.
- Use the floating **⇧** button next to **+** to import a CSV file.
- Goodreads CSV exports are supported (`My Books` export format).

### Reloading metadata for all books

- Use the **Reload metadata** button in the top controls.
- This updates only core metadata fields (title, author, cover, description, publisher, year, pages, language, genre).
- Reviews/stars, shelves, and manual tags stay untouched.

---

## HTTPS Setup for iOS Safari

Safari requires HTTPS for camera access when the host isn't `localhost`. The quickest fix:

```bash
# Install mkcert (creates locally-trusted certificates)
brew install mkcert          # macOS
# or: https://github.com/FiloSottile/mkcert#installation

mkcert -install
mkcert localhost 127.0.0.1 192.168.x.x   # replace with your local IP
```

Then edit the last line of `app.py`:

```python
app.run(host="0.0.0.0", port=5000, ssl_context=("localhost+2.pem", "localhost+2-key.pem"))
```

Open `https://192.168.x.x:5000` on your iPhone.

---

## REST API

All responses are JSON. The base URL is `http://localhost:5000`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/books` | List books — supports `?status=`, `?author=`, `?genre=`, `?shelf_id=`, `?q=`, `?sort=`, `?order=` |
| `POST` | `/api/books` | Add a book `{ isbn, status?, genre_tags?, shelf_ids?, book_data? }` |
| `GET` | `/api/books/:id` | Book detail including all reviews |
| `PATCH` | `/api/books/:id` | Update `status`, `title`, `author`, `description`, `genre_tags`, `shelf_ids` |
| `DELETE` | `/api/books/:id` | Delete a book (reviews cascade) |
| `GET` | `/api/shelves` | List custom shelves with book counts |
| `POST` | `/api/shelves` | Create shelf `{ name, logo_url? }` |
| `PATCH` | `/api/shelves/:id` | Rename shelf and/or update logo URL |
| `DELETE` | `/api/shelves/:id` | Delete shelf (book relations cascade) |
| `GET` | `/api/lookup/:isbn` | Preview ISBN metadata without saving |
| `POST` | `/api/books/refresh` | Refresh metadata for all books (preserves reviews/tags/shelves) |
| `POST` | `/api/books/:id/reviews` | Add review `{ rating?, comment? }` |
| `DELETE` | `/api/books/:id/reviews/:rid` | Remove a review |
| `GET` | `/api/stats` | Library statistics |
| `GET` | `/api/stats/analysis` | Plot-ready analytics dataset (supports `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`) |
| `GET` | `/api/goals/current` | Fetch yearly reading goal + progress (`?year=` optional) |
| `PUT` | `/api/goals/current` | Upsert yearly reading goal `{ goal_year, target_books, target_pages }` |
| `POST` | `/api/books/:id/sessions` | Add reading session `{ start_page, end_page, minutes_spent, session_date?, notes? }` |
| `GET` | `/api/sessions` | List reading sessions (supports `?start_date=&end_date=`) |
| `POST` | `/api/metadata/repair` | Run repair job for books missing metadata |
| `GET` | `/api/metadata/jobs` | List recent metadata jobs |
| `GET` | `/api/metadata/jobs/:id` | Metadata job detail with per-book items |
| `GET` | `/api/export` | Full library export as JSON |
| `GET` | `/api/export/csv` | Export full library as CSV |
| `POST` | `/api/import/csv/preview` | Preview CSV import result (`mapping` optional) |
| `POST` | `/api/import/csv` | Import PageVault or Goodreads-compatible CSV |
| `GET` | `/api/backup/download` | Download ZIP backup of current DB |
| `POST` | `/api/backup/restore/validate` | Validate backup archive and return summary |
| `POST` | `/api/backup/restore/apply` | Apply backup archive to current DB |

**Example — add a book and review it:**

```bash
# Add by ISBN (metadata fetched automatically)
curl -X POST http://localhost:5000/api/books \
  -H "Content-Type: application/json" \
  -d '{"isbn": "9780451524935", "status": "read"}'

# Add a review
curl -X POST http://localhost:5000/api/books/1/reviews \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "comment": "Essential reading."}'
```

---

## Backup & Restore

Everything is in one file and now also exposed via one-click API/UI workflows.

### In-app/API backup workflow

```bash
# Download backup archive
curl -L http://localhost:5000/api/backup/download -o pagevault_backup.zip

# Validate restore archive
curl -X POST http://localhost:5000/api/backup/restore/validate \
  -F "file=@pagevault_backup.zip"

# Apply restore archive
curl -X POST http://localhost:5000/api/backup/restore/apply \
  -F "file=@pagevault_backup.zip"
```

### Manual file backup

```bash
# Backup
cp pagevault.db pagevault_backup.db

# Restore
cp pagevault_backup.db pagevault.db
```

With Docker:

```bash
# Backup
docker cp pagevault:/data/pagevault.db ./pagevault_backup.db

# Restore
docker cp ./pagevault_backup.db pagevault:/data/pagevault.db
```

---

## Development

```bash
# Install dev dependencies (pytest, ruff, mypy)
make dev

# Run tests
make test

# Run tests with coverage
make coverage

# Lint
make lint

# Auto-format
make format
```

## Core Infrastructure

PageVault is now organized into a lightweight core package so features can grow without a single massive script.

- **`app.py`**: app factory + dependency wiring + entrypoint.
- **`pagevault_core/api.py`**: REST blueprint (`/api`) with all route handlers.
- **`pagevault_core/db.py`**: SQLite lifecycle (`get_db`, hooks, schema bootstrap).
- **`pagevault_core/metadata.py`**: ISBN metadata providers + parallel merge chain + TTL cache.
- **`pagevault_core/utils.py`**: shared validation and parsing helpers.

### Metadata fallback chain

When you look up an ISBN (or run metadata refresh), PageVault:

1. Starts with Open Library Books API as primary source.
2. If fields are missing, runs additional fallbacks in parallel: Google Books, Open Library Search, and Crossref.
3. If cover image is still missing, queries Open Library Covers API.

Fields are merged progressively so missing values are filled without discarding good data from earlier providers.

### Metadata lookup cache

- ISBN lookups are cached in-process with a lightweight TTL cache to speed up repeated lookups during refresh/import.
- Default TTL: `900` seconds (15 minutes).
- Default max cache size: `2000` ISBN entries.
- Configure via environment variables:
  - `PAGEVAULT_LOOKUP_CACHE_TTL_SECONDS`
  - `PAGEVAULT_LOOKUP_CACHE_MAX_ITEMS`

### CSV architecture

- **Export (`/api/export/csv`)** writes library rows including book metadata, shelves, tags, and review summary fields.
- **Import (`/api/import/csv`)** accepts both PageVault CSV and Goodreads-compatible CSV headers.
- Import merges metadata safely and preserves existing data where appropriate.

### Project layout

```
pagevault/
├── app.py                        App factory + dependency wiring + entrypoint
├── config.py                     Config resolution + admin password bootstrap
├── pagevault_core/
│   ├── __init__.py
│   ├── api.py                    API blueprint and route handlers
│   ├── db.py                     SQLite connection + schema bootstrap
│   ├── metadata.py               Multi-provider lookup + parallel merge + TTL cache
│   ├── utils.py                  Shared parsing/validation helpers
│   └── services/
│       ├── admin_service.py      Admin console backend
│       └── recommendations.py   Local similarity-based recommendations
├── templates/
│   ├── index.html                Main library frontend
│   └── stats.html                Stats dashboard (Plotly)
├── static/                       PWA manifest, service worker, icons
├── tests/
│   ├── conftest.py               Shared pytest fixtures
│   └── test_api.py               API + CSV + fallback coverage
├── assets/
│   ├── logo.svg                  Full wordmark logo
│   └── icon.svg                  Square icon (GitHub avatar, favicon)
├── docs/                         GitHub Pages site
├── .github/
│   ├── workflows/ci.yml          GitHub Actions: test · lint · typecheck · Docker
│   ├── ISSUE_TEMPLATE/           Bug report & feature request forms
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── .devcontainer/
│   └── devcontainer.json         One-click GitHub Codespaces setup
├── Dockerfile                    Multi-stage, non-root, gunicorn
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

---

## Roadmap

- [ ] Goodreads import mapping presets (regional variants)
- [x] Annual reading goal tracker
- [x] Optional password protection (admin console)
- [x] Mobile QR connect for same-network access
- [x] Local book recommendations

Have an idea? [Open a feature request](https://github.com/ChristianAbele02/PageVault/issues/new/choose).

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

Found a security issue? See [SECURITY.md](SECURITY.md) for how to report it privately.

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Built with <a href="https://flask.palletsprojects.com">Flask</a> ·
  <a href="https://www.sqlite.org">SQLite</a> ·
  <a href="https://openlibrary.org">Open Library API</a>
  <br/><br/>
  <img src="assets/icon.svg" width="28" alt="PageVault icon"/>
</p>
