'The training campaign behind the ranking release, and the evaluation desk.'

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from math import exp
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


_SEAL_KEY = hashlib.sha256(b"authored-ranking-eval-desk-2026-09-07").digest()
_LOCK = threading.RLock()

RECEIPT_FILE = "ledger/receipts.jsonl"


ARRANGEMENTS = ("as run", "assignment", "turn")


def arrangement_note(arrangement: str) -> str:
    if arrangement == "assignment":
        return "the same runs, with the groups against the lots they were freed onto"
    if arrangement == "turn":
        return "the same runs, with the long warm-up turning where it turned"
    return "the campaign as its records stand"


def _fraction(*parts: Any) -> float:
    'A repeatable number in [-1, 1) from a label.'

    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 63) - 1.0


def _draw(*parts: Any) -> float:
    'A repeatable draw of unit spread, roughly bell shaped.'

    return _fraction("a", *parts) + _fraction("b", *parts) + _fraction("c", *parts)


_CENTRED: dict[tuple[Any, ...], tuple[float, ...]] = {}


def _centred(count: int, spread: float, *parts: Any) -> tuple[float, ...]:
    '`count` draws of the given spread that add to nought.'

    key = (count, spread, *parts)
    held = _CENTRED.get(key)
    if held is not None:
        return held
    raw = [_draw(*parts, index) for index in range(count)]
    middle = sum(raw) / count
    scale = spread * (count / (count - 1)) ** 0.5 if count > 1 else 0.0
    drawn = tuple(scale * (value - middle) for value in raw)
    _CENTRED[key] = drawn
    return drawn


_TABLES: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

PRODUCTION_KIND = "model"
CHECKPOINT_KIND = "checkpoint"


