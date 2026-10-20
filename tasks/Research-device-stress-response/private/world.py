'The world behind the QR-40 burst qualification, and the chamber desk.'

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


RECEIPTS_FILE = "session_receipts.json"
BLOCK_LABEL = "DWB-200"
RESULTS = ("leak", "hold")


_SEAL_KEY = hashlib.sha256(b"authored-chamber-desk-instrument-2026-04-12").digest()
_LOCK = threading.RLock()


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def logistic(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def logit(value: float) -> float:
    return math.log(value / (1.0 - value))


def leak_chance(spec: Mapping[str, Any], pressure: float, dwell_min: int) -> float:
    'The chance one unit leaks at this pressure under this hold.'

    shift = 0.0 if int(dwell_min) >= int(spec["plan_hold_min"]) else float(spec["short_hold_bar"])
    return logistic((float(pressure) - shift - float(spec["p50_bar"])) / float(spec["slope_bar"]))


def crossing_of(spec: Mapping[str, Any], dwell_min: int) -> float:
    'The pressure at which one in ten leak under this hold.'

    shift = 0.0 if int(dwell_min) >= int(spec["plan_hold_min"]) else float(spec["short_hold_bar"])
    return float(spec["p50_bar"]) + shift + float(spec["slope_bar"]) * logit(
        float(spec["target_fraction"])
    )


def _spread(total: int, weights: Sequence[float]) -> list[int]:
    'Split one whole number of leaks across cells, largest remainder first.'

    if total <= 0 or not weights:
        return [0] * len(weights)
    scale = sum(weights)
    if scale <= 0:
        return [0] * len(weights)
    raw = [total * float(weight) / scale for weight in weights]
    counts = [int(math.floor(value)) for value in raw]
    left = total - sum(counts)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - counts[i]), i))
    for index in order[:left]:
        counts[index] += 1
    return counts


_JITTER = (0.0, 0.1, -0.1, 0.0, 0.1, -0.1, 0.2, -0.2)


