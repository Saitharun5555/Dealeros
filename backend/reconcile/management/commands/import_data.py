"""
Management command: python manage.py import_data

Reads the three CSV files from backend/data/ and loads them into
the SQLite database.

Idempotency
-----------
Uses update_or_create on the natural key of each model, so running
this command multiple times will not create duplicates.

Error handling
--------------
Malformed rows are logged but do NOT stop the import — every row
is attempted.  Invalid amounts become NULL (never zero).
"""
import csv
import json
import logging
from pathlib import Path
from datetime import date

from django.core.management.base import BaseCommand

from reconcile.models import (
    Location,
    SystemARecord,
    SystemBEntry,
    ImportRowError,
)
from reconcile.normalizers import normalize_ref, parse_amount

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class Command(BaseCommand):
    help = "Import locations.csv, system-a.csv, and system-b.csv into the database."

    def _record_error(self, path, row_number, record_id, row, message):
        raw_row = json.dumps(row, ensure_ascii=False, sort_keys=True)
        ImportRowError.objects.create(
            source_file=path.name,
            row_number=row_number,
            record_id=record_id or "",
            raw_row=raw_row,
            errors=message,
        )
        self.stdout.write(
            f"  [ERROR] Row {row_number} ({record_id or 'no identifier'}): "
            f"{message}"
        )

    def handle(self, *args, **options):
        ImportRowError.objects.all().delete()
        self.stdout.write("=== DealerOS CSV Import ===\n")
        self._import_locations()
        self._import_system_a()
        self._import_system_b()
        self.stdout.write("\n=== Import complete ===\n")

    # ------------------------------------------------------------------
    # locations.csv
    # ------------------------------------------------------------------

    def _import_locations(self):
        path = DATA_DIR / "locations.csv"
        self.stdout.write(f"\nImporting {path} ...")
        read = saved = blanks = 0

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                read += 1
                loc_id = (row.get("location_id") or "").strip()
                org_id = (row.get("org_id") or "").strip()
                name = (row.get("location_name") or "").strip()

                if not loc_id:
                    self._record_error(path, read, "", row, "blank location_id")
                    blanks += 1
                    continue
                if not org_id:
                    self._record_error(path, read, loc_id, row, "blank org_id")
                    blanks += 1
                    continue

                Location.objects.update_or_create(
                    location_id=loc_id,
                    defaults={"org_id": org_id, "name": name},
                )
                saved += 1

        self.stdout.write(
            f"  Locations: read={read}  saved={saved}  skipped={blanks}"
        )

    # ------------------------------------------------------------------
    # system-a.csv
    # ------------------------------------------------------------------

    def _import_system_a(self):
        path = DATA_DIR / "system-a.csv"
        self.stdout.write(f"\nImporting {path} ...")
        read = saved = errors = blank_actors = 0

        # Build a lookup to avoid per-row DB queries
        loc_lookup = {loc.location_id: loc for loc in Location.objects.all()}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                read += 1
                record_id = (row.get("record_id") or "").strip()
                if not record_id:
                    self._record_error(path, read, "", row, "blank record_id")
                    errors += 1
                    continue

                loc_id = (row.get("location_id") or "").strip()
                location = loc_lookup.get(loc_id)
                if location is None:
                    self._record_error(
                        path, read, record_id, row,
                        f"unknown location '{loc_id}'",
                    )
                    errors += 1
                    continue

                actor = (row.get("actor_id") or "").strip() or None
                if actor is None:
                    blank_actors += 1

                try:
                    event_date = date.fromisoformat((row.get("event_date") or "").strip())
                except (ValueError, KeyError) as exc:
                    self._record_error(path, read, record_id, row, f"bad date: {exc}")
                    errors += 1
                    continue

                base_raw = row.get("base_value")
                adjustment_raw = row.get("adjustment")
                total_raw = row.get("total_value")
                base_value = parse_amount(base_raw)
                adjustment = parse_amount(adjustment_raw)
                total_value = parse_amount(total_raw)

                if None in (base_value, adjustment, total_value):
                    bad_fields = [
                        name for name, value in (
                            ("base_value", base_value),
                            ("adjustment", adjustment),
                            ("total_value", total_value),
                        ) if value is None
                    ]
                    self._record_error(
                        path, read, record_id, row,
                        f"unparseable numeric field(s): {', '.join(bad_fields)}; "
                        "stored as NULL",
                    )
                    errors += 1

                SystemARecord.objects.update_or_create(
                    record_id=record_id,
                    defaults={
                        "location": location,
                        "event_date": event_date,
                        "category_code": (row.get("category_code") or "").strip(),
                        "actor_id": actor,
                        "base_value": base_value,
                        "adjustment": adjustment,
                        "total_value": total_value,
                        "state": (row.get("state") or "").strip(),
                    },
                )
                saved += 1

        self.stdout.write(
            f"  SystemA: read={read}  saved={saved}  errors={errors}"
            f"  blank_actors={blank_actors}"
        )

    # ------------------------------------------------------------------
    # system-b.csv
    # ------------------------------------------------------------------

    def _import_system_b(self):
        path = DATA_DIR / "system-b.csv"
        self.stdout.write(f"\nImporting {path} ...")
        read = saved = errors = blank_values = cleaned_refs = 0

        loc_lookup = {loc.location_id: loc for loc in Location.objects.all()}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                read += 1
                entry_id = (row.get("entry_id") or "").strip()
                if not entry_id:
                    self._record_error(path, read, "", row, "blank entry_id")
                    errors += 1
                    continue

                loc_id = (row.get("location_id") or "").strip()
                location = loc_lookup.get(loc_id)
                if location is None:
                    self._record_error(
                        path, read, entry_id, row,
                        f"unknown location '{loc_id}'",
                    )
                    errors += 1
                    continue

                try:
                    recorded_on = date.fromisoformat((row.get("recorded_on") or "").strip())
                except (ValueError, KeyError) as exc:
                    self._record_error(path, read, entry_id, row, f"bad date: {exc}")
                    errors += 1
                    continue

                # Normalise reference
                ref_raw = row.get("record_ref") or ""
                ref_norm = normalize_ref(ref_raw)
                if ref_norm != ref_raw:
                    cleaned_refs += 1
                    if ref_norm:
                        self.stdout.write(
                            f"  [INFO] Row {read} ({entry_id}): "
                            f"ref '{ref_raw}' normalised to '{ref_norm}'"
                        )
                    else:
                        self._record_error(
                            path, read, entry_id, row,
                            f"reference '{ref_raw}' could not be normalised; "
                            "stored as NULL",
                        )

                # Parse value
                value_raw = row.get("value", "")
                value = parse_amount(value_raw)
                if value is None and value_raw.strip():
                    self._record_error(
                        path, read, entry_id, row,
                        f"unparseable value '{value_raw}'; stored as NULL",
                    )
                if not value_raw.strip():
                    blank_values += 1

                SystemBEntry.objects.update_or_create(
                    entry_id=entry_id,
                    defaults={
                        "record_ref_raw": ref_raw,
                        "record_ref": ref_norm,
                        "location": location,
                        "recorded_on": recorded_on,
                        "value_raw": value_raw,
                        "value": value,
                        "label": row.get("label", "").strip(),
                    },
                )
                saved += 1

        self.stdout.write(
            f"  SystemB: read={read}  saved={saved}  errors={errors}"
            f"  blank_values={blank_values}  cleaned_refs={cleaned_refs}"
        )
