from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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


def _clean_year(value: Any) -> str | None:
    """Extract a four-digit publication year from a messy date string.

    Providers return years in many shapes ("1993?", "April 2021", "2011-05-01");
    this returns just the year so the UI shows "1993" rather than "1993?".
    """
    if not value:
        return None
    match = re.search(r"(1[5-9]\d{2}|20\d{2})", str(value))
    return match.group(1) if match else None


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


# Open Library's search API serves crowd-sourced community ratings (CC0) —
# a free, open alternative to Google Books for the stats comparison chart.
# Fields must be requested explicitly or ratings are omitted from the docs.
_OL_SEARCH_FIELDS = (
    "title,author_name,publisher,subject,cover_i,first_publish_year,ratings_average,ratings_count"
)


def _parse_openlibrary_doc(doc: dict, isbn: str | None) -> dict:
    authors = ", ".join(doc.get("author_name") or [])
    publishers = doc.get("publisher") or []
    subjects = normalize_tags(doc.get("subject") or [])[:3]
    cover_id = doc.get("cover_i")
    cover_url = (
        f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false" if cover_id else None
    )
    ratings_average = doc.get("ratings_average")
    ratings_count = doc.get("ratings_count")

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
        "community_rating": round(float(ratings_average), 2) if ratings_average else None,
        "community_rating_count": int(ratings_count) if ratings_count else None,
    }


