'The five readings of one delivered fleet note, against the region itself.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import desk, oracle
from .world import Region, half_year, month_key


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def near(value: Any, wanted: float | None, slack: float) -> bool:
    read = number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def points(value: Any) -> str:
    read = number(value)
    return show(value) if read is None else format(read, "+.1f")


def pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        number(item) is not None for item in value
    ):
        return f"{points(value[0])} to {points(value[1])}"
    return show(value)


def show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "nothing at all" if not value else f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def where(region: Region) -> dict[str, str]:
    return {"region": region.label, "region_id": region.region}


def oldest_age_seen(region: Region) -> int:
    'The oldest the build under review was ever seen on the returns.'

    _early, late = region.spec["compare"]
    last = region.months[-1]
    oldest = 0
    for van in region.vans:
        if half_year(van.build_month) != late:
            continue
        end = min(str(van.off_fleet_date)[:7], last)
        oldest = max(oldest, month_key(end) - month_key(van.build_month))
    return oldest


def card_change_month(region: Region) -> str:
    change = region.spec.get("card")
    return str(change["from_month"]) if change else "no month"


def moved_depot(region: Region) -> str:
    'The depot that went onto the longer card, by name.'

    change = region.spec.get("card")
    return str(change["depot"]) if change else "no depot"


def unmoved_depots(region: Region) -> str:
    'The depots that stayed on the card they always raised faults under.'

    change = region.spec.get("card")
    moved = str(change["depot"]) if change else None
    rest = [str(depot) for depot in region.depots if str(depot) != moved]
    if not rest:
        return "no depot"
    if len(rest) == 1:
        return rest[0]
    return ", ".join(rest[:-1]) + " and " + rest[-1]


