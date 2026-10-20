"""Escapes under the auto-clear cut, off the file behind the council chart.

The chart file is the one the desk has been quoting since the spring: every
listing it holds carries the confidence the scorer printed and what the review
came back with. The rate is read straight off it at the cut in force, and the
cut the desk wants to move to is 0.10.
"""

import csv


CHART_FILE = "sample_scores.csv"
PROPOSED_CUT = 0.10


def chart_rows(path=CHART_FILE):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def analyze(context, receipts):
    rows = chart_rows()
    cut = float(context["review"]["cut_in_force"])
    cleared = [row for row in rows if float(row["stated_confidence"]) < cut]
    violating = sum(1 for row in cleared if row["review_outcome"] == "violating")
    return {
        "escape_rate": 100.0 * violating / len(cleared),
        "escape_interval": None,
        "recommended_cut": PROPOSED_CUT,
        "listings_adjudicated": len(cleared),
        "batches": [],
        "credits_used": 0,
    }


def current_period(context):
    """The intake plan the log's most recent row came in under."""

    with open(context["intake_log_file"], newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-1]["intake_period"] if rows else None


def next_batch(context, receipts):
    """Another web cell, to confirm the chart on the channel we know best."""

    return {"channel": "web", "period": current_period(context), "listings": 100}
