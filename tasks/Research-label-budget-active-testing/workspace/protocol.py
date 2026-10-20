"""How the review notebook is called and what it hands back.

This module ships with the board's reporting stack. The review tool and the
board pack both read a notebook through it, so it stays as it is.

`analysis.analyze(context, ledger)` returns the report:

    {
      "misroute_rate": ...,
      "misroute_rate_range": [low, high],
      "label_purchases": [{"receipt_id": ..., "session_id": ...,
                           "item_id": ..., "price_credits": ...}, ...],
      "credits_spent": ...
    }

* `misroute_rate` is a share of tickets: `0.18` reads as eighteen in a
  hundred.
* `misroute_rate_range` is two endpoints in those units, low first.
* `label_purchases` is a list of entries, each with a `receipt_id`, a
  `session_id`, an `item_id` and a `price_credits` number.
* `credits_spent` is a number of credits.

`analysis.next_collection(context, ledger)` returns what to order from the
vendor next: one session as `{"items": ["NG-P00123", ...]}`, a list of such
sessions to be ordered in the order given, or the word `"stop"`. `{"session":
{...}}` and `{"action": "stop"}` wrappers are read the same way. The items of a
session are labelled in the order they are written.

`context` carries the desk and the review, the window the tickets arrived in,
the vendor's prices, set-up charge, session cap, contracted credits and dates,
the queues the desk routes to, the product catalogue as `{product line:
[segments]}`, and the three exports as lists of rows: `intake`, `pool` and
`adjudication`, with the same columns as the files of the same names.

`ledger` is the receipt lines of `label_ledger.jsonl`, oldest first, each as
the vendor wrote it.

Numbers may be JSON numbers, decimal strings such as `"0.184"`, or exact
rational strings such as `"29/128"`. Identifiers -- ticket ids, item ids,
receipt ids, session ids, segments, queues -- keep their own text and are never
read as numbers. A range may also be written `{"low": ..., "high": ...}`, and
extra descriptive keys alongside these are ignored. A value that is not a
finite number is not a measurement.
"""

from fractions import Fraction
from math import isfinite


def number(value):
    """Read one measurement. An identity or an unreadable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def bound(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def purchases(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append({
            "receipt_id": item.get("receipt_id"),
            "session_id": item.get("session_id"),
            "item_id": item.get("item_id"),
            "price_credits": number(item.get("price_credits")),
        })
    return rows


def report_view(value):
    """One notebook report in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "misroute_rate": number(value.get("misroute_rate")),
        "misroute_rate_range": bound(value.get("misroute_rate_range")),
        "label_purchases": purchases(value.get("label_purchases")),
        "credits_spent": number(value.get("credits_spent")),
    }


def _session(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("session", value.get("order", value.get("action")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _session(inner)
        items = value.get("items")
        if isinstance(items, (list, tuple)):
            return {"items": [str(item) for item in items]}
    return None


def plan_view(value):
    """The next-order answer as the list of sessions the desk would place."""

    items = value if isinstance(value, list) else [value]
    read = [_session(item) for item in items]
    return read if read and all(item is not None for item in read) else None
