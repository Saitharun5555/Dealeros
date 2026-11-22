"""
Database models for the DealerOS reconciliation system.

Three tables mirror the three CSV sources:
  - Location       (from locations.csv)
  - SystemARecord  (from system-a.csv)
  - SystemBEntry   (from system-b.csv)

We deliberately do NOT create a FK from SystemBEntry → SystemARecord
so that orphan B entries (referencing non-existent A records) are
still stored and reportable.
"""

from django.db import models


class Location(models.Model):
    """
    Single source of truth for location → organisation mapping.
    Populated exclusively from locations.csv.
    """
    location_id = models.CharField(max_length=50, unique=True)
    org_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.location_id} ({self.org_id})"


class SystemARecord(models.Model):
    """
    One row from system-a.csv.
    actor_id is nullable because REC-1050 has no actor.
    """
    record_id = models.CharField(max_length=50, unique=True)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="a_records"
    )
    event_date = models.DateField()
    category_code = models.CharField(max_length=50)
    actor_id = models.CharField(max_length=50, blank=True, null=True)
    base_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    adjustment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.record_id} @ {self.location.location_id} = {self.total_value}"


class SystemBEntry(models.Model):
    """
    One row from system-b.csv.

    record_ref_raw  : the original reference string exactly as found in the CSV
    record_ref      : normalised form (e.g. 'REC-1034'), NULL if unresolvable
    value_raw       : the original value string exactly as found in the CSV
    value           : parsed Decimal, NULL when value_raw is blank or unparseable

    No FK to SystemARecord — orphan entries must survive import.
    """
    entry_id = models.CharField(max_length=50, unique=True)
    record_ref_raw = models.CharField(max_length=100)
    record_ref = models.CharField(max_length=50, blank=True, null=True)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="b_entries"
    )
    recorded_on = models.DateField()
    value_raw = models.CharField(max_length=100, blank=True)
    value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    label = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.entry_id} ref={self.record_ref} val={self.value}"


class ImportRowError(models.Model):
    """A malformed or invalid CSV row recorded without stopping the import."""
    source_file = models.CharField(max_length=200)
    row_number = models.PositiveIntegerField()
    record_id = models.CharField(max_length=100, blank=True)
    raw_row = models.TextField()
    errors = models.TextField()
