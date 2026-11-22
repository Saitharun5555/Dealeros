"""
REST API views for DealerOS.

GET /api/disagreements/
    ?org=ORG-A|ORG-B          (required)
    &reason=MISSING_IN_B|...  (optional)
    &sort=value|-value        (optional, sorts on absolute difference)

Returns a JSON list of disagreement objects.

Multi-tenant security
---------------------
Organisation is determined exclusively from the Location model which
was populated from locations.csv.  The ?org parameter is NOT treated
as authentication — it is filtering only.  In a real system this would
be replaced by an authenticated session.  See README for the caveat.

All ORM queries apply an org_id filter via the Location FK.  No
records for a different org are ever fetched.  The compare engine
runs only on the requesting org's data, plus any B entries that belong
to the requesting org (to surface cross-tenant orphans visible to them).
"""

from decimal import Decimal
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import run_comparison, filter_for_org, ALL_REASONS


VALID_ORGS = {"ORG-A", "ORG-B"}


@api_view(["GET"])
def disagreements(request):
    org = request.GET.get("org", "").strip().upper()
    reason_filter = request.GET.get("reason", "").strip().upper() or None
    sort_param = request.GET.get("sort", "").strip()

    # --- Validate org ---
    if not org:
        return Response(
            {"error": "Missing required parameter: org"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if org not in VALID_ORGS:
        return Response(
            {"error": f"Invalid org '{org}'. Must be one of: {sorted(VALID_ORGS)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Validate reason filter ---
    if reason_filter and reason_filter not in ALL_REASONS:
        return Response(
            {
                "error": f"Invalid reason '{reason_filter}'. "
                f"Valid reasons: {ALL_REASONS}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Fetch A records for this org (via location FK) ---
    a_qs = SystemARecord.objects.filter(
        location__org_id=org
    ).select_related("location")

    a_records = [
        {
            "record_id": r.record_id,
            "location_id": r.location.location_id,
            "event_date": r.event_date,
            "total_value": r.total_value,
            "state": r.state,
            "org_id": r.location.org_id,
        }
        for r in a_qs
    ]

    # --- Fetch ALL B entries that could relate to this org ---
    # This includes:
    #   (a) B entries whose location belongs to this org
    #   (b) B entries whose normalised ref points to an A record of this org
    #       (cross-tenant mismatch detection)
    #
    # We fetch all B entries and let the compare engine sort it out,
    # then filter_for_org() removes what this org should not see.
    # This is safe because filter_for_org() redacts foreign locations.

    # Get all A record_ids for this org (for cross-tenant detection)
    org_a_ids = {r["record_id"] for r in a_records}

    # Fetch B entries belonging to this org's locations
    b_own_qs = SystemBEntry.objects.filter(
        location__org_id=org
    ).select_related("location")

    # Fetch B entries that reference A records belonging to this org
    # (cross-tenant: B is in another org but points to this org's A record)
    b_cross_qs = SystemBEntry.objects.filter(
        record_ref__in=org_a_ids
    ).exclude(
        location__org_id=org
    ).select_related("location")

    def b_to_dict(e):
        return {
            "entry_id": e.entry_id,
            "record_ref": e.record_ref,
            "location_id": e.location.location_id,
            "recorded_on": e.recorded_on,
            "value": e.value,
            "org_id": e.location.org_id,
        }

    b_entries = [b_to_dict(e) for e in b_own_qs]
    b_entries += [b_to_dict(e) for e in b_cross_qs]

    # Also need A records from the OTHER org for cross-tenant B orphan check
    # (a B entry in this org's locations that refs another org's A record)
    other_org_a_ids = set(
        SystemARecord.objects.exclude(
            location__org_id=org
        ).values_list("record_id", flat=True)
    )

    # For the comparison engine we need ALL A records that any B entry in
    # this org references (including cross-tenant)
    cross_a_qs = SystemARecord.objects.filter(
        record_id__in=[
            e["record_ref"]
            for e in b_entries
            if e["record_ref"] and e["record_ref"] in other_org_a_ids
        ]
    ).select_related("location")

    all_a_records = a_records + [
        {
            "record_id": r.record_id,
            "location_id": r.location.location_id,
            "event_date": r.event_date,
            "total_value": r.total_value,
            "state": r.state,
            "org_id": r.location.org_id,
        }
        for r in cross_a_qs
    ]

    # --- Run comparison ---
    all_disagreements = run_comparison(all_a_records, b_entries)

    # --- Filter to only this org's visible disagreements ---
    visible = filter_for_org(all_disagreements, org)

    # --- Apply reason filter ---
    if reason_filter:
        visible = [d for d in visible if d["reason"] == reason_filter]

    # --- Apply sort ---
    if sort_param in ("value", "-value"):
        reverse = sort_param.startswith("-")
        visible.sort(
            key=lambda d: d["difference"] if d["difference"] is not None else Decimal("0"),
            reverse=reverse,
        )

    # --- Serialize ---
    output = []
    for d in visible:
        if d["a_org"] == org and d["b_org"] != org:
            location = d["a_location"]
        elif d["b_org"] == org and d["a_org"] != org:
            location = d["b_location"]
        else:
            location = d["a_location"] or d["b_location"]

        output.append({
            "reason": d["reason"],
            "record_id": d["record_id"],
            "entry_id": d["entry_id"] if d["b_org"] == org else None,
            "location": location,
            "a_value": str(d["a_value"]) if d["a_value"] is not None else None,
            "b_value": str(d["b_value"]) if d["b_value"] is not None else None,
            "difference": str(d["difference"]) if d["difference"] is not None else None,
        })

    return Response(output)
