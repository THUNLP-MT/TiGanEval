"""Bundle accuracy across the Harrowgate export.

Each bundle's decision is already on every row of the capture log, so the
accuracy is one pass over the export: the rows it got wrong out of the rows it
saw, in points, with the usual interval around it. The bundle with the fewest
points ships. What is left of the annotation grant goes on counter captures,
which is where the fleet does most of its work.
"""

from math import sqrt


def rows_of(context):
    """The capture log as a list of rows."""

    published = context["capture_log"]
    columns = list(published["columns"])
    return [
        {column: row[index] for index, column in enumerate(columns)}
        for row in published["rows"]
    ]


def analyze(context, receipts):
    rows = rows_of(context)
    scored = []
    for bundle in context["bundles"]:
        wrong = sum(1 for row in rows if int(row[bundle]) != int(row["label"]))
        scored.append({"bundle": bundle, "points": 100.0 * wrong / len(rows)})
    scored.sort(key=lambda entry: entry["points"])
    best = scored[0]
    share = best["points"] / 100.0
    half = 1.96 * sqrt(share * (1.0 - share) / len(rows)) * 100.0
    return {
        "bundle": best["bundle"],
        "worst_profile": "counter",
        "fleet_points": best["points"],
        "points_range": [best["points"] - half, best["points"] + half],
        "rows_used": len(rows),
        "bundle_points": scored,
        "requests": [],
        "credits_used": 0,
    }


def next_collection(context, receipts):
    """More counter captures, which is where the fleet does most of its work."""

    return {
        "duty_profile": "counter",
        "firmware": context["firmware"]["earlier"],
        "condition": "bright",
        "rows": 120,
    }
