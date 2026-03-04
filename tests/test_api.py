"""
tests/test_api.py — PageVault API test suite
Run with: pytest -v
"""

from __future__ import annotations

import io

import app as app_module

# ── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_empty_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.get_json()
        assert data["total"] == 0
        assert data["read"] == 0

    def test_stats_after_add(self, client, sample_book_payload):
        client.post("/api/books", json=sample_book_payload)
        r = client.get("/api/stats")
        data = r.get_json()
        assert data["total"] == 1
        assert data["read"] == 1


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

    def test_add_review_invalid_rating(self, client, added_book):
        r = client.post(f"/api/books/{added_book['id']}/reviews", json={"rating": 6})
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
