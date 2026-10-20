'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The Northgate readout, written to the terms the council set."""

from datetime import date
from math import sqrt


#: One time in twenty shared out over the markets the slide carries.
_POINTS = {1: 1.959964, 2: 2.241403, 3: 2.393980, 4: 2.497705, 5: 2.575829,
           6: 2.638257, 7: 2.690203, 8: 2.734368, 9: 2.772807, 10: 2.807034}


def _day(value):
    return date.fromisoformat(str(value)).toordinal()


def _run_score(row, refreshed, cut):
    """The score the run read on the morning it decided this account."""

    entry = refreshed.get(str(row["account_id"]))
    if entry is not None and row["offer_date"] and entry[0] > str(row["offer_date"]):
        return entry[1]
    return float(row["standing_score"])


def _decided(context, receipts):
    """Every account the line decided, with its orders and its days at risk."""

    cut = float(context["cut"])
    refreshed = {}
    for row in context["recompute"]:
        refreshed[str(row["account_id"])] = (str(row["refresh_date"]), float(row["score_before"]))
    reviewed = {}
    for entry in receipts:
        for item in entry.get("files") or ():
            reviewed[str(item["account_id"])] = item
    out = []
    for row in context["register"]:
        if str(row["run_status"]) != "scored":
            continue
        score = _run_score(row, refreshed, cut)
        if score < cut - 5.0 or score > cut + 5.0:
            continue
        # The credit test runs on `score`, the one the run read, and not on the
        # register's `standing_score`: same score as the side and the band.
        credit = float(row["credits_filed"])
        if credit > 0 and score >= cut and score - credit < cut:
            continue
        watched = reviewed.get(str(row["account_id"]), row)
        start = _day(row["offer_date"])
        if watched["first_order_date"]:
            out.append((score >= cut, 1, _day(watched["first_order_date"]) - start))
        else:
            out.append((score >= cut, 0, _day(watched["last_observed_date"]) - start))
    return out


def _side(rows, above, window):
    """This side's orders, its account-days, and its chance of one in sixty days.

    A day at this side's rate passes without an order with the rest of the
    chance; sixty of them in a row is what it takes to see none, and what is
    left over is the share of accounts that order at least once.
    """

    orders = sum(order for over, order, _days in rows if over is above)
    days = sum(held for over, _order, held in rows if over is above)
    if days <= 0:
        return orders, days, 0.0
    return orders, days, 1.0 - (1.0 - orders / days) ** window


def analyze(context, receipts):
    window = int(context["order_window_days"])
    rows = _decided(context, receipts)
    over = _side(rows, True, window)
    under = _side(rows, False, window)
    multiplier = _POINTS[max(1, min(10, int(context["council"]["markets_on_the_slide"])))]
    spread = 0.0
    for orders, days, _chance in (over, under):
        if orders and days:
            daily = orders / days
            moves = window * (1.0 - daily) ** (window - 1)
            spread += (moves * daily) ** 2 / orders
    half = 100.0 * multiplier * sqrt(spread)
    effect = 100.0 * (over[2] - under[2])
    return {
        "offer_effect_points": effect,
        "effect_range_points": [effect - half, effect + half],
        "account_days": over[1] + under[1],
        "lots": [
            {
                "receipt_id": entry["receipt_id"],
                "files_charged": entry["files_charged"],
                "rows_returned": entry["rows_returned"],
            }
            for entry in receipts
        ],
    }


def _thickest_week(context, receipts):
    """The first balanced run week that can still add observed account-days."""

    cut = float(context["cut"])
    refreshed = {}
    for row in context["recompute"]:
        refreshed[str(row["account_id"])] = (str(row["refresh_date"]), float(row["score_before"]))
    reviewed = {
        str(item["account_id"])
        for entry in receipts
        for item in entry.get("files") or ()
    }
    today = _day(context["as_of"])
    window = int(context["order_window_days"])
    tally = {}
    for row in context["register"]:
        if str(row["run_status"]) != "scored":
            continue
        score = _run_score(row, refreshed, cut)
        if abs(score - cut) > 5.0:
            continue
        if str(row["account_id"]) in reviewed or row["first_order_date"]:
            continue
        through = min(today, _day(row["offer_date"]) + window)
        if through <= _day(row["last_observed_date"]):
            continue
        pair = tally.setdefault(int(row["run_week"]), [0, 0])
        pair[0 if score >= cut else 1] += 1
    best, thickest = None, 0
    for week in sorted(tally):
        both = min(tally[week])
        if both > thickest:
            best, thickest = week, both
    return best


def next_review(context, receipts):
    grant = context["review_grant"]
    left = int(grant["files_granted"]) - sum(int(item["files_charged"]) for item in receipts)
    if left < int(grant["smallest_lot"]):
        return "stop"
    low, high = analyze(context, receipts)["effect_range_points"]
    if high - low <= float(context["council"]["range_bar_points"]):
        return "stop"
    week = _thickest_week(context, receipts)
    if week is None:
        return "stop"
    return {
        "week": week,
        "band": 5.0,
        "above_share": 0.5,
        "files": min(int(grant["files_per_booking"]), left),
    }
'''


SUPPORT = '''"""Nothing lives here in this build; the readout is one module."""
'''


FILES = {"analysis.py": REPORT, "support.py": SUPPORT}
