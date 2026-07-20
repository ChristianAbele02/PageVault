"""Shared utility helpers for PageVault core.

Includes status/logo validation, tag normalization, Goodreads shelf mapping,
CSV value parsing, and ISBN normalization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


VALID_STATUSES = {"want_to_read", "reading", "read", "dnf"}


def validate_status(value: str | None) -> bool:
    if value is None:
        return False
    return value in VALID_STATUSES


def validate_logo_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_tags(value: object) -> list[str]:
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


def int_list(values: object) -> list[int]:
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


_MOJIBAKE_CODECS = ("cp1252", "latin-1")


def _try_repair(text: str) -> str | None:
    for codec in _MOJIBAKE_CODECS:
        try:
            return text.encode(codec, errors="strict").decode("utf-8", errors="strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return None


def repair_mojibake(text: str) -> str:
    """Repair UTF-8 text that was mis-decoded as cp1252/latin-1.

    Goodreads exports are UTF-8, but files that passed through Excel or a
    Windows editor are often double-encoded ("BrontÃ«" instead of "Brontë").
    Both cp1252 and latin-1 round-trips are attempted (latin-1 covers control
    characters like U+009F that "ß" produces). If the whole text cannot be
    repaired, lines are repaired individually so one lossy row does not stop
    the rescue of every other row. Unrepairable text is returned unchanged.
    """
    if "Ã" not in text and "â€" not in text:
        return text
    whole = _try_repair(text)
    if whole is not None:
        return whole

    changed = False
    repaired_lines: list[str] = []
    for line in text.split("\n"):
        if "Ã" in line or "â€" in line:
            fixed = _try_repair(line)
            if fixed is not None:
                repaired_lines.append(fixed)
                changed = True
                continue
        repaired_lines.append(line)
    return "\n".join(repaired_lines) if changed else text


def normalize_goodreads_date(value: str | None) -> str | None:
    """Normalize a Goodreads date ("2026/06/10") to ISO ("2026-06-10").

    Accepts both slash and dash separators; returns ``None`` for empty or
    unparseable values.
    """
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


_BINDING_FORMATS = {
    "kindle edition": "ebook",
    "ebook": "ebook",
    "nook": "ebook",
    "audible audio": "audiobook",
    "audiobook": "audiobook",
    "audio cd": "audiobook",
    "audio cassette": "audiobook",
}


def format_from_binding(value: str | None) -> str | None:
    """Map a Goodreads ``Binding`` value to a PageVault book format.

    Returns ``ebook``/``audiobook`` for digital bindings, ``physical`` for
    known print bindings, or ``None`` when the binding is empty/unknown.
    """
    binding = (value or "").strip().lower()
    if not binding:
        return None
    if binding in _BINDING_FORMATS:
        return _BINDING_FORMATS[binding]
    if any(word in binding for word in ("kindle", "ebook", "audio")):
        return "audiobook" if "audio" in binding else "ebook"
    return "physical"


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
