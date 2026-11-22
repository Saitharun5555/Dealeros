# DECISIONS.md — Design Decisions for DealerOS

## 1. Why total_value is used for comparison (not base_value)

System B stores a single `value` field per entry. Looking at the data:
- `ENT/2026/4001` has value 88969.92, which matches `REC-1001`'s `total_value` exactly
- `ENT/2026/4001`'s value does NOT match `base_value` (69507.75) or `adjustment` (19462.17)

Across all clean, matching rows, `B.value` aligns with `A.total_value` in every case.
`total_value = base_value + adjustment` is the settled figure that System B was given.
Comparing against anything other than `total_value` would produce false positives on every clean row.

## 2. How references are normalised

System B's `record_ref` column contains three non-standard formats in the actual data:
- `rec1034` — lowercase with no separator
- ` REC - 1070 ` — extra whitespace and spaces around the dash
- `1112` — bare number

The normaliser (`normalizers.py::normalize_ref`) handles all three:
1. Strip outer whitespace
2. Remove all interior whitespace
3. Apply a regex that accepts `REC` (case-insensitive) with optional dash, then digits;
   OR just digits alone
4. Return `REC-{digits}` in uppercase

The raw value is preserved in `record_ref_raw` so the original can always be audited.
If a reference cannot be parsed (e.g. a truly garbage string), it is stored as NULL
and treated as an orphan.

## 3. Why blank B amounts are stored as NULL (not zero)

A blank `value` field means the value is **unknown**, not zero.
Storing it as zero would be a factual error — it would look like a legitimate zero-value
transaction and produce a misleading difference.
Storing it as NULL preserves the information that the value was not provided.
In the reconciliation output, NULL values appear as empty cells in the UI, not "0.00".

This is enforced in `parse_amount()`: empty string → `None`, never `Decimal('0')`.

## 4. How split entries are handled

The assignment defines a valid split as two B entries whose amounts sum **exactly** to
`A.total_value`. The comparison engine extends this to N entries:
- If N entries all have non-null values AND they sum exactly to `A.total_value` → no DUPLICATE_IN_B
- If any entry in the group has a NULL value → flagged as DUPLICATE_IN_B (can't verify the split)
- If the sum ≠ `A.total_value` → flagged as DUPLICATE_IN_B

In the actual data, `REC-1055` is a confirmed valid 2-part split:
- ENT/2026/4055: 71950.93
- ENT/2026/4903: 107926.39
- Sum: 179877.32 = A.total_value ✓

`REC-1042` is a duplicate (not a valid split):
- ENT/2026/4042: 112837.06
- ENT/2026/4902: 112837.06
- Sum: 225674.12 ≠ 112837.06

## 5. How VOIDED records are handled

VOIDED A records represent transactions that were cancelled before being processed.
The decision:
- A VOIDED record with **no B entry** → NOT flagged as MISSING_IN_B.
  Rationale: a voided transaction is expected to have no entry in System B.
- A VOIDED record WITH a B entry → comparisons still apply (location, date, value).
  Rationale: if someone entered a B record for a voided transaction, the amounts should still match.
  A mismatch is still an error worth investigating.

In the actual data, `REC-1019` (VOIDED) has a matching B entry `ENT/2026/4019`
with identical value → no disagreement produced.

## 6. Why date and location mismatches are both flagged

Both mismatches indicate that the two systems recorded different facts about the same
transaction. Even if the value matches, a location or date discrepancy could indicate:
- Data entry error
- The B entry was posted against the wrong record
- The record was moved between locations without syncing

Flagging these independently allows the operations team to investigate and correct each
class of issue separately. We report all independent problems on the same record
(value mismatch + location mismatch can appear together for one record).

## 7. How cross-tenant mismatches are handled

When A's location belongs to ORG-X and B's location belongs to ORG-Y, we face a
visibility problem: reporting the full LOCATION_MISMATCH to either org would leak
the other org's location ID.

Decision:
- Both orgs see the LOCATION_MISMATCH disagreement.
- ORG-X sees its own A record's location; B's location appears as `[REDACTED - other org]`.
- ORG-Y sees its own B entry's location; A's location appears as `[REDACTED - other org]`.
- Neither org can infer which organisation owns the other side.

Ownership for the purposes of appearing in an org's response is determined by
whether the org owns either the A record or the B entry in the disagreement.

## 8. Why Decimal is used (not float)

Financial amounts require exact arithmetic. Floating-point (IEEE 754) cannot represent
many decimal fractions exactly. For example, `0.1 + 0.2 == 0.30000000000000004` in
float arithmetic. This would cause `VALUE_MISMATCH` false positives on any amount that
involves those combinations.

Python's `decimal.Decimal` performs exact decimal arithmetic, ensuring that
`Decimal('0.1') + Decimal('0.2') == Decimal('0.3')` is always `True`.

Django's `DecimalField` stores values as `NUMERIC` in SQLite, which preserves precision.

## 9. Why SQLite is used

The assessment is a development/evaluation project. SQLite requires zero infrastructure
(no database server), is bundled with Python, and is sufficient for the data size
(< 10,000 rows). For production, the Django ORM code is compatible with PostgreSQL by
changing only the `DATABASES` setting in `config/settings.py`.

## 10. Why there is no FK from SystemBEntry to SystemARecord

The assignment explicitly requires that every B row is importable, including orphan
rows that reference non-existent A records. A database-level FK constraint would
refuse to insert those rows. By omitting the FK and using `record_ref` as a plain
string (after normalisation), orphans are stored and surfaced as `ORPHAN_IN_B` in the
comparison engine.
