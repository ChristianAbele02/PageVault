"""Tests for shared ISBN utilities (validation and core comparison)."""

from __future__ import annotations

import pytest

from pagevault_core.utils import is_valid_isbn, isbn_core


class TestIsValidIsbn:
    @pytest.mark.parametrize(
        "isbn",
        [
            "9780451524935",  # 1984 (ISBN-13)
            "978-0-451-52493-5",  # hyphenated form of the same
            "9783498003876",  # Lichtspiel (German ISBN-13)
            "0380779331",  # ISBN-10
            "080442957X",  # ISBN-10 ending in the X check digit
        ],
    )
    def test_accepts_valid_isbns(self, isbn):
        assert is_valid_isbn(isbn) is True

    @pytest.mark.parametrize(
        "value",
        [
            "9780451524936",  # 1984 ISBN with a wrong check digit
            "9790451524935",  # 979 prefix but wrong check digit
            "1234567890",  # ISBN-10 with an invalid check digit
            "4006381333931",  # an EAN-13 barcode, but not a book (non-978/979 prefix)
            "12345",  # too short (e.g. an EAN-5 price add-on)
            "",
            None,
        ],
    )
    def test_rejects_invalid_or_non_book_codes(self, value):
        assert is_valid_isbn(value) is False

    def test_x_only_valid_as_final_check_digit(self):
        # An X anywhere but the check position is not a valid ISBN-10.
        assert is_valid_isbn("X804429570") is False


class TestIsbnCore:
    def test_isbn10_and_isbn13_forms_share_a_core(self):
        assert isbn_core("9780380779338") == isbn_core("0380779331")

    def test_different_books_have_different_cores(self):
        assert isbn_core("9780451524935") != isbn_core("9783498003876")

    def test_empty_input_yields_empty_core(self):
        assert isbn_core(None) == ""
        assert isbn_core("") == ""
