<div align="center">

# 📚 PageVault

**Your personal, self-hosted book catalog — a local Goodreads alternative.**

[![CI](https://github.com/yourname/pagevault/actions/workflows/ci.yml/badge.svg)](https://github.com/yourname/pagevault/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Scan ISBN barcodes with your phone, fetch book metadata automatically, and build your personal reading library — all running locally with a single Python file and a SQLite database.

</div>

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 📷 **ISBN barcode scanning** | Works directly in your phone's browser — no app install |
| 🔍 **Auto metadata fetch** | Title, author, cover, publisher, year, pages via [Open Library](https://openlibrary.org) |
| ⭐ **Ratings & reviews** | 1–5 stars with written notes; full history per book |
| 🔖 **Reading status** | Want to Read · Currently Reading · Read |
| 🔎 **Search & filter** | Full-text search across title and author |
| 📊 **Library stats** | Total books, read count, average rating |
| 💾 **100% local** | SQLite database — your data never leaves your machine |
| 🐳 **Docker ready** | Multi-stage Dockerfile + `docker-compose.yml` included |
| 🧪 **Tested** | pytest suite with 30+ tests covering all API endpoints |

---

## 🚀 Quick Start

### Option A — Python (recommended for development)

**Requirements:** Python 3.10+

```bash
git clone https://github.com/yourname/pagevault.git
cd pagevault
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** in your browser.

To access from your **phone on the same Wi-Fi**, replace `localhost` with your machine's local IP:

```bash
# macOS / Linux
ipconfig getifaddr en0   # or: hostname -I

# Windows
ipconfig  # look for IPv4 Address
```

Then open `http://192.168.x.x:5000` on your phone.

---

### Option B — Docker

```bash
git clone https://github.com/yourname/pagevault.git
cd pagevault
docker compose up -d
```

PageVault starts at **http://localhost:5000**. The SQLite database is persisted in a named Docker volume (`pagevault_data`).

```bash
docker compose down        # stop
docker compose down -v     # stop and delete data
```

---

## 📱 Using the App

### Adding a book by scanning

1. Open PageVault on your phone's browser (`http://YOUR-IP:5000`)
2. Tap **+** → **Scan ISBN Barcode**
3. Allow camera access when prompted
4. Point the camera at the barcode on the back of any book
5. Metadata is fetched automatically — tap **Add to My Shelf**

> **Safari on iOS?** Apple requires HTTPS for camera access when the host isn't `localhost`. See the [HTTPS workaround](#-https-for-phone-camera) below.

### Adding a book manually

Tap **+** → type the ISBN in the text field → **Look up**. If the book isn't in Open Library, you can fill in the title and author manually.

### Rating & reviewing

Tap any book card → pick a star rating (1–5) → optionally write a note → **Save Review**. Add as many reviews as you like over time.

### Exporting your library

```bash
curl http://localhost:5000/api/export > my_books.json
```

---

## 🔐 HTTPS for Phone Camera

Safari on iOS blocks camera access over plain HTTP from non-`localhost` origins. The easiest fix:

```bash
pip install mkcert         # or: brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1 192.168.x.x   # your local IP
```

This generates `localhost+2.pem` and `localhost+2-key.pem`. Then run Flask with:

```python
app.run(host="0.0.0.0", port=5000, ssl_context=("localhost+2.pem", "localhost+2-key.pem"))
```

And open `https://192.168.x.x:5000` on your phone.

---

## 🛠️ Development

```bash
# Install dev dependencies (pytest, ruff, mypy)
make dev

# Run the development server
make run

# Run tests
make test

# Run tests with coverage report
make coverage

# Lint
make lint

# Auto-format
make format
```

### Project structure

```
pagevault/
├── app.py                  ← Flask app factory, REST API, ISBN lookup
├── templates/
│   └── index.html          ← Complete frontend (HTML + CSS + JS)
├── tests/
│   └── test_api.py         ← pytest test suite (30+ tests)
├── .github/
│   ├── workflows/ci.yml    ← GitHub Actions (test, lint, Docker)
│   ├── ISSUE_TEMPLATE/     ← Bug report & feature request forms
│   └── PULL_REQUEST_TEMPLATE.md
├── Dockerfile              ← Multi-stage production image
├── docker-compose.yml
├── Makefile                ← Developer convenience commands
├── pyproject.toml          ← Project metadata, tool config
├── requirements.txt
├── requirements-dev.txt
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

---

## 🌐 REST API Reference

All endpoints return JSON.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/books` | List books (`?status=`, `?q=`, `?sort=`, `?order=`) |
| `POST` | `/api/books` | Add a book `{ isbn, status?, book_data? }` |
| `GET` | `/api/books/:id` | Book detail + all reviews |
| `PATCH` | `/api/books/:id` | Update `status`, `title`, `author`, `description`, `genre` |
| `DELETE` | `/api/books/:id` | Delete a book (cascades reviews) |
| `GET` | `/api/lookup/:isbn` | Look up ISBN without saving |
| `POST` | `/api/books/:id/reviews` | Add review `{ rating?, comment? }` |
| `DELETE` | `/api/books/:id/reviews/:rid` | Delete a review |
| `GET` | `/api/stats` | Aggregate stats |
| `GET` | `/api/export` | Export entire library as JSON |

### Example

```bash
# Add a book manually
curl -X POST http://localhost:5000/api/books \
  -H "Content-Type: application/json" \
  -d '{"isbn":"9780451524935","status":"read"}'

# Add a review
curl -X POST http://localhost:5000/api/books/1/reviews \
  -H "Content-Type: application/json" \
  -d '{"rating":5,"comment":"A masterpiece of dystopian fiction."}'
```

---

## 🔄 Backup & Restore

Your entire library lives in a single SQLite file:

```bash
# Backup
cp pagevault.db pagevault.db.bak

# Restore
cp pagevault.db.bak pagevault.db
```

For Docker:

```bash
# Backup
docker cp pagevault:/data/pagevault.db ./pagevault.db.bak

# Restore
docker cp ./pagevault.db.bak pagevault:/data/pagevault.db
```

---

## 🗺️ Roadmap

- [ ] Import from Goodreads CSV export
- [ ] Multiple shelves / custom lists
- [ ] Reading progress tracker (current page / percentage)
- [ ] Book genre tags and filtering
- [ ] Annual reading goal
- [ ] Optional password protection

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions are welcome!

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
Built with Flask · SQLite · Open Library API
</div>
