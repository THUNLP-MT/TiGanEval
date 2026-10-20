"""How the sweep reporting stack calls the notebook and what it hands back.

This module ships with the sweep reporting stack. The node console's tool and
the weekly allocation note both read a notebook through it, so it stays as it
is.

`analysis.report.analyze(context, ledger)` returns the note:

    {
      "funded_run": "cfg-nn",
      "end_loss": ...,
      "end_loss_range": [low, high],
      "segments": [{"segment_id": ..., "config_id": ...,
                    "used": true or false, "set_aside_reason": ...}, ...],
      "collections": [{"receipt_id": ..., "config_id": ..., "node_type": ...,
                       "hours_charged": ..., "steps_returned": ...}, ...],
      "hours_used": ...,
      "hours_left": ...
    }

* `funded_run` is a `config_id` the ledger carries.
* `end_loss` is a loss in the units the trainer writes.
* `end_loss_range` is two endpoints in those units, low first, with `end_loss`
  between them.
* `segments` is a list with one entry per segment on the ledger. Every segment
  in these sweep ledgers belongs to its run's cumulative curve and is in scope,
  so `used` is true and `set_aside_reason` is null.
* `collections` is a list with one entry per receipt on the booking stream;
  its configuration, node, charged hours and returned steps copy that receipt.
* `hours_used` and `hours_left` are whole node-hours.

`analysis.report.next_collection(context, ledger)` returns the next booking:

    {"jobs": [{"config_id": ..., "node_type": ..., "hours": ...}, ...]}

or `"stop"`. A bare list of jobs, a single job object, and `{"booking": ...}`
or `{"action": "stop"}` wrappers are read the same way.

Numbers may be JSON numbers or decimal strings such as `"1.42"`. Config ids,
node names, segment ids and receipt ids are identities and are never read as
numbers. Extra descriptive keys are ignored, and a range may also be written
`{"low": ..., "high": ...}`.

`context` is the window as the reporting stack publishes it: the `campaign`
name, `as_of`, the `cluster` block (`node_types`, `reserved_node_types` and
the `job_hours` a booking has to sit inside), the `budget` block
(`grant_node_hours`, `hours_charged`, `hours_left`), `ledger`, which is the
same segment table as `run_ledger.csv` in the workspace, and `curves`, which
maps each `config_id` to the rows the trainer wrote for it, in the order they
were written, each row carrying `segment_id`, `step`, `lr` and `loss`.

`ledger` is the list of booking receipts in `collection_receipts.json`, oldest
first; each carries a `receipt_id`, the `config_id` and `node_type` it was
asked for, `hours_requested`, `steps_returned`, `schedule_restarted`,
`hours_charged`, `hours_remaining`, a `refusal` (null when the job ran), and
`observed.rows`, the rows that job returned. Fields beyond those are console
transport.
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


def identity(value):
    return value if isinstance(value, str) else None


def segments(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        used = item.get("used")
        rows.append(
            {
                "segment_id": identity(item.get("segment_id")),
                "config_id": identity(item.get("config_id")),
                "used": used if isinstance(used, bool) else None,
                "set_aside_reason": item.get("set_aside_reason"),
            }
        )
    return rows


def collections(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": identity(item.get("receipt_id")),
                "config_id": identity(item.get("config_id")),
                "node_type": identity(item.get("node_type")),
                "hours_charged": whole(item.get("hours_charged")),
                "steps_returned": whole(item.get("steps_returned")),
            }
        )
    return rows


def report_view(value):
    """One delivered note in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "funded_run": identity(value.get("funded_run")),
        "end_loss": number(value.get("end_loss")),
        "end_loss_range": interval(value.get("end_loss_range")),
        "segments": segments(value.get("segments")),
        "collections": collections(value.get("collections")),
        "hours_used": whole(value.get("hours_used")),
        "hours_left": whole(value.get("hours_left")),
    }


def _job(value):
    if not isinstance(value, dict):
        return None
    return {
        "config_id": identity(value.get("config_id")),
        "node_type": identity(value.get("node_type")),
        "hours": whole(value.get("hours")),
    }


def plan_view(value):
    """The next-booking answer as a stop or a list of jobs the console can take."""

    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("jobs", value.get("booking", value.get("action")))
        if inner is not None and inner is not value:
            return plan_view(inner)
        one = _job(value)
        return [one] if one is not None else None
    if isinstance(value, list):
        jobs = [_job(item) for item in value]
        return jobs if jobs and all(item is not None for item in jobs) else None
    return None
