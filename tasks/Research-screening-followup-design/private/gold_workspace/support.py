"""Reading the bench evidence: which runs sit on one scale, and what is left."""

from math import sqrt


def selected_plate(context):
    return context["screen"]["selected_plate"]


def incumbent(context):
    return context["screen"]["incumbent_part"]


def blocks(context, receipts):
    """{(day, part): [rise, ...]} over the screen table and every rig day since."""

    found = {}
    for row in context["screen_runs"]:
        found.setdefault((row["day_id"], row["plate_id"]), []).append(float(row["rise_K"]))
    for receipt in receipts:
        for part in receipt["parts"]:
            if part["returned_runs"]:
                found.setdefault((receipt["day_id"], part["part"]), []).extend(
                    float(rise) for rise in part["rise_K"]
                )
    return found


def _spread(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def run_spread(context, receipts):
    """How far runs of one part on one day sit from each other, over every block."""

    weight = total = 0.0
    for values in blocks(context, receipts).values():
        variance = _spread(values)
        if variance is not None:
            total += (len(values) - 1) * variance
            weight += len(values) - 1
    return sqrt(total / weight) if weight else 0.0


def day_spread(context):
    """How far the screen days sit from each other, off the plates that ran on them."""

    plates = set(context["screen"]["plates"])
    by_day = {}
    for row in context["screen_runs"]:
        if row["plate_id"] in plates:
            by_day.setdefault(row["day_id"], []).append(float(row["score_K"]))
    means = [sum(values) / len(values) for values in by_day.values()]
    variance = _spread(means)
    return sqrt(variance) if variance else 0.0


def same_day_pairs(context, receipts):
    """{day: (plate runs, incumbent runs)} for days that carry both parts."""

    plate, other = selected_plate(context), incumbent(context)
    found = {}
    for receipt in receipts:
        got = {
            part["part"]: [float(rise) for rise in part["rise_K"]]
            for part in receipt["parts"]
            if part["returned_runs"]
        }
        if plate in got and other in got:
            found[receipt["day_id"]] = (got[plate], got[other])
    return found


def screen_effect(context):
    """The plate's screen score, which is the table's own number for it."""

    plate = selected_plate(context)
    scores = [
        float(row["score_K"]) for row in context["screen_runs"] if row["plate_id"] == plate
    ]
    return sum(scores) / len(scores) if scores else 0.0


def day_differences(context, receipts):
    """What each rig day carrying both parts says the plate is worth."""

    return [
        sum(other) / len(other) - sum(plate) / len(plate)
        for plate, other in same_day_pairs(context, receipts).values()
    ]


def effect_and_half_width(context, receipts):
    """The number for the review and how far it can still move."""

    pairs = same_day_pairs(context, receipts)
    scatter = run_spread(context, receipts)
    if pairs:
        differences = day_differences(context, receipts)
        effect = sum(differences) / len(differences)
        # How far one day's answer sits from another's is what the days
        # themselves show, once there are two of them to compare. With one day
        # there is nothing to compare, so the runs inside it are all there is.
        between = _spread(differences)
        term = sum(1.0 / len(plate) + 1.0 / len(other) for plate, other in pairs.values())
        within = scatter * sqrt(term) / len(pairs)
        error = max(sqrt(between / len(differences)), within) if between else within
        return effect, 2.0 * error
    plate = selected_plate(context)
    runs = [
        len(values) for (_day, part), values in blocks(context, receipts).items() if part == plate
    ]
    count = len(runs) or 1
    within = sum(1.0 / max(size, 1) for size in runs) / (count * count)
    move = day_spread(context)
    error = sqrt(move * move * (1.0 + 1.0 / count) + scatter * scatter * within)
    return screen_effect(context), 2.0 * error


def rig_days_left(context, receipts):
    return int(context["booking"]["rig_days_on_the_sheet"]) - len(receipts)


def _seating_spread(context, receipts):
    """How much of a day's difference the two mountings account for.

    Two rig days of the same pair do not give the same difference, and what is
    left once the runs inside each block are taken off is the mounting.
    """

    differences = day_differences(context, receipts)
    between = _spread(differences)
    if between is None:
        return 0.0
    scatter = run_spread(context, receipts)
    pairs = list(same_day_pairs(context, receipts).values())
    runs = sum(1.0 / len(plate) + 1.0 / len(other) for plate, other in pairs) / len(pairs)
    return sqrt(max(between - scatter * scatter * runs, 0.0) / 2.0)


def _day_variance(context, receipts, plate_runs, other_runs):
    scatter = run_spread(context, receipts)
    seating = _seating_spread(context, receipts)
    return 2.0 * seating * seating + scatter * scatter * (1.0 / plate_runs + 1.0 / other_runs)


def _width_after(context, receipts, plate_runs, other_runs, left):
    pairs = same_day_pairs(context, receipts)
    total = sum(
        _day_variance(context, receipts, len(plate), len(other))
        for plate, other in pairs.values()
    )
    total += left * _day_variance(context, receipts, plate_runs, other_runs)
    return 4.0 * sqrt(total) / (len(pairs) + left)


def day_sheet(context, receipts):
    """The sheet for the next rig day, or an empty sheet when there is nothing to book."""

    left = rig_days_left(context, receipts)
    if left <= 0:
        return []
    paired_days = len(same_day_pairs(context, receipts))
    _effect, half_width = effect_and_half_width(context, receipts)
    if (
        paired_days >= 2
        and 2.0 * half_width <= float(context["review"]["range_width_K"])
    ):
        return []
    capacity = int(context["booking"]["runs_per_day"])
    best = None
    for plate_runs in range(1, capacity):
        for other_runs in range(1, capacity - plate_runs + 1):
            width = _width_after(context, receipts, plate_runs, other_runs, left)
            if best is None or width < best[0]:
                best = (width, plate_runs, other_runs)
    return [
        {"part": selected_plate(context), "runs": best[1]},
        {"part": incumbent(context), "runs": best[2]},
    ]


def ledger_lines(receipts):
    """One line per rig day the review was charged for, in the order they ran."""

    return [
        {
            "receipt_id": receipt["receipt_id"],
            "day_id": receipt["day_id"],
            "runs_returned": sum(int(part["returned_runs"]) for part in receipt["parts"]),
        }
        for receipt in receipts
    ]
