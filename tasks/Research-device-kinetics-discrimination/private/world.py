'The world behind the EM-9 soak campaign, and the chamber desk.'

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence


RECEIPTS_FILE = "soak_receipts.json"
TRACE_FILE = "project_records/soak_traces.csv"
REFERENCE_MODULE = "REF-20"
UNIT_SOURCES = ("trace_export", "receipt")


INCOMING_SHEET_COLUMNS = (
    "module_id",
    "lot",
    "rack",
    "drive_a",
    "incoming_mw",
    "started_on",
)


_SEAL_KEY = hashlib.sha256(b"authored-soak-chamber-desk-2026-03-09").digest()
_LOCK = threading.RLock()


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shape(kind: str, constant: float, hours: float) -> float:
    'The loss one catalogue shape puts at `hours` of accumulated soak.'

    hours = max(float(hours), 0.0)
    if kind == "power":
        return hours ** float(constant)
    if kind == "logarithmic":
        return math.log1p(hours / float(constant))
    if kind == "saturating":
        return 1.0 - math.exp(-hours / float(constant))
    if kind == "linear":
        return hours / float(constant)
    raise ValueError(f"unknown decay shape: {kind}")


def drive_factor(form: str, parameter: float, drive_a: float, field_drive_a: float) -> float:
    'How much faster one law says a module ages at this drive.'

    if form == "exponential":
        return math.exp(float(parameter) * (float(drive_a) - float(field_drive_a)))
    if form == "power":
        return (float(drive_a) / float(field_drive_a)) ** float(parameter)
    raise ValueError(f"unknown drive form: {form}")


def temperature_factor(ten_degree: float, temp_c: float, hold_temp_c: float) -> float:
    return float(ten_degree) ** ((float(temp_c) - float(hold_temp_c)) / 10.0)


CATALOGUE_FIELDS = (
    "time_shape",
    "shape_constant",
    "drive_form",
    "drive_constant",
    "ten_degree_factor",
)


