'The world behind the sweep summary table, and the training queue.'

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


RECEIPT_FILE = "sweep_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-training-queue-instrument-2026-09-06").digest()
_LOCK = threading.RLock()


CHECKPOINTS = 40


BATCH = 8


WIDTH_MIN = 8
WIDTH_MAX = 4096
DATA_MIN = 500
DATA_MAX = 4_000_000
LEARNING_RATE_MAX = 1.0


def _unit(*parts: Any) -> float:
    'A stable number in [0, 1) for one authored draw.'

    key = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return int.from_bytes(digest[:7], "big") / float(1 << 56)


def _signed(*parts: Any) -> float:
    return 2.0 * _unit(*parts) - 1.0


def _span(low: float, high: float, *parts: Any) -> float:
    return low + (high - low) * _unit(*parts)


@dataclass(frozen=True, eq=False)
class World:
    'One sweep: its surface, its shards, its queue and the runs it holds.'

    spec: Mapping[str, Any]


    @property
    def sweep(self) -> str:
        return str(self.spec["sweep"])

    @property
    def runs(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.spec["runs"])


    def surface(self, width: float, data: float) -> float:
        'The loss this architecture reaches at a width and an example count.'

        spec = self.spec
        return (
            float(spec["floor"])
            + float(spec["A"]) * float(width) ** (-float(spec["a"]))
            + float(spec["B"]) * float(data) ** (-float(spec["b"]))
        )

    def charge(self, width: int, data: int) -> int:
        'What the scheduler bills for one job, in queue units.'

        divisor = int(self.spec["unit_divisor"])
        return (int(width) * int(width) * int(data) + divisor // 2) // divisor

    def steps(self, data: int) -> int:
        return int(data) // BATCH


    def shard_offset(self, shard: str) -> float:
        'How far one validation shard sits from the pooled validation set.'

        entry = self.spec["shards"][str(shard)]
        offset = float(entry["offset"])
        if entry["lineage"] in self.training_blocks():
            offset += float(self.spec["contamination"])
        return offset

    def training_blocks(self) -> tuple[str, ...]:
        return tuple(
            str(entry["block"])
            for entry in self.spec["blocks"]
            if str(entry["role"]) == "training mixture"
        )

    def shard_lineage(self, shard: str) -> str:
        return str(self.spec["shards"][str(shard)]["lineage"])

    def comes_apart(self, width: int, learning_rate: float) -> bool:
        'Whether a job at these settings destabilises before it converges.'

        return (
            int(width) >= int(self.spec["unstable_width"])
            and float(learning_rate) > float(self.spec["rate_onset"])
        )


    def reading(self, run: Mapping[str, Any]) -> dict[str, Any]:
        "One job's final validation loss and the curve behind it."

        width, data = int(run["width"]), int(run["data"])
        rate, shard = float(run["learning_rate"]), str(run["val_shard_id"])
        run_id = str(run["run_id"])
        key = (str(self.spec.get("noise_key", self.sweep)), run_id, width, data, shard)
        base = self.surface(width, data)
        measured = base + self.shard_offset(shard) + float(self.spec["noise_sd"]) * _signed(
            "noise", *key
        )
        start = measured + _span(0.85, 1.45, "start", *key)
        if not self.comes_apart(width, rate):
            curve = _descent(start, measured, CHECKPOINTS)
            final = measured
        else:
            shortfall = _span(
                *self.spec["late_shortfall"], "shortfall", *key, rate
            )
            rise = _span(*self.spec["late_rise"], "rise", *key, rate)
            turn = _span(0.60, 0.78, "turn", *key, rate)
            low = measured + shortfall
            final = low + rise
            curve = _late_rise(start + shortfall, low, final, turn, CHECKPOINTS)
        total = self.steps(data)
        points = [
            [int(round(total * (index + 1) / CHECKPOINTS)), round(value, 4)]
            for index, value in enumerate(curve)
        ]
        points[-1][0] = total
        points[-1][1] = round(final, 4)
        return {"final_val_loss": round(final, 4), "curve": points}


    def ledger(self) -> list[dict[str, Any]]:
        rows = []
        for run in self.runs:
            reading = self.reading(run)
            rows.append(
                {
                    "run_id": str(run["run_id"]),
                    "date": str(run["date"]),
                    "width": int(run["width"]),
                    "data": int(run["data"]),
                    "learning_rate": float(run["learning_rate"]),
                    "steps": self.steps(int(run["data"])),
                    "final_val_loss": reading["final_val_loss"],
                    "val_shard_id": str(run["val_shard_id"]),
                    "shard_lineage": self.shard_lineage(str(run["val_shard_id"])),
                    "compute_units": self.charge(int(run["width"]), int(run["data"])),
                    "loader_version": str(run["loader_version"]),
                }
            )
        return rows

    def curves(self) -> dict[str, list[list[float]]]:
        return {str(run["run_id"]): self.reading(run)["curve"] for run in self.runs}

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "sweep": self.sweep,
            "target_multiple": int(spec["target_multiple"]),
            "queue": {
                "unit_divisor": int(spec["unit_divisor"]),
                "batch": BATCH,
                "units_granted": int(spec["units_granted"]),
                "job_cap_units": int(spec["job_cap_units"]),
                "job_floor_units": int(spec["job_floor_units"]),
                "reservation_days": int(spec["reservation_days"]),
            },
            "blocks": [dict(entry) for entry in spec["blocks"]],
            "shards": [
                {"val_shard_id": shard, "shard_lineage": str(entry["lineage"])}
                for shard, entry in sorted(spec["shards"].items())
            ],
            "runs": self.ledger(),
            "curves": self.curves(),
            "changes": [dict(entry) for entry in spec["changes"]],
        }


    def largest_units(self) -> int:
        return max(int(row["compute_units"]) for row in self.ledger())

    def target_units(self) -> int:
        return int(self.spec["target_multiple"]) * self.largest_units()

    def target_scale(self) -> float:
        'Width squared times examples at the compute the question is about.'

        return float(self.target_units()) * float(self.spec["unit_divisor"])

    def best_setting(self) -> tuple[float, float]:
        'The width and example count that reach furthest at that compute.'

        spec = self.spec
        a, b = float(spec["a"]), float(spec["b"])
        A, B = float(spec["A"]), float(spec["B"])
        scale = self.target_scale()
        width = math.exp(
            (math.log(a * A / (2.0 * b * B)) + b * math.log(scale)) / (a + 2.0 * b)
        )
        return width, scale / (width * width)

    def truth(self) -> float:
        'The loss reachable at the compute the question is about.'

        width, data = self.best_setting()
        return self.surface(width, data)


    def repeat_groups(self) -> list[list[str]]:
        'Run ids that share a width, an example count and a learning rate.'

        seen: dict[tuple[int, int, float], list[str]] = {}
        for run in self.runs:
            key = (int(run["width"]), int(run["data"]), float(run["learning_rate"]))
            seen.setdefault(key, []).append(str(run["run_id"]))
        return [ids for ids in seen.values() if len(ids) > 1]

    def repeat_spread(self) -> float:
        'The widest distance between two runs of one setting, over the repeats.'

        rows = {str(row["run_id"]): float(row["final_val_loss"]) for row in self.ledger()}
        spreads = [
            max(rows[run_id] for run_id in ids) - min(rows[run_id] for run_id in ids)
            for ids in self.repeat_groups()
        ]
        if not spreads:
            raise ValueError(f"{self.sweep} holds no repeated setting")
        return max(spreads)


    def ratio_band(self) -> tuple[float, float]:
        ratios = [float(row["data"]) / float(row["width"]) for row in self.ledger()]
        return min(ratios), max(ratios)


