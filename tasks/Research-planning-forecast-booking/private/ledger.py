'The settlement ledger: what the carrier billed the desk, sealed line by line.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from . import world as w
from .world import AREAS, WINDOWS


_SEAL_KEY = hashlib.sha256(b"dispatch-desk-settlement-meter-2026-09-07").digest()
_LOCK = threading.RLock()

RECEIPT_FILE = Path("ledger") / "receipts.jsonl"


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def sealed(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def read_order(raw: Any) -> dict[tuple[str, str], int]:
    'One order as the desk accepts it: a van count per area and window.'

    if isinstance(raw, Mapping):
        raw = raw.get("booking", raw.get("order", raw.get("vans")))
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("an order is a list of {area, window, vans} entries")
    order: dict[tuple[str, str], int] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("every line of an order needs an area, a window and a van count")
        area = item.get("area")
        window = item.get("window")
        vans = item.get("vans", item.get("van_count"))
        if area not in AREAS:
            raise ValueError(f"{area!r} is not one of the desk's areas")
        if window not in WINDOWS:
            raise ValueError(f"{window!r} is not one of the shift's windows")
        if isinstance(vans, bool) or not isinstance(vans, int):
            raise ValueError("every line of an order needs a whole van count")
        if (area, window) in order:
            raise ValueError(f"{area} {window} is on the order twice")
        order[(str(area), str(window))] = int(vans)
    return order


def allowance_left(world: w.World, entries: Sequence[Mapping[str, Any]]) -> int:
    spent = sum(float(entry["van_hours_charged"]) for entry in entries)
    return int(round(world.allowance_total - spent))


def booked_shifts(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(entry["shift_id"]) for entry in entries if not entry.get("refusal")]


def next_open_shift(world: w.World, entries: Sequence[Mapping[str, Any]]) -> str | None:
    done = set(booked_shifts(entries))
    for shift in world.shifts:
        if shift not in done:
            return shift
    return None


def receipt_body(
    world: w.World,
    order_id: str,
    shift: str | None,
    order: Mapping[tuple[str, str], int],
    entries: Sequence[Mapping[str, Any]],
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> dict[str, Any]:
    left = allowance_left(world, entries)
    refusal = world.refusal(shift, order, left, booked_shifts(entries))
    if refusal is not None:
        charge = float(world.desk_fee)
        return {
            "campaign": world.campaign,
            "order_id": str(order_id),
            "shift_id": str(shift),
            "lines": [
                {
                    "area": area,
                    "window": window,
                    "vans_booked": int(order.get((area, window), 0)),
                    "drops_metered": None,
                }
                for area in AREAS
                for window in WINDOWS
            ],
            "vans_idle": 0,
            "windows_short": 0,
            "vans_short": 0,
            "spill_charge": 0.0,
            "van_hours_charged": charge,
            "allowance_left_after": int(round(left - charge)),
            "refusal": refusal,
        }
    outcome = world.run_shift(str(shift), order, arrangement, moved_to)
    charge = float(outcome["van_hours_charged"])
    return {
        "campaign": world.campaign,
        "order_id": str(order_id),
        "shift_id": outcome["shift_id"],
        "lines": [
            {
                "area": line["area"],
                "window": line["window"],
                "vans_booked": line["vans_booked"],
                "drops_metered": line["drops_metered"],
            }
            for line in outcome["lines"]
        ],
        "vans_idle": int(outcome["vans_idle"]),
        "windows_short": int(outcome["windows_short"]),
        "vans_short": int(outcome["vans_short"]),
        "spill_charge": float(outcome["spill_charge"]),
        "van_hours_charged": charge,
        "allowance_left_after": int(round(left - charge)),
        "refusal": None,
    }


def extend(
    world: w.World,
    entries: Sequence[Mapping[str, Any]],
    orders: Sequence[tuple[str, str | None, Mapping[tuple[str, str], int]]],
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> list[dict[str, Any]]:
    'The ledger after one more order per entry, keeping the chain.'

    grown = [dict(entry) for entry in entries]
    for order_id, shift, order in orders:
        body = receipt_body(world, order_id, shift, order, grown, arrangement, moved_to)
        grown.append(sealed(body, len(grown) + 1, grown[-1]["seal"] if grown else ""))
    return grown


def replay(
    world: w.World,
    orders: Sequence[tuple[str, str | None, Mapping[tuple[str, str], int]]],
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> list[dict[str, Any]]:
    return extend(world, [], orders, arrangement, moved_to)


def orders_of(
    entries: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str | None, dict[tuple[str, str], int]]]:
    'The orders behind a ledger, so the same shifts can be run elsewhere.'

    orders = []
    for entry in entries:
        order = {
            (str(line["area"]), str(line["window"])): int(line["vans_booked"])
            for line in entry["lines"]
        }
        orders.append((str(entry["order_id"]), str(entry["shift_id"]), order))
    return orders


def dump(campaign: str, entries: Sequence[Mapping[str, Any]]) -> str:
    header = {"campaign": str(campaign), "record": "settlement ledger"}
    lines = [json.dumps(header, sort_keys=True)]
    lines.extend(json.dumps(entry, sort_keys=True) for entry in entries)
    return "\n".join(lines) + "\n"


def read_receipts(workspace: str | Path, world: w.World) -> list[dict[str, Any]]:
    'Every shift this desk has been charged for, or why the ledger will not read.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the ledger must not be a symlink")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("the ledger is empty")
    header = json.loads(lines[0])
    if not isinstance(header, dict) or header.get("campaign") != world.campaign:
        raise ValueError("the ledger does not belong to this campaign")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous = ""
    for sequence, line in enumerate(lines[1:], start=1):
        entry = json.loads(line)
        if not isinstance(entry, dict):
            raise ValueError("a settlement line is not a receipt")
        order_id = entry.get("order_id")
        if not isinstance(order_id, str) or not order_id or order_id in seen:
            raise ValueError("a receipt has a missing or repeated order id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the receipts are not in the order the meter wrote them")
        if entry.get("campaign") != world.campaign:
            raise ValueError("a receipt belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a receipt does not carry the meter's seal")
        seen.add(order_id)
        previous = str(signature)
        entries.append(entry)
    return entries


def collect(
    workspace: str | Path,
    world: w.World,
    shift: Any,
    raw_order: Any,
    order_id: Any,
) -> dict[str, Any]:
    'Put one order on the road, or say why the desk will not take it.'

    if not isinstance(order_id, str) or not order_id.strip() or len(order_id) > 120:
        raise ValueError("order_id must be a short non-empty label you choose")
    order_id = order_id.strip()
    order = read_order(raw_order)
    shift_id = None if shift is None else str(shift)
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["order_id"] == order_id:
                held = {
                    (str(line["area"]), str(line["window"])): int(line["vans_booked"])
                    for line in entry["lines"]
                }
                if held != order or str(entry["shift_id"]) != str(shift_id):
                    raise ValueError("that order id already names another order")
                return {
                    "receipt": entry,
                    "ran": False,
                    "shifts_settled": len(booked_shifts(entries)),
                    "allowance_left": allowance_left(world, entries),
                }
        body = receipt_body(world, order_id, shift_id, order, entries)
        entries.append(sealed(body, len(entries) + 1, entries[-1]["seal"] if entries else ""))
        pending = root / RECEIPT_FILE.with_suffix(".jsonl.pending")
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(dump(world.campaign, entries), encoding="utf-8")
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "shifts_settled": len(booked_shifts(entries)),
            "allowance_left": allowance_left(world, entries),
        }
