"""The board pack for one fleet's bundle decision."""

from support import (
    cells_with_units,
    credits_left,
    credits_used,
    profiles,
    ranking,
    requests,
    separation,
    spread,
)

SMALLEST = 20


def analyze(context, receipts):
    order = ranking(context, receipts)
    best = order[0]
    half = spread(best["points"], best["rows"])
    return {
        "bundle": best["bundle"],
        "worst_profile": best["worst_profile"],
        "fleet_points": best["points"],
        "points_range": [best["points"] - half, best["points"] + half],
        "rows_used": best["rows"],
        "bundle_points": [
            {"bundle": entry["bundle"], "points": entry["points"]} for entry in order
        ],
        "requests": requests(receipts),
        "credits_used": credits_used(receipts),
    }


def next_collection(context, receipts):
    """Buy the bay that decides the top two, while the grant can still pay for it."""

    order = ranking(context, receipts)
    best = order[0]
    if len(order) > 1:
        apart = order[1]["points"] - best["points"]
        if apart > 2.0 * spread(best["points"], best["rows"]):
            return "stop"
    terms = context["annotation"]
    cap = int(terms["max_rows_per_request"])
    left = credits_left(context, receipts)
    counter = counter_plan(context, receipts, cap)
    wanted = []
    for entry in order[:2]:
        profile = entry["worst_profile"]
        if profile in [item["duty_profile"] for item in wanted]:
            continue
        cost = int(terms["credit_cost_per_row"][profile])
        rows = min(cap, left // cost)
        if rows < SMALLEST:
            continue
        if separation(context, receipts, profile, rows) <= counter:
            continue
        for firmware in (context["firmware"]["raised"], context["firmware"]["earlier"]):
            cells = cells_with_units(context, profile, firmware)
            if cells:
                wanted.append(
                    {
                        "duty_profile": profile,
                        "firmware": firmware,
                        "condition": cells[0],
                        "rows": rows,
                    }
                )
                break
    return wanted[0] if wanted else "stop"


def counter_plan(context, receipts, cap):
    """What the request the campaign was going to make anyway would buy."""

    if "counter" not in profiles(context):
        return 0.0
    return separation(context, receipts, "counter", cap)
