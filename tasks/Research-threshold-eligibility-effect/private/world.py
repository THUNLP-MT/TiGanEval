'The world behind the standing-score offer campaign, and the review desk.'

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


TIERS = (0, 1, 2, 3, 4)


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shift(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=int(amount))).isoformat()


def between(first: str, last: str) -> int:
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def standing_rate(spec: Mapping[str, Any], score: float) -> float:
    'The sixty-day chance of an order for an account standing at `score`.'

    low = float(spec["rate_floor"])
    span = float(spec["rate_span"])
    knee = float(spec["rate_knee"])
    width = float(spec["rate_width"])
    middle = float(spec["rate_middle"])
    shape = (
        _normal_cdf((score - middle - knee) / width)
        + _normal_cdf((score - middle + knee) / width)
    ) / 2.0
    return low + span * shape


def offer_effect(spec: Mapping[str, Any], over: float) -> float:
    'What the offer does to an account sitting `over` points above the line.'

    size = float(spec["effect"])
    reach = spec.get("effect_reach")
    if reach is None:
        return size
    return size * math.exp(-max(0.0, float(over)) / float(reach))


@dataclass(frozen=True)
class Market:
    "One market's book, its refresh batches and what the export carries."

    spec: Mapping[str, Any]
    rows: tuple[Mapping[str, Any], ...]
    refreshes: tuple[Mapping[str, Any], ...]

    @property
    def market(self) -> str:
        return str(self.spec["market"])

    @property
    def cut(self) -> float:
        return float(self.spec["cut"])

    @property
    def days(self) -> tuple[str, ...]:
        return tuple(days_from(self.spec["first_day"], int(self.spec["window_days"])))

    @property
    def as_of(self) -> str:
        return self.days[-1]

    def register_rows(self) -> list[dict[str, Any]]:
        'One row an account, as the weekly job writes the offer register.'

        return [
            {
                "account_id": row["account_id"],
                "run_week": int(row["run_week"]),
                "run_status": str(row["run_status"]),
                "standing_score": round(float(row["register_score"]), 2),
                "credits_filed": round(float(row["credit"]), 2),
                "offer_flag": int(row["offer_flag"]),
                "offer_date": str(row["offer_date"]),
                "first_order_date": str(row["first_order_date"]),
                "last_observed_date": str(row["last_observed_date"]),
            }
            for row in self.rows
        ]

    def recompute_rows(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.refreshes]

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "market": self.market,
            "window": {"first_day": self.days[0], "last_day": self.as_of},
            "as_of": self.as_of,
            "cut": self.cut,
            "credit_ceiling": float(spec["credit_ceiling"]),
            "order_window_days": int(spec["order_window_days"]),
            "export_stop_day": self.days[int(spec["export_stop_day"]) - 1],
            "publication_lag_days": int(spec["publication_lag_days"]),
            "review_grant": {
                "files_granted": int(spec["files_granted"]),
                "files_per_booking": int(spec["files_per_booking"]),
                "smallest_lot": int(spec["smallest_lot"]),
                "above_share_range": [
                    float(spec["above_share_low"]),
                    float(spec["above_share_high"]),
                ],
            },
            "council": {
                "markets_on_the_slide": int(spec["markets_on_the_slide"]),
                "odds": "one time in twenty",
                "range_bar_points": float(spec["range_bar_points"]),
            },
            "register": self.register_rows(),
            "recompute": self.recompute_rows(),
        }

    def files_spent(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return int(sum(int(item["files_charged"]) for item in receipts))

    def files_left(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return int(self.spec["files_granted"]) - self.files_spent(receipts)


def _spread(total: int, weights: Sequence[float]) -> list[int]:
    'Split one whole number across a vector, largest remainder first.'

    if total <= 0 or not weights:
        return [0] * len(weights)
    scale = sum(weights)
    raw = [total * float(weight) / scale for weight in weights]
    counts = [int(math.floor(value)) for value in raw]
    left = total - sum(counts)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - counts[i]), i))
    for index in order[:left]:
        counts[index] += 1
    return counts


def score_grid(spec: Mapping[str, Any]) -> list[float]:
    low = float(spec["score_low"])
    high = float(spec["score_high"])
    steps = int(round((high - low) * 4)) + 1
    return [round(low + index * 0.25, 2) for index in range(steps)]


