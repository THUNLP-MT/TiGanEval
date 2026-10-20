"""How the soak notebook is called and what it hands back.

This module ships with the reliability reporting tooling. The chamber tool and
the plan review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the report:

    {
      "hours_to_loss": ...,
      "hours_range": [low, high],
      "standing_laws": ["defect_growth", ...],
      "counted_rows": [{"source": ..., "rows": ..., "modules": ...}, ...],
      "blocks": [{"block_id": ..., "drive_a": ..., "case_temp_c": ...,
                  "ports": ..., "modules": ..., "rows": ..., "days_charged": ...}, ...]
    }

* `hours_to_loss` is a number of hours at the campaign's own field drive and
  hold, as `context` gives them.
* `hours_range` is two numbers of hours, low first.
* `standing_laws` names catalogue laws by the field names the catalogue uses.
* `counted_rows` says how many bench rows the figure was worked out of and how
  many modules they came from, split by where they came from. `source` is one
  of `ROW_SOURCES`: `"trace_export"` for a row the campaign's own export
  carries, `"receipt"` for one a chamber block returned.
* `blocks` is one entry per chamber block, with the `block_id` the desk wrote,
  the `drive_a` and `case_temp_c` it was booked at, the `ports` it asked for,
  the `modules` and `rows` it returned, and the `days_charged`.

`analysis.next_block(context, receipts)` returns the next block to put in front
of the chamber desk: `{"drive_a": 1.6, "case_temp_c": 90.0, "ports": 8,
"chamber_days": 3, "lot": "L-19"}`, or `"stop"`. `{"block": {...}}` and
`{"action": "stop"}` wrappers are read the same way. A list means the review
may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"1250.0"`, or exact
rational strings such as `"5000/4"`. Law names, lot names, block ids and the
source words are identities and are never read as numbers. Extra descriptive
keys are ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` is the same object as `soak_context.json`: the campaign, the family,
the build month, the drive and case temperature the specification is written
against, the share of output the figure is about, the meter's full scale and
its repeat spread, the reference source and the id its rows carry, the racks,
the decay catalogue, the module index, the whole trace export, the chamber
budget and its caps, what the shop holds in spares, when the rig is out for
service and the days the schedule is holding. `receipts` is the list of chamber
receipts in `soak_receipts.json`, oldest first; each has a `block_id`, the
`drive_a`, `case_temp_c`, `ports_asked`, `chamber_days_asked` and `lot` it was
booked with, the `modules` it drew with their incoming readings, the `readings`
it returned, the `modules_returned` and `rows_returned`, the `days_charged`,
the `days_left_after`, the day it was `served_on` and a `refusal` line where
the desk handed the sheet back. Fields beyond those are desk transport.
"""

from fractions import Fraction
from math import isfinite


#: The two places a counted row can have come from.
ROW_SOURCES = ("trace_export", "receipt")

#: The columns of the trace export.
TRACE_COLUMNS = (
    "module_id",
    "lot",
    "rack",
    "drive_a",
    "sample_index",
    "logged_at",
    "elapsed_h",
    "output_mw",
)


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


def law_names(value):
    """The laws a report says are standing, as a list of catalogue field names."""

    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return None
    return [item for item in value if isinstance(item, str)] if all(
        isinstance(item, str) for item in value
    ) else None


def counted_rows(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "source": item.get("source"),
                "rows": number(item.get("rows")),
                "modules": number(item.get("modules")),
            }
        )
    return rows


def blocks(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "block_id": item.get("block_id"),
                "drive_a": number(item.get("drive_a")),
                "case_temp_c": number(item.get("case_temp_c")),
                "ports": number(item.get("ports")),
                "modules": number(item.get("modules")),
                "rows": number(item.get("rows")),
                "days_charged": number(item.get("days_charged")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the reporting tooling passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "hours_to_loss": number(value.get("hours_to_loss")),
        "hours_range": interval(value.get("hours_range")),
        "standing_laws": law_names(value.get("standing_laws")),
        "counted_rows": counted_rows(value.get("counted_rows")),
        "blocks": blocks(value.get("blocks")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("block", value.get("action", value.get("session")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "drive_a" in value or "ports" in value:
            return {
                "drive_a": number(value.get("drive_a")),
                "case_temp_c": number(value.get("case_temp_c")),
                "ports": number(value.get("ports")),
                "chamber_days": number(value.get("chamber_days")),
                "lot": value.get("lot"),
            }
    return None


def plan_view(value):
    """The next-block answer as a list of tied choices the review may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
