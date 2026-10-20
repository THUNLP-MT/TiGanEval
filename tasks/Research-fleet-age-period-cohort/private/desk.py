'The inspection desk: what a booked day returns, and the receipt it writes.'

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence

from .world import (
    RECEIPTS_FILE,
    Region,
    day_in,
    half_year,
    month_key,
    month_label,
)


_SEAL_KEY = hashlib.sha256(b"authored-fleet-inspection-desk-2026-09-07").digest()
_LOCK = threading.RLock()


COVERAGE_MONTHS = 6.0


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def week_of(day: str) -> str:
    parsed = date.fromisoformat(str(day))
    year, week, _ = parsed.isocalendar()
    return f"{year}-W{week:02d}"


def days_charged(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["days_charged"]) for entry in entries)


def days_left(region: Region, entries: Sequence[Mapping[str, Any]]) -> int:
    return int(region.spec["days_granted"]) - days_charged(entries)


def day_used(entries: Sequence[Mapping[str, Any]], day: str) -> bool:
    return any(str(entry["day"]) == str(day) for entry in entries)


def week_full(region: Region, entries: Sequence[Mapping[str, Any]], day: str) -> bool:
    week = week_of(day)
    booked = sum(1 for entry in entries if week_of(str(entry["day"])) == week)
    return booked >= int(region.spec["days_per_week"])


def refusal_for(
    region: Region,
    entries: Sequence[Mapping[str, Any]],
    depot: str,
    builds: Sequence[str],
    age_band: Sequence[int],
    vans: int,
    day: str,
) -> str | None:
    "The desk's own reason for handing a booked day back, or None."

    if str(depot) not in region.depots:
        return "day_off_the_roster"
    if int(vans) > int(region.spec["vans_per_day"]):
        return "day_over_the_van_cap"
    build_count = len({str(name) for name in builds})
    if build_count < 2:
        return "day_single_build"
    if build_count > 2:
        return "day_too_many_builds"
    if day_used(entries, day) or week_full(region, entries, day):
        return "day_over_the_week_cap"
    least = int(region.spec["vans_in_service_minimum"])
    for name in {str(item) for item in builds}:
        if len(region.group(depot, [name], age_band, day)) < least:
            return "day_group_too_small"
    return None


REFUSAL_WORDS: Mapping[str, str] = {
    "day_off_the_roster": "that depot is not on the audit roster",
    "day_over_the_van_cap": "the day was written for more vans than an inspector covers",
    "day_single_build": "a day is booked against two build groups",
    "day_too_many_builds": "a day is booked against exactly two build groups",
    "day_over_the_week_cap": "that day is already worked or the week is full",
    "day_group_too_small": "the group holds fewer vans in service than a day needs",
}


def served_rows(
    region: Region,
    depot: str,
    builds: Sequence[str],
    age_band: Sequence[int],
    vans: int,
    day: str,
) -> list[dict[str, Any]]:
    'One walkaround a van, spread evenly over the group the booking names.'

    group = sorted(
        region.group(depot, builds, age_band, day),
        key=lambda van: (van.build_month, van.van_id),
    )
    if not group:
        return []
    wanted = min(int(vans), len(group))
    chosen = [group[(index * len(group)) // wanted] for index in range(wanted)]
    generator = random.Random(
        int(region.spec["draw"]) + 7919 * len(chosen) + month_key(str(day)[:7])
    )
    last_month = region.months[-1]
    factor = region.card_factor(depot, last_month)
    rows: list[dict[str, Any]] = []
    for van in chosen:
        age = region.age_of(van, day)
        months = min(
            COVERAGE_MONTHS,
            float(
                month_key(str(day)[:7]) - month_key(str(van.in_service_date)[:7]) + 1
            ),
        )
        rate = (
            float(region.spec["base_rate"])
            + float(region.spec["age_slope"]) * age
            + region.spec["period_effect"][last_month]
            + region.spec["build_effect"][van.build_month]
        )
        expected = rate * months * factor / 100.0
        whole = math.floor(expected)
        found = whole + (1 if generator.random() < expected - whole else 0)
        rows.append(
            {
                "van_id": van.van_id,
                "depot": str(depot),
                "build_month": van.build_month,
                "build_group": half_year(van.build_month),
                "age_months": age,
                "van_months": round(months, 3),
                "faults_found": int(found),
                "walkaround_ref": region.card_on(depot, last_month),
            }
        )
    return rows


def receipt_body(
    region: Region,
    depot: str,
    builds: Sequence[str],
    age_band: Sequence[int],
    vans: int,
    day: str,
    rows: Sequence[Mapping[str, Any]],
    refusal: str | None,
    receipt_id: str,
    charged: int,
    remaining: int,
) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt_id),
        "region": region.region,
        "day": str(day),
        "depot": str(depot),
        "builds": sorted({str(name) for name in builds}),
        "age_band": [int(age_band[0]), int(age_band[1])],
        "vans_asked": int(vans),
        "vans_returned": len(rows),
        "faults_returned": sum(int(row["faults_found"]) for row in rows),
        "van_months_returned": round(sum(float(row["van_months"]) for row in rows), 3),
        "walkaround_ref": region.card_on(depot, region.months[-1])
        if str(depot) in region.depots
        else "",
        "days_charged": 1,
        "days_remaining": int(remaining),
        "refusal": None if refusal is None else REFUSAL_WORDS[refusal],
        "observed": {"rows": [dict(row) for row in rows]},
    }


