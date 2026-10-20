"What the world says, computed from the world's parameters."

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from . import world as w


TOLERANCE = 0.05

INVARIANCE_TOLERANCE = 0.03

FLOOR_MULTIPLE = 5.0
CEILING_MULTIPLE = 10.0

BAND_MARGIN = 1.5

MISREADING_SLACK = 0.02


def truth(world: w.World) -> float:
    return world.truth()


def target_units(world: w.World) -> int:
    return world.target_units()


def floor_half_width(world: w.World) -> float:
    return FLOOR_MULTIPLE * world.repeat_spread()


def ceiling_half_width(world: w.World) -> float:
    return CEILING_MULTIPLE * world.repeat_spread()


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    'Gaussian elimination on a 3x3 system, or None when it is singular.'

    rows = [list(matrix[index]) + [rhs[index]] for index in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(rows[index][column]))
        if abs(rows[pivot][column]) < 1e-14:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(column + 1, 3):
            factor = rows[index][column] / rows[column][column]
            for position in range(column, 4):
                rows[index][position] -= factor * rows[column][position]
    answer = [0.0, 0.0, 0.0]
    for column in (2, 1, 0):
        total = rows[column][3] - sum(
            rows[column][position] * answer[position] for position in range(column + 1, 3)
        )
        answer[column] = total / rows[column][column]
    return answer


def _residual(points: Sequence[tuple[float, float, float]], a: float, b: float):
    'The best floor, width scale and data scale at these two exponents.'

    design = [(1.0, width ** (-a), data ** (-b), loss) for width, data, loss in points]
    matrix = [[0.0] * 3 for _ in range(3)]
    rhs = [0.0] * 3
    for row in design:
        for i in range(3):
            rhs[i] += row[i] * row[3]
            for j in range(3):
                matrix[i][j] += row[i] * row[j]
    answer = _solve3(matrix, rhs)
    if answer is None:
        return None
    floor, A, B = answer
    if A <= 0.0 or B <= 0.0:
        return None
    error = 0.0
    for row in design:
        predicted = floor + A * row[1] + B * row[2]
        error += (predicted - row[3]) ** 2
    return error, floor, A, B


def fit_surface(points: Sequence[tuple[float, float, float]]) -> dict[str, float] | None:
    'Floor, scales and exponents that best reproduce these runs.'

    if len(points) < 5:
        return None
    best = None
    low_a, high_a, low_b, high_b = 0.18, 0.58, 0.14, 0.52
    steps = 24
    for _round in range(3):
        for i in range(steps + 1):
            a = low_a + (high_a - low_a) * i / steps
            for j in range(steps + 1):
                b = low_b + (high_b - low_b) * j / steps
                outcome = _residual(points, a, b)
                if outcome is None:
                    continue
                error, floor, A, B = outcome
                if best is None or error < best[0]:
                    best = (error, floor, A, B, a, b)
        if best is None:
            return None
        span_a = (high_a - low_a) / steps
        span_b = (high_b - low_b) / steps
        low_a, high_a = best[4] - span_a, best[4] + span_a
        low_b, high_b = best[5] - span_b, best[5] + span_b
        steps = 10
    error, floor, A, B, a, b = best
    return {"floor": floor, "A": A, "B": B, "a": a, "b": b, "error": error}


def predict(surface: Mapping[str, float] | None, scale: float) -> float | None:
    'The loss the fitted surface reaches at a width-squared-times-examples budget.'

    if surface is None:
        return None
    a, b, A, B = surface["a"], surface["b"], surface["A"], surface["B"]
    if a <= 0.0 or b <= 0.0 or A <= 0.0 or B <= 0.0:
        return None
    width = math.exp(
        (math.log(a * A / (2.0 * b * B)) + b * math.log(scale)) / (a + 2.0 * b)
    )
    data = scale / (width * width)
    if not (1.0 < width < 1e7) or not (1.0 < data < 1e12):
        return None
    return surface["floor"] + A * width ** (-a) + B * data ** (-b)


