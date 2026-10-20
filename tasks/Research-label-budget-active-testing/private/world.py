"The world behind the ticket-triage misroute review, and the vendor's reviewer."

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
import hashlib
import math
from typing import Any, Mapping, Sequence


CHANNELS = ("email", "webform", "phone")
QUEUES = ("billing", "access", "hardware", "orders", "general")


PATTERN = 4


BLOCK = 64
UNTAGGED_DEN = 16


def _unit(*parts: Any) -> Fraction:
    'A reproducible number in [0, 1) for one named draw.'

    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:12]
    return Fraction(int(digest, 16), 16 ** 12)


_CACHE: dict[tuple[str, str], Any] = {}


def _cached(desk: "Desk", name: str, build: Any) -> Any:
    key = (desk.code, name)
    if key not in _CACHE:
        _CACHE[key] = build()
    return _CACHE[key]


def _days(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


@dataclass(frozen=True)
class Desk:
    'One review: its tickets, its label pool, and the reviewer who labels.'

    spec: Mapping[str, Any]


    @property
    def desk(self) -> str:
        return str(self.spec["desk"])

    @property
    def code(self) -> str:
        return str(self.spec["code"])

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.spec["segments"])

    def correct_queue(self, segment: str) -> str:
        return str(self.spec["segments"][str(segment)]["queue"])

    def confusable_queue(self, segment: str) -> str:
        return str(self.spec["segments"][str(segment)]["confusable"])

    def misroutes_per_pattern(self, segment: str) -> int:
        return int(self.spec["segments"][str(segment)]["misroutes"])

    def line_of(self, segment: str) -> str:
        return str(self.spec["segments"][str(segment)]["line"])

    def catalogue(self) -> dict[str, list[str]]:
        'The product catalogue: which segments sit under which product line.'

        lines: dict[str, list[str]] = {}
        for segment in self.segments:
            lines.setdefault(self.line_of(segment), []).append(segment)
        return {line: sorted(members) for line, members in sorted(lines.items())}


    def _routed(self, segment: str, index: int) -> tuple[str, bool]:
        'The queue the classifier sent the index-th ticket of a segment to.'

        misrouted = index % PATTERN < self.misroutes_per_pattern(segment)
        queue = self.confusable_queue(segment) if misrouted else self.correct_queue(segment)
        return queue, misrouted

    def intake_rows(self) -> list[dict[str, Any]]:
        "Last month's tickets, as the intake export writes them."

        return _cached(self, "intake_rows", self._build_intake_rows)

    def _build_intake_rows(self) -> list[dict[str, Any]]:
        window = _days(self.spec["window"][0], self.spec["window_days"])
        outage = set(self.spec["tagger_outage"])
        open_days = [day for day in window if day not in outage]
        rows: list[dict[str, Any]] = []
        counter = 0
        for channel in CHANNELS:
            for segment in self.segments:
                blocks = int(self.spec["intake_mix"].get((channel, segment), 0))
                if not blocks:
                    continue
                size = blocks * BLOCK
                untagged = size // UNTAGGED_DEN
                for index in range(size):
                    counter += 1
                    queue, _ = self._routed(segment, index)
                    if index < untagged:
                        day = sorted(outage)[index % len(outage)]
                        tag = ""
                    else:
                        day = open_days[(index - untagged) % len(open_days)]
                        tag = segment
                    rows.append({
                        "ticket_id": f"{self.code}-I{counter:05d}",
                        "arrived_on": day,
                        "channel": channel,
                        "product_line": self.line_of(segment),
                        "segment": tag,
                        "priority": f"P{index % 5 + 1}",
                        "predicted_queue": queue,
                    })
        rows.sort(key=lambda row: (row["arrived_on"], row["ticket_id"]))
        return rows

    def _intake_index(self) -> dict[str, tuple[str, bool]]:
        '{ticket id: (segment, misrouted)} for every intake ticket, tag or no tag.'

        return _cached(self, "intake_index", self._build_intake_index)

    def _build_intake_index(self) -> dict[str, tuple[str, bool]]:
        index: dict[str, tuple[str, bool]] = {}
        counter = 0
        for channel in CHANNELS:
            for segment in self.segments:
                blocks = int(self.spec["intake_mix"].get((channel, segment), 0))
                for position in range(blocks * BLOCK):
                    counter += 1
                    _, misrouted = self._routed(segment, position)
                    index[f"{self.code}-I{counter:05d}"] = (segment, misrouted)
        return index


    def pool_rows(self) -> list[dict[str, Any]]:
        "The March export the vendor labels from, with the model's own margin."

        return _cached(self, "pool_rows", self._build_pool_rows)

    def _build_pool_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        counter = 0
        for channel in CHANNELS:
            for segment in self.segments:
                size = int(self.spec["pool_mix"].get((channel, segment), 0))
                base = Fraction(str(self.spec["segments"][segment]["margin"]))
                for index in range(size):
                    counter += 1
                    queue, _ = self._routed(segment, index)
                    jitter = (_unit("margin", self.code, segment, index) - Fraction(1, 2)) / 20
                    margin = max(Fraction(1, 100), min(Fraction(99, 100), base + jitter))
                    rows.append({
                        "item_id": f"{self.code}-P{counter:05d}",
                        "channel": channel,
                        "product_line": self.line_of(segment),
                        "segment": segment,
                        "priority": f"P{index % 5 + 1}",
                        "predicted_queue": queue,
                        "model_margin": round(float(margin), 4),
                    })
        return rows

    def pool_index(self) -> dict[str, dict[str, Any]]:
        return _cached(self, "pool_index",
                       lambda: {row["item_id"]: row for row in self.pool_rows()})


    def stamp_chance(self, position: int) -> Fraction:
        "How often the reviewer takes the console's pre-filled routing instead."

        ramp = self.spec["ramp"]
        onset = int(ramp["onset"])
        if int(position) <= onset:
            return Fraction(0)
        rise = Fraction(str(ramp["slope"])) * (int(position) - onset)
        return min(Fraction(str(ramp["cap"])), rise)

    def label_of(self, item: Mapping[str, Any], session_id: str, position: int) -> str:
        'The queue the reviewer writes for one item at one position of a session.'

        chance = self.stamp_chance(position)
        if chance and _unit("stamp", self.code, session_id, position) < chance:
            return str(item["predicted_queue"])
        return self.correct_queue(str(item["segment"]))


    def draw_weights(self) -> dict[str, float]:
        'How hard the sampler pulls on each pool item, by how unsure the model is.'

        return _cached(self, "draw_weights", self._build_draw_weights)

    def _build_draw_weights(self) -> dict[str, float]:
        sharpness = int(self.spec.get("draw_sharpness", 3))
        return {
            row["item_id"]: max(1e-9, (1.0 - float(row["model_margin"])) ** sharpness)
            for row in self.pool_rows()
        }

    def draw_order(self) -> list[dict[str, Any]]:
        'The pool in the order the uncertainty sampler would take it.'

        return _cached(self, "draw_order", self._build_draw_order)

    def _build_draw_order(self) -> list[dict[str, Any]]:
        weights = self.draw_weights()
        ordered = []
        for row in self.pool_rows():
            draw = float(_unit("draw", self.code, row["item_id"]))
            key = -math.log(max(draw, 1e-12)) / weights[row["item_id"]]
            ordered.append((key, row["item_id"], row))
        ordered.sort(key=lambda entry: (entry[0], entry[1]))
        return [entry[2] for entry in ordered]

    def draw_probability(self, item_id: str) -> float:
        "The chance that item had of being the sampler's next pick."

        chances = _cached(self, "draw_probability", self._build_draw_probability)
        return chances[str(item_id)]

    def _build_draw_probability(self) -> dict[str, float]:
        weights = self.draw_weights()
        total = sum(weights.values())
        return {key: round(value / total, 8) for key, value in weights.items()}

    def price_of(self, channel: str) -> int:
        return int(self.spec["prices"][str(channel)])


    def intake_truth(self) -> Fraction:
        "The share of last month's tickets the classifier sent to the wrong queue."

        return _cached(self, "intake_truth", self._build_intake_truth)

    def _build_intake_truth(self) -> Fraction:
        index = self._intake_index()
        misrouted = sum(1 for _segment, wrong in index.values() if wrong)
        return Fraction(misrouted, len(index))

    def pool_rate(self) -> Fraction:
        'The same share read over the March export instead.'

        return _cached(self, "pool_rate", self._build_pool_rate)

    def _build_pool_rate(self) -> Fraction:
        rows = self.pool_rows()
        wrong = sum(
            1 for row in rows
            if row["predicted_queue"] != self.correct_queue(row["segment"])
        )
        return Fraction(wrong, len(rows))

    def bounds(self) -> tuple[Fraction, Fraction]:
        'What the public intake leaves open after its preserved batches are read.'

        return _cached(self, "bounds", self._build_bounds)

    def _build_bounds(self) -> tuple[Fraction, Fraction]:
        fixed = self.intake_truth()
        return fixed, fixed

    def channel_rate(self, channel: str) -> Fraction:
        index = self._intake_index()
        rows = [row for row in self.intake_rows() if row["channel"] == channel]
        wrong = sum(1 for row in rows if index[row["ticket_id"]][1])
        return Fraction(wrong, len(rows))
