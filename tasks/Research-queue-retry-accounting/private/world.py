"The world behind the quote route's failure review, and the edge trace service."

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


VERSION_OLD = "2.3"
VERSION_NEW = "2.4"
VERSIONS = (VERSION_OLD, VERSION_NEW)
RECEIPT_FILE = "trace_receipts.json"


_SEAL_KEY = hashlib.sha256(b"authored-edge-trace-instrument-2026-09-27").digest()
_LOCK = threading.RLock()


_PROFILE = ((0, "3/10"), (40, "21/50"), (72, "3/5"), (86, "23/25"), (94, "1"),
            (104, "23/25"), (120, "31/50"), (150, "21/50"), (179, "3/10"))


def _fraction(value: Any) -> Fraction:
    return Fraction(str(value))


def _interpolate(points: Sequence[tuple[int, str]], index: int) -> Fraction:
    first, last = points[0], points[-1]
    if index <= first[0]:
        return _fraction(first[1])
    if index >= last[0]:
        return _fraction(last[1])
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:]):
        if left_x <= index <= right_x:
            span = right_x - left_x
            if span == 0:
                return _fraction(left_y)
            weight = Fraction(index - left_x, span)
            return _fraction(left_y) + weight * (_fraction(right_y) - _fraction(left_y))
    return _fraction(last[1])


def _wobble(*parts: Any, spread: int) -> Fraction:
    'A fixed per-minute wobble in [-spread, spread] parts per hundred.'

    key = ":".join(str(part) for part in parts).encode()
    digest = int(hashlib.sha256(key).hexdigest()[:8], 16)
    return Fraction(digest % (2 * spread + 1) - spread, 100)


