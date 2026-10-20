'The annotation desk: what a capture request returns, and what it bills.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence

from . import world


RECEIPTS_FILE = world.RECEIPTS_FILE
BELOW_MINIMUM = "fewer than the minimum rows a request may ask for"
OVER_CAP = "over the rows a request may ask for"
OVER_CREDITS = "over the credits the campaign has left"
EMPTY_CELL = "no units in that cell"

_LOCK = threading.RLock()
_SEAL_KEY = hashlib.sha256(b"authored-handheld-annotation-desk-2026-09-07").digest()


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def terms(fleet: world.Fleet) -> Mapping[str, Any]:
    return fleet.terms()


def credits_spent(receipts: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["credits_charged"]) for entry in receipts)


def credits_left(fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]) -> int:
    return int(fleet.spec["credits_granted"]) - credits_spent(receipts)


def row_cost(fleet: world.Fleet, duty_profile: str, condition: str) -> int:
    settings = terms(fleet)
    if str(condition) == world.REFERENCE_CARD:
        return int(settings["reference_card_cost_per_row"])
    return int(settings["credit_cost_per_row"][str(duty_profile)])


def rows_of(receipts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for entry in receipts for row in entry.get("observed", {}).get("rows", ())]


def _taken(receipts: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(row["capture_id"]) for row in rows_of(receipts)}


def _payload(fleet: world.Fleet, index: int) -> dict[str, Any]:
    values = fleet.log_row(index)
    row = dict(zip(fleet.log_columns(), values))
    row["capture_id"] = f"{fleet.spec['unit_prefix']}C-{index:06d}"
    capture = fleet.captures[index]
    row["duty_profile"] = fleet.unit_of(capture).duty_profile
    return row


def cell_frame(
    fleet: world.Fleet,
    duty_profile: str,
    firmware: str,
    condition: str,
    receipts: Sequence[Mapping[str, Any]],
) -> list[int]:
    'The captures the desk could still put in front of an annotator.'

    key = (fleet.campaign, str(duty_profile), str(firmware), str(condition))
    if key not in world._FRAME_CACHE:
        found: list[int] = []
        for index, capture in enumerate(fleet.captures):
            if capture.exported:
                continue
            unit = fleet.unit_of(capture)
            if unit.duty_profile != str(duty_profile) or unit.firmware != str(firmware):
                continue
            if capture.condition != str(condition):
                continue
            found.append(index)
        found.sort(key=lambda item: world.readable_score(fleet.captures[item].truth))
        world._FRAME_CACHE[key] = found
    taken = _taken(receipts)
    prefix = fleet.spec["unit_prefix"]
    return [
        index
        for index in world._FRAME_CACHE[key]
        if f"{prefix}C-{index:06d}" not in taken
    ]


def systematic(frame: Sequence[int], rows: int) -> list[int]:
    "One capture from each equal band of the frame, keeping the band's mix."

    total = len(frame)
    if rows <= 0 or total == 0:
        return []
    if rows >= total:
        return list(frame)
    step = total / float(rows)
    return [frame[min(total - 1, int(position * step))] for position in range(rows)]


def reference_rows(fleet: world.Fleet, firmware: str, rows: int) -> list[dict[str, Any]]:
    'Bench captures of the one reference target, on the firmware asked for.'

    generator = random.Random(int(fleet.spec["seed"]) + 991 + (7 if firmware == str(fleet.spec["raised_firmware"]) else 0))
    centre, spread = world.REFERENCE_PARAMS
    made: list[dict[str, Any]] = []
    for position in range(int(rows)):
        values = tuple(
            max(0.01, generator.gauss(centre[index], spread[index]))
            for index in range(len(world.FEATURES))
        )
        raised = str(firmware) == str(fleet.spec["raised_firmware"])
        written = world.apply_gain(values, fleet.gain) if raised else list(values)
        label = 1 if world.readable_score(values) >= 0.0 else 0
        row = {
            "capture_id": f"{fleet.spec['unit_prefix']}B-{firmware}-{position:04d}",
            "device_id": f"BENCH-{firmware}",
            "duty_profile": "bench",
            "firmware": str(firmware),
            "condition": world.REFERENCE_CARD,
            "day": str(fleet.spec["as_of"]),
            "label": label,
            "stage": "as_captured" if raised else "corrected",
        }
        row.update({name: round(written[index], 4) for index, name in enumerate(world.FEATURES)})
        row.update({name: world.decide(name, written) for name in world.BUNDLES})
        made.append(row)
    return made


