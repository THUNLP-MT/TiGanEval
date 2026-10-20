"""Loss at ten times the compute, read off the sweep summary table.

The trend Marek describes, with the line-by-line of what the sweep ran filled
in: a line through the final validation loss against log compute over every
job in the table, read at ten times the biggest job, the spread of the points
around the line beside it, and the width-512 run he asked for as the next
booking.
"""

from math import log, sqrt


NEXT_WIDTH = 512
NEXT_DATA = 160000


def trend(rows):
    """Slope and intercept of loss against log compute."""

    points = [(log(row["compute_units"]), row["final_val_loss"]) for row in rows]
    count = len(points)
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    across = sum((x - mean_x) * (y - mean_y) for x, y in points)
    spread = sum((x - mean_x) ** 2 for x, _ in points)
    slope = across / spread
    return slope, mean_y - slope * mean_x, points


def analyze(context, receipts):
    rows = context["runs"]
    slope, intercept, points = trend(rows)
    biggest = max(int(row["compute_units"]) for row in rows)
    target = int(context["target_multiple"]) * biggest
    predicted = intercept + slope * log(target)
    residuals = [y - (intercept + slope * x) for x, y in points]
    spread = sqrt(sum(value * value for value in residuals) / (len(residuals) - 2))
    return {
        "target_compute_units": target,
        "predicted_loss": predicted,
        "loss_interval": [predicted - spread, predicted + spread],
        "runs": [
            {
                "run_id": row["run_id"],
                "used": True,
                "compute_units": int(row["compute_units"]),
                "set_aside": None,
            }
            for row in rows
        ]
        + [
            {
                "run_id": item["run_id"],
                "used": True,
                "compute_units": int(item["compute_units_charged"]),
                "set_aside": None,
            }
            for item in receipts or ()
        ],
        "compute_units_left": int(context["queue"]["units_granted"])
        - sum(int(item["compute_units_charged"]) for item in receipts or ()),
    }


def next_run(context, receipts):
    """One more run at the next width up, on the shard the last runs used."""

    last = context["runs"][-1]
    return {
        "width": NEXT_WIDTH,
        "data": NEXT_DATA,
        "learning_rate": last["learning_rate"],
        "val_shard": last["val_shard_id"],
    }