@dataclass(frozen=True)
class Campaign:
    'One training campaign, its evaluation lots and its release candidate.'

    spec: Mapping[str, Any]


    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def label(self) -> str:
        return str(self.spec["label"])

    @property
    def slices(self) -> int:
        return int(self.spec["slices"])

    @property
    def production_id(self) -> str:
        return str(self.spec["production"]["model_id"])

    def runs(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.spec["runs"])

    def run(self, run_id: str) -> Mapping[str, Any] | None:
        for entry in self.runs():
            if str(entry["run_id"]) == str(run_id):
                return entry
        return None

    def steps(self) -> tuple[int, ...]:
        return tuple(int(step) for step in self.spec["checkpoint_steps"])

    def checkpoint_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{entry['run_id']}@{step}" for entry in self.runs() for step in self.steps()
        )


    def lots(self) -> tuple[str, ...]:
        return tuple(self.spec["open_lots"])

    def lot_of(self, run_id: str, arrangement: str = "as run") -> str:
        entry = self.run(run_id)
        if entry is None:
            raise KeyError(run_id)
        table = (
            self.spec["swapped_groups"] if arrangement == "assignment" else self.spec["groups"]
        )
        return str(table[int(entry["group"])])

    def amount(self, lot: str, arrangement: str = "as run") -> float:
        return float(self.spec["lot_amount"][str(lot)])

    def turn_step(self, run_id: str, arrangement: str = "as run") -> int | None:
        table = (
            self.spec["moved_turn_steps"] if arrangement == "turn" else self.spec["turn_steps"]
        )
        value = table.get(str(run_id))
        return None if value is None else int(value)


    def quality(self, item: str, arrangement: str = "as run") -> float | None:
        "The item's own worth, with no lot and no slice in it."

        item = str(item)
        if item == self.production_id:
            return float(self.spec["production"]["quality"])
        if "@" not in item:
            return None
        run_id, _, raw_step = item.partition("@")
        entry = self.run(run_id)
        if entry is None or not raw_step.isdigit():
            return None
        step = int(raw_step)
        if step not in self.steps():
            return None
        value = float(entry["ceiling"]) - float(entry["amplitude"]) * exp(
            -step / float(entry["tau"])
        )
        turn = self.turn_step(run_id, arrangement)
        if turn is not None and step > turn:
            value -= float(entry["turn_rate"]) * (step - turn) / 1000.0
        return value

    def holdout_loss(self, run_id: str, step: int) -> float:
        "What the trainer's own held-back split printed at this step."

        entry = self.run(run_id)
        if entry is None:
            raise KeyError(run_id)
        gap = float(entry["ceiling"]) - float(self.quality(f"{run_id}@{step}") or 0.0)
        wobble = 0.0009 * _draw(self.campaign, "curve", run_id, step)
        return float(entry["loss_offset"]) + 11.5 * gap + wobble

    def train_loss(self, run_id: str, step: int) -> float:
        entry = self.run(run_id)
        if entry is None:
            raise KeyError(run_id)
        base = float(entry["loss_offset"]) - 0.06
        return base + 1.35 * exp(-step / (0.85 * float(entry["tau"]))) + 0.0011 * _draw(
            self.campaign, "train", run_id, step
        )


    def slice_effect(self, lot: str, index: int, arrangement: str = "as run") -> float:
        'What this slice of this lot adds to every item read on it.'

        values = _centred(
            self.slices, float(self.spec["slice_sd"]), self.campaign, "slice", str(lot)
        )
        return values[int(index) % self.slices]

    def read_noise(self, item: str, lot: str, index: int) -> float:
        "The item's own luck on this slice; it adds to nought over the lot."

        values = _centred(
            self.slices, float(self.spec["read_sd"]), self.campaign, "luck", str(lot), str(item)
        )
        return values[int(index) % self.slices]

    def read(
        self, item: str, lot: str, index: int, arrangement: str = "as run"
    ) -> float | None:
        'One score, the way the desk writes it down.'

        worth = self.quality(item, arrangement)
        if worth is None:
            return None
        value = (
            worth
            + self.amount(lot, arrangement)
            + self.slice_effect(lot, index, arrangement)
            + self.read_noise(item, lot, index)
        )
        return round(value, 4)


    def _pipeline_slice(self, run_id: str, step: int) -> int:
        return int(
            hashlib.sha256(
                f"{self.campaign}|auto|{run_id}|{step}".encode("utf-8")
            ).hexdigest()[:4],
            16,
        ) % self.slices

    def ledger_rows(self, arrangement: str = "as run") -> list[dict[str, Any]]:
        'One row per automatic evaluation, the way the pipeline exports them.'

        key = (self.campaign, "ledger", arrangement)
        held = _TABLES.get(key)
        if held is not None:
            return held
        rows: list[dict[str, Any]] = []
        for entry in self.runs():
            run_id = str(entry["run_id"])
            lot = self.lot_of(run_id, arrangement)
            for step in self.steps():
                index = self._pipeline_slice(run_id, step)
                rows.append(
                    {
                        "run_id": run_id,
                        "init_id": str(entry["init_id"]),
                        "warmup": str(entry["warmup"]),
                        "checkpoint_step": int(step),
                        "val_score": self.read(f"{run_id}@{step}", lot, index, arrangement),
                        "val_lot": lot,
                        "val_rows": int(self.spec["slice_rows"]),
                        "compute_units": int(entry["compute_units"]),
                        "trainer_version": str(entry["trainer_version"]),
                    }
                )
        _TABLES[key] = rows
        return rows

    def curve_rows(self, run_id: str) -> list[dict[str, Any]]:
        key = (self.campaign, "curve", str(run_id))
        held = _TABLES.get(key)
        if held is not None:
            return held
        _TABLES[key] = [
            {
                "step": int(step),
                "tokens_seen_m": int(step * 41),
                "train_loss": round(self.train_loss(run_id, step), 4),
                "holdout_loss": round(self.holdout_loss(run_id, step), 4),
            }
            for step in self.steps()
        ]
        return _TABLES[key]


    def on_disk(self, item: str) -> bool:
        item = str(item)
        if item == self.production_id:
            return True
        if item not in set(self.checkpoint_ids()):
            return False
        return item not in set(self.spec["pruned"])

    def registry_rows(self) -> list[dict[str, Any]]:
        key = (self.campaign, "registry", "")
        held = _TABLES.get(key)
        if held is not None:
            return held
        pruned = set(self.spec["pruned"])
        rows = []
        for entry in self.runs():
            run_id = str(entry["run_id"])
            for step in self.steps():
                item = f"{run_id}@{step}"
                rows.append(
                    {
                        "checkpoint_id": item,
                        "run_id": run_id,
                        "checkpoint_step": int(step),
                        "size_gb": 3.4,
                        "on_disk": "no" if item in pruned else "yes",
                        "pruned_on": str(self.spec["prune_date"]) if item in pruned else "",
                    }
                )
        _TABLES[key] = rows
        return rows


    def release_score(self) -> float:
        'The figure the release note stores: one read of the released model.'

        release = self.spec["production"]
        value = self.read(
            str(release["model_id"]),
            str(release["release_lot"]),
            int(release["release_slice"]),
        )
        return float(value or 0.0)

    def context(self, arrangement: str = "as run") -> dict[str, Any]:
        spec = self.spec
        release = dict(spec["production"])
        return {
            "campaign": self.campaign,
            "label": self.label,
            "as_of": str(spec["as_of"]),
            "release": {
                "model_id": str(release["model_id"]),
                "stored_val_score": self.release_score(),
                "measured_on": str(release["release_date"]),
                "measured_lot": str(release["release_lot"]),
            },
            "lots": {
                "open": list(self.lots()),
                "retired": list(spec["retired_lots"]),
                "rows_per_read": int(spec["slice_rows"]),
                "reads_per_lot": int(spec["slices"]),
            },
            "compute": {
                "units_granted": int(spec["units_granted"]),
                "reserved_units": int(spec["reserve"]),
                "job_cap_units": int(spec["job_cap"]),
                "price_per_read": int(spec["read_price"]),
                "price_per_training_run": int(spec["train_price"]),
                "refused_job_fee": int(spec["refusal_fee"]),
            },
            "review": {
                "range_ask_points": float(spec["range_ask_points"]),
                "due": str(spec["review_due"]),
            },
            "run_ledger": self.ledger_rows(arrangement),
            "checkpoint_registry": self.registry_rows(),
            "curves": {
                str(entry["run_id"]): self.curve_rows(str(entry["run_id"]))
                for entry in self.runs()
            },
        }


