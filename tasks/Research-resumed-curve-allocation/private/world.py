'The pretraining sweep behind the board, and the console that books nodes.'

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
from math import cos, pi
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence


RECEIPT_FILE = "collection_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-pretraining-node-console-2026-09-07").digest()
_LOCK = threading.RLock()


WARMUP_STEPS = 300
DECAY_STEPS = 12_000
LR_PEAK = 3.0e-4
LR_FLOOR_FRACTION = 0.05


def schedule_fraction(step: int) -> float:
    'The learning rate at one step of a segment, as a fraction of the peak.'

    if step <= 0:
        return 0.0
    if step < WARMUP_STEPS:
        return step / WARMUP_STEPS
    if step >= DECAY_STEPS:
        return LR_FLOOR_FRACTION
    position = (step - WARMUP_STEPS) / (DECAY_STEPS - WARMUP_STEPS)
    return LR_FLOOR_FRACTION + (1.0 - LR_FLOOR_FRACTION) * 0.5 * (1.0 + cos(pi * position))


def learning_rate(step: int) -> float:
    return LR_PEAK * schedule_fraction(step)


def level(steps: float, floor: float, amplitude: float, exponent: float) -> float:
    "Where a run's curve sits after ``steps`` steps of training."

    thousands = max(1e-6, float(steps) / 1000.0)
    return float(floor) + float(amplitude) * thousands ** (-float(exponent))


@dataclass(frozen=True)
class Segment:
    'One stretch of training on one node, with its own step counter.'

    segment_id: str
    config_id: str
    node_type: str
    wall_hours: float
    first_step: int
    last_step: int
    resumed_from: str | None
    launch_script: str
    started_on: str
    booked: bool = False
    receipt_id: str | None = None


@dataclass(frozen=True)
class Run:
    'One configuration, its segments in order, and its private truth.'

    config_id: str
    floor: float
    amplitude: float
    exponent: float
    log_interval: int
    log_cap_interval: int
    segments: tuple[Segment, ...]
    noise_offset: int

    def steps_so_far(self) -> int:
        return sum(int(segment.last_step) for segment in self.segments)

    def level_at(self, steps: float) -> float:
        return level(steps, self.floor, self.amplitude, self.exponent)