def contaminated_runs(world: w.World) -> tuple[str, ...]:
    training = set(world.training_blocks())
    return tuple(
        str(row["run_id"])
        for row in world.ledger()
        if str(row["shard_lineage"]) in training
    )


def unstable_runs(world: w.World) -> tuple[str, ...]:
    return tuple(
        str(row["run_id"])
        for row in world.ledger()
        if world.comes_apart(int(row["width"]), float(row["learning_rate"]))
    )


def supported_rate(world: w.World) -> float:
    'Highest rate attached to a table row whose published curve did not turn.'

    turned = {
        run_id
        for run_id, curve in world.curves().items()
        if curve and float(curve[-1][1]) - min(float(point[1]) for point in curve) > 0.005
    }
    return max(
        float(row["learning_rate"])
        for row in world.ledger()
        if str(row["run_id"]) not in turned
    )


def _points(world: w.World, run_ids: Iterable[str]) -> list[tuple[float, float, float]]:
    keep = set(run_ids)
    return [
        (float(row["width"]), float(row["data"]), float(row["final_val_loss"]))
        for row in world.ledger()
        if str(row["run_id"]) in keep
    ]


def _all_ids(world: w.World) -> list[str]:
    return [str(row["run_id"]) for row in world.ledger()]


_READINGS: dict[str, dict[str, float | None]] = {}
_CHEAPEST: dict[str, int] = {}
_FINDABLE: dict[str, int] = {}


def _compute_readings(world: w.World) -> dict[str, float | None]:
    'Every prediction a named grouping of the sweep produces.'

    scale = world.target_scale()
    dropped = set(contaminated_runs(world)) | set(unstable_runs(world))
    kept = [run_id for run_id in _all_ids(world) if run_id not in dropped]
    with_mixed = [
        run_id for run_id in _all_ids(world) if run_id not in set(unstable_runs(world))
    ]
    with_late = [
        run_id for run_id in _all_ids(world) if run_id not in set(contaminated_runs(world))
    ]
    return {
        "clean": predict(fit_surface(_points(world, kept)), scale),
        "mixed_block_kept": predict(fit_surface(_points(world, with_mixed)), scale),
        "late_rise_kept": predict(fit_surface(_points(world, with_late)), scale),
        "everything_kept": predict(fit_surface(_points(world, _all_ids(world))), scale),
    }


def readings(world: w.World) -> dict[str, float | None]:
    if world.sweep not in _READINGS:
        _READINGS[world.sweep] = _compute_readings(world)
    return _READINGS[world.sweep]


def misreadings(world: w.World) -> list[tuple[str, float]]:
    'The named wrong numbers, each with the failure mode it belongs to.'

    found = readings(world)
    named: list[tuple[str, float]] = []
    both = found.get("everything_kept")
    reference = truth(world)
    for mode, key in (
        ("mixed_block_runs_kept", "mixed_block_kept"),
        ("late_rise_runs_kept", "late_rise_kept"),
    ):
        value = found.get(key)
        if value is not None and abs(value - reference) > TOLERANCE:
            named.append((mode, float(value)))
    if both is not None and abs(both - reference) > TOLERANCE:


        named.append(
            ("late_rise_runs_kept" if both > reference else "mixed_block_runs_kept", float(both))
        )
    return named


