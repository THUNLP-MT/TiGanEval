'The channel tester as an instrument: it runs sessions and seals its receipts.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from . import world


_SEAL_KEY = hashlib.sha256(b"channel-tester-hx22-cycle-life-2026-09-06").digest()
_LOCK = threading.RLock()

RECEIPT_FILE = "session_receipts.json"


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def seal_body(body: Mapping[str, Any], request_id: str, sequence: int,
              previous: str = "") -> dict[str, Any]:
    "One sealed receipt: the tester's own record of a session it ran."

    value = dict(body)
    value["request_id"] = str(request_id)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def archived_receipts(lot_id: str) -> list[dict[str, Any]]:
    'The sealed stream a lot starts with: one receipt per session already run.'

    entries: list[dict[str, Any]] = []
    for body in world.archived_bodies(lot_id):
        entries.append(
            seal_body(
                body,
                f"archive-{body['session_id']}",
                len(entries) + 1,
                entries[-1]["seal"] if entries else "",
            )
        )
    return entries


def extend(lot_id: str, entries: Sequence[Mapping[str, Any]], bay: str, protocol: str,
           cells: int, request_id: str) -> list[dict[str, Any]]:
    'The stream after one more booked session, without touching any file.'

    held = [dict(entry) for entry in entries]
    lot = world.LOTS[lot_id]
    cost = int(cells) * int(lot["channel_hours_per_cell"])
    remaining = hours_remaining(lot_id, held)
    body = world.booked_receipt_body(lot_id, bay, protocol, int(cells), held, remaining - cost)
    held.append(seal_body(body, request_id, len(held) + 1, held[-1]["seal"] if held else ""))
    return held


def hours_remaining(lot_id: str, entries: Sequence[Mapping[str, Any]]) -> int:
    'What the booking sheet has left after everything in this stream.'

    if entries:
        return int(entries[-1]["channel_hours_remaining_after"])
    return int(world.LOTS[lot_id]["channel_hours_remaining"])


def _read_stream(path: Path, campaign: str) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise ValueError("the receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("campaign") != campaign:
        raise ValueError("the receipt file does not belong to this campaign")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("the receipt file carries no session entries")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError("a session entry is not a tester record")
        request_id = entry.get("request_id")
        if not isinstance(request_id, str) or not request_id or request_id in seen:
            raise ValueError("a session entry has a missing or repeated request id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the session entries are not in the order the tester wrote them")
        if entry.get("campaign") != campaign:
            raise ValueError("a session entry belongs to another campaign")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a session entry does not carry the tester's seal")
        seen.add(request_id)
        previous = str(signature)
    return [dict(entry) for entry in entries]


def read_receipts(workspace: str | Path, campaign: str) -> list[dict[str, Any]]:
    return _read_stream(Path(workspace) / RECEIPT_FILE, campaign)


def collect(workspace: str | Path, lot_id: str, bay: Any, protocol: Any, cells: Any,
            request_id: Any) -> dict[str, Any]:
    'Run one booked session on the tester and append its receipt.'

    lot = world.LOTS[lot_id]
    if bay not in lot["rack"]:
        raise ValueError(f"the rack has no {bay!r} bay; it has {sorted(lot['rack'])}")
    if protocol not in world.PROTOCOLS:
        raise ValueError("protocol must be standard or stepped")
    if not isinstance(cells, int) or isinstance(cells, bool) or cells <= 0:
        raise ValueError("cells must be a positive whole number")
    if cells % world.FIXTURE:
        raise ValueError(
            f"the rack loads cells a fixture at a time, so cells must be a multiple of "
            f"{world.FIXTURE}"
        )
    channels = lot["rack"][bay]["channels"]
    if cells > len(channels):
        raise ValueError(f"the {bay} bay has {len(channels)} channels and cannot hold {cells} cells")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 120:
        raise ValueError("request_id must be a non-empty string of at most 120 characters")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, str(lot["campaign"]))
        for entry in entries:
            if entry["request_id"] == request_id:
                if (entry.get("protocol") != protocol
                        or len(entry.get("observed", {}).get("cells", ())) != cells
                        or world.bay_of_channel(lot, entry["channels"][0]) != bay):
                    raise ValueError("that request id already names a different session")
                return {"receipt": entry, "executed": False,
                        "channel_hours_remaining": hours_remaining(lot_id, entries)}
        cost = int(cells) * int(lot["channel_hours_per_cell"])
        remaining = hours_remaining(lot_id, entries)
        if cost > remaining:
            raise ValueError(
                f"{cells} cells cost {cost} channel hours and the booking sheet has "
                f"{remaining} left"
            )
        entries = extend(lot_id, entries, str(bay), str(protocol), int(cells), str(request_id))
        target = root / RECEIPT_FILE
        pending = root / (RECEIPT_FILE + ".pending")
        pending.write_text(
            json.dumps({"campaign": lot["campaign"], "entries": entries},
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, target)
        return {"receipt": entries[-1], "executed": True,
                "channel_hours_remaining": hours_remaining(lot_id, entries)}
