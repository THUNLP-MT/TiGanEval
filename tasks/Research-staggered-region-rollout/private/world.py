"The world behind Halcombe's batching rollout. Nothing here reaches the Agent."

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
from typing import Any, Mapping, Sequence

BANDS = ("core", "ring", "outer")
ARMS = ("batched", "held_back")
RECEIPTS_FILE = "wave_receipts.json"


WEEKDAY_FACTOR = (1.06, 1.02, 1.00, 1.01, 1.09, 1.12, 0.94)


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shift(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=amount)).isoformat()


def between(first: str, last: str) -> int:
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def monday_of(day: str) -> str:
    stamp = date.fromisoformat(str(day))
    return (stamp - timedelta(days=stamp.weekday())).isoformat()


class _Carry:
    'Whole counts whose running total tracks the exact rate that made them.'

    def __init__(self) -> None:
        self._left: dict[Any, float] = {}

    def take(self, key: Any, exact: float) -> int:
        value = exact + self._left.get(key, 0.0)
        whole = int(math.floor(value))
        self._left[key] = value - whole
        return max(0, whole)


@dataclass(frozen=True)
class Region:
    name: str
    band: str
    readiness: float
    level_points: float
    effect_points: float
    orders_per_day: int
    sample_rate: float
    live_from: str | None
    stack_migrated_on: str
    disabled_on: str | None

    def live_on(self, day: str) -> bool:
        return self.live_from is not None and str(day) >= self.live_from

    def batching_on(self, day: str) -> bool:
        if not self.live_on(day):
            return False
        return self.disabled_on is None or str(day) < self.disabled_on


