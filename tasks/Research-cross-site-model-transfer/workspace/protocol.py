"""How the reporting stack calls the notebook and what it hands back.

This module ships with the triage reporting stack. The review desk's tool and
the quarterly report both read a notebook through it, so it stays as it is.

`analysis.analyze(context, ledger)` returns the report:

    {
      "served_error": ...,
      "error_interval": [low, high],
      "groups": [{"prior_contacts_min": ..., "prior_contacts_max": ...,
                  "share_of_received": ..., "error": ...,
                  "rows_reviewed": ...}, ...],
      "reviews": [{"receipt_id": ..., "channel": ...,
                   "rows_returned": ..., "units_charged": ...}, ...],
      "units_used": ...
    }

* `served_error` is a proportion of tickets: 0.09 prints as nine in a hundred.
* `error_interval` is two endpoints in those units, low first.
* `groups` is a list of entries. Each names a band of prior contacts with
  `prior_contacts_min` and `prior_contacts_max`, either of which may be null
  for an open end, and carries `share_of_received`, `error` and
  `rows_reviewed`.
* `reviews` is a list of entries, each with a `receipt_id`, the `channel` it
  ran on, `rows_returned` and `units_charged`.
* `units_used` is a whole number of review units.

`analysis.next_collection(context, ledger)` returns the next review to buy:

    {"site": ..., "channel": "queue" or "export",
     "prior_contacts_min": ..., "prior_contacts_max": ..., "rows": ...}

or `"stop"`. `{"request": {...}}` and `{"action": "stop"}` wrappers are read
the same way, and a list means the desk may take any one of the entries in it.

Numbers may be JSON numbers or decimal strings such as `"0.091"`. Site names,
channel names and receipt ids are identities and are never read as numbers.
Extra descriptive keys are ignored, and an interval may also be written
`{"low": ..., "high": ...}`.

`context` is the deployment as the reporting stack publishes it: the
`deployment` and `site` names, the `window`, `as_of`, the `intake` settings,
the `review` terms, the shipped `model`, and `intake_counters`, which is the
same day-by-day table as the intake counter export in the workspace.
`ledger` is the list of review receipts in `label_ledger.json`, oldest first;
each carries a `receipt_id`, the `channel` it ran on, the prior-contact band
it was asked for, `n_requested`, `n_returned`, `n_skipped`, `units_charged`,
a `snapshot_id`, and `observed.rows`, the reviewed tickets themselves. Fields
beyond those are desk transport.
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
    if value is None:
        return None
    read = whole(value)
    return read if isinstance(read, int) else None


def groups(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "prior_contacts_min": band(item.get("prior_contacts_min")),
                "prior_contacts_max": band(item.get("prior_contacts_max")),
                "share_of_received": number(item.get("share_of_received")),
                "error": number(item.get("error")),
                "rows_reviewed": whole(item.get("rows_reviewed")),
            }
        )
    return rows


def reviews(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "channel": item.get("channel"),
                "rows_returned": whole(item.get("rows_returned")),
                "units_charged": whole(item.get("units_charged")),
            }
        )
    return rows


def report_view(value):
    """One delivered report in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "served_error": number(value.get("served_error")),
        "error_interval": interval(value.get("error_interval")),
        "groups": groups(value.get("groups")),
        "reviews": reviews(value.get("reviews")),
        "units_used": whole(value.get("units_used")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("request", value.get("action", value.get("review")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "channel" in value or "rows" in value:
            return {
                "site": value.get("site"),
                "channel": value.get("channel"),
                "prior_contacts_min": band(value.get("prior_contacts_min")),
                "prior_contacts_max": band(value.get("prior_contacts_max")),
                "rows": whole(value.get("rows")),
            }
    return None


def plan_view(value):
    """The next-review answer as a list of choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
