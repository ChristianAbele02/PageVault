# Changelog

All notable changes to PageVault are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.1] — 2026-07-23

A security-hardening release. The Android APK is now signed with a persistent
release key.

### Security
- The destructive restore endpoints (`/api/backup/restore/validate` and
  `/apply`) now require the admin session on the web and desktop builds,
  matching the documented behaviour. The Android build is exempt: it has no
  admin accounts and its server is reachable only from the device itself.
- The `/api/cover` proxy validates every redirect hop against the cover-host
  allowlist, closing an open-redirect SSRF vector; the hosts the allowlisted
  services legitimately redirect to (archive.org, googleusercontent.com) are
  permitted.
- The Android WebView no longer allows `file://` access — it only ever renders
  the loopback server, so the capability was unnecessary.
- Session cookies are issued with `SameSite=Lax` and explicit `HttpOnly`.

### Fixed
- Restore validation no longer leaks an open database handle when the uploaded
  archive is not a valid SQLite file (this locked temp files on Windows).

## [1.9.0] — 2026-07-23

The first release with a working, installable Android app.

### Added
- **Full-text search** (`GET /api/search?q=`) across book metadata, review notes,
  and saved quotes, backed by a SQLite FTS5 index. Results group by book with up
  to three highlighted excerpts labelled by source. The index is maintained by
  lightweight dirty-flag triggers and rebuilt lazily, and it degrades gracefully
  on a SQLite build without FTS5.
- **OPDS catalogue** (`GET /opds`). An OPDS 1.2 acquisition feed of every book
  with an attached e-book file, so e-reader apps (KOReader, Moon+ Reader, and
  similar) can browse your library and download EPUB/PDF files directly.
- **Mobile search popup.** On the Android app the inline search box acts as a
  trigger that opens a centred popup window over the library: a large input you
  can type into freely, a Search button (or Enter) that applies the query,
  closes the popup, and shows the filtered results. English and German.
- **Android release workflow** (`android-release.yml`). Every version tag builds
  the APK on CI and attaches it to the GitHub release, signed with a release
  keystore when the `ANDROID_KEYSTORE_*` secrets are configured and debug-signed
  otherwise.

