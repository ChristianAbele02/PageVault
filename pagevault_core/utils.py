"""Shared utility helpers for PageVault core.

Includes status/logo validation, tag normalization, Goodreads shelf mapping,
CSV value parsing, and ISBN normalization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_status(value: str | None) -> bool:
    if value is None:
        return False
    return value in {"want_to_read", "reading", "read"}


def validate_logo_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        source = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        source = [str(part).strip() for part in value]
    else:
        return []
    seen = set()
    result = []
    for item in source:
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def int_list(values) -> list[int]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def normalize_isbn(value: str | None) -> str:
    if not value:
        return ""
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch.upper() == "X")
    return cleaned.upper()


def split_multi_value(value: str | None) -> list[str]:
    if not value:
        return []
    raw = str(value).replace("|", ",")
    return normalize_tags([part.strip() for part in raw.split(",") if part.strip()])


def status_from_goodreads(value: str | None) -> str:
    shelf = (value or "").strip().lower()
    mapping = {
        "read": "read",
        "currently-reading": "reading",
        "currently reading": "reading",
        "reading": "reading",
        "to-read": "want_to_read",
        "to read": "want_to_read",
        "want-to-read": "want_to_read",
        "want to read": "want_to_read",
    }
    return mapping.get(shelf, "want_to_read")
