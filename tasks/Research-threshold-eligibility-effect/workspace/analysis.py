"""What the offer is worth at the line, read off the offer register.

Order rate above the line against order rate below it, on the standing score
the register carries today, differenced and written in points. The review files
that are left go on the accounts that took the offer, which is the side the
council asks about.
"""

from math import sqrt


def analyze(context, receipts):
    cut = float(context["cut"])
    above = [row for row in context["register"] if float(row["standing_score"]) >= cut]
    below = [row for row in context["register"] if float(row["standing_score"]) < cut]
    rate_above = ordered_share(above)
    rate_below = ordered_share(below)
    effect = (rate_above - rate_below) * 100.0
    error = 100.0 * sqrt(
        rate_above * (1.0 - rate_above) / max(1, len(above))
        + rate_below * (1.0 - rate_below) / max(1, len(below))
    )
    return {
        "offer_effect_points": effect,
        "effect_range_points": [effect - 1.96 * error, effect + 1.96 * error],
        "lots": [],
    }


def ordered_share(rows):
    """The share of these accounts the export carries an order for."""

    if not rows:
        return 0.0
    return sum(1 for row in rows if row["first_order_date"]) / len(rows)


def next_review(context, receipts):
    """The next lot of files: the accounts that took the offer."""

    return {"week": 1, "band": 5.0, "above_share": 1.0, "files": 60}
