'The two contact centres behind the triage pipeline, and the review desk.'

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import hashlib
import hmac
import json
from math import exp
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence


FEATURES = (
    "body_length",
    "attachments",
    "wait_minutes",
    "sentiment",
    "account_age_months",
    "product_breadth",
)

CHANNELS = ("queue", "export")
SITES = ("ridgeline", "brookfield")
LEDGER_FILE = "label_ledger.json"


_SEAL_KEY = hashlib.sha256(b"authored-triage-review-desk-2026-09-06").digest()
_LOCK = threading.RLock()


CENTRE = (180.0, 0.8, 14.0, 0.0, 34.0, 2.6)
SPREAD = (60.0, 0.9, 6.0, 1.0, 14.0, 1.1)


LAW_INTERCEPT = -0.35
LAW_LINEAR = (0.85, 0.55, 0.70, -1.05, -0.45, -0.40)
LAW_SCALE = 6.2
LAW_HINGE = -20.0
LAW_HINGE_AGE = -1.0
LAW_HINGE_BREADTH = -0.8


_GOLDEN = 0.6180339887498949


def _days(first_day: str, count: int) -> tuple[str, ...]:
    start = date.fromisoformat(str(first_day))
    return tuple((start + timedelta(days=index)).isoformat() for index in range(count))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + exp(-value))
    scaled = exp(value)
    return scaled / (1.0 + scaled)


def standardise(features: Sequence[float], model: Mapping[str, Any]) -> list[float]:
    centre = list(model["centre"])
    scale = list(model["scale"])
    return [(float(value) - centre[index]) / scale[index] for index, value in enumerate(features)]


def score_row(features: Sequence[float], model: Mapping[str, Any]) -> float:
    "The shipped pipeline's escalation score for one ticket."

    standardised = standardise(features, model)
    total = float(model["intercept"])
    for weight, value in zip(model["coefficients"], standardised):
        total += float(weight) * value
    return _sigmoid(total)


def escalation_probability(features: Sequence[float]) -> float:
    'The law both centres escalate under.'

    unit = [(float(value) - CENTRE[index]) / SPREAD[index] for index, value in enumerate(features)]
    total = LAW_INTERCEPT
    for weight, value in zip(LAW_LINEAR, unit):
        total += weight * value
    hinge = max(0.0, LAW_HINGE_AGE - unit[4]) * max(0.0, LAW_HINGE_BREADTH - unit[5])
    return _sigmoid(LAW_SCALE * total + LAW_HINGE * hinge)


