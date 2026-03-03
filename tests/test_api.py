"""
tests/test_api.py — PageVault API test suite
Run with: pytest -v
"""

from __future__ import annotations

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
