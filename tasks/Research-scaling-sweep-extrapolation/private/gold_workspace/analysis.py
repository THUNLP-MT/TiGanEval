"""The scaling sweep readout notebook."""

from support import (
    charge,
    fit,
    reserved_shards,
    measured,
    ratio_band,
    reservation_days_left,
    reachable,
    repeat_spread,
    set_aside,
    target_scale,
    target_units,
    units_left,
)


#: How far outside the band of examples-per-width the sweep already covers a
#: new job has to sit before it tells the two exponents apart.
BAND_MARGIN = 1.5
#: The half-width of a range the sweep supports, in repeats of one setting.
SPREAD_MULTIPLE = 5.0
#: Bounds printed by the queue's submission form.
WIDTH_MIN, WIDTH_MAX = 8, 4096
DATA_MIN, DATA_MAX = 500, 4_000_000


def analyze(context, receipts):
    entries = measured(context, receipts)
    aside = set_aside(context, receipts)
    points = [
        (entry["width"], entry["data"], entry["final_val_loss"])
        for entry in entries
        if entry["run_id"] not in aside
    ]
    surface = fit(points)
    scale = target_scale(context)
    predicted = reachable(surface, scale)
    half = SPREAD_MULTIPLE * repeat_spread(context)
    return {
        "target_compute_units": target_units(context),
        "predicted_loss": predicted,
        "loss_interval": [predicted - half, predicted + half],
        "runs": [
            {
                "run_id": entry["run_id"],
                "used": entry["run_id"] not in aside,
                "compute_units": entry["compute_units"],
                "set_aside": aside.get(entry["run_id"]),
            }
            for entry in entries
        ],
        "compute_units_left": units_left(context, receipts),
    }


def candidates(context):
    """Every job that sits clear of the band the sweep already covers."""

    low, high = ratio_band(context)
    above, below = high * BAND_MARGIN, low / BAND_MARGIN
    found = []
    for width in range(WIDTH_MIN, WIDTH_MAX + 1):
        for data in (DATA_MIN, int(width * below), int(width * above) + 1):
            if not DATA_MIN <= data <= DATA_MAX:
                continue
            if not (data / width <= below or data / width >= above):
                continue
            found.append((charge(context, width, data), width, data))
    return found


def next_run(context, receipts):
    """The biggest job the queue will take that is clear of the band."""

    if reservation_days_left(context, receipts) <= 0:
        return "stop"
    left = units_left(context, receipts)
    cap = min(int(context["queue"]["job_cap_units"]), left)
    floor_units = int(context["queue"]["job_floor_units"])
    shards = reserved_shards(context)
    if cap < floor_units or not shards:
        return "stop"
    rate = min(float(row["learning_rate"]) for row in context["runs"])
    affordable = [item for item in candidates(context) if floor_units <= item[0] <= cap]
    if not affordable:
        return "stop"
    cost, width, data = max(affordable)
    return {
        "width": width,
        "data": data,
        "learning_rate": rate,
        "val_shard": shards[0],
        "compute_units": cost,
    }