@dataclass(frozen=True)
class Stream:
    "One centre's received tickets over one window, and what the pipeline did."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    ticket_ids: tuple[str, ...]
    day_of: tuple[str, ...]
    surface: tuple[str, ...]
    prior_contacts: tuple[int, ...]
    features: tuple[tuple[float, ...], ...]
    score: tuple[float, ...]
    decision: tuple[int, ...]
    label: tuple[int, ...]
    order: tuple[int, ...] = field(repr=False, default=())

    @property
    def deployment(self) -> str:
        return str(self.spec["deployment"])

    @property
    def site(self) -> str:
        return str(self.spec["site"])

    @property
    def threshold(self) -> int:
        return int(self.spec["history_panel_from_contact"])

    def size(self) -> int:
        return len(self.ticket_ids)

    def wrong(self, index: int) -> bool:
        return self.decision[index] != self.label[index]

    def in_queue(self, index: int) -> bool:
        return self.prior_contacts[index] >= self.threshold

    def in_window(self, index: int, low: int | None, high: int | None) -> bool:
        contacts = self.prior_contacts[index]
        if low is not None and contacts < low:
            return False
        if high is not None and contacts > high:
            return False
        return True

    def indices(self, low: int | None = None, high: int | None = None) -> list[int]:
        return [index for index in range(self.size()) if self.in_window(index, low, high)]


    def counters(self) -> list[dict[str, Any]]:
        'One row a day: received, how many the queue held, how many it passed.'

        received = {day: 0 for day in self.days}
        queued = {day: 0 for day in self.days}
        for index, day in enumerate(self.day_of):
            received[day] += 1
            if self.in_queue(index):
                queued[day] += 1
        rows: list[dict[str, Any]] = []
        pending = 0
        for position, day in enumerate(self.days):
            pending += received[day]
            export_rows = 0
            if position % 7 == 6 or position == len(self.days) - 1:
                export_rows, pending = pending, 0
            rows.append(
                {
                    "day": day,
                    "received": received[day],
                    "queued": queued[day],
                    "skipped_no_history_panel": received[day] - queued[day],
                    "export_rows": export_rows,
                }
            )
        return rows

    def context(self) -> dict[str, Any]:
        'The evidence the reporting stack hands the notebook for this deployment.'

        spec = self.spec
        return {
            "deployment": self.deployment,
            "site": self.site,
            "window": {"first_day": self.days[0], "last_day": self.days[-1]},
            "as_of": str(spec["as_of"]),
            "intake": {
                "queue": str(spec["queue_name"]),
                "export": str(spec["export_name"]),
                "history_panel_from_contact": self.threshold,
                "surfaces": list(spec["surfaces"]),
            },
            "review": {
                "units_granted": int(spec["units_granted"]),
                "unit_cost": {"queue": 1, "export": 3},
                "max_rows_per_request": {"queue": 200, "export": 60},
            },
            "model": dict(MODELS[str(spec["model"])]),
            "intake_counters": self.counters(),
        }


    def eligible(
        self,
        channel: str,
        low: int | None,
        high: int | None,
        through: str | None = None,
    ) -> list[int]:
        'The tickets a channel could hand a reviewer, in the order it serves them.'

        return [
            index
            for index in self.order
            if self.in_window(index, low, high)
            and (channel != "queue" or self.in_queue(index))
            and (through is None or self.day_of[index] <= str(through))
        ]

    def systematic(self, frame: Sequence[int], rows: int) -> list[int]:
        "One ticket from each equal band of the frame, keeping the band's mix."

        total = len(frame)
        if rows <= 0 or total == 0:
            return []
        if rows >= total:
            return list(frame)
        chosen: list[int] = []
        debt = 0.0
        for position in range(rows):
            low = (position * total) // rows
            high = ((position + 1) * total) // rows
            band = list(frame[low:high]) or [frame[min(low, total - 1)]]
            missed = [index for index in band if self.wrong(index)]
            matched = [index for index in band if not self.wrong(index)]
            debt += len(missed) / len(band)
            take_missed = debt >= 1.0 - 1e-9
            pool = missed if (take_missed and missed) else matched
            if not pool:
                pool = missed or matched
            if pool is missed:
                debt -= 1.0
            chosen.append(pool[position % len(pool)])
        return chosen

    def payload(self, index: int) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_ids[index],
            "day": self.day_of[index],
            "surface": self.surface[index],
            "prior_contacts": self.prior_contacts[index],
            "features": {
                name: round(self.features[index][position], 4)
                for position, name in enumerate(FEATURES)
            },
            "pipeline_score": round(self.score[index], 6),
            "pipeline_decision": self.decision[index],
            "reviewed_label": self.label[index],
        }


def _log1m(value: float) -> float:
    from math import log

    return log(max(1e-12, 1.0 - value))


@dataclass(frozen=True)
class Frame:
    "One window's arrivals and outcomes, before any pipeline has read them."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    ticket_ids: tuple[str, ...]
    day_of: tuple[str, ...]
    surface: tuple[str, ...]
    prior_contacts: tuple[int, ...]
    features: tuple[tuple[float, ...], ...]
    label: tuple[int, ...]


