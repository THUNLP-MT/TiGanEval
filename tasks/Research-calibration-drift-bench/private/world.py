'The wear bench behind the bushing qualification, and the console that runs it.'

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

import numpy as np


RIGS = (1, 2)
SUPPLIERS = ("A", "B")
RECEIPT_FILE = "bench_receipts.json"
PART_RUN = "part"
REFERENCE_RUN = "reference"
QUALIFICATION_CYCLES = 10000


_SEAL_KEY = hashlib.sha256(b"authored-wear-bench-console-2026-09-06").digest()
_LOCK = threading.RLock()


@dataclass(frozen=True)
class Campaign:
    'One qualification campaign: its lots, its bench history and its console.'

    spec: Mapping[str, Any]
    lots: tuple[Mapping[str, Any], ...]
    parts: Mapping[str, Mapping[str, Any]]
    runs: tuple[Mapping[str, Any], ...]


    standing: Mapping[int, tuple[str, float]]

    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    def hours_for(self, kind: str) -> float:
        return float(self.spec["hours"][kind])

    def gain(self, rig: int, hours: float) -> float:
        return 1.0 + float(self.spec["beta"][int(rig)]) * float(hours)

    def fixture(self, rig: int) -> float:
        return float(self.spec["fixture"][int(rig)])

    def true_rate(self, part_id: str) -> float:
        "The part's own wear rate in micrometres per ten thousand cycles."

        part = self.parts[str(part_id)]
        lot = self.lot(str(part["lot"]))
        level = float(self.spec["mu_a"])
        if str(lot["supplier"]) == "B":
            level *= float(self.spec["ratio"])
        return level * math.exp(float(lot["effect"]) + float(part["effect"]))

    def lot(self, lot_id: str) -> Mapping[str, Any]:
        for entry in self.lots:
            if str(entry["lot"]) == str(lot_id):
                return entry
        raise KeyError(lot_id)


    def part_reading(self, part_id: str, rig: int, hours: float, cycles: int,
                     noise: float) -> float:
        depth = self.true_rate(part_id) * (int(cycles) / QUALIFICATION_CYCLES)
        reported = depth * self.fixture(rig) * self.gain(rig, hours) + noise
        return round(float(reported), 3)

    def reference_reading(self, rig: int, hours: float, noise: float) -> float:
        certified = float(self.spec["reference_block_um"])
        return round(float(certified * self.gain(rig, hours) + noise), 3)


    def sessions(self) -> list[dict[str, Any]]:
        "The shop's session table: one row per part session, in run order."

        rows = []
        for entry in self.runs:
            if entry["kind"] != PART_RUN:
                continue
            row = {
                "session": entry["session"],
                "day": entry["day"],
                "rig": entry["rig"],
                "calibration": entry["calibration"],
                "part": entry["part"],
                "lot": entry["lot"],
                "supplier": entry["supplier"],
                "cycles": entry["cycles"],
                "depth_um": entry["reading"],
            }
            if entry["reference_um"] is not None:
                row["reference_um"] = entry["reference_um"]
            rows.append(row)
        return rows

    def calibration_log(self) -> list[dict[str, Any]]:
        'Every calibration the house signed off, per rig, with its date.'

        rows = []
        for rig in RIGS:
            for index, day in enumerate(self.spec["calibration_days"][rig]):
                rows.append({
                    "calibration": _calibration_id(self.spec, rig, index),
                    "rig": rig,
                    "signed_off_day": int(day),
                })
        return sorted(rows, key=lambda row: (row["signed_off_day"], row["rig"]))

    def context(self) -> dict[str, Any]:
        'The machine-readable evidence the shop publishes for this campaign.'

        spec = self.spec
        return {
            "campaign": self.campaign,
            "review_day": int(spec["review_day"]),
            "rigs": [dict(entry) for entry in spec["rigs"]],
            "calibrations": self.calibration_log(),
            "sessions": self.sessions(),
            "lots": [
                {key: entry[key] for key in ("lot", "supplier", "arrived_day", "parts")}
                for entry in self.lots
            ],
            "booking": {
                "bench_hours_left": float(spec["bench_hours_left"]),
                "hours_per_part_session": self.hours_for(PART_RUN),
                "hours_per_reference_run": self.hours_for(REFERENCE_RUN),
                "cycles_per_part_session": QUALIFICATION_CYCLES,
                "rig_hours_available": {
                    str(rig): float(value) for rig, value in spec["rig_hours_available"].items()
                },
            },
            "stores": [dict(entry) for entry in spec["stores"]],
            "quotes": dict(spec["quotes"]),
        }


    def standing_hours(self, rig: int) -> float:
        return float(self.standing[int(rig)][1])

    def standing_calibration(self, rig: int) -> str:
        return str(self.standing[int(rig)][0])

    def store_part(self, part_id: str) -> Mapping[str, Any] | None:
        for entry in self.spec["stores"]:
            if str(entry["part"]) == str(part_id):
                return entry
        return None


