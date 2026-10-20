"What the desk's own week says, computed from the world's own parameters."

from __future__ import annotations

from fractions import Fraction
import math
from typing import Any, Mapping, Sequence

from . import ledger as ledger_module
from . import world as w
from .world import AREAS, METER_STEP, WINDOWS, fraction


TOLERANCE = 0.04


DECOY = 0.015


MOVE_TOLERANCE = 0.04


FLOOR = 0.5
CEILING = 2.0


LOCAL_IMPROVEMENT_TOLERANCE = 0.15

_GRID = tuple(-4.5 + 0.03 * step for step in range(301))
_WEIGHTS = tuple(math.exp(-0.5 * z * z) for z in _GRID)
_WEIGHT_SUM = sum(_WEIGHTS)

_SPREAD_CACHE: dict[tuple[str, str], float] = {}
_NEED_CACHE: dict[tuple[str, int, int, int], tuple[float, ...]] = {}


def truth(
    world: w.World,
    shift: str,
    area: str,
    window: str,
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> int:
    return world.demand(area, shift, window, arrangement, moved_to)


def total_truth(
    world: w.World,
    shift: str,
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> int:
    return world.shift_total(shift, arrangement, moved_to)


def misreadings(
    world: w.World,
    shift: str,
    area: str,
    window: str,
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> list[tuple[str, int]]:
    'Named readings of the same two sheets, in the order the desk names them.'

    index = world.index_of(shift)
    found: list[tuple[str, int]] = []
    right = truth(world, shift, area, window, arrangement, moved_to)

    def with_duplicate(day: str) -> int:
        "That day's number with the moved zone left on the sheet it came from."

        base = world.demand(area, day, window, arrangement, moved_to)
        moved = world.moved_zone
        if moved is None or str(area) != str(world.spec["moved_from"]):
            return base
        if world.area_of(moved, day, arrangement, moved_to) == str(area):
            return base
        return base + world.forecast(moved, day, window)

    stale_day = None
    if world.early_area(arrangement) == str(area) and index + 1 < len(world.shifts):
        stale_day = world.shifts[index + 1]
    if stale_day is not None:
        found.append(("demand_reads_stale_shift", with_duplicate(stale_day)))
        found.append(
            ("demand_reads_stale_shift", world.demand(area, stale_day, window, arrangement, moved_to))
        )
    found.append(("demand_double_counts_zone", with_duplicate(shift)))
    smoothed = sum(
        world.smoothed(zone, shift, window)
        for zone in world.zones_of(area, shift, arrangement, moved_to)
    )
    found.append(("demand_uses_the_smoothed_column", smoothed))


    kept: list[tuple[str, int]] = []
    for kind, value in found:
        if abs(value - right) <= TOLERANCE * right:
            continue
        if any(abs(value - held) <= 2 * DECOY * right for _name, held in kept):
            continue
        kept.append((kind, value))
    return kept


def calendar_spread(world: w.World) -> float:
    "The spread of the merchant calendar's move, which every zone carries."

    return float(fraction(world.spec["calendar_spread"]))


def area_spread(world: w.World, area: str) -> float:
    "What one area's window misses by, calendar and its own zones together."

    key = (world.campaign, str(area))
    if key not in _SPREAD_CACHE:
        residuals = []
        for shift in world.shifts:
            move = float(world.calendar_move(shift))
            for window in WINDOWS:
                sheet = world.demand(area, shift, window)
                if not sheet:
                    continue
                metered = world.metered(area, shift, window)
                residuals.append(metered / sheet - 1 - move)
        own = math.sqrt(sum(value * value for value in residuals) / max(len(residuals), 1))
        spread = calendar_spread(world)
        _SPREAD_CACHE[key] = math.sqrt(spread * spread + own * own)
    return _SPREAD_CACHE[key]


def drops_sd(world: w.World, shift: str, area: str, window: str, **kwargs: Any) -> float:
    "How far one area-window's drops sit from the sheet, in drops."

    sheet = truth(world, shift, area, window, **kwargs)
    rounding = (METER_STEP * METER_STEP) / 12.0
    return math.sqrt((area_spread(world, area) * sheet) ** 2 + rounding)


def total_sd(world: w.World, shift: str, **kwargs: Any) -> float:
    "How far the whole network's drops sit from the sheet, in drops."

    sheet = total_truth(world, shift, **kwargs)
    rounding = len(AREAS) * len(WINDOWS) * (METER_STEP * METER_STEP) / 12.0
    return math.sqrt((calendar_spread(world) * sheet) ** 2 + rounding)


def half_band(world: w.World, shift: str, area: str, window: str, **kwargs: Any) -> tuple[float, float]:
    supported = 2.0 * drops_sd(world, shift, area, window, **kwargs)
    return FLOOR * supported, CEILING * supported


def total_half_band(world: w.World, shift: str, **kwargs: Any) -> tuple[float, float]:
    supported = 2.0 * total_sd(world, shift, **kwargs)
    return FLOOR * supported, CEILING * supported


def _need_tail(world: w.World, shift: str, area: str, window: str) -> tuple[float, ...]:
    '`tail[v]` is the vans a window is expected to run short of with `v` booked.'

    sheet = truth(world, shift, area, window)
    key = (world.campaign, sheet, world.drops_per_van, int(round(1e6 * area_spread(world, area))))
    if key not in _NEED_CACHE:
        spread = area_spread(world, area)
        counts: dict[int, float] = {}
        for z, weight in zip(_GRID, _WEIGHTS):
            drops = METER_STEP * round(sheet * (1 + z * spread) / METER_STEP)
            need = world.vans_needed(max(int(drops), 0))
            counts[need] = counts.get(need, 0.0) + weight / _WEIGHT_SUM


        top = max(counts)
        tail = [0.0] * (top + 2)
        for vans in range(top - 1, -1, -1):
            above = sum(weight for need, weight in counts.items() if need > vans)
            tail[vans] = tail[vans + 1] + above
        _NEED_CACHE[key] = tuple(tail)
    return _NEED_CACHE[key]


def short_vans(world: w.World, shift: str, area: str, window: str, vans: int) -> float:
    tail = _need_tail(world, shift, area, window)
    if vans < 0:
        vans = 0
    return tail[vans] if vans < len(tail) else 0.0


def window_charge(world: w.World, shift: str, area: str, window: str, vans: int) -> float:
    return vans + float(world.spill_multiple) * short_vans(world, shift, area, window, vans)


def expected_charge(world: w.World, shift: str, booking: Mapping[tuple[str, str], int]) -> float:
    return sum(
        window_charge(world, shift, area, window, int(booking.get((area, window), 0)))
        for area in AREAS
        for window in WINDOWS
    )


def vans_sd(world: w.World, shift: str, area: str, window: str) -> float:
    return drops_sd(world, shift, area, window) / world.drops_per_van


MAX_SPREAD = 0.5


def _delivered_tail(world: w.World, drops: float, spread: float) -> tuple[float, ...]:
    key = (world.campaign, world.drops_per_van, round(float(drops), 2), round(float(spread), 5))
    if key not in _NEED_CACHE:
        counts: dict[int, float] = {}
        for z, weight in zip(_GRID, _WEIGHTS):
            turned_up = METER_STEP * round(drops * (1.0 + z * spread) / METER_STEP)
            need = world.vans_needed(max(int(turned_up), 0))
            counts[need] = counts.get(need, 0.0) + weight / _WEIGHT_SUM
        top = max(counts)
        tail = [0.0] * (top + 2)
        for vans in range(top - 1, -1, -1):
            above = sum(weight for need, weight in counts.items() if need > vans)
            tail[vans] = tail[vans + 1] + above
        _NEED_CACHE[key] = tuple(tail)
    return _NEED_CACHE[key]


def delivered_short(world: w.World, drops: float, spread: float, vans: int) -> float:
    tail = _delivered_tail(world, drops, spread)
    index = max(int(vans), 0)
    return tail[index] if index < len(tail) else 0.0


def delivered_charge(
    world: w.World,
    sheet: Mapping[tuple[str, str], float],
    spread: Mapping[tuple[str, str], float],
    booking: Mapping[tuple[str, str], int],
) -> float:
    'What one order is expected to cost against the sheet the pack published.'

    multiple = float(world.spill_multiple)
    total = 0.0
    for key, drops in sheet.items():
        vans = int(booking.get(key, 0))
        total += vans + multiple * delivered_short(world, drops, spread[key], vans)
    return total


def delivered_best(
    world: w.World,
    sheet: Mapping[tuple[str, str], float],
    spread: Mapping[tuple[str, str], float],
    allowance_left: int,
) -> dict[tuple[str, str], int] | None:
    "The cheapest order for the pack's own sheet, inside the allowance and caps."

    if allowance_left < world.minimum_booking:
        return None
    multiple = float(world.spill_multiple)
    booking = {key: 1 for key in sheet}
    spent = len(booking)

    def saving(key: tuple[str, str]) -> float:
        vans = booking[key]
        if vans >= world.van_cap:
            return float("-inf")
        prevented = delivered_short(world, sheet[key], spread[key], vans) - delivered_short(
            world, sheet[key], spread[key], vans + 1
        )
        return multiple * prevented - 1.0

    while spent < allowance_left:
        best = max(booking, key=saving)
        gain = saving(best)
        if gain == float("-inf"):
            break
        if gain <= 0 and spent >= world.minimum_booking:
            break
        booking[best] += 1
        spent += 1
    return booking


def delivered_local_improvement(
    world: w.World,
    sheet: Mapping[tuple[str, str], float],
    spread: Mapping[tuple[str, str], float],
    booking: Mapping[tuple[str, str], int],
    allowance_left: int,
) -> float:
    'Best expected-charge improvement from adding, removing or moving one van.'

    baseline = delivered_charge(world, sheet, spread, booking)
    asked = sum(int(value) for value in booking.values())
    improvement = 0.0

    def consider(other: Mapping[tuple[str, str], int]) -> None:
        nonlocal improvement
        improvement = max(
            improvement,
            baseline - delivered_charge(world, sheet, spread, other),
        )

    for key in sorted(sheet):
        vans = int(booking[key])
        if vans < world.van_cap and asked < allowance_left:
            other = dict(booking)
            other[key] += 1
            consider(other)
        if vans > 1 and asked > world.minimum_booking:
            other = dict(booking)
            other[key] -= 1
            consider(other)

    for source in sorted(sheet):
        if int(booking[source]) <= 1:
            continue
        for target in sorted(sheet):
            if source == target or int(booking[target]) >= world.van_cap:
                continue
            other = dict(booking)
            other[source] -= 1
            other[target] += 1
            consider(other)

    return improvement


def delivered_middle(
    world: w.World, sheet: Mapping[tuple[str, str], float]
) -> dict[tuple[str, str], int]:
    return {key: max(1, world.vans_needed(int(drops))) for key, drops in sheet.items()}


def middle_booking(world: w.World, shift: str) -> dict[tuple[str, str], int]:
    'The order that puts the vans on the number and no higher.'

    return {
        (area, window): max(1, world.vans_needed(truth(world, shift, area, window)))
        for area in AREAS
        for window in WINDOWS
    }


def top_of_range_booking(world: w.World, shift: str) -> dict[tuple[str, str], int]:
    'The order that puts the vans on the high end of the published range.'

    booking = {}
    for area in AREAS:
        for window in WINDOWS:
            high = truth(world, shift, area, window) + 2.0 * drops_sd(world, shift, area, window)
            booking[(area, window)] = min(
                world.van_cap, max(1, world.vans_needed(int(high)))
            )
    return booking


def best_booking(
    world: w.World, shift: str, allowance_left: int
) -> dict[tuple[str, str], int] | None:
    'The cheapest order the allowance and the caps allow, or None for a stop.'

    if allowance_left < world.minimum_booking:
        return None
    keys = [(area, window) for area in AREAS for window in WINDOWS]
    booking = {key: 1 for key in keys}
    spent = len(keys)
    multiple = float(world.spill_multiple)

    def saving(key: tuple[str, str]) -> float:
        vans = booking[key]
        if vans >= world.van_cap:
            return float("-inf")
        prevented = short_vans(world, shift, key[0], key[1], vans) - short_vans(
            world, shift, key[0], key[1], vans + 1
        )
        return multiple * prevented - 1.0

    while spent < allowance_left:
        best = max(keys, key=saving)
        gain = saving(best)
        if gain <= 0 and spent >= world.minimum_booking:
            break
        if gain == float("-inf"):
            break
        booking[best] += 1
        spent += 1
    return booking


def allowance_left(world: w.World, entries: Sequence[Mapping[str, Any]]) -> int:
    return ledger_module.allowance_left(world, entries)


def next_shift(world: w.World, entries: Sequence[Mapping[str, Any]]) -> str | None:
    return ledger_module.next_open_shift(world, entries)


def stop_is_right(world: w.World, entries: Sequence[Mapping[str, Any]]) -> bool:
    return (
        next_shift(world, entries) is None
        or allowance_left(world, entries) < world.minimum_booking
    )


def plan_states(
    world: w.World, entries: Sequence[Mapping[str, Any]], limit: int = 6
) -> list[dict[str, Any]]:
    'Every booking state this campaign can be asked for a next order in.'

    states = [{"label": "now", "entries": [dict(entry) for entry in entries]}]

    def walk(start: Sequence[Mapping[str, Any]], label: str, limit: int):
        held = [dict(entry) for entry in start]
        step = 0
        while not stop_is_right(world, held) and step < limit:
            shift = next_shift(world, held)
            order = best_booking(world, shift, allowance_left(world, held))
            if order is None:
                break
            step += 1
            held = ledger_module.extend(world, held, [(f"{label}-{step:02d}", shift, order)])
            states.append({"label": f"{label} {step}", "entries": [dict(e) for e in held]})

    walk(entries, "walk", limit)
    return states