def build_catalogue(entries: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    "One campaign's catalogue, checked to carry every field a law is read with."

    out: dict[str, dict[str, Any]] = {}
    for name, entry in entries.items():
        missing = [field for field in CATALOGUE_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"{name} carries no {', '.join(missing)}")
        shape(str(entry["time_shape"]), float(entry["shape_constant"]), 1.0)
        drive_factor(str(entry["drive_form"]), float(entry["drive_constant"]), 1.0, 1.0)
        out[str(name)] = {field: entry[field] for field in CATALOGUE_FIELDS}
    return out


@dataclass(frozen=True)
class World:
    'One soak campaign: its modules, its racks, its meter and its desk.'

    spec: Mapping[str, Any]

    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def full_scale_mw(self) -> float:
        return float(self.spec["meter_full_scale_mw"])

    @property
    def read_noise_mw(self) -> float:
        return float(self.spec["read_noise_mw"])

    @property
    def field_drive_a(self) -> float:
        return float(self.spec["field_drive_a"])

    @property
    def hold_temp_c(self) -> float:
        return float(self.spec["hold_temp_c"])

    def cadence_min(self, rack: str) -> int:
        return int(self.spec["racks"][str(rack)])

    def true_law(self) -> str:
        return str(self.spec["law"])

    def multiplier(self, drive_a: float, temp_c: float) -> float:
        "The world's own stress multiplier on accumulated soak hours."

        entry = self.spec["catalogue"][self.true_law()]
        return drive_factor(
            str(entry["drive_form"]),
            float(entry["drive_constant"]),
            drive_a,
            self.field_drive_a,
        ) * temperature_factor(entry["ten_degree_factor"], temp_c, self.hold_temp_c)

    def loss(self, hours: float, drive_a: float, temp_c: float) -> float:
        'The share of its output one module has lost after this much soak.'

        entry = self.spec["catalogue"][self.true_law()]
        soak = float(hours) * self.multiplier(drive_a, temp_c)
        return float(self.spec["law_amplitude"]) * shape(
            str(entry["time_shape"]), float(entry["shape_constant"]), soak
        )

    def hours_to_target(self) -> float:
        'Hours at the field drive and the hold to a tenth of the output gone.'

        target = float(self.spec["target_loss"])
        entry = self.spec["catalogue"][self.true_law()]
        kind = str(entry["time_shape"])
        constant = float(entry["shape_constant"])
        value = target / float(self.spec["law_amplitude"])
        if kind == "power":
            return value ** (1.0 / constant)
        if kind == "logarithmic":
            return constant * math.expm1(value)
        if kind == "saturating":
            return -constant * math.log(max(1.0 - value, 1e-12))
        return value * constant


    def _noise(self, key: str, index: int) -> float:
        stream = random.Random(f"{key}|{index}")
        return stream.gauss(0.0, self.read_noise_mw)

    def reading(self, true_mw: float, key: str, index: int) -> float:
        'One bench reading: the meter stops at the sticker on its front.'

        return round(min(float(true_mw) + self._noise(key, index), self.full_scale_mw), 1)

    def modules(self) -> list[dict[str, Any]]:
        'The incoming sheet as goods-in wrote it, and nothing the world knows.'

        return [
            {field: item[field] for field in INCOMING_SHEET_COLUMNS}
            for item in self.spec["modules"]
        ]

    def _stamp(self, started_on: str, hours: float) -> str:
        moment = datetime.fromisoformat(str(started_on)) + timedelta(hours=float(hours))
        return moment.isoformat(sep=" ", timespec="minutes")

    def trace_rows(self) -> list[dict[str, Any]]:
        'Every bench reading the campaign has taken, reference reads included.'

        cached = getattr(self, "_export", None)
        if cached is not None:
            return cached
        rows = self._build_trace_rows()
        object.__setattr__(self, "_export", rows)
        return rows

    def _build_trace_rows(self) -> list[dict[str, Any]]:
        step = float(self.spec["read_interval_h"])
        rows: list[dict[str, Any]] = []
        for module in self.spec["modules"]:
            name = str(module["module_id"])
            rack = str(module["rack"])
            drive = float(module["drive_a"])
            incoming = float(module["incoming_mw"])
            reach = float(module["reach_h"])
            index = 0
            hours = step
            while hours <= reach + 1e-9:
                index += 1
                true_mw = incoming * (1.0 - self.loss(hours, drive, self.hold_temp_c))
                rows.append(
                    self._row(name, module["lot"], rack, drive, hours,
                              module["started_on"], self.reading(true_mw, name, index))
                )
                hours += step
        rows.extend(self._reference_rows())
        rows.sort(key=lambda row: (row["logged_at"], row["module_id"]))
        return rows

    def _row(
        self,
        module_id: str,
        lot: Any,
        rack: str,
        drive_a: float,
        hours: float,
        started_on: str,
        output_mw: float,
    ) -> dict[str, Any]:
        samples = int(round(hours * 60.0 / self.cadence_min(rack)))
        return {
            "module_id": str(module_id),
            "lot": str(lot),
            "rack": str(rack),
            "drive_a": round(float(drive_a), 2),
            "sample_index": samples,
            "logged_at": self._stamp(started_on, hours),
            "elapsed_h": samples,
            "output_mw": float(output_mw),
        }

    def _reference_rows(self) -> list[dict[str, Any]]:
        'The 20 mW reference source, read into the export at every session.'

        step = float(self.spec["read_interval_h"])
        source = float(self.spec["reference_source_mw"])
        rows: list[dict[str, Any]] = []
        for rack in sorted(self.spec["racks"]):
            on_it = [
                module for module in self.spec["modules"]
                if str(module["rack"]) == rack and float(module["reach_h"]) > 0
            ]
            if not on_it:
                continue
            opened = min(str(module["started_on"]) for module in on_it)
            sessions = int(max(float(module["reach_h"]) for module in on_it) / step)
            for index in range(1, sessions + 1):
                hours = step * index
                rows.append(
                    self._row(REFERENCE_MODULE, "", rack, 0.0, hours, opened,
                              self.reading(source, f"{REFERENCE_MODULE}-{rack}", index))
                )
        return rows


    def campaign_days(self) -> list[str]:
        return days_from(self.spec["first_day"], int(self.spec["day_count"]))

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "campaign": self.campaign,
            "family": str(spec["family"]),
            "build_month": str(spec["build_month"]),
            "field_drive_a": self.field_drive_a,
            "hold_temp_c": self.hold_temp_c,
            "target_loss": float(spec["target_loss"]),
            "meter_full_scale_mw": self.full_scale_mw,
            "meter_read_spread_mw": self.read_noise_mw,
            "reference_source_mw": float(spec["reference_source_mw"]),
            "reference_module_id": REFERENCE_MODULE,
            "racks": sorted(spec["racks"]),
            "catalogue": {
                name: dict(entry) for name, entry in sorted(spec["catalogue"].items())
            },
            "modules": self.modules(),
            "traces": self.trace_rows(),
            "budget": {
                "chamber_days_granted": float(spec["days_granted"]),
                "ports_per_block": int(spec["ports_cap"]),
                "days_per_block": int(spec["days_per_block_cap"]),
                "highest_drive_a": float(spec["drive_cap_a"]),
                "highest_case_temp_c": float(spec["temp_cap_c"]),
                "lowest_drive_a": float(spec["drive_floor_a"]),
                "review_on": str(spec["review_on"]),
                "smallest_block_days": int(spec["smallest_block_days"]),
                "block_reading_every_h": float(spec["block_read_interval_h"]),
                "range_the_review_acts_on_h": float(spec["review_acts_within_h"]),
            },
            "spares": {lot: int(count) for lot, count in sorted(spec["spares"].items())},
            "spares_incoming_mw": {
                lot: float(value) for lot, value in sorted(spec["spare_incoming_mw"].items())
            },
            "rig_out_of_service": list(spec["rig_out"]),
            "campaign_days": self.campaign_days(),
        }


    def days_charged(self, chamber_days: int) -> int:
        return max(1, min(int(chamber_days), int(self.spec["days_per_block_cap"])))

    def days_spent(self, stream: Sequence[Mapping[str, Any]]) -> int:
        return sum(int(item["days_charged"]) for item in stream)

    def days_left(self, stream: Sequence[Mapping[str, Any]]) -> int:
        return int(self.spec["days_granted"]) - self.days_spent(stream)

    def spares_left(self, stream: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        left = {lot: int(count) for lot, count in self.spec["spares"].items()}
        for item in stream:
            lot = str(item.get("lot") or "")
            if lot in left:
                left[lot] -= int(item.get("modules_returned") or 0)
        return left

    def served_on(self, stream: Sequence[Mapping[str, Any]]) -> str | None:
        'The day the desk would charge next, which is the day it will charge.'

        days = self.campaign_days()
        index = self.days_spent(stream)
        return days[index] if index < len(days) else None

    def rig_is_out(self, day: str) -> bool:
        window = list(self.spec["rig_out"])
        return bool(window) and str(window[0]) <= str(day) <= str(window[1])
