"""How the fleet reporting stack calls a notebook and what it hands back.

This module ships with the stack. The maintenance board's pack and the audit
desk's tool both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the note:

    {
      "build_difference_points": ...,
      "difference_range": [low, high],
      "vehicle_months": ...,
      "days": [{"receipt_id": ..., "depot": ..., "day": ...,
                "vans_returned": ..., "faults_returned": ...}, ...],
      "days_charged": ...
    }

* `build_difference_points` is faults per hundred vehicle-months, the build the
  review asks about minus the build a year before it. Positive means worse.
* `difference_range` is two endpoints in the same units, low first, and it
  contains the reported `build_difference_points`.
* `vehicle_months` is service-day exposure inside the return window represented
  by the note: either the full fitted table or the two named build groups whose
  contrast it reports. It is not roster headcounts.
* `days` is a list of entries, one for each day the audit was charged for, each
  with the `receipt_id`, the `depot` it was worked at, the `day`, the vans and
  the faults the inspector came back with.
* `days_charged` is a whole number of days.

`analysis.next_collection(context, receipts)` returns the next day to book:

    {"depot": ..., "builds": ["2021-H2", "2022-H2"], "age_band": [low, high],
     "vans": ..., "day": "YYYY-MM-DD"}

or `"stop"`. `{"day": {...}}` and `{"action": "stop"}` wrappers are read the
same way. A list offers alternatives; because the desk may take any one, every
entry in it must be a valid next day.

Numbers may be JSON numbers or decimal strings such as `"-0.6"`. Region names,
depot names, build groups and receipt ids are identities and are never read as
numbers. Extra descriptive keys are ignored, and a range may also be written
`{"low": ..., "high": ...}`.

`context` is the region as the stack publishes it: the `region` name, the
`window` of return months, `as_of`, the `depots`, the `cards` each depot has
raised faults under and from when, the `leases`, the `build_sheets`, the
`change_orders`, the `roster`, the `vans` on the register, the `faults` on the
log, the `audit` terms and the `review` terms. `vans`, `faults` and `roster`
carry the same rows as `van_register.csv`, `fault_log.csv` and the roster table
in the workspace. `receipts` is the list of day receipts in
`audit_receipts.json`, oldest first; each carries a `receipt_id`, the `day`,
`depot`, `builds`, `age_band`, `vans_asked`, `vans_returned`,
`faults_returned`, `van_months_returned`, `walkaround_ref`, `days_charged`,
`days_remaining`, a `refusal` when the desk handed the day back, and
`observed.rows`, the vans the inspector walked round. Fields beyond those are
desk transport.
"""

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


def band(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [whole(item) for item in value]
    return None


def days(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "depot": item.get("depot"),
                "day": item.get("day"),
                "vans_returned": whole(item.get("vans_returned")),
                "faults_returned": whole(item.get("faults_returned")),
            }
        )
    return rows


def report_view(value):
    """One delivered note in the shape the stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "build_difference_points": number(value.get("build_difference_points")),
        "difference_range": interval(value.get("difference_range")),
        "vehicle_months": number(value.get("vehicle_months")),
        "days": days(value.get("days")),
        "days_charged": whole(value.get("days_charged")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("day") if isinstance(value.get("day"), dict) else None
        inner = inner or value.get("request") or value.get("action")
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "depot" in value or "builds" in value:
            builds = value.get("builds")
            if isinstance(builds, str):
                builds = [builds]
            return {
                "depot": value.get("depot"),
                "builds": list(builds) if isinstance(builds, (list, tuple)) else builds,
                "age_band": band(value.get("age_band")),
                "vans": whole(value.get("vans")),
                "day": value.get("day"),
            }
    return None


def plan_view(value):
    """The next-day answer as a list of choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
