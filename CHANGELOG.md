# Changelog

All notable changes to PageVault are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Import from Goodreads CSV export
- Multiple reading shelves / custom lists
- Reading progress tracker (current page)
- Book genres / tags filtering
- Annual reading goal tracker

---

## [1.0.0] — 2025-03-03

### Added
- **ISBN barcode scanning** via phone camera using `html5-qrcode` (no app install required)
- **Automatic metadata fetch** from [Open Library](https://openlibrary.org): title, author, cover, publisher, year, pages, genre
- **Book catalog** with grid view and cover images
- **Reading status tracking**: Want to Read / Currently Reading / Read
- **Star ratings** (1–5) and written reviews per book, with full history
- **Library stats**: total books, read count, average rating
- **Search** across title and author
- **Filter** by reading status
- **Export** full library to JSON (`GET /api/export`)
- **REST API** with full CRUD for books and reviews
- **Docker** support with multi-stage build and `docker-compose.yml`
- **GitHub Actions** CI: tests on Python 3.10, 3.11, 3.12; lint; Docker build
- **pytest** test suite with 30+ tests covering all API endpoints
- **Makefile** for developer convenience
- Local SQLite database — data stays on your machine

[Unreleased]: https://github.com/ChristianAbele02/PageVault
[1.0.0]: https://github.com/ChristianAbele02/PageVault
