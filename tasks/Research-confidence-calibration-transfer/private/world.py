'The listing queues behind the auto-clear cut, and the adjudication desk.'

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import threading
from typing import Any, Mapping


CHANNELS = ("web", "mobile", "partner_feed", "reseller_import")
RECEIPTS_FILE = "audit_receipts.json"
LOG_FILE = "intake_log.csv"
LOG_COLUMNS = (
    "listing_id",
    "channel",
    "intake_date",
    "intake_period",
    "stated_confidence",
    "auto_cleared",
    "review_outcome",
    "outcome_closed_date",
)


BAND_EDGES = (0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
BAND_LABELS = tuple(f"{edge:.2f}" for edge in BAND_EDGES) + ("over",)


BAND_WEIGHTS = (0.42, 0.06, 0.035, 0.025, 0.02, 0.04, 0.03, 0.03, 0.03, 0.04, 0.27)


BAND_NOMINAL = (0.004, 0.012, 0.030, 0.090, 0.085, 0.11, 0.14, 0.17, 0.21, 0.27, 0.42)


_SEAL_KEY = hashlib.sha256(b"authored-listing-adjudication-desk-2026-09-07").digest()
_LOCK = threading.RLock()


_GOLDEN = 0.6180339887498949


def _days(first_day: str, count: int) -> tuple[str, ...]:
    start = date.fromisoformat(str(first_day))
    return tuple((start + timedelta(days=index)).isoformat() for index in range(count))


def band_index(confidence: float) -> int:
    'The band one printed confidence falls in.'

    for index, edge in enumerate(BAND_EDGES):
        if float(confidence) < edge:
            return index
    return len(BAND_EDGES)


def band_label(confidence: float) -> str:
    return BAND_LABELS[band_index(confidence)]


def bands_under(cut: float) -> tuple[str, ...]:
    'The band labels a cut clears, in sheet order.'

    return tuple(
        label
        for index, label in enumerate(BAND_LABELS[: len(BAND_EDGES)])
        if BAND_EDGES[index] <= float(cut) + 1e-12
    )


def _spread(count: int, share: float) -> list[bool]:
    '``count`` decisions holding ``share`` of them true, evenly spread.'

    marks: list[bool] = []
    for index in range(int(count)):
        marks.append(int((index + 1) * float(share)) > int(index * float(share)))
    return marks


def _band_run(count: int) -> list[int]:
    'Which band each of ``count`` listings printed in, laid along the run.'

    boundaries = []
    total = 0.0
    for weight in BAND_WEIGHTS[:-1]:
        total += weight
        boundaries.append(total)
    run: list[int] = []
    for index in range(int(count)):
        position = ((index + 1) * _GOLDEN) % 1.0
        chosen = len(BAND_WEIGHTS) - 1
        for band, edge in enumerate(boundaries):
            if position < edge:
                chosen = band
                break
        run.append(chosen)
    return run


_PLASTIC = 0.7548776662466927


def _confidence(band: int, index: int) -> float:
    low = 0.0 if band == 0 else BAND_EDGES[band - 1]
    high = BAND_EDGES[band] if band < len(BAND_EDGES) else 0.98
    fraction = 0.03 + 0.94 * (((index + 1) * _PLASTIC) % 1.0)
    return round(low + (high - low) * fraction, 4)


@dataclass(frozen=True)
class Queue:
    "One review queue's export window, and what the scorer did to it."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    listing_ids: tuple[str, ...]
    day_of: tuple[int, ...]
    channel: tuple[str, ...]
    period: tuple[str, ...]
    confidence: tuple[float, ...]
    band: tuple[int, ...]
    violating: tuple[bool, ...]
    closed_on: tuple[int, ...]

    @property
    def queue(self) -> str:
        return str(self.spec["queue"])

    @property
    def cut(self) -> float:
        return float(self.spec["cut_in_force"])

    @property
    def bar(self) -> float:
        return float(self.spec["bar_points"]) / 100.0

    def size(self) -> int:
        return len(self.listing_ids)

    def auto_cleared(self, index: int, cut: float | None = None) -> bool:
        return self.confidence[index] < (self.cut if cut is None else float(cut))

    def resolved(self, index: int) -> bool:
        return self.closed_on[index] < len(self.days)

    def rows(self) -> list[dict[str, Any]]:
        'The intake log as the desk exports it, oldest first.'

        return [self.row(index) for index in range(self.size())]

    def row(self, index: int) -> dict[str, Any]:
        closed = self.closed_on[index]
        written = closed < len(self.days)
        return {
            "listing_id": self.listing_ids[index],
            "channel": self.channel[index],
            "intake_date": self.days[self.day_of[index]],
            "intake_period": self.period[index],
            "stated_confidence": self.confidence[index],
            "auto_cleared": "yes" if self.auto_cleared(index) else "no",
            "review_outcome": (
                ("violating" if self.violating[index] else "clean") if written else ""
            ),
            "outcome_closed_date": self.days[closed] if written else "",
        }

    def served_counts(self, first: int, last: int) -> dict[str, int]:
        'How many listings each channel was served over a stretch of days.'

        counts = {name: 0 for name in CHANNELS}
        for index in range(self.size()):
            if first <= self.day_of[index] <= last:
                counts[self.channel[index]] += 1
        return counts

    def traffic(self) -> list[dict[str, Any]]:
        'The traffic report: the month just closed and the month a quarter back.'

        last = len(self.days) - 1
        recent = self.served_counts(last - 29, last)
        earlier = self.served_counts(last - 119, last - 90) if len(self.days) > 119 else (
            self.served_counts(0, 29)
        )
        return [
            {
                "channel": name,
                "served_month_just_closed": recent[name],
                "served_same_month_last_quarter": earlier[name],
            }
            for name in CHANNELS
        ]

    def context(self, as_of_index: int | None = None) -> dict[str, Any]:
        'The evidence the reporting stack hands the notebook for this queue.'

        spec = self.spec
        last = len(self.days) - 1 if as_of_index is None else int(as_of_index)
        return {
            "queue": self.queue,
            "desk": str(spec["desk"]),
            "window": {"first_day": self.days[0], "last_day": self.days[last]},
            "as_of": self.days[last],
            "intake_log_file": LOG_FILE,
            "review": {
                "cut_in_force": float(spec["cut_in_force"]),
                "bar_points": float(spec["bar_points"]),
                "bands": list(BAND_EDGES),
            },
            "audit": {
                "credits_granted": int(spec["credits_granted"]),
                "max_listings_per_batch": int(spec["max_listings_per_batch"]),
                "credit_cost": dict(spec["credit_cost"]),
                "empty_cell_charge": int(spec["empty_cell_charge"]),
            },
            "channel_traffic": self.traffic(),
        }

    def log_csv(self, as_of_index: int | None = None) -> str:
        'The intake log as a CSV document, cut off at one working day.'

        last = len(self.days) - 1 if as_of_index is None else int(as_of_index)
        lines = [",".join(LOG_COLUMNS)]
        for index in range(self.size()):
            if self.day_of[index] > last:
                continue
            row = self.row(index)
            if row["outcome_closed_date"] and self.closed_on[index] > last:
                row = dict(row, review_outcome="", outcome_closed_date="")
            lines.append(",".join(str(row[column]) for column in LOG_COLUMNS))
        return "\n".join(lines) + "\n"


def _closing_day(spec: Mapping[str, Any], channel: str, day: int, weekday: int) -> int:
    "The day a listing's adjudication lands, in day-index terms."

    lag = int(spec["close_lag"][channel])
    if channel not in tuple(spec.get("partner_channels", ())):
        return day + lag
    earliest = day + lag


    offset = (4 - ((weekday + earliest) % 7)) % 7
    return earliest + offset


def build(spec: Mapping[str, Any]) -> Queue:
    "Run one queue's export window through the scorer this desk ships."

    days = _days(spec["first_day"], int(spec["days"]))
    weekday = date.fromisoformat(str(spec["first_day"])).weekday()
    router = int(spec["router_day"])
    periods = list(spec["periods"])

    per_channel: dict[str, list[int]] = {name: [] for name in CHANNELS}
    day_index: dict[str, list[int]] = {name: [] for name in CHANNELS}
    for day in range(len(days)):
        counts = spec["per_day_after"] if day >= router else spec["per_day_before"]
        for name in CHANNELS:
            for _ in range(int(counts[name])):
                day_index[name].append(day)

    listing_ids: list[str] = []
    day_of: list[int] = []
    channel: list[str] = []
    period: list[str] = []
    confidence: list[float] = []
    band: list[int] = []
    violating: list[bool] = []
    closed_on: list[int] = []

    counter = 0
    for name in CHANNELS:
        run_days = day_index[name]
        bands = _band_run(len(run_days))
        per_band: dict[int, list[int]] = {}
        for position, chosen in enumerate(bands):
            per_band.setdefault(chosen, []).append(position)
        marks: dict[int, bool] = {}
        for chosen, positions in per_band.items():
            share = min(1.0, float(spec["overstatement"][name]) * BAND_NOMINAL[chosen])
            for position, flag in zip(positions, _spread(len(positions), share)):
                marks[position] = flag
        for position, day in enumerate(run_days):
            counter += 1
            chosen = bands[position]
            listing_ids.append(f"{spec['listing_prefix']}-{counter:06d}")
            day_of.append(day)
            channel.append(name)
            period.append(periods[0] if day < router else periods[-1])
            confidence.append(_confidence(chosen, position))
            band.append(chosen)
            violating.append(bool(marks[position]))
            closed_on.append(_closing_day(spec, name, day, weekday))

    order = sorted(range(len(listing_ids)), key=lambda index: (day_of[index], listing_ids[index]))
    return Queue(
        spec=spec,
        days=days,
        listing_ids=tuple(listing_ids[index] for index in order),
        day_of=tuple(day_of[index] for index in order),
        channel=tuple(channel[index] for index in order),
        period=tuple(period[index] for index in order),
        confidence=tuple(confidence[index] for index in order),
        band=tuple(band[index] for index in order),
        violating=tuple(violating[index] for index in order),
        closed_on=tuple(closed_on[index] for index in order),
    )
