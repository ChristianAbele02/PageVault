"""Tests for the metadata provider chain: DNB, year cleaning, and routing."""

from __future__ import annotations

import pytest

from pagevault_core import metadata

_DNB_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records><record><recordData>
    <dc xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>[Kehlmann] ; Lichtspiel : Roman / Daniel Kehlmann</dc:title>
      <dc:creator>Kehlmann, Daniel [Verfasser]</dc:creator>
      <dc:publisher>Hamburg : Rowohlt</dc:publisher>
      <dc:date>2023</dc:date>
      <dc:language>ger</dc:language>
      <dc:subject>830 Deutsche Literatur</dc:subject>
    </dc>
  </recordData></record></records>
</searchRetrieveResponse>"""


class _FakeResp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class TestYearCleaning:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1993?", "1993"),
            ("April 2021", "2021"),
            ("2011-05-01", "2011"),
            ("c2008", "2008"),
            ("", None),
            ("forthcoming", None),
            (None, None),
        ],
    )
    def test_clean_year(self, raw, expected):
        assert metadata._clean_year(raw) == expected


class TestDnbCleaning:
    def test_title_strips_sort_prefix_and_responsibility(self):
        raw = "[Kehlmann] ; Lichtspiel : Roman / Daniel Kehlmann"
        assert metadata._clean_dnb_title(raw) == "Lichtspiel: Roman"

    def test_title_passthrough(self):
        assert metadata._clean_dnb_title("Harry Potter und der Stein der Weisen") == (
            "Harry Potter und der Stein der Weisen"
        )

    def test_author_reorders_and_strips_role(self):
        assert metadata._clean_dnb_author("Kehlmann, Daniel [Verfasser]") == "Daniel Kehlmann"


class TestDnbFetch:
    def test_parses_dublin_core(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=8: _FakeResp(_DNB_SAMPLE.encode("utf-8"))
        )
        result = metadata.fetch_dnb("9783498003876")
        assert result is not None
        assert result["title"] == "Lichtspiel: Roman"
        assert result["author"] == "Daniel Kehlmann"
        assert result["publisher"] == "Rowohlt"
        assert result["year"] == "2023"
        assert result["language"] == "de"
        assert result["genre_tags"] == ["Deutsche Literatur"]

    def test_empty_response_returns_none(self, monkeypatch):
        empty = '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><records/></searchRetrieveResponse>'
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=8: _FakeResp(empty.encode("utf-8"))
        )
        assert metadata.fetch_dnb("9780000000000") is None


class TestDnbRouting:
    def test_german_isbn_queries_dnb(self):
        metadata.clear_lookup_cache()
        called = []

        def dnb(isbn):
            called.append(isbn)
            return {"isbn": isbn, "title": "Lichtspiel", "author": "Daniel Kehlmann"}

        result = metadata.lookup_isbn(
            "9783498003876",
            fetch_openlibrary_fn=lambda _i: None,
            fetch_googlebooks_fn=lambda _i: None,
            fetch_crossref_fn=lambda _i: None,
            fetch_openlibrary_search_fn=lambda _i: None,
            fetch_openlibrary_covers_fn=lambda _i: None,
            fetch_dnb_fn=dnb,
        )
        assert called == ["9783498003876"]
        assert result is not None
        assert result["title"] == "Lichtspiel"

    def test_non_german_isbn_skips_dnb(self):
        metadata.clear_lookup_cache()
        called = []

        metadata.lookup_isbn(
            "9780451524935",
            fetch_openlibrary_fn=lambda _i: None,
            fetch_googlebooks_fn=lambda _i: None,
            fetch_crossref_fn=lambda _i: None,
            fetch_openlibrary_search_fn=lambda _i: None,
            fetch_openlibrary_covers_fn=lambda _i: None,
            fetch_dnb_fn=lambda i: called.append(i),
        )
        assert called == []

    def test_is_german_isbn(self):
        assert metadata.is_german_isbn("9783498003876")
        assert metadata.is_german_isbn("3499267829")
        assert not metadata.is_german_isbn("9780451524935")
