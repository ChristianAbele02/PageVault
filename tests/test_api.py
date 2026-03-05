"""
tests/test_api.py — PageVault API test suite
Run with: pytest -v
"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import app as app_module
from pagevault_core import metadata as core_metadata

# ── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_page_route(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        assert b"Reading Analytics" in r.data

    def test_empty_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.get_json()
        assert data["total"] == 0
        assert data["read"] == 0

    def test_empty_stats_analysis(self, client):
        r = client.get("/api/stats/analysis")
        assert r.status_code == 200
        data = r.get_json()
        assert data["summary"]["total_books"] == 0
        assert data["summary"]["total_pages"] == 0
        assert data["summary"]["pages_completed_estimate"] == 0
        assert {item["status"] for item in data["status_breakdown"]} == {
            "want_to_read",
            "reading",
            "read",
        }
        assert data["top_genres"] == []
        assert data["top_authors"] == []
        assert data["rating_distribution"] == []

    def test_stats_after_add(self, client, sample_book_payload):
        client.post("/api/books", json=sample_book_payload)
        r = client.get("/api/stats")
        data = r.get_json()
        assert data["total"] == 1
        assert data["read"] == 1

    def test_stats_analysis_with_books_reviews_tags(self, client):
        first = client.post(
            "/api/books",
            json={
                "isbn": "9780307277671",
                "status": "reading",
                "genre_tags": ["Post-Apocalyptic", "Drama"],
                "book_data": {
                    "title": "The Road",
                    "author": "Cormac McCarthy",
                    "pages": 287,
                    "genre": "Fiction",
                },
            },
        ).get_json()
        second = client.post(
            "/api/books",
            json={
                "isbn": "9780451524935",
                "status": "read",
                "genre_tags": ["Dystopian"],
                "book_data": {
                    "title": "1984",
                    "author": "George Orwell",
                    "pages": 328,
                    "genre": "Dystopian",
                },
            },
        ).get_json()

        client.post(f"/api/books/{first['id']}/reviews", json={"rating": 4, "current_page": 120})
        client.post(
            f"/api/books/{second['id']}/reviews", json={"rating": 5, "comment": "Masterpiece"}
        )

        data = client.get("/api/stats/analysis").get_json()
        assert data["summary"]["total_books"] == 2
        assert data["summary"]["read"] == 1
        assert data["summary"]["reading"] == 1
        assert data["summary"]["total_reviews"] == 2
        assert data["summary"]["pages_completed_estimate"] == 448

        assert any(item["genre"] == "Dystopian" for item in data["top_genres"])
        assert any(item["author"] == "George Orwell" for item in data["top_authors"])
        assert any(item["rating"] == 4 for item in data["rating_distribution"])
        assert any(item["rating"] == 5 for item in data["rating_distribution"])

    def test_stats_analysis_date_filter(self, client):
        old = client.post(
            "/api/books",
            json={
                "isbn": "9780140177398",
                "status": "read",
                "book_data": {
                    "title": "Of Mice and Men",
                    "author": "John Steinbeck",
                    "pages": 187,
                },
            },
        ).get_json()
        recent = client.post(
            "/api/books",
            json={
                "isbn": "9780307277671",
                "status": "reading",
                "book_data": {
                    "title": "The Road",
                    "author": "Cormac McCarthy",
                    "pages": 287,
                },
            },
        ).get_json()

        database_path = client.application.config["DATABASE"]
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "UPDATE books SET added_at = ?, updated_at = ? WHERE id = ?",
                ("2020-01-02T10:00:00", "2020-01-02T10:00:00", old["id"]),
            )
            connection.execute(
                "UPDATE books SET added_at = ?, updated_at = ? WHERE id = ?",
                ("2026-03-05T10:00:00", "2026-03-05T10:00:00", recent["id"]),
            )
            connection.commit()

        filtered = client.get("/api/stats/analysis?start_date=2026-01-01&end_date=2026-12-31")
        data = filtered.get_json()
        assert filtered.status_code == 200
        assert data["summary"]["total_books"] == 1
        assert data["summary"]["reading"] == 1
        assert data["summary"]["read"] == 0

    def test_stats_analysis_invalid_date_filter(self, client):
        response = client.get("/api/stats/analysis?start_date=2026-99-01")
        assert response.status_code == 400


class TestRoadmapApis:
    def test_goal_upsert_and_fetch(self, client):
        save = client.put(
            "/api/goals/current",
            json={"goal_year": 2026, "target_books": 24, "target_pages": 8400},
        )
        assert save.status_code == 200

        goal = client.get("/api/goals/current?year=2026")
        assert goal.status_code == 200
        payload = goal.get_json()
        assert payload["goal_year"] == 2026
        assert payload["target_books"] == 24
        assert payload["target_pages"] == 8400

    def test_reading_sessions_create_and_list(self, client):
        book = client.post(
            "/api/books",
            json={
                "isbn": "9780307277671",
                "status": "reading",
                "book_data": {
                    "title": "The Road",
                    "author": "Cormac McCarthy",
                    "pages": 287,
                },
            },
        ).get_json()

        created = client.post(
            f"/api/books/{book['id']}/sessions",
            json={
                "start_page": 40,
                "end_page": 74,
                "minutes_spent": 35,
                "session_date": "2026-03-01",
            },
        )
        assert created.status_code == 201

        sessions = client.get("/api/sessions?start_date=2026-03-01&end_date=2026-03-31")
        assert sessions.status_code == 200
        data = sessions.get_json()
        assert len(data) == 1
        assert data[0]["book_id"] == book["id"]
        assert data[0]["minutes_spent"] == 35

    def test_metadata_repair_job_updates_missing_fields(self, client, monkeypatch):
        original_lookup = app_module.lookup_isbn
        app_module.lookup_isbn = lambda _isbn: {
            "cover_url": "https://example.com/new-cover.jpg",
            "description": "Recovered description",
            "publisher": "Recovered Publisher",
            "year": "2025",
            "pages": 222,
            "genre": "Fiction",
            "language": "en",
        }
        try:
            book = client.post(
                "/api/books",
                json={
                    "isbn": "9780451524935",
                    "status": "want_to_read",
                    "book_data": {
                        "title": "1984",
                        "author": "George Orwell",
                        "cover_url": None,
                        "description": None,
                    },
                },
            ).get_json()

            repair = client.post("/api/metadata/repair", json={"max_retries": 1})
            assert repair.status_code == 200
            summary = repair.get_json()
            assert summary["total"] >= 1
            assert summary["updated"] >= 1

            refreshed = client.get(f"/api/books/{book['id']}").get_json()
            assert refreshed["cover_url"] == "https://example.com/new-cover.jpg"
            assert refreshed["description"] == "Recovered description"
        finally:
            app_module.lookup_isbn = original_lookup

    def test_backup_restore_validate_and_apply(self, client, tmp_path):
        backup_db = Path(tmp_path) / "backup.db"
        with sqlite3.connect(backup_db) as connection:
            connection.executescript(
                """
                CREATE TABLE books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    cover_url TEXT,
                    description TEXT,
                    publisher TEXT,
                    year TEXT,
                    pages INTEGER,
                    genre TEXT,
                    language TEXT,
                    added_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    rating INTEGER,
                    comment TEXT,
                    current_page INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE shelves (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, logo_url TEXT, created_at TEXT, updated_at TEXT);
                CREATE TABLE book_shelves (book_id INTEGER, shelf_id INTEGER);
                CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
                CREATE TABLE book_tags (book_id INTEGER, tag_id INTEGER);
                """
            )
            connection.execute(
                """INSERT INTO books
                   (isbn, title, author, cover_url, description, publisher, year, pages, genre, language, added_at, updated_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "9780140177398",
                    "Of Mice and Men",
                    "John Steinbeck",
                    None,
                    None,
                    None,
                    "1937",
                    187,
                    "Classic",
                    "en",
                    "2026-03-01T10:00:00",
                    "2026-03-01T10:00:00",
                    "read",
                ),
            )
            connection.commit()

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(backup_db, arcname="pagevault.db")
        archive_bytes = archive.getvalue()

        validated = client.post(
            "/api/backup/restore/validate",
            data={"file": (io.BytesIO(archive_bytes), "backup.zip")},
            content_type="multipart/form-data",
        )
        assert validated.status_code == 200
        validation_payload = validated.get_json()
        assert validation_payload["summary"]["books"] == 1

        applied = client.post(
            "/api/backup/restore/apply",
            data={"file": (io.BytesIO(archive_bytes), "backup.zip")},
            content_type="multipart/form-data",
        )
        assert applied.status_code == 200
        books = client.get("/api/books").get_json()
        assert len(books) == 1
        assert books[0]["title"] == "Of Mice and Men"

    def test_csv_preview_and_dry_run_with_mapping(self, client):
        csv_text = "MyIsbn,Title\n9780307277671,The Road\n"
        mapping = '{"MyIsbn":"isbn","Title":"title"}'

        preview = client.post(
            "/api/import/csv/preview",
            data={
                "file": (io.BytesIO(csv_text.encode("utf-8")), "import.csv"),
                "mapping": mapping,
            },
            content_type="multipart/form-data",
        )
        assert preview.status_code == 200
        preview_payload = preview.get_json()
        assert preview_payload["would_import"] == 1
        assert preview_payload["skipped"] == 0

        dry_run = client.post(
            "/api/import/csv?dry_run=1",
            data={
                "file": (io.BytesIO(csv_text.encode("utf-8")), "import.csv"),
                "mapping": mapping,
                "dry_run": "1",
            },
            content_type="multipart/form-data",
        )
        assert dry_run.status_code == 200
        dry_run_payload = dry_run.get_json()
        assert dry_run_payload["dry_run"] is True
        assert dry_run_payload["would_import"] == 1


