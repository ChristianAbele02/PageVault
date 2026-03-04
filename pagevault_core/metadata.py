from __future__ import annotations

import json
import logging
import urllib.request

from .utils import normalize_tags

log = logging.getLogger(__name__)


UA = {"User-Agent": "PageVault/1.0 (github.com/ChristianAbele02/PageVault)"}


def fetch_openlibrary(isbn: str) -> dict | None:
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        book = data.get(f"ISBN:{isbn}")
        if not book:
            return None
        covers = book.get("cover", {})
        authors = ", ".join(a.get("name", "") for a in book.get("authors", []))
        publishers = book.get("publishers", [])
        subjects = book.get("subjects", [])
        genre_tags = normalize_tags([s.get("name", "") for s in subjects])[:3]
        genre = genre_tags[0] if genre_tags else None
        return {
            "isbn": isbn,
            "title": book.get("title", "Unknown Title"),
            "author": authors or None,
            "cover_url": (covers.get("large") or covers.get("medium") or covers.get("small")),
            "description": ((book.get("excerpts") or [{}])[0].get("text") or None),
            "publisher": publishers[0].get("name") if publishers else None,
            "year": book.get("publish_date") or None,
            "pages": book.get("number_of_pages"),
            "genre": genre,
            "genre_tags": genre_tags,
        }
    except Exception as exc:
        log.warning("Open Library lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_googlebooks(isbn: str) -> dict | None:
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        items = data.get("items") or []
        if not items:
            return None

        info = items[0].get("volumeInfo") or {}
        authors = ", ".join(info.get("authors") or [])
        categories = normalize_tags(info.get("categories") or [])[:3]
        image_links = info.get("imageLinks") or {}
        cover_url = (
            image_links.get("extraLarge")
            or image_links.get("large")
            or image_links.get("medium")
            or image_links.get("thumbnail")
            or image_links.get("smallThumbnail")
        )

        return {
            "isbn": isbn,
            "title": info.get("title") or None,
            "author": authors or None,
            "cover_url": cover_url,
            "description": info.get("description") or None,
            "publisher": info.get("publisher") or None,
            "year": info.get("publishedDate") or None,
            "pages": info.get("pageCount"),
            "genre": categories[0] if categories else None,
            "genre_tags": categories,
            "language": info.get("language") or None,
        }
    except Exception as exc:
        log.warning("Google Books lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_crossref(isbn: str) -> dict | None:
    url = f"https://api.crossref.org/works?filter=isbn:{isbn}&rows=1"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "PageVault/1.0 (mailto:pagevault@localhost)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        items = ((data.get("message") or {}).get("items")) or []
        if not items:
            return None

        item = items[0]
        authors_data = item.get("author") or []
        authors = ", ".join(
            " ".join(part for part in [a.get("given"), a.get("family")] if part).strip()
            for a in authors_data
        ).strip()

        published = item.get("published-print") or item.get("issued") or {}
        date_parts = published.get("date-parts") or []
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else None
        subjects = normalize_tags(item.get("subject") or [])[:3]

        title_data = item.get("title") or []
        subtitle_data = item.get("subtitle") or []
        title = title_data[0] if title_data else None
        if title and subtitle_data:
            title = f"{title}: {subtitle_data[0]}"

        return {
            "isbn": isbn,
            "title": title,
            "author": authors or None,
            "publisher": item.get("publisher") or None,
            "year": year,
            "genre": subjects[0] if subjects else None,
            "genre_tags": subjects,
        }
    except Exception as exc:
        log.warning("Crossref lookup failed for ISBN %s: %s", isbn, exc)
        return None


def merge_lookup_data(primary: dict | None, fallback: dict | None) -> dict | None:
    if not primary:
        return fallback
    if not fallback:
        return primary

    merged = dict(primary)
    fields = [
        "title",
        "author",
        "cover_url",
        "description",
        "publisher",
        "year",
        "pages",
        "genre",
        "language",
    ]
    for field in fields:
        if not merged.get(field) and fallback.get(field):
            merged[field] = fallback[field]

    merged_tags = normalize_tags(
        (primary.get("genre_tags") or []) + (fallback.get("genre_tags") or [])
    )
    merged["genre_tags"] = merged_tags[:3]
    if not merged.get("genre") and merged["genre_tags"]:
        merged["genre"] = merged["genre_tags"][0]
    return merged


def lookup_isbn(
    isbn: str,
    fetch_openlibrary_fn=fetch_openlibrary,
    fetch_googlebooks_fn=fetch_googlebooks,
    fetch_crossref_fn=fetch_crossref,
) -> dict | None:
    clean = isbn.strip().replace("-", "").replace(" ", "")
    if not clean:
        return None

    openlibrary_data = fetch_openlibrary_fn(clean)

    needs_fallback = (
        not openlibrary_data
        or not openlibrary_data.get("cover_url")
        or not openlibrary_data.get("description")
        or not openlibrary_data.get("author")
    )
    if not needs_fallback:
        return openlibrary_data

    googlebooks_data = fetch_googlebooks_fn(clean)
    merged_data = merge_lookup_data(openlibrary_data, googlebooks_data)

    needs_third_fallback = (
        not merged_data
        or not merged_data.get("title")
        or not merged_data.get("author")
        or not merged_data.get("publisher")
        or not merged_data.get("year")
    )
    if not needs_third_fallback:
        return merged_data

    crossref_data = fetch_crossref_fn(clean)
    return merge_lookup_data(merged_data, crossref_data)
