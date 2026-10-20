"""How the release stack calls the notebook and what it hands back.

This module ships with the handheld release stack. The annotation desk's tool
and the board pack both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the board pack:

    {
      "bundle": "...",
      "worst_profile": "...",
      "fleet_points": ...,
      "points_range": [low, high],
      "rows_used": ...,
      "bundle_points": [{"bundle": ..., "points": ...}, ...],
      "requests": [{"receipt_id": ..., "rows_returned": ...,
                    "credits_charged": ..., "refused": ...}, ...],
      "credits_used": ...
    }

* `bundle` is the name of the bundle to ship, out of `context["bundles"]`.
* `fleet_points` is points of error, one decimal, lower better: 12.4 means
  twelve and four tenths of a hundred captures came back wrong.
* `points_range` is the nineteen-times-in-twenty planning range in those units,
  with the low endpoint first.
* `worst_profile` names a duty profile and `rows_used` is how many rows the
  number over that profile stands on.
* `bundle_points` carries one entry per bundle with the same units.
* `requests` is a list, one entry per request the desk billed, with the
  `receipt_id`, `rows_returned`, `credits_charged`, and `refused` as a boolean.
* `credits_used` is a whole number of annotation credits.

`analysis.next_collection(context, receipts)` returns the next capture request:

    {"duty_profile": ..., "firmware": ..., "condition": ..., "rows": ...}

or `"stop"`. `{"request": {...}}` and `{"action": "stop"}` wrappers are read
the same way, and a list means the desk may take any one of the entries in it.
The row count is a whole number from the desk's published minimum through its
maximum, inclusive; those terms are also present in `context["annotation"]`.

Numbers may be JSON numbers or decimal strings such as `"12.4"`. Bundle names,
duty profiles, firmware names, conditions and receipt ids are identities and
are never read as numbers. Extra descriptive keys are ignored, and a range may
also be written `{"low": ..., "high": ...}`.

`context` is the campaign as the release stack publishes it: the `campaign`
and `fleet` names, the `window`, `as_of`, the `bundles` on test, the board's
`promise_points`, the `firmware` settings, the `annotation` terms,
`fleet_register` and `capture_log`. The last two are tables written
`{"columns": [...], "rows": [[...], ...]}`, the same tables as
`fleet_register.csv` and `capture_log.csv` in the workspace.

`receipts` is the list of receipts in `capture_receipts.json`, oldest first;
each carries a `receipt_id`, a `request_id`, the `duty_profile`, `firmware`
and `condition` it asked for, `rows_requested`, `rows_returned`,
`credits_charged`, `credits_remaining`, a `refusal` (null when the desk
answered it), and `observed.rows`, the annotated captures themselves, keyed by
the same column names the capture log uses plus `capture_id` and
`duty_profile`. Fields beyond those are desk transport.
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


def name(value):
    return value if isinstance(value, str) else None


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def table(value):
    """One published table as a list of dictionaries."""

    if not isinstance(value, dict):
        return []
    columns = list(value.get("columns", ()))
    rows = []
    for row in value.get("rows", ()):
        rows.append({column: row[index] for index, column in enumerate(columns)})
    return rows


def bundle_points(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append({"bundle": name(item.get("bundle")), "points": number(item.get("points"))})
    return rows


def requests(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "rows_returned": whole(item.get("rows_returned")),
                "credits_charged": whole(item.get("credits_charged")),
                "refused": bool(item.get("refused")),
            }
        )
    return rows


def report_view(value):
    """One delivered board pack in the shape the release stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "bundle": name(value.get("bundle")),
        "worst_profile": name(value.get("worst_profile")),
        "fleet_points": number(value.get("fleet_points")),
        "points_range": interval(value.get("points_range")),
        "rows_used": whole(value.get("rows_used")),
        "bundle_points": bundle_points(value.get("bundle_points")),
        "requests": requests(value.get("requests")),
        "credits_used": whole(value.get("credits_used")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("request", value.get("action", value.get("capture")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "duty_profile" in value or "rows" in value:
            return {
                "duty_profile": name(value.get("duty_profile")),
                "firmware": name(value.get("firmware")),
                "condition": name(value.get("condition")),
                "rows": whole(value.get("rows")),
            }
    return None


def plan_view(value):
    """The next-capture answer as a list of choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