def build(spec: Mapping[str, Any]) -> Campaign:
    return Campaign(spec=spec)


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def sealed(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def units_spent(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["units_charged"]) for entry in entries)


def units_left(campaign: Campaign, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(campaign.spec["units_granted"]) - units_spent(entries)


def usable_units(campaign: Campaign, entries: Sequence[Mapping[str, Any]]) -> int:
    return units_left(campaign, entries) - int(campaign.spec["reserve"])


def slices_used(entries: Sequence[Mapping[str, Any]], lot: str) -> int:
    'How many slices of this lot the desk has already handed out.'

    return sum(
        int(entry.get("repeats", 0))
        for entry in entries
        if str(entry.get("lot")) == str(lot) and not entry.get("refusal")
    )


def read_request(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    lot: str,
    items: Sequence[str],
    repeats: int,
    arrangement: str = "as run",
) -> list[dict[str, Any]]:
    'The rows one accepted reads job hands back, slice by slice.'

    start = slices_used(entries, lot)
    rows: list[dict[str, Any]] = []
    for offset in range(int(repeats)):
        index = (start + offset) % campaign.slices
        for item in items:
            rows.append(
                {
                    "item": str(item),
                    "kind": PRODUCTION_KIND
                    if str(item) == campaign.production_id
                    else CHECKPOINT_KIND,
                    "lot": str(lot),
                    "slice_no": index + 1,
                    "val_rows": int(campaign.spec["slice_rows"]),
                    "val_score": campaign.read(str(item), str(lot), index, arrangement),
                }
            )
    return rows


def refusal_for(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    kind: str,
    lot: Any,
    items: Sequence[str],
    repeats: Any,
) -> str | None:
    'Why the desk would hand a job back without running it.'

    spec = campaign.spec
    if kind == "train":


        return (
            f"a training run costs {int(spec['train_price'])} units and is billed to the "
            "training grant, not to this evaluation grant"
        )
    if str(lot) not in campaign.lots():
        return f"{lot} is not a lot the desk can score on"
    if not items:
        return "a reads job has to name at least one item"
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats <= 0:
        return "a reads job has to name a whole positive number of reads an item"
    if repeats > campaign.slices:
        return f"the lot holds {campaign.slices} slices and the job asks for {repeats}"
    missing = [item for item in items if not campaign.on_disk(item)]
    if missing:
        return f"{missing[0]} is not on disk"
    cost = int(spec["read_price"]) * len(items) * int(repeats)
    if cost > int(spec["job_cap"]):
        return f"the job costs {cost} units and no job may go over {spec['job_cap']}"
    if cost > usable_units(campaign, entries):
        return (
            f"the job costs {cost} units and {usable_units(campaign, entries)} are free of "
            "the release reserve"
        )


    used = slices_used(entries, str(lot))
    if used + int(repeats) > campaign.slices:
        return (
            f"the desk has served {used} of the {campaign.slices} slices of {lot} and the "
            f"job asks for {repeats} more"
        )
    return None


def receipt_body(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    job_id: str,
    kind: str,
    lot: Any,
    items: Sequence[str],
    repeats: Any,
    arrangement: str = "as run",
) -> dict[str, Any]:
    spec = campaign.spec
    refusal = refusal_for(campaign, entries, kind, lot, items, repeats)
    if refusal is not None:
        charged = int(spec["refusal_fee"])
        rows: list[dict[str, Any]] = []
        served = 0
    else:
        rows = read_request(campaign, entries, str(lot), items, int(repeats), arrangement)
        charged = int(spec["read_price"]) * len(rows)
        served = len(rows)
    body = {
        "job_id": str(job_id),
        "campaign": campaign.campaign,
        "kind": str(kind),
        "lot": None if kind == "train" else str(lot),
        "items": [str(item) for item in items],
        "repeats": 0 if refusal is not None or kind == "train" else int(repeats),
        "reads_returned": served,
        "units_charged": charged,
        "refusal": refusal,
        "rows": rows,
    }
    body["units_left_after"] = int(spec["units_granted"]) - units_spent(entries) - charged
    return body


def extend(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    job_id: str,
    kind: str,
    lot: Any,
    items: Sequence[str],
    repeats: Any,
    arrangement: str = "as run",
) -> list[dict[str, Any]]:
    'The receipt stream with one more job on it, without touching any file.'

    grown = [dict(entry) for entry in entries]
    body = receipt_body(campaign, grown, job_id, kind, lot, items, repeats, arrangement)
    grown.append(sealed(body, len(grown) + 1, grown[-1]["seal"] if grown else ""))
    return grown


def replay_stream(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    arrangement: str,
) -> list[dict[str, Any]]:
    'The same jobs, put through the desk under another arrangement.'

    grown: list[dict[str, Any]] = []
    for entry in entries:
        grown = extend(
            campaign,
            grown,
            str(entry["job_id"]),
            str(entry["kind"]),
            entry.get("lot"),
            [str(item) for item in entry.get("items", ())],
            int(entry.get("repeats") or 0) or 1,
            arrangement,
        )
    return grown


def stream_document(entries: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(dict(entry), sort_keys=True, ensure_ascii=False) + "\n" for entry in entries
    )


def read_receipts(workspace: Path, campaign: Campaign) -> list[dict[str, Any]]:
    'Every job this campaign has paid for, or a reason the stream will not read.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the receipt stream must not be a symlink")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError(f"line {number} of the receipt stream is not a desk record")
        job_id = raw.get("job_id")
        if not isinstance(job_id, str) or not job_id or job_id in seen:
            raise ValueError("a receipt has a missing or repeated job id")
        if raw.get("campaign") != campaign.campaign:
            raise ValueError("a receipt belongs to another campaign")
        if raw.get("sequence") != len(entries) + 1 or raw.get("previous") != previous:
            raise ValueError("the receipts are not in the order the desk wrote them")
        signature = raw.get("seal")
        body = {key: value for key, value in raw.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a receipt does not carry the evaluation desk's seal")
        seen.add(job_id)
        previous = str(signature)
        entries.append(dict(raw))
    return entries


def collect(
    workspace: Path,
    campaign: Campaign,
    job_id: Any,
    kind: Any,
    lot: Any,
    items: Any,
    repeats: Any,
) -> dict[str, Any]:
    'Put one job through the desk and append its sealed receipt.'

    kind = str(kind or "reads")
    if kind not in ("reads", "train"):
        raise ValueError("kind must be reads or train")
    if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 120:
        raise ValueError("job_id must be a short non-empty label you choose")
    if kind == "reads":
        if not isinstance(items, (list, tuple)) or not items:
            raise ValueError("a reads job needs a list of items")
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError("every item is a checkpoint id or the released model id")
        if len(set(items)) != len(items):
            raise ValueError("a reads job names each item once")
        if repeats is None:
            repeats = 1
        if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats <= 0:
            raise ValueError("repeats must be a whole positive number of reads an item")
        names = [str(item).strip() for item in items]
    else:
        names = [str(item).strip() for item in (items or ())]
        repeats = 0

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, campaign)
        for entry in entries:
            if entry["job_id"] == job_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(entries),
                    "units_left": units_left(campaign, entries),
                }
        body = receipt_body(campaign, entries, job_id, kind, lot, names, repeats)
        entries.append(sealed(body, len(entries) + 1, entries[-1]["seal"] if entries else ""))
        pending = root / (RECEIPT_FILE + ".pending")
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(stream_document(entries), encoding="utf-8")
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "units_spent": units_spent(entries),
            "units_left": units_left(campaign, entries),
        }