@dataclass(frozen=True)
class World:
    'One qualification lot: its batches, its benches and its console.'

    spec: Mapping[str, Any]

    batches: Mapping[str, Mapping[str, Any]]

    @property
    def lot(self) -> str:
        return str(self.spec["lot"])

    @property
    def span_bar(self) -> float:
        return float(self.spec["span_bar"])

    def scale_of(self, bench: str) -> float:
        return float(self.spec["benches"][str(bench)])

    def true_bar(self, cartridge: str) -> float:
        return float(self.spec["cartridges"][str(cartridge)])

    def console(self, bench: str, pressure: float, index: int = 0) -> float:
        "What the bench's console writes for one unit at this pressure."

        raw = float(pressure) * self.scale_of(bench) + _JITTER[index % len(_JITTER)]
        return round(min(raw, self.span_bar), 1)

    def block_readings(self, bench: str, batch_id: str) -> list[float]:
        "The dead-weight block as this bench read it at a batch's two ends."

        block = float(self.spec["block_bar"])
        drift = float(self.spec["block_drift_bar"])
        seed = sum(ord(letter) for letter in str(batch_id)) % 3
        offsets = (drift, -drift) if seed != 1 else (-drift, drift)
        return [
            round(min(block * self.scale_of(bench) + offset, self.span_bar), 1)
            for offset in offsets
        ]


    def run_rows(self) -> list[dict[str, Any]]:
        'One row per unit the qualification put on a bench, block checks included.'

        rows: list[dict[str, Any]] = []
        for batch_id in sorted(self.batches):
            batch = self.batches[batch_id]
            bench = str(batch["bench"])
            dwell = int(batch["dwell_min"])
            block = self.block_readings(bench, batch_id)
            rows.append(
                {
                    "unit_id": f"{batch_id}-000",
                    "batch": batch_id,
                    "bench": bench,
                    "cartridge": BLOCK_LABEL,
                    "reading_bar": block[0],
                    "dwell_min": 0,
                    "result": "block",
                }
            )
            for cartridge in sorted(batch["cells"], key=self.true_bar):
                units = int(batch["cells"][cartridge])
                leaks = int(batch["leaks"][cartridge])
                pressure = self.true_bar(cartridge)
                for index in range(units):
                    rows.append(
                        {
                            "unit_id": f"{batch_id}-{index + 1:03d}-{cartridge}",
                            "batch": batch_id,
                            "bench": bench,
                            "cartridge": cartridge,
                            "reading_bar": self.console(bench, pressure, index),
                            "dwell_min": dwell,
                            "result": "leak" if index < leaks else "hold",
                        }
                    )
            rows.append(
                {
                    "unit_id": f"{batch_id}-999",
                    "batch": batch_id,
                    "bench": bench,
                    "cartridge": BLOCK_LABEL,
                    "reading_bar": block[1],
                    "dwell_min": 0,
                    "result": "block",
                }
            )
        return rows

    def bench_sheet_rows(self) -> list[dict[str, Any]]:
        "The bench sheet: each batch's bench, sticker span and two block readings."

        rows = []
        for batch_id in sorted(self.batches):
            bench = str(self.batches[batch_id]["bench"])
            block = self.block_readings(bench, batch_id)
            rows.append(
                {
                    "batch": batch_id,
                    "bench": bench,
                    "sticker_span_bar": self.span_bar,
                    "block_bar": float(self.spec["block_bar"]),
                    "block_readings_bar": block,
                    "dwell_min": int(self.batches[batch_id]["dwell_min"]),
                }
            )
        return rows

    def review_days(self) -> list[str]:
        return days_from(self.spec["first_review_day"], int(self.spec["review_day_count"]))

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "lot": self.lot,
            "family": str(spec["family"]),
            "build_month": str(spec["build_month"]),
            "plan_hold_min": int(spec["plan_hold_min"]),
            "target_fraction": float(spec["target_fraction"]),
            "sticker_span_bar": self.span_bar,
            "block_bar": float(spec["block_bar"]),
            "cartridges_on_the_shelf": sorted(spec["cartridges"]),
            "benches": sorted(spec["benches"]),
            "bench_out_of_service": {
                bench: list(window) for bench, window in spec["bench_out"].items()
            },
            "budget": {
                "chamber_hours_granted": float(spec["hours_granted"]),
                "hours_at_the_plan_hold": float(spec["hold_hours"][str(spec["plan_hold_min"])]),
                "hours_at_the_short_hold": float(
                    spec["hold_hours"][str(spec["short_hold_min"])]
                ),
                "ports_per_session": int(spec["ports"]),
                "closes_on": str(spec["closes_on"]),
            },
            "stores": {batch: int(units) for batch, units in sorted(spec["stores"].items())},
            "review_days": self.review_days(),
            "bench_sheet": self.bench_sheet_rows(),
            "runs": self.run_rows(),
        }


    def hours_charged(self, dwell_min: int) -> float:
        table = self.spec["hold_hours"]
        return float(table.get(str(int(dwell_min)), table[str(self.spec["plan_hold_min"])]))

    def hours_spent(self, stream: Sequence[Mapping[str, Any]]) -> float:
        return round(sum(float(item["hours_charged"]) for item in stream), 3)

    def hours_left(self, stream: Sequence[Mapping[str, Any]]) -> float:
        return round(float(self.spec["hours_granted"]) - self.hours_spent(stream), 3)

    def stock_left(self, stream: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        left = {batch: int(units) for batch, units in self.spec["stores"].items()}
        for item in stream:
            batch = str(item.get("batch") or "")
            if batch in left:
                left[batch] -= int(item.get("units_returned") or 0)
        return left

    def served_on(self, stream: Sequence[Mapping[str, Any]]) -> str | None:
        days = self.review_days()
        index = len(stream)
        return days[index] if index < len(days) else None

    def bench_is_out(self, bench: str, day: str) -> bool:
        window = self.spec["bench_out"].get(str(bench))
        return bool(window) and str(window[0]) <= str(day) <= str(window[1])


def build(spec: Mapping[str, Any]) -> World:
    'Run every batch of one qualification through the bench and the console.'

    batches: dict[str, dict[str, Any]] = {}


    per_cartridge: dict[str, list[tuple[str, int, float]]] = {}
    for batch_id, batch in spec["batches"].items():
        dwell = int(batch["dwell_min"])
        for cartridge, units in batch["cells"].items():
            chance = leak_chance(spec, float(spec["cartridges"][cartridge]), dwell)
            per_cartridge.setdefault(cartridge, []).append((batch_id, int(units), chance))
    leaks: dict[tuple[str, str], int] = {}
    for cartridge, cells in per_cartridge.items():
        expected = sum(units * chance for _batch, units, chance in cells)
        weights = [units * chance for _batch, units, chance in cells]
        for (batch_id, _units, _chance), count in zip(cells, _spread(int(round(expected)), weights)):
            leaks[(batch_id, cartridge)] = int(count)
    for batch_id, batch in spec["batches"].items():
        batches[batch_id] = {
            "bench": str(batch["bench"]),
            "dwell_min": int(batch["dwell_min"]),
            "cells": {name: int(units) for name, units in batch["cells"].items()},
            "leaks": {
                name: min(int(leaks[(batch_id, name)]), int(units))
                for name, units in batch["cells"].items()
            },
        }
    return World(spec=spec, batches=batches)


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def _booked_units(
    world: World, stream: Sequence[Mapping[str, Any]], cartridge: str, dwell_min: int
) -> int:
    return sum(
        int(item["units_returned"])
        for item in stream
        if item.get("cartridge") == cartridge and int(item.get("dwell_min", 0)) == int(dwell_min)
    )


def session_results(
    world: World,
    stream: Sequence[Mapping[str, Any]],
    cartridge: str,
    dwell_min: int,
    units: int,
) -> list[str]:
    'Leak or hold for each unit of one session, carried on from earlier ones.'

    chance = leak_chance(world.spec, world.true_bar(cartridge), dwell_min)
    already = _booked_units(world, stream, cartridge, dwell_min)
    before = int(round(already * chance))
    after = int(round((already + int(units)) * chance))
    made = max(0, min(int(units), after - before))
    return ["leak"] * made + ["hold"] * (int(units) - made)


def receipt(
    world: World,
    *,
    booking_id: str,
    sequence: int,
    previous: str,
    bench: str,
    batch: str,
    cartridge: str,
    dwell_min: int,
    units_asked: int,
    readings: Sequence[float],
    results: Sequence[str],
    block: Sequence[float],
    hours_charged: float,
    hours_left_after: float,
    served_on: str,
    refusal: str,
) -> dict[str, Any]:
    body = {
        "lot": world.lot,
        "sequence": int(sequence),
        "booking_id": str(booking_id),
        "bench": str(bench),
        "batch": str(batch),
        "cartridge": str(cartridge),
        "dwell_min": int(dwell_min),
        "units_asked": int(units_asked),
        "units_returned": len(list(results)),
        "readings_bar": [float(item) for item in readings],
        "results": [str(item) for item in results],
        "block_readings_bar": [float(item) for item in block],
        "hours_charged": float(hours_charged),
        "hours_left_after": float(hours_left_after),
        "served_on": str(served_on),
        "refusal": str(refusal),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def opening_stream(world: World) -> list[dict[str, Any]]:
    'The receipts the review already carries before anybody books anything.'

    entries: list[dict[str, Any]] = []
    for booking in world.spec["opening_bookings"]:
        entries.append(_serve(world, entries, dict(booking)))
    return entries


def _serve(
    world: World, stream: Sequence[Mapping[str, Any]], booking: Mapping[str, Any]
) -> dict[str, Any]:
    'One session as the chamber desk serves it onto an existing stream.'

    bench = str(booking["bench"])
    batch = str(booking["batch"])
    cartridge = str(booking["cartridge"])
    dwell = int(booking["dwell_min"])
    asked = int(booking["units"])
    booking_id = str(booking["booking_id"])
    day = world.served_on(stream) or world.review_days()[-1]
    charged = world.hours_charged(dwell)

    refusal = ""
    if asked > int(world.spec["ports"]) or asked < 1:
        refusal = f"the chamber holds {int(world.spec['ports'])} ports; the sheet asked for {asked}"
    elif world.bench_is_out(bench, day):
        window = world.spec["bench_out"][bench]
        refusal = f"{bench} is out of service from {window[0]} to {window[1]}"
    elif cartridge not in world.spec["cartridges"]:
        refusal = f"{cartridge} is not a cartridge the shop holds"
    elif world.stock_left(stream).get(batch, 0) < asked:
        refusal = (
            f"stores hold {world.stock_left(stream).get(batch, 0)} units of {batch} "
            f"and the sheet asked for {asked}"
        )

    if refusal:
        readings: list[float] = []
        results: list[str] = []
    else:
        results = session_results(world, stream, cartridge, dwell, asked)
        pressure = world.true_bar(cartridge)
        readings = [world.console(bench, pressure, index) for index in range(asked)]
    spent = world.hours_spent(stream) + charged
    return receipt(
        world,
        booking_id=booking_id,
        sequence=len(stream) + 1,
        previous=stream[-1]["seal"] if stream else "",
        bench=bench,
        batch=batch,
        cartridge=cartridge,
        dwell_min=dwell,
        units_asked=asked,
        readings=readings,
        results=results,
        block=world.block_readings(bench, booking_id),
        hours_charged=charged,
        hours_left_after=round(float(world.spec["hours_granted"]) - spent, 3),
        served_on=day,
        refusal=refusal,
    )


def extend(
    world: World, stream: Sequence[Mapping[str, Any]], bookings: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The same stream with more sessions served onto the end of it.'

    grown = [dict(item) for item in stream]
    for booking in bookings:
        grown.append(_serve(world, grown, booking))
    return grown


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every session this review has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the receipt stream must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("lot") != world.lot
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the receipt stream does not belong to this lot")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a chamber receipt is not a desk record")
        booking_id = entry.get("booking_id")
        if not isinstance(booking_id, str) or not booking_id or booking_id in seen:
            raise ValueError("a chamber receipt has a missing or repeated booking id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the chamber receipts are not in the order the desk wrote them")
        if entry.get("lot") != world.lot:
            raise ValueError("a chamber receipt belongs to another lot")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a chamber receipt does not carry the desk seal")
        seen.add(booking_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def collect(
    workspace: Path,
    world: World,
    bench: Any,
    batch: Any,
    cartridge: Any,
    dwell_min: Any,
    units: Any,
    booking_id: Any,
) -> dict[str, Any]:
    'Serve one session and append its receipt to the workspace stream.'

    if not isinstance(units, int) or isinstance(units, bool):
        raise ValueError("units must be a whole number of couplings")
    if not isinstance(dwell_min, int) or isinstance(dwell_min, bool):
        raise ValueError("dwell_min must be a whole number of minutes")
    if str(dwell_min) not in world.spec["hold_hours"]:
        holds = ", ".join(sorted(world.spec["hold_hours"], key=int))
        raise ValueError(f"the chamber runs these holds only: {holds} minutes")
    if not isinstance(booking_id, str) or not booking_id.strip() or len(booking_id) > 120:
        raise ValueError("booking_id must be a short non-empty label you choose")
    if not isinstance(bench, str) or bench not in world.spec["benches"]:
        raise ValueError("bench must name one of the qualification benches")
    if not isinstance(batch, str) or not batch.strip():
        raise ValueError("batch must name a coupling batch the shop holds")
    if not isinstance(cartridge, str) or not cartridge.strip():
        raise ValueError("cartridge must name a pressure cartridge")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["booking_id"] == booking_id:
                same = (
                    entry["bench"] == bench
                    and entry["batch"] == batch
                    and entry["cartridge"] == cartridge
                    and int(entry["dwell_min"]) == dwell_min
                    and int(entry["units_asked"]) == units
                )
                if not same:
                    raise ValueError("that booking id already names another session")
                return {
                    "receipt": entry,
                    "ran": False,
                    "hours_spent": world.hours_spent(entries),
                    "hours_left": world.hours_left(entries),
                    "stores_left": world.stock_left(entries),
                }
        charged = world.hours_charged(dwell_min)
        if world.hours_left(entries) < charged - 1e-9:
            raise ValueError(
                f"this session costs {charged:g} chamber hours and the review has "
                f"{world.hours_left(entries):g} left of the "
                f"{float(world.spec['hours_granted']):g} the plan granted"
            )
        if world.served_on(entries) is None:
            raise ValueError(
                f"the review's days run out on {world.review_days()[-1]}; there is no day left"
            )
        made = _serve(
            world,
            entries,
            {
                "booking_id": booking_id,
                "bench": bench,
                "batch": batch,
                "cartridge": cartridge,
                "dwell_min": dwell_min,
                "units": units,
            },
        )
        entries.append(made)
        pending = root / "session_receipts.pending"
        pending.write_text(
            json.dumps({"lot": world.lot, "entries": entries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": made,
            "ran": True,
            "hours_spent": world.hours_spent(entries),
            "hours_left": world.hours_left(entries),
            "stores_left": world.stock_left(entries),
        }