def score_weights(spec: Mapping[str, Any]) -> list[float]:
    "How the book's standing scores sit before any credit is filed."

    core = float(spec["core_share"])
    core_sd = float(spec["core_sd"])
    spread_sd = float(spec["spread_sd"])


    middle = float(spec["rate_middle"]) - float(spec["week_lift"]) * (
        int(spec["run_weeks"]) - 1
    ) / 2.0
    weights = []
    for value in score_grid(spec):
        near = math.exp(-0.5 * ((value - middle) / core_sd) ** 2) / core_sd
        wide = math.exp(-0.5 * ((value - middle) / spread_sd) ** 2) / spread_sd
        weights.append(core * near + (1.0 - core) * wide)
    return weights


def _stride(places: Sequence[int], wanted: int, offset: int = 0) -> list[int]:
    '`wanted` of these positions, spread evenly and deterministically.'

    count = len(places)
    if wanted <= 0 or count <= 0:
        return []
    wanted = min(wanted, count)
    return [places[int((index + 0.5 + offset) * count / wanted) % count] for index in range(wanted)]


def _account_id(spec: Mapping[str, Any], index: int) -> str:
    return f"{spec['account_prefix']}-{index + 1:06d}"


def build(spec: Mapping[str, Any]) -> Market:
    'Run the book, the credits, the refresh batches and the export.'

    seeds = _seed_book(spec)
    _mark_carried(spec, seeds)
    _mark_credits(spec, seeds)
    refreshes = _mark_refreshes(spec, seeds)
    rows = _run_export(spec, seeds)
    return Market(spec=spec, rows=tuple(rows), refreshes=tuple(refreshes))


