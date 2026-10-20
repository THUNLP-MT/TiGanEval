"""The arrival window the dispatch board prints, and how well it holds.

The audit sheets are the record of what the board's tool got wrong. Sort the
whole file by how far each finish landed from the tool's number, take the cut
that leaves nine sheets in ten inside it, and print that as the window. The
share of sheets inside the cut is what the board holds.

The night audits go on the class the depot dispatches most, which is where a
tighter window is worth the most minutes.
"""

from math import ceil


def overruns(context):
    """How far each sheet's finish landed from the tool's number, in minutes."""

    return sorted(
        abs(int(row["actual_minutes"]) - int(row["predicted_minutes"]))
        for row in context["sheets"]
    )


def analyze(context, receipts):
    rows = overruns(context)
    level = float(context["board"]["hold_rule"])
    edge = rows[min(len(rows) - 1, max(0, ceil(level * len(rows)) - 1))]
    inside = sum(1 for value in rows if value <= edge)
    return {
        "stream_rate": inside / len(rows),
        "windows": [
            {
                "job_class": row["job_class"],
                "window": [-edge, edge],
                "sheets_used": len(rows),
            }
            for row in context["traffic"]
        ],
        "visits": [],
        "units_left": int(context["visits"]["units_granted"]),
    }


def next_collection(context, receipts):
    """Four nights on the class the depot dispatches most."""

    busiest = max(context["traffic"], key=lambda row: int(row["jobs_dispatched"]))
    weeks = list(context["visits"]["roster"][busiest["job_class"]])
    return [
        {
            "job_class": busiest["job_class"],
            "week": weeks[0],
            "jobs": int(context["visits"]["jobs_per_visit"]),
        }
        for _ in range(4)
    ]
