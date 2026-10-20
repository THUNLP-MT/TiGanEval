'The account review desk: what a lot of files costs, and what it returns.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from .world import Market, shift


RECEIPTS_FILE = "review_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-file-review-desk-instrument-2026-09-07").digest()
_LOCK = threading.RLock()


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


_ELIGIBLE: dict[tuple[str, int, float], dict[str, list[Mapping[str, Any]]]] = {}


def eligible_rows(market: Market, week: int, band: float) -> dict[str, list[Mapping[str, Any]]]:
    'The files the desk can pull for one week and one band, either side.'

    key = (market.market, int(week), float(band))
    if key not in _ELIGIBLE:
        _ELIGIBLE[key] = _eligible_rows(market, week, band)
    return _ELIGIBLE[key]


def _eligible_rows(market: Market, week: int, band: float) -> dict[str, list[Mapping[str, Any]]]:
    cut = market.cut
    sides: dict[str, list[Mapping[str, Any]]] = {"above": [], "below": []}
    for row in market.rows:
        if row["run_status"] != "scored" or int(row["run_week"]) != int(week):
            continue
        if abs(float(row["run_score"]) - cut) > float(band):
            continue
        sides["above" if float(row["run_score"]) >= cut else "below"].append(row)
    return sides


def reviewed_row(market: Market, row: Mapping[str, Any]) -> dict[str, Any]:
    "One file as the desk hands it back: the run's own score, orders to date."

    first = str(market.spec["first_day"])
    window = int(market.spec["order_window_days"])
    offer_day = int(row["offer_day"])
    watched = max(0, min(window, int(market.spec["window_days"]) - offer_day))
    offset = row["order_offset"]
    seen = offset is not None and int(offset) <= watched
    return {
        "account_id": row["account_id"],
        "run_week": int(row["run_week"]),
        "run_score": round(float(row["run_score"]), 2),
        "standing_score": round(float(row["register_score"]), 2),
        "credits_filed": round(float(row["credit"]), 2),
        "offer_flag": int(row["offer_flag"]),
        "offer_date": str(row["offer_date"]),
        "first_order_date": (
            shift(first, offer_day + int(offset) - 1) if seen else ""
        ),
        "last_observed_date": shift(first, offer_day + watched - 1),
        "days_watched": watched,
    }


def lot_rows(
    market: Market, week: int, band: float, above_share: float, files: int, seen: Sequence[str]
) -> list[dict[str, Any]]:
    'The files this lot pulls, above the line first, skipping ones already pulled.'

    sides = eligible_rows(market, week, band)
    taken = set(seen)
    wanted_above = int(round(files * float(above_share)))
    picked: list[Mapping[str, Any]] = []
    for name, wanted in (("above", wanted_above), ("below", files - wanted_above)):
        free = [row for row in sides[name] if row["account_id"] not in taken]
        picked.extend(free[: max(0, wanted)])
    return [reviewed_row(market, row) for row in picked]


def refusal_for(
    market: Market, week: Any, band: Any, above_share: Any, files: Any
) -> str | None:
    'Why the desk will not pull this lot, in the words the receipt carries.'

    spec = market.spec
    if int(files) > int(spec["files_per_booking"]):
        return f"a booking takes at most {int(spec['files_per_booking'])} files"
    if int(files) < int(spec["smallest_lot"]):
        return f"the desk will not work a lot under {int(spec['smallest_lot'])} files"
    low, high = float(spec["above_share_low"]), float(spec["above_share_high"])
    if not low <= float(above_share) <= high:
        return (
            f"the desk pulls between {low:.2f} and {high:.2f} of a lot from one side "
            "of the line"
        )
    sides = eligible_rows(market, int(week), float(band))
    if not sides["above"] or not sides["below"]:
        return "that band holds no files on one side of the line"
    return None


