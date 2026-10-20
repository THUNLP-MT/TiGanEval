"""Escalation error for the shipped triage pipeline.

The pipeline's error is read off the reserved Ridgeline split, the rows the
March fit did not train on, with the usual interval around it. The rest of the
quarter's review units go back into the Ridgeline queue, which is where the
pipeline has been measured since it was built.
"""

import csv
from math import sqrt


RESERVED_FILE = "ridgeline_reserved_split.csv"


def reserved_rows(path=RESERVED_FILE):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def analyze(context, ledger):
    rows = reserved_rows()
    wrong = sum(
        1 for row in rows if row["pipeline_decision"] != row["reviewed_label"]
    )
    rate = wrong / len(rows)
    spread = 1.96 * sqrt(rate * (1.0 - rate) / len(rows))
    return {
        "served_error": rate,
        "error_interval": [rate - spread, rate + spread],
        "groups": [],
        "reviews": [],
        "units_used": 0,
    }


def next_collection(context, ledger):
    """More of the split the pipeline has always been measured on."""

    return {"site": "ridgeline", "channel": "queue", "rows": 200}
