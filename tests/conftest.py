"""
Shared pytest fixtures for PageVault test suite.
"""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    """Fresh test app per test using an isolated SQLite file."""
    test_app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_book_payload():
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
    """Add a book and return the JSON response."""
    response = client.post("/api/books", json=sample_book_payload)
    assert response.status_code == 201
    return response.get_json()
