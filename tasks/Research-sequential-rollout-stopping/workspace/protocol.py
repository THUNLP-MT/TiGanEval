"""How the watch notebook is called and what it hands back.

This module ships with the growth reporting stack. The watch tool and the
weekly review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, ledger)` returns the readout:

    {
      "lift_points": ...,
      "lift_interval_points": [low, high],
      "decision": "ship" or "continue",
      "measurements": [{"call_id": ..., "share_pct": ..., "days": ...,
                        "share_day_points": ...}, ...]
    }

* `lift_points` is a difference in fourteen-day reorder written in reorder
  points, the same units as `ship_line_points`: 1.4 reads as one and four
  tenths of a point.
* `lift_interval_points` is two endpoints in those units, low first.
* `decision` is `"ship"` or `"continue"`.
* `measurements` is a list of entries, each with a `call_id`, a `share_pct`, a
  `days` and a `share_day_points` number.

`analysis.next_collection(context, ledger)` returns what to book next from the
traffic service: `{"share_pct": 30, "days": 18, "hold_ramp": true}`, or
`"stop"`. `{"booking": {...}}` and `{"action": "stop"}` wrappers are read the
same way. A list means the growth team may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"1.35"`, or exact
rational strings such as `"27/20"`. Days, shares, call ids and the decision are
identities and are never read as numbers. Extra descriptive keys are ignored,
and an interval may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `watch_context.json`: the window, the line the
watch is judged against, the reorder window, the share cap and its review day,
the topic the reorder events are published on, the archive of looks, the
share-day grant, the audience roll-up, the enrolment snapshot, the reorder
publications and the ingestion receipts. `ledger` is the list of booking
receipts in `collection_ledger.json`, oldest first; each has a `call_id`, the
`share_pct`, `days` and `hold_ramp` it was served with, the `share_day_points`
it cost, the day it was served from, the topic counters over its days and the
enrolments it brought in by session count. Fields beyond those are service
transport.
"""

from fractions import Fraction
from math import isfinite


ARMS = ("control", "treatment")


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
                "call_id": item.get("call_id"),
                "share_pct": number(item.get("share_pct")),
                "days": number(item.get("days")),
                "share_day_points": number(item.get("share_day_points")),
            }
        )
    return rows


def report_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    decision = value.get("decision")
    if isinstance(decision, dict):
        decision = decision.get("action", decision.get("decision"))
    if isinstance(decision, list) and len(decision) == 1:
        decision = decision[0]
    return {
        "lift_points": number(value.get("lift_points")),
        "lift_interval_points": interval(value.get("lift_interval_points")),
        "decision": decision,
        "measurements": measurements(value.get("measurements")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("booking", value.get("action", value.get("plan")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "share_pct" in value or "days" in value:
            hold_ramp = value.get("hold_ramp", True)
            if not isinstance(hold_ramp, bool):
                return None
            return {
                "share_pct": number(value.get("share_pct")),
                "days": number(value.get("days")),
                "hold_ramp": hold_ramp,
            }
    return None


def plan_view(value):
    """The next-booking answer as a list of tied choices the team may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
