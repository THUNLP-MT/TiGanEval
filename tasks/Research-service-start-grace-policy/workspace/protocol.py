"""How the desk notebook is called and what it hands back.

This module ships with the support reporting stack. The desk tool and the
quarterly review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "cost_points": ...,
      "cost_range_points": [low, high],
      "account_days": ...,
      "weeks": [{"receipt_id": ..., "slots_charged": ..., "rows_returned": ...}, ...]
    }

* `cost_points` is a difference in twenty-eight day escalation risk written in
  points: 1.4 reads as one and four tenths of a point. Held minus same-day, so a
  positive number means the wait costs something.
* `cost_range_points` is two endpoints in those units, low first.
* `account_days` is how many account-days of watching the number was worked out
  over, both sides together.
* `weeks` is a list of entries, each with a `receipt_id`, a `slots_charged` and
  a `rows_returned` number.

`analysis.next_collection(context, receipts)` returns the week to book next from
the desk: `{"segment": "all", "hold_share": 0.5, "slots": 40}`, or `"stop"`.
`{"booking": {...}}` and `{"action": "stop"}` wrappers are read the same way. A
list means the desk may take any one of the entries in it. A `week` key is the
week you mean and is carried onto the receipt; the desk serves the next open
week either way.

Numbers may be JSON numbers, decimal strings such as `"1.35"`, or exact rational
strings such as `"27/20"`. Receipt ids and the segment are identities and are
never read as numbers. Extra descriptive keys are ignored, and a range may also
be written `{"low": ..., "high": ...}`.

`context` is the same object as `desk_context.json`: the window, the
twenty-eight day question, the grace window the desk works to, what the review
asked for, the desk's capacity terms, where the export stops and how late a
record lands, the desk's own book, the weeks of the window, the flag ledger and
the account-state log. `receipts` is the list of booking receipts in
`booking_receipts.json`, oldest first; each has a `receipt_id`, the `segment`,
`hold_share` and `slots_asked` it was called with, the `slots_charged`, the
`rows_returned` and `accounts_started` it came back with, and a `refusal` line
that is empty when the desk took the week. Fields beyond those are service
transport.
"""

from fractions import Fraction
from math import isfinite


QUEUES = ("same_day", "next_slot")


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


def weeks(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "slots_charged": number(item.get("slots_charged")),
                "rows_returned": number(item.get("rows_returned")),
            }
        )
    return rows


def report_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "cost_points": number(value.get("cost_points")),
        "cost_range_points": interval(value.get("cost_range_points")),
        "account_days": number(value.get("account_days")),
        "weeks": weeks(value.get("weeks")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("booking", value.get("action", value.get("plan")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "segment" in value or "slots" in value or "hold_share" in value:
            return {
                "segment": value.get("segment", "all"),
                "hold_share": number(value.get("hold_share")),
                "slots": number(value.get("slots")),
                "week": number(value.get("week")),
            }
    return None


def plan_view(value):
    """The next-week answer as a list of tied choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
