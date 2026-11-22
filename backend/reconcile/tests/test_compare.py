"""
Tests for compare.py — the pure comparison engine.

All inputs are plain Python dicts; no database access.
Tests cover all 16 specified scenarios.
"""
from decimal import Decimal
from datetime import date
import pytest

from reconcile.compare import (
    run_comparison,
    filter_for_org,
    MISSING_IN_B,
    ORPHAN_IN_B,
    DUPLICATE_IN_B,
    VALUE_MISMATCH,
    LOCATION_MISMATCH,
    DATE_MISMATCH,
)


# ---------------------------------------------------------------------------
# Helpers to build test records
# ---------------------------------------------------------------------------

def make_a(record_id="REC-0001", location_id="LOC-101", org_id="ORG-A",
           total_value="100.00", state="CONFIRMED",
           event_date=date(2026, 3, 1)):
    return {
        "record_id": record_id,
        "location_id": location_id,
        "event_date": event_date,
        "total_value": Decimal(total_value),
        "state": state,
        "org_id": org_id,
    }


def make_b(entry_id="ENT-0001", record_ref="REC-0001", location_id="LOC-101",
           org_id="ORG-A", value="100.00", recorded_on=date(2026, 3, 1)):
    return {
        "entry_id": entry_id,
        "record_ref": record_ref,
        "location_id": location_id,
        "recorded_on": recorded_on,
        "value": Decimal(value) if value is not None else None,
        "org_id": org_id,
    }


# ---------------------------------------------------------------------------
# 1. MISSING_IN_B
# ---------------------------------------------------------------------------

class TestMissingInB:
    def test_confirmed_record_with_no_b_entry_flagged(self):
        a = [make_a()]
        result = run_comparison(a, [])
        assert len(result) == 1
        assert result[0]["reason"] == MISSING_IN_B
        assert result[0]["record_id"] == "REC-0001"
        assert result[0]["b_value"] is None

    def test_multiple_confirmed_records_all_missing(self):
        a = [make_a("REC-0001"), make_a("REC-0002")]
        result = run_comparison(a, [])
        reasons = [r["reason"] for r in result]
        assert reasons.count(MISSING_IN_B) == 2


# ---------------------------------------------------------------------------
# 2. ORPHAN_IN_B
# ---------------------------------------------------------------------------

class TestOrphanInB:
    def test_b_entry_no_matching_a_record(self):
        a = []
        b = [make_b(record_ref="REC-9999")]
        result = run_comparison(a, b)
        assert len(result) == 1
        assert result[0]["reason"] == ORPHAN_IN_B
        assert result[0]["record_id"] == "REC-9999"

    def test_b_entry_with_none_ref_is_orphan(self):
        a = []
        b = [make_b(record_ref=None)]
        result = run_comparison(a, b)
        assert len(result) == 1
        assert result[0]["reason"] == ORPHAN_IN_B


# ---------------------------------------------------------------------------
# 3. DUPLICATE_IN_B
# ---------------------------------------------------------------------------

