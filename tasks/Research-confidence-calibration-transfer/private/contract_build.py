'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The auto-clear readout, written to the terms the council set."""

import csv
from math import sqrt
import os

#: "any of the five queues this readout is for: one chance in twenty across the
#: run of them, not one in twenty per queue". The chance is spent on the one
#: range the queue prints and not again on each channel's own movement inside
#: it, so the run of queues is the whole of the family.
QUEUES = 5
CHANCE = 0.05
#: "Stop only when no cell left holds forty listings the credits can pay for".
FLOOR = 40


def _quantile(p):
    """The two-sided normal cover for a tail probability, worked out here."""

    # Acklam's rational approximation, refined once by bisection so the build
    # does not depend on a table.
    low, high = 0.0, 10.0
    for _ in range(200):
        middle = (low + high) / 2.0
        # A normal tail through the complementary error function.
        tail = 0.5 * _erfc(middle / sqrt(2.0))
        if tail > p:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _erfc(x):
    """Complementary error function, Numerical-Recipes style."""

    z = abs(x)
    t = 2.0 / (2.0 + z)
    y = t * 2.0 - 1.0
    coefficients = (
        -1.3026537197817094, 6.4196979235649026e-1, 1.9476473204185836e-2,
        -9.561514786808631e-3, -9.46595344482036e-4, 3.66839497852761e-4,
        4.2523324806907e-5, -2.0278578112534e-5, -1.624290004647e-6,
        1.303655835580e-6, 1.5626441722e-8, -8.5238095915e-8,
        6.529054439e-9, 5.059343495e-9, -9.91364156e-10,
    )
    d = dd = 0.0
    for c in reversed(coefficients[1:]):
        d, dd = y * d - dd + c, d
    answer = t * 2.718281828459045 ** (-z * z + 0.5 * (coefficients[0] + y * d) - dd)
    return answer if x >= 0.0 else 2.0 - answer


_SEEN = {}


def _rows(context):
    """Every row of the queue's log, parsed once per queue."""

    path = context["intake_log_file"]
    stamp = (context["queue"], os.stat(path).st_size, os.stat(path).st_mtime_ns)
    if _SEEN.get("stamp") != stamp:
        with open(path, newline="", encoding="utf-8") as handle:
            _SEEN["stamp"], _SEEN["rows"] = stamp, list(csv.DictReader(handle))
    return list(_SEEN["rows"])


def _from_batches(receipts):
    for entry in receipts:
        for row in entry.get("observed", {}).get("rows", ()):
            yield row


def _shares(context):
    table = context["channel_traffic"]
    total = 0
    served = {}
    for line in table:
        served[str(line["channel"])] = int(line["served_month_just_closed"])
        total += int(line["served_month_just_closed"])
    return {name: count / (total or 1) for name, count in served.items()}


def _counters(context, receipts, cut):
    """One pass: per channel, how many carry an outcome and how many violate.

    "read a channel's rate over every row the log holds for it, whichever
    intake plan it came in under": the intake_period column is never looked at
    here. It settles the mix, which the traffic report gives, and not which
    rows a channel's own rate is read over.
    """

    written = {}
    violating = {}
    for row in list(_rows(context)) + list(_from_batches(receipts)):
        if float(row["stated_confidence"]) >= float(cut):
            continue
        outcome = (row.get("review_outcome") or "").strip()
        if not outcome:
            continue
        channel = row["channel"]
        written[channel] = written.get(channel, 0) + 1
        if outcome == "violating":
            violating[channel] = violating.get(channel, 0) + 1
    return written, violating


def _rate(context, receipts, cut):
    written, violating = _counters(context, receipts, cut)
    shares = _shares(context)
    carried = 0.0
    total = 0.0
    for channel, share in shares.items():
        if not written.get(channel):
            continue
        carried += share
        total += share * 100.0 * violating.get(channel, 0) / written[channel]
    return (total / carried) if carried else None


