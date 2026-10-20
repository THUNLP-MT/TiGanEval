"""What the offer is worth at the line, and the next lot of files to review.

The accounts the line decided are the ones the run scored, read on the score
the run used and taken from within five points of the line either way; an
account a manager's credit carried over the line was not decided by the line
and is left out. An order reaches the export two days after it happens and the
export stops before the window does, so each account is counted over the days
it was actually watched and the rate is read back as a sixty-day chance.

The range is the one that would have held on every market the council's slide
carries, and it is worked off the account-days behind it, which the report
carries so the council can see what it stands on.
"""

from support import (
    files_left,
    near_cut_rows,
    person_time,
    range_multiplier,
    sixty_day_rate,
    standard_error,
    week_with_most_files,
)


BAND = 5.0


def analyze(context, receipts):
    window = int(context["order_window_days"])
    rows = near_cut_rows(context, receipts, BAND)
    tally = person_time(rows)
    above = sixty_day_rate(tally[1][0], tally[1][1], window)
    below = sixty_day_rate(tally[0][0], tally[0][1], window)
    effect = 100.0 * (above - below)
    spread = 100.0 * range_multiplier(context) * standard_error(tally, window)
    return {
        "offer_effect_points": effect,
        "effect_range_points": [effect - spread, effect + spread],
        "account_days": tally[0][1] + tally[1][1],
        "lots": [
            {
                "receipt_id": entry["receipt_id"],
                "files_charged": entry["files_charged"],
                "rows_returned": entry["rows_returned"],
            }
            for entry in receipts
        ],
    }


def next_review(context, receipts):
    """Buy files that straddle the line: nothing else speaks to the difference.

    A lot bought outside the band the line decides narrows nothing, and a lot
    smaller than the desk's smallest does not pay for the morning. Stop when
    the files left cannot buy that smallest lot, and stop as well once the
    range in hand is already inside what the council asks for.
    """

    grant = context["review_grant"]
    left = files_left(context, receipts)
    if left < int(grant["smallest_lot"]):
        return "stop"
    low, high = analyze(context, receipts)["effect_range_points"]
    if high - low <= float(context["council"]["range_bar_points"]):
        return "stop"
    week = week_with_most_files(context, receipts, BAND)
    if week is None:
        return "stop"
    return {
        "week": int(week),
        "band": BAND,
        "above_share": 0.5,
        "files": int(min(int(grant["files_per_booking"]), left)),
    }
