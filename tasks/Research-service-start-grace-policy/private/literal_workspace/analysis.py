"""What the grace window costs, off the flag ledger.

Accounts we started the same day against accounts we started inside the grace
window, escalations counted over the twenty-eight days after the flag, the
difference of the two rates, the usual band around it, and a sheet that puts
the slots that are left on held accounts.
"""

from datetime import date, timedelta
from math import sqrt

SIDES = ("same_day", "grace")


def analyze(context, receipts):
    horizon = int(context["escalation_window_days"])
    window = int(context["grace_window_days"])
    counted = {side: 0 for side in SIDES}
    escalated = {side: 0 for side in SIDES}
    for row in context["flags"]:
        started = str(row["start_date"])
        if not started:
            continue
        waited = days_between(str(row["flag_date"]), started)
        if waited == 0:
            side = "same_day"
        elif waited <= window:
            side = "grace"
        else:
            continue
        counted[side] += 1
        escalation = str(row["escalation_date"])
        if escalation and days_between(str(row["flag_date"]), escalation) <= horizon:
            escalated[side] += 1
    rate = {side: escalated[side] / counted[side] for side in SIDES}
    cost = (rate["grace"] - rate["same_day"]) * 100.0
    error = sqrt(
        sum(rate[side] * (1.0 - rate[side]) / counted[side] for side in SIDES)
    ) * 100.0
    return {
        "cost_points": cost,
        "cost_range_points": [cost - 1.96 * error, cost + 1.96 * error],
        "account_days": None,
        "weeks": [],
    }


def days_between(first, last):
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def next_collection(context, receipts):
    """All the slots that are left, on held accounts."""

    return {
        "segment": "all",
        "hold_share": 1.0,
        "slots": int(context["capacity"]["slots_per_week"]),
    }
