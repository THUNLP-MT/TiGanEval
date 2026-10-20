"What the lot says, computed from the lot's own parameters and counts."

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from . import world as w


TOLERANCE = 5.0


CLASSIFY_SLACK = 1.2


RANGE_ROUNDING_BAR = 0.7


CARRIED_OVER_GAP = 8.0


INVARIANCE_SLACK = 3.0
_TARGET_LOGIT = w.logit(0.10)


def truth(world: w.World) -> float:
    "The pressure at which one in ten of the family leak at the plan's hold."

    return w.crossing_of(world.spec, int(world.spec["plan_hold_min"]))


def block_scale(world: w.World, bench: str, key: str) -> float:
    "What a batch's two block readings say that bench's console does."

    readings = world.block_readings(bench, key)
    return (sum(readings) / len(readings)) / float(world.spec["block_bar"])


def _receipt_rows(world: w.World, stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in stream:
        results = list(entry.get("results") or ())
        readings = list(entry.get("readings_bar") or ())
        for reading, result in zip(readings, results):
            rows.append(
                {
                    "batch": str(entry["booking_id"]),
                    "bench": str(entry["bench"]),
                    "cartridge": str(entry["cartridge"]),
                    "reading_bar": float(reading),
                    "dwell_min": int(entry["dwell_min"]),
                    "result": str(result),
                    "source": "receipt",
                }
            )
    return rows


def all_rows(world: w.World, stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every unit row the review holds, from the batch table and the receipts.'

    rows = [dict(row, source="batch_table") for row in world.run_rows()]
    rows.extend(_receipt_rows(world, stream))
    return rows


def levels(
    world: w.World,
    stream: Sequence[Mapping[str, Any]] = (),
    *,
    correct_bench: bool = True,
    drop_pinned: bool = True,
    plan_hold_only: bool = True,
) -> list[tuple[float, int, int]]:
    '(pressure in bar, units, leaks) for each cartridge the ladder counts.'

    span = world.span_bar
    table: dict[str, list[float]] = {}
    for row in all_rows(world, stream):
        if str(row["result"]) not in w.RESULTS:
            continue
        if plan_hold_only and int(row["dwell_min"]) != int(world.spec["plan_hold_min"]):
            continue
        reading = float(row["reading_bar"])
        if drop_pinned and reading >= span - 1e-9:
            continue
        pressure = reading
        if correct_bench:
            pressure = reading / block_scale(world, str(row["bench"]), str(row["batch"]))
        entry = table.setdefault(str(row["cartridge"]), [0.0, 0.0, 0.0])
        entry[0] += pressure
        entry[1] += 1.0
        entry[2] += 1.0 if str(row["result"]) == "leak" else 0.0
    out = [
        (total / units, int(units), int(leaks))
        for total, units, leaks in table.values()
        if units
    ]
    return sorted(out)


def fit(levels_seen: Sequence[tuple[float, int, int]]) -> tuple[float, float, float, float, float]:
    "A straight line through the ladder's log-odds, weighted by its units."

    usable = [
        (pressure, units, leaks)
        for pressure, units, leaks in levels_seen
        if units >= 1
    ]
    if len(usable) < 2:
        raise ValueError("the ladder needs at least two levels that count")
    s0 = s1 = s2 = t0 = t1 = 0.0
    for pressure, units, leaks in usable:


        fraction = min(max((leaks + 0.5) / (units + 1.0), 1e-6), 1.0 - 1e-6)
        weight = units * fraction * (1.0 - fraction)
        value = w.logit(fraction)
        s0 += weight
        s1 += weight * pressure
        s2 += weight * pressure * pressure
        t0 += weight * value
        t1 += weight * value * pressure
    determinant = s0 * s2 - s1 * s1
    if abs(determinant) < 1e-12:
        raise ValueError("the ladder's levels do not separate")
    intercept = (s2 * t0 - s1 * t1) / determinant
    slope = (s0 * t1 - s1 * t0) / determinant
    return intercept, slope, s2 / determinant, s0 / determinant, -s1 / determinant


def maximum_likelihood_fit(
    levels_seen: Sequence[tuple[float, int, int]],
) -> tuple[float, float, float, float, float]:
    'The other fit admitted by the prose contract.'

    intercept, slope, _var_a, _var_b, _cov_ab = fit(levels_seen)
    usable = [
        (float(pressure), int(units), int(leaks))
        for pressure, units, leaks in levels_seen
        if int(units) >= 1
    ]
    if len(usable) < 2:
        raise ValueError("the ladder needs at least two levels that count")
    covariance: tuple[float, float, float] | None = None
    for _step in range(200):
        s0 = s1 = s2 = t0 = t1 = 0.0
        for pressure, units, leaks in usable:
            eta = max(-40.0, min(40.0, intercept + slope * pressure))
            fraction = 1.0 / (1.0 + math.exp(-eta))
            weight = max(units * fraction * (1.0 - fraction), 1e-9)
            target = eta + (leaks - units * fraction) / weight
            s0 += weight
            s1 += weight * pressure
            s2 += weight * pressure * pressure
            t0 += weight * target
            t1 += weight * target * pressure
        determinant = s0 * s2 - s1 * s1
        if abs(determinant) < 1e-12:
            raise ValueError("the ladder's levels do not separate")
        moved_a = (s2 * t0 - s1 * t1) / determinant
        moved_b = (s0 * t1 - s1 * t0) / determinant
        done = abs(moved_a - intercept) < 1e-10 and abs(moved_b - slope) < 1e-12
        intercept, slope = moved_a, moved_b
        covariance = (s2 / determinant, s0 / determinant, -s1 / determinant)
        if done:
            break
    if covariance is None:
        raise ValueError("the ladder's levels do not separate")
    return intercept, slope, *covariance


def crossing(levels_seen: Sequence[tuple[float, int, int]]) -> float:
    intercept, slope, _va, _vb, _cab = fit(levels_seen)
    if abs(slope) < 1e-9:
        raise ValueError("the ladder's log-odds do not climb")
    return (_TARGET_LOGIT - intercept) / slope


def half_width(levels_seen: Sequence[tuple[float, int, int]]) -> float:
    'Two standard errors of the crossing, off the units the ladder counted.'

    intercept, slope, var_a, var_b, cov_ab = fit(levels_seen)
    value = (_TARGET_LOGIT - intercept) / slope
    variance = (var_a + value * value * var_b + 2.0 * value * cov_ab) / (slope * slope)
    return 2.0 * math.sqrt(max(variance, 0.0))


def maximum_likelihood_half_width(
    levels_seen: Sequence[tuple[float, int, int]],
) -> float:
    'Two standard errors of the crossing under maximum likelihood.'

    intercept, slope, var_a, var_b, cov_ab = maximum_likelihood_fit(levels_seen)
    value = (_TARGET_LOGIT - intercept) / slope
    variance = (var_a + value * value * var_b + 2.0 * value * cov_ab) / (slope * slope)
    return 2.0 * math.sqrt(max(variance, 0.0))


def reading(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    'What the ladder gives when the console, the span and the hold are read.'

    return crossing(levels(world, stream))


def supported_half_width(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    return half_width(levels(world, stream))


def admitted_half_widths(
    world: w.World, stream: Sequence[Mapping[str, Any]] = ()
) -> tuple[float, float]:
    'The two-standard-error widths of the two admitted fits.'

    levels_seen = levels(world, stream)
    return half_width(levels_seen), maximum_likelihood_half_width(levels_seen)


def interval(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> tuple[float, float]:
    value = reading(world, stream)
    spread = supported_half_width(world, stream)
    return value - spread, value + spread


def console_bar_reading(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    "The ladder read in the console's own bar, with no block behind it."

    return crossing(levels(world, stream, correct_bench=False))


def pinned_rows_reading(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    'The ladder with the rows that stopped at the sticker kept as a level.'

    return crossing(levels(world, stream, drop_pinned=False))


def short_hold_reading(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    'The ladder with every hold poured into the same levels.'

    return crossing(levels(world, stream, plan_hold_only=False))


def misreadings(
    world: w.World, stream: Sequence[Mapping[str, Any]] = ()
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, kwargs in (
        ("console_bar", {"correct_bench": False}),
        ("pinned_rows", {"drop_pinned": False}),
        ("short_hold", {"plan_hold_only": False}),
        ("console_bar_and_pinned", {"correct_bench": False, "drop_pinned": False}),
        ("pinned_and_short_hold", {"drop_pinned": False, "plan_hold_only": False}),
        ("everything_pooled",
         {"correct_bench": False, "drop_pinned": False, "plan_hold_only": False}),
    ):
        try:
            out[name] = crossing(levels(world, stream, **kwargs))
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
    return out


def readable_cartridges(world: w.World) -> list[str]:
    'The cartridges whose reading does not stop at the sticker on every bench.'

    out = []
    for name in sorted(world.spec["cartridges"], key=world.true_bar):
        pressure = world.true_bar(name)
        if any(
            world.console(bench, pressure) < world.span_bar - 1e-9
            for bench in world.spec["benches"]
        ):
            out.append(name)
    return out


def bracketing_cartridges(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> list[str]:
    'The two cartridges the crossing sits between on the ladder as it stands.'

    value = reading(world, stream)
    readable = readable_cartridges(world)
    below = [name for name in readable if world.true_bar(name) <= value]
    above = [name for name in readable if world.true_bar(name) > value]
    out = []
    if below:
        out.append(max(below, key=world.true_bar))
    if above:
        out.append(min(above, key=world.true_bar))
    return out


def session_hours(world: w.World, dwell_min: int) -> float:
    return world.hours_charged(int(dwell_min))


def stores_can_fill(world: w.World, stream: Sequence[Mapping[str, Any]], units: int) -> bool:
    return any(left >= int(units) for left in world.stock_left(stream).values())


def stop_is_the_only_answer(world: w.World, stream: Sequence[Mapping[str, Any]]) -> bool:
    'Whether the hours or the stores left will no longer carry a session.'

    hold = int(world.spec["plan_hold_min"])
    if world.hours_left(stream) < session_hours(world, hold) - 1e-9:
        return True
    if not stores_can_fill(world, stream, 1):
        return True
    return world.served_on(stream) is None


def best_session(world: w.World, stream: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    'The session this review would book next if it were booking soundly.'

    if stop_is_the_only_answer(world, stream):
        return None
    hold = int(world.spec["plan_hold_min"])
    day = world.served_on(stream)
    benches = [
        name for name in sorted(world.spec["benches"])
        if not world.bench_is_out(name, str(day))
    ]
    if not benches:
        return None
    stock = world.stock_left(stream)
    batch = max(sorted(stock), key=lambda name: stock[name])
    units = min(int(world.spec["ports"]), stock[batch])
    if units < 1:
        return None
    wanted = bracketing_cartridges(world, stream)
    if not wanted:
        return None


    counted = {pressure: units for pressure, units, _leaks in levels(world, stream)}

    def carried(name: str) -> int:
        pressure = world.true_bar(name)
        near = min(counted, key=lambda item: abs(item - pressure), default=None)
        return counted.get(near, 0) if near is not None else 0

    cartridge = min(wanted, key=lambda name: (carried(name), world.true_bar(name)))
    return {
        "bench": benches[0],
        "batch": batch,
        "cartridge": cartridge,
        "dwell_min": hold,
        "units": int(units),
    }


def walk_to_exhaustion(
    world: w.World, stream: Sequence[Mapping[str, Any]], limit: int = 12
) -> list[dict[str, Any]]:
    'The stream this review reaches by booking soundly until nothing is left.'

    grown = [dict(item) for item in stream]
    for _step in range(limit):
        session = best_session(world, grown)
        if session is None:
            break
        grown = w.extend(
            world, grown, [dict(session, booking_id=f"walk-{len(grown) + 1:02d}")]
        )
    return grown
