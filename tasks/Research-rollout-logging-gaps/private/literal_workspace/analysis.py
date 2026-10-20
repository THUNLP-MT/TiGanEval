"""Conversion lift for the checkout hint, read off the session table.

Conversion rate per arm over the window, the treated rate minus the control
rate, the usual interval around it, and the rollout call against the gate. The
rest of the archive budget goes into the treated arm, where the sample is
thinnest.
"""

from math import sqrt

ARMS = ("control", "treatment")


def analyze(context, receipts):
    rows = context["sessions_by_day"]
    totals = {}
    for arm in ARMS:
        totals[arm] = {
            "sessions": sum(row["sessions"] for row in rows if row["arm"] == arm),
            "confirmations": sum(row["confirmations"] for row in rows if row["arm"] == arm),
        }
    rate = {
        arm: totals[arm]["confirmations"] / totals[arm]["sessions"] for arm in ARMS
    }
    lift = rate["treatment"] - rate["control"]
    error = sqrt(
        sum(
            rate[arm] * (1 - rate[arm]) / totals[arm]["sessions"]
            for arm in ARMS
        )
    )
    gate = float(read_gate(context["gate"]))
    return {
        "cohort": totals,
        "lift": lift,
        "lift_bounds": [lift - 1.96 * error, lift + 1.96 * error],
        "measurements": [],
        "decision": "expand" if lift > gate else "hold",
    }


def read_gate(value):
    """The gate as a number, whether it is written `0.003` or `3/1000`."""

    if isinstance(value, str) and "/" in value:
        top, bottom = value.split("/")
        return float(top) / float(bottom)
    return float(value)


def next_collection(context, receipts):
    """Buy retained treated slices, because that is where the owner wants the units."""

    left = int(context["archive"]["units_granted"]) - sum(
        int(entry["units"]) for entry in receipts
    )
    if left < int(context["archive"]["unit_cost"]):
        return "stop"
    billed = {(entry["day"], entry["arm"]) for entry in receipts}
    surge_days = [
        entry["day"] for entry in context["changes"] if entry["kind"] == "crawler_surge"
    ]
    if not surge_days:
        return "stop"
    retained = str(context["archive"]["retained_from"])
    surge = min(surge_days)
    treated = {}
    for row in context["sessions_by_day"]:
        if (
            row["arm"] == "treatment"
            and row["crawler_rules"] == "off"
            and row["day"] >= retained
            and row["day"] >= surge
        ):
            treated[row["day"]] = treated.get(row["day"], 0) + row["sessions"]
    for day, _size in sorted(treated.items(), key=lambda item: item[1]):
        if (day, "treatment") not in billed:
            return {"day": day, "arm": "treatment"}
    return "stop"
