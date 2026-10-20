'What the depot says, counted from its jobs rather than read off a report.'

from __future__ import annotations

from math import ceil
from typing import Any, Mapping, Sequence

from . import desk, world


TOLERANCE = 0.02


DECOY_SLACK = 0.0015


WIDE_SLACK = 0.003


FLOOR_SLACK = 1.5


HOLD_FLOOR = 0.88


WINDOW_MOVE = 4.0
RATE_MOVE = 0.02


def cut_index(rows: int) -> int:
    "Which of a class's rows the window's edge sits on."

    return int(ceil(world.HOLD_RULE * (int(rows) + 1)))


def enough_rows(rows: int) -> bool:
    return int(rows) > 0 and cut_index(rows) <= int(rows)


MIN_ROWS = next(size for size in range(1, 40) if enough_rows(size))


def stopped(depot: world.Depot, job_class: str) -> bool:
    'The class whose pull came back empty in the last audit week.'

    weeks = depot.weeks()
    return int(depot.returned.get((weeks[-1], str(job_class)), 0)) == 0


def sheet_diffs(depot: world.Depot, job_class: str) -> list[int]:
    return [job.actual - job.predicted for job in depot.sheets_of(job_class)]


def visit_diffs(receipts: Sequence[Mapping[str, Any]], job_class: str) -> list[int]:
    return [
        int(row["actual_minutes"]) - int(row["predicted_minutes"])
        for row in desk.rows_of(receipts)
        if str(row["job_class"]) == str(job_class)
    ]


def usable_diffs(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> list[int]:
    'The rows that still describe a class: its own nights, and its sheets when     the pull is still returning them.'

    nights = visit_diffs(receipts, job_class)
    if stopped(depot, job_class):
        return nights
    return sheet_diffs(depot, job_class) + nights


def floor_for(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> float | None:
    "The tightest half-width a class's own rows carry, or None when it has none."

    rows = sorted(abs(value) for value in usable_diffs(depot, receipts, job_class))
    if not enough_rows(len(rows)):
        return None
    return float(rows[cut_index(len(rows)) - 1])


def loose_floor(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> float | None:
    'The edge a build that forgets the printed job would land on.'

    rows = sorted(abs(value) for value in usable_diffs(depot, receipts, job_class))
    index = int(ceil(world.HOLD_RULE * len(rows)))
    if not rows or index > len(rows):
        return None
    return float(rows[index - 1])


def printable(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> bool:
    "A class prints when its own rows carry the level inside the board's limit."

    edge = floor_for(depot, receipts, job_class)
    if edge is None:
        return False
    return 2 * int(ceil(edge)) <= int(depot.spec["window_limit_minutes"])


def unprintable_classes(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]]
) -> list[str]:
    return [name for name in depot.classes if not printable(depot, receipts, name)]


def class_hold(depot: world.Depot, job_class: str, low: float, high: float) -> float:
    jobs = depot.month_jobs(job_class)
    if not jobs:
        return 0.0
    inside = sum(1 for job in jobs if low <= job.actual - job.predicted <= high)
    return inside / len(jobs)


def rows_hold(rows: Sequence[int], low: float, high: float) -> float | None:
    if not rows:
        return None
    return sum(1 for value in rows if low <= value <= high) / len(rows)


Windows = Mapping[str, tuple[float, float]]


def true_rate(depot: world.Depot, windows: Windows) -> float:
    "The share of the month's dispatched jobs these windows hold."

    total = 0.0
    for name in depot.classes:
        if name not in windows:
            continue
        low, high = windows[name]
        total += depot.share(name) * class_hold(depot, name, low, high)
    return total


def gold_windows(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[float, float]]:
    windows: dict[str, tuple[float, float]] = {}
    for name in depot.classes:
        edge = floor_for(depot, receipts, name)
        if edge is None or not printable(depot, receipts, name):
            continue
        half = float(ceil(edge))
        windows[name] = (-half, half)
    return windows


def gold_rate(depot: world.Depot, receipts: Sequence[Mapping[str, Any]]) -> float:
    return true_rate(depot, gold_windows(depot, receipts))


def sheet_counts(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    return {
        name: len(usable_diffs(depot, receipts, name)) or len(sheet_diffs(depot, name))
        for name in depot.classes
    }


def read_off_the_sheets(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], windows: Windows
) -> float | None:
    "The owner's own tally: the share of the sheets on file the windows hold."

    held = 0
    total = 0
    for name in depot.classes:
        rows = usable_diffs(depot, receipts, name) or sheet_diffs(depot, name)
        total += len(rows)
        if name in windows:
            low, high = windows[name]
            held += sum(1 for value in rows if low <= value <= high)
    if not total:
        return None
    return held / total


def weighted_by_sheet_mix(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], windows: Windows
) -> float | None:
    'Each class carried at its share of the sheets rather than of the month.'

    counts = sheet_counts(depot, receipts)
    total = sum(counts.values())
    if not total:
        return None
    value = 0.0
    for name in depot.classes:
        if name not in windows:
            continue
        low, high = windows[name]
        value += counts[name] / total * class_hold(depot, name, low, high)
    return value


def printed_classes_only(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], windows: Windows
) -> list[float]:
    'The readings that drop the class with no window out of the denominator.'

    printed = sum(depot.share(name) for name in depot.classes if name in windows)
    if printed <= 0.0:
        return []
    truth = true_rate(depot, windows)
    readings = [truth / printed, truth + (1.0 - printed) * world.HOLD_RULE]
    off_sheets = 0.0
    for name in depot.classes:
        if name not in windows:
            continue
        low, high = windows[name]
        rows = usable_diffs(depot, receipts, name) or sheet_diffs(depot, name)
        share = rows_hold(rows, low, high)
        if share is not None:
            off_sheets += depot.share(name) * share
    readings.append(off_sheets / printed)
    return readings


