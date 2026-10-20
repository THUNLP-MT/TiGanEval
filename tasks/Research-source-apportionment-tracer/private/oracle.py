"What the world says, computed from the world's own parameters and records."

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from . import world as w
from .world import SUPPLIES, solve3


TOLERANCE = 0.04


BAND_ASK = 0.02


NARROW_FACTOR = 0.8
WIDE_FACTOR = 2.5

COVERAGE = 0.8


MOVEMENT_GAP = 1.5
TRACKING_POWER = 0.5


WINDOW_TRACKING_SPREAD = 1.15

INVARIANCE_SLACK = 0.02


CLASSIFY_SLACK = 0.008


CARRIED_OVER_GAP = 0.04


BETA_RANGE = (0.0, 12.0)


LEVER_MIN = 3.0

SPREAD = 2.0


def truth(world: w.World) -> tuple[float, float, float]:
    "Each supply's share of the window's delivered heat, as the world sets it."

    totals = [0.0, 0.0, 0.0]
    heat = 0.0
    for day in world.days:
        kwh = float(world.kwh[day])
        mixture = world.mixture(day)
        heat += kwh
        for index in range(3):
            totals[index] += kwh * mixture[index]
    return tuple(value / heat for value in totals)


def sheet(world: w.World) -> dict[str, Any]:
    'The signatures the characterisation sheet prints, as a notebook reads them.'

    rows = world.signature_rows()
    return {
        "conductivity": tuple(float(row["cond_uScm"]) for row in rows),
        "marker": tuple(
            float(row["mark_muL"]) if row["mark_flag"] == "value" else None for row in rows
        ),
        "marker_floor": tuple(float(row["mark_floor_muL"]) for row in rows),
        "read_on": str(world.sheet_day),
        "outdoor_C": float(world.sheet_outdoor_C),
    }


def sigma(world: w.World, dwell_min: int = 5) -> dict[str, float]:
    suffix = "30" if int(dwell_min) >= 30 else "5"
    values = world.spec["sigma"]
    return {
        "conductivity": float(values[f"conductivity_{suffix}"]),
        "marker": float(values[f"marker_{suffix}"]),
        "ripple": float(values["ripple"]),
    }


def _in_event(world: w.World, stamp: str) -> bool:
    return world.event_at(stamp) is not None


def header_samples(
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    *,
    set_aside: bool = True,
) -> list[dict[str, Any]]:
    'The header samples a reading of this window stands on.'

    return [
        dict(sample)
        for sample in world.sample_rows(ledger)
        if str(sample["point"]) == "header"
        and world.days[0] <= str(sample["taken_at"])[:10] <= world.days[-1]
        and sample.get("cond_uScm") is not None
        and sample.get("mark_flag") == "value"
        and (not set_aside or not _in_event(world, str(sample["taken_at"])))
    ]


def set_aside_ids(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(sample["sample_id"])
        for sample in world.sample_rows(ledger)
        if world.days[0] <= str(sample["taken_at"])[:10] <= world.days[-1]
        and _in_event(world, str(sample["taken_at"]))
    ]


def weights(world: w.World, samples: Sequence[Mapping[str, Any]]) -> list[float]:
    "Each sample's share of the heat: its day's kilowatt-hours, split between     the samples kept from that day."

    counts: dict[str, int] = {}
    for sample in samples:
        day = str(sample["taken_at"])[:10]
        counts[day] = counts.get(day, 0) + 1
    raw = []
    for sample in samples:
        day = str(sample["taken_at"])[:10]
        raw.append(float(world.kwh.get(day, 0.0)) / counts[day])
    total = sum(raw)
    return [value / total for value in raw] if total else [0.0] * len(raw)


def matrix(
    world: w.World,
    signatures: Mapping[str, Any],
    temperature: float,
    marker_recovery: float,
    beta: float,
) -> list[list[float]]:
    conductivity = list(signatures["conductivity"])
    conductivity[0] = conductivity[0] - float(beta) * (
        float(signatures["outdoor_C"]) - float(temperature)
    )
    marker = list(signatures["marker"])
    marker[2] = float(marker_recovery)
    return [conductivity, marker, [1.0, 1.0, 1.0]]


def sample_shares(
    world: w.World,
    signatures: Mapping[str, Any],
    sample: Mapping[str, Any],
    marker_recovery: float,
    beta: float,
) -> tuple[float, float, float]:
    day = str(sample["taken_at"])[:10]
    temperature = float(world.temperature.get(day, world.sheet_outdoor_C))
    rows = matrix(world, signatures, temperature, marker_recovery, beta)
    answer = solve3(rows, [float(sample["cond_uScm"]), float(sample["mark_muL"]), 1.0])
    return tuple(answer)


