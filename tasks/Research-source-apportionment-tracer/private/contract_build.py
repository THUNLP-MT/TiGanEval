'The report built from `full_information.md` alone, sentence by sentence.'

from math import sqrt


TWO_READINGS = 2.0
COLD_ENOUGH = 3.0


def _solve(rows, right):
    grid = [list(map(float, row)) + [float(right[index])] for index, row in enumerate(rows)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(grid[index][column]))
        grid[column], grid[pivot] = grid[pivot], grid[column]
        for index in range(3):
            if index == column:
                continue
            factor = grid[index][column] / grid[column][column]
            for position in range(column, 4):
                grid[index][position] -= factor * grid[column][position]
    return [grid[index][3] / grid[index][index] for index in range(3)]


def _minutes(text):
    return int(str(text)[:2]) * 60 + int(str(text)[3:5])


def _open_entry(context, stamp):
    day, when = str(stamp)[:10], _minutes(str(stamp)[11:16])
    for entry in context["operations"]:
        if str(entry["day"]) == day and _minutes(entry["from"]) <= when < _minutes(entry["to"]):
            return True
    return False


def _window_slots(context):
    first, last = context["window"]["first_day"], context["window"]["last_day"]
    return [
        row
        for row in context["samples"]
        if first <= str(row["taken_at"])[:10] <= last
    ]


def _header_slots(context):
    kept, aside = [], []
    for row in _window_slots(context):
        if str(row["point"]) != "header":
            continue
        if row.get("cond_uScm") is None or row.get("mark_flag") != "value":
            continue
        (aside if _open_entry(context, row["taken_at"]) else kept).append(row)
    return kept, aside


def _sheet(context):
    order = list(context["supplies"])
    rows = {str(row["supply"]): row for row in context["signature_sheet"]["rows"]}
    return {
        "cond": [float(rows[name]["cond_uScm"]) for name in order],
        "mark": [
            float(rows[name]["mark_muL"]) if rows[name]["mark_flag"] == "value" else None
            for name in order
        ],
        "floor": [float(rows[name]["mark_floor_muL"]) for name in order],
        "day_C": float(context["signature_sheet"]["outdoor_C"]),
        "slots": float(context["signature_sheet"]["rows"][0].get("slots", 1)),
    }


def _outdoor(context):
    return {str(row["day"]): float(row["outdoor_C"]) for row in context["weather"]}


def _delivered(context):
    return {str(row["day"]): float(row["delivered_kwh"]) for row in context["heat_meter"]}


def _repeatability(context, dwell=5):
    note = context["analyser"]["repeatability"][str(int(dwell))]
    return float(note["cond_uScm"]), float(note["mark_muL"])


def _dosing_rate(context, ledger):
    "The drop between the sheet's mild day and the plant room read cold."

    paper, outdoor = _sheet(context), _outdoor(context)
    cold = []
    for entry in ledger:
        if entry.get("refusal") or str(entry.get("point")) != "tie_in_plant_room":
            continue
        for row in entry.get("readings", ()):
            if row.get("cond_uScm") is not None:
                cold.append((outdoor.get(str(row["taken_at"])[:10], paper["day_C"]),
                             float(row["cond_uScm"])))
    if not cold:
        return None
    gap = paper["day_C"] - sum(item[0] for item in cold) / len(cold)
    if abs(gap) < COLD_ENOUGH:
        return None
    drop = paper["cond"][0] - sum(item[1] for item in cold) / len(cold)
    noise = _repeatability(context)[0]
    return drop / gap, sqrt(noise**2 / paper["slots"] + noise**2 / len(cold)) / abs(gap)


def _long_dwell_marker(context, ledger):
    'The recovery marker where a thirty-minute riser slot has printed one.'

    values = []
    for entry in ledger:
        if entry.get("refusal") or str(entry.get("point")) != "east_riser":
            continue
        for row in entry.get("readings", ()):
            if row.get("mark_flag") == "value" and int(row.get("dwell_min", 5)) >= 30:
                values.append(float(row["mark_muL"]))
    return values


def _marker_is_read(context, ledger):
    'Whether the recovery signature is a figure rather than something to run over.'

    return _sheet(context)["mark"][2] is not None or bool(
        _long_dwell_marker(context, ledger)
    )


def _recovery_marker(context, ledger):
    'Everything the recovery signature could still be.'

    paper = _sheet(context)
    if paper["mark"][2] is not None:
        return paper["mark"][2], paper["mark"][2]
    pinned = _long_dwell_marker(context, ledger)
    if pinned:
        middle = sum(pinned) / len(pinned)
        spread = _repeatability(context, 30)[1] / sqrt(len(pinned))
        return max(0.0, middle - TWO_READINGS * spread), middle + TWO_READINGS * spread
    return 0.0, paper["floor"][2]


