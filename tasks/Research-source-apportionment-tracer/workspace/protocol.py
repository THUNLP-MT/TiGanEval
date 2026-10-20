"""How the apportionment notebook is called and what it hands back.

This module ships with the estates reporting stack. The header tool and the
February review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, ledger)` returns the report:

    {
      "shares": {"district_tie_in": ..., "gas_plant": ..., "data_hall_recovery": ...},
      "share_band": {"district_tie_in": [low, high], ...},
      "samples_used": ["hs-001", ...],
      "samples_set_aside": ["hs-007", ...],
      "visits": [{"call_id": ..., "point": ..., "slots_charged": ...}, ...]
    }

* `shares` are fractions of the window's delivered heat, one per supply named
  in `context["supplies"]`: 0.42 reads as forty-two hundredths of the heat.
* `share_band` is two endpoints per supply in those units, low first.
* `samples_used` and `samples_set_aside` are sample ids off the sample sheet.
* `visits` is a list of entries, each with a `call_id`, a `point` and a
  `slots_charged` number.

`analysis.next_collection(context, ledger)` returns the visit to send the
contractor on:

    {"point": ..., "channels": [...], "dwell_min": ..., "samples": ...}

or `"stop"`. `{"visit": {...}}` and `{"action": "stop"}` wrappers are read the
same way. A list means the estates office may take any one of the entries in
it.

Numbers may be JSON numbers, decimal strings such as `"0.52"`, or exact
rational strings such as `"13/25"`. Points, channels, sample ids and call ids
are identities and are never read as numbers. Extra descriptive keys are
ignored, and a band may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `header_context.json`: the window, the supplies,
the characterisation sheet, the analyser's dwells and floors, the weather log,
the heat meter, the sample sheet, the operations log, the terms the collection
agreement carries and what the report was asked for. `ledger` is the list of
visit receipts in `sample_ledger.json`, oldest first; each has a `call_id`, the
`point`, `channels`, `dwell_min` and `samples` it was served with, the
`slots_charged` it cost, the day it was served on, the readings it brought
back, and a `refusal` line where the desk handed the round back. Fields beyond
those are desk transport.
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


def band(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def shares(value):
    if not isinstance(value, dict):
        return None
    return {str(key): number(item) for key, item in value.items()}


def bands(value):
    if not isinstance(value, dict):
        return None
    return {str(key): band(item) for key, item in value.items()}


def ids(value):
    if not isinstance(value, (list, tuple)):
        return None
    return [str(item) for item in value]


def visits(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "call_id": item.get("call_id"),
                "point": item.get("point"),
                "slots_charged": number(item.get("slots_charged")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "shares": shares(value.get("shares")),
        "share_band": bands(value.get("share_band")),
        "samples_used": ids(value.get("samples_used")),
        "samples_set_aside": ids(value.get("samples_set_aside")),
        "visits": visits(value.get("visits")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("visit", value.get("action", value.get("plan")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "point" in value or "samples" in value:
            channels = value.get("channels", ["conductivity", "marker"])
            if isinstance(channels, str):
                channels = [channels]
            return {
                "point": value.get("point"),
                "channels": list(channels) if isinstance(channels, (list, tuple)) else channels,
                "dwell_min": number(value.get("dwell_min", 5)),
                "samples": number(value.get("samples")),
            }
    return None


def plan_view(value):
    """The next-visit answer as a list of tied choices the office may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