# ── Books CRUD ────────────────────────────────────────────────────────────────


class TestBooks:
    def test_list_empty(self, client):
        r = client.get("/api/books")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_add_book(self, client, sample_book_payload):
        r = client.post("/api/books", json=sample_book_payload)
        assert r.status_code == 201
        data = r.get_json()
        assert data["title"] == "The Great Gatsby"
        assert data["author"] == "F. Scott Fitzgerald"
        assert data["status"] == "read"

    def test_add_duplicate_book(self, client, sample_book_payload):
        client.post("/api/books", json=sample_book_payload)
        r = client.post("/api/books", json=sample_book_payload)
        assert r.status_code == 409
        assert "already" in r.get_json()["error"].lower()

    def test_add_book_missing_isbn(self, client):
        r = client.post("/api/books", json={"book_data": {"title": "No ISBN"}})
        assert r.status_code == 400

    def test_get_book(self, client, added_book):
        book_id = added_book["id"]
        r = client.get(f"/api/books/{book_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["id"] == book_id
        assert "reviews" in data

    def test_get_book_not_found(self, client):
        r = client.get("/api/books/99999")
        assert r.status_code == 404

    def test_list_books_after_add(self, client, added_book):
        r = client.get("/api/books")
        assert r.status_code == 200
        books = r.get_json()
        assert len(books) == 1

    def test_list_books_filter_by_status(self, client, sample_book_payload):
        client.post("/api/books", json=sample_book_payload)
        r = client.get("/api/books?status=reading")
        assert r.get_json() == []
        r = client.get("/api/books?status=read")
        assert len(r.get_json()) == 1

    def test_list_books_search(self, client, added_book):
        r = client.get("/api/books?q=gatsby")
        assert len(r.get_json()) == 1
        r = client.get("/api/books?q=notexist")
        assert r.get_json() == []

    def test_list_books_filter_by_author(self, client):
        client.post(
            "/api/books",
            json={
                "isbn": "9780451524935",
                "status": "read",
                "book_data": {"title": "1984", "author": "George Orwell"},
            },
        )
        client.post(
            "/api/books",
            json={
                "isbn": "9780007448036",
                "status": "read",
                "book_data": {"title": "The Hobbit", "author": "J.R.R. Tolkien"},
            },
        )

        data = client.get("/api/books?author=Orwell").get_json()
        assert len(data) == 1
        assert data[0]["author"] == "George Orwell"

    def test_list_books_filter_by_genre_tag(self, client):
        client.post(
            "/api/books",
            json={
                "isbn": "9780451524936",
                "status": "read",
                "genre_tags": ["Dystopian", "Classic"],
                "book_data": {"title": "Animal Farm", "author": "George Orwell"},
            },
        )

        data = client.get("/api/books?genre=Dystopian").get_json()
        assert len(data) == 1
        assert "Dystopian" in data[0]["genre_tags"]

    def test_add_book_with_shelf_and_tags(self, client):
        shelf = client.post(
            "/api/shelves",
            json={"name": "Favorites", "logo_url": "https://example.com/fav.png"},
        ).get_json()

        r = client.post(
            "/api/books",
            json={
                "isbn": "9780141182803",
                "status": "reading",
                "shelf_ids": [shelf["id"]],
                "genre_tags": ["Classic", "Philosophy"],
                "book_data": {"title": "The Stranger", "author": "Albert Camus"},
            },
        )
        assert r.status_code == 201
        data = r.get_json()
        assert {s["name"] for s in data["shelves"]} == {"Favorites"}
        assert set(data["genre_tags"]) == {"Classic", "Philosophy"}

    def test_list_books_filter_by_shelf(self, client):
        shelf = client.post("/api/shelves", json={"name": "To Buy"}).get_json()

        client.post(
            "/api/books",
            json={
                "isbn": "9780140177398",
                "status": "want_to_read",
                "shelf_ids": [shelf["id"]],
                "book_data": {"title": "Of Mice and Men", "author": "John Steinbeck"},
            },
        )
        client.post(
            "/api/books",
            json={
                "isbn": "9780307277671",
                "status": "want_to_read",
                "book_data": {"title": "The Road", "author": "Cormac McCarthy"},
            },
        )

        data = client.get(f"/api/books?shelf_id={shelf['id']}").get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Of Mice and Men"

    def test_list_books_filter_continue_reading(self, client):
        in_progress = client.post(
            "/api/books",
            json={
                "isbn": "9780451524937",
                "status": "reading",
                "book_data": {"title": "Progress Book", "author": "Reader", "pages": 300},
            },
        ).get_json()
        finished = client.post(
            "/api/books",
            json={
                "isbn": "9780451524938",
                "status": "reading",
                "book_data": {"title": "Finished Book", "author": "Reader", "pages": 280},
            },
        ).get_json()

        client.post(f"/api/books/{in_progress['id']}/reviews", json={"current_page": 120})
        client.post(f"/api/books/{finished['id']}/reviews", json={"current_page": 280})

        data = client.get("/api/books?continue_reading=1").get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Progress Book"

    def test_update_book_status(self, client, added_book):
        book_id = added_book["id"]
        r = client.patch(f"/api/books/{book_id}", json={"status": "reading"})
        assert r.status_code == 200
        updated = client.get(f"/api/books/{book_id}").get_json()
        assert updated["status"] == "reading"

    def test_update_book_not_found(self, client):
        r = client.patch("/api/books/99999", json={"status": "read"})
        assert r.status_code == 404

    def test_update_book_no_valid_fields(self, client, added_book):
        r = client.patch(f"/api/books/{added_book['id']}", json={"isbn": "cant-change"})
        assert r.status_code == 400

    def test_delete_book(self, client, added_book):
        book_id = added_book["id"]
        r = client.delete(f"/api/books/{book_id}")
        assert r.status_code == 200
        r = client.get(f"/api/books/{book_id}")
        assert r.status_code == 404

    def test_delete_book_not_found(self, client):
        r = client.delete("/api/books/99999")
        assert r.status_code == 404

    def test_refresh_books_keeps_reviews_tags_and_shelves(self, client):
        shelf = client.post("/api/shelves", json={"name": "Favorites"}).get_json()

        add = client.post(
            "/api/books",
            json={
                "isbn": "9780307743657",
                "status": "read",
                "genre_tags": ["Horror", "CustomTag"],
                "shelf_ids": [shelf["id"]],
                "book_data": {
                    "title": "Old Title",
                    "author": "Old Author",
                    "cover_url": None,
                    "description": None,
                    "publisher": "Old Publisher",
                    "year": "2013",
                    "pages": 531,
                    "genre": "Horror",
                },
            },
        )
        book_id = add.get_json()["id"]

        client.post(
            f"/api/books/{book_id}/reviews",
            json={"rating": 5, "comment": "Great sequel"},
        )

        original_lookup = app_module.lookup_isbn
        app_module.lookup_isbn = lambda _isbn: {
            "isbn": "9780307743657",
            "title": "Doctor Sleep",
            "author": "Stephen King",
            "cover_url": "https://example.com/new-cover.jpg",
            "description": "Updated metadata",
            "publisher": "Scribner",
            "year": "2013",
            "pages": 531,
            "genre": "Thriller",
            "genre_tags": ["Thriller", "Fiction", "Supernatural"],
        }
        try:
            r = client.post("/api/books/refresh")
        finally:
            app_module.lookup_isbn = original_lookup

        assert r.status_code == 200
        data = r.get_json()
        assert data["updated"] == 1

        detail = client.get(f"/api/books/{book_id}").get_json()
        assert detail["title"] == "Doctor Sleep"
        assert detail["author"] == "Stephen King"
        assert detail["cover_url"] == "https://example.com/new-cover.jpg"
        assert detail["reviews"][0]["rating"] == 5
        assert {s["name"] for s in detail["shelves"]} == {"Favorites"}
        assert set(detail["genre_tags"]) == {"Horror", "CustomTag"}


# ── Reviews ───────────────────────────────────────────────────────────────────


class TestReviews:
    def test_add_review_rating_only(self, client, added_book):
        book_id = added_book["id"]
        r = client.post(f"/api/books/{book_id}/reviews", json={"rating": 5})
        assert r.status_code == 201

    def test_add_review_comment_only(self, client, added_book):
        book_id = added_book["id"]
        r = client.post(f"/api/books/{book_id}/reviews", json={"comment": "Great read!"})
        assert r.status_code == 201

    def test_add_review_both(self, client, added_book):
        book_id = added_book["id"]
        r = client.post(
            f"/api/books/{book_id}/reviews",
            json={"rating": 4, "comment": "Very good."},
        )
        assert r.status_code == 201

    def test_add_review_with_current_page(self, client, added_book):
        book_id = added_book["id"]
        r = client.post(
            f"/api/books/{book_id}/reviews",
            json={"current_page": 42},
        )
        assert r.status_code == 201

        detail = client.get(f"/api/books/{book_id}").get_json()
        assert detail["current_page"] == 42
        assert detail["progress_percent"] == 23.3
        assert detail["reviews"][0]["current_page"] == 42

        listing = client.get("/api/books").get_json()
        assert listing[0]["current_page"] == 42
        assert listing[0]["progress_percent"] == 23.3

    def test_add_review_invalid_rating(self, client, added_book):
        r = client.post(f"/api/books/{added_book['id']}/reviews", json={"rating": 6})
        assert r.status_code == 400

    def test_add_review_invalid_current_page(self, client, added_book):
        r = client.post(f"/api/books/{added_book['id']}/reviews", json={"current_page": -1})
        assert r.status_code == 400

    def test_add_review_current_page_exceeds_pages(self, client, added_book):
        r = client.post(f"/api/books/{added_book['id']}/reviews", json={"current_page": 999})
        assert r.status_code == 400

    def test_add_review_empty(self, client, added_book):
        r = client.post(f"/api/books/{added_book['id']}/reviews", json={})
        assert r.status_code == 400

    def test_add_review_book_not_found(self, client):
        r = client.post("/api/books/99999/reviews", json={"rating": 3})
        assert r.status_code == 404

    def test_reviews_appear_in_book_detail(self, client, added_book):
        book_id = added_book["id"]
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 5, "comment": "Excellent"})
        data = client.get(f"/api/books/{book_id}").get_json()
        assert len(data["reviews"]) == 1
        assert data["reviews"][0]["rating"] == 5
        assert data["avg_rating"] == 5.0

    def test_delete_review(self, client, added_book):
        book_id = added_book["id"]
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 3})
        detail = client.get(f"/api/books/{book_id}").get_json()
        review_id = detail["reviews"][0]["id"]
        r = client.delete(f"/api/books/{book_id}/reviews/{review_id}")
        assert r.status_code == 200
        detail = client.get(f"/api/books/{book_id}").get_json()
        assert detail["reviews"] == []

    def test_average_rating_multiple_reviews(self, client, added_book):
        book_id = added_book["id"]
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 4})
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 2})
        data = client.get(f"/api/books/{book_id}").get_json()
        assert data["avg_rating"] == 3.0

    def test_reviews_deleted_with_book(self, client, added_book):
        book_id = added_book["id"]
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 5})
        client.delete(f"/api/books/{book_id}")
        # If the book is gone, cascaded reviews are too (tested via FK)
        r = client.get(f"/api/books/{book_id}")
        assert r.status_code == 404


