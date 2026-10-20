"""Fourteen-day reorder lift for one-tap reorder, and the next booking.

The users the job has finished measuring are not the app: the audience roll-up
counts far more people at one session in twenty-eight days than the watch has
enrolled, and far fewer at thirty. Each session count is read on its own and
put back together with the weights the roll-up carries.

The reorder topic never took every event on the republish days, and the
enrolment topic took all of them, so on those days the table holds fewer
reorders than happened and the denominators are whole. Each of those days is
scaled back up by what the ingestion receipts say went missing.

The bound carries the looks the charter granted, because the watch is read
weekly and the call can be made at any of them.
"""

from support import (
    carried_share,
    cells,
    difference,
    look_multiplier,
    points_left,
    app_weights,
    standard_error,
    strata,
)


def analyze(context, ledger):
    rows = strata(cells(context, restore=True), app_weights(context))
    lift = difference(rows) * 100.0
    spread = look_multiplier(context) * standard_error(rows) * 100.0
    line = float(context["ship_line_points"])
    return {
        "lift_points": lift,
        "lift_interval_points": [lift - spread, lift + spread],
        "decision": "ship" if lift - spread >= line else "continue",
        "measurements": [
            {
                "call_id": entry["call_id"],
                "share_pct": entry["share_pct"],
                "days": entry["days"],
                "share_day_points": entry["share_day_points"],
            }
            for entry in ledger
        ],
    }


def next_collection(context, ledger):
    """One valid continuation that keeps the watch open through later looks.

    The windows still open belong to enrolments the watch has already paid for,
    and a booking shorter than one weekly look adds no useful close. The contract
    also permits a shorter valid commitment of at least a week; this reference
    uses more of the available horizon without claiming it is the only answer.
    """

    left = points_left(context, ledger)
    week = 7
    if left < week:
        return "stop"
    days = min(2 * int(context["reorder_window_days"]), left)
    share = max(1, min(carried_share(context), left // days))
    return {"share_pct": int(share), "days": int(days), "hold_ramp": True}
