"""
PageVault — Personal Book Catalog
Flask application factory and REST API.

Usage:
    python app.py                  # development
    flask run --host=0.0.0.0       # production-ish
    gunicorn -w 2 "app:create_app()"
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Application factory ───────────────────────────────────────────────────────
def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    default_db = os.getenv("PAGEVAULT_DB") or str(Path(__file__).parent / "pagevault.db")
    default_secret = os.getenv("SECRET_KEY") or "change-me-in-production"

    # Defaults
    app.config.update(
        DATABASE=default_db,
        SECRET_KEY=default_secret,
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    # Register components
    _init_db_hook(app)
    app.register_blueprint(_api_bp())
    app.add_url_rule("/", "index", lambda: render_template("index.html"))

    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(db)
        db.close()

    return app


# ── Database helpers ──────────────────────────────────────────────────────────
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


def _init_db_hook(app: Flask) -> None:
    @app.before_request
    def _attach_config() -> None:
        g._app_config = app.config

    @app.teardown_appcontext
    def _close_db(exc: BaseException | None) -> None:
        db = g.pop("_db", None)
        if db is not None:
            db.close()


def _ensure_schema(db: sqlite3.Connection) -> None:
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
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_books_status  ON books(status);
        CREATE INDEX IF NOT EXISTS idx_books_author  ON books(author COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_reviews_book  ON reviews(book_id);
    """)
    db.commit()
    log.info("Database schema verified.")


