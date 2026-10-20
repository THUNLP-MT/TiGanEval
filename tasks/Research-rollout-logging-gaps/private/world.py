'The world behind the checkout-hint readout, and the archive rescan service.'

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


ARMS = ("control", "treatment")
BUCKETS = ("first", "returning")
RECEIPT_FILE = "audit_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-archive-rescan-instrument-2026-09-04").digest()
_LOCK = threading.RLock()


def _fraction(value: Any) -> Fraction:
    return Fraction(str(value))


def _days(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


@dataclass(frozen=True)
class World:
    "One readout's traffic, instrument behaviour and published surface."

    spec: Mapping[str, Any]
    days: tuple[str, ...]

    humans: Mapping[tuple[str, str, str], tuple[int, int]]

    crawlers: Mapping[tuple[str, str], int]

    shed: Mapping[tuple[str, str], int]

    @property
    def readout(self) -> str:
        return str(self.spec["readout"])

    def filtered(self, day: str, arm: str) -> bool:
        "Whether the crawler rule set was live on that arm's path that day."

        live = self.spec["filter_live"].get(arm)
        return live is not None and str(day) >= str(live)

    def crawlers_in_table(self, day: str, arm: str) -> int:
        if self.filtered(day, arm):
            return 0
        return int(self.crawlers.get((day, arm), 0))


    def table_row(self, day: str, arm: str, bucket: str) -> dict[str, Any]:
        sessions, purchases = self.humans[(day, arm, bucket)]
        shed = self._shed_for(day, arm, bucket)
        if bucket == "first":
            sessions += self.crawlers_in_table(day, arm)
        return {
            "day": day,
            "arm": arm,
            "visit": bucket,
            "sessions": int(sessions),
            "confirmations": int(purchases - shed),
            "crawler_rules": "live" if self.filtered(day, arm) else "off",
        }

    def _shed_for(self, day: str, arm: str, bucket: str) -> int:
        "The day's shed confirmations, split across buckets by volume."

        total = int(self.shed.get((day, arm), 0))
        if total <= 0:
            return 0
        first = self.humans[(day, arm, "first")][1]
        returning = self.humans[(day, arm, "returning")][1]
        if first + returning <= 0:
            return 0
        share = round(Fraction(total * first, first + returning))
        return int(share if bucket == "first" else total - share)

    def table(self) -> list[dict[str, Any]]:
        return [
            self.table_row(day, arm, bucket)
            for day in self.days
            for arm in ARMS
            for bucket in BUCKETS
        ]

    def counters(self) -> list[dict[str, Any]]:
        "The checkout queue's per-topic day rollups, with the shedding minutes."

        rows: list[dict[str, Any]] = []
        for day in self.days:
            for arm in ARMS:
                topic = str(self.spec["serving"][arm]["topic"])
                accepted = sum(
                    self.table_row(day, arm, bucket)["confirmations"] for bucket in BUCKETS
                )
                dropped = int(self.shed.get((day, arm), 0))
                row: dict[str, Any] = {
                    "day": day,
                    "topic": topic,
                    "accepted": accepted,
                    "dropped": dropped,
                }
                if dropped:
                    row["minutes_over_quota"] = _minutes(day, topic, dropped)
                rows.append(row)
        return rows

    def context(self) -> dict[str, Any]:
        'The machine-readable evidence the workspace publishes for this readout.'

        spec = self.spec
        return {
            "readout": self.readout,
            "window": {"first_day": self.days[0], "last_day": self.days[-1]},
            "as_of": str(spec["as_of"]),
            "gate": str(spec["gate"]),
            "serving": {arm: dict(spec["serving"][arm]) for arm in ARMS},
            "archive": {
                "retained_from": str(spec["retained_from"]),
                "unit_cost": 1,
                "units_granted": int(spec["units_granted"]),
            },
            "changes": [dict(entry) for entry in spec["changes"]],
            "sessions_by_day": self.table(),
            "checkout_queue": self.counters(),
        }


    def rescan(self, day: str, arm: str) -> dict[str, Any]:
        'Re-run the current crawler rule set over one retained day-slice.'

        return {"crawler_sessions": int(self.crawlers.get((str(day), str(arm)), 0))}

    def slice_is_open(self, day: str, arm: str) -> bool:
        'Whether a rescan of this slice could still change the readout.'

        day, arm = str(day), str(arm)
        if day not in self.days or arm not in ARMS:
            return False
        if day < str(self.spec["retained_from"]) or day > str(self.spec["as_of"]):
            return False
        return not self.filtered(day, arm) and int(self.crawlers.get((day, arm), 0)) > 0

    def open_slices(self) -> list[tuple[str, str]]:
        return [
            (day, arm) for day in self.days for arm in ARMS if self.slice_is_open(day, arm)
        ]


def _minutes(day: str, topic: str, dropped: int) -> list[dict[str, Any]]:
    "The minute counters behind one day's shed total, oldest first."

    digest = int(hashlib.sha256(f"{day}:{topic}".encode()).hexdigest()[:8], 16)
    count = 3 + digest % 3
    rows: list[dict[str, Any]] = []
    left = dropped
    for index in range(count):
        share = left if index == count - 1 else round(Fraction(left, count - index))
        minute = f"{day}T{19 + index // 4:02d}:{(digest + 7 * index) % 60:02d}"
        rows.append({"minute": minute, "dropped": int(share)})
        left -= int(share)
    return [row for row in rows if row["dropped"]]


def build(spec: Mapping[str, Any]) -> World:
    'Run the router, the crawler surge and the queue for one readout window.'

    days = tuple(_days(spec["first_day"], len(spec["new_visits"])))
    shares = [_fraction(value) for value in spec["treated_share"]]
    first_rate = _fraction(spec["first_conversion"])
    return_rate = _fraction(spec["return_conversion"])
    effect = _fraction(spec["effect"])
    pinned = 0
    unpinned = int(spec["visitors_before"])
    humans: dict[tuple[str, str, str], tuple[int, int]] = {}
    crawlers: dict[tuple[str, str], int] = {}
    shed: dict[tuple[str, str], int] = {}

    for index, day in enumerate(days):
        share = shares[index]
        returns = int(spec["return_visits"][index])
        pool = pinned + unpinned
        from_pinned = round(Fraction(returns * pinned, pool)) if pool else 0
        from_unpinned = returns - from_pinned
        drawn_in = round(from_unpinned * share)
        pinned += drawn_in
        unpinned -= drawn_in
        returning = {"treatment": from_pinned + drawn_in, "control": from_unpinned - drawn_in}

        arrivals = int(spec["new_visits"][index])
        new_treated = round(arrivals * share)
        first = {"treatment": new_treated, "control": arrivals - new_treated}
        pinned += new_treated
        unpinned += arrivals - new_treated

        for arm in ARMS:
            lift = effect if arm == "treatment" else Fraction(0)
            humans[(day, arm, "first")] = (
                first[arm],
                round(first[arm] * (first_rate + lift)),
            )
            humans[(day, arm, "returning")] = (
                returning[arm],
                round(returning[arm] * (return_rate + lift)),
            )

        visits = int(spec["crawler_visits"].get(day, 0))
        if visits:
            treated = round(visits * share)
            crawlers[(day, "treatment")] = treated
            crawlers[(day, "control")] = visits - treated
        for arm in ARMS:
            amount = int(spec["shed"].get(day, {}).get(arm, 0))
            if amount:
                shed[(day, arm)] = amount

    return World(spec=spec, days=days, humans=humans, crawlers=crawlers, shed=shed)


def totals(world: World) -> dict[str, dict[str, int]]:
    'Per arm: the real people who arrived for the first time, and their buys.'

    result: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        sessions = sum(world.humans[(day, arm, "first")][0] for day in world.days)
        purchases = sum(world.humans[(day, arm, "first")][1] for day in world.days)
        result[arm] = {"sessions": sessions, "purchases": purchases}
    return result


def observed_first(world: World) -> dict[str, dict[str, int]]:
    'Per arm: what the published table shows for first-visit sessions.'

    result: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        rows = [world.table_row(day, arm, "first") for day in world.days]
        result[arm] = {
            "sessions": sum(row["sessions"] for row in rows),
            "confirmations": sum(row["confirmations"] for row in rows),
            "crawler_sessions": sum(world.crawlers_in_table(day, arm) for day in world.days),
            "shed": sum(int(world.shed.get((day, arm), 0)) for day in world.days),
        }
    return result


def supported_cohort(world: World) -> dict[str, dict[str, int | Fraction]]:
    'The point cohort reproducible from the published evidence.'

    result: dict[str, dict[str, int | Fraction]] = {}
    for arm in ARMS:
        sessions = 0
        confirmations = Fraction(0)
        for day in world.days:
            first = world.table_row(day, arm, "first")
            returning = world.table_row(day, arm, "returning")
            sessions += int(first["sessions"]) - world.crawlers_in_table(day, arm)
            confirmations += int(first["confirmations"])
            dropped = int(world.shed.get((day, arm), 0))
            accepted = int(first["confirmations"]) + int(returning["confirmations"])
            if dropped and accepted:
                confirmations += Fraction(dropped * int(first["confirmations"]), accepted)
        result[arm] = {"sessions": sessions, "confirmations": confirmations}
    return result


def reference(world: World) -> dict[str, Any]:
    'The readout this world supports, in the shape the notebook returns.'

    point = supported_cohort(world)
    seen = observed_first(world)
    cohort = {
        arm: {
            "sessions": int(point[arm]["sessions"]),
            "confirmations": float(point[arm]["confirmations"]),
        }
        for arm in ARMS
    }
    rate = {
        arm: Fraction(point[arm]["confirmations"], point[arm]["sessions"]) for arm in ARMS
    }
    lift = rate["treatment"] - rate["control"]
    clean = {arm: seen[arm]["sessions"] - seen[arm]["crawler_sessions"] for arm in ARMS}
    low = Fraction(seen["treatment"]["confirmations"], clean["treatment"]) - Fraction(
        seen["control"]["confirmations"] + seen["control"]["shed"], clean["control"]
    )
    high = Fraction(
        seen["treatment"]["confirmations"] + seen["treatment"]["shed"], clean["treatment"]
    ) - Fraction(seen["control"]["confirmations"], clean["control"])
    gate = _fraction(world.spec["gate"])
    return {
        "cohort": cohort,
        "lift": float(lift),
        "lift_bounds": [float(low), float(high)],
        "decision": "expand" if low >= gate else "hold",
        "exact": {"lift": lift, "low": low, "high": high, "gate": gate},
    }


def pooled_signature(world: World) -> dict[str, int]:
    'What the table gives for every session of the window, arm by arm.'

    return {
        arm: sum(
            world.table_row(day, arm, bucket)["sessions"]
            for day in world.days
            for bucket in BUCKETS
        )
        for arm in ARMS
    }


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    world: World,
    day: str,
    arm: str,
    scan_id: str,
    sequence: int,
    previous: str = "",
) -> dict[str, Any]:
    body = {
        "readout": world.readout,
        "sequence": int(sequence),
        "scan_id": str(scan_id),
        "day": str(day),
        "arm": str(arm),
        "units": int(world.spec["unit_cost"]),
        "observed": world.rescan(day, arm),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def empty_stream(world: World) -> dict[str, Any]:
    return {"readout": world.readout, "entries": []}


def extend(
    world: World,
    entries: Sequence[Mapping[str, Any]],
    slices: Sequence[tuple[str, str]],
    ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    'The stream with one more rescan per named slice, keeping the chain.'

    grown = [dict(entry) for entry in entries]
    for offset, (day, arm) in enumerate(slices):
        sequence = len(grown) + 1
        label = ids[offset] if ids is not None else f"scan-{sequence:02d}"
        grown.append(
            receipt(world, day, arm, label, sequence, grown[-1]["seal"] if grown else "")
        )
    return grown


def stream_with(
    world: World,
    slices: Sequence[tuple[str, str]],
    ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    'A receipt stream holding one rescan per named slice, in order.'

    return {"readout": world.readout, "entries": extend(world, [], slices, ids)}


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every rescan this readout has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the rescan receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("readout") != world.readout
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the rescan receipt file does not belong to this readout")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a rescan receipt is not a service record")
        scan_id = entry.get("scan_id")
        if not isinstance(scan_id, str) or not scan_id or scan_id in seen:
            raise ValueError("a rescan receipt has a missing or repeated scan id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the rescan receipt order does not hold together")
        if entry.get("readout") != world.readout:
            raise ValueError("a rescan receipt belongs to another readout")
        if entry.get("units") != int(world.spec["unit_cost"]):
            raise ValueError("a rescan receipt is not billed at the published rate")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a rescan receipt does not carry the service seal")
        seen.add(scan_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def units_spent(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["units"]) for entry in entries)


def collect(workspace: Path, world: World, day: Any, arm: Any, scan_id: Any) -> dict[str, Any]:
    'Run one archive rescan and append its receipt, or say why it cannot run.'

    day, arm = str(day or ""), str(arm or "")
    if arm not in ARMS:
        raise ValueError("arm must be control or treatment")
    if not isinstance(scan_id, str) or not scan_id.strip() or len(scan_id) > 120:
        raise ValueError("scan_id must be a short non-empty label you choose")
    if day not in world.days:
        raise ValueError(f"{day} is not a day of the {world.readout} window")
    if day < str(world.spec["retained_from"]):
        raise ValueError(
            f"the archive holds raw ingest from {world.spec['retained_from']}; "
            f"nothing is retained for {day}"
        )
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["scan_id"] == scan_id:
                if (entry["day"], entry["arm"]) != (day, arm):
                    raise ValueError("that scan id already names another slice")
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(entries),
                    "units_left": int(world.spec["units_granted"]) - units_spent(entries),
                }
        granted = int(world.spec["units_granted"])
        if units_spent(entries) + int(world.spec["unit_cost"]) > granted:
            raise ValueError(
                f"the readout has spent all {granted} rescan units granted this month"
            )
        made = receipt(
            world, day, arm, scan_id, len(entries) + 1, entries[-1]["seal"] if entries else ""
        )
        entries.append(made)
        pending = root / "audit_receipts.pending"
        pending.write_text(
            json.dumps({"readout": world.readout, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPT_FILE)
        return {
            "receipt": made,
            "ran": True,
            "units_spent": units_spent(entries),
            "units_left": granted - units_spent(entries),
        }
