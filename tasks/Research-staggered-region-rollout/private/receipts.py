'The wave capacity service: what a booked region-week costs and returns.'

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

from . import world as w


_SEAL_KEY = hashlib.sha256(b"authored-wave-capacity-instrument-2026-05-11").digest()
_LOCK = threading.RLock()

REFUSALS = (
    "region already live",
    "holdback share outside the band",
    "week already full",
    "region under the order floor",
)


def _seal(body: Mapping[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, raw, hashlib.sha256).hexdigest()


def receipt_id(region: str, week: str) -> str:
    return f"{region.lower().replace(' ', '-')}-{week}"


def refusal_for(
    network: w.Network,
    ledger: Sequence[Mapping[str, Any]],
    region: str,
    week: str,
    holdback_share: int,
) -> str | None:
    'Why the wave board would hand this region-week back, if it would.'

    spec = network.spec
    item = network.region(region)
    low, high = (int(value) for value in spec["holdback_share_band"])
    if item.live_from is not None and str(item.live_from) <= str(w.shift(week, 6)):
        return REFUSALS[0]
    if not low <= int(holdback_share) <= high:
        return REFUSALS[1]
    if sum(1 for entry in ledger if str(entry["week"]) == str(week)) >= int(
        spec["region_weeks_per_week"]
    ):
        return REFUSALS[2]
    if int(item.orders_per_day) <= int(spec["minimum_orders_per_day"]):
        return REFUSALS[3]
    return None


def make_receipt(
    network: w.Network,
    ledger: Sequence[Mapping[str, Any]],
    region: str,
    week: str,
    holdback_share: int,
) -> dict[str, Any]:
    'One receipt for one region-week, served or handed back.'

    spec = network.spec
    refusal = refusal_for(network, ledger, region, week, holdback_share)
    charged = len(ledger) + 1
    body: dict[str, Any] = {
        "network": network.network,
        "sequence": charged,
        "receipt_id": receipt_id(region, week),
        "region": str(region),
        "week": str(week),
        "holdback_share": int(holdback_share),
        "region_weeks_charged": 1,
        "region_weeks_left": int(spec["region_weeks_granted"]) - charged,
        "refusal": refusal or "",
        "previous": str(ledger[-1]["seal"]) if ledger else "",
    }
    if refusal:
        body["days_returned"] = 0
        body["orders_returned"] = 0
    else:
        rows = w.booked_week_rows(network, region, week, int(holdback_share))
        body["days_returned"] = len({str(row["date"]) for row in rows})
        body["orders_returned"] = int(sum(int(row["orders"]) for row in rows))
    return dict(body, seal=_seal(body))


def history(network: w.Network, bookings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipts the wave board already charged this campaign for.'

    entries: list[dict[str, Any]] = []
    for booking in bookings:
        entries.append(
            make_receipt(
                network,
                entries,
                str(booking["region"]),
                str(booking["week"]),
                int(booking["holdback_share"]),
            )
        )
    return entries


def read_ledger(workspace: Path, network: w.Network) -> list[dict[str, Any]]:
    'Every region-week this campaign paid for, or a reason it will not read.'

    path = Path(workspace) / w.RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the wave receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("network") != network.network
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the wave receipts do not belong to this network")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a wave receipt is not a service record")
        identifier = entry.get("receipt_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("a wave receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the wave receipts are not in the order the board wrote them")
        if entry.get("network") != network.network:
            raise ValueError("a wave receipt belongs to another network")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a wave receipt does not carry the board's seal")
        seen.add(identifier)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def served(ledger: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The region-weeks the board actually ran, in the order it ran them.'

    return [dict(entry) for entry in ledger if not entry.get("refusal")]


def weeks_left(network: w.Network, ledger: Sequence[Mapping[str, Any]]) -> int:
    return int(network.spec["region_weeks_granted"]) - len(list(ledger))


def collect(
    workspace: Path,
    network: w.Network,
    region: Any,
    week: Any,
    holdback_share: Any,
) -> dict[str, Any]:
    'Book one region-week and append its receipt to the workspace ledger.'

    if not isinstance(region, str) or not region.strip():
        raise ValueError("region must name a metro on the rollout register")
    names = {item.name for item in network.regions}
    if region not in names:
        raise ValueError(f"{region} is not a metro on this network's register")
    if not isinstance(week, str) or week not in set(network.spec["bookable_weeks"]):
        raise ValueError(
            "week must be one of the weeks the wave board has left: "
            + ", ".join(network.spec["bookable_weeks"])
        )
    if not isinstance(holdback_share, int) or isinstance(holdback_share, bool):
        raise ValueError("holdback_share must be a whole number of percentage points")
    if not 0 <= holdback_share <= 100:
        raise ValueError("holdback_share must be a share of the metro's orders")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_ledger(root, network)
        identifier = receipt_id(region, week)
        for entry in entries:
            if entry["receipt_id"] == identifier:
                return {
                    "receipt": entry,
                    "ran": False,
                    "rows": [],
                    "region_weeks_left": weeks_left(network, entries),
                }
        if weeks_left(network, entries) < 1:
            raise ValueError(
                "the wave board granted "
                f"{network.spec['region_weeks_granted']} region-weeks and every one "
                "of them is charged"
            )
        made = make_receipt(network, entries, region, week, holdback_share)
        entries.append(made)
        pending = root / "wave_receipts.pending"
        pending.write_text(
            json.dumps({"network": network.network, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / w.RECEIPTS_FILE)
        rows = (
            w.booked_week_rows(network, region, week, int(holdback_share))
            if not made["refusal"]
            else []
        )
        return {
            "receipt": made,
            "ran": True,
            "rows": rows,
            "region_weeks_left": weeks_left(network, entries),
        }
