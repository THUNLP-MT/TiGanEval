'What the world says, computed from the fleet rather than from a board pack.'

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence

from . import desk, reading, world


TOLERANCE = 2.0


DECOY_SLACK = 0.8


PRINTED_SLACK = 0.5


RANGE_FLOOR = 0.90
RANGE_CEILING = 1.10

COVER = 1.96


COVERAGE_SHARE = 0.8


INVARIANCE = 0.7


def profile_mixture(fleet: world.Fleet, profile: str) -> dict[str, float]:
    "The condition mixture the fleet's units in this profile actually capture."

    counts = {condition: 0 for condition in reading.CONDITIONS}
    total = 0
    for capture in fleet.captures:
        if fleet.unit_of(capture).duty_profile != str(profile):
            continue
        counts[capture.condition] += 1
        total += 1
    if not total:
        return {condition: 0.0 for condition in reading.CONDITIONS}
    return {condition: counts[condition] / total for condition in reading.CONDITIONS}


_MIXTURES: dict[tuple[str, str], dict[str, float]] = {}


def mixture(fleet: world.Fleet, profile: str) -> dict[str, float]:
    key = (fleet.campaign, str(profile))
    if key not in _MIXTURES:
        _MIXTURES[key] = profile_mixture(fleet, profile)
    return _MIXTURES[key]


def profile_points(fleet: world.Fleet, bundle: str, profile: str) -> float:
    'Points of error the bundle costs on one duty profile, in service.'

    shares = mixture(fleet, profile)
    return 100.0 * sum(
        share * reading.condition_error(bundle, condition)
        for condition, share in shares.items()
    )


def worst_profile(fleet: world.Fleet, bundle: str) -> str:
    return max(world.PROFILES, key=lambda profile: profile_points(fleet, bundle, profile))


def bundle_points(fleet: world.Fleet, bundle: str) -> float:
    'What the bundle costs where it serves worst.'

    return max(profile_points(fleet, bundle, profile) for profile in world.PROFILES)


def ranked(fleet: world.Fleet) -> list[tuple[str, float]]:
    return sorted(
        ((bundle, bundle_points(fleet, bundle)) for bundle in reading.BUNDLES),
        key=lambda item: (item[1], item[0]),
    )


def ship(fleet: world.Fleet) -> str:
    return ranked(fleet)[0][0]


def fleet_points(fleet: world.Fleet) -> float:
    return ranked(fleet)[0][1]


def top_two_gap(fleet: world.Fleet) -> float:
    order = ranked(fleet)
    return order[1][1] - order[0][1]


def log_rows(fleet: world.Fleet) -> list[dict[str, Any]]:
    columns = fleet.log_columns()
    rows = []
    profile_of = {unit.unit_id: unit.duty_profile for unit in fleet.units}
    for index in fleet.log_order:
        row = dict(zip(columns, fleet.log_row(index)))
        row["duty_profile"] = profile_of[row["device_id"]]
        rows.append(row)
    return rows


_LOG_ROWS: dict[str, list[dict[str, Any]]] = {}


def export_rows(fleet: world.Fleet) -> list[dict[str, Any]]:
    if fleet.campaign not in _LOG_ROWS:
        _LOG_ROWS[fleet.campaign] = log_rows(fleet)
    return _LOG_ROWS[fleet.campaign]