@dataclass(frozen=True)
class Network:
    'One rollout network: its register, its daily export and its samples.'

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    regions: tuple[Region, ...]

    printed: Mapping[tuple[str, str], tuple[int, int]]

    sampled: Mapping[tuple[str, str], tuple[int, int, int]]

    booked: Mapping[tuple[str, str], tuple[dict[str, Any], ...]] = ()

    @property
    def network(self) -> str:
        return str(self.spec["network"])

    @property
    def as_of(self) -> str:
        return self.days[-1]

    def region(self, name: str) -> Region:
        for item in self.regions:
            if item.name == name:
                return item
        raise KeyError(name)

    def book_regions(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self.spec["book_regions"])

    def book_orders(self) -> dict[str, int]:
        'What the book counted for each of its metros on the day it was cut.'

        counted_on = str(self.spec["book_counted_on"])
        return {
            name: int(self.printed[(name, counted_on)][0]) for name in self.book_regions()
        }

    def window_closes_on(self) -> str:
        return str(self.spec["window_closes_on"])

    def measured_regions(self) -> tuple[str, ...]:
        "The book's metros that went live inside the window the board set."

        closes = self.window_closes_on()
        return tuple(
            name
            for name in self.book_regions()
            if self.region(name).live_from is not None
            and str(self.region(name).live_from) <= closes
        )

    def exposure_days(self, name: str) -> tuple[str, ...]:
        "A metro's first days on batching, up to the window the board reads."

        region = self.region(name)
        if region.live_from is None:
            return ()
        length = int(self.spec["exposure_days"])
        wanted = [shift(region.live_from, step) for step in range(length)]
        return tuple(
            day
            for day in wanted
            if day <= self.as_of and (region.disabled_on is None or day < region.disabled_on)
        )

    def baseline_days(self, name: str) -> tuple[str, ...]:
        'The four weeks before that metro went live, whoever is reading them.'

        region = self.region(name)
        if region.live_from is None:
            return ()
        length = int(self.spec["baseline_days"])
        return tuple(
            day
            for day in (shift(region.live_from, -step) for step in range(1, length + 1))
            if day >= self.days[0]
        )

    def controls_for(self, name: str, day: str) -> tuple[str, ...]:
        'Same band, not live on that day, and not a metro sent back to the old flow.'

        region = self.region(name)
        out = []
        for other in self.regions:
            if other.name == name or other.band != region.band:
                continue
            if other.live_on(day):
                continue
            if other.disabled_on is not None and str(day) >= other.disabled_on:
                continue
            out.append(other.name)
        return tuple(sorted(out))


    def register_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "region": item.name,
                "band": item.band,
                "readiness_score": round(item.readiness, 3),
                "live_from": item.live_from or "",
                "stack_migrated_on": item.stack_migrated_on,
                "orders_per_day": item.orders_per_day,
            }
            for item in sorted(self.regions, key=lambda item: item.name)
        ]

    def daily_rows(self) -> list[dict[str, Any]]:
        rows = []
        for name, day in sorted(self.printed):
            orders, ontime = self.printed[(name, day)]
            rows.append(
                {
                    "region": name,
                    "date": day,
                    "orders": int(orders),
                    "ontime_orders": int(ontime),
                    "ontime_rate": round(ontime / orders, 5) if orders else 0.0,
                }
            )
        return rows

    def sample_rows(self) -> list[dict[str, Any]]:
        rows = []
        for name, day in sorted(self.sampled):
            total, placed, assigned = self.sampled[(name, day)]
            rows.append(
                {
                    "region": name,
                    "date": day,
                    "sampled_orders": int(total),
                    "ontime_by_placed_at": int(placed),
                    "ontime_by_assigned_at": int(assigned),
                }
            )
        return rows

    def incident_rows(self) -> list[dict[str, Any]]:
        'The dispatch on-call log for the window, in the order it was written.'

        rows = [
            {
                "region": str(region),
                "date": shift(str(self.spec["first_day"]), int(offset)),
                "time": str(clock),
                "event": str(event),
                "note": str(note),
            }
            for region, offset, clock, event, note in self.spec["incidents"]
        ]
        rolled = dict(self.spec.get("rollback", {}))
        if rolled:
            region = self.region(str(rolled["region"]))
            rows.append(
                {
                    "region": region.name,
                    "date": str(region.disabled_on),
                    "time": str(rolled.get("time", "09:40")),
                    "event": "disabled",
                    "note": str(rolled.get("note", "batching disabled")),
                }
            )
        return sorted(rows, key=lambda row: (row["date"], row["time"], row["region"]))

    def book_document(self) -> dict[str, Any]:
        return {
            "book": f"{self.network} region book",
            "counted_on": str(self.spec["book_counted_on"]),
            "window_closes_on": self.window_closes_on(),
            "orders_on_the_count_day": self.book_orders(),
        }

    def booked_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(self.booked):
            rows.extend(dict(row) for row in self.booked[key])
        return rows

    def context(self) -> dict[str, Any]:
        return {
            "network": self.network,
            "window": {"first_day": self.days[0], "last_day": self.as_of},
            "as_of": self.as_of,
            "networks_reviewed": int(self.spec["networks_reviewed"]),
            "exposure_days": int(self.spec["exposure_days"]),
            "baseline_days": int(self.spec["baseline_days"]),
            "board_bar_points": float(self.spec["board_bar_points"]),
            "capacity": {
                "region_weeks_granted": int(self.spec["region_weeks_granted"]),
                "region_weeks_per_week": int(self.spec["region_weeks_per_week"]),
                "holdback_share_band": list(self.spec["holdback_share_band"]),
                "minimum_orders_per_day": int(self.spec["minimum_orders_per_day"]),
                "bookable_weeks": list(self.spec["bookable_weeks"]),
            },
            "book": self.book_document(),
            "dispatch_incidents": self.incident_rows(),
            "register": self.register_rows(),
            "daily": self.daily_rows(),
            "order_sample": self.sample_rows(),
            "booked_weeks": self.booked_rows(),
        }


def _regions_of(spec: Mapping[str, Any]) -> tuple[Region, ...]:
    'Turn the parameter table into metros, with live order set by readiness.'

    first_day = str(spec["first_day"])
    entries = sorted(spec["regions"], key=lambda item: -float(item["readiness"]))
    offsets = list(spec["live_offsets"])
    wave = dict(spec.get("january_wave", {}))
    leads = list(spec["migration_lead_days"])
    rolled = dict(spec.get("rollback", {}))
    out: list[Region] = []
    for rank, item in enumerate(entries):
        live_from = (
            shift(first_day, int(offsets[rank])) if rank < len(offsets) else None
        )
        if item["name"] in wave:
            migrated = shift(first_day, int(wave[item["name"]]))
        elif live_from is None:
            migrated = ""
        else:
            migrated = shift(live_from, -int(leads[rank % len(leads)]))
        disabled = (
            shift(first_day, int(rolled["on_day"]))
            if rolled and rolled.get("region") == item["name"]
            else None
        )
        out.append(
            Region(
                name=str(item["name"]),
                band=str(item["band"]),
                readiness=float(item["readiness"]),
                level_points=float(item["level_points"]),
                effect_points=float(item["effect_points"]),
                orders_per_day=int(item["orders_per_day"]),
                sample_rate=float(item["sample_rate"]),
                live_from=live_from,
                stack_migrated_on=migrated,
                disabled_on=disabled,
            )
        )
    return tuple(out)


