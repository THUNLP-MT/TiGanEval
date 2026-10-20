'The handheld fleet behind the bundle decision, and the annotation desk.'

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import random
from statistics import NormalDist
import threading
from typing import Any, Mapping, Sequence

from .reading import (
    BUNDLES,
    CONDITIONS,
    CONDITION_PARAMS,
    FEATURES,
    REFERENCE_CARD,
    REFERENCE_PARAMS,
    LAW_STEEPNESS,
    REFLECTANCE,
    apply_gain,
    decide,
    readable_score,
    remove_gain,
)


PROFILES = ("counter", "backroom", "yard", "night")
RECEIPTS_FILE = "capture_receipts.json"

_LOCK = threading.RLock()


_GOLDEN = 0.6180339887498949

_LOG_CACHE: dict[str, dict[str, Any]] = {}
_REGISTER_CACHE: dict[str, dict[str, Any]] = {}
_FRAME_CACHE: dict[tuple[str, str, str, str], list[int]] = {}


def _days(first_day: str, count: int) -> tuple[str, ...]:
    start = date.fromisoformat(str(first_day))
    return tuple((start + timedelta(days=index)).isoformat() for index in range(count))


@dataclass(frozen=True)
class Unit:
    unit_id: str
    unit_model: str
    duty_profile: str
    shares: tuple[float, ...]
    firmware: str
    in_service_on: str
    reached: bool
    log_rows: int


@dataclass(frozen=True)
class Capture:
    unit: int
    condition: str
    day: str
    truth: tuple[float, ...]
    label: int
    exported: bool


@dataclass(frozen=True)
class Fleet:
    "One fleet's units, its captures, and what the exporter wrote about them."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    units: tuple[Unit, ...]
    captures: tuple[Capture, ...]
    log_order: tuple[int, ...] = field(repr=False, default=())

    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def fleet(self) -> str:
        return str(self.spec["fleet"])

    @property
    def gain(self) -> float:
        return float(self.spec["gain"])

    def unit_of(self, capture: Capture) -> Unit:
        return self.units[capture.unit]

    def raised(self, capture: Capture) -> bool:
        return self.unit_of(capture).firmware == str(self.spec["raised_firmware"])

    def as_written(self, capture: Capture) -> list[float]:
        'The eight columns as the exporter wrote them for this capture.'

        if self.raised(capture):
            return apply_gain(capture.truth, self.gain)
        return [float(value) for value in capture.truth]

    def in_service(self, capture: Capture) -> list[float]:
        'The eight columns the bundle sees on the unit itself.'

        return [float(value) for value in capture.truth]

    def wrong_in_service(self, capture: Capture, bundle: str) -> bool:
        return decide(bundle, self.in_service(capture)) != capture.label


    def log_columns(self) -> tuple[str, ...]:
        return (
            "device_id",
            "firmware",
            "condition",
            "day",
            *FEATURES,
            "label",
            *BUNDLES,
            "stage",
        )

    def log_row(self, index: int) -> list[Any]:
        capture = self.captures[index]
        unit = self.unit_of(capture)
        written = self.as_written(capture)
        return [
            unit.unit_id,
            unit.firmware,
            capture.condition,
            capture.day,
            *[round(value, 4) for value in written],
            capture.label,
            *[decide(name, written) for name in BUNDLES],
            "as_captured" if self.raised(capture) else "corrected",
        ]

    def log(self) -> dict[str, Any]:
        'The export as the release stack publishes it, built once per fleet.'

        if self.campaign not in _LOG_CACHE:
            _LOG_CACHE[self.campaign] = {
                "columns": list(self.log_columns()),
                "rows": [self.log_row(index) for index in self.log_order],
            }
        return _LOG_CACHE[self.campaign]

    def register_columns(self) -> tuple[str, ...]:
        return (
            "unit_id",
            "unit_model",
            "duty_profile",
            "firmware",
            "share_bright",
            "share_dim",
            "share_glare",
            "share_damaged",
            "in_service_on",
        )

    def register(self) -> dict[str, Any]:
        if self.campaign in _REGISTER_CACHE:
            return _REGISTER_CACHE[self.campaign]
        _REGISTER_CACHE[self.campaign] = {
            "columns": list(self.register_columns()),
            "rows": [
                [
                    unit.unit_id,
                    unit.unit_model,
                    unit.duty_profile,
                    unit.firmware,
                    *[round(value, 3) for value in unit.shares],
                    unit.in_service_on,
                ]
                for unit in self.units
            ],
        }
        return _REGISTER_CACHE[self.campaign]

    def terms(self) -> dict[str, Any]:
        'The annotation terms, without building any table.'

        spec = self.spec
        return {
            "credits_granted": int(spec["credits_granted"]),
            "credit_cost_per_row": {
                profile: (1 if profile == "counter" else 3) for profile in PROFILES
            },
            "reference_card_cost_per_row": 1,
            "min_rows_per_request": 20,
            "max_rows_per_request": 120,
            "refusal_charge": 20,
            "conditions": [*CONDITIONS, REFERENCE_CARD],
            "duty_profiles": list(PROFILES),
        }

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "campaign": self.campaign,
            "fleet": self.fleet,
            "window": {"first_day": self.days[0], "last_day": self.days[-1]},
            "as_of": str(spec["as_of"]),
            "bundles": list(BUNDLES),
            "promise_points": float(spec["promise_points"]),
            "firmware": {
                "raised": str(spec["raised_firmware"]),
                "earlier": str(spec["earlier_firmware"]),
                "capture_gain": self.gain,
                "channels": list(REFLECTANCE),
                "rollout_from": str(spec["rollout_from"]),
            },
            "annotation": self.terms(),
            "fleet_register": self.register(),
            "capture_log": self.log(),
        }


from .generate import build
