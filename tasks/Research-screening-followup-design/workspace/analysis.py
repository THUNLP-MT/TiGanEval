"""What P-07 is worth, off the screen table, and where the last rig days go.

The plate's screen score is what it scored, so that is the number. The spread
around it comes from the runs behind it, screen runs and confirming runs
together. The days that are left go on more runs of the plate.
"""

from math import sqrt

Z = 1.96


def _runs_of(context, receipts, plate):
    """Every score the bench has for one plate: screen runs and later runs."""

    baseline = float(context["stored_baseline"]["rise_K"])
    scores = [
        float(row["score_K"])
        for row in context["screen_runs"]
        if row["plate_id"] == plate
    ]
    for receipt in receipts:
        for part in receipt["parts"]:
            if part["part"] == plate:
                scores.extend(baseline - float(rise) for rise in part["rise_K"])
    return scores


def _screen_scores(context, plate):
    return [
        float(row["score_K"])
        for row in context["screen_runs"]
        if row["plate_id"] == plate
    ]


def analyze(context, receipts):
    plate = context["screen"]["selected_plate"]
    screen = _screen_scores(context, plate)
    effect = sum(screen) / len(screen)
    scores = _runs_of(context, receipts, plate)
    if len(scores) > 1:
        mean = sum(scores) / len(scores)
        spread = sqrt(sum((score - mean) ** 2 for score in scores) / (len(scores) - 1))
        half = Z * spread / sqrt(len(scores))
    else:
        half = 0.0
    return {
        "plate": plate,
        "effect_K": effect,
        "effect_range_K": [effect - half, effect + half],
        "measurements": [],
    }


def next_collection(context, receipts):
    """The days that are left go on the plate the review is about."""

    plate = context["screen"]["selected_plate"]
    return {"day": [{"part": plate, "runs": context["booking"]["runs_per_day"]}]}
