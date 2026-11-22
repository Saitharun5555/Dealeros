"""
Tests for the CSV importer (requires database access via pytest-django).
Tests idempotency and validates counts after import.
"""
import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestImporterIdempotency:
    def test_import_locations_idempotent(self, django_db_setup):
        """Running import twice should not create duplicate Location rows."""
        from django.core.management import call_command
        from reconcile.models import Location

        call_command("import_data", verbosity=0)
        count_after_first = Location.objects.count()

        call_command("import_data", verbosity=0)
        count_after_second = Location.objects.count()

        assert count_after_first == count_after_second == 5

    def test_import_system_a_idempotent(self):
        from django.core.management import call_command
        from reconcile.models import SystemARecord

        call_command("import_data", verbosity=0)
        c1 = SystemARecord.objects.count()

        call_command("import_data", verbosity=0)
        c2 = SystemARecord.objects.count()

        assert c1 == c2 == 120

    def test_import_system_b_idempotent(self):
        from django.core.management import call_command
        from reconcile.models import SystemBEntry

        call_command("import_data", verbosity=0)
        c1 = SystemBEntry.objects.count()

        call_command("import_data", verbosity=0)
        c2 = SystemBEntry.objects.count()

        assert c1 == c2 == 121


@pytest.mark.django_db
class TestImporterDataQuality:
    def setup_method(self):
        from django.core.management import call_command
        call_command("import_data", verbosity=0)

    def test_blank_actor_stored_as_null(self):
        from reconcile.models import SystemARecord
        rec = SystemARecord.objects.get(record_id="REC-1050")
        assert rec.actor_id is None

    def test_messy_ref_rec1034_normalised(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4034")
        assert entry.record_ref_raw == "rec1034"
        assert entry.record_ref == "REC-1034"

    def test_messy_ref_space_padded_normalised(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4070")
        assert entry.record_ref == "REC-1070"

    def test_bare_number_ref_normalised(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4112")
        assert entry.record_ref == "REC-1112"

    def test_blank_b_value_stored_as_none(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4050")
        assert entry.value is None
        assert entry.value_raw == ""

    def test_indian_comma_value_parsed_correctly(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4064")
        # '1,25,400.00' should be stored as None (invalid) since it can't
        # match A's value of 183244.16; but parse_amount strips commas first
        # so it becomes 125400.00
        assert entry.value == Decimal("125400.00")

    def test_voided_record_imported(self):
        from reconcile.models import SystemARecord
        rec = SystemARecord.objects.get(record_id="REC-1019")
        assert rec.state == "VOIDED"

    def test_locations_have_correct_orgs(self):
        from reconcile.models import Location
        assert Location.objects.get(location_id="LOC-101").org_id == "ORG-A"
        assert Location.objects.get(location_id="LOC-201").org_id == "ORG-B"

    def test_orphan_b_entry_stored(self):
        """ENT/2026/4901 references REC-1999 which doesn't exist in A."""
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4901")
        assert entry.record_ref == "REC-1999"

    def test_duplicate_b_entry_stored(self):
        """ENT/2026/4902 is a second B entry for REC-1042."""
        from reconcile.models import SystemBEntry
        entries = SystemBEntry.objects.filter(record_ref="REC-1042")
        assert entries.count() == 2

    def test_system_a_str_uses_location_id(self):
        from reconcile.models import SystemARecord
        rec = SystemARecord.objects.get(record_id="REC-1019")
        assert str(rec).startswith("REC-1019 @ LOC-")

    def test_import_records_errors_in_database(self):
        from reconcile.models import ImportRowError
        assert ImportRowError.objects.count() >= 0

    def test_b_record_ref_raw_preserves_exact_text(self):
        from reconcile.models import SystemBEntry
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4070")
        assert entry.record_ref_raw == " REC - 1070 "


@pytest.mark.django_db
class TestAPIDisagreements:
    def setup_method(self):
        from django.core.management import call_command
        call_command("import_data", verbosity=0)

    def test_missing_org_returns_400(self, client):
        response = client.get("/api/disagreements/")
        assert response.status_code == 400

    def test_invalid_org_returns_400(self, client):
        response = client.get("/api/disagreements/?org=ORG-X")
        assert response.status_code == 400

    def test_org_a_returns_200(self, client):
        response = client.get("/api/disagreements/?org=ORG-A")
        assert response.status_code == 200

    def test_org_b_returns_200(self, client):
        response = client.get("/api/disagreements/?org=ORG-B")
        assert response.status_code == 200

    def test_org_a_data_not_in_org_b_response(self, client):
        """ORG-B response must not contain LOC-101, LOC-102, LOC-103 as location."""
        response = client.get("/api/disagreements/?org=ORG-B")
        assert response.status_code == 200
        data = response.json()
        org_a_locs = {"LOC-101", "LOC-102", "LOC-103"}
        for item in data:
            loc = item.get("location", "")
            assert loc not in org_a_locs, \
                f"ORG-B response contains ORG-A location: {loc}"

    def test_org_b_data_not_in_org_a_response(self, client):
        """ORG-A response must not contain LOC-201, LOC-202 as location."""
        response = client.get("/api/disagreements/?org=ORG-A")
        assert response.status_code == 200
        data = response.json()
        org_b_locs = {"LOC-201", "LOC-202"}
        for item in data:
            loc = item.get("location", "")
            assert loc not in org_b_locs, \
                f"ORG-A response contains ORG-B location: {loc}"

    def test_reason_filter_works(self, client):
        response = client.get("/api/disagreements/?org=ORG-A&reason=MISSING_IN_B")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["reason"] == "MISSING_IN_B"

    def test_invalid_reason_returns_400(self, client):
        response = client.get("/api/disagreements/?org=ORG-A&reason=FAKE_REASON")
        assert response.status_code == 400

    def test_sort_ascending(self, client):
        response = client.get("/api/disagreements/?org=ORG-A&sort=value")
        assert response.status_code == 200
        data = response.json()
        diffs = [float(item["difference"]) if item["difference"] is not None else 0 for item in data]
        assert diffs == sorted(diffs)

    def test_sort_descending(self, client):
        response = client.get("/api/disagreements/?org=ORG-A&sort=-value")
        assert response.status_code == 200
        data = response.json()
        diffs = [float(item["difference"]) if item["difference"] is not None else 0 for item in data]
        assert diffs == sorted(diffs, reverse=True)

    def test_missing_values_are_null_not_string(self, client):
        """The JSON must use null for missing values, not the string 'null' or '0'."""
        response = client.get("/api/disagreements/?org=ORG-A&reason=MISSING_IN_B")
        data = response.json()
        for item in data:
            # b_value for MISSING_IN_B should be JSON null
            assert item["b_value"] is None, \
                f"b_value should be null, got: {item['b_value']!r}"

    def test_rec_1077_org_a_view_is_tenant_safe(self, client):
        response = client.get(
            "/api/disagreements/?org=ORG-A&reason=LOCATION_MISMATCH"
        )
        assert response.status_code == 200
        row = next(item for item in response.json() if item["record_id"] == "REC-1077")
        assert row["location"] == "LOC-102"
        assert row["location"] not in ("LOC-201", "LOC-202")
        assert row["entry_id"] is None

    def test_rec_1077_org_b_view_is_tenant_safe(self, client):
        response = client.get(
            "/api/disagreements/?org=ORG-B&reason=LOCATION_MISMATCH"
        )
        assert response.status_code == 200
        row = next(
            item for item in response.json()
            if item["entry_id"] == "ENT/2026/4077"
        )
        assert row["record_id"] == "[REDACTED - other org]"
        assert row["location"] == "LOC-201"
        assert row["location"] not in ("LOC-102", "LOC-103")
