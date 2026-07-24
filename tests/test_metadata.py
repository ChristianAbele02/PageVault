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


_LOC_SAMPLE = """<?xml version="1.0"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
  <zs:numberOfRecords>1</zs:numberOfRecords>
  <zs:records><zs:record><zs:recordData>
    <srw_dc:dc xmlns:srw_dc="info:srw/schema/1/dc-schema">
      <title xmlns="http://purl.org/dc/elements/1.1/">Lord of scoundrels : a novel / Loretta Chase.</title>
      <identifier xmlns="http://purl.org/dc/elements/1.1/">URN:ISBN:9780380779338</identifier>
      <identifier xmlns="http://purl.org/dc/elements/1.1/">URN:ISBN:0380779331</identifier>
      <creator xmlns="http://purl.org/dc/elements/1.1/">Chase, Loretta</creator>
      <type xmlns="http://purl.org/dc/elements/1.1/">text</type>
      <type xmlns="http://purl.org/dc/elements/1.1/">Love stories. gsafd</type>
      <type xmlns="http://purl.org/dc/elements/1.1/">Fiction. lcgft https://id.loc.gov/x</type>
      <language xmlns="http://purl.org/dc/elements/1.1/">eng</language>
      <subject xmlns="http://purl.org/dc/elements/1.1/">Man-woman relationships--Fiction.</subject>
    </srw_dc:dc>
  </zs:recordData></zs:record></zs:records>
</zs:searchRetrieveResponse>"""


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


class TestLocCleaning:
    def test_title_strips_responsibility_and_separator(self):
        assert metadata._clean_loc_title("Lord of scoundrels : a novel / Loretta Chase.") == (
            "Lord of scoundrels: a novel"
        )

    def test_title_strips_bare_trailing_slash(self):
        assert metadata._clean_loc_title("Heart fortune /") == "Heart fortune"

    def test_genres_drop_medium_and_source_codes(self):
        genres = metadata._clean_loc_genres(
            ["text", "Love stories. gsafd", "Fiction. lcgft https://id.loc.gov/x"],
            ["Man-woman relationships--Fiction."],
        )
        assert "Love stories" in genres
        assert "Man-woman relationships" in genres
        assert "text" not in genres and "Fiction" not in genres


class TestLocFetch:
    def test_parses_dublin_core(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=8: _FakeResp(_LOC_SAMPLE.encode("utf-8"))
        )
        result = metadata.fetch_loc("9780380779338")
        assert result is not None
        assert result["title"] == "Lord of scoundrels: a novel"
        assert result["author"] == "Loretta Chase"
        assert result["language"] == "en"
        assert result["genre_tags"][0] == "Love stories"

    def test_empty_response_returns_none(self, monkeypatch):
        empty = '<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/"><zs:records/></zs:searchRetrieveResponse>'
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=8: _FakeResp(empty.encode("utf-8"))
        )
        assert metadata.fetch_loc("9780000000000") is None

    def test_rejects_record_whose_isbn_does_not_match(self, monkeypatch):
        """A non-exact SRU match returning a different book is discarded."""
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=8: _FakeResp(_LOC_SAMPLE.encode("utf-8"))
        )
        # The sample record is ISBN 9780380779338; a different query must not
        # adopt it.
        assert metadata.fetch_loc("9781111111111") is None

    def test_matches_isbn10_form_of_isbn13_query(self):
        """The query's ISBN-13 matches a record that lists the ISBN-10 form."""
        assert metadata._isbn_core("9780380779338") == metadata._isbn_core("0380779331")


