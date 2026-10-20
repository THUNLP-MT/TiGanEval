"""Quarterly capacity readout for the reservation platform.

The peak wait a quarter reaches, taken over every draw the sampler has stored
this quarter, with how far that average could still move. The grant that is left
buys two more runs started from scratch, which is what `next_run` asks for.
"""

from math import sqrt


def analyze(context, receipts):
    values = []
    for chain in context["chains"]:
        values.extend(chain["draws"]["peak_wait_s"])
    count = len(values)
    middle = sum(values) / count
    spread = sum((value - middle) ** 2 for value in values) / (count - 1)
    error = sqrt(spread / count)
    return {
        "answer": round(middle, 3),
        "answer_range": [middle - 1.96 * error, middle + 1.96 * error],
        "steps_kept": count,
        "steps_set_aside": 0,
        "runs": [],
        "jobs": [],
    }


def next_run(context, receipts):
    """Two more runs from scratch, as long as the grant will carry them."""

    return {"start": "new", "steps": 6000}
