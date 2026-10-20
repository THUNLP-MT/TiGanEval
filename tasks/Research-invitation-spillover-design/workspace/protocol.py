"""How the campaign reporting stack calls a notebook and what it reads back.

This module ships with the reporting stack. The month-end pack and the mail
house desk both read a notebook through it, so it stays as it is.

`report.analyze(context)` returns the readout:

    {
      "ticket_effect_points": ...,
      "effect_range_points": [low, high],
      "bookings": [{"receipt_id": ..., "drum": ..., "tickets_charged": ...,
                    "accounts_reached": ..., "credits_charged": ...}, ...],
      "tickets_charged": ...,
      "accounts_reached": ...,
      "credits_charged": ...
    }

* `ticket_effect_points` is in points of sign-up rate: 12.5 means twelve and a
  half percentage points.
* `effect_range_points` is two endpoints in those units, low first, with the
  reported `ticket_effect_points` between them.
* `bookings` is a list of entries, one an entry, each naming the `receipt_id`
  the mail house wrote, the `drum` it ran, the `tickets_charged` it printed,
  the `accounts_reached` those tickets landed on and the `credits_charged`.
* `tickets_charged`, `accounts_reached` and `credits_charged` are the month's
  totals as whole numbers.

`report.next_collection(context)` returns what to book next:

    [{"drum": ..., "tickets": ..., "send_on": "YYYY-MM-DD"}, ...]

or `"stop"`. A single booking may be returned on its own rather than in a list,
and `{"plan": [...]}` and `{"action": "stop"}` wrappers are read the same way.

Numbers may be JSON numbers or decimal strings such as `"12.5"`. Drum names,
receipt ids and dates are identities and are never read as numbers. Extra
descriptive keys are ignored, and a range may also be written
`{"low": ..., "high": ...}`.

`context` is the month as the reporting stack publishes it: the `campaign` and
`office` names, the `window`, `as_of`, the `target`, the `account`, the
`mail_house` terms, the `drums` on the floor with their prices, names left and
allowances, and `files`, which names the four files this month's evidence is
in. Those files sit beside the notebook and are read with the ordinary library:
`account_register.csv`, `invitation_receipts.csv`, `signup_counter.csv` and
`ledger/receipts.jsonl`.
"""

import json
from math import isfinite


def number(value):
    """Read one figure. An identity or an unreadable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def whole(value):
    read = number(value)
    if isinstance(read, float) and read.is_integer():
        return int(read)
    return read


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def bookings(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "drum": item.get("drum"),
                "tickets_charged": whole(item.get("tickets_charged")),
                "accounts_reached": whole(item.get("accounts_reached")),
                "credits_charged": whole(item.get("credits_charged")),
            }
        )
    return rows


def report_view(value):
    """One delivered readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "ticket_effect_points": number(value.get("ticket_effect_points")),
        "effect_range_points": interval(value.get("effect_range_points")),
        "bookings": bookings(value.get("bookings")),
        "tickets_charged": whole(value.get("tickets_charged")),
        "accounts_reached": whole(value.get("accounts_reached")),
        "credits_charged": whole(value.get("credits_charged")),
    }


def _booking(value):
    if not isinstance(value, dict):
        return None
    if "drum" not in value and "tickets" not in value:
        return None
    return {
        "drum": value.get("drum"),
        "tickets": whole(value.get("tickets")),
        "send_on": value.get("send_on"),
    }


def plan_view(value):
    """The next-booking answer as a stop or a list of bookings, in order."""

    if isinstance(value, dict):
        inner = value.get("plan", value.get("action", value.get("booking")))
        if isinstance(inner, (str, list, dict)) and inner is not value:
            return plan_view(inner)
    if isinstance(value, str):
        return "stop" if value.strip().lower() == "stop" else value
    items = value if isinstance(value, list) else [value]
    rows = [_booking(item) for item in items]
    if not rows or any(item is None for item in rows):
        return value if isinstance(value, (str, int, float)) else "not a plan"
    return rows


def load_json_lines(path):
    """Every JSON object on its own line of a file, in the order written."""

    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows
