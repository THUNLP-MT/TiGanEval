"What the world says, computed from the world's own parameters."

from __future__ import annotations

from fractions import Fraction
from math import sqrt
from typing import Any, Mapping, Sequence

from . import world as w
from .world import COUPON, INCUMBENT, fraction


TOLERANCE = Fraction(1, 4)


DECOY_TOLERANCE = Fraction(3, 50)


MOVE_TOLERANCE = Fraction(3, 20)


TIGHTEST = 0.4
WIDEST = 6.0


def truth(world: w.World) -> Fraction:
    'The kelvin the selected plate really takes off the case temperature rise.'

    return world.truth(world.selected)


def returned(entry: Mapping[str, Any], part: str) -> list[Fraction]:
    for item in entry.get("parts", ()):
        if str(item["part"]) == str(part):
            return [fraction(value) for value in item.get("rise_K", ())]
    return []


def paired_days(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[int, int]]:
    'Days whose sheet returned runs of both the selected plate and the incumbent.'

    found: dict[str, tuple[int, int]] = {}
    for entry in receipts:
        plate = returned(entry, world.selected)
        incumbent = returned(entry, INCUMBENT)
        if plate and incumbent:
            found[str(entry["day_id"])] = (len(plate), len(incumbent))
    return found


def plate_days(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    'Every day carrying runs of the selected plate, the screen day included.'

    days: dict[str, int] = {}
    for day, part in world.screen_blocks():
        if part == world.selected:
            days[day] = int(world.spec["screen_runs"])
    for entry in receipts:
        plate = returned(entry, world.selected)
        if plate:
            days[str(entry["day_id"])] = len(plate)
    return days


def screen_reading(world: w.World, arrangement: str = "as run") -> Fraction:
    "The selected plate's screen score: the number on the table."

    value = world.screen_score(world.selected, arrangement)
    return Fraction(0) if value is None else value


def baseline_reading(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> Fraction | None:
    'Follow-up runs of the plate read against the stored incumbent number.'

    scores: list[Fraction] = []
    for entry in receipts:
        scores.extend(world.score(rise) for rise in returned(entry, world.selected))
    if not scores:
        return None
    return sum(scores, Fraction(0)) / len(scores)


def pooled_reading(
    world: w.World, receipts: Sequence[Mapping[str, Any]], arrangement: str = "as run"
) -> Fraction | None:
    'Screen runs and follow-up runs of the plate thrown into one average.'

    runs = int(world.spec["screen_runs"])
    scores: list[Fraction] = []
    for day, part in world.screen_blocks(arrangement):
        if part == world.selected:
            scores.extend(
                world.score(rise) for rise in world.readings(day, part, runs, arrangement)
            )
    for entry in receipts:
        scores.extend(world.score(rise) for rise in returned(entry, world.selected))
    if not scores:
        return None
    return sum(scores, Fraction(0)) / len(scores)


def misreadings(
    world: w.World, receipts: Sequence[Mapping[str, Any]], arrangement: str = "as run"
) -> list[tuple[str, Fraction]]:
    'Named readings a wrong grouping of the same runs produces, in report order.'

    found: list[tuple[str, Fraction]] = [
        ("effect_is_the_screen_score", screen_reading(world, arrangement))
    ]
    for name, value in (
        ("effect_ignores_the_day_the_runs_sat_on", baseline_reading(world, receipts)),
        ("effect_ignores_the_day_the_runs_sat_on", pooled_reading(world, receipts, arrangement)),
    ):
        if value is not None:
            found.append((name, value))
    return [(name, value) for name, value in found if abs(value - truth(world)) > TOLERANCE]


def _day_variance(world: w.World, plate: int, incumbent: int) -> float:
    'What one paired rig day leaves between its difference and the truth.'

    scatter = float(fraction(world.spec["run_scatter"]))
    seating = float(fraction(world.spec["seating_spread"]))
    return 2.0 * seating * seating + scatter * scatter * (1.0 / plate + 1.0 / incumbent)


def supported_error(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> float:
    'The standard error the best reading of the held runs carries.'

    scatter = float(fraction(world.spec["run_scatter"]))
    seating = float(fraction(world.spec["seating_spread"]))
    day_spread = float(fraction(world.spec["day_shift_sd"]))
    paired = paired_days(world, receipts)
    if paired:
        total = sum(
            _day_variance(world, plate, incumbent) for plate, incumbent in paired.values()
        )
        return sqrt(total) / len(paired)
    days = plate_days(world, receipts)
    count = max(len(days), 1)
    within = sum(
        seating * seating + scatter * scatter / max(runs, 1) for runs in days.values()
    ) / (count * count)
    return sqrt(day_spread * day_spread * (1.0 + 1.0 / count) + within)


def range_band(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    'The narrowest and the widest half-width the held runs stand behind.'

    error = supported_error(world, receipts)
    return TIGHTEST * error, WIDEST * error


def days_left(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> int:
    return int(world.spec["rig_days_on_the_sheet"]) - len(receipts)


def sheet_counts(sheet: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in sheet:
        counts[str(item["part"])] = counts.get(str(item["part"]), 0) + int(item["runs"])
    return counts


def implied_width(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    sheet: Sequence[Mapping[str, Any]],
    left: int,
) -> float:
    'The range width this sheet leaves, run on each rig day still on the sheet.'

    counts = sheet_counts(sheet)
    plate, incumbent = counts.get(world.selected, 0), counts.get(INCUMBENT, 0)
    if plate <= 0 or incumbent <= 0 or left <= 0:
        return float("inf")
    held = paired_days(world, receipts)
    total = sum(
        _day_variance(world, held_plate, held_incumbent)
        for held_plate, held_incumbent in held.values()
    )
    total += left * _day_variance(world, plate, incumbent)
    return 4.0 * sqrt(total) / (len(held) + left)


def candidate_sheets(world: w.World) -> list[list[dict[str, Any]]]:
    'Every day sheet the rig would run that carries the plate and the incumbent.'

    caps = world.day_capacity()
    sheets: list[list[dict[str, Any]]] = []
    for plate in range(1, caps["runs_per_day"]):
        for incumbent in range(1, caps["runs_per_day"] - plate + 1):
            sheets.append(
                [
                    {"part": world.selected, "runs": plate},
                    {"part": INCUMBENT, "runs": incumbent},
                ]
            )
    return sheets


def best_width(world: w.World, receipts: Sequence[Mapping[str, Any]], left: int) -> float:
    return min(
        (implied_width(world, receipts, sheet, left) for sheet in candidate_sheets(world)),
        default=float("inf"),
    )


def bar(world: w.World) -> float:
    return float(fraction(world.spec["range_width_K"]))


def held_width(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> float:
    return 4.0 * supported_error(world, receipts)


STOP_SLACK = 1.25


def stop_is_right(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> bool:
    return (
        days_left(world, receipts) <= 0
        or held_width(world, receipts) <= STOP_SLACK * bar(world)
    )


def wanted_width(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> float:
    'The width the review can still be got to with the rig days that are left.'

    left = days_left(world, receipts)
    reachable = best_width(world, receipts, left)
    return bar(world) if reachable <= bar(world) else reachable


def best_sheet(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The day sheet the review would book next, or an empty sheet for a stop.'

    if stop_is_right(world, receipts):
        return []
    left = days_left(world, receipts)
    return min(
        candidate_sheets(world),
        key=lambda sheet: (implied_width(world, receipts, sheet, left), -sheet[0]["runs"]),
    )


def coupon_gap(world: w.World, arrangement: str = "as run") -> Fraction:
    "How far apart the reference plate's two screen scores sit."

    scores = sorted(w.coupon_scores(world, arrangement).values())
    return scores[-1] - scores[0] if len(scores) > 1 else Fraction(0)


def runner_up(world: w.World) -> tuple[str, Fraction]:
    ranked = w.sorted_screen_scores(world)
    return ranked[1] if len(ranked) > 1 else ranked[0]


def selected_rank(world: w.World) -> int:
    ranked = [plate for plate, _score in w.sorted_screen_scores(world)]
    return ranked.index(world.selected) + 1


PARTS = (INCUMBENT, COUPON)
