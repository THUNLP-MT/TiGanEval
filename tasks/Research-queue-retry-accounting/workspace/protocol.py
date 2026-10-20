"""How the failure notebook is called and what it hands back.

This module ships with the platform's review stack. The review tool and the
platform's own reading of a notebook both go through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the report:

    {
      "operations": ...,
      "failed_operations": ...,
      "failure_rate": ...,
      "failure_rate_range": [low, high],
      "trace_units": [{"trace_id": ..., "minute": ..., "pool": ...,
                       "probe_receipts": ..., "probe_errors": ...}, ...]
    }

* `operations` and `failed_operations` are counts.
* `failure_rate` is a number in the units of the two counts above it: 0.021
  reads as two and a tenth per cent.
* `failure_rate_range` is two endpoints in those units, low first.
* `trace_units` is a list of entries, each with a `trace_id`, the `minute` and
  `pool` it covers, and the `probe_receipts` and `probe_errors` numbers.

`analysis.next_trace(context, receipts)` returns what to pull from the edge
archive next: `{"minute": "2026-09-24T19:32", "pool": "edge-ams"}`, or
`"stop"`. `{"trace": {...}}` and `{"action": "stop"}` wrappers are read the
same way. A list means the operator may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"0.0226"`, or exact
rational strings such as `"7/310"`. Minutes, pools, trace ids and the stop word
are identities and are never read as numbers. Extra descriptive keys are
ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` carries what `service_context.json` carries — the review, the route,
the window and its service block, the archive terms, the pools, the fleets and
the daily dashboard — plus `rollup`, the rows of `request_rollup.json`, and
`pool_counters`, the rows of `edge_pool_counters.json`. `receipts` is the list
of trace receipts in `trace_receipts.json`, oldest first; each has a
`trace_id`, the `minute` and `pool` it covers, the `units` it cost and its
`observed` return. Fields beyond those are service transport.
"""

from fractions import Fraction
from math import isfinite


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


def bound(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def trace_units(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "trace_id": item.get("trace_id"),
                "minute": item.get("minute"),
                "pool": item.get("pool"),
                "probe_receipts": number(item.get("probe_receipts")),
                "probe_errors": number(item.get("probe_errors")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the review stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "operations": number(value.get("operations")),
        "failed_operations": number(value.get("failed_operations")),
        "failure_rate": number(value.get("failure_rate")),
        "failure_rate_range": bound(value.get("failure_rate_range")),
        "trace_units": trace_units(value.get("trace_units")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("trace", value.get("action", value.get("next")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "minute" in value or "pool" in value:
            return {"minute": value.get("minute"), "pool": value.get("pool")}
    return None


def plan_view(value):
    """The next-trace answer as a list of tied choices the operator may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
