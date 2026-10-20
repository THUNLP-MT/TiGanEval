"""The month's dispatch board: one window a class, and what the board holds."""

from support import (
    board,
    open_weeks,
    stream_rate,
    units_left,
    visits,
    waiting,
)


def analyze(context, receipts):
    printed = board(context, receipts)
    return {
        "stream_rate": round(stream_rate(context, receipts, printed), 2),
        "windows": printed,
        "visits": visits(receipts),
        "units_left": units_left(context, receipts),
    }


def next_collection(context, receipts):
    """Book the class the board cannot print, while the grant can still pay."""

    terms = context["visits"]
    short = waiting(context, receipts)
    if not short:
        return "stop"
    if units_left(context, receipts) < int(terms["units_per_visit"]):
        return "stop"
    for job_class in short:
        weeks = open_weeks(context, receipts, job_class)
        if weeks:
            return {
                "job_class": job_class,
                "week": weeks[0],
                "jobs": int(terms["jobs_per_visit"]),
            }
    return "stop"
