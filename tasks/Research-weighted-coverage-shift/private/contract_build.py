'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The month's dispatch board, written to the terms the desk agreed."""


def _level_index(count, level):
    """The row the edge sits on, over one row more than the file holds."""

    top = int(round(float(level) * 1000.0)) * (int(count) + 1)
    return -(-top // 1000)


def classes_of(context):
    """Every class the depot dispatched this month, biggest share first."""

    total = 0
    counts = {}
    for row in context["traffic"]:
        counts[str(row["job_class"])] = int(row["jobs_dispatched"])
        total += int(row["jobs_dispatched"])
    return counts, (total or 1)


def pull_stopped(context, job_class):
    """True when the last audit week pulled sheets on the class and got none."""

    last = 0
    pulled = 0
    returned = 0
    for row in context["intake_log"]:
        if str(row["job_class"]) != str(job_class):
            continue
        if int(row["week"]) > last:
            last = int(row["week"])
            pulled = int(row["pulled"])
            returned = int(row["sheets_returned"])
    return pulled > 0 and returned == 0


def rows_for(context, receipts, job_class):
    """The rows that still describe the class, in minutes past the tool."""

    nights = [
        int(row["actual_minutes"]) - int(row["predicted_minutes"])
        for entry in receipts
        for row in entry.get("observed", {}).get("rows", ())
        if str(row["job_class"]) == str(job_class)
    ]
    if pull_stopped(context, job_class):
        return nights
    filed = [
        int(row["actual_minutes"]) - int(row["predicted_minutes"])
        for row in context["sheets"]
        if str(row["job_class"]) == str(job_class)
    ]
    return filed + nights


def edge_for(context, receipts, job_class):
    """Minutes either side of the tool's number, or None when nothing prints."""

    rows = rows_for(context, receipts, job_class)
    if not rows:
        return None
    ranked = sorted(abs(value) for value in rows)
    index = _level_index(len(ranked), context["board"]["hold_rule"])
    if index > len(ranked):
        return None
    edge = int(ranked[index - 1])
    while edge < ranked[index - 1]:
        edge += 1
    if 2 * edge > int(context["board"]["window_limit_minutes"]):
        return None
    return edge


def analyze(context, receipts):
    counts, total = classes_of(context)
    printed = []
    share_held = 0.0
    for job_class in counts:
        edge = edge_for(context, receipts, job_class)
        if edge is None:
            continue
        rows = rows_for(context, receipts, job_class)
        inside = len([value for value in rows if -edge <= value <= edge])
        share_held += (counts[job_class] / total) * (inside / len(rows))
        printed.append(
            {
                "job_class": job_class,
                "window": [-edge, edge],
                "sheets_used": len(rows),
            }
        )
    spent = sum(int(entry["units_charged"]) for entry in receipts)
    return {
        "stream_rate": round(share_held, 2),
        "windows": printed,
        "visits": [
            {
                "receipt_id": entry["receipt_id"],
                "job_class": entry["job_class"],
                "jobs_returned": int(entry["jobs_returned"]),
                "units_charged": int(entry["units_charged"]),
            }
            for entry in receipts
        ],
        "units_left": int(context["visits"]["units_granted"]) - spent,
    }


def next_collection(context, receipts):
    counts, total = classes_of(context)
    terms = context["visits"]
    spent = sum(int(entry["units_charged"]) for entry in receipts)
    if int(terms["units_granted"]) - spent < int(terms["units_per_visit"]):
        return "stop"
    short = [
        job_class
        for job_class in counts
        if edge_for(context, receipts, job_class) is None
    ]
    short.sort(key=lambda name: (-counts[name], name))
    if not short:
        return "stop"
    booked = {}
    for entry in receipts:
        if not entry.get("refusal"):
            booked[int(entry["week"])] = booked.get(int(entry["week"]), 0) + 1
    for job_class in short:
        free = [
            int(week)
            for week in terms["roster"].get(job_class, ())
            if booked.get(int(week), 0) < int(terms["visits_per_week"])
        ]
        if free:
            return {
                "job_class": job_class,
                "week": sorted(free)[0],
                "jobs": int(terms["jobs_per_visit"]),
            }
    return "stop"
'''


SUPPORT = '''"""Nothing lives here in this build; the board is one module."""
'''


FILES = {"analysis.py": REPORT, "support.py": SUPPORT}