def build_frame(spec: Mapping[str, Any]) -> Frame:
    'Arrivals over the window, and whether each ticket ended up escalated.'

    days = _days(spec["first_day"], int(spec["days"]))
    generator = random.Random(int(spec["seed"]))
    marketplace = float(spec["marketplace_share"])
    per_day = list(spec["arrivals"])
    shift = dict(spec.get("marketplace_shift", {}))

    ticket_ids: list[str] = []
    day_of: list[str] = []
    surface: list[str] = []
    prior: list[int] = []
    features: list[tuple[float, ...]] = []
    probability: list[float] = []

    counter = 0
    for position, day in enumerate(days):
        arrivals = int(per_day[position % len(per_day)])
        for _ in range(arrivals):
            from_marketplace = generator.random() < marketplace
            name = spec["surfaces"][1] if from_marketplace else spec["surfaces"][0]
            mean_contacts = (
                float(spec["marketplace_contacts"])
                if from_marketplace
                else float(spec["portal_contacts"])
            )
            base = int(
                spec["marketplace_base_contacts"]
                if from_marketplace
                else spec["portal_base_contacts"]
            )
            contacts = base + int(-mean_contacts * _log1m(generator.random()))
            row = []
            for axis, (centre, spread) in enumerate(zip(CENTRE, SPREAD)):
                offset = float(shift.get(FEATURES[axis], 0.0)) if from_marketplace else 0.0
                row.append(generator.gauss(centre + offset * spread, spread))
            values = tuple(row)
            counter += 1
            ticket_ids.append(f"{spec['ticket_prefix']}-{counter:06d}")
            day_of.append(day)
            surface.append(name)
            prior.append(contacts)
            features.append(values)
            probability.append(escalation_probability(values))

    ranking = sorted(range(len(probability)), key=lambda index: (probability[index], index))
    label = [0] * len(ranking)
    turn = float(spec.get("label_offset", 0.37))
    for index in ranking:
        turn = (turn + _GOLDEN) % 1.0
        label[index] = 1 if turn < probability[index] else 0

    return Frame(
        spec=spec,
        days=days,
        ticket_ids=tuple(ticket_ids),
        day_of=tuple(day_of),
        surface=tuple(surface),
        prior_contacts=tuple(prior),
        features=tuple(features),
        label=tuple(label),
    )


def build(spec: Mapping[str, Any]) -> Stream:
    "Run one centre's window through the pipeline this deployment ships."

    frame = build_frame(spec)
    model = MODELS[str(spec["model"])]
    score = tuple(score_row(values, model) for values in frame.features)
    decision = tuple(1 if value >= float(model["threshold"]) else 0 for value in score)
    order = tuple(sorted(range(len(score)), key=lambda index: (score[index], index)))
    return Stream(
        spec=spec,
        days=frame.days,
        ticket_ids=frame.ticket_ids,
        day_of=frame.day_of,
        surface=frame.surface,
        prior_contacts=frame.prior_contacts,
        features=frame.features,
        score=score,
        decision=decision,
        label=frame.label,
        order=order,
    )


MODELS: dict[str, dict[str, Any]] = {}


def _load_models() -> None:
    path = Path(__file__).resolve().with_name("models.json")
    MODELS.clear()
    MODELS.update(json.loads(path.read_text(encoding="utf-8")))


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt_body(
    stream: Stream,
    channel: str,
    low: int | None,
    high: int | None,
    requested: int,
    served: Sequence[int],
    passed_over: int,
    receipt_id: str,
    day: str,
) -> dict[str, Any]:
    unit = int(stream.context()["review"]["unit_cost"][channel])
    return {
        "receipt_id": str(receipt_id),
        "deployment": stream.deployment,
        "day": str(day),
        "site": stream.site,
        "channel": str(channel),
        "prior_contacts_min": None if low is None else int(low),
        "prior_contacts_max": None if high is None else int(high),
        "n_requested": int(requested),
        "n_returned": len(served),
        "n_skipped": int(passed_over),
        "units_charged": unit * len(served),
        "snapshot_id": str(stream.spec["snapshot_id"]),
        "observed": {"rows": [stream.payload(index) for index in served]},
    }


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def served_indices(stream: Stream, entries: Sequence[Mapping[str, Any]]) -> set[str]:
    served: set[str] = set()
    for entry in entries:
        for row in entry.get("observed", {}).get("rows", ()):
            served.add(str(row["ticket_id"]))
    return served