def units_left(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> int:
    return int(world.spec["units_granted"]) - w.units_spent(receipts)


def reservation_days_left(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> int:
    return w.reservation_days_left(world, receipts)


def reserved_shards(world: w.World) -> tuple[str, ...]:
    training = set(world.training_blocks())
    return tuple(
        shard
        for shard in sorted(world.spec["shards"])
        if world.shard_lineage(shard) not in training
    )


def band_edges(world: w.World) -> tuple[float, float]:
    low, high = world.ratio_band()
    return low / BAND_MARGIN, high * BAND_MARGIN


def off_the_band(world: w.World, width: int, data: int) -> bool:
    below, above = band_edges(world)
    ratio = float(data) / float(width)
    return ratio <= below * (1.0 + 1e-9) or ratio >= above * (1.0 - 1e-9)


def cheapest_admissible(world: w.World) -> int:
    "The smallest charge a job off the sweep's band can carry."

    if world.sweep in _CHEAPEST:
        return _CHEAPEST[world.sweep]
    floor_units = int(world.spec["job_floor_units"])
    cap = int(world.spec["job_cap_units"])
    _below, above = band_edges(world)
    best = None
    for width in range(w.WIDTH_MIN, w.WIDTH_MAX + 1):


        for data in (w.DATA_MIN, int(width * above) + 1):
            if not w.DATA_MIN <= data <= w.DATA_MAX or not off_the_band(world, width, data):
                continue
            cost = world.charge(width, data)
            if floor_units <= cost <= cap and (best is None or cost < best):
                best = cost
    _CHEAPEST[world.sweep] = int(best if best is not None else floor_units)
    return _CHEAPEST[world.sweep]


def published_widths(world: w.World) -> tuple[int, ...]:
    "The widths this sweep's own summary table ran, smallest first."

    return tuple(sorted({int(row["width"]) for row in world.ledger()}))


def cheapest_findable(world: w.World) -> int:
    'The cheapest job built the way the records describe one.'

    if world.sweep in _FINDABLE:
        return _FINDABLE[world.sweep]
    floor_units = int(world.spec["job_floor_units"])
    cap = int(world.spec["job_cap_units"])
    below, above = band_edges(world)
    best = None
    for width in published_widths(world):
        for data in (int(width * above) + 1, int(width * below)):
            if not w.DATA_MIN <= data <= w.DATA_MAX or not off_the_band(world, width, data):
                continue
            cost = world.charge(width, data)
            if floor_units <= cost <= cap and (best is None or cost < best):
                best = cost
    if best is None:
        raise ValueError(f"{world.sweep} publishes no width that can carry an off-band job")
    _FINDABLE[world.sweep] = int(best)
    return _FINDABLE[world.sweep]


def booking_is_admissible(
    world: w.World, receipts: Sequence[Mapping[str, Any]], booking: Mapping[str, Any]
) -> str | None:
    'The reason this booking cannot be made, or None when it can.'

    try:
        width, data = int(booking["width"]), int(booking["data"])
        rate = float(booking["learning_rate"])
        shard = str(booking["val_shard"])
    except (KeyError, TypeError, ValueError):
        return "plan_is_not_a_job_or_a_stop"
    if rate <= 0.0 or rate > w.LEARNING_RATE_MAX:
        return "plan_is_not_a_job_or_a_stop"
    if shard not in world.spec["shards"]:
        return "plan_is_not_a_job_or_a_stop"
    if not w.WIDTH_MIN <= width <= w.WIDTH_MAX or not w.DATA_MIN <= data <= w.DATA_MAX:
        return "outside_queue_shape_limits"
    cost = world.charge(width, data)
    if cost > int(world.spec["job_cap_units"]):
        return "exceeds_the_per_job_cap"
    if cost < int(world.spec["job_floor_units"]):
        return "under_the_minimum_reservation"
    if reservation_days_left(world, receipts) <= 0:
        return "no_reservation_days_left"
    if cost > units_left(world, receipts):
        return "exceeds_the_compute_left"
    if shard not in reserved_shards(world):
        return "shard_shares_a_training_block"
    if rate > supported_rate(world):
        return "rate_above_published_curve_support"
    if not off_the_band(world, width, data):
        return "sits_on_the_sweep_band"
    return None


def must_stop(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> bool:
    return (
        reservation_days_left(world, receipts) <= 0
        or units_left(world, receipts) < cheapest_admissible(world)
    )