def difference_failures(
    region: Region, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    truth = oracle.truth(region)
    reported = report.get("build_difference_points")
    miss = oracle.misreadings(region)
    slack = oracle.CLASSIFY_SLACK
    fleet = oracle.vehicle_months(region)
    compared = oracle.compared_vehicle_months(region)
    roster = oracle.roster_vehicle_months(region)
    shared = {
        **where(region),
        "reported_points": points(reported),
        "reported_van_months": round(number(report.get("vehicle_months")) or 0.0),
        "roster_van_months": round(roster),
        "fleet_van_months": round(fleet),
        "compared_van_months": round(compared),
        "card_change_month": card_change_month(region),
        "moved_depot": moved_depot(region),
        "unmoved_depots": unmoved_depots(region),
        "oldest_age_seen": oldest_age_seen(region),
    }
    if near(reported, truth, oracle.TOLERANCE):
        counted = report.get("vehicle_months")
        if near(counted, fleet, 0.02 * fleet) or near(counted, compared, 0.02 * compared):
            return []
        return [fail("vehicle_months_disagree", **shared)]


    if near(reported, miss["her_cut"], slack):
        return [fail("build_difference_disagrees", **shared)]
    counted = report.get("vehicle_months")
    if near(counted, roster, 0.02 * roster) and not near(counted, fleet, 0.02 * fleet):
        return [fail("exposure_from_the_roster", **shared)]
    if near(reported, miss["residual"], slack):
        return [fail("build_difference_disagrees", **shared)]
    if near(reported, miss["pooled_cards"], slack):
        return [fail("pools_the_two_cards", **shared)]
    if near(reported, miss["raw_age"], slack):
        return [fail("compares_across_different_ages", **shared)]
    return [fail("build_difference_disagrees", **shared)]


def range_shape(region: Region, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    "Check the published range's shape and its relation to the published point."

    published = report.get("difference_range")
    floor = 2.0 * oracle.floor_half_width(region)
    shared = {
        **where(region),
        "reported_range": pair(published),
        "reported_points": points(report.get("build_difference_points")),
        "reported_van_months": round(number(report.get("vehicle_months")) or 0.0),
        "supported_width": format(floor, ".2f"),
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [fail("range_is_not_a_pair", **shared, reported=show(published))]
    reported = number(report.get("build_difference_points"))
    if reported is None or not float(published[0]) <= reported <= float(published[1]):
        return [fail("range_excludes_reported_point", **shared)]
    width = float(published[1]) - float(published[0])
    if width < floor * oracle.NARROW_FACTOR:
        return [fail("range_below_floor", **shared)]
    if width > floor * oracle.WIDE_FACTOR:
        return [fail("range_wider_than_the_months_support", **shared)]
    return []


def range_holds(region: Region, report: Mapping[str, Any]) -> bool:
    published = report.get("difference_range")
    if not isinstance(published, list) or len(published) != 2:
        return False
    if any(number(value) is None for value in published):
        return False
    return float(published[0]) <= oracle.truth(region) <= float(published[1])


def range_response_failures(
    reports: Sequence[tuple[Region, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    'Reject a nearly fixed span across regions with materially different support.'

    if len(reports) < 2:
        return []
    narrow = min(reports, key=lambda item: oracle.floor_half_width(item[0]))
    wide = max(reports, key=lambda item: oracle.floor_half_width(item[0]))

    def width(item: tuple[Region, Mapping[str, Any]]) -> float:
        published = item[1]["difference_range"]
        return float(published[1]) - float(published[0])

    narrow_width = width(narrow)
    wide_width = width(wide)
    if wide_width >= narrow_width * oracle.RANGE_RESPONSE_FACTOR:
        return []
    narrow_region, narrow_report = narrow
    wide_region, wide_report = wide
    return [
        fail(
            "range_ignores_region_information",
            **where(narrow_region),
            other_region=wide_region.label,
            reported_width=format(narrow_width, ".2f"),
            other_width=format(wide_width, ".2f"),
            reported_van_months=round(number(narrow_report.get("vehicle_months")) or 0.0),
            other_van_months=round(number(wide_report.get("vehicle_months")) or 0.0),
        )
    ]


def invariance_failures(
    here: Region,
    readings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'The answer on this region against the answer on its redraws.'

    base = number(readings.get(here.region))
    out: list[dict[str, Any]] = []
    if base is None:
        return out
    for other, label, kind in (
        ("linthorpe", "Linthorpe", "moves_with_the_card_month"),
        ("wardley", "Wardley", "moves_with_the_lease_returns"),
    ):
        value = number(readings.get(other))
        if value is None:
            continue
        moved = abs(value - base)
        if moved > oracle.INVARIANCE_SLACK:
            out.append(
                fail(
                    kind,
                    **where(here),
                    other_region=label,
                    reported_points=points(base),
                    other_points=points(value),
                    moved_by=format(moved, ".1f"),
                )
            )
    return out


def carried_over_failures(
    regions: Sequence[Region], readings: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'One number printed for two regions the returns do not agree about.'


    for first in regions:
        here = number(readings.get(first.region))
        if here is None:
            continue
        alike = [
            other
            for other in regions
            if number(readings.get(other.region)) is not None
            and abs(number(readings.get(other.region)) - here) <= 0.05
        ]
        span = [oracle.truth(other) for other in alike]
        if len(alike) >= 4 and max(span) - min(span) >= oracle.CARRIED_OVER_GAP:
            other = max(alike, key=lambda item: abs(oracle.truth(item) - oracle.truth(first)))
            return [
                fail(
                    "hardcoded_history",
                    **where(first),
                    other_region=other.label,
                    reported_points=points(here),
                    regions_alike=len(alike),
                )
            ]
    return []


def plan_failures(
    region: Region, entries: Sequence[Mapping[str, Any]], answer: Any
) -> list[dict[str, Any]]:
    choices = list(answer) if isinstance(answer, list) else [answer]
    left = desk.days_left(region, entries)
    shared = {
        **where(region),
        "days_left": left,
        "days_granted": int(region.spec["days_granted"]),
        "vans_cap": int(region.spec["vans_per_day"]),
        "least_in_service": int(region.spec["vans_in_service_minimum"]),
        "depots_on_the_plan": len(region.depots),
    }
    if not choices:
        return [fail("day_is_not_a_day_or_a_stop", **shared, reported=show(answer),
                     depot_asked="none", builds_asked="none", vans_asked=0,
                     day_asked="none", vans_in_service=0, card_asked="no card",
                     card_read_at="no depot")]
    for choice in choices:
        problem = oracle.plan_is_allowed(region, entries, choice)
        if problem is None:
            continue
        asked = choice if isinstance(choice, Mapping) else {}
        builds = asked.get("builds")
        builds = builds if isinstance(builds, (list, tuple)) else []
        depot = str(asked.get("depot") or "none")
        band = asked.get("age_band")
        band = band if isinstance(band, (list, tuple)) and len(band) == 2 else (0, 120)
        card = region.card_on(depot, region.months[-1]) if depot in region.depots else ""
        held = 0
        if depot in region.depots and builds:
            held = min(
                len(region.group(depot, [name], band, str(asked.get("day") or region.spec["as_of"])))
                for name in builds
                if isinstance(name, str)
            ) if all(isinstance(name, str) for name in builds) else 0
        return [
            fail(
                problem,
                **shared,
                reported=show(choice if not isinstance(choice, Mapping) else
                              f"{asked.get('vans')} vans at {depot} on {', '.join(map(str, builds))}"),
                depot_asked=depot,
                builds_asked=", ".join(map(str, builds)) or "none",
                vans_asked=asked.get("vans") if isinstance(asked.get("vans"), int) else 0,
                day_asked=str(asked.get("day") or "none"),
                vans_in_service=held,
                card_asked=str(card or "no card"),
                card_read_at=(
                    oracle.card_read_at(region, entries, card) if card else "no depot"
                ),
            )
        ]
    return []


def receipt_failures(
    region: Region,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    unreadable: str | None,
) -> list[dict[str, Any]]:
    shared = {**where(region), "days_on_file": len(entries)}
    if unreadable:
        return [fail("receipts_unreadable", **shared, reason=str(unreadable))]
    rows = report.get("days")
    if not isinstance(rows, list):
        return [fail("days_are_not_a_list", **shared, reported=show(rows))]
    charged = {str(entry["receipt_id"]): entry for entry in entries}
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [fail("days_are_not_a_list", **shared, reported=show(row))]
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [fail("day_counted_twice", **shared, receipt_id=key,
                         times_reported=seen[key])]
        entry = charged.get(key)
        if entry is None:
            return [fail("day_not_on_the_receipts", **shared, receipt_id=key)]
        returned = number(row.get("vans_returned"))
        if returned is None or int(returned) != int(entry["vans_returned"]):
            return [fail("day_not_on_the_receipts", **shared, receipt_id=key,
                         reported_vans=show(row.get("vans_returned")),
                         desk_vans=int(entry["vans_returned"]))]
        faults = number(row.get("faults_returned"))
        if (
            str(row.get("depot")) != str(entry["depot"])
            or str(row.get("day")) != str(entry["day"])
            or faults is None
            or int(faults) != int(entry["faults_returned"])
        ):
            return [
                fail(
                    "day_not_on_the_receipts",
                    **shared,
                    receipt_id=key,
                    reported_depot=show(row.get("depot")),
                    desk_depot=str(entry["depot"]),
                    reported_day=show(row.get("day")),
                    desk_day=str(entry["day"]),
                    reported_faults=show(row.get("faults_returned")),
                    desk_faults=int(entry["faults_returned"]),
                )
            ]
    for key, entry in charged.items():
        if key in seen:
            continue
        kind = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        return [fail(kind, **shared, receipt_id=key, day=str(entry["day"]),
                     depot=str(entry["depot"]))]
    charged_days = desk.days_charged(entries)
    reported_days = number(report.get("days_charged"))
    if reported_days is None or int(reported_days) != charged_days:
        return [fail("days_charged_disagree", **shared,
                     reported_days=show(report.get("days_charged")),
                     desk_days=charged_days)]
    return []