def _rng(spec: Mapping[str, Any]) -> np.random.Generator:
    return np.random.default_rng(int(spec["draw"]))


def build(spec: Mapping[str, Any]) -> Campaign:
    'Run one qualification campaign across the two rigs, session by session.'

    rng = _rng(spec)
    lots: list[dict[str, Any]] = []
    parts: dict[str, dict[str, Any]] = {}
    for entry in spec["lots"]:
        effect = float(rng.normal(0.0, float(spec["lot_sd"])))
        lot = dict(entry)
        lot["effect"] = effect
        lot["parts"] = len(entry["rig_plan"])
        lots.append(lot)
        run = len(entry["rig_plan"])
        for index in range(1, run + int(entry.get("spares", 0)) + 1):
            part_id = f"{entry['lot']}-{index:02d}"
            parts[part_id] = {
                "part": part_id,
                "lot": entry["lot"],
                "supplier": entry["supplier"],
                "rig": int(entry["rig_plan"][index - 1]) if index <= run else None,
                "effect": float(rng.normal(0.0, float(spec["part_sd"]))),
            }

    campaign = Campaign(spec=spec, lots=tuple(lots), parts=parts, runs=(), standing={})
    schedule = _schedule(spec, lots)
    days = {rig: list(spec["calibration_days"][rig]) for rig in RIGS}
    used = {rig: 0.0 for rig in RIGS}
    index = {rig: 0 for rig in RIGS}
    runs: list[dict[str, Any]] = []
    coupon_every = int(spec["reference_run_every"])
    for order, item in enumerate(schedule, start=1):
        rig = int(item["rig"])
        while (
            index[rig] + 1 < len(days[rig])
            and int(item["day"]) >= int(days[rig][index[rig] + 1])
        ):
            index[rig] += 1
            used[rig] = 0.0
        calibration = _calibration_id(spec, rig, index[rig])
        reference = None
        if order % coupon_every != 0:
            reference = campaign.reference_reading(
                rig, used[rig], float(rng.normal(0.0, float(spec["reference_noise"])))
            )
            used[rig] += campaign.hours_for(REFERENCE_RUN)
        hours = used[rig]
        reading = campaign.part_reading(
            item["part"], rig, hours, QUALIFICATION_CYCLES,
            float(rng.normal(0.0, float(spec["noise_sd"]))),
        )
        used[rig] += campaign.hours_for(PART_RUN)
        part = parts[item["part"]]
        runs.append({
            "session": f"S-{order:03d}",
            "kind": PART_RUN,
            "day": int(item["day"]),
            "rig": rig,
            "calibration": calibration,
            "part": item["part"],
            "lot": part["lot"],
            "supplier": part["supplier"],
            "cycles": QUALIFICATION_CYCLES,
            "hours_since_calibration": float(hours),
            "reading": reading,
            "reference_um": reference,
        })
    standing = {rig: (_calibration_id(spec, rig, index[rig]), used[rig]) for rig in RIGS}
    return Campaign(
        spec=spec, lots=tuple(lots), parts=parts, runs=tuple(runs), standing=standing
    )


def _calibration_id(spec: Mapping[str, Any], rig: int, index: int) -> str:
    return f"C{int(rig)}-{index + 1:02d}"