def _shares(context, rows, marker, rate):
    'One reading of the kept slots, each slot speaking for its own day.'

    paper, outdoor, delivered = _sheet(context), _outdoor(context), _delivered(context)
    per_day = {}
    for row in rows:
        per_day[str(row["taken_at"])[:10]] = per_day.get(str(row["taken_at"])[:10], 0) + 1
    total = sum(delivered.get(day, 0.0) for day in per_day)
    answer = [0.0, 0.0, 0.0]
    for row in rows:
        day = str(row["taken_at"])[:10]
        weight = delivered.get(day, 0.0) / per_day[day] / total if total else 0.0
        cond = list(paper["cond"])
        cond[0] -= rate * (paper["day_C"] - outdoor.get(day, paper["day_C"]))
        mark = list(paper["mark"])
        mark[2] = marker
        mix = _solve(
            [cond, mark, [1.0, 1.0, 1.0]],
            [float(row["cond_uScm"]), float(row["mark_muL"]), 1.0],
        )
        for index in range(3):
            answer[index] += weight * mix[index]
    return answer


def _reading_spread(context, rows, marker, rate):
    "What the analyser's repeatability leaves on the weighted figure."

    paper, outdoor, delivered = _sheet(context), _outdoor(context), _delivered(context)
    per_day = {}
    for row in rows:
        per_day[str(row["taken_at"])[:10]] = per_day.get(str(row["taken_at"])[:10], 0) + 1
    total = sum(delivered.get(day, 0.0) for day in per_day)
    variance = [0.0, 0.0, 0.0]
    for row in rows:
        day = str(row["taken_at"])[:10]
        weight = delivered.get(day, 0.0) / per_day[day] / total if total else 0.0
        noise = _repeatability(context, int(row.get("dwell_min", 5)))
        here = _shares(context, [row], marker, rate)
        for channel, step in (("cond_uScm", noise[0]), ("mark_muL", noise[1])):
            moved = dict(row)
            moved[channel] = float(row[channel]) + step
            there = _shares(context, [moved], marker, rate)
            for index in range(3):
                variance[index] += (weight * (there[index] - here[index])) ** 2
    return [sqrt(value) for value in variance]


def _report(context, ledger):
    found = _dosing_rate(context, ledger)
    rate = found[0] if found else 0.0
    low, high = _recovery_marker(context, ledger)
    kept, aside = _header_slots(context)
    middle = _shares(context, kept, (low + high) / 2.0, rate)
    ends = (_shares(context, kept, low, rate), _shares(context, kept, high, rate))
    spread = _reading_spread(context, kept, (low + high) / 2.0, rate)
    if found:
        edges = (
            _shares(context, kept, (low + high) / 2.0, rate - TWO_READINGS * found[1]),
            _shares(context, kept, (low + high) / 2.0, rate + TWO_READINGS * found[1]),
        )
        dosing = [abs(edges[0][index] - edges[1][index]) / 2.0 for index in range(3)]
    else:
        dosing = [0.0, 0.0, 0.0]
    band = [
        [
            min(ends[0][index], ends[1][index]) - TWO_READINGS * spread[index] - dosing[index],
            max(ends[0][index], ends[1][index]) + TWO_READINGS * spread[index] + dosing[index],
        ]
        for index in range(3)
    ]


    left_by_the_slots = [
        (max(ends[0][index], ends[1][index]) - min(ends[0][index], ends[1][index])) / 2.0
        + TWO_READINGS * spread[index]
        for index in range(3)
    ]
    return {
        "shares": middle,
        "band": band,
        "kept": kept,
        "aside": aside,
        "rate_measured": found is not None,
        "marker_read": _marker_is_read(context, ledger),
        "left_by_the_slots": left_by_the_slots,
    }


def analyze(context, ledger):
    answer = _report(context, ledger)
    names = list(context["supplies"])
    return {
        "shares": {name: answer["shares"][index] for index, name in enumerate(names)},
        "share_band": {name: answer["band"][index] for index, name in enumerate(names)},
        "samples_used": [str(row["sample_id"]) for row in answer["kept"]],
        "samples_set_aside": [str(row["sample_id"]) for row in answer["aside"]],
        "visits": [
            {
                "call_id": entry["call_id"],
                "point": entry["point"],
                "slots_charged": entry["slots_charged"],
            }
            for entry in ledger
        ],
    }


def next_collection(context, ledger):
    answer = _report(context, ledger)
    granted = int(context["collection"]["slots_granted"])
    left = granted - sum(int(entry["slots_charged"]) for entry in ledger)
    asked = float(context["report_request"]["recovery_band_half_width_at_most"])
    per_visit = int(context["collection"]["slots_per_visit"])
    long_dwell = int(context["collection"]["long_dwell_slots"])


    if not answer["rate_measured"] and left >= 1:
        return {
            "point": "tie_in_plant_room",
            "channels": ["conductivity", "marker"],
            "dwell_min": 5,
            "samples": min(per_visit, left),
        }

    if answer["rate_measured"] and answer["left_by_the_slots"][2] <= asked:
        return "stop"


    if not answer["marker_read"] and left >= long_dwell:
        return {
            "point": "east_riser",
            "channels": ["marker"],
            "dwell_min": 30,
            "samples": 1,
        }
    return "stop"
