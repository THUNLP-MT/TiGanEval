"""Helpers for the header apportionment notebook."""

from math import sqrt

#: The analyser is dwell-limited, so a thirty-minute slot costs two.
LONG_DWELL_SLOTS = 2
#: How many degrees a plant-room reading has to sit from the sheet's own day
#: before the drop between them says anything about the dosing rate.
LEVER_MIN = 3.0
#: The width the report is asked for: two readings' worth each side.
SPREAD = 2.0


def solve3(rows, rhs):
    """Gaussian elimination on a three-by-three system."""

    grid = [[float(value) for value in row] + [float(rhs[index])]
            for index, row in enumerate(rows)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(grid[index][column]))
        if abs(grid[pivot][column]) < 1e-12:
            raise ZeroDivisionError("the three signatures do not separate")
        grid[column], grid[pivot] = grid[pivot], grid[column]
        for index in range(3):
            if index == column:
                continue
            factor = grid[index][column] / grid[column][column]
            for position in range(column, 4):
                grid[index][position] -= factor * grid[column][position]
    return [grid[index][3] / grid[index][index] for index in range(3)]


def supplies(context):
    return list(context["supplies"])


def temperatures(context):
    return {str(row["day"]): float(row["outdoor_C"]) for row in context["weather"]}


def heat(context):
    return {str(row["day"]): float(row["delivered_kwh"]) for row in context["heat_meter"]}


def in_window(context, day):
    window = context["window"]
    return str(window["first_day"]) <= str(day) <= str(window["last_day"])


def minutes(stamp):
    hour, minute = str(stamp)[11:16].split(":")
    return int(hour) * 60 + int(minute)


def clock(text):
    hour, minute = str(text).split(":")
    return int(hour) * 60 + int(minute)


def held_open(context, stamp):
    """Whether the operations log had an entry open when a sample was drawn."""

    day = str(stamp)[:10]
    when = minutes(stamp)
    for entry in context["operations"]:
        if str(entry["day"]) == day and clock(entry["from"]) <= when < clock(entry["to"]):
            return True
    return False


def header_rows(context):
    """The header slots inside the window that carry both channels."""

    return [
        row
        for row in context["samples"]
        if str(row["point"]) == "header"
        and in_window(context, str(row["taken_at"])[:10])
        and row.get("cond_uScm") is not None
        and row.get("mark_flag") == "value"
    ]


def split(context):
    """The header slots this reading stands on, and the ones set aside."""

    kept, aside = [], []
    for row in header_rows(context):
        (aside if held_open(context, str(row["taken_at"])) else kept).append(row)
    return kept, aside


def weights(context, rows):
    """Each slot's share of the heat: its day's kilowatt-hours, split between
    the slots kept from that day."""

    delivered = heat(context)
    counts = {}
    for row in rows:
        day = str(row["taken_at"])[:10]
        counts[day] = counts.get(day, 0) + 1
    raw = [delivered.get(str(row["taken_at"])[:10], 0.0) / counts[str(row["taken_at"])[:10]]
           for row in rows]
    total = sum(raw)
    return [value / total for value in raw] if total else [0.0] * len(rows)


def sheet(context):
    """The characterisation sheet, in the order the supplies are listed."""

    rows = {str(row["supply"]): row for row in context["signature_sheet"]["rows"]}
    order = supplies(context)
    return {
        "conductivity": [float(rows[name]["cond_uScm"]) for name in order],
        "marker": [
            float(rows[name]["mark_muL"]) if rows[name]["mark_flag"] == "value" else None
            for name in order
        ],
        "floor": [float(rows[name]["mark_floor_muL"]) for name in order],
        "outdoor_C": float(context["signature_sheet"]["outdoor_C"]),
        "point": [str(rows[name]["point"]) for name in order],
    }


def repeat(context, dwell_min=5):
    values = context["analyser"]["repeatability"][str(int(dwell_min))]
    return float(values["cond_uScm"]), float(values["mark_muL"])


def served(ledger):
    return [entry for entry in ledger if not entry.get("refusal")]


def rate(context, ledger):
    """The dosing rate, and how far the analyser's own repeatability leaves it.

    The sheet was read on one mild day, so the drop between it and a plant room
    read cold is what the tie-in's conductivity does per degree.
    """

    paper = sheet(context)
    warm = paper["outdoor_C"]
    day_of = temperatures(context)
    cold = []
    for entry in served(ledger):
        if str(entry["point"]) != "tie_in_plant_room":
            continue
        for row in entry.get("readings", ()):
            if row.get("cond_uScm") is None:
                continue
            cold.append((day_of.get(str(row["taken_at"])[:10], warm), float(row["cond_uScm"])))
    if not cold:
        return None
    lever = warm - sum(item[0] for item in cold) / len(cold)
    if abs(lever) < LEVER_MIN:
        return None
    noise = repeat(context)[0]
    slots = float(context["signature_sheet"]["rows"][0].get("slots", 1))
    return (
        (paper["conductivity"][0] - sum(item[1] for item in cold) / len(cold)) / lever,
        sqrt(noise**2 / slots + noise**2 / len(cold)) / abs(lever),
    )


def long_dwell_marker(context, ledger):
    """The recovery marker as a thirty-minute riser slot printed it, if one has."""

    values = []
    for entry in served(ledger):
        if str(entry["point"]) != "east_riser":
            continue
        for row in entry.get("readings", ()):
            if row.get("mark_flag") == "value" and int(row["dwell_min"]) >= 30:
                values.append(float(row["mark_muL"]))
    return values


