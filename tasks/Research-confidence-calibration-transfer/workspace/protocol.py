"""How the review reporting stack calls the notebook and what it hands back.

This module ships with the listing review reporting stack. The council pack
and the adjudication desk's tool both read a notebook through it, so it stays
as it is.

`analysis.analyze(context, receipts)` returns the readout:

    {
      "escape_rate": ...,
      "escape_interval": [low, high],
      "recommended_cut": ...,
      "listings_adjudicated": ...,
      "batches": [{"batch_id": ..., "listings_returned": ...,
                   "credits_charged": ...}, ...],
      "credits_used": ...
    }

* `escape_rate` is in points: 3.6 means three point six auto-cleared listings
  in a hundred, and higher is worse.
* `escape_interval` is two endpoints in those same points, low first.
* `recommended_cut` is a printed confidence, one of the sheet's ten bands in
  `context["review"]["bands"]`.
* `listings_adjudicated` is a whole number of listings.
* `batches` is a list of entries, each with a `batch_id`, the
  `listings_returned` the desk sent back and the `credits_charged`.
* `credits_used` is a whole number of credits.

`analysis.next_batch(context, receipts)` returns the next batch to book:

    {"channel": ..., "period": ..., "listings": ...}

or `"stop"`. `{"batch": {...}}` and `{"action": "stop"}` wrappers are read the
same way, and a list means the desk may take any one of the entries in it.

Numbers may be JSON numbers or decimal strings such as `"3.62"`. Channel
names, intake plan names, band names and batch ids are identities and are
never read as numbers. Extra descriptive keys are ignored, and an interval may
also be written `{"low": ..., "high": ...}`.

`context` is the queue as the reporting stack publishes it: the `queue` and
`desk` names, the `window`, `as_of`, `intake_log_file`, the `review` terms
(`cut_in_force`, `bar_points`, `bands`), the `audit` terms
(`credits_granted`, `max_listings_per_batch`, `credit_cost` per channel,
`empty_cell_charge`) and `channel_traffic`, the same table as the traffic
report in the workspace. `intake_log_file` names the intake log for the queue
in hand, written beside the notebook with the columns the workspace copy
carries. `receipts` is the list of batch receipts in `audit_receipts.json`,
oldest first; each carries a `batch_id`, the `channel` and `period` of the
cell it named, `listings_requested`, `listings_returned`,
`violating_returned`, `credits_charged`, `credits_remaining`, a `refusal` (or
null) and `observed.rows`, the adjudicated listings themselves. Fields beyond
those are desk transport.
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


def batches(value):
    if not isinstance(value, list):
        return None
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return None
        rows.append(
            {
                "batch_id": item.get("batch_id"),
                "listings_returned": whole(item.get("listings_returned")),
                "credits_charged": whole(item.get("credits_charged")),
            }
        )
    return rows


def report_view(value):
    """One delivered readout in the shape the reporting stack passes on."""

    if not isinstance(value, dict):
        return {}
    return {
        "escape_rate": number(value.get("escape_rate")),
        "escape_interval": interval(value.get("escape_interval")),
        "recommended_cut": number(value.get("recommended_cut")),
        "listings_adjudicated": whole(value.get("listings_adjudicated")),
        "batches": batches(value.get("batches")),
        "credits_used": whole(value.get("credits_used")),
    }


def _choice(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("batch", value.get("action", value.get("request")))
        if isinstance(inner, (str, dict)) and inner is not value:
            return _choice(inner)
        if "channel" in value or "listings" in value:
            return {
                "channel": value.get("channel"),
                "period": value.get("period"),
                "listings": whole(value.get("listings")),
            }
    return None


def plan_view(value):
    """The next-batch answer as a list of choices the desk may take."""

    items = value if isinstance(value, list) else [value]
    choices = [_choice(item) for item in items]
    return choices if choices and all(item is not None for item in choices) else None
