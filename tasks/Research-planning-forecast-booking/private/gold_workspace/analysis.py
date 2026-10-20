"""The desk's planning notebook: tomorrow's sheet, its range, and the order."""

from support import (
    allowance_left,
    demand,
    half_width,
    next_shift,
    order,
    settlement_lines,
)


def analyze(context, receipts):
    shift = next_shift(context, receipts)
    sheets = demand(context, receipts, shift)
    rows = []
    for area in context["areas"]:
        for window in context["windows"]:
            drops = sheets[(area, window)]
            half = half_width(context, receipts, drops)
            rows.append(
                {
                    "area": area,
                    "window": window,
                    "drops": drops,
                    "drops_range": [drops - half, drops + half],
                }
            )
    total = sum(sheets.values())
    span = half_width(context, receipts, total)
    return {
        "shift_id": shift,
        "demand": rows,
        "shift_total": {"drops": total, "drops_range": [total - span, total + span]},
        "settlements": settlement_lines(receipts),
    }


def next_collection(context, receipts):
    booked = order(context, receipts)
    if not booked:
        return "stop"
    return {
        "booking": [
            {"area": area, "window": window, "vans": vans}
            for (area, window), vans in sorted(booked.items())
        ]
    }