def analyze(context, receipts):
    cut = float(context["review"]["cut_in_force"])
    written, violating = _counters(context, receipts, cut)
    shares = _shares(context)
    centre = _rate(context, receipts, cut)

    # "the range the queue prints is the tightest one that still holds at that
    # level once those movements are put together ... those movements are not
    # laid end to end": each channel's own movement is carried at its share and
    # the movements are put together rather than added one onto the next. A
    # channel with a share and nothing adjudicated behind it is the exception
    # the same sentence names, and its whole share stays open on top.
    cover = _quantile(CHANCE / (2.0 * QUEUES))
    variance = 0.0
    unread = 0.0
    for channel, share in shares.items():
        if share <= 0.0:
            continue
        held = written.get(channel, 0)
        if not held:
            unread += 50.0 * share
            continue
        rate = violating.get(channel, 0) / held
        variance += share * share * rate * (1.0 - rate) / held
    spread = cover * sqrt(variance) * 100.0 + unread

    bands = list(context["review"]["bands"])
    bar = float(context["review"]["bar_points"])
    chosen = bands[0]
    for edge in sorted(bands, reverse=True):
        here = _rate(context, receipts, edge)
        if here is not None and here <= bar:
            chosen = edge
            break

    return {
        "escape_rate": centre,
        "escape_interval": None if centre is None else [
            max(0.0, centre - spread), min(100.0, centre + spread)
        ],
        "recommended_cut": chosen,
        # "Print how many adjudicated listings the number stands on": the rows
        # the rate above was read over, which is the same counters — under the
        # cut in force and carrying an outcome — and not every closed row in
        # the export.
        "listings_adjudicated": sum(written.values()),
        "batches": [
            {
                "batch_id": entry["batch_id"],
                "listings_returned": int(entry["listings_returned"]),
                "credits_charged": int(entry["credits_charged"]),
            }
            for entry in receipts
        ],
        "credits_used": sum(int(entry["credits_charged"]) for entry in receipts),
    }


def next_batch(context, receipts):
    cut = float(context["review"]["cut_in_force"])
    left = int(context["audit"]["credits_granted"]) - sum(
        int(entry["credits_charged"]) for entry in receipts
    )
    done = set()
    for entry in receipts:
        for row in entry.get("observed", {}).get("rows", ()):
            done.add(row["listing_id"])

    # "counted over every auto-cleared listing the export holds for that
    # channel, both intake plans together, and taking the whole of that cell's
    # backlog rather than the slice one batch would bring back": `cleared`
    # counts a channel over the whole log and `waiting` counts a cell's whole
    # backlog, neither of them capped by what a batch could carry.
    cleared = {}
    waiting = {}
    sitting = {}
    for row in _rows(context):
        channel = row["channel"]
        cell = (channel, row["intake_period"])
        auto = float(row["stated_confidence"]) < cut
        if auto:
            cleared[channel] = cleared.get(channel, 0) + 1
        if (row.get("review_outcome") or "").strip() or row["listing_id"] in done:
            continue
        sitting[cell] = sitting.get(cell, 0) + 1
        if auto:
            waiting[cell] = waiting.get(cell, 0) + 1

    shares = _shares(context)
    best = None
    for cell, count in sorted(sitting.items()):
        channel = cell[0]
        cost = int(context["audit"]["credit_cost"][channel])
        room = min(int(context["audit"]["max_listings_per_batch"]), left // cost)
        if count < FLOOR or room < FLOOR:
            continue
        worth = shares.get(channel, 0.0) * waiting.get(cell, 0) / max(1, cleared.get(channel, 0))
        if worth <= 0.0:
            continue
        if best is None or worth > best[0]:
            best = (worth, cell, min(count, room))
    if best is None:
        return "stop"
    return {"channel": best[1][0], "period": best[1][1], "listings": best[2]}
'''

SUPPORT = '''"""Everything this readout needs is in analysis.py."""
'''

FILES = {"analysis.py": REPORT, "support.py": SUPPORT}