def combine(
    world: w.World,
    samples: Sequence[Mapping[str, Any]],
    marker_recovery: float,
    beta: float,
    *,
    weighted: bool = True,
    signatures: Mapping[str, Any] | None = None,
) -> tuple[float, float, float]:
    "The window's apportionment from one reading of the samples."

    signatures = signatures or sheet(world)
    if not samples:
        return (0.0, 0.0, 0.0)
    share = weights(world, samples) if weighted else [1.0 / len(samples)] * len(samples)
    totals = [0.0, 0.0, 0.0]
    for weight, sample in zip(share, samples):
        values = sample_shares(world, signatures, sample, marker_recovery, beta)
        for index in range(3):
            totals[index] += weight * values[index]
    return tuple(totals)


def rate_reading(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[float, float] | None:
    "The dosing rate and how sure of it the analyser's repeatability leaves us."

    signatures = sheet(world)
    readings: list[tuple[float, float]] = []
    for entry in ledger:
        if entry.get("refusal") or str(entry.get("point")) != "tie_in_plant_room":
            continue
        for reading in entry.get("readings", ()):
            if reading.get("cond_uScm") is None:
                continue
            temperature = float(world.temperature.get(str(reading["taken_at"])[:10], 0.0))
            readings.append((temperature, float(reading["cond_uScm"])))
    if not readings:
        return None
    lever = signatures["outdoor_C"] - sum(item[0] for item in readings) / len(readings)
    if abs(lever) < LEVER_MIN:
        return None
    cold = sum(item[1] for item in readings) / len(readings)
    beta = (signatures["conductivity"][0] - cold) / lever
    noise = sigma(world)["conductivity"]
    spread = math.sqrt(noise**2 / 3.0 + noise**2 / len(readings)) / abs(lever)
    return beta, spread


def beta_of(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> float:
    reading = rate_reading(world, ledger)
    return reading[0] if reading else 0.0


def marker_reading(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[float, float] | None:
    'The recovery marker, when a long dwell on the riser has read it.'

    long_dwell: list[float] = []
    for entry in ledger:
        if entry.get("refusal") or str(entry.get("point")) != "east_riser":
            continue
        for reading in entry.get("readings", ()):
            if reading.get("mark_flag") == "value" and int(reading["dwell_min"]) >= 30:
                long_dwell.append(float(reading["mark_muL"]))
    if long_dwell:
        return (
            sum(long_dwell) / len(long_dwell),
            sigma(world, 30)["marker"] / math.sqrt(len(long_dwell)),
        )
    return None


def marker_interval(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[float, float]:
    'Everything the recovery marker could still be.'

    signatures = sheet(world)
    printed = signatures["marker"][2]
    if printed is not None:
        return (printed, printed)
    reading = marker_reading(world, ledger)
    if reading is not None:
        value, spread = reading
        return (max(0.0, value - SPREAD * spread), value + SPREAD * spread)
    return (0.0, float(signatures["marker_floor"][2]))


def per_sample_spread(
    world: w.World,
    signatures: Mapping[str, Any],
    sample: Mapping[str, Any],
    marker_recovery: float,
    beta: float,
) -> tuple[float, float, float]:
    'What one reading of the analyser is worth, carried into the three shares.'

    noise = sigma(world, int(sample.get("dwell_min", 5)))
    base = sample_shares(world, signatures, sample, marker_recovery, beta)
    moved_c = sample_shares(
        world,
        signatures,
        dict(sample, cond_uScm=float(sample["cond_uScm"]) + noise["conductivity"]),
        marker_recovery,
        beta,
    )
    moved_m = sample_shares(
        world,
        signatures,
        dict(sample, mark_muL=float(sample["mark_muL"]) + noise["marker"]),
        marker_recovery,
        beta,
    )
    return tuple(
        math.sqrt((moved_c[index] - base[index]) ** 2 + (moved_m[index] - base[index]) ** 2)
        for index in range(3)
    )


def standard_error(
    world: w.World,
    samples: Sequence[Mapping[str, Any]],
    marker_recovery: float,
    beta: float,
) -> tuple[float, float, float]:
    'How far the reading itself can sit from what the samples measured.'

    if not samples:
        return (0.0, 0.0, 0.0)
    signatures = sheet(world)
    share = weights(world, samples)
    totals = [0.0, 0.0, 0.0]
    for weight, sample in zip(share, samples):
        spread = per_sample_spread(world, signatures, sample, marker_recovery, beta)
        for index in range(3):
            totals[index] += (weight * spread[index]) ** 2
    return tuple(math.sqrt(value) for value in totals)


def reading(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> tuple[float, float, float]:
    'The figure the records support: the middle of what the marker leaves.'

    samples = header_samples(world, ledger)
    low, high = marker_interval(world, ledger)
    return combine(world, samples, (low + high) / 2.0, beta_of(world, ledger))


def sweep(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[tuple[float, float], ...]:
    "Each share's range as the recovery marker runs over what is left of it."

    samples = header_samples(world, ledger)
    beta = beta_of(world, ledger)
    low, high = marker_interval(world, ledger)
    ends = [
        combine(world, samples, low, beta),
        combine(world, samples, high, beta),
    ]
    return tuple(
        (min(ends[0][index], ends[1][index]), max(ends[0][index], ends[1][index]))
        for index in range(3)
    )


def band(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> dict[str, list[float]]:
    'The band the records support, low endpoint first.'

    samples = header_samples(world, ledger)
    low, high = marker_interval(world, ledger)
    beta = beta_of(world, ledger)
    spread = standard_error(world, samples, (low + high) / 2.0, beta)
    ends = sweep(world, ledger)
    rate = rate_spread(world, ledger)
    return {
        supply: [
            ends[index][0] - SPREAD * spread[index] - rate[index],
            ends[index][1] + SPREAD * spread[index] + rate[index],
        ]
        for index, supply in enumerate(SUPPLIES)
    }


def rate_spread(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[float, float, float]:
    'How far the shares move over what is left of the dosing rate.'

    samples = header_samples(world, ledger)
    low, high = marker_interval(world, ledger)
    middle = (low + high) / 2.0
    found = rate_reading(world, ledger)
    if found is None:
        span = BETA_RANGE
    else:
        span = (found[0] - SPREAD * found[1], found[0] + SPREAD * found[1])
    lower = combine(world, samples, middle, span[0])
    upper = combine(world, samples, middle, span[1])
    return tuple(abs(upper[index] - lower[index]) / 2.0 for index in range(3))


def supported_half(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> float:
    "The half-width the recovery share's band cannot honestly fall inside."

    samples = header_samples(world, ledger)
    low, high = marker_interval(world, ledger)
    spread = standard_error(world, samples, (low + high) / 2.0, beta_of(world, ledger))
    ends = sweep(world, ledger)
    return (ends[2][1] - ends[2][0]) / 2.0 + SPREAD * spread[2]


def identification_half(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> float:
    "The widest of the three shares' bands, the rate included."

    samples = header_samples(world, ledger)
    low, high = marker_interval(world, ledger)
    spread = standard_error(world, samples, (low + high) / 2.0, beta_of(world, ledger))
    ends = sweep(world, ledger)
    rate = rate_spread(world, ledger)
    return max(
        (ends[index][1] - ends[index][0]) / 2.0 + SPREAD * spread[index] + rate[index]
        for index in range(3)
    )


def rate_is_measured(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> bool:
    return rate_reading(world, ledger) is not None


def header_slope(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> float:
    "The rate a regression of the header's own rows on the weather gives."

    samples = header_samples(world, ledger)
    points = [
        (float(world.temperature[str(sample["taken_at"])[:10]]), float(sample["cond_uScm"]))
        for sample in samples
    ]
    if len(points) < 2:
        return 0.0
    mean_t = sum(point[0] for point in points) / len(points)
    mean_c = sum(point[1] for point in points) / len(points)
    top = sum((point[0] - mean_t) * (point[1] - mean_c) for point in points)
    bottom = sum((point[0] - mean_t) ** 2 for point in points)
    return -top / bottom if bottom else 0.0


def misreadings(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[float, float, float]]:
    'The apportionments the families of misreading produce on this window.'

    signatures = sheet(world)
    beta = beta_of(world, ledger)
    low, high = marker_interval(world, ledger)
    middle = (low + high) / 2.0
    kept = header_samples(world, ledger)
    everything = header_samples(world, ledger, set_aside=False)
    floor = float(signatures["marker_floor"][2])
    printed = signatures["marker"][2]
    at_floor = printed if printed is not None else floor
    return {
        "sheet_signature": combine(world, kept, middle, 0.0),
        "header_slope": combine(world, kept, middle, header_slope(world, ledger)),
        "unweighted": combine(world, kept, middle, beta, weighted=False),
        "changeover_kept": combine(world, everything, middle, beta),
        "floor_as_value": combine(world, kept, at_floor, beta),
        "sheet_and_unweighted": combine(world, kept, middle, 0.0, weighted=False),
        "sheet_and_floor": combine(world, kept, at_floor, 0.0),
        "everything_wrong": combine(world, everything, at_floor, 0.0, weighted=False),
    }


def slot_cost(world: w.World, plan: Mapping[str, Any]) -> int:
    return w.slot_cost(
        str(plan.get("point")),
        int(plan.get("dwell_min", 5)),
        int(plan.get("samples", 0)),
        tuple(plan.get("channels", ("conductivity", "marker"))),
        world.spec,
    )


def plan_refusal(world: w.World, plan: Mapping[str, Any]) -> str | None:
    return w.refusal_reason(
        world,
        plan.get("point"),
        int(plan.get("dwell_min", 5)),
        int(plan.get("samples", 0)),
        tuple(plan.get("channels", ("conductivity", "marker"))),
    )


def _predicted(world: w.World, ledger: Sequence[Mapping[str, Any]], plan: Mapping[str, Any]):
    'The ledger this window would hold after one more visit, read noiselessly.'

    served = [str(entry["served_on"]) for entry in ledger]
    free = [day for day in world.open_days() if day not in served]
    if not free:
        return None
    channels = tuple(
        name for name in w.CHANNELS
        if name in tuple(plan.get("channels", ("conductivity", "marker")))
    )
    day = free[0]
    temperature = float(world.temperature.get(day, world.sheet_outdoor_C))
    point = str(plan.get("point"))
    dwell = int(plan.get("dwell_min", 5))
    count = int(plan.get("samples", 0))
    mix = world._pure(point, temperature)
    if mix is None:
        mix = world.mixture(day)
    ends = world.endmembers(temperature)
    readings = []
    for index in range(count):
        row = {
            "sample_id": f"plan-{index + 1}",
            "taken_at": f"{day}T09:{20 + index:02d}:00",
            "point": point,
            "dwell_min": dwell,
        }
        if "conductivity" in channels:
            row["cond_uScm"] = sum(
                mix[position] * ends["conductivity"][position] for position in range(3)
            )
        if "marker" in channels:
            value = sum(mix[position] * ends["marker"][position] for position in range(3))
            floor = float(world.spec["marker_floor_30"] if dwell >= 30 else world.spec["marker_floor_5"])
            if value < floor:
                row["mark_muL"] = None
                row["mark_flag"] = "floor"
            else:
                row["mark_muL"] = value
                row["mark_flag"] = "value"
        if "ripple" in channels:
            row["ripple_idx"] = sum(
                mix[position] * ends["ripple"][position] for position in range(3)
            )
        readings.append(row)
    entry = {
        "call_id": "planned",
        "point": point,
        "channels": list(channels),
        "dwell_min": dwell,
        "slots_charged": slot_cost(world, plan),
        "served_on": day,
        "refusal": None,
        "readings": readings,
    }
    return [*ledger, entry]


def width_after(
    world: w.World, ledger: Sequence[Mapping[str, Any]], plan: Mapping[str, Any]
) -> float:
    grown = _predicted(world, ledger, plan)
    if grown is None:
        return identification_half(world, ledger)
    return identification_half(world, grown)


def header_bar(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> float:
    'What another round of header samples would leave, and no visit may match.'

    left = world.slots_left(ledger)
    count = min(int(world.spec["slots_per_visit"]), max(1, left))
    return width_after(
        world,
        ledger,
        {"point": "header", "dwell_min": 5, "samples": count,
         "channels": ("conductivity", "marker")},
    )


def affordable_plans(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every visit the agreement would serve from here, one point at a time.'

    left = world.slots_left(ledger)
    plans: list[dict[str, Any]] = []
    for point in world.spec["access_points"]:
        for dwell in (5, 30):
            for count in range(1, int(world.spec["slots_per_visit"]) + 1):
                for channels in (
                    ("conductivity", "marker"),
                    ("conductivity", "marker", "ripple"),
                ):
                    plan = {
                        "point": point,
                        "dwell_min": dwell,
                        "samples": count,
                        "channels": channels,
                    }
                    if plan_refusal(world, plan) is not None:
                        continue
                    if slot_cost(world, plan) > left:
                        continue
                    plans.append(plan)
    return plans


def plan_state(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'What this window can still buy, and whether stopping is the answer.'

    left = world.slots_left(ledger)
    here = identification_half(world, ledger)
    bar = header_bar(world, ledger)
    served = {str(entry["served_on"]) for entry in ledger}
    rounds_left = [day for day in world.open_days() if day not in served]
    plans = affordable_plans(world, ledger) if rounds_left else []
    best = min((width_after(world, ledger, plan) for plan in plans), default=here)
    inside = supported_half(world, ledger) <= BAND_ASK and rate_is_measured(world, ledger)
    return {
        "slots_left": left,
        "width": here,
        "bar": bar,
        "best": best,
        "rounds_left": len(rounds_left),
        "rate_measured": rate_is_measured(world, ledger),
        "recovery_half": supported_half(world, ledger),
        "stop_only": bool(inside or best > here * 0.99),
    }


def plan_qualifies(
    world: w.World, ledger: Sequence[Mapping[str, Any]], plan: Mapping[str, Any]
) -> bool:
    return width_after(world, ledger, plan) <= header_bar(world, ledger) * 0.99
