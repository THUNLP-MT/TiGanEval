"""How the dispatch stack calls the notebook and what it hands back.

This module ships with the dispatch stack. The audit desk's tool and the
monthly board review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the board:

    {
      "stream_rate": ...,
      "windows": [{"job_class": ..., "window": [low, high],
                   "sheets_used": ...}, ...],
      "visits": [{"receipt_id": ..., "job_class": ...,
                  "jobs_returned": ..., "units_charged": ...}, ...],
      "units_left": ...
    }

* `stream_rate` is a share of jobs rounded to the nearest whole percentage
  point: 0.79 prints as seventy-nine in a hundred.
* `windows` is a list of entries. Each names a `job_class` and carries
  `window`, two whole minutes either side of the tool's number, low first, so
  `[-47, 47]` prints a job estimated at 60 minutes as 13 to 107. A class with
  no entry gets no window on the board and the crews are given the tool's
  number bare. `sheets_used` is how many rows stood behind the entry.
* `visits` is a list of entries, each with a `receipt_id`, the `job_class` the
  night was booked on, `jobs_returned` and `units_charged`.
* `units_left` is a whole number of audit units.

`analysis.next_collection(context, receipts)` returns the next night to book:

    {"job_class": ..., "week": ..., "jobs": ...}

or `"stop"`. `{"visit": {...}}` and `{"action": "stop"}` wrappers are read the
same way, and a list means the desk may take any one of the entries in it.

Numbers may be JSON numbers or decimal strings such as `"0.793"`. Class names
and receipt ids are identities and are never read as numbers. Extra
descriptive keys are ignored, and a window may also be written
`{"low": ..., "high": ...}`.

`context` is the depot as the dispatch stack publishes it: the `depot` and
`month` names, `as_of`, the `board` terms, the `audit` terms, the `visits`
terms, `traffic`, `intake_log` and `sheets`. `traffic` is the same table as
the monthly traffic report in the workspace, `intake_log` the same table as
the audit intake log, and `sheets` the same rows as the audit sheet export,
each with the five job facts, the tool's number and the close-out duration.
`receipts` is the list of visit receipts in `visit_receipts.json`, oldest
first; each carries a `receipt_id`, a `visit_id`, the `week` and `job_class`
it was booked on, `jobs_requested`, `jobs_returned`, `units_charged`,
`roster_ok`, `refusal`, `units_remaining`, and `observed.rows`, the jobs the
crew timed. Fields beyond those are desk transport.
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


def window(value):
    """A pair of edges, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def windows(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "job_class": item.get("job_class"),
                "window": window(item.get("window")),
                "sheets_used": whole(item.get("sheets_used")),
            }
        )
    return rows


def visits(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "job_class": item.get("job_class"),
                "jobs_returned": whole(item.get("jobs_returned")),
                "units_charged": whole(item.get("units_charged")),
            }
        )
    return rows


def board_view(value):
    """One delivered board in the shape the dispatch stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "stream_rate": number(value.get("stream_rate")),
        "windows": windows(value.get("windows")),
        "visits": visits(value.get("visits")),
        "units_left": whole(value.get("units_left")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("visit", value.get("action", value.get("booking")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "job_class" in value or "week" in value:
            return {
                "job_class": value.get("job_class"),
                "week": whole(value.get("week")),
                "jobs": whole(value.get("jobs")),
            }
    return None


def plan_view(value):
    """The next-visit answer as a list of bookings the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
