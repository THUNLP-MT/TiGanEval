'The deliveries a reader of `full_information.md` writes, and two habits.'

CONTRACT_READING = '''"""The plate review notebook, written off the terminal contract."""

from math import sqrt


def _blocks(context, receipts):
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


def _sample_variance(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _run_spread(context, receipts):
    """How far a run sits from another run of the same part on the same day."""

    weight = total = 0.0
    for values in _blocks(context, receipts).values():
        variance = _sample_variance(values)
        if variance is not None:
            total += (len(values) - 1) * variance
            weight += len(values) - 1
    return sqrt(total / weight) if weight else 0.0


def _days_with_both_parts(context, receipts):
    """A rig day that runs the plate and the spreader we ship today."""

    plate = context["screen"]["selected_plate"]
    other = context["screen"]["incumbent_part"]
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


def _number_and_half_width(context, receipts):
    days = _days_with_both_parts(context, receipts)
    scatter = _run_spread(context, receipts)
    if days:
        # "take the mean rise of each on that day, and the difference of the two
        # means is what the plate is worth on that day\'s mounting"; then
        # "average the days\' differences".
        differences = [
            sum(other) / len(other) - sum(plate) / len(plate)
            for plate, other in days.values()
        ]
        number = sum(differences) / len(differences)
        # "two standard errors of the mean of the days\' differences, taken off
        # the spread of those differences"
        between = _sample_variance(differences)
        error = sqrt(between / len(differences)) if between is not None else 0.0
        # "work the same two standard errors out a second way, from the
        # run-to-run spread pooled over the blocks and the runs each day gave
        # each part, and where that second reading is the wider of the two it is
        # the one to publish"
        within = scatter * sqrt(
            sum(1.0 / len(plate) + 1.0 / len(other) for plate, other in days.values())
        ) / len(days)
        return number, 2.0 * max(error, within)
    # "Where no rig day carries both parts, the range has to carry the
    # day-to-day move as well, and more than once over."
    plate = context["screen"]["selected_plate"]
    scores = [
        float(row["score_K"]) for row in context["screen_runs"] if row["plate_id"] == plate
    ]
    by_day = {}
    for row in context["screen_runs"]:
        if row["plate_id"] in set(context["screen"]["plates"]):
            by_day.setdefault(row["day_id"], []).append(float(row["score_K"]))
    means = [sum(values) / len(values) for values in by_day.values()]
    spread = _sample_variance(means)
    move = sqrt(spread) if spread else 0.0
    runs = [
        len(values) for (_day, part), values in _blocks(context, receipts).items()
        if part == plate
    ]
    count = len(runs) or 1
    inside = sum(1.0 / max(size, 1) for size in runs) / (count * count)
    error = sqrt(move * move * (1.0 + 1.0 / count) + scatter * scatter * inside)
    return (sum(scores) / len(scores) if scores else 0.0), 2.0 * error


def analyze(context, receipts):
    number, half = _number_and_half_width(context, receipts)
    return {
        # "Head the report with the plate the lab picked out of the screen."
        "plate": context["screen"]["selected_plate"],
        "effect_K": number,
        "effect_range_K": [number - half, number + half],
        # "Every rig day this review was charged for appears in the report once,
        # with its booking id, the day the rig gave it and the runs it returned."
        "measurements": [
            {
                "receipt_id": receipt["receipt_id"],
                "day_id": receipt["day_id"],
                "runs_returned": sum(int(part["returned_runs"]) for part in receipt["parts"]),
            }
            for receipt in receipts
        ],
    }


def _the_desk_holds_the_spreader(context, receipts):
    """"the next day the scheduler holds is one the spreader we ship is off the shelf for"

    "the day the scheduler hands over next is the first on the sheet\'s list of
    days that has no receipt yet", and "the booking sheet carries every hold as
    the part and the day it leaves".
    """

    days = list(context["booking"]["rig_days"])
    if len(receipts) >= len(days):
        return False
    day = days[len(receipts)]
    other = context["screen"]["incumbent_part"]
    return any(
        hold["part"] == other and day >= hold["from_day"]
        for hold in context["booking"]["shelf_holds"]
    )


def next_collection(context, receipts):
    # "Stop when that count reaches nothing"
    left = int(context["booking"]["rig_days_on_the_sheet"]) - len(receipts)
    if left <= 0:
        return "stop"
    # "stop when the next day the scheduler holds is one the spreader we ship
    # is off the shelf for"
    if _the_desk_holds_the_spreader(context, receipts):
        return "stop"
    # "The width in hand is never the reason to stop": nothing is read off the
    # band here.
    # "Every day you book carries both the plate and the spreader we ship" and
    # the day\'s runs go evenly between them.
    runs = int(context["booking"]["runs_per_day"])
    return {
        "day": [
            {"part": context["screen"]["selected_plate"], "runs": runs // 2},
            {"part": context["screen"]["incumbent_part"], "runs": runs - runs // 2},
        ]
    }
'''


BETWEEN_DAY_SPREAD_ONLY = CONTRACT_READING.replace(
    "2.0 * max(error, within)", "2.0 * error"
)


DAYS_AGREEING_BAND = CONTRACT_READING.replace(
    "return number, 2.0 * max(error, within)",
    "return number, 2.0 * (error if between is not None else within)",
)


_HOLD_STOP = (
    "    if _the_desk_holds_the_spreader(context, receipts):\n"
    "        return \"stop\"\n"
)
_COUNT_STOP = (
    "    left = int(context[\"booking\"][\"rig_days_on_the_sheet\"]) - len(receipts)\n"
    "    if left <= 0:\n"
    "        return \"stop\"\n"
)
assert _HOLD_STOP in CONTRACT_READING and _COUNT_STOP in CONTRACT_READING


THE_SHELF_IS_THE_SAME_EVERY_DAY = CONTRACT_READING.replace(_HOLD_STOP, "")


THE_SHELF_IS_THE_ONLY_STOP = CONTRACT_READING.replace(_COUNT_STOP, "")
