"""How the qualification notebook is called and what it hands back.

This module ships with the reliability reporting tooling. The chamber tool and
the plan review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the report:

    {
      "crossing_bar": ...,
      "crossing_range_bar": [low, high],
      "counted_units": [{"source": ..., "units": ..., "leaks": ...}, ...],
      "sessions": [{"booking_id": ..., "bench": ..., "dwell_min": ...,
                    "units": ..., "leaks": ..., "hours_charged": ...}, ...]
    }

* `crossing_bar` is a pressure in bar.
* `crossing_range_bar` is two pressures in bar, low first.
* `counted_units` says where the units behind the number came from. `source`
  is one of `UNIT_SOURCES`: `"batch_table"` for a unit the qualification batches
  put on a bench, `"receipt"` for one a chamber session returned.
* `sessions` is one entry per chamber session, with the `booking_id` the desk
  wrote, the `bench` and `dwell_min` it ran at, the `units` it returned, the
  `leaks` among them and the `hours_charged`.

`analysis.next_block(context, receipts)` returns the next session to put in
front of the chamber desk:
`{"bench": "B-1", "batch": "B-05", "cartridge": "C-185", "dwell_min": 30,
"units": 6}`, or `"stop"`. `{"session": {...}}` and `{"action": "stop"}`
wrappers are read the same way. A list means the review may take any one of the
entries in it.

Numbers may be JSON numbers, decimal strings such as `"193.4"`, or exact
rational strings such as `"967/5"`. Bench names, batch names, cartridge names,
booking ids and the source words are identities and are never read as numbers.
Extra descriptive keys are ignored, and a range may also be written
`{"low": ..., "high": ...}`.

`context` is the same object as `stress_context.json`: the lot, the family, the
build month, the plan's hold, the fraction the plan is written against, the
console's sticker span, the dead-weight block's own pressure, the cartridges on
the shelf, the benches, when a bench is out of service, the chamber budget, what
the stores hold, the days the scheduler is holding, the bench sheet and the run
table. `receipts` is the list of chamber receipts in `session_receipts.json`,
oldest first; each has a `booking_id`, the `bench`, `batch`, `cartridge`,
`dwell_min` and `units_asked` it was booked with, the `units_returned`, the
`readings_bar` and `results` the chamber gave back, the `block_readings_bar`
the bench wrote for it, the `hours_charged`, the `hours_left_after`, the day it
was `served_on` and a `refusal` line where the desk handed the sheet back.
Fields beyond those are desk transport.
"""

from fractions import Fraction
from math import isfinite


#: The two places a counted unit can have come from.
UNIT_SOURCES = ("batch_table", "receipt")

#: What the console writes in the result column of the run table.
RESULTS = ("leak", "hold")


def number(value):
    """Read one measurement. An identity or an unreadable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def counted_units(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "source": item.get("source"),
                "units": number(item.get("units")),
                "leaks": number(item.get("leaks")),
            }
        )
    return rows


def sessions(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "booking_id": item.get("booking_id"),
                "bench": item.get("bench"),
                "dwell_min": number(item.get("dwell_min")),
                "units": number(item.get("units")),
                "leaks": number(item.get("leaks")),
                "hours_charged": number(item.get("hours_charged")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the reporting tooling passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "crossing_bar": number(value.get("crossing_bar")),
        "crossing_range_bar": interval(value.get("crossing_range_bar")),
        "counted_units": counted_units(value.get("counted_units")),
        "sessions": sessions(value.get("sessions")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("session", value.get("action", value.get("block")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "cartridge" in value or "units" in value:
            return {
                "bench": value.get("bench"),
                "batch": value.get("batch"),
                "cartridge": value.get("cartridge"),
                "dwell_min": number(value.get("dwell_min")),
                "units": number(value.get("units")),
            }
    return None


def plan_view(value):
    """The next-session answer as a list of tied choices the review may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
