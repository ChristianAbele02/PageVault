<p align="center">
  <img src="assets/logo.svg" alt="PageVault" width="380"/>
</p>

<p align="center">
  <strong>A self-hosted, local Goodreads alternative.</strong><br/>
  Scan ISBN barcodes with your phone · Fetch covers & metadata automatically · Keep your reading life private.
</p>

<br/>

<p align="center">
  <a href="https://github.com/ChristianAbele02/PageVault/actions/workflows/ci.yml">
    <img src="https://github.com/ChristianAbele02/PageVault/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  &nbsp;
  <a href="https://github.com/ChristianAbele02/PageVault/releases">
    <img src="https://img.shields.io/github/v/release/ChristianAbele02/PageVault?color=c8913a&label=release" alt="Release"/>
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

---

## Features

**📷 Scan any book in seconds**
Open PageVault on your phone browser, tap the scan button, and point at the barcode. No app install. No account.

**📚 Automatic metadata**
Title, author, cover image, publisher, year, and page count — fetched from [Open Library](https://openlibrary.org), which is free and requires no API key.

**⭐ Ratings & personal notes**
Give each book a 1–5 star rating and add written notes. Build up a reading journal over time.

**🔖 Reading status**
Track every book as *Want to Read*, *Currently Reading*, or *Read*.

**🔍 Search & filter**
Find any book in your library instantly by title or author.

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
pip install -r requirements.txt
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

### Exporting your library

```bash
curl http://localhost:5000/api/export > my_library.json
```

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
| `GET` | `/api/books` | List books — supports `?status=`, `?q=`, `?sort=`, `?order=` |
| `POST` | `/api/books` | Add a book `{ isbn, status?, book_data? }` |
| `GET` | `/api/books/:id` | Book detail including all reviews |
| `PATCH` | `/api/books/:id` | Update `status`, `title`, `author`, `description` |
| `DELETE` | `/api/books/:id` | Delete a book (reviews cascade) |
| `GET` | `/api/lookup/:isbn` | Preview ISBN metadata without saving |
| `POST` | `/api/books/:id/reviews` | Add review `{ rating?, comment? }` |
| `DELETE` | `/api/books/:id/reviews/:rid` | Remove a review |
| `GET` | `/api/stats` | Library statistics |
| `GET` | `/api/export` | Full library export as JSON |

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

Everything is in one file.

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

### Project layout

```
pagevault/
├── app.py                        Flask app factory + REST API + ISBN lookup
├── templates/
│   └── index.html                Complete frontend (HTML + CSS + JS, single file)
├── tests/
│   ├── conftest.py               Shared pytest fixtures
│   └── test_api.py               36-test suite
├── assets/
│   ├── logo.svg                  Full wordmark logo
│   └── icon.svg                  Square icon (GitHub avatar, favicon)
├── .github/
│   ├── workflows/ci.yml          GitHub Actions: test · lint · Docker build
│   ├── ISSUE_TEMPLATE/           Bug report & feature request forms
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── .devcontainer/
│   └── devcontainer.json         One-click GitHub Codespaces setup
├── Dockerfile                    Multi-stage, non-root, gunicorn
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

---

## Roadmap

- [ ] Import from Goodreads CSV export
- [ ] Multiple shelves / custom lists
- [ ] Reading progress (current page)
- [ ] Genre tags and filtering
- [ ] Annual reading goal tracker
- [ ] Optional password protection

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
