'The labelling vendor as an instrument: it runs sessions and seals its receipts.'

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from .world import Desk


_SEAL_KEY = hashlib.sha256(b"label-vendor-ticket-triage-2026-09-06").digest()
_LOCK = threading.RLock()

LEDGER_FILE = "label_ledger.jsonl"
BILLED_FIELDS = ("receipt_id", "session_id", "position_in_session", "item_id",
                 "channel", "segment", "price_credits", "label", "draw_rule", "draw_p")


def _seal(body: Mapping[str, Any]) -> str:
    text = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, text, hashlib.sha256).hexdigest()


def _sealed(body: Mapping[str, Any], sequence: int, previous: str) -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def _chain(desk: Desk, bodies: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for body in bodies:
        entries.append(_sealed(body, len(entries) + 1, entries[-1]["seal"] if entries else ""))
    return entries


def chain(desk: Desk, bodies: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'One sealed ledger from a list of receipt bodies, in the order given.'

    return _chain(desk, bodies)


def bodies_of(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipt bodies of a ledger, without the transport fields.'

    return [
        {key: value for key, value in entry.items()
         if key not in ("sequence", "previous", "seal")}
        for entry in entries
    ]


def receipt_body(desk: Desk, session: Mapping[str, Any], position: int,
                 item: Mapping[str, Any], receipt_id: str) -> dict[str, Any]:
    return {
        "desk": desk.code,
        "receipt_id": str(receipt_id),
        "session_id": str(session["session_id"]),
        "position_in_session": int(position),
        "reviewer": str(session.get("reviewer", "R-00")),
        "ordered_at": str(session["ordered_at"]),
        "delivered_at": str(session["delivered_at"]),
        "item_id": str(item["item_id"]),
        "channel": str(item["channel"]),
        "product_line": str(item["product_line"]),
        "segment": str(item["segment"]),
        "draw_rule": str(session.get("draw_rule", "uncertainty")),
        "draw_p": desk.draw_probability(item["item_id"]),
        "price_credits": desk.price_of(item["channel"]),
        "label": desk.label_of(item, str(session["session_id"]), int(position)),
    }


def historical_sessions(desk: Desk) -> list[dict[str, Any]]:
    'Each past session with the items the sampler drew for it, in order.'

    order = desk.draw_order()
    cursor = 0
    sessions = []
    for entry in desk.spec["sessions"]:
        size = int(entry["items"])
        sessions.append({**entry, "picks": order[cursor:cursor + size]})
        cursor += size
    return sessions


def archived_bodies(desk: Desk) -> list[dict[str, Any]]:
    'Every receipt line the desk holds before this review does anything.'

    retry = desk.spec.get("redelivery") or {}
    bodies: list[dict[str, Any]] = []
    counter = 0
    for session in historical_sessions(desk):
        issued = []
        for position, item in enumerate(session["picks"], start=1):
            counter += 1
            body = receipt_body(desk, session, position, item, f"{desk.code}-R{counter:05d}")
            issued.append(body)
        bodies.extend(issued)
        if str(retry.get("session_id")) == str(session["session_id"]):
            bodies.extend(dict(body) for body in issued[: int(retry["receipts"])])
    return bodies


def archived_ledger(desk: Desk) -> list[dict[str, Any]]:
    return _chain(desk, archived_bodies(desk))


def adjudication_rows(desk: Desk) -> list[dict[str, Any]]:
    'The bought items two senior agents settled between them, item by item.'

    from .world import _unit

    sessions = set(desk.spec["adjudicated_from"])
    lines = desk.spec.get("adjudicated_lines")
    owned = set(lines) if lines else None
    seen: dict[str, dict[str, Any]] = {}
    for body in archived_bodies(desk):
        if str(body["session_id"]) not in sessions:
            continue
        if owned is not None and str(body["product_line"]) not in owned:
            continue
        seen.setdefault(str(body["item_id"]), body)
    ordered = sorted(
        seen.values(),
        key=lambda body: (_unit("settle", desk.code, body["item_id"]), body["item_id"]),
    )
    chosen = sorted(ordered[: int(desk.spec["adjudicated"])], key=lambda body: body["item_id"])
    return [
        {
            "item_id": str(body["item_id"]),
            "settled_on": str(desk.spec["adjudicated_on"]),
            "settled_queue": desk.correct_queue(str(body["segment"])),
            "panel": "two senior agents",
        }
        for body in chosen
    ]


def closing_bodies(desk: Desk, session_id: str, ordered_at: str,
                   items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Receipts for one further session, run in the order the items are given.'

    session = {
        "session_id": session_id,
        "ordered_at": ordered_at,
        "delivered_at": _delivered(ordered_at),
        "reviewer": "R-22",
        "draw_rule": "chosen",
    }
    return [
        receipt_body(desk, session, position, item, f"{desk.code}-{session_id}-{position:03d}")
        for position, item in enumerate(items, start=1)
    ]


def _delivered(ordered_at: str) -> str:
    stamp = datetime.fromisoformat(str(ordered_at))
    return (stamp + timedelta(hours=9, minutes=25)).isoformat(timespec="minutes")


def sessions_on(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for entry in entries:
        if entry["session_id"] not in seen:
            seen.append(str(entry["session_id"]))
    return seen


def distinct(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'One line per receipt id, in the order the vendor first issued it.'

    seen: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry["receipt_id"])
        if key not in seen:
            seen[key] = dict(entry)
    return list(seen.values())


def credits_spent(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    "What the vendor's statement charges for this stream."

    unique = distinct(entries)
    labels = sum(int(entry["price_credits"]) for entry in unique)
    return labels + len(sessions_on(unique)) * int(desk.spec["setup_credits"])


def credits_left(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(desk.spec["credits_contracted"]) - credits_spent(desk, entries)


def bought_items(entries: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(entry["item_id"]) for entry in entries}


def read_entries(workspace: str | Path, desk: Desk) -> list[dict[str, Any]]:
    'Every receipt line the desk holds, or a reason the stream will not read.'

    path = Path(workspace) / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("the label ledger must not be a symlink")
    entries: list[dict[str, Any]] = []
    issued: dict[str, dict[str, Any]] = {}
    previous = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"line {number} of the label ledger is not a vendor record") from None
        if not isinstance(entry, dict):
            raise ValueError(f"line {number} of the label ledger is not a vendor record")
        if entry.get("desk") != desk.code:
            raise ValueError(f"line {number} of the label ledger belongs to another desk")
        if entry.get("sequence") != len(entries) + 1 or entry.get("previous") != previous:
            raise ValueError("the label ledger is not in the order the vendor wrote it")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError(f"line {number} of the label ledger carries no vendor seal")
        key = str(entry.get("receipt_id"))
        first = issued.get(key)
        if first is not None:
            if any(first[field] != entry.get(field) for field in BILLED_FIELDS):
                raise ValueError(f"receipt {key} was re-issued with different terms")
        else:
            issued[key] = dict(entry)
        entries.append(dict(entry))
        previous = str(signature)
    if not entries:
        raise ValueError("the label ledger holds no receipts")
    return entries


def write_entries(workspace: str | Path, entries: Sequence[Mapping[str, Any]]) -> None:
    root = Path(workspace).resolve()
    text = "".join(
        json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in entries
    )
    pending = root / (LEDGER_FILE + ".pending")
    pending.write_text(text, encoding="utf-8")
    os.replace(pending, root / LEDGER_FILE)


def _picked(desk: Desk, held: Sequence[Mapping[str, Any]], arguments: Mapping[str, Any]
            ) -> list[Mapping[str, Any]]:
    pool = desk.pool_index()
    already = bought_items(held)
    listed = arguments.get("items")
    draw = arguments.get("draw")
    if listed is not None and draw is not None:
        raise ValueError("give the vendor a list of items or a draw, not both")
    if listed is not None:
        if not isinstance(listed, (list, tuple)) or not listed:
            raise ValueError("items must be a non-empty list of pool item ids")
        chosen = []
        seen: set[str] = set()
        for raw in listed:
            item_id = str(raw)
            if item_id in seen:
                raise ValueError(f"{item_id} appears twice in the same session")
            if item_id not in pool:
                raise ValueError(f"{item_id} is not in the label pool")
            if item_id in already:
                raise ValueError(f"{item_id} already has a label on the ledger")
            seen.add(item_id)
            chosen.append(pool[item_id])
        return chosen
    if not isinstance(draw, Mapping):
        raise ValueError("a session needs items=[...] or draw={rule, n, ...}")
    rule = str(draw.get("rule", "uncertainty"))
    if rule not in ("uncertainty", "confidence", "pool_order"):
        raise ValueError("draw rule must be uncertainty, confidence or pool_order")
    count = draw.get("n")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("draw n must be a positive whole number")
    rows = [row for row in desk.pool_rows() if row["item_id"] not in already]
    for field in ("channel", "segment", "product_line", "priority"):
        wanted = draw.get(field)
        if wanted is not None:
            rows = [row for row in rows if row[field] == str(wanted)]
    if rule == "uncertainty":
        rows.sort(key=lambda row: (row["model_margin"], row["item_id"]))
    elif rule == "confidence":
        rows.sort(key=lambda row: (-row["model_margin"], row["item_id"]))
    if len(rows) < count:
        raise ValueError(
            f"the pool has {len(rows)} unlabelled items matching that draw, not {count}"
        )
    return rows[:count]


def collect(workspace: str | Path, desk: Desk, arguments: Mapping[str, Any]) -> dict[str, Any]:
    'Run one labelling session and append its receipts, or say why it cannot run.'

    session_id = arguments.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 60:
        raise ValueError("session_id must be a short label you choose")
    root = Path(workspace).resolve()
    with _LOCK:
        held = read_entries(root, desk)
        existing = [entry for entry in held if entry["session_id"] == session_id]
        if existing:
            return {
                "receipts": existing,
                "ran": False,
                "credits_spent": credits_spent(desk, held),
                "credits_left": credits_left(desk, held),
            }

        today = datetime.fromisoformat(str(desk.spec["today"])).date()
        cutoff = datetime.fromisoformat(str(desk.spec["order_cutoff"])).date()
        available_days = [
            today + timedelta(days=offset)
            for offset in range(int(desk.spec["sessions_before_cutoff"]))
            if today + timedelta(days=offset) <= cutoff
        ]
        occupied_days = {
            datetime.fromisoformat(str(entry["ordered_at"])).date()
            for entry in distinct(held)
        }
        order_day = next((day for day in available_days if day not in occupied_days), None)
        if order_day is None:
            raise ValueError(
                f"the account has no session day left on or before {cutoff.isoformat()}"
            )

        chosen = _picked(desk, held, arguments)
        cap = int(desk.spec["session_item_cap"])
        if len(chosen) > cap:
            raise ValueError(f"the vendor takes at most {cap} items in one session")
        cost = int(desk.spec["setup_credits"]) + sum(
            desk.price_of(item["channel"]) for item in chosen
        )
        left = credits_left(desk, held)
        if cost > left:
            raise ValueError(
                f"that session costs {cost} credits and the account has {left} left"
            )
        ordered_at = f"{order_day.isoformat()}T09:30"
        bodies = closing_bodies(desk, session_id, ordered_at, chosen)
        grown = _chain(desk, bodies_of(held) + bodies)
        write_entries(root, grown)
        made = grown[len(held):]
        return {
            "receipts": made,
            "ran": True,
            "credits_spent": credits_spent(desk, grown),
            "credits_left": credits_left(desk, grown),
        }