def marker_is_read(context, ledger):
    """Whether the recovery signature is a figure rather than something to run over.

    The sheet prints a figure on that line for a main whose return carries
    enough marker for five minutes to hold it; where it prints a floor flag
    instead, only a thirty-minute riser slot puts a figure under it.
    """

    return sheet(context)["marker"][2] is not None or bool(
        long_dwell_marker(context, ledger)
    )


def marker_range(context, ledger):
    """Everything the recovery signature could still be, low end first.

    The hire module's third channel is not a way round the floor: backing the
    signature out of a header slot divides the sheet's own scatter by a recovery
    share near a fifth, and the plant sets the module reads in the same pass
    carry the ripple channel's repeatability on top, so what comes back is
    wider than the bound the sheet already prints. The bound stands.
    """

    paper = sheet(context)
    printed = paper["marker"][2]
    if printed is not None:
        return printed, printed
    long_dwell = long_dwell_marker(context, ledger)
    if long_dwell:
        value = sum(long_dwell) / len(long_dwell)
        spread = repeat(context, 30)[1] / sqrt(len(long_dwell))
        return max(0.0, value - SPREAD * spread), value + SPREAD * spread
    return 0.0, paper["floor"][2]


def signature_matrix(context, paper, temperature, marker_recovery, shift):
    conductivity = list(paper["conductivity"])
    conductivity[0] -= shift * (paper["outdoor_C"] - temperature)
    marker = list(paper["marker"])
    marker[2] = marker_recovery
    return [conductivity, marker, [1.0, 1.0, 1.0]]


def slot_shares(context, row, marker_recovery, shift):
    paper = sheet(context)
    temperature = temperatures(context).get(str(row["taken_at"])[:10], paper["outdoor_C"])
    rows = signature_matrix(context, paper, temperature, marker_recovery, shift)
    return solve3(rows, [float(row["cond_uScm"]), float(row["mark_muL"]), 1.0])


def combine(context, rows, marker_recovery, shift, share=None):
    """The window's apportionment from one reading of the slots."""

    if not rows:
        return [0.0, 0.0, 0.0]
    share = weights(context, rows) if share is None else share
    totals = [0.0, 0.0, 0.0]
    for weight, row in zip(share, rows):
        values = slot_shares(context, row, marker_recovery, shift)
        for index in range(3):
            totals[index] += weight * values[index]
    return totals


def slot_spread(context, row, marker_recovery, shift):
    """What one reading of the analyser is worth, carried into the three shares."""

    noise = repeat(context, int(row.get("dwell_min", 5)))
    base = slot_shares(context, row, marker_recovery, shift)
    moved = []
    for index, column in enumerate(("cond_uScm", "mark_muL")):
        nudged = dict(row)
        nudged[column] = float(row[column]) + noise[index]
        moved.append(slot_shares(context, nudged, marker_recovery, shift))
    return [
        sqrt(sum((item[index] - base[index]) ** 2 for item in moved)) for index in range(3)
    ]


def standard_error(context, rows, marker_recovery, shift):
    if not rows:
        return [0.0, 0.0, 0.0]
    share = weights(context, rows)
    totals = [0.0, 0.0, 0.0]
    for weight, row in zip(share, rows):
        spread = slot_spread(context, row, marker_recovery, shift)
        for index in range(3):
            totals[index] += (weight * spread[index]) ** 2
    return [sqrt(value) for value in totals]


def reading(context, ledger):
    """The figure, the band and what the ledger has pinned."""

    found = rate(context, ledger)
    shift = found[0] if found else 0.0
    low, high = marker_range(context, ledger)
    kept, aside = split(context)
    middle = combine(context, kept, (low + high) / 2.0, shift)
    ends = [combine(context, kept, low, shift), combine(context, kept, high, shift)]
    spread = standard_error(context, kept, (low + high) / 2.0, shift)
    if found:
        rates = [
            combine(context, kept, (low + high) / 2.0, shift - SPREAD * found[1]),
            combine(context, kept, (low + high) / 2.0, shift + SPREAD * found[1]),
        ]
        drift = [abs(rates[0][index] - rates[1][index]) / 2.0 for index in range(3)]
    else:
        drift = [0.0, 0.0, 0.0]
    band = [
        [
            min(ends[0][index], ends[1][index]) - SPREAD * spread[index] - drift[index],
            max(ends[0][index], ends[1][index]) + SPREAD * spread[index] + drift[index],
        ]
        for index in range(3)
    ]
    return {
        "shares": middle,
        "band": band,
        "kept": kept,
        "aside": aside,
        "rate_measured": found is not None,
        "marker_read": marker_is_read(context, ledger),
        # What the slots themselves leave, before the dosing term goes on: the
        # width the stop clause is read against.
        "left_by_the_slots": [
            (max(ends[0][index], ends[1][index]) - min(ends[0][index], ends[1][index])) / 2.0
            + SPREAD * spread[index]
            for index in range(3)
        ],
    }


def slot_cost(context, point, dwell_min, samples, channels):
    per_slot = LONG_DWELL_SLOTS if int(dwell_min) >= 30 else 1
    cost = per_slot * int(samples)
    if "ripple" in channels:
        cost += int(context["collection"]["module_slots"])
    return cost


def slots_left(context, ledger):
    granted = int(context["collection"]["slots_granted"])
    return granted - sum(int(entry["slots_charged"]) for entry in ledger)
