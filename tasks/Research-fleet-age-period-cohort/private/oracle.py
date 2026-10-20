"What the region says, computed from the region's own parameters and counts."

from __future__ import annotations

from datetime import date, timedelta
from statistics import NormalDist
from typing import Any, Mapping, Sequence

import numpy as np

from . import desk, world
from .world import Region, day_in, month_key


TOLERANCE = 0.4


CLASSIFY_SLACK = 0.12


NARROW_FACTOR = 0.95
WIDE_FACTOR = 4.0
RANGE_RESPONSE_FACTOR = 1.15


INVARIANCE_SLACK = 0.2


CARRIED_OVER_GAP = 0.5


_CACHE: dict[str, Any] = {}


def level(region: Region) -> float:
    'The multiplier a range needs to be safe at any of the regions covered.'

    regions = max(1, int(region.spec["regions_on_the_note"]))
    chance = 1.0 / float(region.spec["one_time_in"])
    return NormalDist().inv_cdf(1.0 - chance / (2.0 * regions))


def table(
    region: Region, *, card: bool = True, roster: bool = False
) -> tuple[list[tuple[str, str]], np.ndarray, np.ndarray]:
    '(build, month) cells, what each carries and what each raised.'

    change = region.spec.get("card")
    factor = float(change["factor"]) if (card and change) else 1.0
    exposure: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], float] = {}
    if roster:
        for month in region.months:
            first = day_in(month, 1)
            for van in region.vans:
                if van.allocated_date > first or van.roster_until < first:
                    continue
                key = (van.build_month, month)
                exposure[key] = exposure.get(key, 0.0) + 1.0
    else:
        for (build, month, _depot), months in region.exposure.items():
            exposure[(build, month)] = exposure.get((build, month), 0.0) + months
    for (build, month, depot), count in region.counts.items():
        key = (build, month)
        scale = factor if region.card_factor(depot, month) > 1.0 else 1.0
        counts[key] = counts.get(key, 0.0) + count / scale
    keys = sorted(key for key, months in exposure.items() if months > 1e-9)
    return (
        keys,
        np.array([exposure[key] for key in keys], dtype=float),
        np.array([counts.get(key, 0.0) for key in keys], dtype=float),
    )


def standards(region: Region) -> dict[str, str]:
    'Build month -> the build standard it came off the line to.'

    order = {str(row["effective_build_month"]) for row in region.spec["change_orders"]}
    label = region.builds[0]
    out: dict[str, str] = {}
    for build in region.builds:
        if build in order:
            label = build
        out[build] = label
    return out


def design(
    region: Region, keys: Sequence[tuple[str, str]], group_builds: bool = True
) -> tuple[np.ndarray, list[str]]:
    'Intercept, months of age, a column a return month, a column a standard.'
    months = list(region.months)
    builds = list(region.builds)
    keyed = standards(region) if group_builds else {build: build for build in builds}
    names: list[str] = ["intercept", "age"]
    names.extend(f"month:{month}" for month in months[1:])
    seen: list[str] = []
    for build in builds:
        if keyed[build] not in seen:
            seen.append(keyed[build])
    build_columns = {label: len(names) + index for index, label in enumerate(seen[1:])}
    names.extend(f"build:{label}" for label in seen[1:])
    month_columns = {month: 2 + index for index, month in enumerate(months[1:])}
    matrix = np.zeros((len(keys), len(names)), dtype=float)
    for row, (build, month) in enumerate(keys):
        matrix[row, 0] = 1.0
        matrix[row, 1] = month_key(month) - month_key(build)
        if month in month_columns:
            matrix[row, month_columns[month]] = 1.0
        column = build_columns.get(keyed[build])
        if column is not None:
            matrix[row, column] = 1.0
    return matrix, names


def contrast(region: Region, names: Sequence[str], group_builds: bool = True) -> np.ndarray:
    'The build the review asks about, minus the build a year before it.'

    early, late = region.spec["compare"]
    built = region.vans_built()
    groups = region.build_groups()
    keyed = standards(region) if group_builds else {build: build for build in region.builds}
    vector = np.zeros(len(names), dtype=float)
    index = {name: position for position, name in enumerate(names)}
    for sign, group in ((1.0, late), (-1.0, early)):
        members = groups[group]
        total = sum(built[build] for build in members)
        for build in members:
            column = index.get(f"build:{keyed[build]}")
            if column is not None:
                vector[column] += sign * built[build] / total
    return vector