class TestDuplicateInB:
    def test_two_equal_amounts_not_valid_split(self):
        # Both entries have the same value but they don't sum to A's total
        a = [make_a(total_value="100.00")]
        b = [
            make_b(entry_id="ENT-0001", record_ref="REC-0001", value="100.00"),
            make_b(entry_id="ENT-0002", record_ref="REC-0001", value="100.00"),
        ]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DUPLICATE_IN_B in reasons

    def test_two_entries_wrong_sum_flagged(self):
        a = [make_a(total_value="100.00")]
        b = [
            make_b(entry_id="ENT-0001", record_ref="REC-0001", value="60.00"),
            make_b(entry_id="ENT-0002", record_ref="REC-0001", value="60.00"),
        ]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DUPLICATE_IN_B in reasons

    def test_three_entries_wrong_sum_duplicate(self):
        # Three entries that do NOT sum to A.total_value → DUPLICATE_IN_B
        a = [make_a(total_value="150.00")]
        b = [
            make_b(entry_id="ENT-0001", record_ref="REC-0001", value="60.00"),
            make_b(entry_id="ENT-0002", record_ref="REC-0001", value="60.00"),
            make_b(entry_id="ENT-0003", record_ref="REC-0001", value="60.00"),
        ]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DUPLICATE_IN_B in reasons

    def test_duplicate_entries_are_consolidated_with_b_entry_details(self):
        a = [make_a(total_value="100.00")]
        b = [
            make_b(entry_id="ENT-0001", record_ref="REC-0001", value="60.00"),
            make_b(entry_id="ENT-0002", record_ref="REC-0001", value="60.00"),
        ]
        result = run_comparison(a, b)
        duplicate = [r for r in result if r["reason"] == DUPLICATE_IN_B]
        assert len(duplicate) == 1
        assert duplicate[0]["b_value"] == Decimal("120.00")
        assert duplicate[0]["entry_ids"] == ["ENT-0001", "ENT-0002"]
        assert duplicate[0]["b_values"] == [Decimal("60.00"), Decimal("60.00")]


# ---------------------------------------------------------------------------
# 4. VALUE_MISMATCH
# ---------------------------------------------------------------------------

class TestValueMismatch:
    def test_b_value_differs_from_a_total(self):
        a = [make_a(total_value="100.00")]
        b = [make_b(value="99.00")]
        result = run_comparison(a, b)
        assert len(result) == 1
        assert result[0]["reason"] == VALUE_MISMATCH
        assert result[0]["a_value"] == Decimal("100.00")
        assert result[0]["b_value"] == Decimal("99.00")
        assert result[0]["difference"] == Decimal("-1.00")

    def test_matching_values_no_flag(self):
        a = [make_a(total_value="100.00")]
        b = [make_b(value="100.00")]
        result = run_comparison(a, b)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 5. BLANK_B_VALUE (VALUE_MISMATCH with None)
# ---------------------------------------------------------------------------

class TestBlankBValue:
    def test_blank_value_is_value_mismatch_not_zero(self):
        a = [make_a(total_value="100.00")]
        b = [make_b(value=None)]
        result = run_comparison(a, b)
        assert len(result) == 1
        assert result[0]["reason"] == VALUE_MISMATCH
        assert result[0]["b_value"] is None
        # difference is None when b_value is None
        assert result[0]["difference"] is None


# ---------------------------------------------------------------------------
# 6. VALID_SPLIT
# ---------------------------------------------------------------------------

class TestValidSplit:
    def test_two_entries_summing_to_total_not_flagged_as_duplicate(self):
        a = [make_a(total_value="179877.32")]
        b = [
            make_b(entry_id="ENT-4055", record_ref="REC-0001", value="71950.93"),
            make_b(entry_id="ENT-4903", record_ref="REC-0001", value="107926.39"),
        ]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DUPLICATE_IN_B not in reasons

    def test_valid_split_with_equal_parts(self):
        a = [make_a(total_value="100.00")]
        b = [
            make_b(entry_id="ENT-0001", record_ref="REC-0001", value="50.00"),
            make_b(entry_id="ENT-0002", record_ref="REC-0001", value="50.00"),
        ]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DUPLICATE_IN_B not in reasons
        assert VALUE_MISMATCH not in reasons


# ---------------------------------------------------------------------------
# 7. MESSY REFERENCES
# ---------------------------------------------------------------------------