def book(
    region: Region,
    entries: Sequence[Mapping[str, Any]],
    depot: Any,
    builds: Sequence[str],
    age_band: Sequence[int],
    vans: Any,
    day: str,
    receipt_id: str,
) -> list[dict[str, Any]]:
    'The receipts with one more day on them, without touching any file.'

    held = [dict(entry) for entry in entries]
    refusal = refusal_for(region, held, str(depot), builds, age_band, int(vans), str(day))
    rows = (
        []
        if refusal
        else served_rows(region, str(depot), builds, age_band, int(vans), str(day))
    )
    body = receipt_body(
        region, depot, builds, age_band, int(vans), str(day), rows, refusal,
        receipt_id, 1, days_left(region, held) - 1,
    )
    held.append(seal_body(body, len(held) + 1, held[-1]["seal"] if held else ""))
    return held


def receipts_document(region: Region, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"region": region.region, "entries": [dict(entry) for entry in entries]}


def read_receipts(workspace: Path, region: Region) -> list[dict[str, Any]]:
    'Every day this region has been charged for, or a reason the file will not read.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the audit receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("region") != region.region
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the audit receipts do not belong to this region")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a receipt is not a desk record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the receipts are not in the order the desk wrote them")
        if entry.get("region") != region.region:
            raise ValueError("a receipt belongs to another region")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a receipt does not carry the inspection desk's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


_ALLOWED_BUILD_GROUPS = ("H1", "H2")


def collect(
    workspace: Path,
    region: Region,
    depot: Any,
    builds: Any,
    age_band: Any,
    vans: Any,
    day: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    'Send the inspector out for one day and append the receipt.'

    if not isinstance(depot, str) or not depot.strip():
        raise ValueError("depot must be the name of a depot on the audit roster")
    if isinstance(builds, str):
        builds = [builds]
    if not isinstance(builds, (list, tuple)) or not builds:
        raise ValueError("builds must be a list of build groups such as 2021-H2")
    groups = region.build_groups()
    for name in builds:
        if not isinstance(name, str) or name not in groups:
            raise ValueError(f"{name!r} is not a build group this region put on the road")
    if (
        not isinstance(age_band, (list, tuple))
        or len(age_band) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) for value in age_band)
        or age_band[0] < 0
        or age_band[0] > age_band[1]
    ):
        raise ValueError("age_band must be two whole months of age, lowest first")
    if not isinstance(vans, int) or isinstance(vans, bool) or vans <= 0:
        raise ValueError("vans must be a positive whole number of vans")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")
    try:
        parsed = date.fromisoformat(str(day))
    except (TypeError, ValueError):
        raise ValueError("day must be a calendar day the inspector can work, as YYYY-MM-DD") from None
    if parsed.isoweekday() > 5:
        raise ValueError("the inspector works Monday to Friday")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, region)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "days_charged": days_charged(entries),
                    "days_left": days_left(region, entries),
                }
        if days_left(region, entries) <= 0:
            raise ValueError(
                f"the audit was granted {region.spec['days_granted']} days and every one is charged"
            )
        entries = book(region, entries, depot, builds, age_band, vans, str(day), receipt_id)
        pending = root / (RECEIPTS_FILE + ".pending")
        pending.write_text(
            json.dumps(receipts_document(region, entries), indent=2) + "\n", encoding="utf-8"
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": entries[-1],
            "ran": True,
            "days_charged": days_charged(entries),
            "days_left": days_left(region, entries),
        }
