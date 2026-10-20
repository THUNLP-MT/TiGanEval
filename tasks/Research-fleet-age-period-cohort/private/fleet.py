"How one region's register, exposure grid and fault log are laid down."

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from .world import (
    FAULT_CODES,
    Region,
    Van,
    add_months,
    day_in,
    half_year,
    month_key,
    month_label,
    month_length,
    month_span,
)

def _period_effects(spec: Mapping[str, Any], months: Sequence[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for index, month in enumerate(months):
        season = int(month[5:7])
        out[month] = (
            0.55 * math.sin(2.0 * math.pi * season / 12.0 + 0.7)
            + 0.22 * math.cos(2.0 * math.pi * index / 7.0 + 0.3)
        )
    return out


def _build_effects(spec: Mapping[str, Any], builds: Sequence[str], weights: Mapping[str, int]) -> dict[str, float]:
    'One effect a build standard: build months the sheets leave alike read alike.'

    segments = spec["build_segment"]
    levels = {
        segment: 0.42 * math.sin(2.7 * segment + 1.1) + 0.26 * math.cos(1.3 * segment + 0.4)
        for segment in sorted(set(segments.values()))
    }
    trend = float(spec.get("build_trend", 0.0))
    opened: dict[int, int] = {}
    for index, build in enumerate(builds):
        opened.setdefault(segments[build], index)
    wiggle = {
        build: levels[segments[build]] + trend * opened[segments[build]]
        for build in builds
    }
    early, late = spec["compare"]
    groups: dict[str, list[str]] = {}
    for build in builds:
        groups.setdefault(half_year(build), []).append(build)

    def mean(name: str) -> float:
        members = groups[name]
        total = sum(weights[build] for build in members)
        return sum(weights[build] * wiggle[build] for build in members) / total

    shift = float(spec["truth_points"]) - (mean(late) - mean(early))
    return {
        build: wiggle[build] + (shift if half_year(build) == late else 0.0)
        for build in builds
    }


def _lease_of(spec: Mapping[str, Any], build_month: str) -> tuple[str, int]:
    short = spec.get("short_lease")
    if short and half_year(build_month) == str(short["group"]):
        return str(short["lease_ref"]), int(short["months"])
    return str(spec["lease_ref"]), int(spec["lease_months"])


def _depot_share(spec: Mapping[str, Any], build_month: str, generator: random.Random) -> str:
    shares = spec["depot_shares"]
    weights = list(shares.get(half_year(build_month), shares["default"]))
    return generator.choices(list(spec["depots"]), weights=weights, k=1)[0]


def build_region(spec: Mapping[str, Any]) -> Region:
    "Run one region's parameter set into a register, an exposure grid and a log."

    months = month_span(str(spec["first_return"]), int(spec["returns"]))
    builds = month_span(str(spec["first_build"]), int(spec["builds"]))
    generator = random.Random(int(spec["draw"]))

    vans: list[Van] = []
    counter = 0
    per_build: dict[str, int] = {}
    boost = float(spec.get("cohort_boost", 1.0))
    compared = set(spec["compare"])
    for build in builds:
        count = generator.randint(*spec["per_build"])
        if half_year(build) in compared:
            count = int(round(count * boost))
        per_build[build] = count
        lease_ref, term = _lease_of(spec, build)
        for _ in range(count):
            counter += 1
            allocated = day_in(build, generator.randint(2, 24))
            in_service = day_in(month_label(month_key(build) + 2), generator.randint(1, 28))
            off_fleet = add_months(allocated, term)
            depot = _depot_share(spec, build, generator)
            transfer_date = None
            transfer_depot = None
            if generator.random() < float(spec["transfer_rate"]):
                other = [name for name in spec["depots"] if name != depot]
                transfer_depot = generator.choice(other)
                transfer_date = day_in(
                    months[generator.randrange(len(months))], generator.randint(1, 28)
                )
            vans.append(
                Van(
                    van_id=f"{spec['van_prefix']}-{counter:05d}",
                    build_month=build,
                    allocated_date=allocated,
                    in_service_date=in_service,
                    depot=depot,
                    transfer_date=transfer_date,
                    transfer_depot=transfer_depot,
                    off_fleet_date=off_fleet,
                    roster_until=(date.fromisoformat(off_fleet) + timedelta(days=80)).isoformat(),
                    lease_ref=lease_ref,
                )
            )

    spec = dict(spec)
    spec["period_effect"] = _period_effects(spec, months)
    spec["build_effect"] = _build_effects(spec, builds, per_build)

    region = Region(spec=spec, months=months, builds=builds, vans=tuple(vans), faults=())
    exposure, holders = _exposure(region)
    counts, faults = _faults(region, exposure, holders, generator)
    return Region(
        spec=spec,
        months=months,
        builds=builds,
        vans=tuple(vans),
        faults=tuple(faults),
        exposure=exposure,
        counts=counts,
    )


def _exposure(
    region: Region,
) -> tuple[
    dict[tuple[str, str, str], float],
    dict[tuple[str, str, str], list[tuple[Van, str, str]]],
]:
    'Days on the fleet that month, in service to off fleet or transfer.'

    exposure: dict[tuple[str, str, str], float] = {}
    holders: dict[tuple[str, str, str], list[tuple[Van, str, str]]] = {}
    for month in region.months:
        length = month_length(month)
        first, last = day_in(month, 1), day_in(month, length)
        for van in region.vans:
            start = max(van.in_service_date, first)
            end = min(van.off_fleet_date, last)
            if start > end:
                continue
            spans: list[tuple[str, str, str]] = []
            move = van.transfer_date
            if move and start < move <= end:
                before_move = (
                    date.fromisoformat(move) - timedelta(days=1)
                ).isoformat()
                spans.append((van.depot, start, before_move))
                spans.append((str(van.transfer_depot), move, end))
            else:
                depot = van.depot
                if move and move <= start:
                    depot = str(van.transfer_depot)
                spans.append((depot, start, end))
            for depot, run_start, run_end in spans:
                days = (date.fromisoformat(run_end) - date.fromisoformat(run_start)).days + 1
                if days <= 0:
                    continue
                key = (van.build_month, month, depot)
                exposure[key] = exposure.get(key, 0.0) + days / length
                holders.setdefault(key, []).append((van, run_start, run_end))
    return exposure, holders


def _faults(
    region: Region,
    exposure: Mapping[tuple[str, str, str], float],
    holders: Mapping[tuple[str, str, str], list[tuple[Van, str, str]]],
    generator: random.Random,
) -> tuple[dict[tuple[str, str, str], int], list[dict[str, Any]]]:
    'Faults raised in each cell, and the log rows that carry them.'

    counts: dict[tuple[str, str, str], int] = {}
    rows: list[dict[str, Any]] = []
    serial = 0


    carried: dict[tuple[str, str], float] = {}
    for key in sorted(exposure, key=lambda item: (item[2], item[0], item[1])):
        build, month, depot = key
        expected = (
            region.rate(build, month)
            * exposure[key]
            * region.card_factor(depot, month)
            / 100.0
        )
        chain = (depot, build)
        wanted = expected + carried.get(chain, 0.0)
        count = max(0, int(math.floor(wanted + 0.5)))
        carried[chain] = wanted - count
        counts[key] = count
        spans = holders[key]
        length = month_length(month)
        for step in range(count):
            van, held_from, held_to = spans[
                (step * 7 + len(spans) // 3) % len(spans)
            ]
            serial += 1
            raised = day_in(month, 1 + (step * 5 + serial) % length)
            raised = max(raised, held_from)
            raised = min(raised, held_to)
            rows.append(
                {
                    "fault_id": f"{region.spec['fault_prefix']}-{serial:05d}",
                    "van_id": van.van_id,
                    "depot": depot,
                    "raised_date": raised,
                    "walkaround_ref": region.card_on(depot, month),
                    "fault_code": FAULT_CODES[(serial * 3) % len(FAULT_CODES)],
                }
            )
    rows.sort(key=lambda row: (row["raised_date"], row["fault_id"]))
    return counts, rows