### Fixed
- **Android: stale UI after app updates.** Extracted web assets now refresh on
  every (re)install (the version marker includes the APK's `lastUpdateTime`);
  previously debug deploys kept serving the first-installed templates forever.
- **Android build under Gradle 8.13.** Toolchain aligned to a supported
  combination (Gradle 8.13 · AGP 8.13.2 · Chaquopy 17.0.0 · Python 3.13), and
  the Chaquopy/AGP merge tasks now declare explicit dependencies on the
  `syncPythonSource`/`syncWebAssets` staging tasks, which Gradle 8.13 requires.
- **Mobile UI.** The gear tools menu is anchored to the viewport with a capped
  width, so it can no longer clip off the screen edge on narrow devices; the
  search fields no longer render near-white text on a white background in dark
  mode.

## [1.8.0] — 2026-07-20

### Added
- **Android app (on-device).** A new `android/` project runs the existing Flask
  app on a loopback port inside the app process (embedded CPython via Chaquopy)
  and renders the web UI in a WebView. ISBN scanning uses the phone camera
  (loopback is a secure context, so no certificate is needed); the catalogue,
  reader, stats, import/export and backups all run locally. Admin login is
  omitted. See `android/README.md` and `ANDROID_APP_PLAN.md`.
- **Offline front-end.** html5-qrcode, Plotly, epub.js, qrcodejs and the
  Playfair Display / Lato web fonts are vendored under `static/vendor`, so the
  app no longer depends on any CDN at runtime. This is a prerequisite for the
  Android build and also hardens the web and desktop builds against CDN outages.
- **Offline cover cache.** Covers are cached two ways so a browsed library keeps
  them without a connection: the service worker caches cover images in the
  browser, and a new `/api/cover` proxy downloads each cover once and serves it
  from local disk (with an SSRF host allowlist). The on-disk cache is what makes
  covers survive offline in the Android app.

### Fixed
- **Reader page listed no books.** `/reader` parsed the book list as
  `data.books`, but `/api/books` returns a plain array — the sidebar was always
  empty, so library e-books could not be opened from the reader page (device
  files still worked). The response is now read as the array it is.
- **Clicking an author name in the book detail did nothing.** The author link's
  `onclick` attribute was built with raw double quotes inside a double-quoted
  attribute, truncating it for every author. Quotes are now HTML-escaped, so the
  author filter shortcut works again (including names with apostrophes).
- **Backups could silently miss recent writes.** The database runs in WAL mode,
  where recent commits live in the `-wal` sidecar file; the backup endpoint
  zipped only the `.db` file. It now snapshots via the SQLite backup API, so a
  backup taken right after adding books always contains them.
- **Restoring a corrupt archive returned a 500.** Restore now verifies the
  SQLite header and runs a quick integrity check before touching the live
  database, rejecting invalid uploads with a clear 400 and leaving the library
  untouched.
- **Stale pages after updates (PWA).** The service worker served `/` and
  `/stats` cache-first with a fixed cache name, so an updated PageVault kept
  showing the old UI until the browser cache was cleared. Navigations are now
  network-first (cache only as offline fallback) and static assets revalidate in
  the background.

### Changed
- **Lighter, faster front-end.** The stats page now loads the `plotly-basic`
  build (~1 MB) instead of the full 4.5 MB one, since it only uses bar, pie, and
  scatter traces. The scanner, QR, and reader libraries are deferred so they no
  longer block first paint, and the vendored libraries and fonts carry a one-day
  cache header.
- **gzip for networked clients.** Text responses (HTML, JSON) are gzip-compressed
  for non-loopback clients, so same-Wi-Fi phones and self-hosted deployments
  transfer far less. Loopback callers (the desktop and Android WebViews) skip it,
  since compression buys nothing over the local socket.
- **SQLite tuning.** Connections now use `synchronous=NORMAL` (the recommended,
  faster pairing with WAL) and a 5-second `busy_timeout`, so the desktop build's
  two servers queue on writes instead of failing with "database is locked".
- **Faster title lookups.** For books without a real ISBN, the Open Library and
  Google Books title searches now run in parallel, matching the ISBN path.
- **Listing endpoints no longer run two queries per book.** `/api/books`,
  `/api/export/csv`, and recommendations batch-load tags, shelves, and latest
  reviews in a fixed number of queries instead of N+1 per-book lookups, which
  keeps large libraries fast.
- The Docker builder stage copies `config.py`/`desktop.py`, so the wheel built
  inside the image contains every module `pyproject.toml` declares.

---

## [1.7.1] — 2026-06-30

### Added
- **Local HTTPS for mobile barcode scanning.** Browsers only expose the camera
  (`getUserMedia`) in a secure context, so scanning an ISBN from a phone over the
  LAN (plain HTTP) never opened the camera. `python app.py` now serves over HTTPS
  by default using a persistent self-signed certificate generated at startup
  (`pagevault_core/tls.py`), with the local hostnames and the detected LAN IP in
  its SubjectAltName so the same cert is reused across restarts. The mobile QR link
  follows the request scheme, so it now hands the phone an `https://` address. Set
  `PAGEVAULT_HTTPS=0` to fall back to plain HTTP.
- **Phone scanning from the desktop app.** The desktop app now starts a second,
  phone-facing HTTPS server on the LAN (alongside the loopback server the window
  uses), so the **Mobile** QR opens PageVault on a phone with a working camera
  scanner. The QR points at that `https://<lan-ip>:<port>/` endpoint; the button
  is shown only once the HTTPS server is up.
- **Deutsche Nationalbibliothek (DNB) metadata.** German-language ISBNs (978-3)
  now also query the German national library, which catalogues German books that
  Open Library lacks and the keyless Google Books quota cannot always reach. This
  fixes ISBN lookups that returned no title/author for many German editions. DNB
  supplies authoritative title/author/publisher/year/language; covers still come
  from the other providers.

### Changed
- Publication years are normalised to a four-digit year, so the UI shows "1993"
  instead of provider strings like "1993?" or "April 2021".

### Fixed
- **Mobile layout: the add button is reachable without zooming out.** The header
  action pills and stats bar no longer force the page wider than the screen, which
  had made phones shrink the whole layout and push the floating add button off the
  right edge. The header now wraps to a second row on narrow screens, with
  `overflow-x: clip` as a backstop and safe-area insets so the button clears the
  phone's home indicator.
- The ISBN scanner now shows a clear "camera needs HTTPS" message on an insecure
  origin instead of a confusing access-denied error.

### Security
- CDN scripts (html5-qrcode, qrcodejs, epub.js, Plotly) are pinned with
  Subresource Integrity hashes, so a tampered CDN response is rejected.
- Admin login is rate-limited: 5 failed attempts from one address within 5 minutes
  trigger an `HTTP 429` lockout, slowing password brute-forcing.
- The session cookie is marked `Secure` when `python app.py` serves over HTTPS.

---

## [1.7.0] — 2026-06-22

### Added
- **Native Windows desktop app.** PageVault can be built as a double-click
  `PageVault.exe` that opens in its own window (pywebview on WebView2) backed by a
  local waitress server — no terminal and no Python install required.
  - `desktop.py` launcher: auto-selected free port, single-instance guard, and a
    `--no-window` server-only mode for testing or browser use.
  - Persists `SECRET_KEY` and the admin password to the per-user data directory, so
    login sessions and admin access survive restarts (there is no console in a
    windowed app to print a one-time password to).
  - `pagevault.spec` (PyInstaller, one-folder), an Inno Setup per-user installer
    (`installer.iss`), and `tools/make_icon.py` to render the app icon.
  - `Desktop Release` GitHub Actions workflow builds the executable, smoke-tests it,
    compiles the installer, and attaches the installer and a portable zip to tagged
    releases.
  - Optional Authenticode code signing: `tools/sign_windows.ps1` (signtool, with a
    `Set-AuthenticodeSignature` fallback) and `tools/make_selfsigned_cert.ps1` for
    private trust. CI signs the executable and installer when `WINDOWS_CERT_BASE64` and
    `WINDOWS_CERT_PASSWORD` secrets are set; the private key is never committed.
  - `desktop`, `build` optional-dependency groups and `make desktop` / `make exe` /
    `make desktop-deps` targets.
- **Open local files in the reader.** The standalone `/reader` page can open an EPUB
  or PDF straight from the device through a file picker, without adding it to the
  library. The file is read client-side (no upload, no new server route); device
  files do not sync reading position.

### Changed
- When running as a frozen executable, the database, e-book files, and log default
  to a per-user OS data directory (`%LOCALAPPDATA%\PageVault` on Windows); set
  `PAGEVAULT_DATA_DIR` to override. Source checkouts and Docker are unchanged.

### Fixed
- Git-ignore the runtime `secret_key` and `admin_password.txt` files written by a
  source checkout, so local credentials cannot be accidentally committed.

---

## [1.6.0] — 2026-06-11

### Added
- **Goodreads import overhaul** based on a real library export:
  - Background import jobs (`POST /api/import/csv/start`) with a live progress bar in the CSV wizard (rows processed, saved, skipped); the floating import button now routes through the same job and opens the wizard to show progress.
  - Import settings: fetch metadata online (on/off), import books without ISBN, keep Goodreads dates and reading history.
  - Books without an ISBN (common for Kindle/Audible editions) are imported via their Goodreads Book Id instead of being silently skipped.
  - `Date Added` is preserved as the library timestamp (keeps growth/timeline charts historically accurate), `Date Read` becomes the finish date and a reading-history entry, `Binding` maps to book format (Kindle → e-book, Audible → audiobook), and `Owned Copies` sets the owned flag.
  - Mojibake repair for double-encoded exports ("BrontÃ«" → "Brontë", "WeiÃŸe NÃ¤chte" → "Weiße Nächte"), including per-line rescue and a cp1252 decode fallback for non-UTF-8 files.
  - Status shelves (`to-read`, `currently-reading`) are no longer turned into junk custom shelves.
- **Title/author metadata lookup** for books without a real ISBN (Goodreads `GR…` placeholder ids): CSV import, "Reload metadata", and "Repair missing metadata" now resolve those books via an Open Library title search plus a Google Books title query, so Kindle/Audible editions get covers, descriptions, and community ratings too.
- Google Books rate-limit protection: requests are throttled (`PAGEVAULT_GOOGLE_BOOKS_MIN_INTERVAL_SECONDS`, default 0.6 s) and an HTTP 429 puts the provider on a cooldown (`PAGEVAULT_GOOGLE_BOOKS_COOLDOWN_SECONDS`, default 120 s) instead of spamming failed lookups. Optional `PAGEVAULT_GOOGLE_BOOKS_API_KEY` raises the quota for large libraries.
- "Repair missing metadata" now also backfills missing community ratings and series info, so the *Your rating vs community* stats chart fills in after a bulk import.
- **Community ratings without an API key**: Open Library's crowd-sourced ratings (CC0) are now fetched alongside its search results and used as the primary community-rating source — Google Books is only a second opinion. No key, no rate-limit pain.
- **Progress bars for all long-running jobs**: "Repair missing metadata" and "Reload metadata" now run as background jobs (`POST /api/metadata/repair/start`, `POST /api/books/refresh/start`) with a live progress bar in the Tools dialog — books processed, books updated — matching the CSV import experience. The synchronous endpoints remain for scripting.
- **Figure export on the stats page**: every chart panel has a download button in its top corner that saves the figure as a 2× PNG on a solid paper background (so dark-mode exports stay readable). The DOM-based activity heatmap is redrawn onto a canvas for its export; buttons hide automatically while a figure has no data.
- **Built-in e-book reader**: attach an EPUB or PDF file to any book (drag & drop or file picker in the detail view), read it in an in-app reader dialog or on the dedicated `/reader` page with a searchable sidebar, font-size controls, keyboard navigation, and a progress bar.
- E-book file API: `POST/GET/DELETE /api/books/:id/file` with magic-byte content validation (only real EPUB/PDF files are accepted) and friendly download filenames.
- Reading position sync: `PATCH /api/books/:id/position` stores the EPUB locator (`{cfi, percent}`) and, when the book has a page count, converts the percentage into `current_page` progress on the latest review — so reading in the e-reader updates the library progress bars automatically.
- German/English interface toggle (`static/i18n.js`) on the library, stats, and reader pages; language preference persists locally.
- `PAGEVAULT_BOOK_FILES_DIR` environment variable for the e-book storage directory (default: `book_files/` next to the database).
- Test coverage for e-book upload/serve/delete and reading-position endpoints (78 tests total); test fixtures now isolate the book-files directory.

### Changed
- **Physical-library visual theme** (all textures are procedural inline SVG — no binary assets, works offline):
  - The library grid is now a wooden bookcase: dark wood-grain back panel, framed case with side rails, and 3D shelf boards that every book stands on. Card heights are fixed and the shelf rhythm is measured from the actual cover baseline, so boards and books stay perfectly aligned at any window size. Titles/authors sit below each board like shelf labels, and hovering pulls the book off the shelf.
  - All pop-up dialogs (book details, tools, settings, mobile QR, …) are torn-out pages: textured paper with a ragged torn top edge (SVG mask), in both a daylight and a night-reading paper tone.
  - The stats page is an open book on a wooden desk: leather cover frame, two-page paper spread with a central gutter shadow, and stacked page edges peeking out at the sides; narrow screens collapse to a single page.
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
- Community ratings (and series info) from Google Books were dropped during metadata merging whenever Open Library answered first — books almost never received a community rating.
- Bulk metadata jobs sent Goodreads `GR…` placeholder ids to every ISBN provider, wasting rate limit on lookups that could never succeed.
- CSV import crashed when a metadata lookup result contained no genre tags.

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

[1.7.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.7.0
[1.6.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.6.0
[1.5.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.5.0
[1.4.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.4.0
[1.3.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.3.0
[1.2.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.2.0
[1.1.0]: https://github.com/ChristianAbele02/PageVault/releases/tag/v1.1.0
[1.0.0]: https://github.com/ChristianAbele02/PageVault