@dataclass(frozen=True)
class Campaign:
    'One sweep window: the runs, the nodes, the grant and what was billed.'

    spec: Mapping[str, Any]
    runs: tuple[Run, ...]
    receipts: tuple[Mapping[str, Any], ...] = field(default=())
    _rows: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict, repr=False, compare=False
    )

    @property
    def campaign_id(self) -> str:
        return str(self.spec["campaign"])

    def node_steps_per_hour(self, node_type: str) -> int:
        return int(self.spec["node_steps_per_hour"][str(node_type)])

    def free_nodes(self) -> tuple[str, ...]:
        reserved = set(self.spec["reserved_nodes"])
        return tuple(name for name in self.spec["node_steps_per_hour"] if name not in reserved)

    def run(self, config_id: str) -> Run | None:
        for item in self.runs:
            if item.config_id == str(config_id):
                return item
        return None


    def rows(self, run: Run) -> list[dict[str, Any]]:
        'Every logged row of every segment of one run, in the order written.'

        cached = self._rows.get(run.config_id)
        if cached is not None:
            return [dict(row) for row in cached]
        seed = int(self.spec["seed"])
        noise_sd = float(self.spec["noise_sd"])
        instrument = float(self.spec["instrument_k"])
        written: list[dict[str, Any]] = []
        before = 0
        for segment in run.segments:
            step = run.log_interval
            cap = (segment.last_step // run.log_cap_interval) * run.log_cap_interval
            while step <= cap:
                fraction = schedule_fraction(step)
                scatter = random.Random(
                    f"{seed}:{run.config_id}:{segment.segment_id}:{step}"
                ).gauss(0.0, noise_sd)
                reading = run.level_at(before + step) + instrument * fraction + scatter
                written.append(
                    {
                        "segment_id": segment.segment_id,
                        "step": int(step),
                        "lr": round(LR_PEAK * fraction, 9),
                        "loss": round(reading, 4),
                    }
                )
                step += run.log_interval
            before += int(segment.last_step)
        self._rows[run.config_id] = [dict(row) for row in written]
        return written

    def segment_rows(self, run: Run, segment_id: str) -> list[dict[str, Any]]:
        return [row for row in self.rows(run) if row["segment_id"] == str(segment_id)]

    def last_row(self, run: Run) -> Mapping[str, Any] | None:
        written = self.rows(run)
        return written[-1] if written else None


    def ledger_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for run in self.runs:
            for segment in run.segments:
                rows.append(
                    {
                        "segment_id": segment.segment_id,
                        "config_id": segment.config_id,
                        "node_type": segment.node_type,
                        "wall_hours": round(float(segment.wall_hours), 2),
                        "first_step": int(segment.first_step),
                        "last_step": int(segment.last_step),
                        "resumed_from": segment.resumed_from,
                        "launch_script": segment.launch_script,
                        "started_on": segment.started_on,
                    }
                )
        return rows

    def hours_charged(self) -> int:
        return sum(int(entry["hours_charged"]) for entry in self.receipts)

    def hours_left(self) -> int:
        return int(self.spec["grant_node_hours"]) - self.hours_charged()

    def context(self) -> dict[str, Any]:
        'The campaign as the sweep reporting stack publishes it.'

        spec = self.spec
        return {
            "campaign": self.campaign_id,
            "as_of": str(spec["as_of"]),
            "cluster": {
                "node_types": list(spec["node_steps_per_hour"]),
                "reserved_node_types": list(spec["reserved_nodes"]),
                "job_hours": dict(spec["job_hours"]),
            },
            "budget": {
                "grant_node_hours": int(spec["grant_node_hours"]),
                "hours_charged": self.hours_charged(),
                "hours_left": self.hours_left(),
            },
            "ledger": self.ledger_rows(),
            "curves": {
                run.config_id: [
                    {key: row[key] for key in ("segment_id", "step", "lr", "loss")}
                    for row in self.rows(run)
                ]
                for run in self.runs
            },
        }


    def with_receipts(self, receipts: Sequence[Mapping[str, Any]]) -> "Campaign":
        'The same campaign carrying a different set of billed bookings.'

        return build(self.spec, receipts)


def _segment_id(config_id: str, index: int) -> str:
    return f"{config_id}-s{index:02d}"


def build(
    spec: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]] = ()
) -> Campaign:
    'One parameter set plus whatever the console has billed, as a campaign.'

    booked: dict[str, list[Mapping[str, Any]]] = {}
    for entry in receipts:
        if entry.get("refusal") or not int(entry.get("steps_returned", 0)):
            continue
        booked.setdefault(str(entry["config_id"]), []).append(entry)

    runs: list[Run] = []
    for offset, item in enumerate(spec["runs"]):
        config_id = str(item["config_id"])
        segments: list[Segment] = []
        previous: str | None = None
        for index, plan in enumerate(item["segments"], start=1):
            node_type = str(plan["node"])
            hours = float(plan["hours"])
            steps = int(
                plan["steps"] if "steps" in plan
                else round(hours * int(spec["node_steps_per_hour"][node_type]))
            )
            segment_id = _segment_id(config_id, index)
            segments.append(
                Segment(
                    segment_id=segment_id,
                    config_id=config_id,
                    node_type=node_type,
                    wall_hours=hours,
                    first_step=0,
                    last_step=steps,
                    resumed_from=previous,
                    launch_script=str(item.get("launch_script", "launch/train_v4.sh")),
                    started_on=str(plan.get("started_on", spec["as_of"])),
                )
            )
            previous = segment_id
        for entry in booked.get(config_id, ()):
            index = len(segments) + 1
            segment_id = _segment_id(config_id, index)
            segments.append(
                Segment(
                    segment_id=segment_id,
                    config_id=config_id,
                    node_type=str(entry["node_type"]),
                    wall_hours=float(entry["hours_charged"]),
                    first_step=0,
                    last_step=int(entry["steps_returned"]),
                    resumed_from=previous,
                    launch_script=str(item.get("launch_script", "launch/train_v4.sh")),
                    started_on=str(entry.get("day", spec["as_of"])),
                    booked=True,
                    receipt_id=str(entry["receipt_id"]),
                )
            )
            previous = segment_id
        runs.append(
            Run(
                config_id=config_id,
                floor=float(item["floor"]),
                amplitude=float(item["amplitude"]),
                exponent=float(item["exponent"]),
                log_interval=int(item.get("log_interval", spec["log_interval"])),
                log_cap_interval=int(
                    item.get("log_cap_interval", item.get("log_interval", spec["log_interval"]))
                ),
                segments=tuple(segments),
                noise_offset=offset + 1,
            )
        )
    return Campaign(spec=spec, runs=tuple(runs), receipts=tuple(dict(e) for e in receipts))


