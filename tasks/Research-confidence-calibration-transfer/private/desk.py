'The adjudication desk: what a batch returns, what it charges, what it seals.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .world import BAND_LABELS, CHANNELS, RECEIPTS_FILE, Queue, _LOCK, _SEAL_KEY


REFUSAL_OVER_CAP = "over the batch cap"
REFUSAL_EMPTY = "the cell came back empty"
REFUSAL_CREDITS = "not enough credits left"


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def receipts_document(queue: Queue, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"queue": queue.queue, "batches": [dict(entry) for entry in entries]}


def read_receipts(workspace: Path, queue: Queue) -> list[dict[str, Any]]:
    'Every batch this queue was charged for, or a reason the file will not read.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("queue") != queue.queue
        or not isinstance(raw.get("batches"), list)
    ):
        raise ValueError("the receipt file does not belong to this queue")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["batches"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a batch entry is not a desk record")
        batch_id = entry.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id or batch_id in seen:
            raise ValueError("a batch entry has a missing or repeated batch id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the batch entries are not in the order the desk wrote them")
        if entry.get("queue") != queue.queue:
            raise ValueError("a batch entry belongs to another queue")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a batch entry does not carry the adjudication desk's seal")
        seen.add(batch_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["batches"]]


def credits_charged(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["credits_charged"]) for entry in entries)


def credits_left(queue: Queue, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(queue.spec["credits_granted"]) - credits_charged(entries)


def returned_ids(entries: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(row["listing_id"])
        for entry in entries
        for row in entry.get("observed", {}).get("rows", ())
    }


def returned_rows(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for entry in entries for row in entry.get("observed", {}).get("rows", ())]


def cell_backlog(
    queue: Queue,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    period: str,
) -> list[int]:
    'The listings of one cell that still carry no outcome, oldest first.'

    already = returned_ids(entries)
    return [
        index
        for index in range(queue.size())
        if queue.channel[index] == channel
        and queue.period[index] == period
        and not queue.resolved(index)
        and queue.listing_ids[index] not in already
    ]


def adjudicated_row(queue: Queue, index: int) -> dict[str, Any]:
    'One listing as it comes back from an out-of-band adjudication.'

    return {
        "listing_id": queue.listing_ids[index],
        "channel": queue.channel[index],
        "intake_date": queue.days[queue.day_of[index]],
        "intake_period": queue.period[index],
        "stated_confidence": queue.confidence[index],
        "band": BAND_LABELS[queue.band[index]],
        "auto_cleared": "yes" if queue.auto_cleared(index) else "no",
        "review_outcome": "violating" if queue.violating[index] else "clean",
    }


def _receipt(
    queue: Queue,
    batch_id: str,
    channel: str,
    period: str,
    requested: int,
    served: Sequence[int],
    charged: int,
    remaining: int,
    refusal: str | None,
    day: str,
) -> dict[str, Any]:
    rows = [adjudicated_row(queue, index) for index in served]
    return {
        "batch_id": str(batch_id),
        "queue": queue.queue,
        "day": str(day),
        "channel": str(channel),
        "period": str(period),
        "listings_requested": int(requested),
        "listings_returned": len(rows),
        "violating_returned": sum(1 for row in rows if row["review_outcome"] == "violating"),
        "credits_charged": int(charged),
        "credits_remaining": int(remaining),
        "refusal": refusal,
        "observed": {"rows": rows},
    }


def book(
    queue: Queue,
    entries: Sequence[Mapping[str, Any]],
    channel: str,
    period: str,
    listings: int,
    batch_id: str,
    day: str | None = None,
) -> list[dict[str, Any]]:
    'The receipt list with one more batch on it, without touching any file.'

    spec = queue.spec
    unit = int(spec["credit_cost"][channel])
    cap = int(spec["max_listings_per_batch"])
    left = credits_left(queue, entries)
    when = str(day or queue.days[-1])
    served: list[int] = []
    refusal: str | None = None
    charged = 0
    if int(listings) > cap:
        refusal = REFUSAL_OVER_CAP
    else:
        backlog = cell_backlog(queue, entries, channel, period)
        if not backlog:
            refusal = REFUSAL_EMPTY
            charged = min(int(spec["empty_cell_charge"]), max(0, left))
        else:
            wanted = backlog[: int(listings)]
            cost = unit * len(wanted)
            if cost > left:
                refusal = REFUSAL_CREDITS
            else:
                served = wanted
                charged = cost
    grown = [dict(entry) for entry in entries]
    body = _receipt(
        queue, batch_id, channel, period, int(listings), served, charged,
        left - charged, refusal, when,
    )
    grown.append(seal_body(body, len(grown) + 1, grown[-1]["seal"] if grown else ""))
    return grown


def collect(
    workspace: Path,
    queue: Queue,
    channel: Any,
    period: Any,
    listings: Any,
    batch_id: Any,
) -> dict[str, Any]:
    'Put one batch through the adjudication desk and append its receipt.'

    channel = str(channel or "")
    period = str(period or "")
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {', '.join(CHANNELS)}")
    if period not in tuple(queue.spec["periods"]):
        raise ValueError(
            "period must be one of the intake plans this queue ran under: "
            + ", ".join(queue.spec["periods"])
        )
    if not isinstance(listings, int) or isinstance(listings, bool) or listings <= 0:
        raise ValueError("listings must be a positive whole number")
    if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 120:
        raise ValueError("batch_id must be a short non-empty label you choose")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, queue)
        for entry in entries:
            if entry["batch_id"] == batch_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "credits_charged": credits_charged(entries),
                    "credits_left": credits_left(queue, entries),
                }
        entries = book(queue, entries, channel, period, int(listings), batch_id)
        pending = root / (RECEIPTS_FILE + ".pending")
        pending.write_text(
            json.dumps(receipts_document(queue, entries), indent=2) + "\n", encoding="utf-8"
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "credits_charged": credits_charged(entries),
            "credits_left": credits_left(queue, entries),
        }
