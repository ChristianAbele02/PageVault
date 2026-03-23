from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

from .utils import normalize_tags

log = logging.getLogger(__name__)

# Centralise the package version so User-Agent strings stay in sync (issue #17)
try:
    _VERSION = importlib.metadata.version("pagevault")
except importlib.metadata.PackageNotFoundError:
    _VERSION = "dev"

UA = {"User-Agent": f"PageVault/{_VERSION} (github.com/ChristianAbele02/PageVault)"}
_CROSSREF_UA = {"User-Agent": f"PageVault/{_VERSION} (mailto:pagevault@localhost)"}

LOOKUP_CACHE_TTL_SECONDS = max(0, int(os.getenv("PAGEVAULT_LOOKUP_CACHE_TTL_SECONDS", "900")))
LOOKUP_CACHE_MAX_ITEMS = max(1, int(os.getenv("PAGEVAULT_LOOKUP_CACHE_MAX_ITEMS", "2000")))

_LOOKUP_CACHE: OrderedDict[str, tuple[float, dict | None]] = OrderedDict()
_LOOKUP_CACHE_LOCK = threading.RLock()


def clear_lookup_cache() -> None:
    with _LOOKUP_CACHE_LOCK:
        _LOOKUP_CACHE.clear()


def _get_cached_lookup(isbn: str) -> tuple[bool, dict | None]:
    if LOOKUP_CACHE_TTL_SECONDS <= 0:
        return False, None
    now = time.monotonic()
    with _LOOKUP_CACHE_LOCK:
        entry = _LOOKUP_CACHE.get(isbn)
        if not entry:
            return False, None
        expires_at, cached_value = entry
        if expires_at <= now:
            _LOOKUP_CACHE.pop(isbn, None)
            return False, None
        _LOOKUP_CACHE.move_to_end(isbn)
        return True, (dict(cached_value) if isinstance(cached_value, dict) else None)


def _set_cached_lookup(isbn: str, value: dict | None) -> None:
    if LOOKUP_CACHE_TTL_SECONDS <= 0:
        return
    expires_at = time.monotonic() + LOOKUP_CACHE_TTL_SECONDS
    cached_value = dict(value) if isinstance(value, dict) else None
    with _LOOKUP_CACHE_LOCK:
        _LOOKUP_CACHE[isbn] = (expires_at, cached_value)
        _LOOKUP_CACHE.move_to_end(isbn)
        while len(_LOOKUP_CACHE) > LOOKUP_CACHE_MAX_ITEMS:
            _LOOKUP_CACHE.popitem(last=False)


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


def fetch_openlibrary_search(isbn: str) -> dict | None:
    url = f"https://openlibrary.org/search.json?isbn={isbn}&limit=1"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        docs = data.get("docs") or []
        if not docs:
            return None

        doc = docs[0]
        authors = ", ".join(doc.get("author_name") or [])
        publishers = doc.get("publisher") or []
        subjects = normalize_tags(doc.get("subject") or [])[:3]
        cover_id = doc.get("cover_i")
        cover_url = (
            f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false"
            if cover_id
            else None
        )

        return {
            "isbn": isbn,
            "title": doc.get("title") or None,
            "author": authors or None,
            "cover_url": cover_url,
            "publisher": publishers[0] if publishers else None,
            "year": str(doc.get("first_publish_year")) if doc.get("first_publish_year") else None,
            "genre": subjects[0] if subjects else None,
            "genre_tags": subjects,
            "language": None,
        }
    except Exception as exc:
        log.warning("Open Library search lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_openlibrary_covers(isbn: str) -> dict | None:
    cover_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
    try:
        req = urllib.request.Request(cover_url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=5):
            pass
        return {"isbn": isbn, "cover_url": cover_url}
    except (
        urllib.error.URLError,
        OSError,
    ):  # specific exceptions instead of bare except (issue #6)
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

        avg_rating = info.get("averageRating")
        ratings_count = info.get("ratingsCount")
        series_info = info.get("seriesInfo") or {}
        series_name = series_info.get("shortSeriesBookTitle") or None
        series_number = None
        if series_info.get("bookDisplayNumber"):
            series_number = str(series_info["bookDisplayNumber"])

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
            "community_rating": float(avg_rating) if avg_rating is not None else None,
            "community_rating_count": int(ratings_count) if ratings_count is not None else None,
            "series_name": series_name,
            "series_number": series_number,
        }
    except Exception as exc:
        log.warning("Google Books lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_crossref(isbn: str) -> dict | None:
    url = f"https://api.crossref.org/works?filter=isbn:{isbn}&rows=1"
    try:
        req = urllib.request.Request(url, headers=_CROSSREF_UA)
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
    fetch_openlibrary_search_fn=fetch_openlibrary_search,
    fetch_openlibrary_covers_fn=fetch_openlibrary_covers,
) -> dict | None:
    clean = isbn.strip().replace("-", "").replace(" ", "")
    if not clean:
        return None

    hit, cached = _get_cached_lookup(clean)
    if hit:
        return cached

    openlibrary_data = fetch_openlibrary_fn(clean)

    needs_fallback = (
        not openlibrary_data
        or not openlibrary_data.get("cover_url")
        or not openlibrary_data.get("description")
        or not openlibrary_data.get("author")
        or not openlibrary_data.get("publisher")
        or not openlibrary_data.get("year")
    )
    if not needs_fallback:
        _set_cached_lookup(clean, openlibrary_data)
        return cast(dict[Any, Any], openlibrary_data)

    provider_jobs = {
        "googlebooks": fetch_googlebooks_fn,
        "openlibrary_search": fetch_openlibrary_search_fn,
        "crossref": fetch_crossref_fn,
    }
    if not openlibrary_data or not openlibrary_data.get("cover_url"):
        provider_jobs["openlibrary_covers"] = fetch_openlibrary_covers_fn

    results: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=len(provider_jobs)) as executor:
        future_map = {
            executor.submit(provider_fn, clean): provider_name
            for provider_name, provider_fn in provider_jobs.items()
        }
        for future in as_completed(future_map):
            provider_name = future_map[future]
            try:
                results[provider_name] = future.result()
            except Exception as exc:
                log.warning("%s fallback failed for ISBN %s: %s", provider_name, clean, exc)
                results[provider_name] = None

    merged_data = openlibrary_data
    for provider_name in ["googlebooks", "openlibrary_search", "crossref", "openlibrary_covers"]:
        if provider_name in results:
            merged_data = merge_lookup_data(merged_data, results[provider_name])

    _set_cached_lookup(clean, merged_data)
    return cast(dict[Any, Any], merged_data)
