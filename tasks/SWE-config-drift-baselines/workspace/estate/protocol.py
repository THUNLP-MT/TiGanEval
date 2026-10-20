"""Runtime contract for the estate's configuration compliance service.

Every region runs this file unchanged, so the settings a service declaration
carries, the drift vocabulary, the severity table, the status words, the
arithmetic behind the compliance number and the console's clock read the same
everywhere. Time moves only when the console moves it, and a night's scan holds
whatever the collector read off the hosts that night.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping


#: Every setting a service declaration carries, in the order the console prints
#: them. A scan holds the settings the collector could read; a setting it has
#: nothing to report for is simply not in the mapping.
CONFIG_KEYS: tuple[str, ...] = (
    "image", "restart_policy", "network", "env", "ports", "mounts",
    "labels", "memory_mb", "cpu_share",
)

#: The setting release tooling uses as a service's compact release reference.
RELEASE_REFERENCE_KEY = "image"

#: Settings the host reports as a collection. The collector emits them in
#: whatever order the runtime happens to hold them in, which changes whenever a
#: service is recreated, so these carry contents rather than sequences.
LIST_KEYS: tuple[str, ...] = ("env", "ports", "mounts")
MAP_KEYS: tuple[str, ...] = ("labels",)

IMAGE_CHANGED, RESTART_POLICY_CHANGED, NETWORK_CHANGED = (
    "image_changed", "restart_policy_changed", "network_changed")
ENV_CHANGED, BINDING_CHANGED, LABEL_CHANGED = (
    "env_changed", "binding_changed", "label_changed")
RESOURCE_CHANGED, SERVICE_MISSING, SERVICE_ADDED = (
    "resource_changed", "service_missing", "service_added")
CRITICAL, HIGH, MEDIUM, LOW = "critical", "high", "medium", "low"

#: What the estate calls a change to one setting.
DRIFT_TYPE_BY_KEY: Mapping[str, str] = {
    "image": IMAGE_CHANGED, "restart_policy": RESTART_POLICY_CHANGED,
    "network": NETWORK_CHANGED, "env": ENV_CHANGED, "ports": BINDING_CHANGED,
    "mounts": BINDING_CHANGED, "labels": LABEL_CHANGED,
    "memory_mb": RESOURCE_CHANGED, "cpu_share": RESOURCE_CHANGED,
}

#: How urgently the platform treats each kind of change. The notification
#: policy pages on the critical and high counts, so this table is the same in
#: every region.
SEVERITY_BY_TYPE: Mapping[str, str] = {
    IMAGE_CHANGED: CRITICAL, SERVICE_MISSING: CRITICAL, ENV_CHANGED: HIGH,
    NETWORK_CHANGED: HIGH, BINDING_CHANGED: HIGH, RESOURCE_CHANGED: MEDIUM,
    RESTART_POLICY_CHANGED: MEDIUM, SERVICE_ADDED: MEDIUM, LABEL_CHANGED: LOW,
}


class Status:
    """The four words a stored record's status may hold.

    ``detected`` is what the nightly comparison writes and what appears in the
    operator's action queue. ``acknowledged`` and ``ignored`` are the
    operator's own decisions about a deviation; they leave that queue but stay
    in the durable ledger, and they are hers: the service does not take one back.
    ``resolved`` is what the service writes on a record it is still carrying
    itself, once the estate no longer holds the condition that record describes.
    """

    DETECTED, ACKNOWLEDGED, IGNORED, RESOLVED = (
        "detected", "acknowledged", "ignored", "resolved")
    ALL: tuple[str, ...] = (DETECTED, ACKNOWLEDGED, IGNORED, RESOLVED)


class EstateError(RuntimeError):
    """Base of everything the compliance service raises."""

class NoActiveBaseline(EstateError):
    """There is nothing to compare this environment against."""


def severity_for(drift_type: str) -> str:
    """How urgently the platform treats one kind of change."""

    try:
        return SEVERITY_BY_TYPE[str(drift_type)]
    except KeyError:
        raise EstateError(f"not a drift type this estate knows: {drift_type!r}") from None


def drift_type_for(key: str) -> str:
    """What a change to one setting is called."""

    try:
        return DRIFT_TYPE_BY_KEY[str(key)]
    except KeyError:
        raise EstateError(f"not a setting this estate compares: {key!r}") from None


def field_for(drift_type: str, key: str) -> str:
    """The ``field`` a record carries next to its drift type.

    Two drift types cover more than one setting, so those name the setting and
    every other type leaves the field empty; the console groups the morning
    list by drift type and field together.
    """

    return str(key) if str(drift_type) in (BINDING_CHANGED, RESOURCE_CHANGED) else ""


def canonical_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    """One service declaration in the form the estate compares.

    Collections come back in the order the runtime held them, so they are
    reduced to their contents; numbers are given their declared type. A setting
    the mapping does not carry is left out rather than filled in, because the
    collector reporting nothing about a setting is not the same as the host
    holding nothing there.
    """

    source = dict(raw or {})
    canonical: dict[str, Any] = {}
    for key in CONFIG_KEYS:
        if key not in source:
            continue
        value = source[key]
        if key in LIST_KEYS:
            canonical[key] = tuple(sorted(str(item) for item in value or ()))
        elif key in MAP_KEYS:
            canonical[key] = dict(sorted((str(k), str(v)) for k, v in dict(value or {}).items()))
        elif key == "memory_mb":
            canonical[key] = int(value)
        elif key == "cpu_share":
            canonical[key] = round(float(value), 3)
        else:
            canonical[key] = str(value)
    return canonical


def render_value(value: Any) -> str:
    """One canonical setting as it is written into a record.

    Two records that describe the same condition read identically because both
    sides went through here first.
    """

    if value is None:
        return ""
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={item}" for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def compliance_score(compliant: int, total: int) -> float:
    """The number the dashboard plots for one environment.

    An environment with nothing in its baseline has nothing to be out of line
    with, so it reads as fully compliant.
    """

    if int(total) <= 0:
        return 100.0
    return round(int(compliant) / int(total) * 100.0, 1)


def record_key(baseline_id: str, service: str, drift_type: str, field: str) -> str:
    """What makes two records the same record.

    One baseline, one service, one drift type and one field: everything that
    points at a deviation from outside the comparison -- an acknowledgement, a
    ticket, a page -- points at this.
    """

    return f"{baseline_id}|{service}|{drift_type}|{field}"


#: The night the console counts from. One tick is one night.
FIRST_NIGHT = date(2026, 3, 1)


def stamp(tick: int) -> str:
    """The night a tick belongs to, as the console prints it."""

    return (FIRST_NIGHT + timedelta(days=int(tick))).isoformat()


class Clock:
    """The console's clock, counted in nights."""

    def __init__(self, tick: int = 0):
        self._now = int(tick)

    def now(self) -> int:
        return self._now

    def set(self, tick: int) -> None:
        self._now = int(tick)