def effect_on(spec: Mapping[str, Any], region: Region, day: str) -> float:
    'What batching is worth to that metro on that day, in on-time points.'

    if not region.batching_on(day):
        return 0.0
    since = between(str(region.live_from), str(day))
    if since < int(spec["settle_days"]):
        return region.effect_points - float(spec["settle_penalty_points"])
    return region.effect_points


def true_points(spec: Mapping[str, Any], region: Region, day: str, index: int) -> float:
    "The share of that metro-day's orders delivered on time, in points."

    drift = float(spec["band_drift_points"][region.band]) * index
    value = region.level_points + drift + effect_on(spec, region, day)
    return min(float(spec["ceiling_points"]), value)


def orders_on(spec: Mapping[str, Any], region: Region, index: int) -> int:
    growth = 1.0 + float(spec["order_growth"]) * index
    return int(round(region.orders_per_day * WEEKDAY_FACTOR[index % 7] * growth))


def build(spec: Mapping[str, Any], booked: Mapping[Any, Any] | None = None) -> Network:
    "Run one network's register, daily export and order sample end to end."

    days = tuple(days_from(spec["first_day"], int(spec["days"])))
    regions = _regions_of(spec)
    lift = float(spec["clock_lift_points"])
    printed: dict[tuple[str, str], tuple[int, int]] = {}
    sampled: dict[tuple[str, str], tuple[int, int, int]] = {}
    carry = _Carry()
    for region in regions:
        for index, day in enumerate(days):
            orders = orders_on(spec, region, index)
            share = true_points(spec, region, day, index)
            on_assigned = min(float(spec["ceiling_points"]), share + lift)
            migrated = bool(region.stack_migrated_on) and day >= region.stack_migrated_on
            shown = on_assigned if migrated else share
            printed[(region.name, day)] = (
                orders,
                carry.take((region.name, "printed"), orders * shown / 100.0),
            )
            total = carry.take((region.name, "sampled"), orders * region.sample_rate)
            sampled[(region.name, day)] = (
                total,
                carry.take((region.name, "placed"), total * share / 100.0),
                carry.take((region.name, "assigned"), total * on_assigned / 100.0),
            )
    return Network(
        spec=spec,
        days=days,
        regions=regions,
        printed=printed,
        sampled=sampled,
        booked=dict(booked or {}),
    )


def booked_week_rows(
    network: Network, region_name: str, week: str, holdback_share: int
) -> list[dict[str, Any]]:
    "One booked week's daily rows, both arms, as the wave service returns them."

    spec = network.spec
    region = network.region(region_name)
    share = int(holdback_share) / 100.0
    lift = float(spec["clock_lift_points"])
    rows: list[dict[str, Any]] = []
    carry = _Carry()
    for step in range(7):
        day = shift(week, step)
        index = between(str(spec["first_day"]), day)
        orders = orders_on(spec, region, index)
        base = min(
            float(spec["ceiling_points"]),
            region.level_points + float(spec["band_drift_points"][region.band]) * index,
        )
        settled = region.effect_points - float(spec["settle_penalty_points"])
        for arm, count in (
            ("held_back", int(round(orders * share))),
            ("batched", orders - int(round(orders * share))),
        ):
            share_points = base + (settled if arm == "batched" else 0.0)
            share_points = min(float(spec["ceiling_points"]), share_points)
            total = carry.take((arm, "sampled"), count * region.sample_rate)
            rows.append(
                {
                    "region": region_name,
                    "week": week,
                    "date": day,
                    "arm": arm,
                    "orders": count,
                    "sampled_orders": total,
                    "ontime_by_placed_at": carry.take(
                        (arm, "placed"), total * share_points / 100.0
                    ),
                    "ontime_by_assigned_at": carry.take(
                        (arm, "assigned"),
                        total * min(float(spec["ceiling_points"]), share_points + lift) / 100.0,
                    ),
                }
            )
    return rows


def with_bookings(
    spec: Mapping[str, Any], bookings: Sequence[Mapping[str, Any]]
) -> Network:
    'The same network with a list of served holdback weeks attached.'

    network = build(spec)
    booked: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {}
    for item in bookings:
        if item.get("refusal"):
            continue
        key = (str(item["region"]), str(item["week"]))
        booked[key] = tuple(
            booked_week_rows(
                network, str(item["region"]), str(item["week"]), int(item["holdback_share"])
            )
        )
    return build(spec, booked)
