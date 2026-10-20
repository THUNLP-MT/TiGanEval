'A second build of the notebook, written from `full_information.md` alone.'

from __future__ import annotations


REPORT = '''"""The Ryecourt build note, written to the terms the board set."""

import calendar
from datetime import date, timedelta
from statistics import NormalDist


def key_of(label):
    year, month = str(label)[:7].split("-")
    return int(year) * 12 + int(month) - 1


def label_of(key):
    return "%04d-%02d" % (key // 12, key % 12 + 1)


def group_of(build_month):
    year, month = str(build_month)[:7].split("-")
    return "%s-H%d" % (year, 1 if int(month) <= 6 else 2)


def return_months(context):
    first = key_of(context["window"]["first_return"])
    last = key_of(context["window"]["last_return"])
    return [label_of(step) for step in range(first, last + 1)]


def card_of(context, depot, month):
    """The card that depot was raising faults under in that return month."""

    answer = None
    for row in context["cards"]:
        if row["depot"] != depot:
            continue
        if key_of(row["from_month"]) > key_of(month):
            continue
        if row.get("to_month") and key_of(row["to_month"]) < key_of(month):
            continue
        answer = row["walkaround_ref"]
    return answer


def opening_card(context):
    """The card the whole region was on when the window opened."""

    earliest = min(key_of(row["from_month"]) for row in context["cards"])
    for row in context["cards"]:
        if key_of(row["from_month"]) == earliest:
            return row["walkaround_ref"]
    return None


def months_on_the_fleet(context):
    """(build month, return month, card) -> days on the fleet as a share of each."""

    window = return_months(context)
    first_key, last_key = key_of(window[0]), key_of(window[-1])
    held = {}
    for van in context["vans"]:
        start = date.fromisoformat(van["in_service_date"])
        end = date.fromisoformat(van["off_fleet_date"])
        moved = van.get("transfer_date") or ""
        for step in range(max(first_key, key_of(van["in_service_date"])),
                          min(last_key, key_of(van["off_fleet_date"])) + 1):
            month = label_of(step)
            length = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
            opens = date(int(month[:4]), int(month[5:7]), 1)
            closes = date(int(month[:4]), int(month[5:7]), length)
            runs = [(van["depot"], max(start, opens), min(end, closes))]
            if moved:
                turn = date.fromisoformat(moved)
                if runs[0][1] < turn <= runs[0][2]:
                    runs = [(van["depot"], runs[0][1], turn - timedelta(days=1)),
                            (van["transfer_depot"], turn, runs[0][2])]
                elif turn <= runs[0][1]:
                    runs = [(van["transfer_depot"], runs[0][1], runs[0][2])]
            for depot, from_day, to_day in runs:
                days = (to_day - from_day).days + 1
                if days <= 0:
                    continue
                mark = (van["build_month"], month, card_of(context, depot, month))
                held[mark] = held.get(mark, 0.0) + days / length
    return held


def faults_raised(context):
    """(build month, return month, card) -> faults on the log."""

    built = {van["van_id"]: van["build_month"] for van in context["vans"]}
    raised = {}
    for row in context["faults"]:
        mark = (built[row["van_id"]], str(row["raised_date"])[:7], row["walkaround_ref"])
        raised[mark] = raised.get(mark, 0) + 1
    return raised


def card_scales(context, held, raised):
    """What each card books against the card the region opened on."""

    opened = opening_card(context)
    scales = {opened: 1.0}
    for card in sorted({mark[2] for mark in held} - {opened}):
        moved_side = 0.0
        stayed_side = 0.0
        for (build, month, mark) in held:
            if mark != opened:
                continue
            there = held[(build, month, opened)]
            here = held.get((build, month, card), 0.0)
            if here < 2.0 or there < 2.0:
                continue
            share = here if here < there else there
            moved_side += share * raised.get((build, month, card), 0) / here
            stayed_side += share * raised.get((build, month, opened), 0) / there
        scales[card] = moved_side / stayed_side if stayed_side > 0 else 1.0
    return scales


def one_scale(context):
    """(build month, return month) -> vehicle-months and faults on one scale."""

    held = months_on_the_fleet(context)
    raised = faults_raised(context)
    scales = card_scales(context, held, raised)
    grid = {}
    for (build, month, card), value in held.items():
        row = grid.setdefault((build, month), [0.0, 0.0])
        row[0] += value
        row[1] += raised.get((build, month, card), 0) / scales.get(card, 1.0)
    return {mark: row for mark, row in grid.items() if row[0] > 0.0}


def build_standard(context):
    """Build month -> the standard the change orders leave it in."""

    marks = {}
    for row in context["build_sheets"]:
        marks[row["build_month"]] = (row["body_spec"], tuple(row["lots"]))
    standing = None
    held = None
    out = {}
    for build in sorted(marks):
        if marks[build] != held:
            held = marks[build]
            standing = build
        out[build] = standing
    return out


def cholesky_solve(matrix, vector):
    """Solve a symmetric positive system by factorising it."""

    size = len(vector)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            total = matrix[row][column]
            for step in range(column):
                total -= lower[row][step] * lower[column][step]
            if row == column:
                if total <= 1e-12:
                    raise ValueError("the fit has nothing to separate two of its terms")
                lower[row][column] = total**0.5
            else:
                lower[row][column] = total / lower[column][column]
    forward = [0.0] * size
    for row in range(size):
        total = vector[row]
        for step in range(row):
            total -= lower[row][step] * forward[step]
        forward[row] = total / lower[row][row]
    answer = [0.0] * size
    for row in range(size - 1, -1, -1):
        total = forward[row]
        for step in range(row + 1, size):
            total -= lower[step][row] * answer[step]
        answer[row] = total / lower[row][row]
    return answer


def assemble(context):
    grid = one_scale(context)
    window = return_months(context)
    standing = build_standard(context)
    labels = ["level", "age"] + ["month " + month for month in window[1:]]
    order = []
    for build in sorted(standing):
        if standing[build] not in order:
            order.append(standing[build])
    place = {}
    for standard in order[1:]:
        place[standard] = len(labels)
        labels.append("build " + standard)
    at_month = {month: 2 + index for index, month in enumerate(window[1:])}
    rows = []
    for (build, month) in sorted(grid):
        months, faults = grid[(build, month)]
        parts = [(0, 1.0), (1, float(key_of(month) - key_of(build)))]
        if month in at_month:
            parts.append((at_month[month], 1.0))
        if standing[build] in place:
            parts.append((place[standing[build]], 1.0))
        rows.append((parts, months, 100.0 * faults / months))
    return rows, labels, standing, place


def wanted_contrast(context, labels, standing, place):
    early, late = context["audit"]["compare"]
    made = {}
    for van in context["vans"]:
        made[van["build_month"]] = made.get(van["build_month"], 0) + 1
    vector = [0.0] * len(labels)
    for sign, name in ((1.0, late), (-1.0, early)):
        members = context["audit"]["build_groups"][name]
        total = float(sum(made.get(build, 0) for build in members))
        for build in members:
            column = place.get(standing[build])
            if column is not None:
                vector[column] += sign * made.get(build, 0) / total
    return vector


def note(context):
    rows, labels, standing, place = assemble(context)
    size = len(labels)
    normal = [[0.0] * size for _ in range(size)]
    target = [0.0] * size
    for parts, weight, value in rows:
        for index, first in parts:
            target[index] += weight * first * value
            for other, second in parts:
                normal[index][other] += weight * first * second
    beta = cholesky_solve([list(row) for row in normal], list(target))
    vector = wanted_contrast(context, labels, standing, place)
    left = 0.0
    for parts, weight, value in rows:
        fitted = sum(beta[index] * factor for index, factor in parts)
        left += weight * (value - fitted) ** 2
    left /= float(max(1, len(rows) - size))
    solved = cholesky_solve([list(row) for row in normal], list(vector))
    spread = left * sum(vector[index] * solved[index] for index in range(size))
    regions = float(context["review"]["regions_on_the_note"])
    tail = (1.0 / float(context["review"]["one_time_in"])) / (2.0 * regions)
    # The board's one-point bar is what it does with this width once it has it,
    # so the width is the spread the fit leaves at the level the note is written
    # to and is not trimmed towards a point.
    reach = NormalDist().inv_cdf(1.0 - tail) * spread**0.5
    return {
        "difference": sum(vector[index] * beta[index] for index in range(size)),
        "reach": reach,
        "months": sum(weight for _parts, weight, _value in rows),
    }


def analyze(context, receipts):
    read = note(context)
    return {
        "build_difference_points": round(read["difference"], 1),
        "difference_range": [read["difference"] - read["reach"],
                             read["difference"] + read["reach"]],
        "vehicle_months": round(read["months"], 1),
        "days": [
            {
                "receipt_id": entry["receipt_id"],
                "depot": entry["depot"],
                "day": entry["day"],
                "vans_returned": int(entry["vans_returned"]),
                "faults_returned": int(entry["faults_returned"]),
            }
            for entry in receipts
        ],
        "days_charged": sum(int(entry["days_charged"]) for entry in receipts),
    }


def running(context, depot, group, band, day):
    """Vans of that build group in service at that depot inside the band."""

    when = key_of(day)
    total = 0
    for van in context["vans"]:
        if group_of(van["build_month"]) != group:
            continue
        if not (van["in_service_date"] <= day <= van["off_fleet_date"]):
            continue
        where = van["depot"]
        moved = van.get("transfer_date") or ""
        if moved and moved <= day:
            where = van["transfer_depot"]
        if where != depot:
            continue
        if band[0] <= when - key_of(van["build_month"]) <= band[1]:
            total += 1
    return total


def next_collection(context, receipts):
    terms = context["audit"]
    charged = sum(int(entry["days_charged"]) for entry in receipts)
    if int(terms["days_granted"]) - charged <= 0:
        return "stop"
    seen = set()
    for entry in receipts:
        if not entry.get("refusal") and entry.get("walkaround_ref"):
            seen.add(entry["walkaround_ref"])
    last = context["window"]["last_return"]
    open_cards = {card_of(context, depot, last) for depot in context["depots"]} - seen
    if not open_cards:
        return "stop"
    worked = {str(entry["day"]) for entry in receipts}
    weeks = {}
    for entry in receipts:
        stamp = date.fromisoformat(str(entry["day"])).isocalendar()
        weeks[(stamp[0], stamp[1])] = weeks.get((stamp[0], stamp[1]), 0) + 1
    free = None
    when = date.fromisoformat(str(context["as_of"]))
    for step in range(70):
        try_day = when + timedelta(days=step)
        stamp = try_day.isocalendar()
        if try_day.isoweekday() > 5 or try_day.isoformat() in worked:
            continue
        if weeks.get((stamp[0], stamp[1]), 0) >= int(terms["days_per_week"]):
            continue
        free = try_day.isoformat()
        break
    if free is None:
        return "stop"
    band = [12, 48]
    least = int(terms["vans_in_service_minimum"])
    best = None
    for depot in context["depots"]:
        if card_of(context, depot, last) not in open_cards:
            continue
        counted = [
            (running(context, depot, group, band, free), group)
            for group in sorted(terms["build_groups"])
        ]
        counted.sort(reverse=True)
        if len(counted) < 2 or counted[1][0] < least:
            continue
        weight = counted[0][0] + counted[1][0]
        if best is None or weight > best[0]:
            best = (weight, depot, sorted([counted[0][1], counted[1][1]]))
    if best is None:
        return "stop"
    return {
        "depot": best[1],
        "builds": best[2],
        "age_band": band,
        "vans": int(terms["vans_per_day"]),
        "day": free,
    }
'''


SUPPORT = '''"""Nothing lives here in this build; the note is one module."""
'''


FILES = {"analysis.py": REPORT, "support.py": SUPPORT}
