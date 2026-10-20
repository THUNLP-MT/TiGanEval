"""Wear rate by supplier, read off the session table.

Mean depth per supplier over the campaign's part sessions, B over A, the usual
two-sample interval around it, and the bench-hours that are left into more
supplier B parts on rig 2, where the B sample is thinnest.
"""

from math import sqrt

SUPPLIERS = ("A", "B")
WANTED_B_SESSIONS = 12


def analyze(context, receipts):
    rows = context["sessions"]
    depth = {
        supplier: [float(row["depth_um"]) for row in rows if row["supplier"] == supplier]
        for supplier in SUPPLIERS
    }
    mean = {supplier: sum(depth[supplier]) / len(depth[supplier]) for supplier in SUPPLIERS}
    spread = {
        supplier: _variance(depth[supplier]) / len(depth[supplier]) for supplier in SUPPLIERS
    }
    ratio = mean["B"] / mean["A"]
    error = ratio * sqrt(
        spread["B"] / mean["B"] ** 2 + spread["A"] / mean["A"] ** 2
    )
    return {
        "wear_rate_ratio": ratio,
        "ratio_range": [ratio - 1.96 * error, ratio + 1.96 * error],
        "sessions_used": {supplier: len(depth[supplier]) for supplier in SUPPLIERS},
        "measurements": [],
    }


def _variance(values):
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def next_collection(context, receipts):
    """More supplier B parts on rig 2, which is the side the review asks about."""

    lots = [lot for lot in context["lots"] if lot["supplier"] == "B"]
    number = {lot["lot"]: int(lot["parts"]) for lot in lots}
    booked = []
    while lots and len(booked) < WANTED_B_SESSIONS:
        for lot in lots:
            if len(booked) >= WANTED_B_SESSIONS:
                break
            number[lot["lot"]] += 1
            booked.append({"rig": 2, "part": f"{lot['lot']}-{number[lot['lot']]:02d}"})
    return booked
