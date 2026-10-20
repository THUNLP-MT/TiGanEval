"""How the release tooling calls the readout and what it reads back.

This module ships with the release tooling. The review packet and the
evaluation desk's own console both read a notebook through it, so it stays as
it is.

`analysis.analyze(context, ledger)` returns the readout:

    {
      "shipped_checkpoint": "r06@13500",
      "gain_points": ...,
      "gain_range": [low, high],
      "jobs": [{"job_id": ..., "lot": ..., "reads": ..., "units_charged": ...}, ...],
      "units_left": ...
    }

* `shipped_checkpoint` is a checkpoint id, `<run_id>@<checkpoint_step>`, the
  same shape the registry uses.
* `gain_points` and both ends of `gain_range` are in points of `val_score`,
  where one point is 0.01: a checkpoint that scores 0.8100 against a model
  that scores 0.7900 is two points ahead. Low end first.
* `jobs` is a list of entries, each with the `job_id` of one job the desk ran,
  the `lot` it ran on, the number of `reads` it returned and the
  `units_charged` for it.
* `units_left` is a whole number of compute units.

`analysis.next_collection(context, ledger)` returns the next job to send the
desk:

    {"kind": "reads", "lot": ..., "items": [...], "repeats": ...}

or `{"kind": "train", "config": ..., "runs": ...}`, or `"stop"`. `{"job": {...}}`
and `{"action": "stop"}` wrappers are read the same way, and a list means the
desk may take any one of the entries in it. An entry with no `kind` and an
`items` list is read as a reads job.

Numbers may be JSON numbers or decimal strings such as `"2.26"`. Checkpoint
ids, model ids, lot names and job ids are identities and are never read as
numbers. Extra descriptive keys are ignored, and a range may also be written
`{"low": ..., "high": ...}`.

`context` is the campaign as the release tooling publishes it: the `campaign`
and `label` names, `as_of`, the `release` block (the model id in production,
the `stored_val_score` the release note carries and the day and lot it was
read on), `lots` (which are open, which are retired, and how many rows a read
covers), `compute` (the grant, the reserve, the per-job cap and the prices),
`review` (what the review note asks for and when it is due), `run_ledger`,
which is the same table as `run_ledger.csv` in the workspace, and
`checkpoint_registry` and `curves`, likewise.

`ledger` is the list of receipts in `ledger/receipts.jsonl`, oldest first. Each
carries a `job_id`, its `kind`, the `lot` it ran on, the `items` it was asked
for, `repeats`, `reads_returned`, `units_charged`, `units_left_after`, a
`refusal` (null when the desk ran the job) and `rows`, the reads themselves.
Each row carries the `item`, its `kind`, the `lot`, the `slice_no` the desk
scored it on, `val_rows` and `val_score`. Fields beyond those are desk
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
    if isinstance(read, bool):
        return None
    if isinstance(read, int):
        return read
    if isinstance(read, float) and read.is_integer():
        return int(read)
    return None


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def jobs(value):
    if not isinstance(value, list):
        return None
    lines = []
    for item in value:
        if not isinstance(item, dict):
            return None
        lines.append(
            {
                "job_id": item.get("job_id"),
                "lot": item.get("lot"),
                "reads": whole(item.get("reads")),
                "units_charged": whole(item.get("units_charged")),
            }
        )
    return lines


def report_view(value):
    """One delivered readout in the shape the release tooling passes on."""

    if not isinstance(value, dict):
        return {}
    shipped = value.get("shipped_checkpoint")
    return {
        "shipped_checkpoint": shipped if isinstance(shipped, str) else None,
        "gain_points": number(value.get("gain_points")),
        "gain_range": interval(value.get("gain_range")),
        "jobs": jobs(value.get("jobs")),
        "units_left": whole(value.get("units_left")),
    }


def _items(value):
    if not isinstance(value, (list, tuple)):
        return None
    names = [item for item in value if isinstance(item, str) and item.strip()]
    return names if len(names) == len(list(value)) else None


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("job", value.get("action", value.get("request")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        kind = value.get("kind")
        if kind == "train" or (kind is None and "config" in value):
            return {
                "kind": "train",
                "config": value.get("config"),
                "runs": whole(value.get("runs")),
            }
        if kind == "reads" or "items" in value or "lot" in value:
            return {
                "kind": "reads",
                "lot": value.get("lot"),
                "items": _items(value.get("items")),
                "repeats": whole(value.get("repeats", 1)),
            }
    return None


def plan_view(value):
    """The next-job answer as a list of choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
