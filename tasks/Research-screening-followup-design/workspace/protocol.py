"""How the review reads the notebook's two answers. No analysis lives here.

This module ships with the bench's reporting tooling. The rig tool and the
design review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns

    {
      "plate": the part the report is about,
      "effect_K": a number in K,
      "effect_range_K": [low, high] in K, low first,
      "measurements": [{"receipt_id": ..., "day_id": ...,
                        "runs_returned": ...}, ...]
    }

* `effect_K` is in kelvin: how much lower the module's case temperature rise
  sits with that plate than with the part the module ships with today.
* `effect_range_K` is two endpoints in the same kelvin, low first.
* `measurements` is a list of entries, each naming a `receipt_id`, the `day_id`
  it covers and the `runs_returned` on it.

`analysis.next_collection(context, receipts)` returns the sheet for the next
rig day, `{"day": [{"part": "P-07", "runs": 3}, ...]}`, or `"stop"`. A bare
list of entries is read as a day sheet, `{"booking": ...}` and
`{"action": "stop"}` wrappers are read the same way, and a list of sheets means
the desk may take any one of them.

Numbers may be JSON numbers, decimal strings such as `"1.25"`, or exact
rational strings such as `"5/4"`. Part ids, plate ids, day ids and receipt ids
are identities and are never read as numbers. Extra descriptive keys are
ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `screen_context.json`: the campaign, the plate
list and which plate the review is about, the stored incumbent number and the
day it was read, the screen table run by run, the rig log, the booking terms
and the review's own note. `receipts` is the list in `bench_receipts.json`,
oldest first; each carries a `receipt_id`, the `day_id` the rig gave it, the
day's coolant set point and ambient, the rig hours it was charged, the rig days
left after it, a `refusal` line when the desk handed the sheet back, and under
`parts` one entry per part on the sheet with its slot, its fixture, the runs
asked for, the runs returned and each returned run's `rise_K`.
"""

from fractions import Fraction
from math import isfinite


def number(value):
    """Read one measurement. An identity or an unusable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def endpoints(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def lines(value):
    if not isinstance(value, list):
        return None
    read = []
    for item in value:
        if not isinstance(item, dict):
            return None
        read.append(
            {
                "receipt_id": item.get("receipt_id"),
                "day_id": item.get("day_id"),
                "runs_returned": number(item.get("runs_returned")),
            }
        )
    return read


def report_view(value):
    """One delivered report in the shape the review reads it in."""

    if not isinstance(value, dict):
        return {"plate": None, "effect_K": None, "effect_range_K": None, "measurements": None}
    return {
        "plate": value.get("plate"),
        "effect_K": number(value.get("effect_K")),
        "effect_range_K": endpoints(value.get("effect_range_K")),
        "measurements": lines(value.get("measurements")),
    }


def _entry(item):
    if not isinstance(item, dict):
        return None
    part = item.get("part", item.get("plate_id"))
    runs = number(item.get("runs", item.get("run_count")))
    if not isinstance(part, str) or runs is None:
        return None
    return {"part": part, "runs": runs}


def _unwrap(value):
    while isinstance(value, dict):
        inner = None
        for key in ("day", "booking", "sheet", "action", "plan"):
            if key in value:
                inner = value[key]
                break
        if inner is None or inner is value:
            return value
        value = inner
    return value


def _sheet(value):
    """One day sheet: a word such as "stop", or a list of {part, runs} entries."""

    value = _unwrap(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        entry = _entry(value)
        return [entry] if entry is not None else None
    if isinstance(value, (list, tuple)):
        read = [_entry(item) for item in value]
        return read if read and all(item is not None for item in read) else None
    return None


def plan_view(value):
    """The next rig day as a list of sheets the desk may take any one of."""

    read = _sheet(value)
    if read is not None:
        return [read]
    inner = _unwrap(value)
    if isinstance(inner, (list, tuple)) and inner:
        offered = [_sheet(item) for item in inner]
        if all(item is not None for item in offered):
            return offered
    return [None]
