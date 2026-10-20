'The audit desk: what a night visit costs, what it returns, and its receipts.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from .world import Depot


RECEIPTS_FILE = "visit_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-halstow-audit-desk-2026-09-07").digest()
_LOCK = threading.RLock()

OFF_ROSTER = "class is not on that week's night roster"
OVER_CAPS = "the desk will not take that visit"
SHORT_OF_UNITS = "not enough of the grant left for a visit"


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def units_spent(receipts: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["units_charged"]) for entry in receipts)


def units_left(depot: Depot, receipts: Sequence[Mapping[str, Any]]) -> int:
    return int(depot.spec["units_granted"]) - units_spent(receipts)


def rows_of(receipts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for entry in receipts for row in entry.get("observed", {}).get("rows", ())]


def taken_ids(receipts: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(row["job_id"]) for row in rows_of(receipts)]


def visits_in_week(receipts: Sequence[Mapping[str, Any]], week: int) -> int:
    return sum(
        1
        for entry in receipts
        if int(entry["week"]) == int(week) and not entry.get("refusal")
    )


def refusal_reason(
    depot: Depot, receipts: Sequence[Mapping[str, Any]], week: int, job_class: str, jobs: int
) -> str | None:
    'Why the desk would turn this request away, or None when it would take it.'

    context = depot.visit_terms()
    roster = context["roster"].get(str(job_class), ())
    if int(week) not in [int(item) for item in roster]:
        return OFF_ROSTER
    if int(jobs) > int(context["jobs_per_visit"]):
        return OVER_CAPS
    if visits_in_week(receipts, week) >= int(context["visits_per_week"]):
        return OVER_CAPS
    if units_left(depot, receipts) < int(context["units_per_visit"]):
        return SHORT_OF_UNITS
    return None


def receipt_body(
    depot: Depot,
    receipts: Sequence[Mapping[str, Any]],
    week: int,
    job_class: str,
    jobs: int,
    receipt_id: str,
    refusal: str | None,
    rows: Sequence[Mapping[str, Any]],
    charged: int,
) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt_id),
        "depot": depot.depot,
        "visit_id": f"{depot.spec['visit_prefix']}-{len(receipts) + 1:03d}",
        "week": int(week),
        "job_class": str(job_class),
        "jobs_requested": int(jobs),
        "jobs_returned": len(rows),
        "units_charged": int(charged),
        "roster_ok": refusal != OFF_ROSTER,
        "refusal": refusal,
        "units_remaining": units_left(depot, receipts) - int(charged),
        "observed": {"rows": [dict(row) for row in rows]},
    }


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def book(
    depot: Depot,
    receipts: Sequence[Mapping[str, Any]],
    week: Any,
    job_class: Any,
    jobs: Any,
    receipt_id: str,
) -> list[dict[str, Any]]:
    'The receipts with one more visit on them, without touching any file.'

    held = [dict(entry) for entry in receipts]
    context = depot.visit_terms()
    refusal = refusal_reason(depot, held, int(week), str(job_class), int(jobs))
    if refusal is None:
        rows = depot.visit_rows(str(job_class), int(jobs), taken_ids(held))
        charged = int(context["units_per_visit"])
    else:
        rows = []
        charged = int(context["units_per_refusal"])
    body = receipt_body(
        depot, held, int(week), str(job_class), int(jobs), receipt_id, refusal, rows, charged
    )
    held.append(seal_body(body, len(held) + 1, held[-1]["seal"] if held else ""))
    return held


def receipts_document(depot: Depot, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"depot": depot.depot, "receipts": [dict(entry) for entry in receipts]}


def read_receipts(workspace: Path, depot: Depot) -> list[dict[str, Any]]:
    'Every visit this depot has been billed for, or a reason the file will not read.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the visit receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("depot") != depot.depot
        or not isinstance(raw.get("receipts"), list)
    ):
        raise ValueError("the visit receipts do not belong to this depot")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["receipts"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a visit receipt is not a desk record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a visit receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the visit receipts are not in the order the desk wrote them")
        if entry.get("depot") != depot.depot:
            raise ValueError("a visit receipt belongs to another depot")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a visit receipt does not carry the audit desk's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["receipts"]]


def collect(
    workspace: Path,
    depot: Depot,
    week: Any,
    job_class: Any,
    jobs: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    'Book one night visit and append its receipt.'

    context = depot.visit_terms()
    if str(job_class) not in depot.classes:
        raise ValueError(
            f"{job_class!r} is not a class this depot dispatches; it runs "
            + ", ".join(depot.classes)
        )
    if not isinstance(week, int) or isinstance(week, bool) or int(week) not in context["weeks"]:
        raise ValueError(
            "week must be one of the audit weeks still open: "
            + ", ".join(str(item) for item in context["weeks"])
        )
    if not isinstance(jobs, int) or isinstance(jobs, bool) or jobs <= 0:
        raise ValueError("jobs must be a positive whole number of jobs to time")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")

    root = Path(workspace).resolve()
    with _LOCK:
        receipts = read_receipts(root, depot)
        for entry in receipts:
            if entry["receipt_id"] == receipt_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(receipts),
                    "units_left": units_left(depot, receipts),
                }
        if units_left(depot, receipts) < int(context["units_per_refusal"]):
            raise ValueError(
                "the grant has nothing left; the desk cannot even bill a refusal"
            )
        grown = book(depot, receipts, week, job_class, jobs, str(receipt_id))
        pending = root / (RECEIPTS_FILE + ".pending")
        pending.write_text(
            json.dumps(receipts_document(depot, grown), indent=2) + "\n", encoding="utf-8"
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": grown[-1],
            "ran": not grown[-1]["refusal"],
            "units_spent": units_spent(grown),
            "units_left": units_left(depot, grown),
        }
