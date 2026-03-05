"""API blueprint for PageVault.

This module owns route registration and endpoint behavior for the REST API.
The application entrypoint (`app.py`) injects runtime dependencies (database access,
lookup providers, validators, and helpers) so this module stays modular and easy
to test in isolation.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, Response, jsonify, request


def create_api_blueprint(*, deps: dict[str, Any]) -> Blueprint:
    """Create and return the `/api` blueprint.

    Parameters
    ----------
    deps:
        Dependency injection container. Required keys:
        - `get_db`: callable returning sqlite3 connection
        - `lookup_isbn`: callable ISBN lookup with fallback chain
        - `merge_lookup_data`: callable for metadata merging
        - `now`: callable producing UTC ISO timestamp
        - `err`: callable returning JSON error response tuple
        - `validate_status`: callable status validator
        - `validate_logo_url`: callable logo URL validator
        - `normalize_tags`: callable to sanitize/de-duplicate tags
        - `int_list`: callable parsing int lists
        - `normalize_isbn`: callable ISBN normalizer
        - `split_multi_value`: callable parser for comma/pipe-separated fields
        - `status_from_goodreads`: callable Goodreads shelf -> status mapper
        - `log`: logger instance
    """

    get_db = deps["get_db"]
    lookup_isbn = deps["lookup_isbn"]
    merge_lookup_data = deps["merge_lookup_data"]
    now = deps["now"]
    err = deps["err"]
    validate_status = deps["validate_status"]
    validate_logo_url = deps["validate_logo_url"]
    normalize_tags = deps["normalize_tags"]
    int_list = deps["int_list"]
    normalize_isbn = deps["normalize_isbn"]
    split_multi_value = deps["split_multi_value"]
    status_from_goodreads = deps["status_from_goodreads"]
    log = deps["log"]

    def fetch_book_shelves(db: sqlite3.Connection, book_id: int) -> list[dict]:
        rows = db.execute(
            """SELECT s.id, s.name, s.logo_url
               FROM shelves s
               JOIN book_shelves bs ON bs.shelf_id = s.id
               WHERE bs.book_id = ?
               ORDER BY s.name COLLATE NOCASE""",
            (book_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def fetch_book_tags(db: sqlite3.Connection, book_id: int) -> list[str]:
        rows = db.execute(
            """SELECT t.name
               FROM tags t
               JOIN book_tags bt ON bt.tag_id = t.id
               WHERE bt.book_id = ?
               ORDER BY t.name COLLATE NOCASE""",
            (book_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def replace_book_shelves(db: sqlite3.Connection, book_id: int, shelf_ids: list[int]) -> None:
        db.execute("DELETE FROM book_shelves WHERE book_id = ?", (book_id,))
        if not shelf_ids:
            return
        valid_ids = {
            r["id"]
            for r in db.execute(
                "SELECT id FROM shelves WHERE id IN ({})".format(",".join("?" for _ in shelf_ids)),
                shelf_ids,
            ).fetchall()
        }
        for shelf_id in shelf_ids:
            if shelf_id in valid_ids:
                db.execute(
                    "INSERT OR IGNORE INTO book_shelves (book_id, shelf_id) VALUES (?, ?)",
                    (book_id, shelf_id),
                )

    def replace_book_tags(db: sqlite3.Connection, book_id: int, tags: list[str]) -> None:
        db.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
        if not tags:
            return
        for tag in tags:
            db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            tag_row = db.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if tag_row:
                db.execute(
                    "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
                    (book_id, tag_row["id"]),
                )

    def with_book_relations(db: sqlite3.Connection, book_row: sqlite3.Row | None):
        if not book_row:
            return None
        result = dict(book_row)
        pages = result.get("pages")
        current_page = result.get("current_page")
        if pages and current_page is not None:
            progress = round((max(0, min(current_page, pages)) / pages) * 100, 1)
        else:
            progress = None
        result["progress_percent"] = progress
        result["genre_tags"] = fetch_book_tags(db, result["id"])
        result["shelves"] = fetch_book_shelves(db, result["id"])
        return result

    def ensure_shelf(db: sqlite3.Connection, name: str) -> int | None:
        clean_name = (name or "").strip()
        if not clean_name:
            return None
        row = db.execute("SELECT id FROM shelves WHERE name = ?", (clean_name,)).fetchone()
        if row:
            return row["id"]
        current = now()
        db.execute(
            "INSERT INTO shelves (name, logo_url, created_at, updated_at) VALUES (?, NULL, ?, ?)",
            (clean_name, current, current),
        )
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

    bp = Blueprint("api", __name__, url_prefix="/api")

    @bp.get("/lookup/<isbn>")
    def api_lookup(isbn: str):
        data = lookup_isbn(isbn)
        if not data:
            return err("Book not found for this ISBN", 404)
        return jsonify(data)

    @bp.get("/books")
    def api_list_books():
        db = get_db()
        status = request.args.get("status", "").strip()
        q = request.args.get("q", "").strip()
        author = request.args.get("author", "").strip()
        genre = request.args.get("genre", "").strip()
        shelf_id = request.args.get("shelf_id", "").strip()
        continue_reading = request.args.get("continue_reading", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        sort = request.args.get("sort", "added_at")
        order = "ASC" if request.args.get("order", "desc").lower() == "asc" else "DESC"

        allowed_sorts = {"added_at", "title", "author", "avg_rating", "year"}
        if sort not in allowed_sorts:
            sort = "added_at"

        sql = """
            SELECT b.*,
                   rs.avg_rating,
                                     COALESCE(rs.review_count, 0) AS review_count,
                                     (
                                             SELECT r.current_page
                                             FROM reviews r
                                             WHERE r.book_id = b.id
                                                 AND r.current_page IS NOT NULL
                                             ORDER BY r.created_at DESC, r.id DESC
                                             LIMIT 1
                                     ) AS current_page
            FROM books b
            LEFT JOIN (
                SELECT book_id,
                       ROUND(AVG(rating), 1) AS avg_rating,
                       COUNT(id) AS review_count
                FROM reviews
                GROUP BY book_id
            ) rs ON rs.book_id = b.id
        """
        conditions, params = [], []
        if status:
            conditions.append("b.status = ?")
            params.append(status)
        if q:
            conditions.append(
                """(
                    b.title LIKE ?
                    OR b.author LIKE ?
                    OR b.isbn LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM book_tags bt
                        JOIN tags t ON t.id = bt.tag_id
                        WHERE bt.book_id = b.id AND t.name LIKE ?
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM book_shelves bs
                        JOIN shelves s ON s.id = bs.shelf_id
                        WHERE bs.book_id = b.id AND s.name LIKE ?
                    )
                )"""
            )
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
        if author:
            conditions.append("b.author LIKE ?")
            params.append(f"%{author}%")
        if genre:
            conditions.append(
                """(
                    b.genre LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM book_tags bt
                        JOIN tags t ON t.id = bt.tag_id
                        WHERE bt.book_id = b.id AND t.name LIKE ?
                    )
                )"""
            )
            params.extend([f"%{genre}%", f"%{genre}%"])
        if shelf_id:
            try:
                shelf_id_int = int(shelf_id)
            except ValueError:
                return err("shelf_id must be an integer")
            conditions.append(
                "EXISTS (SELECT 1 FROM book_shelves bs WHERE bs.book_id = b.id AND bs.shelf_id = ?)"
            )
            params.append(shelf_id_int)
        if continue_reading:
            latest_progress_sql = """COALESCE((
                SELECT r.current_page
                FROM reviews r
                WHERE r.book_id = b.id
                  AND r.current_page IS NOT NULL
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT 1
            ), 0)"""
            conditions.append("b.status = 'reading'")
            conditions.append(f"{latest_progress_sql} > 0")
            conditions.append(f"(b.pages IS NULL OR {latest_progress_sql} < b.pages)")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sort_col = "avg_rating" if sort == "avg_rating" else f"b.{sort}"
        sql += f" ORDER BY {sort_col} {order}"

        rows = db.execute(sql, params).fetchall()
        return jsonify([with_book_relations(db, r) for r in rows])

    @bp.post("/books")
    def api_add_book():
        db = get_db()
        payload = request.get_json(force=True, silent=True) or {}
        isbn = payload.get("isbn", "").strip().replace("-", "")
        status = payload.get("status", "want_to_read")
        genre_tags = normalize_tags(payload.get("genre_tags"))
        shelf_ids = int_list(payload.get("shelf_ids"))

        if not isbn:
            return err("isbn is required")
        if not validate_status(status):
            return err("status must be one of: want_to_read, reading, read")

        existing = db.execute("SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone()
        if existing:
            return err("Book already in your library", 409)

        book = payload.get("book_data") or lookup_isbn(isbn)
        if not book:
            return err("Could not fetch metadata — try providing book_data manually", 404)

        current = now()
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
                current,
                current,
                status,
            ),
        )
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        replace_book_shelves(db, new_id, shelf_ids)
        replace_book_tags(db, new_id, genre_tags)
        db.commit()
        row = db.execute(
            """SELECT b.*, 0 AS avg_rating, 0 AS review_count
               FROM books b WHERE b.id = ?""",
            (new_id,),
        ).fetchone()
        log.info("Book added: %s (ISBN %s)", book.get("title"), isbn)
        return jsonify(with_book_relations(db, row)), 201

    @bp.get("/books/<int:book_id>")
    def api_get_book(book_id: int):
        db = get_db()
        row = db.execute(
            """SELECT b.*,
                      rs.avg_rating,
                                            COALESCE(rs.review_count, 0) AS review_count,
                                            (
                                                    SELECT r.current_page
                                                    FROM reviews r
                                                    WHERE r.book_id = b.id
                                                        AND r.current_page IS NOT NULL
                                                    ORDER BY r.created_at DESC, r.id DESC
                                                    LIMIT 1
                                            ) AS current_page
               FROM books b
               LEFT JOIN (
                    SELECT book_id,
                           ROUND(AVG(rating), 1) AS avg_rating,
                           COUNT(id) AS review_count
                    FROM reviews
                    GROUP BY book_id
               ) rs ON rs.book_id = b.id
               WHERE b.id = ?""",
            (book_id,),
        ).fetchone()
        if not row:
            return err("Book not found", 404)
        result = with_book_relations(db, row)
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
            return err("Book not found", 404)
        payload = request.get_json(force=True, silent=True) or {}
        allowed = {"status", "title", "author", "description", "genre", "language"}
        updates = {k: v for k, v in payload.items() if k in allowed}
        genre_tags = normalize_tags(payload.get("genre_tags")) if "genre_tags" in payload else None
        shelf_ids = int_list(payload.get("shelf_ids")) if "shelf_ids" in payload else None

        if not updates and genre_tags is None and shelf_ids is None:
            return err("No valid fields to update")
        if "status" in updates and not validate_status(updates["status"]):
            return err("status must be one of: want_to_read, reading, read")
        if updates:
            updates["updated_at"] = now()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            db.execute(
                f"UPDATE books SET {set_clause} WHERE id = ?",
                (*updates.values(), book_id),
            )
        if genre_tags is not None:
            replace_book_tags(db, book_id, genre_tags)
        if shelf_ids is not None:
            replace_book_shelves(db, book_id, shelf_ids)
        db.commit()
        return jsonify({"ok": True})

    @bp.get("/shelves")
    def api_list_shelves():
        db = get_db()
        rows = db.execute(
            """SELECT s.*, COUNT(bs.book_id) AS book_count
               FROM shelves s
               LEFT JOIN book_shelves bs ON bs.shelf_id = s.id
               GROUP BY s.id
               ORDER BY s.name COLLATE NOCASE"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @bp.post("/shelves")
    def api_add_shelf():
        db = get_db()
        payload = request.get_json(force=True, silent=True) or {}
        name = (payload.get("name") or "").strip()
        logo_url = (payload.get("logo_url") or "").strip() or None

        if not name:
            return err("name is required")
        if not validate_logo_url(logo_url):
            return err("logo_url must be a valid http/https URL")

        current = now()
        try:
            db.execute(
                "INSERT INTO shelves (name, logo_url, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, logo_url, current, current),
            )
        except sqlite3.IntegrityError:
            return err("Shelf already exists", 409)
        db.commit()
        shelf_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = db.execute(
            """SELECT s.*, COUNT(bs.book_id) AS book_count
               FROM shelves s
               LEFT JOIN book_shelves bs ON bs.shelf_id = s.id
               WHERE s.id = ?
               GROUP BY s.id""",
            (shelf_id,),
        ).fetchone()
        return jsonify(dict(row)), 201

    @bp.patch("/shelves/<int:shelf_id>")
    def api_update_shelf(shelf_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM shelves WHERE id = ?", (shelf_id,)).fetchone():
            return err("Shelf not found", 404)

        payload = request.get_json(force=True, silent=True) or {}
        updates = {}
        if "name" in payload:
            name = (payload.get("name") or "").strip()
            if not name:
                return err("name cannot be empty")
            updates["name"] = name
        if "logo_url" in payload:
            logo_url = (payload.get("logo_url") or "").strip() or None
            if not validate_logo_url(logo_url):
                return err("logo_url must be a valid http/https URL")
            updates["logo_url"] = logo_url

        if not updates:
            return err("No valid fields to update")

        updates["updated_at"] = now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        try:
            db.execute(
                f"UPDATE shelves SET {set_clause} WHERE id = ?",
                (*updates.values(), shelf_id),
            )
        except sqlite3.IntegrityError:
            return err("Shelf already exists", 409)
        db.commit()
        return jsonify({"ok": True})

    @bp.delete("/shelves/<int:shelf_id>")
    def api_delete_shelf(shelf_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM shelves WHERE id = ?", (shelf_id,)).fetchone():
            return err("Shelf not found", 404)
        db.execute("DELETE FROM shelves WHERE id = ?", (shelf_id,))
        db.commit()
        return jsonify({"ok": True})

    @bp.delete("/books/<int:book_id>")
    def api_delete_book(book_id: int):
        db = get_db()
        if not db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone():
            return err("Book not found", 404)
        db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        db.commit()
        log.info("Book %d deleted.", book_id)
        return jsonify({"ok": True})

    @bp.post("/books/refresh")
    def api_refresh_books():
        """Refresh metadata for all books without touching reviews/tags/shelves."""
        db = get_db()
        rows = db.execute("SELECT * FROM books ORDER BY id").fetchall()

        total = len(rows)
        updated = 0
        skipped = 0

        for row in rows:
            metadata = lookup_isbn(row["isbn"])
            if not metadata:
                skipped += 1
                continue

            updates = {}
            for field in [
                "title",
                "author",
                "cover_url",
                "description",
                "publisher",
                "year",
                "pages",
                "genre",
                "language",
            ]:
                value = metadata.get(field)
                if value in (None, ""):
                    continue
                updates[field] = value

            if not updates:
                skipped += 1
                continue

            updates["updated_at"] = now()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            db.execute(
                f"UPDATE books SET {set_clause} WHERE id = ?",
                (*updates.values(), row["id"]),
            )
            updated += 1

        db.commit()
        return jsonify({"ok": True, "total": total, "updated": updated, "skipped": skipped})

    @bp.post("/books/<int:book_id>/reviews")
    def api_add_review(book_id: int):
        db = get_db()
        book = db.execute("SELECT id, pages FROM books WHERE id=?", (book_id,)).fetchone()
        if not book:
            return err("Book not found", 404)
        payload = request.get_json(force=True, silent=True) or {}
        rating = payload.get("rating")
        comment = (payload.get("comment") or "").strip() or None
        current_page = payload.get("current_page")
        if rating is not None:
            try:
                rating = int(rating)
            except ValueError:
                return err("rating must be an integer 1–5")
            if not 1 <= rating <= 5:
                return err("rating must be an integer 1–5")
        if current_page is not None and current_page != "":
            try:
                current_page = int(current_page)
            except (ValueError, TypeError):
                return err("current_page must be a non-negative integer")
            if current_page < 0:
                return err("current_page must be a non-negative integer")
            if book["pages"] and current_page > book["pages"]:
                return err("current_page cannot exceed total pages")
        else:
            current_page = None

        if rating is None and comment is None and current_page is None:
            return err("Provide at least a rating, comment, or current_page")
        current = now()
        db.execute(
            "INSERT INTO reviews (book_id, rating, comment, current_page, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (book_id, rating, comment, current_page, current, current),
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

    @bp.get("/stats/analysis")
    def api_stats_analysis():
        db = get_db()

        start_date = (request.args.get("start_date") or "").strip()
        end_date = (request.args.get("end_date") or "").strip()

        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return err("start_date must be YYYY-MM-DD")
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return err("end_date must be YYYY-MM-DD")
        if start_dt and end_dt and start_dt > end_dt:
            return err("start_date must be before or equal to end_date")

        start_iso = start_dt.strftime("%Y-%m-%dT00:00:00") if start_dt else None
        end_iso_exclusive = (
            (end_dt + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00") if end_dt else None
        )

        book_conditions = []
        book_params: list[Any] = []
        if start_iso:
            book_conditions.append("b.added_at >= ?")
            book_params.append(start_iso)
        if end_iso_exclusive:
            book_conditions.append("b.added_at < ?")
            book_params.append(end_iso_exclusive)
        book_where = f" WHERE {' AND '.join(book_conditions)}" if book_conditions else ""

        review_conditions = []
        review_params: list[Any] = []
        if start_iso:
            review_conditions.append("r.created_at >= ?")
            review_params.append(start_iso)
        if end_iso_exclusive:
            review_conditions.append("r.created_at < ?")
            review_params.append(end_iso_exclusive)

        review_with_books_conditions = ["b.id = r.book_id"]
        review_with_books_params: list[Any] = []
        if book_conditions:
            review_with_books_conditions.extend(book_conditions)
            review_with_books_params.extend(book_params)
        if review_conditions:
            review_with_books_conditions.extend(review_conditions)
            review_with_books_params.extend(review_params)
        review_with_books_where = " WHERE " + " AND ".join(review_with_books_conditions)

        summary_books_row = db.execute(
            f"""SELECT
                COUNT(*) AS total_books,
                COALESCE(SUM(COALESCE(b.pages, 0)), 0) AS total_pages,
                COUNT(CASE WHEN b.status = 'read' THEN 1 END) AS read,
                COUNT(CASE WHEN b.status = 'reading' THEN 1 END) AS reading,
                COUNT(CASE WHEN b.status = 'want_to_read' THEN 1 END) AS want_to_read
               FROM books b
               {book_where}""",
            book_params,
        ).fetchone()
        summary_reviews_row = db.execute(
            f"""SELECT
                COUNT(*) AS total_reviews,
                ROUND(AVG(r.rating), 1) AS avg_rating
               FROM reviews r
               JOIN books b ON b.id = r.book_id
               {review_with_books_where}""",
            review_with_books_params,
        ).fetchone()

        progress_rows = db.execute(
            f"""SELECT b.id,
                      b.status,
                      COALESCE(b.pages, 0) AS pages,
                      (
                        SELECT rv.current_page
                        FROM reviews rv
                        WHERE rv.book_id = b.id
                          AND rv.current_page IS NOT NULL
                        ORDER BY rv.created_at DESC, rv.id DESC
                        LIMIT 1
                      ) AS latest_current_page
               FROM books b
               {book_where}""",
            book_params,
        ).fetchall()

        pages_completed_estimate = 0
        for row in progress_rows:
            pages = int(row["pages"] or 0)
            latest_current = row["latest_current_page"]
            if row["status"] == "read":
                pages_completed_estimate += pages
            elif latest_current is not None and pages > 0:
                pages_completed_estimate += max(0, min(int(latest_current), pages))

        status_rows = db.execute(
            f"""SELECT b.status,
                      COUNT(*) AS book_count,
                      COALESCE(SUM(COALESCE(b.pages, 0)), 0) AS total_pages
               FROM books b
               {book_where}
               GROUP BY b.status""",
            book_params,
        ).fetchall()
        status_map = {
            "want_to_read": {"label": "Want to Read", "book_count": 0, "total_pages": 0},
            "reading": {"label": "Reading", "book_count": 0, "total_pages": 0},
            "read": {"label": "Read", "book_count": 0, "total_pages": 0},
        }
        for row in status_rows:
            if row["status"] in status_map:
                status_map[row["status"]]["book_count"] = int(row["book_count"])
                status_map[row["status"]]["total_pages"] = int(row["total_pages"])
        status_breakdown = [
            {"status": key, **status_map[key]} for key in ["want_to_read", "reading", "read"]
        ]

        genre_rows = db.execute(
            f"""WITH filtered_books AS (
                    SELECT *
                    FROM books b
                    {book_where}
                ),
                book_genres AS (
                    SELECT bt.book_id, t.name AS genre
                    FROM book_tags bt
                    JOIN tags t ON t.id = bt.tag_id
                    JOIN filtered_books fb ON fb.id = bt.book_id
                    UNION ALL
                    SELECT fb.id AS book_id, fb.genre AS genre
                    FROM filtered_books fb
                    WHERE fb.genre IS NOT NULL
                      AND TRIM(fb.genre) <> ''
                      AND NOT EXISTS (
                        SELECT 1
                        FROM book_tags bt2
                        WHERE bt2.book_id = fb.id
                      )
                )
                SELECT bg.genre,
                       COUNT(DISTINCT bg.book_id) AS book_count,
                       COALESCE(SUM(COALESCE(b.pages, 0)), 0) AS total_pages
                FROM book_genres bg
                JOIN books b ON b.id = bg.book_id
                GROUP BY bg.genre
                ORDER BY book_count DESC, total_pages DESC, bg.genre COLLATE NOCASE
                LIMIT 12""",
            book_params,
        ).fetchall()
        top_genres = [
            {
                "genre": row["genre"],
                "book_count": int(row["book_count"]),
                "total_pages": int(row["total_pages"]),
            }
            for row in genre_rows
        ]

        author_conditions = ["b.author IS NOT NULL", "TRIM(b.author) <> ''"]
        if book_conditions:
            author_conditions.extend(book_conditions)
        author_where = " WHERE " + " AND ".join(author_conditions)

        author_rows = db.execute(
            f"""SELECT b.author,
                      COUNT(*) AS book_count,
                      COALESCE(SUM(COALESCE(b.pages, 0)), 0) AS total_pages,
                      ROUND(AVG(rs.avg_rating), 2) AS avg_rating
               FROM books b
               LEFT JOIN (
                 SELECT r.book_id, AVG(r.rating) AS avg_rating
                 FROM reviews r
                 WHERE r.rating IS NOT NULL
                 GROUP BY r.book_id
               ) rs ON rs.book_id = b.id
               {author_where}
               GROUP BY b.author
               ORDER BY book_count DESC, total_pages DESC, b.author COLLATE NOCASE
               LIMIT 12""",
            book_params,
        ).fetchall()
        top_authors = [
            {
                "author": row["author"],
                "book_count": int(row["book_count"]),
                "total_pages": int(row["total_pages"]),
                "avg_rating": float(row["avg_rating"]) if row["avg_rating"] is not None else None,
            }
            for row in author_rows
        ]

        rating_rows = db.execute(
            f"""SELECT r.rating, COUNT(*) AS review_count
               FROM reviews r
               JOIN books b ON b.id = r.book_id
               {review_with_books_where}
                 AND r.rating IS NOT NULL
               GROUP BY r.rating
               ORDER BY r.rating""",
            review_with_books_params,
        ).fetchall()
        rating_distribution = [
            {"rating": int(row["rating"]), "review_count": int(row["review_count"])}
            for row in rating_rows
        ]

        monthly_review_rows = db.execute(
            f"""SELECT SUBSTR(r.created_at, 1, 7) AS month,
                      COUNT(*) AS review_count,
                      ROUND(AVG(r.rating), 2) AS avg_rating,
                      COALESCE(SUM(COALESCE(r.current_page, 0)), 0) AS pages_logged
               FROM reviews r
               JOIN books b ON b.id = r.book_id
               {review_with_books_where}
               GROUP BY SUBSTR(r.created_at, 1, 7)
               ORDER BY month""",
            review_with_books_params,
        ).fetchall()
        monthly_reviews = [
            {
                "month": row["month"],
                "review_count": int(row["review_count"]),
                "avg_rating": float(row["avg_rating"]) if row["avg_rating"] is not None else None,
                "pages_logged": int(row["pages_logged"]),
            }
            for row in monthly_review_rows
        ]

        monthly_added_rows = db.execute(
            f"""SELECT SUBSTR(b.added_at, 1, 7) AS month,
                      COUNT(*) AS books_added,
                      COALESCE(SUM(COALESCE(b.pages, 0)), 0) AS pages_added
               FROM books b
               {book_where}
               GROUP BY SUBSTR(b.added_at, 1, 7)
               ORDER BY month""",
            book_params,
        ).fetchall()
        monthly_additions = [
            {
                "month": row["month"],
                "books_added": int(row["books_added"]),
                "pages_added": int(row["pages_added"]),
            }
            for row in monthly_added_rows
        ]

        summary = dict(summary_books_row)
        summary["total_books"] = int(summary.get("total_books") or 0)
        summary["total_pages"] = int(summary.get("total_pages") or 0)
        summary["total_reviews"] = int(summary_reviews_row["total_reviews"] or 0)
        summary["avg_rating"] = summary_reviews_row["avg_rating"]
        summary["read"] = int(summary.get("read") or 0)
        summary["reading"] = int(summary.get("reading") or 0)
        summary["want_to_read"] = int(summary.get("want_to_read") or 0)
        summary["pages_completed_estimate"] = int(pages_completed_estimate)

        return jsonify(
            {
                "range": {
                    "start_date": start_date or None,
                    "end_date": end_date or None,
                },
                "summary": summary,
                "status_breakdown": status_breakdown,
                "top_genres": top_genres,
                "top_authors": top_authors,
                "rating_distribution": rating_distribution,
                "monthly_reviews": monthly_reviews,
                "monthly_additions": monthly_additions,
            }
        )

    @bp.get("/export")
    def api_export():
        db = get_db()
        books = [dict(r) for r in db.execute("SELECT * FROM books ORDER BY title").fetchall()]
        reviews = [
            dict(r)
            for r in db.execute("SELECT * FROM reviews ORDER BY book_id, created_at").fetchall()
        ]
        shelves = [dict(r) for r in db.execute("SELECT * FROM shelves ORDER BY name").fetchall()]
        book_shelves = [
            dict(r)
            for r in db.execute("SELECT * FROM book_shelves ORDER BY shelf_id, book_id").fetchall()
        ]
        tags = [dict(r) for r in db.execute("SELECT * FROM tags ORDER BY name").fetchall()]
        book_tags = [
            dict(r)
            for r in db.execute("SELECT * FROM book_tags ORDER BY book_id, tag_id").fetchall()
        ]
        return jsonify(
            {
                "exported_at": now(),
                "books": books,
                "reviews": reviews,
                "shelves": shelves,
                "book_shelves": book_shelves,
                "tags": tags,
                "book_tags": book_tags,
            }
        )

    @bp.get("/export/csv")
    def api_export_csv():
        db = get_db()
        rows = db.execute(
            """SELECT b.*,
                      ROUND(AVG(r.rating), 1) AS avg_rating,
                      COUNT(r.id)              AS review_count
               FROM books b
               LEFT JOIN reviews r ON r.book_id = b.id
               GROUP BY b.id
               ORDER BY b.title COLLATE NOCASE"""
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "isbn",
                "title",
                "author",
                "status",
                "publisher",
                "year",
                "pages",
                "language",
                "genre",
                "genre_tags",
                "shelves",
                "cover_url",
                "description",
                "avg_rating",
                "review_count",
                "latest_rating",
                "latest_review",
                "added_at",
                "updated_at",
            ]
        )

        for row in rows:
            book_id = row["id"]
            shelves = [s["name"] for s in fetch_book_shelves(db, book_id)]
            tags = fetch_book_tags(db, book_id)
            latest_review = db.execute(
                """SELECT rating, comment
                   FROM reviews
                   WHERE book_id = ?
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (book_id,),
            ).fetchone()

            writer.writerow(
                [
                    row["id"],
                    row["isbn"],
                    row["title"],
                    row["author"],
                    row["status"],
                    row["publisher"],
                    row["year"],
                    row["pages"],
                    row["language"],
                    row["genre"],
                    "|".join(tags),
                    "|".join(shelves),
                    row["cover_url"],
                    row["description"],
                    row["avg_rating"],
                    row["review_count"],
                    (latest_review["rating"] if latest_review else ""),
                    (latest_review["comment"] if latest_review else ""),
                    row["added_at"],
                    row["updated_at"],
                ]
            )

        filename = f"pagevault_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @bp.post("/import/csv")
    def api_import_csv():
        db = get_db()
        upload = request.files.get("file")
        if not upload:
            return err("CSV file is required", 400)

        try:
            text = upload.read().decode("utf-8-sig")
        except Exception:
            return err("Could not read CSV file", 400)

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return err("CSV is missing a header row", 400)

        imported = 0
        updated = 0
        skipped = 0
        reviews_added = 0

        for raw_row in reader:
            row = {str(k).strip(): (v or "").strip() for k, v in raw_row.items() if k is not None}
            isbn = (
                normalize_isbn(row.get("isbn"))
                or normalize_isbn(row.get("ISBN13"))
                or normalize_isbn(row.get("ISBN"))
            )
            if not isbn:
                skipped += 1
                continue

            title = row.get("title") or row.get("Title") or None
            author = row.get("author") or row.get("Author") or None
            publisher = row.get("publisher") or row.get("Publisher") or None
            year = (
                row.get("year") or row.get("Year Published") or row.get("Original Publication Year")
            )
            cover_url = row.get("cover_url") or None
            description = row.get("description") or None
            language = row.get("language") or "en"
            genre = row.get("genre") or None

            pages_value = row.get("pages") or row.get("Number of Pages")
            try:
                pages = int(pages_value) if pages_value else None
            except ValueError:
                pages = None

            status_raw = row.get("status") or row.get("Exclusive Shelf")
            status = (
                status_raw if validate_status(status_raw) else status_from_goodreads(status_raw)
            )

            lookup_data = lookup_isbn(isbn)
            metadata = merge_lookup_data(
                {
                    "isbn": isbn,
                    "title": title,
                    "author": author,
                    "cover_url": cover_url,
                    "description": description,
                    "publisher": publisher,
                    "year": year,
                    "pages": pages,
                    "genre": genre,
                    "language": language,
                },
                lookup_data,
            )

            genre_tags = normalize_tags(
                split_multi_value(row.get("genre_tags") or row.get("genres"))
                + (lookup_data.get("genre_tags") if lookup_data else [])
            )[:3]

            shelves_input = split_multi_value(row.get("shelves")) + split_multi_value(
                row.get("Bookshelves")
            )
            exclusive_shelf = (row.get("Exclusive Shelf") or "").strip()
            if exclusive_shelf and exclusive_shelf.lower() not in {
                "read",
                "currently-reading",
                "currently reading",
                "to-read",
                "to read",
            }:
                shelves_input.append(exclusive_shelf)

            shelf_ids = []
            for shelf_name in normalize_tags(shelves_input):
                shelf_id = ensure_shelf(db, shelf_name)
                if shelf_id is not None:
                    shelf_ids.append(shelf_id)

            existing = db.execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()
            current = now()

            if existing:
                updates = {}
                for field in [
                    "title",
                    "author",
                    "cover_url",
                    "description",
                    "publisher",
                    "year",
                    "pages",
                    "genre",
                    "language",
                ]:
                    existing_value = existing[field]
                    incoming_value = metadata.get(field)
                    if incoming_value and not existing_value:
                        updates[field] = incoming_value
                if updates:
                    updates["updated_at"] = current
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    db.execute(
                        f"UPDATE books SET {set_clause} WHERE id = ?",
                        (*updates.values(), existing["id"]),
                    )
                    updated += 1
                book_id = existing["id"]
            else:
                db.execute(
                    """INSERT INTO books
                       (isbn, title, author, cover_url, description, publisher,
                        year, pages, genre, language, added_at, updated_at, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        isbn,
                        metadata.get("title") or "Unknown",
                        metadata.get("author"),
                        metadata.get("cover_url"),
                        metadata.get("description"),
                        metadata.get("publisher"),
                        metadata.get("year"),
                        metadata.get("pages"),
                        metadata.get("genre"),
                        metadata.get("language") or "en",
                        current,
                        current,
                        status,
                    ),
                )
                book_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                imported += 1

            if shelf_ids:
                for shelf_id in set(shelf_ids):
                    db.execute(
                        "INSERT OR IGNORE INTO book_shelves (book_id, shelf_id) VALUES (?, ?)",
                        (book_id, shelf_id),
                    )

            for tag in genre_tags:
                db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                tag_row = db.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
                if tag_row:
                    db.execute(
                        "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
                        (book_id, tag_row["id"]),
                    )

            rating_value = row.get("my_rating") or row.get("latest_rating") or row.get("My Rating")
            comment_value = (
                row.get("my_review")
                or row.get("latest_review")
                or row.get("My Review")
                or row.get("Private Notes")
            )

            rating = None
            if rating_value:
                try:
                    parsed = int(float(rating_value))
                    if 1 <= parsed <= 5:
                        rating = parsed
                except ValueError:
                    rating = None
            comment = comment_value.strip() if comment_value else None

            if rating is not None or comment:
                existing_review = db.execute(
                    """SELECT 1 FROM reviews
                       WHERE book_id = ?
                         AND COALESCE(rating, -1) = COALESCE(?, -1)
                         AND COALESCE(comment, '') = COALESCE(?, '')""",
                    (book_id, rating, comment),
                ).fetchone()
                if not existing_review:
                    db.execute(
                        "INSERT INTO reviews (book_id, rating, comment, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (book_id, rating, comment, current, current),
                    )
                    reviews_added += 1

        db.commit()
        return jsonify(
            {
                "ok": True,
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "reviews_added": reviews_added,
            }
        )

    @bp.app_errorhandler(404)
    def not_found(_):
        return err("Not found", 404)

    @bp.app_errorhandler(405)
    def method_not_allowed(_):
        return err("Method not allowed", 405)

    @bp.app_errorhandler(500)
    def internal_error(exc):
        log.exception("Unhandled exception: %s", exc)
        return err("Internal server error", 500)

    return bp