# ── ISBN metadata (Open Library) ──────────────────────────────────────────────
def _fetch_openlibrary(isbn: str) -> dict | None:
    url = (
        "https://openlibrary.org/api/books"
        f"?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "PageVault/1.0 (github.com/ChristianAbele02/PageVault)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        book = data.get(f"ISBN:{isbn}")
        if not book:
            return None
        covers = book.get("cover", {})
        authors = ", ".join(a.get("name", "") for a in book.get("authors", []))
        publishers = book.get("publishers", [])
        subjects = book.get("subjects", [])
        genre = subjects[0].get("name", "") if subjects else None
        return {
            "isbn": isbn,
            "title": book.get("title", "Unknown Title"),
            "author": authors or None,
            "cover_url": (
                covers.get("large") or covers.get("medium") or covers.get("small")
            ),
            "description": (
                (book.get("excerpts") or [{}])[0].get("text") or None
            ),
            "publisher": publishers[0].get("name") if publishers else None,
            "year": book.get("publish_date") or None,
            "pages": book.get("number_of_pages"),
            "genre": genre,
        }
    except Exception as exc:
        log.warning("Open Library lookup failed for ISBN %s: %s", isbn, exc)
        return None


def lookup_isbn(isbn: str) -> dict | None:
    clean = isbn.strip().replace("-", "").replace(" ", "")
    if not clean:
        return None
    return _fetch_openlibrary(clean)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _validate_status(value: str | None) -> bool:
    if value is None:
        return False
    return value in {"want_to_read", "reading", "read"}


# ── API Blueprint ─────────────────────────────────────────────────────────────
def _api_bp():
    from flask import Blueprint

    bp = Blueprint("api", __name__, url_prefix="/api")

    # ── /api/lookup/<isbn> ────────────────────────────────────────────────────
    @bp.get("/lookup/<isbn>")
    def api_lookup(isbn: str):
        data = lookup_isbn(isbn)
        if not data:
            return _err("Book not found for this ISBN", 404)
        return jsonify(data)

    # ── /api/books ────────────────────────────────────────────────────────────
    @bp.get("/books")
    def api_list_books():
        db = get_db()
        status = request.args.get("status", "").strip()
        q = request.args.get("q", "").strip()
        sort = request.args.get("sort", "added_at")
        order = "ASC" if request.args.get("order", "desc").lower() == "asc" else "DESC"

        allowed_sorts = {"added_at", "title", "author", "avg_rating", "year"}
        if sort not in allowed_sorts:
            sort = "added_at"

        sql = """
            SELECT b.*,
                   ROUND(AVG(r.rating), 1) AS avg_rating,
                   COUNT(r.id)              AS review_count
            FROM books b
            LEFT JOIN reviews r ON r.book_id = b.id
        """
        conditions, params = [], []
        if status:
            conditions.append("b.status = ?")
            params.append(status)
        if q:
            conditions.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sort_col = "avg_rating" if sort == "avg_rating" else f"b.{sort}"
        sql += f" GROUP BY b.id ORDER BY {sort_col} {order}"

        rows = db.execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])

    @bp.post("/books")
    def api_add_book():
        db = get_db()
        payload = request.get_json(force=True, silent=True) or {}
        isbn = payload.get("isbn", "").strip().replace("-", "")
        status = payload.get("status", "want_to_read")

        if not isbn:
            return _err("isbn is required")
        if not _validate_status(status):
            return _err("status must be one of: want_to_read, reading, read")

        existing = db.execute("SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone()
        if existing:
            return _err("Book already in your library", 409)

        book = payload.get("book_data") or lookup_isbn(isbn)
        if not book:
            return _err("Could not fetch metadata — try providing book_data manually", 404)

        now = _now()
        db.execute(
            """INSERT INTO books
               (isbn, title, author, cover_url, description, publisher,
                year, pages, genre, language, added_at, updated_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                isbn,
                book.get("title", "Unknown"),
                book.get("author"),
                book.get("cover_url"),
                book.get("description"),
                book.get("publisher"),
                book.get("year"),
                book.get("pages"),
                book.get("genre"),
                book.get("language", "en"),
                now, now,
                status,
            ),
        )
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = db.execute(
            """SELECT b.*, 0 AS avg_rating, 0 AS review_count
               FROM books b WHERE b.id = ?""",
            (new_id,),
        ).fetchone()
        log.info("Book added: %s (ISBN %s)", book.get("title"), isbn)
        return jsonify(dict(row)), 201

    # ── /api/books/<id> ───────────────────────────────────────────────────────
    @bp.get("/books/<int:book_id>")
    def api_get_book(book_id: int):
        db = get_db()
        row = db.execute(
            """SELECT b.*,
                      ROUND(AVG(r.rating), 1) AS avg_rating,
                      COUNT(r.id)              AS review_count
               FROM books b
               LEFT JOIN reviews r ON r.book_id = b.id
               WHERE b.id = ? GROUP BY b.id""",
            (book_id,),
        ).fetchone()
        if not row:
            return _err("Book not found", 404)
        result = dict(row)
        reviews = db.execute(
            "SELECT * FROM reviews WHERE book_id = ? ORDER BY created_at DESC",
            (book_id,),
        ).fetchall()
        result["reviews"] = [dict(r) for r in reviews]
        return jsonify(result)

    @bp.patch("/books/<int:book_id>")
    def api_update_book(book_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone():
            return _err("Book not found", 404)
        payload = request.get_json(force=True, silent=True) or {}
        allowed = {"status", "title", "author", "description", "genre", "language"}
        updates = {k: v for k, v in payload.items() if k in allowed}
        if not updates:
            return _err("No valid fields to update")
        if "status" in updates and not _validate_status(updates["status"]):
            return _err("status must be one of: want_to_read, reading, read")
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        db.execute(
            f"UPDATE books SET {set_clause} WHERE id = ?",
            (*updates.values(), book_id),
        )
        db.commit()
        return jsonify({"ok": True})

    @bp.delete("/books/<int:book_id>")
    def api_delete_book(book_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone():
            return _err("Book not found", 404)
        db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        db.commit()
        log.info("Book %d deleted.", book_id)
        return jsonify({"ok": True})

    # ── /api/books/<id>/reviews ───────────────────────────────────────────────
    @bp.post("/books/<int:book_id>/reviews")
    def api_add_review(book_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone():
            return _err("Book not found", 404)
        payload = request.get_json(force=True, silent=True) or {}
        rating = payload.get("rating")
        comment = (payload.get("comment") or "").strip() or None
        if rating is not None:
            try:
                rating = int(rating)
            except ValueError:
                return _err("rating must be an integer 1–5")
            if not 1 <= rating <= 5:
                return _err("rating must be an integer 1–5")
        if rating is None and comment is None:
            return _err("Provide at least a rating or a comment")
        now = _now()
        db.execute(
            "INSERT INTO reviews (book_id, rating, comment, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (book_id, rating, comment, now, now),
        )
        db.commit()
        return jsonify({"ok": True}), 201

    @bp.delete("/books/<int:book_id>/reviews/<int:review_id>")
    def api_delete_review(book_id: int, review_id: int):
        db = get_db()
        db.execute(
            "DELETE FROM reviews WHERE id = ? AND book_id = ?",
            (review_id, book_id),
        )
        db.commit()
        return jsonify({"ok": True})

    # ── /api/stats ────────────────────────────────────────────────────────────
    @bp.get("/stats")
    def api_stats():
        db = get_db()
        row = db.execute(
            """SELECT
                COUNT(DISTINCT b.id)                               AS total,
                COUNT(DISTINCT CASE WHEN b.status='read'         THEN b.id END) AS read,
                COUNT(DISTINCT CASE WHEN b.status='reading'      THEN b.id END) AS reading,
                COUNT(DISTINCT CASE WHEN b.status='want_to_read' THEN b.id END) AS want_to_read,
                ROUND(AVG(r.rating), 1)                            AS avg_rating,
                COUNT(DISTINCT r.id)                               AS total_reviews
               FROM books b
               LEFT JOIN reviews r ON r.book_id = b.id"""
        ).fetchone()
        return jsonify(dict(row))

    # ── /api/export ───────────────────────────────────────────────────────────
    @bp.get("/export")
    def api_export():
        """Export entire library as JSON."""
        db = get_db()
        books = [
            dict(r)
            for r in db.execute("SELECT * FROM books ORDER BY title").fetchall()
        ]
        reviews = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM reviews ORDER BY book_id, created_at"
            ).fetchall()
        ]
        return jsonify({"exported_at": _now(), "books": books, "reviews": reviews})

    # ── Global error handlers ─────────────────────────────────────────────────
    @bp.app_errorhandler(404)
    def not_found(_):
        return _err("Not found", 404)

    @bp.app_errorhandler(405)
    def method_not_allowed(_):
        return _err("Method not allowed", 405)

    @bp.app_errorhandler(500)
    def internal_error(exc):
        log.exception("Unhandled exception: %s", exc)
        return _err("Internal server error", 500)

    return bp


def main() -> None:
    import socket

    app = create_app()
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"

    print("\n📚  PageVault is running!")
    print(f"    Local  → http://localhost:{port}")
    print(f"    Phone  → http://{local_ip}:{port}  (same Wi-Fi)\n")
    app.run(host=host, port=port, debug=debug)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
