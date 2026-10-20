"""How the rollout notebook is called and what it hands back.

This module ships with the programme reporting stack. The wave tool and the
board pack both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "effect_points": ...,
      "effect_range_points": [low, high],
      "metro_days": ...,
      "measurements": [{"receipt_id": ..., "region": ..., "week": ...,
                        "region_weeks_charged": ..., "days_returned": ...}, ...]
    }

* `effect_points` is a difference in on-time share written in on-time points,
  the same units as `board_bar_points`: 1.4 reads as one and four tenths of a
  point, and a positive number means batching helped.
* `effect_range_points` is two endpoints in those units, low first.
* `metro_days` is a whole number of metro-days.
* `measurements` is a list of entries, each with a `receipt_id`, a `region`, a
  `week`, a `region_weeks_charged` and a `days_returned` number.

`analysis.next_collection(context, receipts)` returns the region-week to book
next from the wave board: `{"region": "Fennhaven", "week": "2026-05-11",
"holdback_share": 40}`, or `"stop"`. `{"booking": {...}}` and
`{"action": "stop"}` wrappers are read the same way. A list means the programme
may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"1.35"`, or exact
rational strings such as `"27/20"`. Regions, weeks, receipt ids and the stop
word are identities and are never read as numbers. Extra descriptive keys are
ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `rollout_context.json`: the window, the bar the
board acts inside, the exposure and baseline lengths the programme reads on,
the wave capacity terms, the region book, the rollout register, the daily
export, the order sample and any booked weeks the wave board has served.
`receipts` is the list of wave receipts in `wave_receipts.json`, oldest first;
each has a `receipt_id`, the `region`, `week` and `holdback_share` it was asked
for, the `region_weeks_charged` and `region_weeks_left` the board recorded, the
`days_returned` and `orders_returned` it came back with, and a `refusal` that is
empty when the week was served. Fields beyond those are board transport.
"""

from fractions import Fraction
from math import isfinite


ARMS = ("batched", "held_back")


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


def measurements(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "region": item.get("region"),
                "week": item.get("week"),
                "region_weeks_charged": number(item.get("region_weeks_charged")),
                "days_returned": number(item.get("days_returned")),
            }
        )
    return rows


def report_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "effect_points": number(value.get("effect_points")),
        "effect_range_points": interval(value.get("effect_range_points")),
        "metro_days": number(value.get("metro_days")),
        "measurements": measurements(value.get("measurements")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("booking", value.get("action", value.get("plan")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "region" in value or "week" in value:
            return {
                "region": value.get("region"),
                "week": value.get("week"),
                "holdback_share": number(value.get("holdback_share")),
            }
    return None


def plan_view(value):
    """The next-booking answer as a list of tied choices the programme may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