PRESENTATIONS = ("as recorded", "nodes", "logging")


def presentation_note(presentation: str) -> str:
    if presentation == "nodes":
        return "the same segments with the node each one landed on written the other way round"
    if presentation == "logging":
        return "the same segments with every curve written at the same row spacing"
    return "the segments as the ledger carries them"


def presented(spec: Mapping[str, Any], presentation: str) -> Mapping[str, Any]:
    'The same training under a different accident of how it was recorded.'

    if presentation == "as recorded":
        return spec
    changed = json.loads(json.dumps(dict(spec)))
    if presentation == "logging":
        finest = min(
            [int(spec["log_interval"])]
            + [int(item["log_interval"]) for item in spec["runs"] if "log_interval" in item]
        )
        for item in changed["runs"]:
            item["log_cap_interval"] = int(item.get("log_interval", spec["log_interval"]))
            item["log_interval"] = finest
        return changed
    speeds = dict(changed["node_steps_per_hour"])
    reckoned = str(changed["reckoning_node"])
    reserved = list(changed["reserved_nodes"])
    names = list(speeds)
    base = speeds[reckoned]


    for name in names:
        if name == reckoned:
            continue
        speeds[name] = int(round(base * (1.15 if name in reserved else 0.55)))
    rotation = {name: names[(index - 1) % len(names)] for index, name in enumerate(names)}
    for item in changed["runs"]:
        for plan in item["segments"]:
            was = str(plan["node"])
            steps = int(round(float(plan["hours"]) * int(spec["node_steps_per_hour"][was])))
            now = rotation[was]
            plan["node"] = now
            plan["steps"] = steps
            plan["hours"] = round(steps / speeds[now], 2)
    changed["node_steps_per_hour"] = speeds
    return changed


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def _refusal(
    campaign: Campaign,
    config_id: Any,
    node_type: Any,
    hours: Any,
    reason: str,
    receipt_id: str,
    day: str,
    charged: int,
    remaining: int,
) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt_id),
        "campaign": campaign.campaign_id,
        "day": str(day),
        "config_id": None if config_id is None else str(config_id),
        "node_type": None if node_type is None else str(node_type),
        "hours_requested": hours if isinstance(hours, int) else None,
        "steps_returned": 0,
        "schedule_restarted": False,
        "hours_charged": int(charged),
        "hours_remaining": int(remaining),
        "refusal": str(reason),
        "observed": {"rows": []},
    }


def refusal_reason(
    campaign: Campaign, config_id: Any, node_type: Any, hours: Any
) -> str | None:
    'Why the console will not run this request, or None when it will.'

    window = campaign.spec["job_hours"]
    if not isinstance(hours, int) or isinstance(hours, bool):
        return "a job is booked in whole wall hours"
    if hours < int(window["min"]) or hours > int(window["max"]):
        return f"a job runs {int(window['min'])} to {int(window['max'])} wall hours"
    if str(node_type) not in campaign.spec["node_steps_per_hour"]:
        return "no node type of that name on this cluster"
    if str(node_type) in set(campaign.spec["reserved_nodes"]):
        return f"{node_type} is reserved for the whole window"
    if campaign.run(str(config_id)) is None:
        return "no run of that name in this campaign"
    return None


