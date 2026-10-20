"""What the grace window costs at this desk, and the week to book next.

The flags on accounts the desk could not have started that day are not the
desk's to answer for, so they come out first. What is left is counted from the
flag date on the side the desk put it on: an account it started that day on one
side, an account it queued on the other, whether or not the queue ever reached
it. A queued account stops saying anything about waiting once the grace window
has closed without a start, so it stops counting there.

The export stops two days before the migration, so each flag is carried only
over the days it was actually watched and the daily rate that gives is turned
into the twenty-eight day risk the review asks about.

The desk holds quieter accounts than it starts, so the two sides are compared
inside each error rate and plan tier and put back together with the share of the
desk's own book each segment carries, not the share of the flags this window
happened to raise.
"""

from support import (
    arm_days,
    book_weights,
    combine,
    matches,
    recent_mix,
    segments,
    slots_left,
    spread_after,
)


def analyze(context, receipts):
    horizon = int(context["escalation_window_days"])
    cells = arm_days(context)
    cost, spread, days = combine(cells, book_weights(context), horizon)
    return {
        "cost_points": cost,
        "cost_range_points": [cost - 1.96 * spread, cost + 1.96 * spread],
        "account_days": days,
        "weeks": [
            {
                "receipt_id": entry["receipt_id"],
                "slots_charged": entry["slots_charged"],
                "rows_returned": entry["rows_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    """Buy the week that narrows the answer most, inside what the desk will serve.

    The desk lead's own week puts the cap's share on the whole book. A week
    aimed at the segment whose thin side is carrying the range does better for
    the same slots, so the sheet takes the best of the selectors the desk
    accepts. When the slots left will not buy the smallest week the desk serves,
    there is nothing left to book.
    """

    horizon = int(context["escalation_window_days"])
    capacity = context["capacity"]
    left = slots_left(context, receipts)
    if left < int(capacity["smallest_week_slots"]):
        return "stop"
    slots = min(int(capacity["slots_per_week"]), left)
    cap = float(capacity["hold_cap"])
    cells = arm_days(context)
    weights = book_weights(context)
    mix = recent_mix(context)
    best = None
    for selector in segments(context):
        if sum(share for key, share in mix.items() if matches(selector, key)) <= 0.02:
            continue
        for hold in (0.2, 0.35, 0.5, cap):
            spread = spread_after(cells, weights, context, selector, hold, slots, horizon)
            if spread is None:
                continue
            if best is None or spread < best[0]:
                best = (spread, selector, hold)
    if best is None:
        return {"segment": "all", "hold_share": cap, "slots": slots}
    return {"segment": best[1], "hold_share": best[2], "slots": slots}
