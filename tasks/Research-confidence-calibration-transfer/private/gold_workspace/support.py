"""Reading a queue's evidence: what carries an outcome, what the stream is now,
and how far the number can still move on what has been adjudicated."""

import csv
from math import sqrt
import os

#: One chance in twenty across the run of queues the council reads together.
COVER = 2.5758
#: The smallest batch worth a trip to the desk.
BATCH_FLOOR = 40


_LOG = {}


def log_rows(context):
    """The intake log for the queue in hand, read once per queue."""

    path = context["intake_log_file"]
    stamp = (context["queue"], path, os.stat(path).st_size, os.stat(path).st_mtime_ns)
    if _LOG.get("stamp") != stamp:
        with open(path, newline="", encoding="utf-8") as handle:
            _LOG["stamp"], _LOG["rows"] = stamp, list(csv.DictReader(handle))
    return _LOG["rows"]


def served_shares(context):
    """The mixture the traffic report gives for the month just closed."""

    rows = context["channel_traffic"]
    total = sum(int(row["served_month_just_closed"]) for row in rows) or 1
    return {
        str(row["channel"]): int(row["served_month_just_closed"]) / total for row in rows
    }


def cleared(rows, cut):
    return [row for row in rows if float(row["stated_confidence"]) < float(cut)]


def written(rows):
    """The listings an adjudication has closed. An empty cell is not an outcome."""

    return [row for row in rows if str(row.get("review_outcome") or "").strip()]


def rate_of(rows):
    if not rows:
        return None
    violating = sum(1 for row in rows if row["review_outcome"] == "violating")
    return 100.0 * violating / len(rows)


def batch_rows(receipts):
    """The listings the desk has sent back, in the log's own shape."""

    return [row for entry in receipts for row in entry.get("observed", {}).get("rows", ())]


def evidence(context, receipts, cut=None):
    """Per channel: its share of the stream served now and what is written."""

    cut = context["review"]["cut_in_force"] if cut is None else cut
    rows = written(cleared(log_rows(context), cut)) + written(
        cleared(batch_rows(receipts), cut)
    )
    found = {}
    for channel, share in served_shares(context).items():
        held = [row for row in rows if row["channel"] == channel]
        found[channel] = {"share": share, "listings": len(held), "rate": rate_of(held)}
    return found


def combined(found):
    """The channels put back together in the proportions the traffic report gives."""

    weight = 0.0
    total = 0.0
    for row in found.values():
        if row["rate"] is None or row["share"] <= 0.0:
            continue
        weight += row["share"]
        total += row["share"] * row["rate"]
    return (total / weight) if weight else None


def half_width(found):
    """How far the published number can still move on what has been adjudicated.

    A channel with adjudicated listings behind it moves by its own sampling
    spread. A channel with a share of the stream and nothing written behind it
    at all is not narrowed by anything, so half its share is added straight on.
    """

    variance = 0.0
    unread = 0.0
    for row in found.values():
        share = row["share"]
        if share <= 0.0:
            continue
        if row["rate"] is None or not row["listings"]:
            unread += share * 50.0
            continue
        rate = row["rate"] / 100.0
        variance += share * share * rate * (1.0 - rate) / row["listings"]
    return COVER * sqrt(variance) * 100.0 + unread


def rate_at(context, receipts, cut):
    return combined(evidence(context, receipts, cut))


def recommended_cut(context, receipts):
    """The loosest band on the sheet whose rate holds under the bar."""

    bar = float(context["review"]["bar_points"])
    holding = [
        edge
        for edge in context["review"]["bands"]
        if (rate_at(context, receipts, edge) or 0.0) <= bar
    ]
    return max(holding) if holding else min(context["review"]["bands"])


def credits_used(receipts):
    return sum(int(entry["credits_charged"]) for entry in receipts)


def credits_left(context, receipts):
    return int(context["audit"]["credits_granted"]) - credits_used(receipts)


def batches(receipts):
    return [
        {
            "batch_id": entry["batch_id"],
            "listings_returned": int(entry["listings_returned"]),
            "credits_charged": int(entry["credits_charged"]),
        }
        for entry in receipts
    ]


def open_cells(context, receipts):
    """Every cell the desk could fill with a batch worth booking, best first.

    A cell is one channel and one intake plan. What it is worth is the
    channel's share of the stream served now multiplied by the part of that
    channel's auto-cleared listings it would put an outcome against.
    """

    cut = context["review"]["cut_in_force"]
    done = {row["listing_id"] for row in batch_rows(receipts)}
    shares = served_shares(context)
    held = {}
    backlog = {}
    waiting = {}
    for row in log_rows(context):
        channel = row["channel"]
        cell = (channel, row["intake_period"])
        auto = float(row["stated_confidence"]) < float(cut)
        if auto:
            held[channel] = held.get(channel, 0) + 1
        if str(row.get("review_outcome") or "").strip() or row["listing_id"] in done:
            continue
        backlog[cell] = backlog.get(cell, 0) + 1
        if auto:
            waiting[cell] = waiting.get(cell, 0) + 1
    found = []
    for cell, count in backlog.items():
        channel = cell[0]
        unit = int(context["audit"]["credit_cost"][channel])
        room = min(int(context["audit"]["max_listings_per_batch"]),
                   credits_left(context, receipts) // unit)
        if count < BATCH_FLOOR or room < BATCH_FLOOR:
            continue
        worth = shares.get(channel, 0.0) * waiting.get(cell, 0) / (held.get(channel) or 1)
        if worth <= 0.0:
            continue
        found.append((worth, cell, count, room))
    return sorted(found, key=lambda item: (-item[0], item[1]))
