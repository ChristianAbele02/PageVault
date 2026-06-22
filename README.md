<p align="center">
  <img src="assets/logo.svg" alt="PageVault" width="380"/>
</p>

<p align="center">
  <strong>A self-hosted, local Goodreads alternative.</strong><br/>
  Scan ISBN barcodes with your phone · Fetch covers & metadata automatically · Keep your reading life private.
</p>

<p align="center"><strong>Latest release:</strong> v1.6.0</p>

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

**📖 Built-in e-book reader**
Attach an EPUB or PDF to any book (drag & drop in the detail view) and read it right in the app — in a full-screen reader dialog or on the dedicated `/reader` page. Your reading position is saved automatically and synced into the book's page progress.

**🌍 English / German interface**
Toggle the interface language (EN/DE) from the header on every page. The preference is remembered locally.

**🤝 Local recommendations**
Each book's detail view suggests similar books from your own library based on shared author, genres, and tags — computed locally, no external service.

**📱 Mobile QR connect**
Tap **Mobile** in the header to show a QR code that opens PageVault on your phone over the same Wi-Fi.

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

**Windows (PowerShell):**

```powershell
git clone https://github.com/ChristianAbele02/PageVault.git
cd PageVault
python -m venv .pagevault
.\.pagevault\Scripts\activate
pip install .
python app.py
```

**macOS / Linux:**

```bash
git clone https://github.com/ChristianAbele02/PageVault.git
cd PageVault
python3 -m venv .pagevault
source .pagevault/bin/activate
pip install .
python app.py
```

Open **http://localhost:5000** in your browser. The startup banner also prints a
same-Wi-Fi URL for your phone, and — if `PAGEVAULT_ADMIN_PASSWORD` is not set —
a one-time admin password.

> Optional: copy `.env.example` to `.env` and set `SECRET_KEY` and
> `PAGEVAULT_ADMIN_PASSWORD` before exposing PageVault to your network.

### Docker

```bash
git clone https://github.com/ChristianAbele02/PageVault.git
cd PageVault
docker compose up -d
```

PageVault starts at **http://localhost:5000**. Data persists in a named Docker volume.

### Desktop app (Windows)

