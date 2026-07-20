"""Database infrastructure for PageVault.

This module encapsulates connection lifecycle, Flask request-scoped DB access,
schema bootstrap, and initialization helpers used by the app factory.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import cast

from flask import Flask, g

log = logging.getLogger(__name__)

# Wait up to this long for a write lock before raising "database is locked".
# The desktop build serves the same database from two servers (loopback plus the
# phone-facing HTTPS one), so concurrent writers are normal and must queue, not fail.
_BUSY_TIMEOUT_MS = 5000


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Apply the connection pragmas PageVault relies on.

    WAL allows concurrent readers alongside a writer; ``synchronous=NORMAL`` is the
    recommended, durable-enough pairing for WAL and is markedly faster than FULL;
    ``busy_timeout`` makes contending writers wait instead of failing; foreign keys
    are enforced per connection.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")


def get_db() -> sqlite3.Connection:
    if "_db" not in g:
        g._db = sqlite3.connect(
            g._app_config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g._db.row_factory = sqlite3.Row
        _configure_connection(g._db)
    return cast(sqlite3.Connection, g._db)


def init_db_hook(app: Flask) -> None:
    @app.before_request
    def _attach_config() -> None:
        g._app_config = app.config

    @app.teardown_appcontext
    def _close_db(exc: BaseException | None) -> None:
        db = g.pop("_db", None)
        if db is not None:
            db.close()


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn        TEXT    UNIQUE NOT NULL,
            title       TEXT    NOT NULL,
            author      TEXT,
            cover_url   TEXT,
            description TEXT,
            publisher   TEXT,
            year        TEXT,
            pages       INTEGER,
            genre       TEXT,
            language    TEXT    DEFAULT 'en',
            location_type TEXT   NOT NULL DEFAULT 'shelf'
                        CHECK(location_type IN ('shelf','ebook','loaned_to','loaned_from','other')),
            location_note TEXT,
            loan_person TEXT,
            added_at    TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'want_to_read'
                        CHECK(status IN ('want_to_read','reading','read','dnf')),
            series_name TEXT,
            series_number TEXT,
            community_rating REAL,
            community_rating_count INTEGER,
            book_format TEXT NOT NULL DEFAULT 'physical'
                        CHECK(book_format IN ('physical','ebook','audiobook')),
            owned       INTEGER NOT NULL DEFAULT 0,
            start_date  TEXT,
            finish_date TEXT,
            file_path   TEXT,
            file_type   TEXT,
            reader_position TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            rating      REAL CHECK(rating >= 0.5 AND rating <= 5),
            comment     TEXT,
            current_page INTEGER,
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shelves (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    UNIQUE NOT NULL,
            logo_url    TEXT,
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS book_shelves (
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            shelf_id    INTEGER NOT NULL REFERENCES shelves(id) ON DELETE CASCADE,
            PRIMARY KEY (book_id, shelf_id)
        );

        CREATE TABLE IF NOT EXISTS tags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL COLLATE NOCASE UNIQUE
        );

        CREATE TABLE IF NOT EXISTS book_tags (
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (book_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS reading_goals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_year       INTEGER NOT NULL UNIQUE,
            target_books    INTEGER NOT NULL DEFAULT 0,
            target_pages    INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reading_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id         INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            start_page      INTEGER NOT NULL,
            end_page        INTEGER NOT NULL,
            minutes_spent   INTEGER NOT NULL,
            session_date    TEXT    NOT NULL,
            notes           TEXT,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata_jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type        TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            total_books     INTEGER NOT NULL DEFAULT 0,
            processed_books INTEGER NOT NULL DEFAULT 0,
            updated_books   INTEGER NOT NULL DEFAULT 0,
            failed_books    INTEGER NOT NULL DEFAULT 0,
            started_at      TEXT    NOT NULL,
            finished_at     TEXT,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata_job_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL REFERENCES metadata_jobs(id) ON DELETE CASCADE,
            book_id         INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            status          TEXT    NOT NULL,
            attempts        INTEGER NOT NULL DEFAULT 0,
            last_error      TEXT,
            updated_fields  TEXT,
            updated_at      TEXT    NOT NULL,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS restore_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            status          TEXT    NOT NULL,
            summary_json    TEXT,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type      TEXT    NOT NULL,
            details_json    TEXT,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quotes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            text        TEXT    NOT NULL,
            page_number INTEGER,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reading_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            started_at  TEXT,
            finished_at TEXT,
            notes       TEXT,
            created_at  TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_quotes_book ON quotes(book_id);
        CREATE INDEX IF NOT EXISTS idx_reading_history_book ON reading_history(book_id);
        CREATE INDEX IF NOT EXISTS idx_books_status  ON books(status);
        CREATE INDEX IF NOT EXISTS idx_books_author  ON books(author COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_reviews_book  ON reviews(book_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_book ON reading_sessions(book_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_date ON reading_sessions(session_date);
        CREATE INDEX IF NOT EXISTS idx_metadata_job_items_job ON metadata_job_items(job_id);
        CREATE INDEX IF NOT EXISTS idx_book_shelves_book ON book_shelves(book_id);
        CREATE INDEX IF NOT EXISTS idx_book_shelves_shelf ON book_shelves(shelf_id);
        CREATE INDEX IF NOT EXISTS idx_book_tags_book ON book_tags(book_id);
        CREATE INDEX IF NOT EXISTS idx_book_tags_tag ON book_tags(tag_id);
        CREATE INDEX IF NOT EXISTS idx_admin_events_created ON admin_events(created_at DESC);
    """)
    review_cols = {row["name"] for row in db.execute("PRAGMA table_info(reviews)").fetchall()}
    if "current_page" not in review_cols:
        db.execute("ALTER TABLE reviews ADD COLUMN current_page INTEGER")

    book_cols = {row["name"] for row in db.execute("PRAGMA table_info(books)").fetchall()}
    if "location_type" not in book_cols:
        db.execute(
            "ALTER TABLE books ADD COLUMN location_type TEXT NOT NULL DEFAULT 'shelf' "
            "CHECK(location_type IN ('shelf','ebook','loaned_to','loaned_from','other'))"
        )
    if "location_note" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN location_note TEXT")
    if "loan_person" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN loan_person TEXT")
    if "series_name" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN series_name TEXT")
    if "series_number" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN series_number TEXT")
    if "community_rating" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN community_rating REAL")
    if "community_rating_count" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN community_rating_count INTEGER")
    if "book_format" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN book_format TEXT NOT NULL DEFAULT 'physical'")
    if "owned" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN owned INTEGER NOT NULL DEFAULT 0")
    if "start_date" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN start_date TEXT")
    if "finish_date" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN finish_date TEXT")
    if "file_path" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN file_path TEXT")
    if "file_type" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN file_type TEXT")
    if "reader_position" not in book_cols:
        db.execute("ALTER TABLE books ADD COLUMN reader_position TEXT")

    db.commit()
    log.info("Database schema verified.")


def bootstrap_database(app: Flask) -> None:
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        _configure_connection(db)
        ensure_schema(db)
        db.close()