def fetch_openlibrary_search(isbn: str) -> dict | None:
    url = f"https://openlibrary.org/search.json?isbn={isbn}&limit=1&fields={_OL_SEARCH_FIELDS}"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        docs = data.get("docs") or []
        if not docs:
            return None
        return _parse_openlibrary_doc(docs[0], isbn)
    except Exception as exc:
        log.warning("Open Library search lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_openlibrary_title_search(title: str, author: str | None = None) -> dict | None:
    """Look up a book on Open Library by title (and optionally author)."""
    params: dict[str, str] = {"title": title, "limit": "1", "fields": _OL_SEARCH_FIELDS}
    if author:
        params["author"] = author.split(",")[0].strip()
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        docs = data.get("docs") or []
        if not docs:
            return None
        return _parse_openlibrary_doc(docs[0], None)
    except Exception as exc:
        log.warning("Open Library title lookup failed for %r: %s", title, exc)
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


# Google Books has a very low unauthenticated quota: bulk jobs (repair, refresh,
# CSV import) trip HTTP 429 after a handful of back-to-back requests. Requests
# are therefore throttled to a minimum interval, and a 429 puts the provider on
# a cooldown during which calls return None immediately instead of hammering
# the API and spamming the log.
GOOGLE_BOOKS_API_KEY = os.getenv("PAGEVAULT_GOOGLE_BOOKS_API_KEY", "").strip()
GOOGLE_BOOKS_MIN_INTERVAL_SECONDS = max(
    0.0, float(os.getenv("PAGEVAULT_GOOGLE_BOOKS_MIN_INTERVAL_SECONDS", "0.6"))
)
GOOGLE_BOOKS_COOLDOWN_SECONDS = max(
    1.0, float(os.getenv("PAGEVAULT_GOOGLE_BOOKS_COOLDOWN_SECONDS", "120"))
)

_googlebooks_lock = threading.Lock()
_googlebooks_next_request_at = 0.0
_googlebooks_cooldown_until = 0.0


def reset_googlebooks_limiter() -> None:
    """Clear the Google Books throttle/cooldown state (used by tests)."""
    global _googlebooks_next_request_at, _googlebooks_cooldown_until
    with _googlebooks_lock:
        _googlebooks_next_request_at = 0.0
        _googlebooks_cooldown_until = 0.0


def _googlebooks_get(url: str) -> dict | None:
    """GET a Google Books API URL respecting the throttle and 429 cooldown.

    Returns the parsed JSON payload, or ``None`` when the provider is on
    cooldown or responds with HTTP 429 (which starts a new cooldown).
    Other errors propagate to the caller.
    """
    global _googlebooks_next_request_at, _googlebooks_cooldown_until
    if GOOGLE_BOOKS_API_KEY:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"key": GOOGLE_BOOKS_API_KEY})
    with _googlebooks_lock:
        if time.monotonic() < _googlebooks_cooldown_until:
            return None
        wait = _googlebooks_next_request_at - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _googlebooks_next_request_at = time.monotonic() + GOOGLE_BOOKS_MIN_INTERVAL_SECONDS
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return cast(dict[Any, Any], json.loads(resp.read()))
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise
        try:
            retry_after = float(exc.headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            retry_after = 0.0
        pause = max(GOOGLE_BOOKS_COOLDOWN_SECONDS, retry_after)
        with _googlebooks_lock:
            _googlebooks_cooldown_until = time.monotonic() + pause
        log.warning(
            "Google Books rate limit hit (HTTP 429) — pausing Google Books lookups "
            "for %.0f s. Set PAGEVAULT_GOOGLE_BOOKS_API_KEY for a higher quota.",
            pause,
        )
        return None


def _parse_googlebooks_items(items: list, isbn: str | None) -> dict | None:
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


def fetch_googlebooks(isbn: str) -> dict | None:
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        data = _googlebooks_get(url)
        if not data:
            return None
        return _parse_googlebooks_items(data.get("items") or [], isbn)
    except Exception as exc:
        log.warning("Google Books lookup failed for ISBN %s: %s", isbn, exc)
        return None


def fetch_googlebooks_title_author(title: str, author: str | None = None) -> dict | None:
    """Look up a book on Google Books by title (and optionally author).

    Used for books without a real ISBN (Goodreads `GR…` placeholder ids).
    """
    query = f'intitle:"{title}"'
    if author:
        # Goodreads lists co-authors comma-separated; the first is the primary.
        query += f' inauthor:"{author.split(",")[0].strip()}"'
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(
        {"q": query, "maxResults": 1}
    )
    try:
        data = _googlebooks_get(url)
        if not data:
            return None
        return _parse_googlebooks_items(data.get("items") or [], None)
    except Exception as exc:
        log.warning("Google Books title lookup failed for %r: %s", title, exc)
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


# Deutsche Nationalbibliothek (DNB): the German national library. Keyless and
# authoritative for German-language books, which Open Library frequently lacks and
# the keyless Google Books quota cannot always cover. The SRU service returns
# Dublin Core XML.
DNB_SRU_URL = "https://services.dnb.de/sru/dnb"
_DC_NS = "{http://purl.org/dc/elements/1.1/}"
# MARC/ISO-639-2 language codes DNB emits, mapped to PageVault's two-letter codes.
_MARC_LANG = {"ger": "de", "eng": "en", "fre": "fr", "spa": "es", "ita": "it", "dut": "nl"}


def is_german_isbn(isbn: str) -> bool:
    """True for ISBNs in the German-language group (prefix 978-3 or ISBN-10 '3')."""
    return isbn.startswith("9783") or (len(isbn) == 10 and isbn.startswith("3"))


def _clean_dnb_title(raw: str | None) -> str | None:
    """Normalise a DNB Dublin Core title.

    DNB titles carry library apparatus, e.g.
    "[Kehlmann] ; Lichtspiel : Roman / Daniel Kehlmann". Drop the leading sort
    prefix and the trailing "/ statement of responsibility".
    """
    if not raw:
        return None
    title = raw.strip()
    if title.startswith("["):
        semicolon = title.find(";")
        if semicolon != -1:
            title = title[semicolon + 1 :].strip()
    slash = title.find(" / ")
    if slash != -1:
        title = title[:slash].strip()
    return title.replace(" : ", ": ").strip() or None


def _clean_dnb_author(raw: str | None) -> str | None:
    """Normalise a DNB creator: "Kehlmann, Daniel [Verfasser]" -> "Daniel Kehlmann"."""
    if not raw:
        return None
    author = re.sub(r"\[[^\]]*\]", "", raw).strip(" ;,")
    if "," in author:
        last, _, first = author.partition(",")
        author = f"{first.strip()} {last.strip()}".strip()
    return author or None


def fetch_dnb(isbn: str) -> dict | None:
    """Look up book metadata in the Deutsche Nationalbibliothek by ISBN.

    Returns title/author/publisher/year/language/genre, or ``None`` when DNB has
    no record. DNB does not serve cover images, so covers come from other
    providers in the merge chain.
    """
    params = urllib.parse.urlencode(
        {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": f"ISBN={isbn}",
            "recordSchema": "oai_dc",
            "maximumRecords": "1",
        }
    )
    try:
        req = urllib.request.Request(f"{DNB_SRU_URL}?{params}", headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            root = ET.fromstring(resp.read())
    except (urllib.error.URLError, OSError, ET.ParseError) as exc:
        log.warning("DNB lookup failed for ISBN %s: %s", isbn, exc)
        return None

    titles = [e.text for e in root.iter(f"{_DC_NS}title") if e.text]
    title = _clean_dnb_title(titles[0]) if titles else None
    if not title:
        return None

    authors = [a for a in (_clean_dnb_author(e.text) for e in root.iter(f"{_DC_NS}creator")) if a]
    publishers = [e.text for e in root.iter(f"{_DC_NS}publisher") if e.text]
    dates = [e.text for e in root.iter(f"{_DC_NS}date") if e.text]
    languages = [e.text for e in root.iter(f"{_DC_NS}language") if e.text]
    subjects = [e.text for e in root.iter(f"{_DC_NS}subject") if e.text]

    # DNB subjects are often "830 Deutsche Literatur" (DDC number + label).
    genre_tags = normalize_tags([re.sub(r"^\d+\s*", "", s).strip() for s in subjects])[:3]
    publisher = publishers[0].split(":")[-1].strip() if publishers else None
    language = _MARC_LANG.get((languages[0] or "").strip().lower()) if languages else None

    return {
        "isbn": isbn,
        "title": title,
        "author": ", ".join(authors) or None,
        "publisher": publisher or None,
        "year": _clean_year(dates[0]) if dates else None,
        "language": language,
        "genre": genre_tags[0] if genre_tags else None,
        "genre_tags": genre_tags,
    }


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
        # Google Books exclusives — without these the community rating was
        # dropped whenever Open Library answered first.
        "community_rating",
        "community_rating_count",
        "series_name",
        "series_number",
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
    fetch_dnb_fn=fetch_dnb,
) -> dict | None:
    clean = isbn.strip().replace("-", "").replace(" ", "")
    if not clean:
        return None
    if clean.upper().startswith("GR"):
        # Synthetic Goodreads placeholder id, not a real ISBN — no provider
        # can resolve it. Callers should use lookup_title_author() instead.
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
        # The OL Books API never carries ratings; the search fallback does.
        or not openlibrary_data.get("community_rating")
    )
    if not needs_fallback:
        _set_cached_lookup(clean, openlibrary_data)
        return cast(dict[Any, Any], openlibrary_data)

    provider_jobs = {
        "googlebooks": fetch_googlebooks_fn,
        "openlibrary_search": fetch_openlibrary_search_fn,
        "crossref": fetch_crossref_fn,
    }
    # DNB is authoritative for German-language books that Open Library lacks; only
    # query it for German-group ISBNs to spare its servers on other lookups.
    if is_german_isbn(clean):
        provider_jobs["dnb"] = fetch_dnb_fn
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

    # DNB first so its authoritative bibliographic fields win for German books;
    # Google Books then fills cover, description, and ratings it does not carry.
    merged_data = openlibrary_data
    for provider_name in [
        "dnb",
        "googlebooks",
        "openlibrary_search",
        "crossref",
        "openlibrary_covers",
    ]:
        if provider_name in results:
            merged_data = merge_lookup_data(merged_data, results[provider_name])

    if merged_data and merged_data.get("year"):
        merged_data["year"] = _clean_year(merged_data["year"]) or merged_data["year"]

    _set_cached_lookup(clean, merged_data)
    return cast(dict[Any, Any], merged_data)


def lookup_title_author(
    title: str,
    author: str | None = None,
    fetch_openlibrary_title_fn=fetch_openlibrary_title_search,
    fetch_googlebooks_title_fn=fetch_googlebooks_title_author,
) -> dict | None:
    """Look up book metadata by title/author for books without a real ISBN.

    Goodreads exports leave the ISBN empty for many Kindle/Audible editions;
    those books are stored with a synthetic ``GR…`` identifier that no ISBN
    provider can resolve. This combines an Open Library title search with a
    Google Books title query (the only source of community ratings).
    """
    clean_title = (title or "").strip()
    if not clean_title:
        return None

    cache_key = f"title:{clean_title.casefold()}|author:{(author or '').strip().casefold()}"
    hit, cached = _get_cached_lookup(cache_key)
    if hit:
        return cached

    openlibrary_data = fetch_openlibrary_title_fn(clean_title, author)
    googlebooks_data = fetch_googlebooks_title_fn(clean_title, author)
    merged = merge_lookup_data(openlibrary_data, googlebooks_data)

    if merged and merged.get("year"):
        merged["year"] = _clean_year(merged["year"]) or merged["year"]

    _set_cached_lookup(cache_key, merged)
    return cast(dict[Any, Any], merged)
