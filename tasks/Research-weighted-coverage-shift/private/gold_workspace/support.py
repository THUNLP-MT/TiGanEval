"""Reading a depot's evidence: which rows still describe a class, how wide a
window those rows carry, and how much of the month each class is."""

from math import ceil


def overrun(row):
    return int(row["actual_minutes"]) - int(row["predicted_minutes"])


def shares(context):
    """Each class's share of the jobs the depot dispatched this month."""

    total = sum(int(row["jobs_dispatched"]) for row in context["traffic"]) or 1
    return {
        str(row["job_class"]): int(row["jobs_dispatched"]) / total
        for row in context["traffic"]
    }


def last_week(context):
    return max(int(row["week"]) for row in context["intake_log"])


def stopped(context, job_class):
    """The class whose pull came back empty in the last week of the audit."""

    week = last_week(context)
    return all(
        int(row["sheets_returned"]) == 0
        for row in context["intake_log"]
        if int(row["week"]) == week and str(row["job_class"]) == str(job_class)
    )


def sheet_rows(context, job_class):
    return [
        overrun(row) for row in context["sheets"] if str(row["job_class"]) == str(job_class)
    ]


def night_rows(receipts, job_class):
    return [
        overrun(row)
        for entry in receipts
        for row in entry.get("observed", {}).get("rows", ())
        if str(row["job_class"]) == str(job_class)
    ]


def usable_rows(context, receipts, job_class):
    """The rows that still describe a class.

    A class whose pull stopped returning is described by the nights the audit
    crew has timed itself and by nothing else; the sheets from before the pull
    stopped are about work the class no longer does.
    """

    nights = night_rows(receipts, job_class)
    if stopped(context, job_class):
        return nights
    return sheet_rows(context, job_class) + nights


def cut_index(rows, level):
    """Which row the window's edge sits on.

    The window is printed for a job that is not one of the rows behind it, so
    the level is taken over one row more than the file holds and the edge sits
    a place up.
    """

    return int(ceil(float(level) * (int(rows) + 1)))


def half_width(context, receipts, job_class):
    """The tightest window a class's own rows carry, or None when they cannot."""

    rows = sorted(abs(value) for value in usable_rows(context, receipts, job_class))
    level = float(context["board"]["hold_rule"])
    index = cut_index(len(rows), level)
    if not rows or index > len(rows):
        return None
    edge = int(ceil(rows[index - 1]))
    if 2 * edge > int(context["board"]["window_limit_minutes"]):
        return None
    return edge


def board(context, receipts):
    """One entry per class the rows on file can print a window for."""

    printed = []
    for job_class in shares(context):
        edge = half_width(context, receipts, job_class)
        if edge is None:
            continue
        printed.append(
            {
                "job_class": job_class,
                "window": [-edge, edge],
                "sheets_used": len(usable_rows(context, receipts, job_class)),
            }
        )
    return printed


def held_share(context, receipts, job_class, low, high):
    rows = usable_rows(context, receipts, job_class)
    if not rows:
        return None
    return sum(1 for value in rows if low <= value <= high) / len(rows)


def stream_rate(context, receipts, printed):
    """The share of the month's dispatched jobs the printed windows hold.

    Every class the depot dispatched counts, in the proportions the traffic
    report gives. A class with no window on the board holds none of its jobs.
    """

    weights = shares(context)
    total = 0.0
    for entry in printed:
        low, high = entry["window"]
        share = held_share(context, receipts, entry["job_class"], low, high)
        if share is None:
            continue
        total += weights.get(entry["job_class"], 0.0) * share
    return total


def units_spent(receipts):
    return sum(int(entry["units_charged"]) for entry in receipts)


def units_left(context, receipts):
    return int(context["visits"]["units_granted"]) - units_spent(receipts)


def visits(receipts):
    return [
        {
            "receipt_id": entry["receipt_id"],
            "job_class": entry["job_class"],
            "jobs_returned": int(entry["jobs_returned"]),
            "units_charged": int(entry["units_charged"]),
        }
        for entry in receipts
    ]


def visits_in_week(receipts, week):
    return sum(
        1
        for entry in receipts
        if int(entry["week"]) == int(week) and not entry.get("refusal")
    )


def waiting(context, receipts):
    """The classes with no window, biggest share of the month first."""

    weights = shares(context)
    short = [
        job_class
        for job_class in weights
        if half_width(context, receipts, job_class) is None
    ]
    return sorted(short, key=lambda name: (-weights[name], name))


def open_weeks(context, receipts, job_class):
    terms = context["visits"]
    return [
        int(week)
        for week in terms["roster"].get(job_class, ())
        if visits_in_week(receipts, week) < int(terms["visits_per_week"])
    ]