Prefer a double-click program with no terminal and no Python install? Download
**`PageVault-Setup-<version>.exe`** from the
[latest release](https://github.com/ChristianAbele02/PageVault/releases), run it,
and launch PageVault from the Start menu. It opens in its own window instead of a
browser tab.

- The installer is per-user and needs no administrator rights.
- If the build is unsigned, Windows SmartScreen shows an "unknown publisher" prompt on
  first run; choose **More info → Run anyway**. See [Code signing](#code-signing-optional)
  to remove it.
- Rendering uses **WebView2**, which ships with Windows 11. On Windows 10, install
  the [Evergreen WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
  once if prompted.
- Your library lives in `%LOCALAPPDATA%\PageVault` (database, e-book files, log)
  and survives uninstalling or reinstalling the app.
- Prefer a no-install copy? The release also ships a portable
  `PageVault-<version>-portable-win64.zip`; unzip and run `PageVault.exe`.

**Build it yourself** (from a source checkout, on Windows):

```powershell
make desktop-deps   # installs pywebview, waitress, PyInstaller, Pillow
make exe            # writes dist\PageVault\PageVault.exe
```

`make desktop` runs the same native app directly from source without freezing it.

### Code signing (optional)

Unsigned builds trigger the Windows SmartScreen "unknown publisher" prompt. Three ways
to address it, by audience:

| Goal | Approach |
|---|---|
| **Trust on your own PCs** | Run `tools/make_selfsigned_cert.ps1` to create a self-signed certificate, then import its `.cer` into *Trusted Root Certification Authorities* and *Trusted Publishers* on each machine. Clears the warning for your household only. |
| **Public, free** | [SignPath](https://signpath.io) provides free code signing for open-source projects. |
| **Public, commercial** | An OV/EV certificate from a CA (DigiCert, Sectigo, …); EV certificates gain SmartScreen reputation immediately. |

The release workflow signs the executable and the installer automatically **when** two
repository secrets are present:

- `WINDOWS_CERT_BASE64` — base64 of your code-signing `.pfx`
- `WINDOWS_CERT_PASSWORD` — its password

Without them the build still runs, just unsigned. The private key stays in GitHub Secrets
and is never committed (`*.pfx`, `*.cer`, and `certs/` are git-ignored). To sign a local
build by hand:

```powershell
.\tools\sign_windows.ps1 -Path dist\PageVault\PageVault.exe `
  -PfxPath certs\pagevault-codesign.pfx -Password (Read-Host -AsSecureString)
```

`sign_windows.ps1` uses `signtool` when the Windows SDK is installed and otherwise falls
back to PowerShell's built-in `Set-AuthenticodeSignature`, so it works without the SDK.

---

## Admin Panel

- Visit **`/admin/login`**.
- A random one-time password is printed to the console on startup when `PAGEVAULT_ADMIN_PASSWORD` is not set.
- Set `PAGEVAULT_ADMIN_PASSWORD` in your environment or `.env` to make it permanent.
- In the **desktop app** there is no console, so a password is generated once and
  saved to `%LOCALAPPDATA%\PageVault\admin_password.txt` (alongside a persisted
  `secret_key` that keeps you logged in across restarts).

## Your data on disk

| File / folder | What it is |
|---|---|
| `pagevault.db` | Your entire library — books, reviews, shelves, tags, goals, sessions. **Back this up.** |
| `book_files/` | Uploaded e-book files (EPUB/PDF), one per book, created on first upload. |
| `pagevault.log` | Rotating application log (10 MB × 5 backups). Safe to delete. |

From a source checkout these sit next to `app.py`. The **desktop app** keeps them
(plus `secret_key` and `admin_password.txt`) in `%LOCALAPPDATA%\PageVault`. Set
`PAGEVAULT_DATA_DIR` to override the location for either.

Everything else that appears after running the app or the tests
(`__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `build/`,
`*.egg-info/`, `.coverage`, `coverage.xml`) is a regenerable artifact and is
git-ignored — delete freely.

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

### Reading e-books

| Step | Action |
|------|--------|
| 1 | Open a book's detail view and find the **E-Book File** section |
| 2 | Drop an EPUB/PDF onto the zone (or **Browse Files…**) |
| 3 | Click **Open** — or use the 📖 **Read** overlay on the book cover |
| 4 | Navigate with the on-screen arrows or ← / → keys; adjust font size with A− / A+ |

Your position is saved automatically (and converted into page progress when the
book has a page count). The **Reader** link in the header opens a dedicated
full-page reader with a searchable sidebar of all your e-books.

### Language switching

Use the **DE/EN** toggle in the header to switch the interface between English
and German. The choice is stored in your browser.

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
| `POST` | `/api/books/refresh/start` | Same as a background job with progress (poll `/api/metadata/jobs/:id`) |
| `POST` | `/api/books/:id/reviews` | Add review `{ rating?, comment?, current_page? }` |
| `DELETE` | `/api/books/:id/reviews/:rid` | Remove a review |
| `POST` | `/api/books/:id/file` | Upload an EPUB/PDF e-book file (multipart `file`) |
| `GET` | `/api/books/:id/file` | Download/stream the attached e-book file |
| `DELETE` | `/api/books/:id/file` | Remove the attached e-book file |
| `PATCH` | `/api/books/:id/position` | Save reader position `{ cfi?, percent?, current_page? }` |
| `GET` | `/api/books/:id/recommendations` | Similar books from your own library (`?limit=`) |
| `GET` | `/api/books/:id/quotes` · `POST` · `DELETE /:qid` | Quotes & highlights per book |
| `GET` | `/api/books/:id/reads` · `POST` · `DELETE /:rid` | Re-read history per book |
| `GET` | `/api/mobile/connect` | Same-network URL for the mobile QR code |
| `POST` | `/api/admin/login` · `/api/admin/logout` | Admin session management |
| `GET` | `/api/admin/diagnostics` · `/api/admin/logs` | Admin diagnostics & log tail (admin only) |
| `GET` | `/api/stats` | Library statistics |
| `GET` | `/api/stats/analysis` | Plot-ready analytics dataset (supports `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`) |
| `GET` | `/api/goals/current` | Fetch yearly reading goal + progress (`?year=` optional) |
| `PUT` | `/api/goals/current` | Upsert yearly reading goal `{ goal_year, target_books, target_pages }` |
| `POST` | `/api/books/:id/sessions` | Add reading session `{ start_page, end_page, minutes_spent, session_date?, notes? }` |
| `GET` | `/api/sessions` | List reading sessions (supports `?start_date=&end_date=`) |
| `POST` | `/api/metadata/repair` | Run repair job for books missing metadata |
| `POST` | `/api/metadata/repair/start` | Same as a background job with progress (poll `/api/metadata/jobs/:id`) |
| `GET` | `/api/metadata/jobs` | List recent metadata jobs |
| `GET` | `/api/metadata/jobs/:id` | Metadata job detail with per-book items |
| `GET` | `/api/export` | Full library export as JSON |
| `GET` | `/api/export/csv` | Export full library as CSV |
| `POST` | `/api/import/csv/preview` | Preview CSV import result (`mapping`, settings optional) |
| `POST` | `/api/import/csv` | Import PageVault or Goodreads-compatible CSV (synchronous) |
| `POST` | `/api/import/csv/start` | Start a background import job with progress (poll `/api/metadata/jobs/:id`) |
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

The `Makefile` bundles common developer commands for environments with GNU
`make` (macOS, Linux, Git Bash, Codespaces). On Windows PowerShell, use the
plain commands in the right column — they are identical.

| `make` shortcut | Plain command (works everywhere) |
|---|---|
| `make dev` | `pip install ".[dev,prod]"` |
| `make run` | `python app.py` |
| `make test` | `python -m pytest` |
| `make coverage` | `python -m pytest --cov=app --cov-report=html` |
| `make lint` | `python -m ruff check .` |
| `make format` | `python -m ruff format .` then `python -m ruff check --fix .` |
| `make clean` | removes caches, build artifacts, and coverage files |

Type checking runs with `python -m mypy app.py config.py pagevault_core`.

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

Fields are merged progressively so missing values are filled without discarding good data from earlier providers. Community ratings come from Open Library's crowd-sourced ratings (CC0, no key required) with Google Books as a second source; series info comes from Google Books only.

Books without a real ISBN (Goodreads imports store those under a `GR…` placeholder id) are resolved by a title/author search against Open Library and Google Books instead.

#### Google Books rate limits

Google Books has a very small unauthenticated quota — bulk jobs over a large
library will hit `HTTP 429: Too Many Requests` without an API key. PageVault
throttles requests and pauses Google Books lookups after a 429, and covers,
descriptions, and community ratings work without Google thanks to Open
Library. For maximum coverage (descriptions and series info especially) you
can still set a free API key:

1. Create a project at <https://console.cloud.google.com/apis/credentials>, enable the **Books API**, and create an API key.
2. Put it in your `.env`: `PAGEVAULT_GOOGLE_BOOKS_API_KEY=your-key`.
3. Re-run **Tools → Repair missing metadata** — it backfills missing covers, descriptions, community ratings, and series info.

Tuning knobs: `PAGEVAULT_GOOGLE_BOOKS_MIN_INTERVAL_SECONDS` (default `0.6`) and
`PAGEVAULT_GOOGLE_BOOKS_COOLDOWN_SECONDS` (default `120`).

### Metadata lookup cache

- ISBN lookups are cached in-process with a lightweight TTL cache to speed up repeated lookups during refresh/import.
- Default TTL: `900` seconds (15 minutes).
- Default max cache size: `2000` ISBN entries.
- Configure via environment variables:
  - `PAGEVAULT_LOOKUP_CACHE_TTL_SECONDS`
  - `PAGEVAULT_LOOKUP_CACHE_MAX_ITEMS`

### CSV architecture

- **Export (`/api/export/csv`)** writes library rows including book metadata, shelves, tags, and review summary fields.
- **Import** accepts both PageVault CSV and Goodreads-compatible CSV headers, with
  three settings in the wizard: fetch metadata online, import books without ISBN
  (identified by their Goodreads Book Id), and keep Goodreads dates.
- Goodreads specifics handled automatically: Excel-quoted ISBNs (`="..."`),
  `Date Added`/`Date Read` (preserved as added/finish dates plus reading history),
  `Binding` → book format, `Owned Copies`, ratings/reviews, and repair of
  double-encoded text ("BrontÃ«" → "Brontë"). Status shelves like `to-read`
  become reading statuses, not custom shelves.
- Large imports run as a background job with a live progress bar; re-imports are
  idempotent (no duplicate books, reviews, or reading history).

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
│   ├── stats.html                Stats dashboard (Plotly)
│   ├── reader.html               Full-page e-book reader (EPUB/PDF)
│   ├── admin.html                Admin dashboard
│   └── admin_login.html          Admin login
├── static/                       PWA manifest, service worker, icons, i18n.js (EN/DE)
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
- [x] Built-in e-book reader (EPUB/PDF) with position sync
- [x] English/German interface translation
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
