"""How long an EM-9 holds at the field drive, off the March soak export.

Loss for each bench row against the row the module opened at, pooled on the
`elapsed_h` column, a straight line through log loss against log hours, and the
hours where that line reaches a tenth. The range comes off how far the rows sit
from the line. The days that are left go on more 1.7 A ports, which is where
the loss is.
"""

from math import exp, log

TARGET = 0.10
LAW = "defect_growth"


def analyze(context, receipts):
    points = rows(context)
    slope, intercept = straight_line(points)
    hours = exp((log(TARGET) - intercept) / slope)
    spread = 2.0 * scatter(points, slope, intercept) / abs(slope)
    return {
        "hours_to_loss": hours,
        "hours_range": [hours * exp(-spread), hours * exp(spread)],
        "standing_laws": [LAW],
        "counted_rows": [],
        "blocks": [],
    }


def rows(context):
    """(log hours, log loss) for every bench row, against the row it opened at."""

    opening = {}
    for row in context["traces"]:
        name = row["module_id"]
        if name == context["reference_module_id"]:
            continue
        if name not in opening or float(row["elapsed_h"]) < opening[name][0]:
            opening[name] = (float(row["elapsed_h"]), float(row["output_mw"]))
    points = []
    for row in context["traces"]:
        name = row["module_id"]
        if name not in opening:
            continue
        hours = float(row["elapsed_h"])
        if hours <= 0:
            continue
        loss = 1.0 - float(row["output_mw"]) / opening[name][1]
        if loss <= 0.0:
            # nothing has come off this one yet; it says nothing about the slope
            continue
        points.append((log(hours), log(loss)))
    return points


def straight_line(points):
    """Least squares through log loss against log hours."""

    count = len(points)
    mean_x = sum(x for x, _y in points) / count
    mean_y = sum(y for _x, y in points) / count
    top = sum((x - mean_x) * (y - mean_y) for x, y in points)
    bottom = sum((x - mean_x) ** 2 for x, _y in points)
    slope = top / bottom
    return slope, mean_y - slope * mean_x


def scatter(points, slope, intercept):
    """How far the rows sit from the line, in log loss."""

    return (
        sum((y - (intercept + slope * x)) ** 2 for x, y in points) / len(points)
    ) ** 0.5


def next_block(context, receipts):
    """The days that are left go on more 1.7 A ports, where the loss is."""

    lot = sorted(context["spares"])[0]
    return {
        "drive_a": 1.7,
        "case_temp_c": context["hold_temp_c"],
        "ports": min(int(context["budget"]["ports_per_block"]), context["spares"][lot]),
        "chamber_days": int(context["budget"]["days_per_block"]),
        "lot": lot,
    }