def refusal_reason(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    duty_profile: str,
    firmware: str,
    condition: str,
    rows: int,
) -> str | None:
    'Why the desk would turn this request away, or None when it would take it.'

    settings = terms(fleet)
    if int(rows) < int(settings["min_rows_per_request"]):
        return BELOW_MINIMUM
    if int(rows) > int(settings["max_rows_per_request"]):
        return OVER_CAP
    cost = row_cost(fleet, duty_profile, condition) * int(rows)
    if cost > credits_left(fleet, receipts):
        return OVER_CREDITS
    if str(condition) == world.REFERENCE_CARD:
        return None
    if not cell_frame(fleet, duty_profile, firmware, condition, receipts):
        return EMPTY_CELL
    return None


def receipt_body(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    duty_profile: str,
    firmware: str,
    condition: str,
    rows: int,
    receipt_id: str,
    refusal: str | None,
    returned: Sequence[Mapping[str, Any]],
    charged: int,
    day: str | None = None,
) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt_id),
        "campaign": fleet.campaign,
        "request_id": f"{fleet.spec['request_prefix']}-{len(receipts) + 1:03d}",
        "day": str(day or fleet.spec["as_of"]),
        "duty_profile": str(duty_profile),
        "firmware": str(firmware),
        "condition": str(condition),
        "rows_requested": int(rows),
        "rows_returned": len(returned),
        "credits_charged": int(charged),
        "credits_remaining": credits_left(fleet, receipts) - int(charged),
        "refusal": refusal,
        "observed": {"rows": [dict(row) for row in returned]},
    }


def book(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    duty_profile: Any,
    firmware: Any,
    condition: Any,
    rows: Any,
    receipt_id: str,
    day: str | None = None,
) -> list[dict[str, Any]]:
    'The receipts with one more request on them, without touching any file.'

    held = [dict(entry) for entry in receipts]
    refusal = refusal_reason(
        fleet, held, str(duty_profile), str(firmware), str(condition), int(rows)
    )
    if refusal is None:
        if str(condition) == world.REFERENCE_CARD:
            returned = reference_rows(fleet, str(firmware), int(rows))
        else:
            frame = cell_frame(fleet, str(duty_profile), str(firmware), str(condition), held)
            returned = [_payload(fleet, index) for index in systematic(frame, int(rows))]
        charged = row_cost(fleet, str(duty_profile), str(condition)) * len(returned)
    else:
        returned = []
        charged = int(terms(fleet)["refusal_charge"])
    body = receipt_body(
        fleet, held, str(duty_profile), str(firmware), str(condition), int(rows),
        str(receipt_id), refusal, returned, charged, day,
    )
    held.append(seal_body(body, len(held) + 1, held[-1]["seal"] if held else ""))
    return held


def receipts_document(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {"campaign": fleet.campaign, "receipts": [dict(entry) for entry in receipts]}


def read_receipts(workspace: Path, fleet: world.Fleet) -> list[dict[str, Any]]:
    'Every request this campaign has been billed for, or why the file will not read.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("campaign") != fleet.campaign
        or not isinstance(raw.get("receipts"), list)
    ):
        raise ValueError("the receipt file does not belong to this campaign")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["receipts"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a receipt is not a desk record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the receipts are not in the order the desk wrote them")
        if entry.get("campaign") != fleet.campaign:
            raise ValueError("a receipt belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a receipt does not carry the annotation desk's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["receipts"]]


def collect(
    workspace: Path,
    fleet: world.Fleet,
    duty_profile: Any,
    firmware: Any,
    condition: Any,
    rows: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    'Put one capture request to the desk and append its receipt.'

    settings = terms(fleet)
    if str(duty_profile) not in world.PROFILES:
        raise ValueError(
            "duty_profile must be one of " + ", ".join(world.PROFILES)
        )
    if str(firmware) not in (
        str(fleet.spec["raised_firmware"]),
        str(fleet.spec["earlier_firmware"]),
    ):
        raise ValueError("firmware must be one this fleet runs")
    if str(condition) not in settings["conditions"]:
        raise ValueError("condition must be one of " + ", ".join(settings["conditions"]))
    if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
        raise ValueError("rows must be a positive whole number of captures")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")

    root = Path(workspace).resolve()
    with _LOCK:
        receipts = read_receipts(root, fleet)
        for entry in receipts:
            if entry["receipt_id"] == receipt_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "credits_spent": credits_spent(receipts),
                    "credits_left": credits_left(fleet, receipts),
                }
        if credits_left(fleet, receipts) < int(settings["refusal_charge"]):
            raise ValueError(
                "the campaign has nothing left; the desk cannot even bill a refusal"
            )
        grown = book(fleet, receipts, duty_profile, firmware, condition, rows, str(receipt_id))
        pending = root / (RECEIPTS_FILE + ".pending")
        pending.write_text(
            json.dumps(receipts_document(fleet, grown), indent=2) + "\n", encoding="utf-8"
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": grown[-1],
            "ran": grown[-1]["refusal"] is None,
            "credits_spent": credits_spent(grown),
            "credits_left": credits_left(fleet, grown),
        }
