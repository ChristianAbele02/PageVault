# Changelog

All notable changes to PageVault are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Built-in e-book reader**: attach an EPUB or PDF file to any book (drag & drop or file picker in the detail view), read it in an in-app reader dialog or on the dedicated `/reader` page with a searchable sidebar, font-size controls, keyboard navigation, and a progress bar.
- E-book file API: `POST/GET/DELETE /api/books/:id/file` with magic-byte content validation (only real EPUB/PDF files are accepted) and friendly download filenames.
- Reading position sync: `PATCH /api/books/:id/position` stores the EPUB locator (`{cfi, percent}`) and, when the book has a page count, converts the percentage into `current_page` progress on the latest review — so reading in the e-reader updates the library progress bars automatically.
- German/English interface toggle (`static/i18n.js`) on the library, stats, and reader pages; language preference persists locally.
- `PAGEVAULT_BOOK_FILES_DIR` environment variable for the e-book storage directory (default: `book_files/` next to the database).
- Test coverage for e-book upload/serve/delete and reading-position endpoints (78 tests total); test fixtures now isolate the book-files directory.

### Changed
- Frontend visual refresh across all pages: staggered entrance animations for book cards and KPI tiles, cover shine on hover, skeleton loading placeholders, animated count-up statistics, scroll-reveal chart panels, refined toasts, custom scrollbars, and visible focus rings. All animation respects `prefers-reduced-motion`.
- Deleting a book (or its file) now also removes the stored e-book file from disk instead of leaving orphans.
- Uploading a new e-book file resets the saved reading position for that book.

### Fixed
- Reading positions were never persisted: the position endpoint expected a `position` key the readers never sent; it now accepts the raw locator payload.
- Review timestamps written by the position endpoint used SQLite `datetime('now')` format instead of the ISO-8601 format used everywhere else, breaking "latest review" ordering.
- Rating distribution in stats collapsed half-star ratings into integer buckets (4.5★ counted as 4★).
- File upload response did not include `file_path`, leaving the frontend cache out of sync.
- DNF books showed a raw `dnf` status badge on the library grid.
- Pinch-zoom was blocked on all pages (`maximum-scale=1.0` removed for accessibility).
- Admin login ignored the Enter key and did not focus the password field.
- Reader sidebar crashed when filtering books without a title.

---

## [1.5.0] — 2026-03-23

### Added
- Advanced statistics dashboard expansion: 8 new charts including a GitHub-style reading activity heatmap, rating trend over time, genre trends by year, time-to-finish distribution, reading speed per book, shelf breakdown, longest-unread list, and active loans tracker.
- Goodreads-inspired tracking fields: series name/number, book format (physical/ebook/audiobook), owned flag, start/finish dates, community ratings from Google Books, re-read history, and quotes with page numbers.
- Mobile QR connect: scan a QR code from the header to open PageVault on your phone over the same Wi-Fi (`GET /api/mobile/connect`, `PAGEVAULT_MOBILE_HOST` override).

### Changed
- UI modernisation: native `<dialog>` modals with top-layer rendering and entrance/exit transitions, design tokens, and performance hardening (no GPU-blur backdrops).
- Alembic migrations removed — schema evolution is handled by idempotent `ALTER TABLE` checks in `pagevault_core/db.py`, which suits the single-file SQLite model.

### Fixed
- CI test stability (admin password in test config), type-check issues, and config import order.

---

## [1.4.0] — 2026-03-05

### Added
- Role-aware admin area with password-protected login, diagnostics, event history, and log viewer (`/admin`, `/admin/login`, `/api/admin/*`).
- Structured physical location tracking for books (`location_type`, `location_note`, `loan_person`) with UI and API support.
- Local recommendations endpoint and detail view panel for similar books (`GET /api/books/:id/recommendations`) based on author/genre/tag similarity.
- Alembic migration setup (`alembic/`) with baseline and schema revision scripts for safer schema evolution.
- New service layer modules for admin diagnostics and recommendation scoring under `pagevault_core/services/`.

### Changed
- Configuration is now centralized in `config.py` with environment-aware defaults and admin/password settings.
- CI now enforces lint, type checking, tests, and a dedicated coverage gate job on pull requests.
- Dependency management is now pyproject-based (`pip install .[dev,prod]`), replacing legacy requirements files.
- Docker/devcontainer/build docs were aligned with pyproject packaging and extras.

### Fixed
- Packaging/build backend and setuptools discovery were adjusted to support flat-layout installs reliably.
- Admin login form alignment and main dashboard hint cleanup improved UI consistency.

