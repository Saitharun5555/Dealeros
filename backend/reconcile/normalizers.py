"""
Data normalization helpers.

These are pure functions — no Django imports, no database access.
They are tested directly in tests/test_normalizers.py.
"""
import re
from decimal import Decimal, InvalidOperation


def normalize_ref(raw):
    """
    Normalise a System-B record_ref to the canonical 'REC-NNNN' format.

    Handled cases
    -------------
    'REC-1034'      -> 'REC-1034'   (already canonical)
    'rec1034'       -> 'REC-1034'   (lowercase, no separator)
    ' REC - 1070 '  -> 'REC-1070'   (extra whitespace around separator)
    '1112'          -> 'REC-1112'   (bare number)
    'REC-1042'      -> 'REC-1042'   (normal)

    Returns None for empty / truly unrecognisable input.
    """
    if not raw:
        return None

    s = raw.strip()
    if not s:
        return None

    # Remove all whitespace inside the string
    s = re.sub(r"\s+", "", s)

    # Pattern: optional 'REC' prefix, optional separator, then digits
    m = re.fullmatch(r"(?:REC[-]?)?(\d+)", s, re.IGNORECASE)
    if m:
        number = m.group(1)
        return f"REC-{number}"

    return None


def parse_amount(raw):
    """
    Parse a monetary string to Decimal.

    Handled cases
    -------------
    '88969.92'       -> Decimal('88969.92')
    '1,25,400.00'    -> Decimal('125400.00')   (Indian grouping commas stripped)
    ''               -> None                   (blank → unknown, NOT zero)
    None             -> None
    'abc'            -> None                   (invalid → None, NOT zero)

    Rules
    -----
    - Strip leading/trailing whitespace.
    - Remove all commas before parsing (commas are only digit grouping).
    - Return None for blank or unparseable input.
    - NEVER return Decimal('0') for invalid/blank input.
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if not s:
        return None

    # Remove grouping commas (e.g. 1,25,400.00 → 125400.00)
    s = s.replace(",", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        return None
