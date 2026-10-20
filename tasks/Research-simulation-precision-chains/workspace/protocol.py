"""How a quarter's notebook is called and what it hands back.

This module ships with the capacity reporting stack. The study tool and the
quarterly review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "answer": ...,
      "answer_range": [low, high],
      "steps_kept": ...,
      "steps_set_aside": ...,
      "runs": [{"chain_id": ..., "steps_stored": ..., "steps_kept": ...,
                "steps_set_aside": ...}, ...],
      "jobs": [{"call_id": ..., "steps_charged": ..., "refused": ...}, ...]
    }

* `answer` is the number the review takes from the study, in whatever units the
  quarter's charter asks the study for. `capacity_charter.md` states the ask.
* `answer_range` is two endpoints for that number, low first, in those units.
* `steps_kept` and `steps_set_aside` are whole numbers of sampler steps and are
  what the readout says it read and what it says it left out.
* `runs` is one entry per stored run, each with a `chain_id`, the
  `steps_stored` the manifest carries for it, and the `steps_kept` and
  `steps_set_aside` of that run.
* `jobs` is one entry per console receipt, each with the receipt's `call_id`,
  the `steps_charged` the console billed, and `refused` true or false.

`analysis.next_run(context, receipts)` returns the next job to put to the
console: `{"chain_id": "run-c", "steps": 2400}` to carry a stored run on, or
`{"start": "new", "steps": 3000}` to open a fresh one, or `"stop"`.
`{"job": {...}}` and `{"action": "stop"}` wrappers are read the same way. A list
means the group may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"0.095"`, or exact
rational strings such as `"19/200"`. Run ids, call ids and `"stop"` are
identities and are never read as numbers. Extra descriptive keys are ignored,
and a range may also be written `{"low": ..., "high": ...}`.

`context` is what the reporting job publishes for one quarter: the study and
quarter labels, the day the files were pulled, the charter's commitment, the
compute grant's terms, and `chains`, one entry per stored run with its
`chain_id`, `node`, `job_id`, `steps_stored`, `init_source` and a `draws` object
holding the run's stored columns as equal-length lists in step order
(`arrival_rate`, `service_rate`, `peak_wait_s`, `step_size`, `accepted`). The
same rows are on disk in `chains/<chain_id>.csv`, numbered from step 1.
`receipts` is the list of console receipts in `collection_receipts.json`, oldest
first; each has a `call_id`, a `job_id`, the `chain_id` it ran on or null, the
`init_source` the manifest carries for that run, `steps_requested`, `steps_returned`,
`steps_charged`, a `refusal` line or null, and the `steps_left` the console
wrote after it. Fields beyond those are console transport.
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


def interval(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def runs(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "chain_id": item.get("chain_id"),
                "steps_stored": number(item.get("steps_stored")),
                "steps_kept": number(item.get("steps_kept")),
                "steps_set_aside": number(item.get("steps_set_aside")),
            }
        )
    return rows


def jobs(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "call_id": item.get("call_id"),
                "steps_charged": number(item.get("steps_charged")),
                "refused": bool(item.get("refused")),
            }
        )
    return rows


def report_view(value):
    """One notebook readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "answer": number(value.get("answer")),
        "answer_range": interval(value.get("answer_range")),
        "steps_kept": number(value.get("steps_kept")),
        "steps_set_aside": number(value.get("steps_set_aside")),
        "runs": runs(value.get("runs")),
        "jobs": jobs(value.get("jobs")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("job", value.get("action", value.get("plan")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if any(key in value for key in ("steps", "chain_id", "start", "new_run")):
            start = value.get("start")
            fresh = start in ("new", True) or value.get("new_run") is True
            chain_id = value.get("chain_id")
            names_run = isinstance(chain_id, str) and bool(chain_id)
            #: A step count by itself is not a job. The stack has to retain the
            #: distinction between carrying one stored run on and opening a new
            #: dispersed run, because the scheduler handles them differently.
            if "steps" not in value or names_run == fresh:
                return None
            return {
                "chain_id": None if fresh else chain_id,
                "steps": number(value.get("steps")),
                "start_new": bool(fresh),
            }
    return None


def plan_view(value):
    """The next-job answer as a list of tied choices the group may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