class TestLookupPipeline:
    _STUBS = {
        "fetch_crossref_fn": lambda _i: None,
        "fetch_openlibrary_search_fn": lambda _i: None,
        "fetch_openlibrary_covers_fn": lambda _i: None,
        "fetch_dnb_fn": lambda _i: None,
        "fetch_loc_fn": lambda _i: None,
    }

    def test_all_providers_run_even_when_openlibrary_complete(self):
        """No early exit: Google Books is still queried when OL already answered."""
        metadata.clear_lookup_cache()
        gb_called: list[str] = []
        complete = {
            "isbn": "9780000000009", "title": "T", "author": "A", "cover_url": "c",
            "description": "d", "publisher": "p", "year": "2020", "community_rating": 4.0,
        }
        stubs = {**self._STUBS, "fetch_googlebooks_fn": lambda i: gb_called.append(i)}
        metadata.lookup_isbn("9780000000009", fetch_openlibrary_fn=lambda i: dict(complete, isbn=i), **stubs)
        assert gb_called == ["9780000000009"]

    def test_later_provider_enriches_present_field(self):
        """A later provider overrides an enrichable field (e.g. a better cover)."""
        metadata.clear_lookup_cache()
        stubs = {
            **self._STUBS,
            "fetch_googlebooks_fn": lambda i: {
                "isbn": i, "cover_url": "http://google/large.jpg",
                "description": "a much fuller description",
            },
        }
        r = metadata.lookup_isbn(
            "9780000000010",
            fetch_openlibrary_fn=lambda i: {
                "isbn": i, "title": "T", "author": "A",
                "cover_url": "http://ol/small.jpg", "description": "short",
            },
            **stubs,
        )
        assert r is not None
        assert r["cover_url"] == "http://google/large.jpg"
        assert r["description"] == "a much fuller description"
        assert r["title"] == "T"  # title is protected from override

    def test_title_protected_from_non_authoritative_override(self):
        """LoC (sentence-cased) must not overwrite a good Open Library title,
        but its genre still enriches the record."""
        metadata.clear_lookup_cache()
        stubs = {
            **self._STUBS,
            "fetch_googlebooks_fn": lambda _i: None,
            "fetch_loc_fn": lambda i: {
                "isbn": i, "title": "it ends with us", "author": "Hoover, Colleen",
                "genre_tags": ["Love stories"],
            },
        }
        r = metadata.lookup_isbn(
            "9780000000011",
            fetch_openlibrary_fn=lambda i: {"isbn": i, "title": "It Ends With Us", "author": "Colleen Hoover"},
            **stubs,
        )
        assert r is not None
        assert r["title"] == "It Ends With Us"
        assert r["author"] == "Colleen Hoover"
        assert "Love stories" in r["genre_tags"]

    def test_unresolved_isbn_returns_none(self):
        metadata.clear_lookup_cache()
        r = metadata.lookup_isbn(
            "9780000000012",
            fetch_openlibrary_fn=lambda _i: None,
            fetch_googlebooks_fn=lambda _i: None,
            **self._STUBS,
        )
        assert r is None


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
            fetch_loc_fn=lambda _i: None,
        )
        assert called == ["9783498003876"]
        assert result is not None
        assert result["title"] == "Lichtspiel"

    def test_german_dnb_overrides_open_library(self):
        """DNB is authoritative for German books: its title wins over Open Library."""
        metadata.clear_lookup_cache()
        result = metadata.lookup_isbn(
            "9783498003876",
            # A complete but mis-cased Open Library record.
            fetch_openlibrary_fn=lambda i: {
                "isbn": i,
                "title": "lichtspiel",
                "author": "D. Kehlmann",
                "cover_url": "http://x/c.jpg",
                "description": "desc",
                "publisher": "Rowohlt",
                "year": "2023",
                "community_rating": 4.1,
            },
            fetch_googlebooks_fn=lambda _i: None,
            fetch_crossref_fn=lambda _i: None,
            fetch_openlibrary_search_fn=lambda _i: None,
            fetch_openlibrary_covers_fn=lambda _i: None,
            fetch_dnb_fn=lambda i: {"isbn": i, "title": "Lichtspiel: Roman", "author": "Daniel Kehlmann"},
            fetch_loc_fn=lambda _i: None,
        )
        assert result is not None
        assert result["title"] == "Lichtspiel: Roman"
        assert result["author"] == "Daniel Kehlmann"
        # Fields DNB does not carry still come from Open Library.
        assert result["cover_url"] == "http://x/c.jpg"

    def test_non_german_isbn_skips_dnb_and_queries_loc(self):
        metadata.clear_lookup_cache()
        dnb_called: list[str] = []
        loc_called: list[str] = []

        result = metadata.lookup_isbn(
            "9780451524935",
            fetch_openlibrary_fn=lambda _i: None,
            fetch_googlebooks_fn=lambda _i: None,
            fetch_crossref_fn=lambda _i: None,
            fetch_openlibrary_search_fn=lambda _i: None,
            fetch_openlibrary_covers_fn=lambda _i: None,
            fetch_dnb_fn=lambda i: dnb_called.append(i),
            fetch_loc_fn=lambda i: (loc_called.append(i), {"isbn": i, "title": "1984"})[1],
        )
        assert dnb_called == []
        assert loc_called == ["9780451524935"]
        assert result is not None and result["title"] == "1984"

    def test_is_german_isbn(self):
        assert metadata.is_german_isbn("9783498003876")
        assert metadata.is_german_isbn("3499267829")
        assert not metadata.is_german_isbn("9780451524935")

    def test_is_english_isbn(self):
        assert metadata.is_english_isbn("9780451524935")
        assert metadata.is_english_isbn("9781234567897")
        assert metadata.is_english_isbn("0451524935")  # ISBN-10, English group
        assert not metadata.is_english_isbn("9783498003876")
        # 979-8 (Amazon KDP self-publishing range) is deliberately excluded.
        assert not metadata.is_english_isbn("9798000000000")
