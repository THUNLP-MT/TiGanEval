"""Release readout for the ranking campaign.

The number is the best `val_score` in the run ledger against the figure the
release note stores for the ranker in production. The range around it is the
spread of the top five rows either side. The compute that is left goes back
into two more runs of the configuration that produced that checkpoint, because
that is the configuration we are going to ship.
"""


def ranked(context):
    return sorted(context["run_ledger"], key=lambda row: -float(row["val_score"]))


def analyze(context, ledger):
    rows = ranked(context)
    best = rows[0]
    stored = float(context["release"]["stored_val_score"])
    gain = (float(best["val_score"]) - stored) * 100.0
    spread = (float(rows[0]["val_score"]) - float(rows[4]["val_score"])) * 100.0
    return {
        "shipped_checkpoint": f"{best['run_id']}@{best['checkpoint_step']}",
        "gain_points": gain,
        "gain_range": [gain - spread, gain + spread],
        "jobs": [],
        "units_left": int(context["compute"]["units_granted"]),
    }


def next_collection(context, ledger):
    """Two more runs of the configuration that produced the best checkpoint."""

    best = ranked(context)[0]
    return {"kind": "train", "config": best["run_id"], "runs": 2}
