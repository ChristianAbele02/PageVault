<p align="center">
  <img src="assets/logo.svg" alt="PageVault" width="380"/>
</p>

<p align="center">
  <strong>A self-hosted, fully local Goodreads alternative.</strong><br/>
  Scan ISBN barcodes · fetch covers &amp; metadata automatically · keep your reading life private.
</p>

<p align="center"><strong>Latest release:</strong> v1.9.2 · fresh app icon · installable <a href="https://github.com/ChristianAbele02/PageVault/releases">Android APK</a></p>

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
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"/></a>
</p>

---

## What is PageVault?

PageVault is a book catalogue that runs entirely on your own hardware. Point a camera at
any ISBN barcode and it fetches the title, author, cover, and metadata, then stores
everything in a single SQLite file that never leaves your device. Think Goodreads, but
yours, with no account and no cloud.

The same Flask app powers three builds: a **web server**, a **native desktop app**, and an
**Android app**. All three share one codebase and one feature set.

Made with love for my wife Emili. ❤️

---

## Three ways to run it

| Build | Best for | How |
|---|---|---|
| **Web server** | Any device on your network, self-hosting, Docker | `python app.py`, or `docker compose up` |
| **Desktop app** (Windows) | A double-click program, no terminal | Install the `.exe` from [Releases](https://github.com/ChristianAbele02/PageVault/releases) |
| **Android app** | A phone app that runs fully offline on-device | Install the APK from [Releases](https://github.com/ChristianAbele02/PageVault/releases), or build `android/` yourself ([guide](android/README.md)) |

The web and desktop builds also let a phone scan barcodes over the LAN; the Android build
puts the whole app on the phone, using its camera directly with no network needed (except
to look up metadata).

---

## Features

**Scanning &amp; metadata.** Scan an ISBN with the camera (or type it) and PageVault fills in
title, author, cover, publisher, year, page count, genre, language, and community rating
through a multi-provider fallback chain: Open Library → Google Books → Open Library Search →
Crossref, with Open Library Covers for cover rescue. German-group ISBNs (978-3) also query
the Deutsche Nationalbibliothek. Books without a real ISBN are resolved by title/author.

**Reading tracking.** Status (*want to read* / *reading* / *read* / *DNF*), per-review page
progress with a live progress bar, reading sessions (pages + time), annual goals with pace
and streak metrics, re-read history with dates, series name/number, and format
(physical / e-book / audiobook) with owned/wishlist state.

**Reviews, ratings &amp; quotes.** Half-star ratings (0.5–5.0), written notes over time, and
saved quotes with page numbers.

**Built-in e-book reader.** Attach an EPUB or PDF to any book and read it in-app, in a
full-screen dialog or on the dedicated `/reader` page. Position is saved automatically and
folded into page progress. An **OPDS feed** (`/opds`) also lets external e-reader apps
(KOReader, Moon+ Reader) browse and download your library.

**Organisation, search &amp; discovery.** Custom shelves (with optional logos), genre-tag
chips (deduped, max 10), filtering by status/author/genre/shelf, **full-text search across
book metadata, your review notes, and saved quotes** (SQLite FTS5), and local similarity
recommendations computed from your own library, no external service.

**Stats dashboard.** `/stats` renders 20+ interactive Plotly charts: books/pages by status,
top genres and authors, rating distribution, monthly activity, format and decade breakdowns,
publisher insights, community-vs-personal ratings, reading pace and speed, a GitHub-style
activity heatmap, library growth, rating and genre trends, time-to-finish, shelf breakdown,
and active loans. Preset and custom date ranges; inherits your light/dark theme.

**Import / export / backup.** CSV export and import (Goodreads `My Books` format supported,
with mapping preview and dry-run), full JSON export, and a one-click ZIP backup / validated
restore. Large imports run as background jobs with a progress bar and are idempotent.

**Interface.** English / German toggle and light / dark library themes, both remembered
locally. Responsive layout with native-app polish on the Android build.

**Fully local &amp; offline-capable.** Your whole library is one `pagevault.db` file. All
front-end libraries and fonts are vendored (no CDN at runtime), and the app shell and book
covers are cached locally (a service worker plus an on-disk cover cache), so everything
except online metadata lookup works offline.

---

## Quick start

### Web server (Python)

Requires Python 3.10+.

```bash
git clone https://github.com/ChristianAbele02/PageVault.git
cd PageVault
python -m venv .pagevault
.\.pagevault\Scripts\activate      # Windows;  source .pagevault/bin/activate on macOS/Linux
pip install .
python app.py
```

`python app.py` serves over **HTTPS by default** so phones can use the camera scanner
(browsers only allow the camera on a secure origin). The banner prints the local and
same-Wi-Fi URLs and, unless `PAGEVAULT_ADMIN_PASSWORD` is set, a one-time admin password.
Open **https://localhost:5000** and accept the one-time self-signed-certificate warning.
Don't need the phone scanner? `PAGEVAULT_HTTPS=0 python app.py` serves plain HTTP.

> Copy `.env.example` to `.env` and set `SECRET_KEY` and `PAGEVAULT_ADMIN_PASSWORD` before
> exposing PageVault to your network.

### Docker

```bash
docker compose up -d      # http://localhost:5000, data in a named volume
```

### Desktop app (Windows)

Download **`PageVault-Setup-<version>.exe`** from the
[latest release](https://github.com/ChristianAbele02/PageVault/releases) and launch from the
Start menu; it opens in its own WebView2 window. The installer is per-user (no admin rights),
data lives in `%LOCALAPPDATA%\PageVault`, and a portable ZIP is also provided. Phone scanning
works: the app runs a LAN HTTPS server, so **Mobile** shows a QR the phone can open with a
working scanner. Build from source with `make exe` (see [Development](#development)).

### Android app

Download **`PageVault-<version>.apk`** from the
[latest release](https://github.com/ChristianAbele02/PageVault/releases) onto your phone,
open it, and allow installing from unknown sources when Android asks (the app is not on the
Play Store). Everything runs on-device: the Flask app runs on a loopback port inside the
app via embedded CPython (Chaquopy) and the UI renders in a WebView, so the catalogue,
camera scanner, reader, stats, import/export, and backups all work locally with no server.
Admin login is omitted. To build from source instead, open the `android/` folder in Android
Studio and Run — see [android/README.md](android/README.md) and
[ANDROID_APP_PLAN.md](ANDROID_APP_PLAN.md).

---

## Phone scanning &amp; HTTPS

Browsers expose the camera only on a **secure origin** (`localhost` or HTTPS). A phone reaches
the web/desktop build over the LAN, so those serve HTTPS with a self-signed certificate
generated on first launch under your data directory (git-ignored, reused across restarts,
covering `localhost` and your LAN IP). Accept the one-time warning per device, or trust a
[mkcert](https://github.com/FiloSottile/mkcert) certificate to remove it:

```bash
mkcert -install
mkcert -cert-file certs/pagevault-cert.pem -key-file certs/pagevault-key.pem localhost 127.0.0.1 192.168.x.x
```

The Android build needs none of this: `http://127.0.0.1` is already a secure origin, so the
on-device camera works with no certificate. Behind a reverse proxy or Docker, TLS is
terminated upstream and this does not apply.

---

## Your data &amp; privacy

| File / folder | What it is |
|---|---|
| `pagevault.db` | Your entire library — books, reviews, shelves, tags, goals, sessions. **Back this up.** |
| `book_files/` | Uploaded e-book files (EPUB/PDF), one per book. |
| `pagevault.log` | Rotating log (10 MB × 5). Safe to delete. |

From a source checkout these sit next to `app.py`. The desktop app keeps them (plus
`secret_key` and `admin_password.txt`) in `%LOCALAPPDATA%\PageVault`; the Android app keeps
them in its private storage. Set `PAGEVAULT_DATA_DIR` to override the location. Nothing is
sent anywhere except the metadata providers you look ISBNs up against.

**Admin panel** (web/desktop only): visit `/admin/login`. The password is printed on startup
(or saved to `admin_password.txt` in the desktop app) unless `PAGEVAULT_ADMIN_PASSWORD` is
set. Login is rate-limited (5 failures per address → HTTP 429 for 5 minutes).

---

## REST API

All responses are JSON. Base URL is `http://localhost:5000` under Docker/gunicorn/`PAGEVAULT_HTTPS=0`,
otherwise `https://localhost:5000` (add `curl -k`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/books` | List books — `?status=&author=&genre=&shelf_id=&q=&sort=&order=` |
| `POST` | `/api/books` | Add a book `{ isbn, status?, genre_tags?, shelf_ids?, book_data? }` |
| `GET` `PATCH` `DELETE` | `/api/books/:id` | Book detail / update / delete |
| `GET` | `/api/books/:id/recommendations` | Similar books from your library (`?limit=`) |
| `GET` | `/api/search` | Full-text search across metadata, review notes, and quotes (`?q=`) |
| `GET` `POST` `DELETE` | `/api/books/:id/reviews[/:rid]` | Reviews `{ rating?, comment?, current_page? }` |
| `GET` `POST` `DELETE` | `/api/books/:id/quotes[/:qid]` | Quotes with page numbers |
| `GET` `POST` `DELETE` | `/api/books/:id/reads[/:rid]` | Re-read history |
| `POST` `GET` `DELETE` | `/api/books/:id/file` | Upload / stream / remove the e-book file |
| `PATCH` | `/api/books/:id/position` | Save reader position `{ cfi?, percent?, current_page? }` |
| `POST` | `/api/books/:id/sessions` · `GET /api/sessions` | Reading sessions |
| `GET` `POST` `PATCH` `DELETE` | `/api/shelves[/:id]` | Custom shelves |
| `GET` | `/api/lookup/:isbn` | Preview ISBN metadata without saving |
| `POST` | `/api/books/refresh[/start]` | Refresh metadata for all books (preserves reviews/tags/shelves) |
| `POST` | `/api/metadata/repair[/start]` · `GET /api/metadata/jobs[/:id]` | Repair jobs + progress |
| `GET` `PUT` | `/api/goals/current` | Yearly reading goal + progress |
| `GET` | `/api/stats` · `/api/stats/analysis` | Statistics + plot-ready dataset (`?start_date=&end_date=`) |
| `GET` | `/api/export` · `/api/export/csv` | Full library export (JSON / CSV) |
| `POST` | `/api/import/csv[/preview][/start]` | Import PageVault or Goodreads CSV (preview / sync / background) |
| `GET` `POST` | `/api/backup/download` · `/api/backup/restore/{validate,apply}` | Backup / restore |
| `POST` | `/api/admin/{login,logout}` · `GET /api/admin/{diagnostics,logs}` | Admin session + diagnostics |
| `GET` | `/api/mobile/connect` | Same-network URL for the mobile QR |
| `GET` | `/opds` | OPDS 1.2 acquisition feed of books with e-book files (for e-reader apps) |

```bash
# Add by ISBN (metadata fetched automatically), then review it
curl -X POST http://localhost:5000/api/books -H "Content-Type: application/json" \
  -d '{"isbn": "9780451524935", "status": "read"}'
curl -X POST http://localhost:5000/api/books/1/reviews -H "Content-Type: application/json" \
  -d '{"rating": 5, "comment": "Essential reading."}'
```

---

## Metadata &amp; performance notes

Lookups start with the Open Library Books API; if fields are missing, Google Books, Open
Library Search, Crossref, and (for 978-3 ISBNs) the DNB run **in parallel**, then merge
progressively so good data is never discarded. Community ratings come from Open Library's
CC0 ratings (keyless) with Google Books as backup; series info is Google-Books-only. Results
are cached in-process (TTL `PAGEVAULT_LOOKUP_CACHE_TTL_SECONDS`, default 900 s).

Google Books has a small keyless quota; bulk jobs throttle and pause after an HTTP 429. Set a
free `PAGEVAULT_GOOGLE_BOOKS_API_KEY` for higher coverage, then run **Tools → Repair missing
metadata**. SQLite runs in WAL mode with `busy_timeout` so the desktop build's two servers
never collide on a write.

---

## Development

```bash
pip install ".[dev,prod]"     # or: make dev
python -m pytest              # 132 tests;  make test
python -m ruff check .        # lint;        make lint
python -m mypy app.py desktop.py config.py pagevault_core
```

CI (GitHub Actions) runs tests, ruff, mypy, and a Docker build. The `Makefile` wraps the same
commands. Front-end libraries are vendored under `static/vendor` (no CDN at runtime); the
desktop build freezes with PyInstaller (`make exe`); the Android build embeds CPython via
Chaquopy.

### Project layout

```
pagevault/
├── app.py · config.py · desktop.py     Web factory · config/data dirs · desktop launcher
├── pagevault_core/
│   ├── api.py                          REST blueprint (all routes)
│   ├── db.py · metadata.py · utils.py  SQLite · multi-provider lookup · helpers
│   ├── tls.py                          Self-signed cert for local HTTPS (phone scanning)
│   └── services/                       admin_service.py · recommendations.py
├── templates/                          index · stats · reader · admin (Jinja2)
├── static/                             PWA manifest · service worker · i18n.js · vendor/
├── android/                            On-device Android app (Chaquopy + WebView)
├── tests/                              132 tests (API · metadata · TLS)
├── Dockerfile · docker-compose.yml     Multi-stage, non-root, gunicorn
├── Makefile · pyproject.toml           Tooling and packaging
└── ANDROID_APP_PLAN.md · CHANGELOG.md · CONTRIBUTING.md · SECURITY.md
```

---

## Roadmap

- [x] Built-in e-book reader (EPUB/PDF) with position sync
- [x] English/German interface · annual goal tracker · admin console
- [x] Mobile QR connect · local recommendations · desktop app
- [x] Offline front-end (vendored libraries, cover cache)
- [x] Android app: on-device release with installable APK
- [x] Full-text search (FTS5) · OPDS catalogue feed for e-reader apps
- [ ] Goodreads import mapping presets (regional variants)

Have an idea? [Open a feature request](https://github.com/ChristianAbele02/PageVault/issues/new/choose).

## Contributing &amp; license

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Report security issues
privately per [SECURITY.md](SECURITY.md). Licensed under [MIT](LICENSE).

<p align="center"><br/>
  Built with <a href="https://flask.palletsprojects.com">Flask</a> ·
  <a href="https://www.sqlite.org">SQLite</a> ·
  <a href="https://openlibrary.org">Open Library</a>
  <br/><br/>
  <img src="assets/icon.svg" width="28" alt="PageVault icon"/>
</p>
