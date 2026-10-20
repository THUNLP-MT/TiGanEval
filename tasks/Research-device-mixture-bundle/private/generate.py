'Building one fleet: its units, their captures and the rows the app carried.'

from __future__ import annotations

import random
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from .reading import CONDITIONS, CONDITION_PARAMS, FEATURES, LAW_STEEPNESS, readable_score
from .world import Capture, Fleet, PROFILES, Unit, _GOLDEN, _days


def _stream(spec: Mapping[str, Any], index: int, block: int) -> random.Random:
    return random.Random(int(spec["seed"]) * 1_000_003 + index * 17 + block)


def _shares(generator: random.Random, centre: Sequence[float], jitter: float) -> tuple[float, ...]:
    "One unit's condition mixture: its profile's, moved a little."

    drawn = [
        0.0 if float(value) <= 0.0 else max(0.01, float(value) + generator.gauss(0.0, jitter))
        for value in centre
    ]
    total = sum(drawn)
    return tuple(value / total for value in drawn)


_QUANTILES: dict[int, tuple[float, ...]] = {}


def _quantiles(count: int) -> tuple[float, ...]:
    'The `count` evenly spaced points of a standard normal, cached.'

    if count not in _QUANTILES:
        distribution = NormalDist()
        _QUANTILES[count] = tuple(
            distribution.inv_cdf((index + 0.5) / count) for index in range(count)
        )
    return _QUANTILES[count]


def _condition_counts(shares: Sequence[float], count: int) -> list[tuple[str, int]]:
    "How many of a block's captures fall in each condition, in proportion."

    exact = [float(share) * count for share in shares]
    whole = [int(value) for value in exact]
    spare = count - sum(whole)
    order = sorted(
        (index for index in range(len(shares)) if float(shares[index]) > 0.0),
        key=lambda index: -(exact[index] - whole[index]),
    )
    for position in range(spare):
        whole[order[position % len(order)]] += 1
    return [
        (CONDITIONS[index], whole[index]) for index in range(len(CONDITIONS)) if whole[index]
    ]


def _condition_block(
    generator: random.Random, condition: str, count: int
) -> list[tuple[float, ...]]:
    '`count` captures of one condition, spread evenly over every column.'

    centre, spread = CONDITION_PARAMS[condition]
    points = _quantiles(count)
    columns = []
    for _ in range(len(FEATURES)):
        drawn = list(points)
        generator.shuffle(drawn)
        columns.append(drawn)
    return [
        tuple(
            max(0.01, centre[axis] + spread[axis] * columns[axis][position])
            for axis in range(len(FEATURES))
        )
        for position in range(count)
    ]


def _block(
    spec: Mapping[str, Any],
    generator: random.Random,
    shares: Sequence[float],
    count: int,
) -> list[tuple[str, tuple[float, ...], int]]:
    "One block of a unit's captures, with readings laid along the law's ranking."

    drawn: list[tuple[str, tuple[float, ...]]] = []
    for condition, held in _condition_counts(shares, count):
        for values in _condition_block(generator, condition, held):
            drawn.append((condition, values))
    generator.shuffle(drawn)
    ranking = sorted(range(count), key=lambda item: readable_score(drawn[item][1]))
    labels = [0] * count
    turn = float(spec["label_offset"])
    for position in ranking:
        turn = (turn + _GOLDEN) % 1.0
        score = readable_score(drawn[position][1])
        chance = 1.0 / (1.0 + pow(2.718281828459045, -LAW_STEEPNESS * score))
        labels[position] = 1 if turn < chance else 0
    return [(drawn[index][0], drawn[index][1], labels[index]) for index in range(count)]


def _positions(total: int, count: int, offset: int) -> list[int]:
    return [(offset + step) % total for step in range(min(count, total))]


def build(spec: Mapping[str, Any]) -> Fleet:
    "One fleet's units, their captures, and the rows the exporter carried."

    days = _days(spec["first_day"], int(spec["days"]))
    raised_name = str(spec["raised_firmware"])
    earlier = str(spec["earlier_firmware"])
    truth_captures = int(spec["truth_captures"])
    jitter = float(spec["share_jitter"])

    units: list[Unit] = []
    counter = 0
    for profile in PROFILES:
        plan = spec["profiles"][profile]
        total = int(plan["units"])
        reached = set(_positions(total, int(plan["reached_units"]), int(spec["reach_offset"])))
        inside = sorted(reached)
        outside = [position for position in range(total) if position not in reached]
        raised = set(inside[: int(plan["raised_reached_units"])])
        spare = int(plan["raised_units"]) - int(plan["raised_reached_units"])
        if spare > 0 and outside:
            shift = int(spec["rollout_offset"]) % len(outside)
            raised.update(outside[(shift + step) % len(outside)] for step in range(min(spare, len(outside))))
        for position in range(total):
            counter += 1
            units.append(
                Unit(
                    unit_id=f"{spec['unit_prefix']}-{counter:04d}",
                    unit_model=str(plan["unit_model"]),
                    duty_profile=profile,
                    shares=_shares(
                        _stream(spec, counter, 2), plan["shares"], jitter
                    ),
                    firmware=raised_name if position in raised else earlier,
                    in_service_on=days[(counter * 5) % len(days)],
                    reached=position in reached,
                    log_rows=int(plan["log_rows_each"]) if position in reached else 0,
                )
            )

    captures: list[Capture] = []
    log_order: list[int] = []
    for index, unit in enumerate(units):
        held = _block(spec, _stream(spec, index, 0), unit.shares, truth_captures)


        carried: set[int] = set()
        if unit.log_rows:
            ranking = sorted(range(truth_captures), key=lambda item: readable_score(held[item][1]))
            step = truth_captures / float(min(unit.log_rows, truth_captures))
            carried = {
                ranking[min(truth_captures - 1, int(position * step))]
                for position in range(min(unit.log_rows, truth_captures))
            }
        for step, (condition, values, label) in enumerate(held):
            if step in carried:
                log_order.append(len(captures))
            captures.append(
                Capture(
                    unit=index,
                    condition=condition,
                    day=days[(index + step) % len(days)],
                    truth=values,
                    label=label,
                    exported=step in carried,
                )
            )

    return Fleet(
        spec=spec,
        days=days,
        units=tuple(units),
        captures=tuple(captures),
        log_order=tuple(log_order),
    )