@dataclass(slots=True)
class Baseline:
    """One environment's declared configuration, as captured on one night."""

    id: str
    environment: str
    name: str
    services: dict[str, dict[str, Any]]
    captured_at: int
    active: bool = True

    @property
    def service_count(self) -> int:
        return len(self.services)


@dataclass(slots=True)
class Drift:
    """One deviation of the estate from a baseline.

    ``expected`` and ``actual`` are the two current sides written out.  A
    standing record keeps its identity and first-seen date while ``actual`` is
    refreshed from each night's observation.  ``status`` is one of
    :class:`Status`, and ``resolved_at`` is the night the condition was seen to
    have cleared.
    """

    id: str
    baseline_id: str
    environment: str
    service: str
    drift_type: str
    field: str
    expected: str
    actual: str
    severity: str
    status: str
    detected_at: int
    resolved_at: int | None = None

    @property
    def key(self) -> str:
        return record_key(self.baseline_id, self.service, self.drift_type, self.field)


@dataclass(slots=True)
class Snapshot:
    """One environment's compliance numbers for one night."""

    environment: str
    baseline_id: str
    scanned_at: int
    total_services: int
    compliant_services: int
    drifted_services: int
    missing_services: int
    unknown_services: int
    added_services: int
    critical: int
    high: int
    medium: int
    low: int
    score: float


def _get(item: Any, name: str, default: Any = "") -> Any:
    return item.get(name, default) if isinstance(item, Mapping) else getattr(item, name, default)

def _text(value: Any) -> str:
    return "" if value is None else str(value)

def _whole(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def drift_row(record: Any) -> dict[str, Any]:
    """One stored record as the console prints it in the durable ledger."""

    baseline_id, service = _text(_get(record, "baseline_id")), _text(_get(record, "service"))
    drift_type, field = _text(_get(record, "drift_type")), _text(_get(record, "field"))
    detected_at = _whole(_get(record, "detected_at", 0))
    resolved_at = _get(record, "resolved_at", None)
    return {
        "id": _text(_get(record, "id")),
        "key": record_key(baseline_id, service, drift_type, field),
        "baseline_id": baseline_id, "environment": _text(_get(record, "environment")),
        "service": service, "drift_type": drift_type, "field": field,
        "expected": _text(_get(record, "expected")), "actual": _text(_get(record, "actual")),
        "severity": _text(_get(record, "severity")), "status": _text(_get(record, "status")),
        "detected_at": detected_at, "detected_on": stamp(detected_at),
        "resolved_at": None if resolved_at is None else _whole(resolved_at),
        "resolved_on": None if resolved_at is None else stamp(_whole(resolved_at)),
    }


def snapshot_row(snapshot: Any) -> dict[str, Any]:
    """One night's compliance numbers as the dashboard reads them."""

    scanned_at = _whole(_get(snapshot, "scanned_at", 0))
    try:
        score = float(_get(snapshot, "score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    row = {"environment": _text(_get(snapshot, "environment")),
           "baseline_id": _text(_get(snapshot, "baseline_id")),
           "scanned_at": scanned_at, "scanned_on": stamp(scanned_at)}
    for name in ("total_services", "compliant_services", "drifted_services",
                 "missing_services", "unknown_services", "added_services",
                 "critical", "high", "medium", "low"):
        row[name] = _whole(_get(snapshot, name, 0))
    row["score"] = score
    return row


def baseline_row(baseline: Any) -> dict[str, Any]:
    """One captured baseline as the console lists it."""

    captured_at = _whole(_get(baseline, "captured_at", 0))
    names = sorted(str(name) for name in dict(_get(baseline, "services", {}) or {}))
    return {
        "id": _text(_get(baseline, "id")), "environment": _text(_get(baseline, "environment")),
        "name": _text(_get(baseline, "name")), "captured_at": captured_at,
        "captured_on": stamp(captured_at), "active": bool(_get(baseline, "active", False)),
        "service_count": len(names), "services": names,
    }


def sort_records(rows: Any) -> list[dict[str, Any]]:
    """The stored record ledger in the order the console prints it."""

    return sorted((dict(row) for row in rows),
                  key=lambda row: (str(row.get("key", "")),
                                   _whole(row.get("detected_at", 0)),
                                   str(row.get("id", ""))))
