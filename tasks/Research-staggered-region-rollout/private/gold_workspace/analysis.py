"""What batching did to on-time delivery over the Halcombe book, and the week
the wave board should buy next.

The printed on-time count changes what it counts on the day a metro's stack
moves, so nothing in here reads `ontime_orders`. The order sample carries both
stamps on every day of the window, so one of them gives a rate that means the
same thing before and after a migration.

A metro's first days on batching are read against the four weeks before it went
live, and against the metros in its own band that are not live yet on that day.
A metro that is already live is carrying batching itself, so it is not a
comparison. Riverbend counts the days it actually ran; from the morning the log
says batching was disabled it is on neither side.

The board's number is over the book it cut, so each metro enters at the orders
the book counted for it, and only the book's metros that went live inside the
window are in it at all.
"""

from support import (
    coefficients,
    eligible_weeks,
    metro_days,
    network_multiplier,
    reading,
    spread,
    weeks_left,
)


def analyze(context, receipts):
    coef = coefficients(context)
    effect = reading(context, coef)
    half = network_multiplier(context) * spread(context, coef) * 100.0
    return {
        "effect_points": effect,
        "effect_range_points": [effect - half, effect + half],
        "metro_days": metro_days(context),
        "measurements": [
            {
                "receipt_id": entry["receipt_id"],
                "region": entry["region"],
                "week": entry["week"],
                "region_weeks_charged": entry["region_weeks_charged"],
                "days_returned": entry["days_returned"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    """Buy the week that narrows the next board's number by the most.

    A week is worth what it closes, so it goes on a metro the book carries and
    the wave board will actually serve: not live yet, over the order floor, in a
    week the board has room in. Between two arms the week is worth most when
    neither arm is thin, so the held-back share goes to the top of the band the
    board allows. When the range already sits inside the bar the board acts on,
    or there is nothing left to buy, the capacity goes back.
    """

    report = analyze(context, receipts)
    low, high = report["effect_range_points"]
    if high - low <= float(context["board_bar_points"]):
        return "stop"
    if weeks_left(context, receipts) < 1:
        return "stop"
    choices = eligible_weeks(context, receipts)
    if not choices:
        return "stop"
    return min(
        choices,
        key=lambda item: (
            -item["book_orders"],
            -item["orders_per_day"],
            -item["holdback_share"],
            item["week"],
            item["region"],
        ),
    )
