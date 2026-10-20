"""How the study notebook's two answers are read. No analysis lives here.

`analyze(context, receipts)` returns an object with

    sessions: {session id: {cells: whole number,
                            channel_hours: number,
                            retirement_cycles: {cell id: cycle}}}
              one entry for every session the receipts hold, and one cycle for
              every cell those sessions ran;
    qualification_difference: number, or null;
    difference_range: [lower, upper];
    decision: "switch", "keep", or null.

`next_collection(context, receipts)` returns {bay, protocol, cells}, or "stop".
A list of bookings means any one of them will do, and every entry in it has to
stand on its own; the same holds for a list of decisions.

Numbers may be written as ordinary numbers, as exact fractions such as "3/2",
or as decimal strings. Identifiers -- session ids, cell ids, bay names,
protocol names, decisions -- keep their own text and are never read as
numbers. A range may also be written as {lower, upper}, a decision as
{action: ...}, and a booking as {booking: ...}; extra descriptive keys
alongside them are ignored. A value that is not a finite number is not a
measurement.

A context carries the campaign, the rated capacity and the retirement
fraction, the cycle spacing of the capacity checks, the certified reference
cell, the rack with each bay's channels and setpoint, the temperature the
qualification build runs at, the cycles the programme requires before it
requalifies, the lot certificate's cycle-life window, the fixture size, the
channel-hour price and balance, and the firmware the tester is on today.

A receipt is one session the campaign paid for: its session id, start date,
firmware, protocol, the channels it occupied, the temperature its chamber's
trace reported, the reference cell reading taken at the start of it, the
cycles it ran, its channel hours and the balance left after it, and under
`observed` one entry per cell with the cell id, its channel and its capacity
checks as [cycle, amp-hours] pairs.
"""

from fractions import Fraction
from math import isfinite


def measurement(value):
    """Read one number. An identifier or an unusable display comes back as it is."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if isinstance(value, int) or isfinite(value) else None
    if not isinstance(value, str):
        return None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def interval(value):
    if isinstance(value, dict):
        value = [value.get("lower"), value.get("upper")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [measurement(value[0]), measurement(value[1])]
    return None


def _named(value, *keys):
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return value[key]
    return value


def choices(value, *keys):
    """One answer or several tied ones, as a list of plain answers."""

    value = _named(value, *keys)
    if isinstance(value, (list, tuple)):
        return [_named(item, *keys) for item in value]
    return [] if value is None else [value]


def booking(value):
    """One next booking, or several tied ones, or the word that stops."""

    offered = []
    for item in choices(value, "booking", "collection", "plan"):
        if isinstance(item, str):
            offered.append(item)
        elif isinstance(item, dict):
            offered.append({
                "bay": item.get("bay"),
                "protocol": item.get("protocol"),
                "cells": measurement(item.get("cells")),
            })
        else:
            offered.append(item)
    return offered


def _sessions(value):
    if isinstance(value, (list, tuple)):
        value = {
            str(entry.get("session_id")): entry
            for entry in value
            if isinstance(entry, dict) and entry.get("session_id") is not None
        }
    if not isinstance(value, dict):
        return None
    read = {}
    for session_id, entry in value.items():
        if not isinstance(entry, dict):
            read[str(session_id)] = None
            continue
        cycles = entry.get("retirement_cycles")
        read[str(session_id)] = {
            "cells": measurement(entry.get("cells")),
            "channel_hours": measurement(entry.get("channel_hours")),
            "retirement_cycles": (
                {str(cell): measurement(cycle) for cell, cycle in cycles.items()}
                if isinstance(cycles, dict) else None
            ),
        }
    return read


def study_view(value):
    """The four answers, read out of whatever shape the notebook returned them in."""

    if not isinstance(value, dict):
        return {"sessions": None, "qualification_difference": None,
                "difference_range": None, "decision": []}
    difference = value.get("qualification_difference")
    return {
        "sessions": _sessions(value.get("sessions")),
        "qualification_difference": None if difference is None else measurement(difference),
        "difference_range": interval(value.get("difference_range")),
        "decision": choices(value.get("decision"), "action", "decision"),
    }