def _schedule(spec: Mapping[str, Any], lots: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every part session of the campaign in the order the bench ran it.'

    items: list[dict[str, Any]] = []
    for lot in sorted(lots, key=lambda entry: (int(entry["arrived_day"]), str(entry["lot"]))):
        day = int(lot["arrived_day"])
        for index, rig in enumerate(lot["rig_plan"], start=1):
            items.append({
                "part": f"{lot['lot']}-{index:02d}",
                "rig": int(rig),
                "day": day + (index - 1) // 2,
            })
    return items


def _new_run_hours(campaign: Campaign, entries: Sequence[Mapping[str, Any]], rig: int) -> float:
    'Bench-hours that rig has run under its standing calibration.'

    hours = campaign.standing_hours(rig)
    for entry in entries:
        if int(entry["rig"]) == int(rig):
            hours += float(entry["hours"])
    return hours


def _noise(campaign: Campaign, label: str, sd: float) -> float:
    digest = hashlib.sha256(f"{campaign.campaign}:{label}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return float(np.sqrt(2.0) * sd * _erfinv(2.0 * value - 1.0))


def _erfinv(value: float) -> float:
    "Inverse error function, good enough for a bench reading's noise term."

    a = 0.147
    ln = math.log(max(1e-12, 1.0 - value * value))
    first = 2.0 / (math.pi * a) + ln / 2.0
    return math.copysign(math.sqrt(max(0.0, math.sqrt(first * first - ln / a) - first)), value)


def run_session(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    rig: Any,
    part: Any,
    reference_block: Any,
    cycles: Any,
) -> dict[str, Any]:
    'One session on the bench, as the console would run it now.'

    rig = int(rig) if str(rig).strip() in {"1", "2"} else None
    if rig not in RIGS:
        raise ValueError("rig must be 1 or 2")
    wants_reference = bool(reference_block)
    part_id = str(part).strip() if isinstance(part, str) and part.strip() else None
    if wants_reference and part_id:
        raise ValueError("a session runs either a part or the reference block, not both")
    if not wants_reference and not part_id:
        raise ValueError("name a part from stores, or ask for the reference block")
    cycles = QUALIFICATION_CYCLES if cycles in (None, "") else cycles
    kind = REFERENCE_RUN if wants_reference else PART_RUN
    hours = campaign.hours_for(kind)
    spent = sum(float(entry["hours"]) for entry in entries)
    left = float(campaign.spec["bench_hours_left"]) - spent
    if hours > left + 1e-9:
        raise ValueError(
            f"the campaign has {left:g} bench-hours left before the review and that "
            f"session needs {hours:g}"
        )
    rig_spent = sum(float(entry["hours"]) for entry in entries if int(entry["rig"]) == rig)
    rig_left = float(campaign.spec["rig_hours_available"][rig]) - rig_spent
    if hours > rig_left + 1e-9:
        raise ValueError(
            f"rig {rig} has {rig_left:g} bench-hours open before the review and that "
            f"session needs {hours:g}"
        )
    at = _new_run_hours(campaign, entries, rig)
    label = f"{kind}:{rig}:{part_id or 'block'}:{len(entries)}"
    if wants_reference:
        reading = campaign.reference_reading(
            rig, at, _noise(campaign, label, float(campaign.spec["reference_noise"]))
        )
        observed = {"kind": REFERENCE_RUN, "reading_um": reading}
        body: dict[str, Any] = {"part": None, "lot": None, "supplier": None, "cycles": 0}
    else:
        if int(cycles) != QUALIFICATION_CYCLES:
            raise ValueError(
                f"the qualification block is {QUALIFICATION_CYCLES} cycles; the console "
                "will not run a part for anything else"
            )
        stored = campaign.store_part(part_id)
        if stored is None:
            raise ValueError(f"{part_id} is not a part this campaign holds in stores")
        used = [entry for entry in entries if entry.get("part") == part_id]
        if used:
            raise ValueError(f"{part_id} has already been run; a part is worn once")
        reading = campaign.part_reading(
            part_id, rig, at, QUALIFICATION_CYCLES,
            _noise(campaign, label, float(campaign.spec["noise_sd"])),
        )
        observed = {"kind": PART_RUN, "reading_um": reading}
        body = {
            "part": part_id,
            "lot": str(stored["lot"]),
            "supplier": str(stored["supplier"]),
            "cycles": QUALIFICATION_CYCLES,
        }
    body.update({
        "rig": rig,
        "calibration": campaign.standing_calibration(rig),
        "fixture": str(campaign.spec["rigs"][rig - 1]["fixture"]),
        "hours": hours,
        "observed": observed,
    })
    return body


def store_parts(campaign: Campaign) -> list[str]:
    return [str(entry["part"]) for entry in campaign.spec["stores"]]


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    campaign: Campaign,
    body: Mapping[str, Any],
    run_id: str,
    sequence: int,
    previous: str = "",
) -> dict[str, Any]:
    value = {
        "campaign": campaign.campaign,
        "sequence": int(sequence),
        "run_id": str(run_id),
        "previous": str(previous),
        **{key: body[key] for key in sorted(body)},
    }
    return dict(value, seal=_seal(value))


def empty_stream(campaign: Campaign) -> dict[str, Any]:
    return {"campaign": campaign.campaign, "entries": []}


def extend(
    campaign: Campaign,
    entries: Sequence[Mapping[str, Any]],
    bookings: Sequence[Mapping[str, Any]],
    ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    'The stream with one more session per booking, keeping the chain.'

    grown = [dict(entry) for entry in entries]
    for offset, booking in enumerate(bookings):
        body = run_session(
            campaign,
            grown,
            booking.get("rig"),
            booking.get("part"),
            booking.get("reference_block"),
            booking.get("cycles"),
        )
        sequence = len(grown) + 1
        label = ids[offset] if ids is not None else f"run-{sequence:02d}"
        grown.append(
            receipt(campaign, body, label, sequence, grown[-1]["seal"] if grown else "")
        )
    return grown


def stream_with(
    campaign: Campaign,
    bookings: Sequence[Mapping[str, Any]],
    ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {"campaign": campaign.campaign, "entries": extend(campaign, [], bookings, ids)}


def read_receipts(workspace: Path, campaign: Campaign) -> list[dict[str, Any]]:
    'Every session this campaign has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the bench receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("campaign") != campaign.campaign
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the bench receipt file does not belong to this campaign")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a bench receipt is not a console record")
        run_id = entry.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id in seen:
            raise ValueError("a bench receipt has a missing or repeated run id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the bench receipt order does not hold together")
        if entry.get("campaign") != campaign.campaign:
            raise ValueError("a bench receipt belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a bench receipt does not carry the console seal")
        seen.add(run_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def hours_spent(entries: Sequence[Mapping[str, Any]]) -> float:
    return float(sum(float(entry["hours"]) for entry in entries))


def hours_left(campaign: Campaign, entries: Sequence[Mapping[str, Any]]) -> float:
    return float(campaign.spec["bench_hours_left"]) - hours_spent(entries)


def rig_hours_left(
    campaign: Campaign, entries: Sequence[Mapping[str, Any]], rig: int
) -> float:
    spent = sum(float(entry["hours"]) for entry in entries if int(entry["rig"]) == int(rig))
    return float(campaign.spec["rig_hours_available"][int(rig)]) - spent


def collect(
    workspace: Path,
    campaign: Campaign,
    rig: Any,
    part: Any,
    reference_block: Any,
    cycles: Any,
    run_id: Any,
) -> dict[str, Any]:
    'Run one session on the bench and append its receipt, or say why not.'

    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 120:
        raise ValueError("run_id must be a short non-empty label you choose")
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, campaign)
        for entry in entries:
            if entry["run_id"] == run_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "hours_spent": hours_spent(entries),
                    "hours_left": hours_left(campaign, entries),
                }
        body = run_session(campaign, entries, rig, part, reference_block, cycles)
        made = receipt(
            campaign, body, run_id, len(entries) + 1, entries[-1]["seal"] if entries else ""
        )
        entries.append(made)
        pending = root / "bench_receipts.pending"
        pending.write_text(
            json.dumps({"campaign": campaign.campaign, "entries": entries},
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": made,
            "ran": True,
            "hours_spent": hours_spent(entries),
            "hours_left": hours_left(campaign, entries),
        }
