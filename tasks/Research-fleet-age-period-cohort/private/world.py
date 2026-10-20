"One region's van fleet, the walkaround cards its depots raise faults under, and the returns the maintenance system publishes."

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

RECEIPTS_FILE = "audit_receipts.json"

FAULT_CODES = ("BRK", "SUS", "TYR", "LGT", "BDY", "EXH", "STR", "ELE")


def month_key(label: str) -> int:
    year, month = str(label).split("-")
    return int(year) * 12 + (int(month) - 1)


def month_label(key: int) -> str:
    return f"{key // 12:04d}-{key % 12 + 1:02d}"


def month_span(first: str, count: int) -> tuple[str, ...]:
    start = month_key(first)
    return tuple(month_label(start + step) for step in range(count))


def month_length(label: str) -> int:
    year, month = str(label).split("-")
    return calendar.monthrange(int(year), int(month))[1]


def day_in(label: str, day: int) -> str:
    return f"{label}-{min(int(day), month_length(label)):02d}"


def add_months(day: str, months: int) -> str:
    parsed = date.fromisoformat(str(day))
    key = (parsed.year * 12 + parsed.month - 1) + int(months)
    label = month_label(key)
    return day_in(label, parsed.day)


def half_year(build_month: str) -> str:
    year, month = str(build_month).split("-")
    return f"{year}-H{1 if int(month) <= 6 else 2}"


@dataclass(frozen=True)
class Van:
    van_id: str
    build_month: str
    allocated_date: str
    in_service_date: str
    depot: str
    transfer_date: str | None
    transfer_depot: str | None
    off_fleet_date: str
    roster_until: str
    lease_ref: str


@dataclass(frozen=True)
class Region:
    "One region's register, its raised faults and the terms it runs under."

    spec: Mapping[str, Any]
    months: tuple[str, ...]
    builds: tuple[str, ...]
    vans: tuple[Van, ...]
    faults: tuple[Mapping[str, Any], ...]
    exposure: Mapping[tuple[str, str, str], float] = field(repr=False, default_factory=dict)
    counts: Mapping[tuple[str, str, str], int] = field(repr=False, default_factory=dict)

    @property
    def region(self) -> str:
        return str(self.spec["region"])

    @property
    def label(self) -> str:
        return str(self.spec["label"])

    @property
    def depots(self) -> tuple[str, ...]:
        return tuple(self.spec["depots"])

    def card_on(self, depot: str, month: str) -> str:
        change = self.spec.get("card")
        if change and str(depot) == str(change["depot"]) and month >= str(change["from_month"]):
            return str(change["to_card"])
        return str(self.spec["base_card"])

    def card_factor(self, depot: str, month: str) -> float:
        change = self.spec.get("card")
        if change and str(depot) == str(change["depot"]) and month >= str(change["from_month"]):
            return float(change["factor"])
        return 1.0

    def rate(self, build_month: str, month: str) -> float:
        'Faults per hundred vehicle-months for that build in that month.'

        age = month_key(month) - month_key(build_month)
        return (
            float(self.spec["base_rate"])
            + float(self.spec["age_slope"]) * age
            + self.spec["period_effect"][month]
            + self.spec["build_effect"][build_month]
        )

    def build_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for build in self.builds:
            groups.setdefault(half_year(build), []).append(build)
        return groups

    def vans_built(self) -> dict[str, int]:
        counted: dict[str, int] = {build: 0 for build in self.builds}
        for van in self.vans:
            counted[van.build_month] += 1
        return counted


    def roster(self) -> list[dict[str, Any]]:
        "Vans on the region's books on the first day of each return month."

        rows: list[dict[str, Any]] = []
        for month in self.months:
            first = day_in(month, 1)
            held: dict[tuple[str, str], int] = {}
            for van in self.vans:
                if van.allocated_date > first or van.roster_until < first:
                    continue
                depot = van.depot
                if van.transfer_date and van.transfer_date <= first:
                    depot = str(van.transfer_depot)
                key = (van.build_month, depot)
                held[key] = held.get(key, 0) + 1
            for (build, depot), count in sorted(held.items()):
                rows.append(
                    {
                        "month": month,
                        "build_month": build,
                        "depot": depot,
                        "vans_on_the_books": count,
                    }
                )
        return rows

    def register_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "van_id": van.van_id,
                "build_month": van.build_month,
                "allocated_date": van.allocated_date,
                "in_service_date": van.in_service_date,
                "depot": van.depot,
                "transfer_date": van.transfer_date or "",
                "transfer_depot": van.transfer_depot or "",
                "off_fleet_date": van.off_fleet_date,
                "lease_ref": van.lease_ref,
            }
            for van in self.vans
        ]

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "region": self.label,
            "window": {"first_return": self.months[0], "last_return": self.months[-1]},
            "as_of": str(spec["as_of"]),
            "depots": list(self.depots),
            "cards": list(spec["cards"]),
            "leases": list(spec["leases"]),
            "build_sheets": list(spec["build_sheets"]),
            "change_orders": list(spec["change_orders"]),
            "roster": self.roster(),
            "vans": self.register_rows(),
            "faults": [dict(row) for row in self.faults],
            "audit": {
                "days_granted": int(spec["days_granted"]),
                "days_per_week": int(spec["days_per_week"]),
                "vans_per_day": int(spec["vans_per_day"]),
                "vans_in_service_minimum": int(spec["vans_in_service_minimum"]),
                "roster_depots": list(self.depots),
                "build_groups": {
                    name: list(months) for name, months in sorted(self.build_groups().items())
                },
                "compare": list(spec["compare"]),
            },
            "review": {
                "range_bar_points": float(spec["range_bar_points"]),
                "regions_on_the_note": int(spec["regions_on_the_note"]),
                "one_time_in": int(spec["one_time_in"]),
                "tolerance_points": float(spec["tolerance_points"]),
            },
        }


    def age_of(self, van: Van, day: str) -> int:
        return month_key(day[:7]) - month_key(van.build_month)

    def depot_of(self, van: Van, day: str) -> str:
        if van.transfer_date and van.transfer_date <= day:
            return str(van.transfer_depot)
        return van.depot

    def in_service(self, van: Van, day: str) -> bool:
        return van.in_service_date <= day <= van.off_fleet_date

    def group(
        self, depot: str, builds: Sequence[str], age_band: Sequence[int], day: str
    ) -> list[Van]:
        'The vans a day at that depot could put a walkaround over.'

        low, high = int(age_band[0]), int(age_band[1])
        wanted = {str(name) for name in builds}
        return [
            van
            for van in self.vans
            if half_year(van.build_month) in wanted
            and self.depot_of(van, day) == str(depot)
            and self.in_service(van, day)
            and low <= self.age_of(van, day) <= high
        ]