# ── Export ────────────────────────────────────────────────────────────────────


class TestExport:
    def test_export_empty(self, client):
        r = client.get("/api/export")
        assert r.status_code == 200
        data = r.get_json()
        assert data["books"] == []
        assert data["reviews"] == []
        assert "exported_at" in data

    def test_export_with_data(self, client, added_book):
        book_id = added_book["id"]
        client.post(f"/api/books/{book_id}/reviews", json={"rating": 5})
        data = client.get("/api/export").get_json()
        assert len(data["books"]) == 1
        assert len(data["reviews"]) == 1
        assert "shelves" in data
        assert "book_shelves" in data
        assert "tags" in data
        assert "book_tags" in data


class TestCsv:
    def test_export_csv_contains_tags_and_shelves(self, client):
        shelf = client.post("/api/shelves", json={"name": "Favorites"}).get_json()
        add = client.post(
            "/api/books",
            json={
                "isbn": "9780141182803",
                "status": "read",
                "genre_tags": ["Classic", "Philosophy"],
                "shelf_ids": [shelf["id"]],
                "book_data": {
                    "title": "The Stranger",
                    "author": "Albert Camus",
                    "publisher": "Vintage",
                    "year": "1942",
                },
            },
        ).get_json()
        client.post(f"/api/books/{add['id']}/reviews", json={"rating": 4, "comment": "Great"})

        r = client.get("/api/export/csv")
        assert r.status_code == 200
        assert "text/csv" in r.content_type
        text = r.data.decode("utf-8")
        assert "genre_tags" in text
        assert "shelves" in text
        assert "Classic|Philosophy" in text
        assert "Favorites" in text

    def test_import_goodreads_csv(self, client, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "lookup_isbn",
            lambda _isbn: {
                "isbn": "9780307743657",
                "cover_url": "https://example.com/doctor-sleep.jpg",
                "description": "Imported via fallback",
                "genre_tags": ["Horror", "Fiction"],
                "genre": "Horror",
            },
        )

        goodreads_csv = """Book Id,Title,Author,ISBN,ISBN13,My Rating,Publisher,Number of Pages,Year Published,Bookshelves,Exclusive Shelf,My Review\n1,Doctor Sleep,Stephen King,,9780307743657,5,Scribner,531,2013,horror,read,Excellent sequel\n"""

        r = client.post(
            "/api/import/csv",
            data={"file": (io.BytesIO(goodreads_csv.encode("utf-8")), "goodreads.csv")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        result = r.get_json()
        assert result["imported"] == 1

        books = client.get("/api/books").get_json()
        assert len(books) == 1
        assert books[0]["title"] == "Doctor Sleep"
        assert books[0]["status"] == "read"
        assert books[0]["cover_url"] == "https://example.com/doctor-sleep.jpg"

        detail = client.get(f"/api/books/{books[0]['id']}").get_json()
        assert any(s["name"] == "horror" for s in detail["shelves"])
        assert detail["reviews"][0]["rating"] == 5


# ── Shelves ───────────────────────────────────────────────────────────────────


class TestShelves:
    def test_create_shelf(self, client):
        r = client.post(
            "/api/shelves",
            json={"name": "Sci-Fi", "logo_url": "https://example.com/scifi.png"},
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data["name"] == "Sci-Fi"
        assert data["book_count"] == 0

    def test_create_duplicate_shelf(self, client):
        client.post("/api/shelves", json={"name": "Sci-Fi"})
        r = client.post("/api/shelves", json={"name": "Sci-Fi"})
        assert r.status_code == 409

    def test_update_shelf(self, client):
        shelf = client.post("/api/shelves", json={"name": "Old"}).get_json()
        r = client.patch(
            f"/api/shelves/{shelf['id']}",
            json={"name": "New", "logo_url": "https://example.com/new.png"},
        )
        assert r.status_code == 200
        shelves = client.get("/api/shelves").get_json()
        assert shelves[0]["name"] == "New"

    def test_delete_shelf(self, client):
        shelf = client.post("/api/shelves", json={"name": "Temp"}).get_json()
        r = client.delete(f"/api/shelves/{shelf['id']}")
        assert r.status_code == 200
        shelves = client.get("/api/shelves").get_json()
        assert shelves == []


# ── Frontend ──────────────────────────────────────────────────────────────────


class TestFrontend:
    def test_index_returns_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"PageVault" in r.data

    def test_404_returns_json(self, client):
        r = client.get("/api/nonexistent")
        assert r.status_code == 404
        assert r.get_json()["error"] == "Not found"


class TestLookup:
    def test_lookup_uses_ttl_cache_for_repeated_isbn(self, monkeypatch):
        core_metadata.clear_lookup_cache()
        calls = {"openlibrary": 0}

        def fake_openlibrary(_isbn):
            calls["openlibrary"] += 1
            return {
                "isbn": "9789999999991",
                "title": "Cached Book",
                "author": "Cached Author",
                "cover_url": "https://example.com/cached-cover.jpg",
                "description": "Cached Description",
                "publisher": "Cached Publisher",
                "year": "2025",
                "genre_tags": ["Cached"],
            }

        monkeypatch.setattr(app_module, "_fetch_openlibrary", fake_openlibrary)
        monkeypatch.setattr(app_module, "_fetch_googlebooks", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_crossref", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_search", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_covers", lambda _isbn: None)

        first = app_module.lookup_isbn("9789999999991")
        second = app_module.lookup_isbn("9789999999991")

        assert first is not None
        assert second is not None
        assert first["title"] == second["title"]
        assert calls["openlibrary"] == 1

        core_metadata.clear_lookup_cache()

    def test_lookup_returns_three_genre_tags_max(self, client, monkeypatch):
        def fake_lookup(_isbn):
            return {
                "isbn": "1234567890",
                "title": "Sample",
                "author": "Author",
                "genre": "Tag 1",
                "genre_tags": ["Tag 1", "Tag 2", "Tag 3"],
            }

        monkeypatch.setattr(app_module, "lookup_isbn", fake_lookup)

        r = client.get("/api/lookup/1234567890")
        assert r.status_code == 200
        data = r.get_json()
        assert data["genre_tags"] == ["Tag 1", "Tag 2", "Tag 3"]
        assert len(data["genre_tags"]) == 3

    def test_lookup_falls_back_when_openlibrary_missing_cover(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "_fetch_openlibrary",
            lambda _isbn: {
                "isbn": "9780000000001",
                "title": "Doctor Sleep",
                "author": "Stephen King",
                "cover_url": None,
                "description": None,
                "genre": "Horror",
                "genre_tags": ["Horror"],
            },
        )
        monkeypatch.setattr(
            app_module,
            "_fetch_googlebooks",
            lambda _isbn: {
                "isbn": "9780000000001",
                "cover_url": "https://books.google.com/doctor-sleep-cover.jpg",
                "description": "A sequel to The Shining.",
                "genre_tags": ["Thriller", "Fiction"],
            },
        )
        monkeypatch.setattr(app_module, "_fetch_openlibrary_search", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_covers", lambda _isbn: None)

        data = app_module.lookup_isbn("9780000000001")
        assert data is not None
        assert data["cover_url"] == "https://books.google.com/doctor-sleep-cover.jpg"
        assert data["description"] == "A sequel to The Shining."
        assert data["genre_tags"] == ["Horror", "Thriller", "Fiction"]

    def test_lookup_uses_googlebooks_when_openlibrary_missing(self, monkeypatch):
        monkeypatch.setattr(app_module, "_fetch_openlibrary", lambda _isbn: None)
        monkeypatch.setattr(
            app_module,
            "_fetch_googlebooks",
            lambda _isbn: {
                "isbn": "9780000000002",
                "title": "Fallback Title",
                "author": "Fallback Author",
                "cover_url": "https://books.google.com/fallback-cover.jpg",
                "genre_tags": ["Mystery", "Suspense"],
            },
        )
        monkeypatch.setattr(app_module, "_fetch_openlibrary_search", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_covers", lambda _isbn: None)

        data = app_module.lookup_isbn("9780000000002")
        assert data is not None
        assert data["title"] == "Fallback Title"
        assert data["cover_url"] == "https://books.google.com/fallback-cover.jpg"

    def test_lookup_uses_crossref_as_third_fallback(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "_fetch_openlibrary",
            lambda _isbn: {
                "isbn": "9780000000003",
                "title": "Partial",
                "author": None,
                "publisher": None,
                "year": None,
                "genre_tags": [],
            },
        )
        monkeypatch.setattr(app_module, "_fetch_googlebooks", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_search", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_covers", lambda _isbn: None)
        monkeypatch.setattr(
            app_module,
            "_fetch_crossref",
            lambda _isbn: {
                "isbn": "9780000000003",
                "author": "Cross Ref Author",
                "publisher": "Cross Ref Pub",
                "year": "2020",
                "genre_tags": ["Reference"],
            },
        )

        data = app_module.lookup_isbn("9780000000003")
        assert data is not None
        assert data["author"] == "Cross Ref Author"
        assert data["publisher"] == "Cross Ref Pub"
        assert data["year"] == "2020"

    def test_lookup_uses_openlibrary_search_as_additional_fallback(self, monkeypatch):
        monkeypatch.setattr(app_module, "_fetch_openlibrary", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_googlebooks", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_crossref", lambda _isbn: None)
        monkeypatch.setattr(
            app_module,
            "_fetch_openlibrary_search",
            lambda _isbn: {
                "isbn": "9780000000004",
                "title": "Search Title",
                "author": "Search Author",
                "publisher": "Search Publisher",
                "year": "2018",
                "genre_tags": ["Fantasy"],
            },
        )
        monkeypatch.setattr(app_module, "_fetch_openlibrary_covers", lambda _isbn: None)

        data = app_module.lookup_isbn("9780000000004")
        assert data is not None
        assert data["title"] == "Search Title"
        assert data["author"] == "Search Author"

    def test_lookup_uses_openlibrary_covers_for_cover_fallback(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "_fetch_openlibrary",
            lambda _isbn: {
                "isbn": "9780000000005",
                "title": "No Cover",
                "author": "Author",
                "description": "Desc",
                "publisher": "Pub",
                "year": "2024",
                "cover_url": None,
            },
        )
        monkeypatch.setattr(app_module, "_fetch_googlebooks", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_crossref", lambda _isbn: None)
        monkeypatch.setattr(app_module, "_fetch_openlibrary_search", lambda _isbn: None)
        monkeypatch.setattr(
            app_module,
            "_fetch_openlibrary_covers",
            lambda _isbn: {
                "isbn": "9780000000005",
                "cover_url": "https://covers.openlibrary.org/b/isbn/9780000000005-L.jpg?default=false",
            },
        )

        data = app_module.lookup_isbn("9780000000005")
        assert data is not None
        assert data["cover_url"].startswith("https://covers.openlibrary.org/b/isbn/")


class TestRecommendationsAndLocation:
    def test_book_location_fields_roundtrip(self, client):
        created = client.post(
            "/api/books",
            json={
                "isbn": "9789991234500",
                "status": "reading",
                "location_type": "loaned_to",
                "location_note": "Needs return next month",
                "loan_person": "Alex",
                "book_data": {"title": "Borrowed Book", "author": "A. Author", "genre": "Drama"},
            },
        )
        assert created.status_code == 201
        payload = created.get_json()
        assert payload["location_type"] == "loaned_to"
        assert payload["loan_person"] == "Alex"

        book_id = payload["id"]
        updated = client.patch(
            f"/api/books/{book_id}",
            json={"location_type": "ebook", "location_note": "Kindle", "loan_person": None},
        )
        assert updated.status_code == 200
        detail = client.get(f"/api/books/{book_id}").get_json()
        assert detail["location_type"] == "ebook"
        assert detail["location_note"] == "Kindle"

    def test_recommendations_returns_similar_books(self, client):
        first = client.post(
            "/api/books",
            json={
                "isbn": "9780000001111",
                "status": "read",
                "genre_tags": ["Fantasy", "Epic"],
                "book_data": {"title": "Book One", "author": "Author X", "genre": "Fantasy"},
            },
        ).get_json()
        client.post(
            "/api/books",
            json={
                "isbn": "9780000002222",
                "status": "read",
                "genre_tags": ["Fantasy"],
                "book_data": {"title": "Book Two", "author": "Author X", "genre": "Fantasy"},
            },
        )

        rec = client.get(f"/api/books/{first['id']}/recommendations")
        assert rec.status_code == 200
        items = rec.get_json()
        assert len(items) >= 1
        assert items[0]["title"] == "Book Two"


class TestAdminApis:
    def test_admin_endpoints_require_login(self, client):
        denied = client.get("/api/admin/diagnostics")
        assert denied.status_code == 403

    def test_admin_login_and_diagnostics(self, client):
        login = client.post("/api/admin/login", json={"password": "1111"})
        assert login.status_code == 200

        diagnostics = client.get("/api/admin/diagnostics")
        assert diagnostics.status_code == 200
        payload = diagnostics.get_json()
        assert payload["health"]["status"] == "ok"
        assert "storage" in payload

        logs = client.get("/api/admin/logs")
        assert logs.status_code == 200