def _solve(matrix: np.ndarray, weights: np.ndarray, values: np.ndarray):
    scaled = matrix * weights[:, None]
    normal = matrix.T @ scaled
    return np.linalg.solve(normal, scaled.T @ values), normal


def read(region: Region, *, card: bool = True, roster: bool = False) -> float:
    keys, exposure, counts = table(region, card=card, roster=roster)
    matrix, names = design(region, keys)
    beta, _ = _solve(matrix, exposure, 100.0 * counts / exposure)
    return float(contrast(region, names) @ beta)


def truth(region: Region) -> float:
    "The build difference the region's own line put there, in points."

    built = region.vans_built()
    groups = region.build_groups()
    effect = region.spec["build_effect"]
    early, late = region.spec["compare"]

    def mean(name: str) -> float:
        members = groups[name]
        total = sum(built[build] for build in members)
        return sum(built[build] * effect[build] for build in members) / total

    return mean(late) - mean(early)


def vehicle_months(region: Region) -> float:
    return float(sum(region.exposure.values()))


def compared_vehicle_months(region: Region) -> float:
    'Return-window exposure in the two build groups named by the review.'

    compared = set(region.spec["compare"])
    return float(
        sum(
            exposure
            for (build, _month, _depot), exposure in region.exposure.items()
            if world.half_year(build) in compared
        )
    )


def roster_vehicle_months(region: Region) -> float:
    return float(sum(row["vans_on_the_books"] for row in region.roster()))


def floor_half_width(region: Region) -> float:
    'The half width the vehicle-months behind the answer support.'

    key = f"floor:{region.region}"
    if key not in _CACHE:
        keys, exposure, counts = table(region)
        matrix, names = design(region, keys)
        vector = contrast(region, names)
        values = 100.0 * counts / exposure
        beta, normal = _solve(matrix, exposure, values)
        spread = float(
            (exposure * (values - matrix @ beta) ** 2).sum() / (len(keys) - matrix.shape[1])
        )
        variance = spread * float(vector @ np.linalg.solve(normal, vector))
        _CACHE[key] = level(region) * float(np.sqrt(variance))
    return float(_CACHE[key])


def counted_half_width(region: Region) -> float:
    'The same range with the spread taken off the fault counts instead.'
    key = f"counted:{region.region}"
    if key not in _CACHE:
        keys, exposure, counts = table(region)
        matrix, names = design(region, keys)
        vector = contrast(region, names)
        _, normal = _solve(matrix, exposure, 100.0 * counts / exposure)
        spread = 100.0 * 100.0 * float(counts.sum()) / float(exposure.sum())
        _CACHE[key] = level(region) * float(
            np.sqrt(spread * float(vector @ np.linalg.solve(normal, vector)))
        )
    return float(_CACHE[key])


def residual_reading(region: Region, *, card: bool = True, roster: bool = False) -> float:
    'The build taken off what a fit on age and calendar month leaves over.'

    keys, exposure, counts = table(region, card=card, roster=roster)
    matrix, names = design(region, keys)
    values = 100.0 * counts / exposure
    keep = [index for index, name in enumerate(names) if not name.startswith("build:")]
    beta, _ = _solve(matrix[:, keep], exposure, values)
    left = values - matrix[:, keep] @ beta
    groups = region.build_groups()
    early, late = region.spec["compare"]

    def mean(name: str) -> float:
        members = set(groups[name])
        rows = [index for index, key in enumerate(keys) if key[0] in members]
        weight = exposure[rows]
        return float((left[rows] * weight).sum() / weight.sum())

    return mean(late) - mean(early)


def raw_age_reading(region: Region) -> float:
    "One build's plain rate against the other, over whatever ages each ran."

    keys, exposure, counts = table(region)
    groups = region.build_groups()
    early, late = region.spec["compare"]

    def rate(name: str) -> float:
        members = set(groups[name])
        rows = [index for index, key in enumerate(keys) if key[0] in members]
        return 100.0 * float(counts[rows].sum()) / float(exposure[rows].sum())

    return rate(late) - rate(early)


def misreadings(region: Region) -> dict[str, float]:
    key = f"miss:{region.region}"
    if key not in _CACHE:
        _CACHE[key] = {
            "residual": residual_reading(region),
            "pooled_cards": read(region, card=False),
            "roster": read(region, roster=True),
            "raw_age": raw_age_reading(region),
            "her_cut": residual_reading(region, card=False, roster=True),
        }
    return dict(_CACHE[key])


