"""
tests/conftest.py — Shared pytest fixtures for PageVault.
"""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    """
    Fresh application instance with an isolated temp database for each test.
    Ensures tests never share state.
    """
    test_app = create_app(
        {
            "DATABASE": str(tmp_path / "test.db"),
            "TESTING": True,
            "SECRET_KEY": "test-secret",
        }
    )
    yield test_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def sample_book_payload():
    """A valid POST /api/books payload with pre-filled book_data."""
    return {
        "isbn": "9780743273565",
        "book_data": {
            "isbn": "9780743273565",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "cover_url": None,
            "description": "A novel set in the Jazz Age.",
            "publisher": "Scribner",
            "year": "1925",
            "pages": 180,
            "genre": "Fiction",
        },
        "status": "read",
    }


@pytest.fixture()
def added_book(client, sample_book_payload):
    """Add a book to the library and return the response JSON."""
    r = client.post("/api/books", json=sample_book_payload)
    assert r.status_code == 201, f"Setup failed: {r.get_json()}"
    return r.get_json()


@pytest.fixture()
def book_with_reviews(client, added_book):
    """A book that already has two reviews attached."""
    book_id = added_book["id"]
    client.post(f"/api/books/{book_id}/reviews", json={"rating": 5, "comment": "Excellent"})
    client.post(f"/api/books/{book_id}/reviews", json={"rating": 3, "comment": "Decent"})
    return added_book