def review(
    campaign: Campaign,
    receipts: Sequence[Mapping[str, Any]],
    config_id: Any,
    node_type: Any,
    hours: Any,
    receipt_id: str,
    day: str,
) -> list[dict[str, Any]]:
    'The receipt stream with one more booking on it, touching no file.'

    held = build(campaign.spec, receipts)
    grown = [dict(entry) for entry in receipts]
    reason = refusal_reason(held, config_id, node_type, hours)
    charged = 1 if reason else int(hours)
    remaining = held.hours_left() - charged
    if reason is not None:
        body = _refusal(
            held, config_id, node_type, hours, reason, receipt_id, day, charged, remaining
        )
    else:
        run = held.run(str(config_id))
        steps = int(round(int(hours) * held.node_steps_per_hour(str(node_type))))
        after = build(
            campaign.spec,
            [
                *receipts,
                {
                    "receipt_id": str(receipt_id),
                    "config_id": str(config_id),
                    "node_type": str(node_type),
                    "hours_charged": int(hours),
                    "steps_returned": steps,
                    "refusal": None,
                    "day": str(day),
                },
            ],
        )
        grown_run = after.run(str(config_id))
        assert grown_run is not None and run is not None
        fresh = grown_run.segments[-1]
        body = {
            "receipt_id": str(receipt_id),
            "campaign": campaign.campaign_id,
            "day": str(day),
            "config_id": str(config_id),
            "node_type": str(node_type),
            "hours_requested": int(hours),
            "steps_returned": steps,
            "schedule_restarted": True,
            "hours_charged": charged,
            "hours_remaining": remaining,
            "refusal": None,
            "observed": {
                "segment_id": fresh.segment_id,
                "resumed_from": fresh.resumed_from,
                "rows": after.segment_rows(grown_run, fresh.segment_id),
            },
        }
    grown.append(seal_body(body, len(grown) + 1, grown[-1]["seal"] if grown else ""))
    return grown


def receipt_document(
    campaign: Campaign, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "campaign": campaign.campaign_id,
        "entries": [dict(entry) for entry in receipts],
    }


def read_receipts(workspace: Path, campaign: Campaign) -> list[dict[str, Any]]:
    'Every booking this window was billed for, or a reason the file will not read.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the booking receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("campaign") != campaign.campaign_id
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the booking receipts do not belong to this campaign")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a booking entry is not a console record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a booking entry has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the booking entries are not in the order the console wrote them")
        if entry.get("campaign") != campaign.campaign_id:
            raise ValueError("a booking entry belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a booking entry does not carry the node console's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def collect(
    workspace: Path,
    campaign: Campaign,
    config_id: Any,
    node_type: Any,
    hours: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    'Put one booking through the node console and append its receipt.'

    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, campaign)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                held = build(campaign.spec, entries)
                return {
                    "receipt": entry,
                    "ran": False,
                    "hours_charged": held.hours_charged(),
                    "hours_left": held.hours_left(),
                }
        held = build(campaign.spec, entries)
        reason = refusal_reason(held, config_id, node_type, hours)
        wanted = 1 if reason else int(hours)
        if wanted > held.hours_left():
            raise ValueError(
                f"that job wants {wanted} node-hours and the window has "
                f"{held.hours_left()} left on the grant"
            )
        entries = review(
            campaign, entries, config_id, node_type, hours, receipt_id,
            str(campaign.spec["as_of"]),
        )
        grown = build(campaign.spec, entries)
        pending = root / (RECEIPT_FILE + ".pending")
        pending.write_text(
            json.dumps(receipt_document(campaign, entries), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "hours_charged": grown.hours_charged(),
            "hours_left": grown.hours_left(),
        }