def receipt(
    market: Market,
    receipt_id: str,
    week: int,
    band: float,
    above_share: float,
    files_charged: int,
    files_remaining: int,
    rows: Sequence[Mapping[str, Any]],
    refusal: str | None,
    sequence: int,
    previous: str,
) -> dict[str, Any]:
    body = {
        "market": market.market,
        "sequence": int(sequence),
        "receipt_id": str(receipt_id),
        "week": int(week),
        "band": float(band),
        "above_share": float(above_share),
        "files_charged": int(files_charged),
        "files_remaining": int(files_remaining),
        "rows_returned": len(rows),
        "refusal": refusal,
        "files": [dict(item) for item in rows],
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def read_receipts(workspace: Path, market: Market) -> list[dict[str, Any]]:
    'Every lot this campaign has been charged for, or why the file will not read.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the review receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("market") != market.market
        or not isinstance(raw.get("lots"), list)
    ):
        raise ValueError("the review receipts do not belong to this market")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["lots"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a review receipt is not a desk record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a review receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the review receipts are not in the order the desk wrote them")
        if entry.get("market") != market.market:
            raise ValueError("a review receipt belongs to another market")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a review receipt does not carry the desk seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["lots"]]


def opening_receipts(market: Market) -> list[dict[str, Any]]:
    'The lots the campaign was already charged for before this notebook.'

    entries: list[dict[str, Any]] = []
    for call in market.spec["opening_lots"]:
        entries.append(_charge(market, entries, dict(call)))
    return entries


def _charge(
    market: Market, entries: Sequence[Mapping[str, Any]], call: Mapping[str, Any]
) -> dict[str, Any]:
    'Serve one lot against the grant and write the receipt for it.'

    left = market.files_left(entries)
    asked = int(call["files"])
    refusal = refusal_for(market, call["week"], call["band"], call["above_share"], asked)
    if refusal is None and asked > left:
        refusal = f"the grant has only {left} files left"
    charged = max(0, min(asked, int(market.spec["files_per_booking"]), left))
    rows: list[dict[str, Any]] = []
    if refusal is None and charged:
        seen = [
            str(item["account_id"]) for entry in entries for item in entry.get("files", ())
        ]
        rows = lot_rows(
            market, int(call["week"]), float(call["band"]), float(call["above_share"]),
            charged, seen,
        )
        charged = len(rows)
    if not charged:
        refusal = refusal or "the grant has no files left"
    return receipt(
        market,
        str(call["receipt_id"]),
        int(call["week"]),
        float(call["band"]),
        float(call["above_share"]),
        charged,
        left - charged,
        rows,
        refusal,
        len(entries) + 1,
        entries[-1]["seal"] if entries else "",
    )


def lot_of(market: Market, entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The files one receipt returned.'

    return [dict(item) for item in entry.get("files") or ()]


def review(
    workspace: Path,
    market: Market,
    week: Any,
    band: Any,
    above_share: Any,
    files: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    "Pull one lot of files and append the desk's receipt to the campaign file."

    if not isinstance(week, int) or isinstance(week, bool):
        raise ValueError("week must be a whole run week of this campaign")
    if not isinstance(files, int) or isinstance(files, bool) or files < 1:
        raise ValueError("files must be a whole number of files, at least one")
    if not isinstance(band, (int, float)) or isinstance(band, bool) or band <= 0:
        raise ValueError("band must be a positive number of points either side of the line")
    if not isinstance(above_share, (int, float)) or isinstance(above_share, bool):
        raise ValueError("above_share must be the share of the lot pulled from above the line")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")
    if not 1 <= int(week) <= int(market.spec["run_weeks"]):
        raise ValueError(
            f"this campaign ran {int(market.spec['run_weeks'])} weekly scoring runs"
        )

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, market)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "rows": lot_of(market, entry),
                    "files_spent": market.files_spent(entries),
                    "files_left": market.files_left(entries),
                }
        made = _charge(
            market,
            entries,
            {
                "receipt_id": receipt_id,
                "week": int(week),
                "band": float(band),
                "above_share": float(above_share),
                "files": int(files),
            },
        )
        entries.append(made)
        pending = root / "review_receipts.pending"
        pending.write_text(
            json.dumps({"market": market.market, "lots": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": made,
            "ran": True,
            "rows": lot_of(market, made),
            "files_spent": market.files_spent(entries),
            "files_left": market.files_left(entries),
        }