def _days(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def _minute_label(day: str, block_start: str, offset: int) -> str:
    start = datetime.fromisoformat(f"{day}T{block_start}")
    return (start + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M")


@dataclass(frozen=True)
class Minute:
    'One minute of the service block, as the world ran it.'

    label: str
    day: str
    offset: int
    load: Fraction

    operations: Mapping[str, int]

    chain: Mapping[str, tuple[tuple[int, int, int, int], ...]]

    failed: Mapping[str, int]

    pools: Mapping[str, tuple[int, int, int]]

    pool_load: Mapping[str, tuple[int, int]]

    @property
    def customer_operations(self) -> int:
        return sum(self.operations.values())

    @property
    def failed_operations(self) -> int:
        return sum(self.failed.values())

    @property
    def spilled(self) -> int:
        return sum(entry[1] for entry in self.pools.values())

    @property
    def expired(self) -> int:
        return sum(entry[2] for entry in self.pools.values())

    def first_attempt_finals(self) -> int:
        'The 2.4 receipts written as a first attempt nobody retries.'

        return self.chain[VERSION_NEW][0][2] + self.expired


@dataclass(frozen=True)
class World:
    "One review window's traffic, client mix, probe spill and published surface."

    spec: Mapping[str, Any]
    minutes: tuple[Minute, ...]

    @property
    def review(self) -> str:
        return str(self.spec["review"])

    @property
    def days(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(minute.day for minute in self.minutes))

    @property
    def cap(self) -> int:
        return int(self.spec["retry_cap"])

    def minute(self, label: str) -> Minute | None:
        return _index(self).get(str(label))


    def rollup_rows(self, minute: Minute) -> list[dict[str, Any]]:
        'The receipts this minute wrote, grouped the way the export groups them.'

        rows: list[dict[str, Any]] = []

        def row(version: str, attempt: int | None, outcome: str,
                retryable: bool | None, receipts: int) -> None:
            if receipts:
                rows.append({
                    "minute": minute.label,
                    "client_version": version,
                    "attempt": attempt,
                    "outcome": outcome,
                    "retryable": retryable,
                    "receipts": int(receipts),
                })

        if minute.operations[VERSION_OLD]:
            failed = minute.failed[VERSION_OLD]
            row(VERSION_OLD, None, "ok", None, minute.operations[VERSION_OLD] - failed)
            row(VERSION_OLD, None, "error", None, failed)
        new = minute.chain[VERSION_NEW]
        spilled = minute.spilled
        expired = minute.expired
        for index, (attempts, ok, non_retryable, retried) in enumerate(new, start=1):
            extra_ok = spilled - expired if index == 1 else 0
            extra_final = expired if index == 1 else 0
            row(VERSION_NEW, index, "ok", None, ok + extra_ok)
            row(VERSION_NEW, index, "error", False, non_retryable + extra_final)
            row(VERSION_NEW, index, "error", True, retried)
        return rows

    def rollup(self) -> list[dict[str, Any]]:
        return [row for minute in self.minutes for row in self.rollup_rows(minute)]

    def counter_rows(self, minute: Minute) -> list[dict[str, Any]]:
        rows = []
        for pool in self.spec["pools"]:
            name = str(pool["name"])
            emitted, spilled, _expired = minute.pools[name]
            requests, backlog = minute.pool_load[name]
            rows.append({
                "minute": minute.label,
                "pool": name,
                "requests_handled": int(requests),
                "probes_emitted": int(emitted),
                "probes_spilled": int(spilled),
                "sink_backlog_ms": int(backlog),
            })
        return rows

    def counters(self) -> list[dict[str, Any]]:
        return [row for minute in self.minutes for row in self.counter_rows(minute)]

    def dashboard(self) -> list[dict[str, Any]]:
        'The daily error percentage the platform dashboard draws.'

        rows = []
        for day in self.days:
            receipts = 0
            errors = 0
            for minute in self.minutes:
                if minute.day != day:
                    continue
                for row in self.rollup_rows(minute):
                    receipts += int(row["receipts"])
                    if row["outcome"] == "error":
                        errors += int(row["receipts"])
            rows.append({
                "day": day,
                "receipts": receipts,
                "error_receipts": errors,
                "error_percent": round(100 * errors / receipts, 2) if receipts else 0.0,
            })
        return rows

    def context(self) -> dict[str, Any]:
        return _context(self)


    def trace(self, minute_label: str, pool: str) -> dict[str, Any]:
        "What one pool's edge rows say about a minute the archive still holds."

        minute = self.minute(minute_label)
        if minute is None:
            return {"probe_receipts": 0, "probe_errors": 0, "client_receipts": 0}
        emitted, spilled, expired = minute.pools[str(pool)]
        requests, _backlog = minute.pool_load[str(pool)]
        return {
            "probe_receipts": int(spilled),
            "probe_errors": int(expired),
            "client_receipts": int(requests) - int(emitted),
        }

    def edge_rows(self, minute_label: str, pool: str) -> list[dict[str, Any]]:
        "The pool's rows for that minute, grouped by source and outcome."

        minute = self.minute(minute_label)
        if minute is None:
            return []
        observed = self.trace(minute_label, pool)
        spilled = int(observed["probe_receipts"])
        expired = int(observed["probe_errors"])
        client = int(observed["client_receipts"])
        rows = []
        if spilled - expired:
            rows.append({"source": "probe", "client_version": VERSION_NEW, "attempt": 1,
                         "outcome": "ok", "retryable": None, "receipts": spilled - expired})
        if expired:
            rows.append({"source": "probe", "client_version": VERSION_NEW, "attempt": 1,
                         "outcome": "error", "retryable": False, "receipts": expired})
        total = sum(entry[0] for chain in minute.chain.values() for entry in chain)
        if total:
            for row in self.rollup_rows(minute):
                receipts = int(row["receipts"])
                if row["client_version"] == VERSION_NEW and row["attempt"] == 1:
                    if row["outcome"] == "ok":
                        receipts -= spilled - expired
                    elif row["retryable"] is False:
                        receipts -= expired
                taken = round(Fraction(receipts * client, total))
                if taken:
                    rows.append({
                        "source": "client",
                        "client_version": row["client_version"],
                        "attempt": row["attempt"],
                        "outcome": row["outcome"],
                        "retryable": row["retryable"],
                        "receipts": int(taken),
                    })
        return rows

    def retained_from(self) -> str:
        as_of = datetime.fromisoformat(str(self.spec["as_of"]))
        keep = as_of - timedelta(hours=int(self.spec["retention_hours"]))
        return keep.strftime("%Y-%m-%dT%H:%M")

    def retained(self, minute_label: str) -> bool:
        return str(minute_label) >= self.retained_from()

    def spilling_pools(self, minute_label: str) -> list[str]:
        minute = self.minute(minute_label)
        if minute is None:
            return []
        return [name for name, entry in sorted(minute.pools.items()) if entry[1] > 0]

    def open_traces(self) -> list[tuple[str, str]]:
        'Pool-minutes the archive still holds whose probe outcomes are unknown.'

        found = []
        for minute in self.minutes:
            if not self.retained(minute.label) or minute.first_attempt_finals() <= 0:
                continue
            if minute.chain[VERSION_NEW][0][0] == 0:


                continue
            for pool in self.spilling_pools(minute.label):
                found.append((minute.label, pool))
        return found


_INDEX: dict[str, dict[str, Minute]] = {}
_CONTEXT: dict[str, dict[str, Any]] = {}


def _index(world: World) -> dict[str, Minute]:
    key = world.review
    if key not in _INDEX:
        _INDEX[key] = {minute.label: minute for minute in world.minutes}
    return _INDEX[key]


def _context(world: World) -> dict[str, Any]:
    key = world.review
    if key not in _CONTEXT:
        spec = world.spec
        _CONTEXT[key] = {
            "review": world.review,
            "route": str(spec["route"]),
            "window": {"first_day": world.days[0], "last_day": world.days[-1],
                       "block_start": str(spec["block_start"]),
                       "minutes_per_day": int(spec["minutes_per_day"])},
            "as_of": str(spec["as_of"]),
            "archive": {
                "retained_from": world.retained_from(),
                "retention_hours": int(spec["retention_hours"]),
                "unit_cost": int(spec["unit_cost"]),
                "units_granted": int(spec["units_granted"]),
            },
            "pools": [{"name": str(pool["name"]), "probes_per_minute": int(pool["probes_per_minute"])}
                      for pool in spec["pools"]],
            "fleets": [{"name": str(fleet["name"]),
                        "share_percent": float(round(100 * _fraction(fleet["share"]), 1))}
                       for fleet in spec["fleets"]],
            "dashboard": world.dashboard(),
            "rollup": world.rollup(),
            "pool_counters": world.counters(),
        }
    return json.loads(json.dumps(_CONTEXT[key]))


def _chain(operations: int, failure: Fraction, final_share: Fraction,
           cap: int) -> tuple[tuple[int, int, int, int], ...]:
    'One attempt chain: (attempts, ok, non-retryable, retried) per attempt.'

    rows: list[tuple[int, int, int, int]] = []
    attempts = int(operations)
    for index in range(1, cap + 1):
        failures = round(failure * attempts)
        if index < cap:
            final = round(final_share * failures)
            retried = failures - final
        else:
            final = round(final_share * failures)
            retried = failures - final
        rows.append((attempts, attempts - failures, final, retried))
        attempts = retried if index < cap else 0
    return tuple(rows)


def _failed(chain: Sequence[tuple[int, int, int, int]], cap: int) -> int:
    'Operations that ran out of attempts or hit a failure nobody retries.'

    total = 0
    for index, (_attempts, _ok, final, retried) in enumerate(chain, start=1):
        total += final
        if index == cap:
            total += retried
    return total


def build(spec: Mapping[str, Any]) -> World:
    'Run six evenings of the quote route through the clients and the pools.'

    days = _days(spec["first_day"], len(spec["day_scale"]))
    block = int(spec["minutes_per_day"])
    cap = int(spec["retry_cap"])
    peak_operations = int(spec["peak_operations"])
    failure_low, failure_high = (_fraction(v) for v in spec["attempt_failure"])
    final_low, final_high = (_fraction(v) for v in spec["final_share"])
    expiry_low, expiry_high = (_fraction(v) for v in spec["probe_expiry"])
    spill_low, spill_high = (_fraction(v) for v in spec["spill_fraction"])
    minutes: list[Minute] = []

    for day_index, day in enumerate(days):
        scale = _fraction(spec["day_scale"][day_index])
        for offset in range(block):
            label = _minute_label(day, str(spec["block_start"]), offset)
            load = _interpolate(_PROFILE, offset) * scale
            wobble = _wobble(spec["review"], day, offset, spread=4)
            operations_total = max(1, round(peak_operations * load * (1 + wobble)))
            heat = min(Fraction(1), max(Fraction(0), (load - Fraction(11, 20)) / Fraction(9, 20)))
            failure = failure_low + (failure_high - failure_low) * heat
            final_share = final_low + (final_high - final_low) * heat

            new_share = Fraction(0)
            for fleet in spec["fleets"]:
                moved = fleet.get("moved_on")
                if moved is not None and day >= str(moved):
                    new_share += _fraction(fleet["share"])
            new_operations = round(operations_total * new_share)
            operations = {VERSION_OLD: operations_total - new_operations,
                          VERSION_NEW: new_operations}
            chain = {version: _chain(operations[version], failure, final_share, cap)
                     for version in VERSIONS}
            failed = {version: _failed(chain[version], cap) for version in VERSIONS}
            customer_attempts = sum(entry[0] for rows in chain.values() for entry in rows)

            pools: dict[str, tuple[int, int, int]] = {}
            pool_load: dict[str, tuple[int, int]] = {}
            for pool in spec["pools"]:
                name = str(pool["name"])
                emitted = int(pool["probes_per_minute"])
                threshold = int(pool["threshold"])
                share = _fraction(pool["traffic_share"])
                requests = round(share * customer_attempts) + emitted
                if requests > threshold:
                    over = Fraction(requests - threshold, threshold)
                    fraction = min(spill_high, spill_low + over * Fraction(3, 2))
                    spilled = round(fraction * emitted)
                    expiry = expiry_low + (expiry_high - expiry_low) * min(Fraction(1), over * 4)
                    expired = round(expiry * spilled)
                    backlog = 40 + round(600 * over)
                else:
                    spilled, expired, backlog = 0, 0, max(0, round(30 * Fraction(requests, threshold)) - 20)
                pools[name] = (emitted, int(spilled), int(expired))
                pool_load[name] = (int(requests), int(backlog))

            minutes.append(Minute(
                label=label, day=day, offset=offset, load=load,
                operations=operations, chain=chain, failed=failed,
                pools=pools, pool_load=pool_load,
            ))

    _INDEX.pop(str(spec["review"]), None)
    _CONTEXT.pop(str(spec["review"]), None)
    return World(spec=spec, minutes=tuple(minutes))


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(world: World, minute_label: str, pool: str, trace_id: str, sequence: int,
            previous: str = "") -> dict[str, Any]:
    body = {
        "review": world.review,
        "sequence": int(sequence),
        "trace_id": str(trace_id),
        "minute": str(minute_label),
        "pool": str(pool),
        "units": int(world.spec["unit_cost"]),
        "observed": world.trace(minute_label, pool),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def extend(world: World, entries: Sequence[Mapping[str, Any]],
           traces: Sequence[tuple[str, str]],
           ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    grown = [dict(entry) for entry in entries]
    for offset, (minute_label, pool) in enumerate(traces):
        sequence = len(grown) + 1
        label = ids[offset] if ids is not None else f"t-{sequence:03d}"
        grown.append(receipt(world, minute_label, pool, label, sequence,
                             grown[-1]["seal"] if grown else ""))
    return grown


def ledger_with(world: World, traces: Sequence[tuple[str, str]],
                ids: Sequence[str] | None = None) -> dict[str, Any]:
    return {"review": world.review, "entries": extend(world, [], traces, ids)}


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every trace unit this review has paid for, or a reason the ledger is broken.'

    path = Path(workspace) / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("the trace receipt file must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("review") != world.review
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the trace receipt file does not belong to this review")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a trace receipt is not a service record")
        trace_id = entry.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id or trace_id in seen:
            raise ValueError("a trace receipt has a missing or repeated trace id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the trace receipt order does not hold together")
        if entry.get("review") != world.review:
            raise ValueError("a trace receipt belongs to another review")
        if entry.get("units") != int(world.spec["unit_cost"]):
            raise ValueError("a trace receipt is not billed at the published rate")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a trace receipt does not carry the service seal")
        seen.add(trace_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def units_spent(entries: Sequence[Mapping[str, Any]]) -> int:
    return sum(int(entry["units"]) for entry in entries)


def collect(workspace: Path, world: World, minute_label: Any, pool: Any,
            trace_id: Any) -> dict[str, Any]:
    'Pull one pool-minute out of the edge archive, or say why it cannot be pulled.'

    minute_label, pool = str(minute_label or ""), str(pool or "")
    names = [str(entry["name"]) for entry in world.spec["pools"]]
    if pool not in names:
        raise ValueError("pool must be one of " + ", ".join(names))
    if not isinstance(trace_id, str) or not trace_id.strip() or len(trace_id) > 120:
        raise ValueError("trace_id must be a short non-empty label you choose")
    if world.minute(minute_label) is None:
        raise ValueError(f"{minute_label} is not a minute of the {world.review} window")
    if not world.retained(minute_label):
        raise ValueError(
            f"the edge archive holds rows from {world.retained_from()}; "
            f"nothing is retained for {minute_label}"
        )
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["trace_id"] == trace_id:
                if (entry["minute"], entry["pool"]) != (minute_label, pool):
                    raise ValueError("that trace id already names another pool-minute")
                return {
                    "receipt": entry,
                    "ran": False,
                    "units_spent": units_spent(entries),
                    "units_left": int(world.spec["units_granted"]) - units_spent(entries),
                }
        granted = int(world.spec["units_granted"])
        if units_spent(entries) + int(world.spec["unit_cost"]) > granted:
            raise ValueError(
                f"the review has spent all {granted} trace units granted this month"
            )
        made = receipt(world, minute_label, pool, trace_id, len(entries) + 1,
                       entries[-1]["seal"] if entries else "")
        entries.append(made)
        pending = root / "trace_receipts.pending"
        pending.write_text(
            json.dumps({"review": world.review, "entries": entries}, indent=2, sort_keys=True)
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
