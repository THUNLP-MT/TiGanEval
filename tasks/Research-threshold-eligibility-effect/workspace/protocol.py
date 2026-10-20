"""How the campaign notebook is called and what it hands back.

This module ships with the growth reporting stack. The campaign tool and the
council review both read a notebook through it, so it stays as it is.

`analysis.analyze(context, receipts)` returns the report:

    {
      "offer_effect_points": ...,
      "effect_range_points": [low, high],
      "account_days": ...,
      "lots": [{"receipt_id": ..., "files_charged": ..., "rows_returned": ...}, ...]
    }

* `offer_effect_points` is a difference in sixty-day order rate written in
  points: 1.4 reads as one and four tenths of a point.
* `effect_range_points` is two endpoints in those units, low first.
* `account_days` is a count of account-days: how much watching the
  number stands on.
* `lots` is a list of entries, each with a `receipt_id`, a `files_charged` and
  a `rows_returned`.

`analysis.next_review(context, receipts)` returns the lot to ask the file desk
for next: `{"week": 4, "band": 2.5, "above_share": 0.5, "files": 40}`, or
`"stop"`. `{"lot": {...}}` and `{"action": "stop"}` wrappers are read the same
way. A list means the growth desk may take any one of the entries in it.

Numbers may be JSON numbers, decimal strings such as `"1.35"`, or exact
rational strings such as `"27/20"`. A lot's `week` and `files` must resolve to
whole values; receipt ids and the stop are identities. Extra descriptive keys
are ignored, and a range may also be written `{"low": ..., "high": ...}`.

`context` carries the campaign's terms and its two tables. The terms are the
window, the line, the credit ceiling, the order window, the day the export
stops and how late an order reaches it, the review grant and the council's own
note; they are the same fields as `campaign_context.json`. The tables are `context["register"]`, one entry per
account with the columns of `project_records/offer_register.csv`, and
`context["recompute"]`, one entry per refreshed account with the columns of
`project_records/recompute_log.csv`. The copies of both under
`project_records/` are this campaign's own; the job hands the notebook the
market it is running on, which is not always this one.

`receipts` is the list of review receipts in `review_receipts.json`, oldest
first; each has a `receipt_id`, the `week`, `band`, `above_share` it asked
for, the `files_charged`, the `files_remaining` after it, the `rows_returned`
and a `refusal`, which is null when the desk served the lot. Fields beyond
those are desk transport.
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


def window(value):
    """A pair of endpoints, low first, from a list or a {low, high} object."""

    if isinstance(value, dict):
        value = [value.get("low"), value.get("high")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(item) for item in value]
    return None


def lots(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "receipt_id": item.get("receipt_id"),
                "files_charged": number(item.get("files_charged")),
                "rows_returned": number(item.get("rows_returned")),
            }
        )
    return rows


def report_view(value):
    """One notebook report in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "offer_effect_points": number(value.get("offer_effect_points")),
        "effect_range_points": window(value.get("effect_range_points")),
        "account_days": number(value.get("account_days")),
        "lots": lots(value.get("lots")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("lot", value.get("action", value.get("review")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "week" in value or "files" in value:
            return {
                "week": number(value.get("week")),
                "band": number(value.get("band")),
                "above_share": number(value.get("above_share")),
                "files": number(value.get("files")),
            }
    return None


def plan_view(value):
    """The next-lot answer as a list of tied choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