---

## [1.3.0] — 2026-03-05

### Added
- Annual reading goals with API support (`GET/PUT /api/goals/current`) and progress data integrated into analytics.
- Reading session tracking (`POST /api/books/:id/sessions`, `GET /api/sessions`) with pace summaries in stats analysis.
- CSV import wizard backend support with mapping preview and dry-run (`POST /api/import/csv/preview`, `POST /api/import/csv?dry_run=1`).
- Metadata health repair jobs with run/list/detail endpoints (`POST /api/metadata/repair`, `GET /api/metadata/jobs`, `GET /api/metadata/jobs/:id`).
- Backup/restore API workflow with archive download and restore validation/apply (`GET /api/backup/download`, `POST /api/backup/restore/validate`, `POST /api/backup/restore/apply`).
- PWA baseline assets (`static/manifest.webmanifest`, `static/sw.js`) and offline cache bootstrap for core pages.

### Changed
- Main dashboard now includes operational control panels for goals, sessions, metadata jobs, CSV preview/dry-run/import, and backup/restore.
- Stats page now supports saved views via URL/local persistence and shareable range links.
- CI smoke coverage extended to verify library, stats, API stats, and manifest endpoints, plus critical UI marker checks.

### Fixed
- Restore apply flow now re-applies schema verification after DB replacement so newer tables remain available.

---

## [1.2.0] — 2026-03-05

### Added
- Dedicated `/stats` analytics page with Plotly visualizations for status, pages, genres, authors, ratings, and monthly activity.
- New analytics API endpoint `GET /api/stats/analysis` for plot-ready aggregated dashboard datasets.
- Date range filtering on stats analysis via `start_date` / `end_date` (`YYYY-MM-DD`) with preset and custom range support in the UI.
- Header navigation link from the main app to the stats page.
- GitHub Pages **Open Stats Demo** entry point and a standalone `docs/stats-demo.html` page with example chart data.

### Changed
- Stats page now follows the main design system and color palette, with automatic dark/light theme inheritance from saved browser preference.
- README and GitHub Pages portfolio content updated to document and showcase the stats dashboard workflow.
- Automated tests expanded for stats page routing, analysis payload shape, and date filter validation.

### Fixed
- Ruff formatting compliance for updated API and tests to keep CI format checks green.

---

## [1.1.0] — 2026-03-05

### Added
- Multi-shelf library system with shelf CRUD endpoints, optional shelf logo URL, and book-to-many-shelves mapping.
- Genre tag system with normalized tags, chip-based add/remove UX, duplicate protection, and max-tag constraints.
- Expanded book filtering for `status`, `author`, `genre`, `shelf_id`, and free-text search across core fields/relations.
- Goodreads-compatible CSV import plus full-library CSV export endpoint and UI actions.
- Metadata reload endpoint/UI action to refresh stored metadata in bulk.
- Additional metadata providers: Open Library Search API and Open Library Covers API.
- In-memory ISBN lookup TTL cache to speed repeated lookups during CSV import and bulk refresh.

### Changed
- Metadata pipeline now uses a richer fallback chain with progressive merge and provider concurrency for better completeness and latency.
- Book detail and list payloads now hydrate related shelves and genre tags directly.
- Frontend refreshed with PageVault branding, improved control layout, compact filters, and shelf-themed visual styling.
- Theme system expanded with persistent dark/light toggle (dark default) and improved readability contrast.
- Core architecture modularized via `pagevault_core` (`db.py`, `api.py`, `metadata.py`, `utils.py`) with dependency-injected routing.

### Fixed
- Docker runtime packaging now includes modular core package so Gunicorn boot succeeds in containerized runs.
- Date parsing/formatting for review timestamps (now consistent `DD.MM.YYYY HH:MM` display).
- Cover fallback reliability for ISBNs with partial provider metadata.
- CSV import metadata merge behavior to better preserve existing non-empty stored fields.
- CI quality gates (`ruff` format/import checks) for updated modular code paths.

### Documentation
- README updated for modular architecture, expanded metadata API chain, CSV behavior, and lookup cache configuration.
- API and project-layout documentation aligned with current implementation.

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

[Unreleased]: https://github.com/ChristianAbele02/PageVault/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.5.0
[1.4.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.4.0
[1.3.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.3.0
[1.2.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.2.0
[1.1.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.1.0
[1.0.0]: https://github.com/ChristianAbele02/PageVault