def cards_read(entries: Sequence[Mapping[str, Any]]) -> set[str]:
    'The walkaround cards a served day has already read.'

    return {
        str(entry["walkaround_ref"])
        for entry in entries
        if not entry.get("refusal") and entry.get("walkaround_ref")
    }


def cards_on_the_roster(region: Region) -> set[str]:
    return {region.card_on(depot, region.months[-1]) for depot in region.depots}


def depots_worked(entries: Sequence[Mapping[str, Any]]) -> set[str]:
    'The depots a served day has already walked. A refused day walked none.'

    return {str(entry["depot"]) for entry in entries if not entry.get("refusal")}


def card_read_at(
    region: Region, entries: Sequence[Mapping[str, Any]], card: str
) -> str:
    "The depot whose served day first read that card, in the desk's order."

    for entry in entries:
        if entry.get("refusal"):
            continue
        if str(entry.get("walkaround_ref") or "") == str(card):
            return str(entry["depot"])
    return "no depot"


def open_cards(region: Region, entries: Sequence[Mapping[str, Any]]) -> set[str]:
    return cards_on_the_roster(region) - cards_read(entries)


def free_days(region: Region, entries: Sequence[Mapping[str, Any]]) -> list[str]:
    'Weekdays the inspector could still work, earliest first.'

    start = date.fromisoformat(str(region.spec["as_of"]))
    out: list[str] = []
    for step in range(70):
        day = (start + timedelta(days=step)).isoformat()
        if date.fromisoformat(day).isoweekday() > 5:
            continue
        if desk.day_used(entries, day) or desk.week_full(region, entries, day):
            continue
        out.append(day)
    return out


AGE_BANDS = ((14, 40), (16, 36), (20, 32))


def a_useful_day(
    region: Region, entries: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    'One day the plan allows that reads a card no served day has read.'

    if desk.days_left(region, entries) <= 0:
        return None
    wanted = open_cards(region, entries)
    days = free_days(region, entries)
    if not wanted or not days:
        return None
    groups = sorted(region.build_groups())
    for depot in region.depots:
        if region.card_on(depot, region.months[-1]) not in wanted:
            continue
        for low, high in AGE_BANDS:
            for first in range(len(groups)):
                for second in range(first + 1, len(groups)):
                    builds = [groups[first], groups[second]]
                    least = int(region.spec["vans_in_service_minimum"])
                    if all(
                        len(region.group(depot, [name], (low, high), days[0])) >= least
                        for name in builds
                    ):
                        return {
                            "depot": depot,
                            "builds": builds,
                            "age_band": [low, high],
                            "vans": int(region.spec["vans_per_day"]),
                            "day": days[0],
                        }
    return None


def plan_is_allowed(
    region: Region, entries: Sequence[Mapping[str, Any]], choice: Any
) -> str | None:
    'The reason the desk or the plan would not take this answer, or None.'

    useful = a_useful_day(region, entries)
    if isinstance(choice, str):
        if choice.strip().lower() != "stop":
            return "day_is_not_a_day_or_a_stop"
        return None if useful is None else "stopped_with_days_left"
    if not isinstance(choice, Mapping):
        return "day_is_not_a_day_or_a_stop"
    depot, builds = choice.get("depot"), choice.get("builds")
    band, vans, day = choice.get("age_band"), choice.get("vans"), choice.get("day")
    if (
        not isinstance(depot, str)
        or not isinstance(builds, (list, tuple))
        or not builds
        or any(name not in region.build_groups() for name in builds)
        or not isinstance(band, (list, tuple))
        or len(band) != 2
        or not all(isinstance(value, int) and not isinstance(value, bool) for value in band)
        or band[0] < 0
        or band[0] > band[1]
        or not isinstance(vans, int)
        or isinstance(vans, bool)
        or vans <= 0
        or not isinstance(day, str)
    ):
        return "day_is_not_a_day_or_a_stop"
    try:
        weekday = date.fromisoformat(day).isoweekday()
    except ValueError:
        return "day_is_not_a_day_or_a_stop"
    if desk.days_left(region, entries) <= 0:
        return "day_over_the_days_granted"
    if weekday > 5:
        return "day_over_the_week_cap"
    refusal = desk.refusal_for(region, entries, depot, builds, band, vans, day)
    if refusal is not None:
        return refusal
    if region.card_on(depot, region.months[-1]) not in open_cards(region, entries):


        if str(depot) in depots_worked(entries):
            return "day_at_a_depot_already_worked"
        return "day_on_a_card_already_read"
    return None
