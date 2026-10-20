"""Fourteen-day reorder lift for one-tap reorder, read off the weekly tables.

Reorder rate per arm over the users the job has finished measuring, treated
minus control, the usual interval around it, and the call against the line the
charter set. The share-day points that are left go into more traffic on the new
experience, which is the smaller of the two sides.
"""

from datetime import date, timedelta
from math import sqrt

ARMS = ("control", "treatment")


def analyze(context, ledger):
    finished = finished_through(context)
    users = {arm: 0 for arm in ARMS}
    reorders = {arm: 0 for arm in ARMS}
    for row in context["enrolment"]:
        if row["day"] <= finished:
            users[row["arm"]] += row["users"]
    for row in context["reorders"]:
        if row["enrolled_on"] <= finished:
            reorders[row["arm"]] += row["reorders"]
    rate = {arm: reorders[arm] / users[arm] for arm in ARMS}
    lift = (rate["treatment"] - rate["control"]) * 100.0
    error = sqrt(sum(rate[arm] * (1.0 - rate[arm]) / users[arm] for arm in ARMS)) * 100.0
    line = float(context["ship_line_points"])
    return {
        "lift_points": lift,
        "lift_interval_points": [lift - 1.96 * error, lift + 1.96 * error],
        "decision": "ship" if lift > line else "continue",
        "measurements": [],
    }


def finished_through(context):
    """The last enrolment day whose fourteen-day window is over."""

    as_of = date.fromisoformat(context["as_of"])
    return (as_of - timedelta(days=int(context["reorder_window_days"]))).isoformat()


def next_collection(context, ledger):
    """All the traffic we can get onto the new experience, for one more week."""

    return {"share_pct": 100, "days": 7, "hold_ramp": True}
