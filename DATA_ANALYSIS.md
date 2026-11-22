# DATA_ANALYSIS.md — DealerOS CSV Data Quality Report

## Overview

| File | Rows | Notes |
|------|------|-------|
| locations.csv | 5 | Clean |
| system-a.csv | 120 | 1 blank actor |
| system-b.csv | 121 | Multiple quality issues |

---

## 1. locations.csv

**Total rows:** 5

| location_id | org_id | location_name |
|-------------|--------|---------------|
| LOC-101 | ORG-A | Location 101 |
| LOC-102 | ORG-A | Location 102 |
| LOC-103 | ORG-A | Location 103 |
| LOC-201 | ORG-B | Location 201 |
| LOC-202 | ORG-B | Location 202 |

**Issues found:** None. All rows are clean and complete.

**Org mapping:**
- ORG-A owns: LOC-101, LOC-102, LOC-103
- ORG-B owns: LOC-201, LOC-202

---

## 2. system-a.csv

**Total rows:** 120

### Missing / blank values

| Record | Field | Issue |
|--------|-------|-------|
| REC-1050 | actor_id | Blank — stored as NULL |

### State distribution

| State | Count |
|-------|-------|
| CONFIRMED | 119 |
| VOIDED | 1 (REC-1019) |

### Duplicate identifiers
None found — all 120 `record_id` values are unique.

### Indian-format monetary value
None found — all `base_value`, `adjustment`, and `total_value` fields are well-formed decimals.

### Verification: total_value = base_value + adjustment
Spot-checked; all totals are consistent with base + adjustment.

### Orphan references
Not applicable — System A references locations, all of which exist in locations.csv.

---

## 3. system-b.csv

**Total rows:** 121 (System A has 120 rows; the 121st B entry is an orphan/duplicate)

### Missing entry numbers (gaps in ENT/2026/4xxx sequence)

| Missing | Notes |
|---------|-------|
| ENT/2026/4015 | No B entry for REC-1015 → MISSING_IN_B |
| ENT/2026/4061 | No B entry for REC-1061 → MISSING_IN_B |

These are legitimate gaps; both A records (REC-1015, REC-1061) have no matching B entry.

### Malformed / non-standard record_ref values

| entry_id | record_ref_raw | Normalised to | Issue |
|----------|---------------|---------------|-------|
| ENT/2026/4034 | `rec1034` | `REC-1034` | Lowercase, no separator |
| ENT/2026/4070 | ` REC - 1070 ` | `REC-1070` | Extra whitespace, spaces around dash |
| ENT/2026/4112 | `1112` | `REC-1112` | Bare number, no prefix |

### Blank / NULL values

| entry_id | record_ref | value_raw | Issue |
|----------|-----------|-----------|-------|
| ENT/2026/4050 | REC-1050 | (empty) | Value unknown — stored as NULL, flagged as VALUE_MISMATCH |

### Invalid monetary values

| entry_id | value_raw | Parsed as | Issue |
|----------|----------|-----------|-------|
| ENT/2026/4064 | `"1,25,400.00"` | `125400.00` | Indian-format comma grouping is accepted and normalized; A's total_value is 183244.16 → VALUE_MISMATCH |

Note: The comma-grouped value parses successfully to 125400.00 after stripping commas.
However it does NOT match A's total_value of 183244.16, so it generates a VALUE_MISMATCH.

### Orphan B entries (reference non-existent A records)

| entry_id | record_ref | Location (org) | Notes |
|----------|-----------|----------------|-------|
| ENT/2026/4901 | REC-1999 | LOC-102 (ORG-A) | REC-1999 does not exist in System A |

### Duplicate B entries (multiple B entries for one A record)

| A record | B entry 1 | B entry 2 | Total B | A total | Valid split? |
|----------|-----------|-----------|---------|---------|-------------|
| REC-1042 (LOC-101, ORG-A) | ENT/2026/4042: 112837.06 | ENT/2026/4902: 112837.06 | 225674.12 | 112837.06 | No — duplicate amounts |
| REC-1055 (LOC-103, ORG-A) | ENT/2026/4055: 71950.93 | ENT/2026/4903: 107926.39 | 179877.32 | 179877.32 | YES — valid split |

**REC-1042:** Two B entries with identical amounts (112837.06 each), summing to 225674.12 ≠ 112837.06. This is a **DUPLICATE_IN_B**.

**REC-1055:** Two B entries with different amounts that sum exactly to A's total_value (179877.32). This is a **valid split** — not flagged as duplicate. Note that ENT/2026/4055 alone has 71950.93 ≠ 179877.32, so the split is essential.

### Date mismatches

| A record | A date | B entry | B date | Notes |
|----------|--------|---------|--------|-------|
| REC-1009 | 2026-03-31 | ENT/2026/4009 | 2026-04-02 | DATE_MISMATCH (1 day off) |

### Location mismatches

| A record | A location (org) | B entry | B location (org) | Notes |
|----------|-----------------|---------|-----------------|-------|
| REC-1077 | LOC-102 (ORG-A) | ENT/2026/4077 | LOC-201 (ORG-B) | Cross-tenant LOCATION_MISMATCH |

This is the cross-tenant mismatch: REC-1077 belongs to ORG-A (LOC-102) but its matching B entry
is at LOC-201 which belongs to ORG-B.

### Cross-tenant inconsistencies

The REC-1077 / ENT/2026/4077 case is the only cross-tenant inconsistency found.
The API handles this by:
- Showing ORG-A the LOCATION_MISMATCH with B's location redacted
- Showing ORG-B the LOCATION_MISMATCH with A's location redacted

### VOIDED record

| record_id | B entry | Notes |
|-----------|---------|-------|
| REC-1019 | ENT/2026/4019 | B entry exists and value matches — no disagreement |

---

## Summary of all data quality issues found

| # | Type | Record(s) | Severity |
|---|------|-----------|----------|
| 1 | Blank actor_id | REC-1050 | Low |
| 2 | Lowercase ref | ENT/2026/4034 (`rec1034`) | Medium |
| 3 | Whitespace-padded ref | ENT/2026/4070 (` REC - 1070 `) | Medium |
| 4 | Bare-number ref | ENT/2026/4112 (`1112`) | Medium |
| 5 | Blank B value | ENT/2026/4050 | High |
| 6 | Indian-format amount mismatch | ENT/2026/4064 (`1,25,400.00`) | High |
| 7 | Orphan B entry | ENT/2026/4901 (REC-1999) | High |
| 8 | Duplicate B entries | REC-1042 (ENT/2026/4042 + 4902) | High |
| 9 | Valid split | REC-1055 (ENT/2026/4055 + 4903) | Informational |
| 10 | Date mismatch | REC-1009 / ENT/2026/4009 (1 day off) | Medium |
| 11 | Cross-tenant location mismatch | REC-1077 (ORG-A) / ENT/2026/4077 (ORG-B) | High |
| 12 | VOIDED state | REC-1019 | Informational |
