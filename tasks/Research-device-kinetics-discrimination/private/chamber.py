'The chamber desk: what a booked block returns, and the receipt it writes.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .world import _LOCK, _SEAL_KEY, RECEIPTS_FILE, World


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def spare_modules(world: World, lot: str, taken: int, ports: int) -> list[dict[str, Any]]:
    'The next `ports` spare modules of one lot, with their incoming readings.'

    base = float(world.spec["spare_incoming_mw"][str(lot)])
    spread = (0.0, 0.2, 0.1, 0.3, 0.0, 0.4, 0.2, 0.1, 0.3, 0.0, 0.2, 0.4)
    out = []
    for offset in range(int(ports)):
        index = int(taken) + offset
        out.append(
            {
                "module_id": f"{lot}-S{index + 1:02d}",
                "incoming_mw": round(base + spread[index % len(spread)], 1),
            }
        )
    return out


def block_readings(
    world: World,
    block_id: str,
    modules: Sequence[Mapping[str, Any]],
    drive_a: float,
    case_temp_c: float,
    chamber_days: int,
) -> list[dict[str, Any]]:
    'One reading per module per bench session of the block.'

    step = float(world.spec["block_read_interval_h"])
    rows: list[dict[str, Any]] = []
    for module in modules:
        incoming = float(module["incoming_mw"])
        index = 0
        hours = step
        while hours <= float(chamber_days) * 24.0 + 1e-9:
            index += 1
            true_mw = incoming * (1.0 - world.loss(hours, drive_a, case_temp_c))
            rows.append(
                {
                    "module_id": str(module["module_id"]),
                    "soak_h": round(hours, 3),
                    "output_mw": world.reading(
                        true_mw, f"{block_id}|{module['module_id']}", index
                    ),
                }
            )
            hours += step
    return rows


def _days_of(world: World, stream: Sequence[Mapping[str, Any]], charged: int) -> list[str]:
    days = world.campaign_days()
    start = world.days_spent(stream)
    return days[start : start + int(charged)]


def refusal_for(
    world: World,
    stream: Sequence[Mapping[str, Any]],
    *,
    drive_a: float,
    case_temp_c: float,
    ports: int,
    chamber_days: int,
    lot: str,
    charged: int,
) -> str:
    budget = world.spec
    if not 1 <= int(ports) <= int(budget["ports_cap"]):
        return (
            f"the rig holds {int(budget['ports_cap'])} ports; the sheet asked for {int(ports)}"
        )
    if not int(budget["smallest_block_days"]) <= int(chamber_days) <= int(
        budget["days_per_block_cap"]
    ):
        return (
            f"a block runs from {int(budget['smallest_block_days'])} to "
            f"{int(budget['days_per_block_cap'])} chamber-days; the sheet asked for "
            f"{int(chamber_days)}"
        )
    if not float(budget["drive_floor_a"]) - 1e-9 <= float(drive_a) <= float(
        budget["drive_cap_a"]
    ) + 1e-9:
        return (
            f"the supply runs from {float(budget['drive_floor_a']):g} to "
            f"{float(budget['drive_cap_a']):g} A; the sheet asked for {float(drive_a):g} A"
        )
    if not world.hold_temp_c - 1e-9 <= float(case_temp_c) <= float(budget["temp_cap_c"]) + 1e-9:
        return (
            f"the chamber holds from {world.hold_temp_c:g} to "
            f"{float(budget['temp_cap_c']):g} C; the sheet asked for {float(case_temp_c):g} C"
        )
    left = world.spares_left(stream)
    if str(lot) not in left:
        return f"{lot} is not a lot the shop holds spares of"
    if left[str(lot)] < int(ports):
        return (
            f"stores hold {left[str(lot)]} spares of {lot} and the sheet asked for {int(ports)}"
        )
    days = _days_of(world, stream, charged)
    if len(days) < int(charged):
        return "the schedule has no day left before the review"
    shut = [day for day in days if world.rig_is_out(day)]
    if shut:
        window = list(world.spec["rig_out"])
        return (
            f"the rig is off for its service from {window[0]} to {window[1]} and the "
            f"block would run over {shut[0]}"
        )
    return ""