def _seed_book(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    grid = score_grid(spec)
    weeks = int(spec["run_weeks"])
    tier_mix = [float(value) for value in spec["tier_mix"]]
    per_score = _spread(int(spec["accounts"]), score_weights(spec))
    seeds: list[dict[str, Any]] = []
    for value, count in zip(grid, per_score):
        for week, week_count in enumerate(_spread(count, [1.0] * weeks), start=1):
            for tier, tier_count in enumerate(_spread(week_count, tier_mix)):
                for _ in range(tier_count):
                    seeds.append(
                        {
                            "base_score": value,
                            "run_week": week,
                            "tier": tier,
                            "carried": False,
                            "credit": 0.0,
                            "refresh_delta": 0.0,
                            "refresh_day": None,
                            "refresh_batch": None,
                        }
                    )
    seeds.sort(key=lambda row: (row["run_week"], row["base_score"], row["tier"]))
    return seeds


def _places(seeds: Sequence[Mapping[str, Any]], tier: int) -> list[int]:
    return [index for index, row in enumerate(seeds) if row["tier"] == tier]


def _mark_carried(spec: Mapping[str, Any], seeds: list[dict[str, Any]]) -> None:
    "The accounts the run passed over: below the week's activity floor."

    share = float(spec["carried_share"])
    for tier in TIERS:
        places = _places(seeds, tier)
        weight = float(spec["carried_by_tier"][tier])
        for index in _stride(places, int(round(len(places) * share * weight))):
            seeds[index]["carried"] = True


def _mark_credits(spec: Mapping[str, Any], seeds: list[dict[str, Any]]) -> None:
    "Credits filed before the run's cut-off, on accounts just under the line."

    ceiling = float(spec["credit_ceiling"])
    share = float(spec["credit_share"])
    cut = float(spec["cut"])
    if ceiling <= 0 or share <= 0:
        return
    lift = float(spec["week_lift"])

    def settled(row: Mapping[str, Any]) -> float:
        return row["base_score"] + lift * (int(row["run_week"]) - 1)

    eligible = [
        index
        for index, row in enumerate(seeds)
        if row["tier"] >= int(spec["credit_tier_floor"])
        and cut - ceiling <= settled(row) < cut
        and not row["carried"]
    ]
    over = list(spec["credit_over"])
    for step, index in enumerate(_stride(eligible, int(round(len(seeds) * share)))):
        row = seeds[index]
        row["credit"] = round(
            min(ceiling, cut - settled(row) + over[step % len(over)]), 2
        )


def _mark_refreshes(
    spec: Mapping[str, Any], seeds: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    'The recompute batches: part of the book, rescored part-way through.'

    batches = list(spec["refresh_batches"])
    share = float(spec["refresh_share"])
    drift = [float(value) for value in spec["refresh_drift"]]
    days = days_from(spec["first_day"], int(spec["window_days"]))


    for number, (name, day) in enumerate(batches):
        for tier in TIERS:
            places = [
                index for index in _places(seeds, tier) if seeds[index]["refresh_batch"] is None
            ]
            wanted = int(round(len(places) * share / max(1, len(batches) - number)))
            for index in _stride(places, wanted, offset=number * 2):
                seeds[index]["refresh_batch"] = str(name)
                seeds[index]["refresh_day"] = int(day)
                seeds[index]["refresh_delta"] = drift[tier]
    lift = float(spec["week_lift"])
    return [
        {
            "account_id": _account_id(spec, index),
            "refresh_batch": row["refresh_batch"],
            "refresh_date": days[int(row["refresh_day"]) - 1],
            "score_before": round(
                row["base_score"] + lift * (int(row["run_week"]) - 1) + row["credit"], 2
            ),
        }
        for index, row in enumerate(seeds)
        if row["refresh_batch"] is not None
    ]


def _run_export(spec: Mapping[str, Any], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    'Offer the book, watch it for sixty days and stop the export at its day.'

    days = days_from(spec["first_day"], int(spec["window_days"]))
    window = int(spec["order_window_days"])
    last_export = int(spec["export_stop_day"]) - int(spec["publication_lag_days"])
    cut = float(spec["cut"])
    bumps = [float(value) for value in spec["tier_bump"]]
    lift = float(spec["week_lift"])
    gain = float(spec["refresh_gain"])
    favour = float(spec["credit_favour"])
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(seeds):
        week = int(row["run_week"])
        offer_day = 1 + (week - 1) * 7
        before_run = row["refresh_day"] is not None and int(row["refresh_day"]) <= offer_day
        settled = row["base_score"] + lift * (week - 1)
        register_score = settled + row["credit"] + row["refresh_delta"]
        run_score = settled + row["credit"] + (row["refresh_delta"] if before_run else 0.0)
        offered = (not row["carried"]) and run_score >= cut
        lifted = bool(row["credit"] > 0 and run_score >= cut > run_score - row["credit"])
        chance = standing_rate(spec, settled + row["refresh_delta"]) + bumps[row["tier"]]
        chance += gain * float(row["refresh_delta"])
        if row["credit"] > 0:
            chance += favour
        if row["carried"]:
            chance -= float(spec["carried_penalty"])
        if offered:
            chance += offer_effect(spec, run_score - cut) / 100.0
        chance = min(0.92, max(0.05, chance))
        rows.append(
            {
                "account_id": _account_id(spec, index),
                "run_week": week,
                "run_status": "carried" if row["carried"] else "scored",
                "register_score": register_score,
                "run_score": run_score,
                "credit": row["credit"],
                "credit_lifted": lifted,
                "tier": row["tier"],
                "offer_flag": 1 if offered else 0,
                "offer_day": offer_day,
                "offer_date": "" if row["carried"] else days[offer_day - 1],
                "true_chance": chance,
                "hazard": 1.0 - (1.0 - chance) ** (1.0 / window),
                "watched_days": max(0, min(window, last_export - offer_day)),
            }
        )
    _draw_orders(spec, rows)
    for row in rows:
        offset = row["order_offset"]
        watched = int(row["watched_days"])
        seen = offset is not None and offset <= watched
        row["first_order_date"] = days[row["offer_day"] + offset - 1] if seen else ""
        row["last_observed_date"] = days[row["offer_day"] + watched - 1]
    return rows


def _draw_orders(spec: Mapping[str, Any], rows: list[dict[str, Any]]) -> None:
    'Who ordered inside sixty days, and on which day, without a random draw.'

    cut = float(spec["cut"])
    window = int(spec["order_window_days"])
    groups: dict[tuple[Any, ...], list[int]] = {}
    for index, row in enumerate(rows):
        row["group_key"] = (
            row["run_status"],
            row["offer_flag"],
            bool(row["credit_lifted"]),
            abs(row["run_score"] - cut) <= float(spec["band_points"]),
        )
        row["cell_key"] = (
            row["group_key"],
            max(-20, min(20, int(math.floor(row["run_score"] - cut)))),
            row["run_week"],
        )
        row["order_offset"] = None
        groups.setdefault(row["group_key"], []).append(index)

    for key, places in groups.items():
        cells: dict[Any, list[int]] = {}
        for index in places:
            cells.setdefault(rows[index]["cell_key"], []).append(index)
        order = sorted(cells, key=lambda item: (item[1], item[2]))
        wanted = [sum(rows[index]["true_chance"] for index in cells[cell]) for cell in order]
        total = int(round(sum(wanted)))
        for cell, count in zip(order, _spread(total, wanted)):
            members = cells[cell]
            picked = sorted(_stride(members, count))
            for rank, index in enumerate(picked):
                row = rows[index]
                share = (rank + 0.5) / max(1, len(picked))
                hazard = float(row["hazard"])
                reach = 1.0 - (1.0 - hazard) ** window
                offset = math.ceil(
                    math.log(max(1e-12, 1.0 - share * reach)) / math.log(1.0 - hazard)
                )
                row["order_offset"] = int(min(window, max(1, offset)))
