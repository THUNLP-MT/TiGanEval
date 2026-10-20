"""Quarterly capacity readout for the reservation platform.

Nadia's method, filled out to the shape the reporting stack reads a notebook
through: the peak wait a quarter reaches, over every draw the sampler has stored
this quarter, with the standard error of that average, plus the run and job
lines the stack asks for. The grant that is left buys two more runs started from
scratch.
"""

from math import sqrt


def analyze(context, receipts):
    values = []
    runs = []
    for chain in context["chains"]:
        draws = chain["draws"]["peak_wait_s"]
        values.extend(draws)
        runs.append(
            {
                "chain_id": chain["chain_id"],
                "steps_stored": len(draws),
                "steps_kept": len(draws),
                "steps_set_aside": 0,
            }
        )
    count = len(values)
    middle = sum(values) / count
    spread = sum((value - middle) ** 2 for value in values) / (count - 1)
    error = sqrt(spread / count)
    return {
        "answer": round(middle, 3),
        "answer_range": [middle - 1.96 * error, middle + 1.96 * error],
        "steps_kept": count,
        "steps_set_aside": 0,
        "runs": runs,
        "jobs": [
            {
                "call_id": entry["call_id"],
                "steps_charged": entry["steps_charged"],
                "refused": bool(entry.get("refusal")),
            }
            for entry in receipts
        ],
    }


def next_run(context, receipts):
    """Two more runs from scratch, as long as the grant will carry them."""

    return {"start": "new", "steps": 6000}
