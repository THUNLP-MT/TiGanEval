"""The quarterly triage report for a centre the pipeline was shipped into."""

from support import (
    combined,
    groups,
    range_bounds,
    reviews,
    units_left,
    units_used,
    unseen_band,
)


def analyze(context, ledger):
    found = groups(context, ledger)
    centre = combined(found)
    interval = range_bounds(found) if found else None
    return {
        "served_error": centre,
        "error_interval": interval,
        "groups": found,
        "reviews": reviews(ledger),
        "units_used": units_used(ledger),
    }


def next_collection(context, ledger):
    """Buy the band the queue never shows, while the quarter can still pay for it."""

    band = unseen_band(context)
    if band is None:
        return "stop"
    unit = int(context["review"]["unit_cost"]["export"])
    cap = int(context["review"]["max_rows_per_request"]["export"])
    rows = min(cap, units_left(context, ledger) // unit)
    if rows <= 0:
        return "stop"
    return {
        "site": context["site"],
        "channel": "export",
        "prior_contacts_min": band["prior_contacts_min"],
        "prior_contacts_max": band["prior_contacts_max"],
        "rows": rows,
    }
