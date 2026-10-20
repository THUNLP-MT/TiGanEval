"""How the sweep readout is called and what it hands back.

This module ships with the group's reporting stack. The sweep tool and the
compute review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "target_compute_units": ...,
      "predicted_loss": ...,
      "loss_interval": [low, high],
      "runs": [{"run_id": ..., "used": ..., "compute_units": ...,
                "set_aside": ...}, ...],
      "compute_units_left": ...
    }

* `target_compute_units` is a number of queue units.
* `predicted_loss` is a validation loss in the same units as the
  `final_val_loss` column, and is the loss reached at `target_compute_units`.
* `loss_interval` is two endpoints in those units, low first.
* `runs` is a list of entries, each with a `run_id`, a `used` flag that is
  `true` or `false`, the `compute_units` that job was charged, and, when
  `used` is `false`, a `set_aside` line saying why.
* `compute_units_left` is a number of queue units.

`analysis.next_run(context, receipts)` returns the job to book next:
`{"width": 256, "data": 90000, "learning_rate": 0.02, "val_shard": "val-c"}`,
or `"stop"`. `{"job": {...}}` and `{"action": "stop"}` wrappers are read the
same way. A list means the scheduler may take any one of the entries in it.

Numbers may be JSON numbers or decimal strings such as `"1.4821"`. Run ids,
shard ids and the stop word are identities and are never read as numbers.
Extra descriptive keys are ignored, and an interval may also be written
`{"low": ..., "high": ...}`.

`context` is the same object as `sweep_context.json`: the queue's terms, the
block table, the shard table, the summary row of every job the sweep ran, the
loss curve each job wrote, and the change log. `receipts` is the list of queue
receipts in `sweep_receipts.json`, oldest first; each has a `job_id`, a
`run_id`, the settings the job ran at, the `compute_units_charged` and its
`observed` return. Fields beyond those are queue transport.
"""

from math import isfinite


def number(value):
    """Read one measurement. An identity or an unreadable display stays as it is."""

    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (int, float)):
        return value if isfinite(value) else None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def accounting(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "run_id": item.get("run_id"),
                "used": item.get("used"),
                "compute_units": number(item.get("compute_units")),
                "set_aside": item.get("set_aside"),
            }
        )
    return rows


def report_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "target_compute_units": number(value.get("target_compute_units")),
        "predicted_loss": number(value.get("predicted_loss")),
        "loss_interval": interval(value.get("loss_interval")),
        "runs": accounting(value.get("runs")),
        "compute_units_left": number(value.get("compute_units_left")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("job", value.get("action", value.get("run")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "width" in value or "data" in value:
            return {
                "width": number(value.get("width")),
                "data": number(value.get("data")),
                "learning_rate": number(value.get("learning_rate")),
                "val_shard": value.get("val_shard"),
            }
    return None


def plan_view(value):
    """The next-job answer as a list of tied choices the scheduler may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
