"""
Tests for normalizers.py — normalize_ref() and parse_amount().

These are pure function tests; no database needed.
"""
from decimal import Decimal
import pytest

from reconcile.normalizers import normalize_ref, parse_amount


# ---------------------------------------------------------------------------
# normalize_ref
# ---------------------------------------------------------------------------

class TestNormalizeRef:
    def test_already_canonical(self):
        assert normalize_ref("REC-1034") == "REC-1034"

    def test_lowercase_no_separator(self):
        # Test case from actual data: rec1034
        assert normalize_ref("rec1034") == "REC-1034"

    def test_spaces_around_separator(self):
        # Test case from actual data: ' REC - 1070 '
        assert normalize_ref(" REC - 1070 ") == "REC-1070"

    def test_bare_number(self):
        # Test case from actual data: '1112'
        assert normalize_ref("1112") == "REC-1112"

    def test_empty_string(self):
        assert normalize_ref("") is None

    def test_none_input(self):
        assert normalize_ref(None) is None

    def test_whitespace_only(self):
        assert normalize_ref("   ") is None

    def test_truly_invalid(self):
        assert normalize_ref("GARBAGE_XYZ") is None

    def test_already_has_prefix(self):
        assert normalize_ref("REC-1001") == "REC-1001"

    def test_rec_uppercase_no_dash(self):
        assert normalize_ref("REC1070") == "REC-1070"


# ---------------------------------------------------------------------------
# parse_amount
# ---------------------------------------------------------------------------

class TestParseAmount:
    def test_normal_decimal(self):
        assert parse_amount("88969.92") == Decimal("88969.92")

    def test_indian_grouping_commas(self):
        # Test case from actual data: '1,25,400.00'
        assert parse_amount("1,25,400.00") == Decimal("125400.00")

    def test_standard_grouping_comma(self):
        assert parse_amount("125,400.00") == Decimal("125400.00")

    def test_empty_string_is_none(self):
        assert parse_amount("") is None

    def test_none_input_is_none(self):
        assert parse_amount(None) is None

    def test_whitespace_only_is_none(self):
        assert parse_amount("   ") is None

    def test_invalid_string_is_none(self):
        assert parse_amount("not_a_number") is None

    def test_never_returns_zero_for_blank(self):
        # Critical requirement: blank != 0
        result = parse_amount("")
        assert result is None
        assert result != Decimal("0")

    def test_never_returns_zero_for_invalid(self):
        result = parse_amount("abc")
        assert result is None
        assert result != Decimal("0")

    def test_integer_string(self):
        assert parse_amount("12345") == Decimal("12345")

    def test_zero_is_valid(self):
        # Zero IS a valid amount when explicitly written
        assert parse_amount("0.00") == Decimal("0.00")