def receipt(world: World, stream: Sequence[Mapping[str, Any]], booking: Mapping[str, Any]) -> dict:
    'One block as the desk serves it onto an existing stream.'

    block_id = str(booking["block_id"])
    drive = float(booking["drive_a"])
    temp = float(booking["case_temp_c"])
    ports = int(booking["ports"])
    chamber_days = int(booking["chamber_days"])
    lot = str(booking["lot"])
    charged = world.days_charged(chamber_days)
    refusal = refusal_for(
        world, stream, drive_a=drive, case_temp_c=temp, ports=ports,
        chamber_days=chamber_days, lot=lot, charged=charged,
    )
    modules: list[dict[str, Any]] = []
    readings: list[dict[str, Any]] = []
    if not refusal:
        taken = sum(
            int(item["modules_returned"]) for item in stream if str(item.get("lot")) == lot
        )
        modules = spare_modules(world, lot, taken, ports)
        readings = block_readings(world, block_id, modules, drive, temp, chamber_days)
    days = _days_of(world, stream, charged)
    body = {
        "campaign": world.campaign,
        "sequence": len(stream) + 1,
        "block_id": block_id,
        "drive_a": round(drive, 2),
        "case_temp_c": round(temp, 1),
        "ports_asked": ports,
        "chamber_days_asked": chamber_days,
        "lot": lot,
        "modules": modules,
        "readings": readings,
        "modules_returned": len(modules),
        "rows_returned": len(readings),
        "days_charged": int(charged),
        "days_left_after": world.days_left(stream) - int(charged),
        "served_on": days[0] if days else world.campaign_days()[-1],
        "refusal": refusal,
        "previous": stream[-1]["seal"] if stream else "",
    }
    return dict(body, seal=_seal(body))


def opening_stream(world: World) -> list[dict[str, Any]]:
    'The receipts the campaign already carries before anybody books anything.'

    entries: list[dict[str, Any]] = []
    for booking in world.spec["opening_blocks"]:
        entries.append(receipt(world, entries, dict(booking)))
    return entries


def extend(
    world: World, stream: Sequence[Mapping[str, Any]], bookings: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The same stream with more blocks served onto the end of it.'

    grown = [dict(item) for item in stream]
    for booking in bookings:
        grown.append(receipt(world, grown, booking))
    return grown


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every block this campaign has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the receipt stream must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("campaign") != world.campaign
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the receipt stream does not belong to this campaign")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a chamber receipt is not a desk record")
        block_id = entry.get("block_id")
        if not isinstance(block_id, str) or not block_id or block_id in seen:
            raise ValueError("a chamber receipt has a missing or repeated block id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the chamber receipts are not in the order the desk wrote them")
        if entry.get("campaign") != world.campaign:
            raise ValueError("a chamber receipt belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a chamber receipt does not carry the desk seal")
        seen.add(block_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def collect(
    workspace: Path,
    world: World,
    drive_a: Any,
    case_temp_c: Any,
    ports: Any,
    chamber_days: Any,
    lot: Any,
    block_id: Any,
) -> dict[str, Any]:
    'Serve one block and append its receipt to the workspace stream.'

    if not isinstance(ports, int) or isinstance(ports, bool):
        raise ValueError("ports must be a whole number of modules")
    if not isinstance(chamber_days, int) or isinstance(chamber_days, bool):
        raise ValueError("chamber_days must be a whole number of days")
    if not 1 <= chamber_days <= 60:
        raise ValueError("chamber_days must be between 1 and 60")
    for name, value in (("drive_a", drive_a), ("case_temp_c", case_temp_c)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
    if not isinstance(block_id, str) or not block_id.strip() or len(block_id) > 120:
        raise ValueError("block_id must be a short non-empty label you choose")
    if not isinstance(lot, str) or not lot.strip():
        raise ValueError("lot must name a lot the shop holds spares of")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["block_id"] == block_id:
                same = (
                    abs(float(entry["drive_a"]) - float(drive_a)) < 1e-9
                    and abs(float(entry["case_temp_c"]) - float(case_temp_c)) < 1e-9
                    and int(entry["ports_asked"]) == ports
                    and int(entry["chamber_days_asked"]) == chamber_days
                    and entry["lot"] == lot
                )
                if not same:
                    raise ValueError("that block id already names another block")
                return {
                    "receipt": entry,
                    "ran": False,
                    "days_spent": world.days_spent(entries),
                    "days_left": world.days_left(entries),
                    "spares_left": world.spares_left(entries),
                }
        charged = world.days_charged(chamber_days)
        if world.days_left(entries) < charged:
            raise ValueError(
                f"this block costs {charged} chamber-days and the campaign has "
                f"{world.days_left(entries)} left of the "
                f"{int(world.spec['days_granted'])} the plan granted"
            )
        made = receipt(
            world,
            entries,
            {
                "block_id": block_id,
                "drive_a": float(drive_a),
                "case_temp_c": float(case_temp_c),
                "ports": ports,
                "chamber_days": chamber_days,
                "lot": lot,
            },
        )
        entries.append(made)
        pending = root / "soak_receipts.pending"
        pending.write_text(
            json.dumps({"campaign": world.campaign, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": made,
            "ran": True,
            "days_spent": world.days_spent(entries),
            "days_left": world.days_left(entries),
            "spares_left": world.spares_left(entries),
        }