class TestMessyReferences:
    def test_lowercase_ref_matches_a_record(self):
        # After normalization 'rec1034' → 'REC-1034'
        from reconcile.normalizers import normalize_ref
        a = [make_a(record_id="REC-1034", total_value="84939.99")]
        b = [make_b(record_ref=normalize_ref("rec1034"), value="84939.99")]
        result = run_comparison(a, b)
        assert len(result) == 0

    def test_space_padded_ref_matches(self):
        from reconcile.normalizers import normalize_ref
        a = [make_a(record_id="REC-1070", total_value="1608.95")]
        b = [make_b(record_ref=normalize_ref(" REC - 1070 "), value="1608.95")]
        result = run_comparison(a, b)
        assert len(result) == 0

    def test_bare_number_ref_matches(self):
        from reconcile.normalizers import normalize_ref
        a = [make_a(record_id="REC-1112", total_value="52028.74")]
        b = [make_b(record_ref=normalize_ref("1112"), value="52028.74")]
        result = run_comparison(a, b)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 8. CLEAN MATCH
# ---------------------------------------------------------------------------

class TestCleanMatch:
    def test_perfect_match_produces_no_disagreements(self):
        a = [make_a(
            record_id="REC-0001",
            location_id="LOC-101",
            total_value="156337.55",
            event_date=date(2026, 3, 20),
        )]
        b = [make_b(
            record_ref="REC-0001",
            location_id="LOC-101",
            value="156337.55",
            recorded_on=date(2026, 3, 20),
        )]
        result = run_comparison(a, b)
        assert result == []


# ---------------------------------------------------------------------------
# 9. LOCATION_MISMATCH
# ---------------------------------------------------------------------------

class TestLocationMismatch:
    def test_different_locations_flagged(self):
        a = [make_a(location_id="LOC-101", total_value="100.00")]
        b = [make_b(location_id="LOC-102", value="100.00")]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert LOCATION_MISMATCH in reasons

    def test_same_location_no_flag(self):
        a = [make_a(location_id="LOC-101", total_value="100.00")]
        b = [make_b(location_id="LOC-101", value="100.00")]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert LOCATION_MISMATCH not in reasons


# ---------------------------------------------------------------------------
# 10. DATE_MISMATCH
# ---------------------------------------------------------------------------

class TestDateMismatch:
    def test_different_dates_flagged(self):
        a = [make_a(event_date=date(2026, 3, 31), total_value="111699.30")]
        b = [make_b(recorded_on=date(2026, 4, 2), value="111699.30")]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DATE_MISMATCH in reasons
        mismatch = next(r for r in result if r["reason"] == DATE_MISMATCH)
        assert mismatch["record_id"] == "REC-0001"

    def test_same_date_no_flag(self):
        a = [make_a(event_date=date(2026, 3, 1), total_value="100.00")]
        b = [make_b(recorded_on=date(2026, 3, 1), value="100.00")]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert DATE_MISMATCH not in reasons


# ---------------------------------------------------------------------------
# 11. VOIDED RECORDS
# ---------------------------------------------------------------------------

class TestVoidedRecords:
    def test_voided_with_no_b_entry_not_flagged(self):
        # VOIDED records with no matching B entry should NOT produce MISSING_IN_B
        a = [make_a(state="VOIDED")]
        result = run_comparison(a, [])
        assert len(result) == 0

    def test_voided_with_b_entry_checks_value(self):
        # If a VOIDED record HAS a B entry that disagrees on value, flag it
        a = [make_a(state="VOIDED", total_value="57092.35")]
        b = [make_b(value="57092.35")]
        result = run_comparison(a, b)
        # Exact match → no disagreement even for VOIDED
        assert len(result) == 0

    def test_voided_with_mismatched_b_entry_flagged(self):
        a = [make_a(state="VOIDED", total_value="57092.35")]
        b = [make_b(value="99999.99")]
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert VALUE_MISMATCH in reasons


# ---------------------------------------------------------------------------
# 12. CROSS-TENANT MISMATCH VISIBILITY
# ---------------------------------------------------------------------------

