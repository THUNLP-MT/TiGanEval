"""What batching did to on-time delivery across Halcombe, off the daily export.

On-time rate per metro-day from `region_daily.csv`, a metro term and a week term
fitted to it, and the coefficient on whether the metro was live that day. The
range around it is the usual one. The wave capacity that is left goes on the
biggest metros already running batching, since those are the ones the board asks
about.
"""

from math import sqrt

BATCHING = "live"


def rows_of(context):
    """One row per metro-day: the printed rate, the metro, the week, live or not."""

    live = {
        str(item["region"]): str(item["live_from"] or "")
        for item in context["register"]
    }
    out = []
    for row in context["daily"]:
        region = str(row["region"])
        day = str(row["date"])
        started = live.get(region) or ""
        out.append(
            {
                "region": region,
                "week": day[:7] + "-" + str((int(day[8:10]) - 1) // 7),
                "rate": float(row["ontime_orders"]) / float(row["orders"]),
                "live": 1.0 if started and day >= started else 0.0,
                "orders": float(row["orders"]),
            }
        )
    return out


def headline(rows):
    """On-time on the metros running batching, against the ones not live yet."""

    out = {}
    for flag, label in ((1.0, "batching"), (0.0, "not_live")):
        wanted = [row for row in rows if row["live"] == flag]
        orders = sum(row["orders"] for row in wanted)
        out[label] = 100.0 * sum(row["rate"] * row["orders"] for row in wanted) / orders
    return out


def _demean(rows, values, keys):
    """Take the group means out of a column, one grouping at a time."""

    for _ in range(400):
        moved = 0.0
        for key in keys:
            totals = {}
            for row, value in zip(rows, values):
                entry = totals.setdefault(row[key], [0.0, 0])
                entry[0] += value
                entry[1] += 1
            for index, row in enumerate(rows):
                total, count = totals[row[key]]
                mean = total / count
                values[index] -= mean
                moved += abs(mean)
        if moved < 1e-12:
            break
    return values


def fit(rows):
    """The coefficient on being live, with a metro term and a week term taken out."""

    y = _demean(rows, [row["rate"] for row in rows], ("region", "week"))
    x = _demean(rows, [row["live"] for row in rows], ("region", "week"))
    denominator = sum(value * value for value in x)
    slope = sum(a * b for a, b in zip(x, y)) / denominator
    residual = [a - slope * b for a, b in zip(y, x)]
    spread = sum(value * value for value in residual) / max(1, len(rows) - len(rows) // 8)
    return slope * 100.0, sqrt(spread / denominator) * 100.0


def analyze(context, receipts):
    rows = rows_of(context)
    effect, error = fit(rows)
    return {
        "effect_points": effect,
        "effect_range_points": [effect - 1.96 * error, effect + 1.96 * error],
        "metro_days": sum(1 for row in rows if row["live"]),
        "measurements": [],
    }


def next_collection(context, receipts):
    """The three biggest metros already on batching, for the first week we have."""

    week = str(context["capacity"]["bookable_weeks"][0])
    live = [
        row for row in context["register"] if str(row["live_from"] or "")
    ]
    live.sort(key=lambda row: -int(row["orders_per_day"]))
    return [
        {"region": str(row["region"]), "week": week, "holdback_share": 0}
        for row in live[:3]
    ]
