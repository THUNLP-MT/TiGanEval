'The rig as an instrument: it runs a booked day and seals its receipt.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from . import world as w


_SEAL_KEY = hashlib.sha256(b"thermal-bench-rig-plate-screen-2026-09-06").digest()
_LOCK = threading.RLock()

RECEIPT_FILE = "bench_receipts.json"


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def _sheet(raw: Any) -> list[dict[str, Any]]:
    'One day sheet, as the booking desk accepts it.'

    if isinstance(raw, Mapping):
        raw = raw.get("day", raw.get("parts", raw.get("runs")))
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("a day sheet is a list of {part, runs} entries")
    read: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("every entry of a day sheet needs a part and a run count")
        part = item.get("part", item.get("plate_id"))
        runs = item.get("runs", item.get("run_count"))
        if not isinstance(part, str) or not part.strip():
            raise ValueError("every entry of a day sheet needs a part")
        if isinstance(runs, bool) or not isinstance(runs, int) or runs <= 0:
            raise ValueError("every entry of a day sheet needs a whole positive run count")
        read.append({"part": part.strip(), "runs": int(runs)})
    if len({item["part"] for item in read}) != len(read):
        raise ValueError("a day sheet names each part once")
    return read


def receipt_body(
    world: w.World,
    day: str,
    sheet: Sequence[Mapping[str, Any]],
    receipt_id: str,
    days_left_after: int,
    arrangement: str = "as run",
) -> dict[str, Any]:
    outcome = world.run_day(day, sheet, arrangement)
    return {
        "campaign": world.campaign,
        "receipt_id": str(receipt_id),
        "day_id": outcome["day_id"],
        "coolant_setpoint_C": outcome["coolant_setpoint_C"],
        "ambient_C": outcome["ambient_C"],
        "rig_hours_charged": outcome["rig_hours_charged"],
        "rig_days_left_after": int(days_left_after),
        "refusal": outcome["refusal"],
        "parts": outcome["parts"],
    }


def sealed(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def days_left(world: w.World, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(world.spec["rig_days_on_the_sheet"]) - len(entries)


def extend(
    world: w.World,
    entries: Sequence[Mapping[str, Any]],
    sheets: Sequence[Sequence[Mapping[str, Any]]],
    ids: Sequence[str] | None = None,
    arrangement: str = "as run",
) -> list[dict[str, Any]]:
    'The stream after one more booked day per sheet, keeping the chain.'

    grown = [dict(entry) for entry in entries]
    for offset, sheet in enumerate(sheets):
        index = len(grown)
        if index >= len(world.open_days):
            raise ValueError(f"{world.campaign} has no rig day {index + 1} on the sheet")
        label = ids[offset] if ids is not None else f"day-{index + 1:02d}"
        body = receipt_body(
            world,
            world.open_days[index],
            _sheet(list(sheet)),
            label,
            days_left(world, grown) - 1,
            arrangement,
        )
        grown.append(sealed(body, index + 1, grown[-1]["seal"] if grown else ""))
    return grown


def stream(
    world: w.World,
    sheets: Sequence[Sequence[Mapping[str, Any]]],
    ids: Sequence[str] | None = None,
    arrangement: str = "as run",
) -> dict[str, Any]:
    return {
        "campaign": world.campaign,
        "entries": extend(world, [], sheets, ids, arrangement),
    }


def requests_of(entries: Sequence[Mapping[str, Any]]) -> list[list[dict[str, Any]]]:
    'The day sheets behind a stream, so the same days can be run elsewhere.'

    return [
        [
            {"part": str(part["part"]), "runs": int(part["requested_runs"])}
            for part in entry["parts"]
        ]
        for entry in entries
    ]


def read_receipts(workspace: str | Path, world: w.World) -> list[dict[str, Any]]:
    'Every rig day this review has been charged for, or why the stream is broken.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("campaign") != world.campaign
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the receipt file does not belong to this campaign")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a receipt is not a rig record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the receipts are not in the order the rig wrote them")
        if entry.get("campaign") != world.campaign:
            raise ValueError("a receipt belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a receipt does not carry the rig's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def collect(
    workspace: str | Path, world: w.World, sheet: Any, booking_id: Any
) -> dict[str, Any]:
    'Put one day sheet on the rig, or say why the desk will not take it.'

    if not isinstance(booking_id, str) or not booking_id.strip() or len(booking_id) > 120:
        raise ValueError("booking_id must be a short non-empty label you choose")
    booking_id = booking_id.strip()
    read = _sheet(sheet)
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["receipt_id"] == booking_id:
                held = [
                    {"part": str(part["part"]), "runs": int(part["requested_runs"])}
                    for part in entry["parts"]
                ]
                if held != read:
                    raise ValueError("that booking id already names another day sheet")
                return {
                    "receipt": entry,
                    "ran": False,
                    "rig_days_spent": len(entries),
                    "rig_days_left": days_left(world, entries),
                }
        left = days_left(world, entries)
        if left <= 0:
            raise ValueError(
                f"the sheet has no rig days left; all "
                f"{int(world.spec['rig_days_on_the_sheet'])} are spent"
            )
        body = receipt_body(
            world, world.open_days[len(entries)], read, booking_id, left - 1
        )
        entries.append(sealed(body, len(entries) + 1, entries[-1]["seal"] if entries else ""))
        pending = root / (RECEIPT_FILE + ".pending")
        pending.write_text(
            json.dumps({"campaign": world.campaign, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "rig_days_spent": len(entries),
            "rig_days_left": days_left(world, entries),
        }