def _descent(start: float, final: float, count: int) -> list[float]:
    values = []
    for index in range(count):
        t = (index + 1) / count
        values.append(final + (start - final) * (1.0 - t) ** 1.8)
    return values


def _late_rise(start: float, low: float, final: float, turn: float, count: int) -> list[float]:
    values = []
    for index in range(count):
        t = (index + 1) / count
        if t <= turn:
            values.append(low + (start - low) * (1.0 - t / turn) ** 1.8)
        else:
            share = (t - turn) / (1.0 - turn)
            values.append(low + (final - low) * share ** 1.4)
    return values


def build(spec: Mapping[str, Any]) -> World:
    return World(spec=dict(spec))


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    world: World,
    settings: Mapping[str, Any],
    job_id: str,
    sequence: int,
    previous: str = "",
) -> dict[str, Any]:
    'One queue receipt for a job the sweep paid for.'

    width, data = int(settings["width"]), int(settings["data"])
    rate, shard = float(settings["learning_rate"]), str(settings["val_shard"])
    run_id = f"{world.sweep[:2]}-{job_id}"
    reading = world.reading(
        {
            "run_id": run_id,
            "width": width,
            "data": data,
            "learning_rate": rate,
            "val_shard_id": shard,
        }
    )
    body = {
        "sweep": world.sweep,
        "sequence": int(sequence),
        "job_id": str(job_id),
        "run_id": run_id,
        "width": width,
        "data": data,
        "learning_rate": rate,
        "steps": world.steps(data),
        "val_shard_id": shard,
        "shard_lineage": world.shard_lineage(shard),
        "compute_units_charged": world.charge(width, data),
        "observed": reading,
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def empty_stream(world: World) -> dict[str, Any]:
    return {"sweep": world.sweep, "entries": []}


def extend(
    world: World,
    entries: Sequence[Mapping[str, Any]],
    jobs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'The stream with one more job per entry, keeping the chain.'

    grown = [dict(entry) for entry in entries]
    for job in jobs:
        sequence = len(grown) + 1
        label = str(job.get("job_id") or f"job-{sequence:02d}")
        grown.append(
            receipt(world, job, label, sequence, grown[-1]["seal"] if grown else "")
        )
    return grown


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every job this sweep has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the queue receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("sweep") != world.sweep
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the queue receipt file does not belong to this sweep")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a queue receipt is not a service record")
        job_id = entry.get("job_id")
        if not isinstance(job_id, str) or not job_id or job_id in seen:
            raise ValueError("a queue receipt has a missing or repeated job id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the queue receipt order does not hold together")
        if entry.get("sweep") != world.sweep:
            raise ValueError("a queue receipt belongs to another sweep")
        charged = entry.get("compute_units_charged")
        if charged != world.charge(int(entry["width"]), int(entry["data"])):
            raise ValueError("a queue receipt is not billed at the published rate")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a queue receipt does not carry the queue seal")
        seen.add(job_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def units_spent(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["compute_units_charged"]) for entry in entries)


def reservation_days_left(world: World, entries: Sequence[Mapping[str, Any]]) -> int:
    'Reservation days still available after the receipts in ``entries``.'

    return max(0, int(world.spec["reservation_days"]) - len(entries))


def collect(
    workspace: Path,
    world: World,
    width: Any,
    data: Any,
    learning_rate: Any,
    val_shard: Any,
    job_id: Any,
) -> dict[str, Any]:
    'Book one job on the queue and append its receipt, or say why it will not run.'

    if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 120:
        raise ValueError("job_id must be a short non-empty label you choose")
    try:
        width, data = int(width), int(data)
        rate = float(learning_rate)
    except (TypeError, ValueError):
        raise ValueError("width and data must be whole numbers and learning_rate a number")
    shard = str(val_shard or "")
    if shard not in world.spec["shards"]:
        raise ValueError(f"{shard or 'that shard'} is not a validation shard of this sweep")
    if width < WIDTH_MIN or width > WIDTH_MAX or data < DATA_MIN or data > DATA_MAX:
        raise ValueError(
            f"width must be {WIDTH_MIN} to {WIDTH_MAX} and data "
            f"{DATA_MIN} to {DATA_MAX} examples"
        )
    if not 0.0 < rate <= LEARNING_RATE_MAX:
        raise ValueError("learning_rate must sit above 0 and at or under 1")
    cost = world.charge(width, data)
    cap = int(world.spec["job_cap_units"])
    floor_units = int(world.spec["job_floor_units"])
    if cost > cap:
        raise ValueError(
            f"the queue kills any job over {cap} units; that one is charged {cost}"
        )
    if cost < floor_units:
        raise ValueError(
            f"the queue takes no reservation under {floor_units} units; that one is charged {cost}"
        )
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["job_id"] == job_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(entries),
                    "units_left": int(world.spec["units_granted"]) - units_spent(entries),
                    "reservation_days_left": reservation_days_left(world, entries),
                }
        if reservation_days_left(world, entries) <= 0:
            raise ValueError("the sweep has no reservation days left this quarter")
        granted = int(world.spec["units_granted"])
        if units_spent(entries) + cost > granted:
            raise ValueError(
                f"the sweep has {granted - units_spent(entries)} of its {granted} units "
                f"left and that job is charged {cost}"
            )
        made = receipt(
            world,
            {"width": width, "data": data, "learning_rate": rate, "val_shard": shard},
            job_id,
            len(entries) + 1,
            entries[-1]["seal"] if entries else "",
        )
        entries.append(made)
        pending = root / "sweep_receipts.pending"
        pending.write_text(
            json.dumps({"sweep": world.sweep, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": made,
            "ran": True,
            "units_spent": units_spent(entries),
            "units_left": granted - units_spent(entries),
            "reservation_days_left": reservation_days_left(world, entries),
        }
