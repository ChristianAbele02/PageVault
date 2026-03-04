"""Database infrastructure for PageVault.

This module encapsulates connection lifecycle, Flask request-scoped DB access,
schema bootstrap, and initialization helpers used by the app factory.
"""

from __future__ import annotations

import logging
import sqlite3

from flask import Flask, g

log = logging.getLogger(__name__)


def get_db() -> sqlite3.Connection:
    if "_db" not in g:
        g._db = sqlite3.connect(
            g._app_config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g._db.row_factory = sqlite3.Row
        g._db.execute("PRAGMA journal_mode=WAL")
        g._db.execute("PRAGMA foreign_keys=ON")
    return g._db


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
            added_at    TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'want_to_read'
                        CHECK(status IN ('want_to_read','reading','read'))
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            rating      INTEGER CHECK(rating BETWEEN 1 AND 5),
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

        CREATE INDEX IF NOT EXISTS idx_books_status  ON books(status);
        CREATE INDEX IF NOT EXISTS idx_books_author  ON books(author COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_reviews_book  ON reviews(book_id);
        CREATE INDEX IF NOT EXISTS idx_book_shelves_book ON book_shelves(book_id);
        CREATE INDEX IF NOT EXISTS idx_book_shelves_shelf ON book_shelves(shelf_id);
        CREATE INDEX IF NOT EXISTS idx_book_tags_book ON book_tags(book_id);
        CREATE INDEX IF NOT EXISTS idx_book_tags_tag ON book_tags(tag_id);
    """)
    review_cols = {row["name"] for row in db.execute("PRAGMA table_info(reviews)").fetchall()}
    if "current_page" not in review_cols:
        db.execute("ALTER TABLE reviews ADD COLUMN current_page INTEGER")
    db.commit()
    log.info("Database schema verified.")


def bootstrap_database(app: Flask) -> None:
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        ensure_schema(db)
        db.close()
