"""Tomorrow's sheet off the newest rows on both engines, at eighteen a van.

Both sheets carry an `as_of_shift`, so the rows for tomorrow are the ones
stamped tomorrow. Add the two areas up window by window, put the range around
each number off how far the meter has come off the sheet on the shifts already
settled, and order the vans the number asks for. The weekly pack also wants a line for
every order the carrier has charged the desk for, so the ledger goes out
with it as it stands.
"""

from math import sqrt

DROPS_PER_VAN = 18

SHEETS = (("Harbour", "harbour_rows"), ("Ridge", "ridge_rows"))


def next_shift(context, receipts):
    done = {entry["shift_id"] for entry in receipts if not entry.get("refusal")}
    for shift in context["shifts"]:
        if shift not in done:
            return shift
    return context["shifts"][-1]


def sheet_for(context, shift):
    """Both engines' rows stamped that shift, added up by area and window."""

    totals = {
        (area, window): 0.0
        for area, _key in SHEETS
        for window in context["windows"]
    }
    for area, key in SHEETS:
        for row in context[key]:
            if str(row["as_of_shift"]) == str(shift):
                totals[(area, str(row["window"]))] += float(row["drops_fcst"])
    return totals


def spread(context, receipts):
    """How far the meter has come off the sheet, over every window settled."""

    misses = []
    for entry in receipts:
        if entry.get("refusal"):
            continue
        sheet = sheet_for(context, entry["shift_id"])
        for line in entry["lines"]:
            key = (line["area"], line["window"])
            if sheet.get(key) and line.get("drops_metered") is not None:
                misses.append(float(line["drops_metered"]) / sheet[key] - 1.0)
    if len(misses) < 2:
        return 0.0, 1
    mean = sum(misses) / len(misses)
    deviation = sqrt(sum((miss - mean) ** 2 for miss in misses) / (len(misses) - 1))
    return deviation, len(misses)


def analyze(context, receipts):
    shift = next_shift(context, receipts)
    totals = sheet_for(context, shift)
    deviation, count = spread(context, receipts)
    rows = []
    for area in context["areas"]:
        for window in context["windows"]:
            drops = totals[(area, window)]
            half = 2.0 * deviation * drops / sqrt(count)
            rows.append(
                {
                    "area": area,
                    "window": window,
                    "drops": drops,
                    "drops_range": [drops - half, drops + half],
                }
            )
    total = sum(totals.values())
    half = 2.0 * deviation * total / sqrt(count)
    return {
        "shift_id": shift,
        "demand": rows,
        "shift_total": {"drops": total, "drops_range": [total - half, total + half]},
        "settlements": [
            {
                "order_id": entry["order_id"],
                "shift_id": entry["shift_id"],
                "van_hours_charged": entry["van_hours_charged"],
            }
            for entry in receipts
        ],
    }


def next_collection(context, receipts):
    shift = next_shift(context, receipts)
    totals = sheet_for(context, shift)
    return {
        "booking": [
            {
                "area": area,
                "window": window,
                "vans": max(1, int(round(totals[(area, window)] / DROPS_PER_VAN))),
            }
            for area in context["areas"]
            for window in context["windows"]
        ]
    }
