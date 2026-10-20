"""How the desk reads the notebook's two answers. No planning lives here.

This module ships with the dispatch reporting stack. The order desk and the
weekly settlement pack both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns

    {
      "shift_id": the shift the sheet is for,
      "demand": [{"area": ..., "window": ...,
                  "drops": a number of drops,
                  "drops_range": [low, high]}, ...],
      "shift_total": {"drops": ..., "drops_range": [low, high]},
      "settlements": [{"order_id": ..., "shift_id": ...,
                       "van_hours_charged": ...}, ...]
    }

* `demand` carries one entry per area and window of that shift, each with the
  drops the sheet is for and a range in the same drops, low end first.
* `shift_total` is the same two things for the whole network on that shift.
* `settlements` is a line per settled order: its `order_id`, the `shift_id` it
  covers and the `van_hours_charged` on it.

`analysis.next_collection(context, receipts)` returns the order for the next
shift, `{"booking": [{"area": "Harbour", "window": "W1", "vans": 26}, ...]}`,
or `"stop"`. A bare list of lines is read as an order, `{"order": ...}` and
`{"action": "stop"}` wrappers are read the same way, and a list of orders means
the desk may take any one of them.

Numbers may be JSON numbers, decimal strings such as `"371.5"`, or exact
rational strings such as `"5/4"`. Areas, windows, zone codes, shift ids and
order ids are identities and are never read as numbers. Extra descriptive keys
are ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `desk_context.json`: the campaign, its shift
calendar, the two areas and four windows, both areas' zone rows, the network's
own area line, the routing table, the carrier terms and what the desk rounds
to. `receipts` is the settlement ledger, oldest first; each carries an
`order_id`, the `shift_id` it covers, a `lines` list with the `vans_booked` and
the `drops_metered` for every area and window, `vans_idle`, `windows_short`,
`vans_short`, `spill_charge`, `van_hours_charged`, `allowance_left_after`, and
a `refusal` line when the desk handed the order back.
"""

from fractions import Fraction
from math import isfinite


AREAS = ("Harbour", "Ridge")
WINDOWS = ("W1", "W2", "W3", "W4")


def number(value):
    """Read one quantity. An identity or an unusable display stays as it is."""

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


def _demand_rows(value):
    if not isinstance(value, list):
        return None
    read = []
    for item in value:
        if not isinstance(item, dict):
            return None
        read.append(
            {
                "area": item.get("area"),
                "window": item.get("window"),
                "drops": number(item.get("drops")),
                "drops_range": endpoints(item.get("drops_range")),
            }
        )
    return read


def _total(value):
    if not isinstance(value, dict):
        return {"drops": None, "drops_range": None}
    return {
        "drops": number(value.get("drops")),
        "drops_range": endpoints(value.get("drops_range")),
    }


def _settlement_rows(value):
    if not isinstance(value, list):
        return None
    read = []
    for item in value:
        if not isinstance(item, dict):
            return None
        read.append(
            {
                "order_id": item.get("order_id"),
                "shift_id": item.get("shift_id"),
                "van_hours_charged": number(item.get("van_hours_charged")),
            }
        )
    return read


def report_view(value):
    """One delivered sheet in the shape the desk reads it in."""

    if not isinstance(value, dict):
        return {
            "shift_id": None,
            "demand": None,
            "shift_total": {"drops": None, "drops_range": None},
            "settlements": None,
        }
    return {
        "shift_id": value.get("shift_id"),
        "demand": _demand_rows(value.get("demand")),
        "shift_total": _total(value.get("shift_total")),
        "settlements": _settlement_rows(value.get("settlements")),
    }


def _line(item):
    if not isinstance(item, dict):
        return None
    area = item.get("area")
    window = item.get("window")
    vans = number(item.get("vans", item.get("van_count")))
    if not isinstance(area, str) or not isinstance(window, str) or vans is None:
        return None
    return {"area": area, "window": window, "vans": vans}


def _unwrap(value):
    while isinstance(value, dict):
        inner = None
        for key in ("booking", "order", "sheet", "action", "plan"):
            if key in value:
                inner = value[key]
                break
        if inner is None or inner is value:
            return value
        value = inner
    return value


def _order(value):
    """One order: a word such as "stop", or a list of {area, window, vans}."""

    value = _unwrap(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        line = _line(value)
        return [line] if line is not None else None
    if isinstance(value, (list, tuple)):
        read = [_line(item) for item in value]
        return read if read and all(item is not None for item in read) else None
    return None


def plan_view(value):
    """The next order as a list of orders the desk may take any one of."""

    read = _order(value)
    if read is not None:
        return [read]
    inner = _unwrap(value)
    if isinstance(inner, (list, tuple)) and inner:
        offered = [_order(item) for item in inner]
        if all(item is not None for item in offered):
            return offered
    return [None]
