"""How the qualification notebook is called and what it hands back.

This module ships with the shop's reporting stack. The bench tool and the
procurement office both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the report:

    {
      "wear_rate_ratio": ...,
      "ratio_range": [low, high],
      "sessions_used": {"A": ..., "B": ...},
      "measurements": [{"run_id": ..., "rig": ..., "kind": ...,
                        "reading_um": ...}, ...]
    }

* `wear_rate_ratio` is supplier B's wear rate over supplier A's: 1.0 reads as
  the two wearing alike.
* `ratio_range` is two endpoints in those units, low first.
* `sessions_used` carries the count of valid part-session readings behind the
  reported comparison for `A` and for `B`.
* `measurements` is a list of entries, each with a `run_id`, the `rig` it ran
  on, its `kind` and its `reading_um`.

`analysis.next_collection(context, receipts)` returns what to book on the
bench next: a list of sessions, each `{"rig": 1, "part": "A-3330-09"}` or
`{"rig": 1, "reference_block": true}`, or `"stop"`. A bare session object and
the `{"book": [...]}` and `{"action": "stop"}` wrappers are read the same way.

Numbers may be JSON numbers, decimal strings such as `"0.93"`, or exact
rational strings such as `"49/50"`. Rigs, run ids, part names and kinds are
identities and are never read as numbers. Extra descriptive keys are ignored,
and a range may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `bench_context.json`: the campaign, the review
day, the two rigs, the calibration log, the session table, the lots, the
booking terms, what stores holds and the price the two suppliers quoted.
`receipts` is the `entries` list inside `bench_receipts.json`, oldest first;
each carries a `run_id`, the `rig`, the `calibration` standing at the time, the
`part` and `lot` when a part ran, the `hours` it was charged and its `observed`
reading. Fields beyond those are console transport.
"""

from fractions import Fraction
from math import isfinite


SUPPLIERS = ("A", "B")
RIGS = (1, 2)


def number(value):
    """Read one measurement. An identity or an unreadable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return value if value is None else value
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(Fraction(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def count(value):
    parsed = number(value)
    if isinstance(parsed, (int, float)) and not isinstance(parsed, bool):
        return int(round(parsed))
    return None


def bound(value):
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
                "run_id": item.get("run_id"),
                "rig": item.get("rig"),
                "kind": item.get("kind"),
                "reading_um": number(item.get("reading_um")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    used = value.get("sessions_used")
    if isinstance(used, dict):
        used = {supplier: count(used.get(supplier)) for supplier in SUPPLIERS}
    return {
        "wear_rate_ratio": number(value.get("wear_rate_ratio")),
        "ratio_range": bound(value.get("ratio_range")),
        "sessions_used": used,
        "measurements": measurements(value.get("measurements")),
    }


def _session(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("book", value.get("action", value.get("session")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _session(inner)
        if "rig" in value or "part" in value or "reference_block" in value:
            return {
                "rig": value.get("rig"),
                "part": value.get("part"),
                "reference_block": bool(value.get("reference_block")),
            }
    return None


def booking_view(value):
    """The next-session answer as the list of sessions the console would take."""

    items = value if isinstance(value, list) else [value]
    if isinstance(value, dict) and isinstance(value.get("book"), list):
        items = value["book"]
    sessions = [_session(item) for item in items]
    return sessions if sessions and all(item is not None for item in sessions) else None
