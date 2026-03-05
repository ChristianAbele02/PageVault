# Changelog

All notable changes to PageVault are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Saved stats views

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

[Unreleased]: https://github.com/ChristianAbele02/PageVault/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.3.0
[1.2.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.2.0
[1.1.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.1.0
[1.0.0]: https://github.com/ChristianAbele02/PageVault