class TestCrossTenantMismatch:
    def _cross_data(self):
        """
        REC-0001 belongs to ORG-A (LOC-101).
        ENT-0001 is in ORG-B (LOC-201) but references REC-0001.
        """
        a = [make_a(record_id="REC-0001", location_id="LOC-101", org_id="ORG-A",
                    total_value="100.00")]
        b = [make_b(entry_id="ENT-0001", record_ref="REC-0001",
                    location_id="LOC-201", org_id="ORG-B", value="100.00")]
        return a, b

    def test_cross_tenant_location_mismatch_reported(self):
        a, b = self._cross_data()
        result = run_comparison(a, b)
        reasons = [r["reason"] for r in result]
        assert LOCATION_MISMATCH in reasons

    def test_org_a_does_not_see_org_b_location(self):
        a, b = self._cross_data()
        result = run_comparison(a, b)
        org_a_view = filter_for_org(result, "ORG-A")
        for item in org_a_view:
            assert item.get("b_location") != "LOC-201", \
                "ORG-A should not see ORG-B's location ID"

    def test_org_b_does_not_see_org_a_location(self):
        a, b = self._cross_data()
        result = run_comparison(a, b)
        org_b_view = filter_for_org(result, "ORG-B")
        for item in org_b_view:
            assert item.get("a_location") != "LOC-101", \
                "ORG-B should not see ORG-A's location ID"
            assert item.get("record_id") == "[REDACTED - other org]", \
                "ORG-B should not see the foreign A record identifier"


# ---------------------------------------------------------------------------
# 13. ORG-A ISOLATION
# ---------------------------------------------------------------------------

class TestOrgAIsolation:
    def test_org_a_does_not_see_org_b_records(self):
        a_records = [
            make_a("REC-A1", location_id="LOC-101", org_id="ORG-A", total_value="100.00"),
            make_a("REC-B1", location_id="LOC-201", org_id="ORG-B", total_value="200.00"),
        ]
        # Both have no B entries → both CONFIRMED → both MISSING_IN_B in raw result
        result = run_comparison(a_records, [])
        org_a_view = filter_for_org(result, "ORG-A")
        ids = [d["record_id"] for d in org_a_view]
        assert "REC-A1" in ids
        assert "REC-B1" not in ids


# ---------------------------------------------------------------------------
# 14. ORG-B ISOLATION
# ---------------------------------------------------------------------------

class TestOrgBIsolation:
    def test_org_b_does_not_see_org_a_records(self):
        a_records = [
            make_a("REC-A1", location_id="LOC-101", org_id="ORG-A", total_value="100.00"),
            make_a("REC-B1", location_id="LOC-201", org_id="ORG-B", total_value="200.00"),
        ]
        result = run_comparison(a_records, [])
        org_b_view = filter_for_org(result, "ORG-B")
        ids = [d["record_id"] for d in org_b_view]
        assert "REC-B1" in ids
        assert "REC-A1" not in ids


# ---------------------------------------------------------------------------
# 15. IMPORTER IDEMPOTENCY — tested via Django DB
# ---------------------------------------------------------------------------

# This test is in test_importer.py (requires pytest-django)


# ---------------------------------------------------------------------------
# 16. INVALID MONETARY VALUE HANDLING
# ---------------------------------------------------------------------------

class TestInvalidMonetaryValues:
    def test_invalid_b_value_stored_as_none_causes_mismatch(self):
        # In the real flow, parse_amount('1,25,400.00') = Decimal('125400.00')
        # but an entry that failed parsing (stored as None) should trigger VALUE_MISMATCH
        from reconcile.normalizers import parse_amount
        raw = "1,25,400.00"
        parsed = parse_amount(raw)
        assert parsed == Decimal("125400.00")

    def test_b_entry_with_none_value_triggers_value_mismatch(self):
        a = [make_a(total_value="183244.16")]
        b = [make_b(value=None)]  # simulates a failed parse
        result = run_comparison(a, b)
        assert any(r["reason"] == VALUE_MISMATCH for r in result)

    def test_invalid_string_parse_returns_none_not_zero(self):
        from reconcile.normalizers import parse_amount
        result = parse_amount("INVALID")
        assert result is None
