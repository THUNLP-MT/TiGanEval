"""How the readout notebook is called and what it hands back.

This module ships with the reporting stack. The readout tool and the analytics
review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "cohort": {"control":   {"sessions": ..., "confirmations": ...},
                 "treatment": {"sessions": ..., "confirmations": ...}},
      "lift": ...,
      "lift_bounds": [low, high],
      "measurements": [{"scan_id": ..., "day": ..., "arm": ...,
                        "crawler_sessions": ...}, ...],
      "decision": "expand" or "hold"
    }

* `cohort` carries an entry for `control` and one for `treatment`, each with a
  `sessions` number and a `confirmations` number, or null.
* `lift` is a number in the same units as `gate`, a proportion of sessions:
  0.004 reads as four tenths of a conversion point.
* `lift_bounds` is two endpoints in those units, low first.
* `measurements` is a list of entries, each with a `scan_id`, a `day`, an `arm`
  and a `crawler_sessions` number.
* `decision` is `"expand"` or `"hold"`.

`analysis.next_collection(context, receipts)` returns what to buy next from
the archive rescan service: `{"day": "2026-08-30", "arm": "treatment"}`, or
`"stop"`. `{"scan": {...}}` and `{"action": "stop"}` wrappers are read the same
way. A list means the operator may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"0.0035"`, or exact
rational strings such as `"7/2000"`. Days, arms, scan ids and the decision are
identities and are never read as numbers. Extra descriptive keys are ignored,
and a bound may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `readout_context.json`: the window, the gate
the release is judged against, which service serves each arm, the archive
terms, the change log, the daily session table and the checkout queue
counters. `receipts` is the list of rescan receipts in `audit_receipts.json`,
oldest first; each has a `scan_id`, the `day` and `arm` it covers, the `units`
it cost and its `observed` return. Fields beyond those are service transport.
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


def bound(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def counts(value):
    if not isinstance(value, dict):
        return None
    return {
        "sessions": number(value.get("sessions")),
        "confirmations": number(value.get("confirmations")),
    }


def measurements(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "scan_id": item.get("scan_id"),
                "day": item.get("day"),
                "arm": item.get("arm"),
                "crawler_sessions": number(item.get("crawler_sessions")),
            }
        )
    return rows


def readout_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    cohort = value.get("cohort")
    if isinstance(cohort, dict):
        cohort = {arm: counts(cohort.get(arm)) for arm in ARMS}
    decision = value.get("decision")
    if isinstance(decision, dict):
        decision = decision.get("action", decision.get("decision"))
    if isinstance(decision, list) and len(decision) == 1:
        decision = decision[0]
    return {
        "cohort": cohort,
        "lift": number(value.get("lift")),
        "lift_bounds": bound(value.get("lift_bounds")),
        "measurements": measurements(value.get("measurements")),
        "decision": decision,
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("scan", value.get("action", value.get("regime")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "day" in value or "arm" in value:
            return {"day": value.get("day"), "arm": value.get("arm")}
    return None


def plan_view(value):
    """The next-rescan answer as a list of tied choices the operator may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