def wanted_class(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]]
) -> str | None:
    'The class the next visit has to reach, or None when every class prints.'

    waiting = unprintable_classes(depot, receipts)
    if not waiting:
        return None
    return max(waiting, key=lambda name: (depot.share(name), name))


def actionable_class(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]]
) -> str | None:
    'The largest unprintable class that still has a rostered night free.'

    waiting = [
        name
        for name in unprintable_classes(depot, receipts)
        if open_weeks(depot, receipts, name)
    ]
    if not waiting:
        return None
    return max(waiting, key=lambda name: (depot.share(name), name))


def open_weeks(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> list[int]:
    context = depot.visit_terms()
    roster = [int(week) for week in context["roster"].get(str(job_class), ())]
    return [
        week
        for week in roster
        if desk.visits_in_week(receipts, week) < int(context["visits_per_week"])
    ]


def can_afford(depot: world.Depot, receipts: Sequence[Mapping[str, Any]]) -> bool:
    context = depot.visit_terms()
    return desk.units_left(depot, receipts) >= int(context["units_per_visit"])


def plan_is_allowed(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], choice: Any
) -> str | None:
    'None when the booking is one this depot can act on, else the incident.'

    context = depot.visit_terms()
    wanted = wanted_class(depot, receipts)
    reachable = actionable_class(depot, receipts) is not None and can_afford(
        depot, receipts
    )
    if choice == "stop":
        if reachable:
            return "stops_with_a_class_unprintable"
        return None
    if not isinstance(choice, Mapping):
        return "visit_is_not_a_booking_or_a_stop"
    job_class = choice.get("job_class")
    week = choice.get("week")
    jobs = choice.get("jobs")
    if str(job_class) not in depot.classes:
        return "visit_is_not_a_booking_or_a_stop"
    for value in (week, jobs):
        if not isinstance(value, int) or isinstance(value, bool):
            return "visit_is_not_a_booking_or_a_stop"
    if int(week) not in [int(item) for item in context["weeks"]] or int(jobs) <= 0:
        return "visit_is_not_a_booking_or_a_stop"
    if int(week) not in [int(item) for item in context["roster"].get(str(job_class), ())]:
        return "visit_off_roster"
    if int(jobs) > int(context["jobs_per_visit"]) or desk.visits_in_week(
        receipts, int(week)
    ) >= int(context["visits_per_week"]):
        return "visit_over_the_desk_caps"
    if not can_afford(depot, receipts):
        return "visit_over_budget"
    if wanted is None:
        return "visit_when_every_class_prints"


    if str(job_class) not in unprintable_classes(depot, receipts):
        return "visit_skips_the_class_with_no_sheets"
    if int(jobs) < int(context["jobs_per_visit"]):
        return "visit_wastes_night_capacity"
    return None


def one_allowed_plan(depot: world.Depot, receipts: Sequence[Mapping[str, Any]]) -> Any:
    'A booking this depot can take now, or a stop when nothing is left to buy.'

    context = depot.visit_terms()
    wanted = actionable_class(depot, receipts)
    if wanted is None or not can_afford(depot, receipts):
        return "stop"
    weeks = open_weeks(depot, receipts, wanted)
    return {
        "job_class": wanted,
        "week": weeks[0],
        "jobs": int(context["jobs_per_visit"]),
    }
