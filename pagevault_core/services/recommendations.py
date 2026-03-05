from __future__ import annotations

import sqlite3
from typing import Any


def _genre_set(book: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    if book.get("genre"):
        values.add(str(book["genre"]).strip().lower())
    for tag in book.get("genre_tags") or []:
        values.add(str(tag).strip().lower())
    return {value for value in values if value}


def recommend_books(db: sqlite3.Connection, book_id: int, limit: int = 6) -> list[dict[str, Any]]:
    base_row = db.execute(
        """SELECT b.*,
                  COALESCE(rs.avg_rating, 0) AS avg_rating,
                  COALESCE(rs.review_count, 0) AS review_count
           FROM books b
           LEFT JOIN (
                SELECT book_id, ROUND(AVG(rating), 2) AS avg_rating, COUNT(id) AS review_count
                FROM reviews
                GROUP BY book_id
           ) rs ON rs.book_id = b.id
           WHERE b.id = ?""",
        (book_id,),
    ).fetchone()
    if not base_row:
        return []

    base = dict(base_row)
    base_tags = {
        row["name"].strip().lower()
        for row in db.execute(
            """SELECT t.name
               FROM tags t
               JOIN book_tags bt ON bt.tag_id = t.id
               WHERE bt.book_id = ?""",
            (book_id,),
        ).fetchall()
    }
    base["genre_tags"] = sorted(base_tags)
    base_genres = _genre_set(base)
    base_author = (base.get("author") or "").strip().lower()

    candidates = db.execute(
        """SELECT b.*,
                  COALESCE(rs.avg_rating, 0) AS avg_rating,
                  COALESCE(rs.review_count, 0) AS review_count
           FROM books b
           LEFT JOIN (
                SELECT book_id, ROUND(AVG(rating), 2) AS avg_rating, COUNT(id) AS review_count
                FROM reviews
                GROUP BY book_id
           ) rs ON rs.book_id = b.id
           WHERE b.id != ?""",
        (book_id,),
    ).fetchall()

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in candidates:
        candidate = dict(row)
        tag_rows = db.execute(
            """SELECT t.name
               FROM tags t
               JOIN book_tags bt ON bt.tag_id = t.id
               WHERE bt.book_id = ?""",
            (candidate["id"],),
        ).fetchall()
        candidate_tags = {tag["name"].strip().lower() for tag in tag_rows if tag["name"]}
        candidate["genre_tags"] = sorted(candidate_tags)
        candidate_genres = _genre_set(candidate)
        candidate_author = (candidate.get("author") or "").strip().lower()

        shared_genres = len(base_genres & candidate_genres)
        shared_tags = len(base_tags & candidate_tags)
        author_match = (
            1 if base_author and candidate_author and base_author == candidate_author else 0
        )

        score = (shared_genres * 3.0) + (shared_tags * 2.0) + (author_match * 4.0)
        score += min(float(candidate.get("avg_rating") or 0.0), 5.0) / 5.0

        if score <= 0:
            continue

        candidate["score"] = round(score, 3)
        candidate["shared_genres"] = sorted(base_genres & candidate_genres)
        candidate["shared_tags"] = sorted(base_tags & candidate_tags)
        candidate["author_match"] = bool(author_match)
        scored.append((score, candidate))

    scored.sort(
        key=lambda item: (item[0], item[1].get("review_count", 0), item[1].get("title", "")),
        reverse=True,
    )
    return [item[1] for item in scored[: max(1, min(limit, 20))]]