def draw(
    stream: Stream,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    low: int | None,
    high: int | None,
    rows: int,
    through: str | None = None,
) -> tuple[list[int], int]:
    'The rows a channel hands back, and how many it passed over unserved.'

    already = served_indices(stream, entries)
    frame = [
        index
        for index in stream.eligible(channel, low, high, through)
        if stream.ticket_ids[index] not in already
    ]
    served = stream.systematic(frame, rows)
    if served:
        return served, 0
    if channel == "queue" and stream.indices(low, high):
        return [], int(rows)
    return [], 0


def review(
    stream: Stream,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    low: int | None,
    high: int | None,
    rows: int,
    receipt_id: str,
    day: str,
    through: str | None = None,
) -> list[dict[str, Any]]:
    'The ledger with one more review on it, without touching any file.'

    served, passed_over = draw(stream, entries, channel, low, high, rows, through)
    body = receipt_body(
        stream, channel, low, high, rows, served, passed_over, receipt_id, day
    )
    grown = [dict(entry) for entry in entries]
    grown.append(seal_body(body, len(grown) + 1, grown[-1]["seal"] if grown else ""))
    return grown


def units_spent(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["units_charged"]) for entry in entries)


def units_left(stream: Stream, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(stream.spec["units_granted"]) - units_spent(entries)


def ledger_document(stream: Stream, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"deployment": stream.deployment, "entries": [dict(entry) for entry in entries]}


def read_ledger(workspace: Path, stream: Stream) -> list[dict[str, Any]]:
    'Every review this deployment has paid for, or a reason the file will not read.'

    path = Path(workspace) / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("the review ledger must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("deployment") != stream.deployment
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the review ledger does not belong to this deployment")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a review entry is not a desk record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a review entry has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the review entries are not in the order the desk wrote them")
        if entry.get("deployment") != stream.deployment:
            raise ValueError("a review entry belongs to another deployment")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a review entry does not carry the review desk's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def collect(
    workspace: Path,
    stream: Stream,
    site: Any,
    channel: Any,
    rows: Any,
    receipt_id: Any,
    low: Any = None,
    high: Any = None,
) -> dict[str, Any]:
    'Put one review request through a channel and append its receipt.'

    site = str(site or "")
    channel = str(channel or "")
    if site != stream.site:
        raise ValueError(
            f"this deployment reviews {stream.site} tickets; {site!r} has no review desk here"
        )
    if channel not in CHANNELS:
        raise ValueError("channel must be queue or export")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
        raise ValueError("rows must be a positive whole number")
    context = stream.context()
    cap = int(context["review"]["max_rows_per_request"][channel])
    if rows > cap:
        raise ValueError(f"the {channel} takes at most {cap} rows a request")
    for name, value in (("prior_contacts_min", low), ("prior_contacts_max", high)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise ValueError(f"{name} must be a whole number of prior contacts, or left out")
    if low is not None and high is not None and int(low) > int(high):
        raise ValueError("prior_contacts_min cannot be above prior_contacts_max")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")

    unit = int(context["review"]["unit_cost"][channel])
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_ledger(root, stream)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(entries),
                    "units_left": units_left(stream, entries),
                }
        served, passed_over = draw(stream, entries, channel, low, high, int(rows))
        cost = unit * len(served)
        if cost > units_left(stream, entries):
            raise ValueError(
                f"{len(served)} rows on the {channel} cost {cost} units and the quarter has "
                f"{units_left(stream, entries)} left"
            )
        body = receipt_body(
            stream, channel, low, high, int(rows), served, passed_over, receipt_id,
            str(context["as_of"]),
        )
        entries.append(seal_body(body, len(entries) + 1, entries[-1]["seal"] if entries else ""))
        pending = root / (LEDGER_FILE + ".pending")
        pending.write_text(
            json.dumps(ledger_document(stream, entries), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / LEDGER_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "units_spent": units_spent(entries),
            "units_left": units_left(stream, entries),
        }


_load_models()