def desk_field_rows(receipts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    'The rows the desk returned that came off a unit in a bay.'

    return [
        row
        for row in desk.rows_of(receipts)
        if str(row.get("duty_profile")) in world.PROFILES
    ]


def field_rows(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    'Every field row a build holds: the export, plus what the desk returned.'

    return list(export_rows(fleet)) + desk_field_rows(receipts)


_ROW_COUNTS: dict[tuple[Any, ...], dict[str, int]] = {}


def rows_in_profile(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], profile: str
) -> int:
    key = _key(fleet, receipts)
    if key not in _ROW_COUNTS:
        counts = {name: 0 for name in world.PROFILES}
        for row in field_rows(fleet, receipts):
            counts[row["duty_profile"]] += 1
        _ROW_COUNTS[key] = counts
    return _ROW_COUNTS[key].get(str(profile), 0)


def _wrong(fleet: world.Fleet, row: Mapping[str, Any], bundle: str, corrected: bool) -> bool:
    if not corrected or row["stage"] != "as_captured":
        return int(row[bundle]) != int(row["label"])
    values = reading.remove_gain(
        [float(row[name]) for name in reading.FEATURES], fleet.gain
    )
    return reading.decide(bundle, values) != int(row["label"])


_MEASURED: dict[tuple[Any, ...], dict[str, float]] = {}
_EXPORT_TALLY: dict[tuple[str, str, bool], dict[str, list[int]]] = {}


def _key(fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    return (
        fleet.campaign,
        len(receipts),
        sum(int(entry["rows_returned"]) for entry in receipts),
    )


def _tally(
    fleet: world.Fleet,
    rows: Sequence[Mapping[str, Any]],
    bundle: str,
    corrected: bool,
) -> dict[str, list[int]]:
    counted = {profile: [0, 0] for profile in world.PROFILES}
    for row in rows:
        cell = counted[row["duty_profile"]]
        cell[1] += 1
        if _wrong(fleet, row, bundle, corrected):
            cell[0] += 1
    return counted


def _export_tally(
    fleet: world.Fleet, bundle: str, corrected: bool
) -> dict[str, list[int]]:
    key = (fleet.campaign, bundle, corrected)
    if key not in _EXPORT_TALLY:
        _EXPORT_TALLY[key] = _tally(fleet, export_rows(fleet), bundle, corrected)
    return _EXPORT_TALLY[key]


def _measured(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    bundle: str,
    corrected: bool,
) -> dict[str, float]:
    'Points of error per duty profile, read off the rows a build holds.'

    key = _key(fleet, receipts) + (bundle, corrected)
    cached = _MEASURED.get(key)
    if cached is not None:
        return cached
    base = _export_tally(fleet, bundle, corrected)
    added = _tally(fleet, desk_field_rows(receipts), bundle, corrected)
    found = {
        profile: 100.0 * (base[profile][0] + added[profile][0])
        / (base[profile][1] + added[profile][1])
        for profile in world.PROFILES
        if base[profile][1] + added[profile][1]
    }
    _MEASURED[key] = found
    return found


def measured_points(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], bundle: str
) -> float:
    "The worst duty profile's points, off the rows a build holds, corrected."

    return max(_measured(fleet, receipts, bundle, True).values())


def measured_profile(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], bundle: str
) -> str:
    'The bay where this bundle reads worst in the rows a build holds.'

    measured = _measured(fleet, receipts, str(bundle), True)
    return max(measured, key=lambda name: measured[name])


def measured_ranking(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> list[tuple[str, float, str, int]]:
    "Every bundle's worst bay off the rows a build holds, best first."

    found = []
    for bundle in reading.BUNDLES:
        measured = _measured(fleet, receipts, bundle, True)
        profile = measured_profile(fleet, receipts, bundle)
        found.append(
            (
                bundle,
                measured[profile],
                profile,
                rows_in_profile(fleet, receipts, profile),
            )
        )
    found.sort(key=lambda item: (item[1], item[0]))
    return found


def pooled_over_the_log(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, float]:
    'One rate over every row the export carries, as the exporter wrote them.'

    best: tuple[str, float] | None = None
    for bundle in reading.BUNDLES:
        base = _export_tally(fleet, bundle, False)
        added = _tally(fleet, desk_field_rows(receipts), bundle, False)
        wrong = sum(base[p][0] + added[p][0] for p in world.PROFILES)
        held = sum(base[p][1] + added[p][1] for p in world.PROFILES)
        points = 100.0 * wrong / max(1, held)
        if best is None or points < best[1]:
            best = (bundle, points)
    return best or ("", 0.0)


def worst_as_captured(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, float]:
    'The worst duty profile, read on the rows as the exporter wrote them.'

    best: tuple[str, float] | None = None
    for bundle in reading.BUNDLES:
        points = max(_measured(fleet, receipts, bundle, False).values())
        if best is None or points < best[1]:
            best = (bundle, points)
    return best or ("", 0.0)


def profiles_averaged(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> tuple[str, float]:
    "The register's profiles combined by how many units each one holds."

    units = {profile: 0 for profile in world.PROFILES}
    for unit in fleet.units:
        units[unit.duty_profile] += 1
    total = sum(units.values()) or 1
    best: tuple[str, float] | None = None
    for bundle in reading.BUNDLES:
        measured = _measured(fleet, receipts, bundle, True)
        points = sum(units[profile] * measured.get(profile, 0.0) for profile in world.PROFILES)
        points /= total
        if best is None or points < best[1]:
            best = (bundle, points)
    return best or ("", 0.0)


def range_width(points: float, rows: int) -> float:
    'Width of the published 95% construction for one stated rate and row count.'

    if rows <= 0 or not 0.0 <= float(points) <= 100.0:
        return 100.0
    share = float(points) / 100.0
    return 2.0 * COVER * sqrt(share * (1.0 - share) / rows) * 100.0


def honest_width(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], bundle: str
) -> float:
    "How wide a range the rows behind that bundle's worst bay leave open."

    measured = _measured(fleet, receipts, str(bundle), True)
    if not measured:
        return 100.0
    profile = measured_profile(fleet, receipts, str(bundle))
    rows = rows_in_profile(fleet, receipts, profile)
    return range_width(measured[profile], rows)


from .plan import (
    SMALLEST_REQUEST,
    cell_has_units,
    credits_left,
    deciding_profiles,
    must_stop,
    narrowing,
    one_allowed_plan,
    owner_narrowing,
    plan_is_allowed,
    request_cost,
)
