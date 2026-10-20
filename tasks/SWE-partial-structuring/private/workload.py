'Deterministic provider drops, correction rounds, and the reading the rules give.'

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


CLEAN = 0
UNREADABLE_OPTIONAL = 1
ABSENT_OPTIONAL = 2
UNREADABLE_REQUIRED = 3
ABSENT_REQUIRED = 4
NESTED_PART_READABLE = 5
NESTED_UNUSABLE = 6
BAD_LINE_ELEMENT = 7
EXTRA_COLUMN = 8
CORRECTION_TARGET = 9


DROP_PROFILES: Mapping[str, tuple[int, ...]] = {
    "abort": (CLEAN, UNREADABLE_OPTIONAL, UNREADABLE_REQUIRED, ABSENT_REQUIRED, EXTRA_COLUMN),
    "provenance": (CLEAN, ABSENT_OPTIONAL, ABSENT_REQUIRED, NESTED_PART_READABLE, EXTRA_COLUMN),
    "orders": (CLEAN, BAD_LINE_ELEMENT, NESTED_UNUSABLE, BAD_LINE_ELEMENT),
    "console": (CLEAN, CORRECTION_TARGET),
    "nightly": (
        CLEAN,
        UNREADABLE_OPTIONAL,
        ABSENT_OPTIONAL,
        UNREADABLE_REQUIRED,
        ABSENT_REQUIRED,
        NESTED_PART_READABLE,
        NESTED_UNUSABLE,
        BAD_LINE_ELEMENT,
        EXTRA_COLUMN,
        CORRECTION_TARGET,
    ),
}

_TIERS = ("standard", "premium", "business")
_LOCALES = ("en-GB", "en-IE", "fr-FR")
_CITIES = ("Leeds", "Bristol", "Newcastle", "Manchester", "Edinburgh", "Cardiff")
_STREETS = ("Bank Street", "Mill Road", "Quarry Lane", "Harbour Way", "Foundry Row")
_AREAS = ("LS", "BS", "NE", "M", "EH", "CF")
_UNIT = "ABDEFGHJLNPQRSTUWXYZ"


def _postcode(seed: int, index: int) -> str:
    area = _AREAS[index % len(_AREAS)]
    return (
        f"{area}{1 + index % 9} {(seed + index) % 10}"
        f"{_UNIT[(seed + index) % len(_UNIT)]}{_UNIT[(seed + 3 * index) % len(_UNIT)]}"
    )


def _day(seed: int, index: int) -> str:
    return (
        f"20{18 + (seed + index) % 8:02d}-"
        f"{1 + (3 * seed + index) % 12:02d}-{1 + (seed + 2 * index) % 28:02d}"
    )


def _lines(seed: int, index: int, count: int) -> list[dict[str, Any]]:
    return [
        {
            "sku": f"SKU-{seed:02d}-{index:03d}-{item}",
            "quantity": 1 + (index + item) % 4,
            "unit_pence": 199 + 50 * ((seed + item) % 9),
        }
        for item in range(count)
    ]


def _payload(seed: int, index: int, *, line_count: int = 0) -> dict[str, Any]:
    return {
        "account_ref": f"AC-{seed:02d}-{index:04d}",
        "joined_on": _day(seed, index),
        "tier": _TIERS[(seed + index) % len(_TIERS)],
        "credit_pence": 100 * ((seed + index) % 37),
        "locale": _LOCALES[index % len(_LOCALES)],
        "address": {
            "line1": f"{10 + index} {_STREETS[index % len(_STREETS)]}",
            "city": _CITIES[(seed + index) % len(_CITIES)],
            "postcode": _postcode(seed, index),
            "country": "GB",
        },
        "lines": _lines(seed, index, line_count or 1 + index % 3),
    }


def _damaged(slot: int, seed: int, index: int) -> dict[str, Any]:
    payload = _payload(seed, index, line_count=3 if slot == BAD_LINE_ELEMENT else 0)
    if slot == UNREADABLE_OPTIONAL:
        payload["credit_pence"] = "n/a"
    elif slot == ABSENT_OPTIONAL:
        payload.pop("tier")
    elif slot == UNREADABLE_REQUIRED:
        payload["joined_on"] = "31/02/2026"
    elif slot == ABSENT_REQUIRED:
        payload.pop("account_ref")
    elif slot == NESTED_PART_READABLE:
        payload["address"]["postcode"] = "?"
    elif slot == NESTED_UNUSABLE:
        payload["address"] = f"{10 + index} {_STREETS[index % len(_STREETS)]}, unknown"
    elif slot == BAD_LINE_ELEMENT:
        payload["lines"][1]["quantity"] = "two"
    elif slot == EXTRA_COLUMN:
        payload["churn_score"] = 0.7
    elif slot == CORRECTION_TARGET:
        payload["credit_pence"] = "tbc"
        payload["address"]["postcode"] = "?"
    return payload


def build_drop(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    "One night's drop: a list of ``{record_id, payload}`` entries."

    slots = DROP_PROFILES[str(profile)]
    drop: list[dict[str, Any]] = []
    index = 0
    for _repeat in range(max(1, int(scale))):
        for slot in slots:
            drop.append(
                {
                    "record_id": f"SUB-{int(seed):02d}-{index:03d}",
                    "slot": int(slot),
                    "payload": _damaged(int(slot), int(seed), index),
                }
            )
            index += 1
    return drop


def build_corrections(
    drop: Sequence[Mapping[str, Any]], seed: int, *, arrangements: Sequence[str]
) -> dict[str, Any] | None:
    "Support's correction round for the first payload that needs one."

    entry = next((item for item in drop if int(item.get("slot", -1)) == CORRECTION_TARGET), None)
    if entry is None:
        return None
    index = int(str(entry["record_id"]).rsplit("-", 1)[1])
    block = _payload(int(seed), index)["address"]
    credit = {"credit_pence": 1400}
    address = {"address": deepcopy(block)}
    whole = {**credit, **address}
    programme = {
        "single": [whole],
        "split": [credit, address],
        "repeated": [{**whole, "tier": "business", "locale": "fr-FR"}],
    }
    return {
        "record_id": str(entry["record_id"]),
        "arrangements": {name: programme[name] for name in arrangements},
    }


def build_case(profile: str, seed: int, scale: int) -> dict[str, Any]:
    'The whole night: the drop and, where support sent one, the correction round.'

    drop = build_drop(profile, seed, scale)
    arrangements = ("single", "split", "repeated") if profile == "nightly" else ("single",)
    return {"drop": drop, "corrections": build_corrections(drop, seed, arrangements=arrangements)}


def _protocol():
    from ..workspace.ingest import protocol

    return protocol


def expected_reading(payload: Any, record: Any) -> dict[str, Any]:
    'What the frozen contract says one payload reads as.'

    protocol = _protocol()
    structured: list[str] = []
    failed: list[str] = []
    values: dict[str, Any] = {}
    producible = True
    if not isinstance(payload, Mapping):
        return {
            "value": None,
            "structured": frozenset(),
            "failed": frozenset(protocol.field_names(record)),
            "is_complete": False,
            "lines": (f"{protocol.NOT_AN_OBJECT_MESSAGE} @ $",),
            "field_values": {},
        }
    for spec in protocol.init_fields(record):
        if spec.name in payload:
            raw = payload[spec.name]
            if not protocol.field_problems(spec, raw, f"$.{spec.name}"):
                structured.append(spec.name)
                values[spec.name] = protocol.field_value(spec, raw)
                continue
            failed.append(spec.name)
            if spec.kind == "record" and isinstance(raw, Mapping):
                child = expected_reading(raw, spec.record)
                if child["value"] is not None:
                    values[spec.name] = child["value"]
                    continue
        else:
            failed.append(spec.name)
        if spec.default is protocol.MISSING:
            producible = False
        else:
            values[spec.name] = spec.default
    problems = protocol.record_problems(payload, record, "$")
    return {
        "value": protocol.build(record, values) if producible else None,
        "structured": frozenset(structured),
        "failed": frozenset(failed),
        "is_complete": not failed,
        "lines": protocol.describe_errors(protocol.StructureErrors(problems)) if problems else (),
        "field_values": values,
    }


def expected_after(
    payload: Mapping[str, Any], patches: Sequence[Mapping[str, Any]], record: Any
) -> dict[str, Any]:
    "The reading support's corrections fold the original into, patch by patch."

    effective = dict(payload)
    for patch in patches:
        gaps = expected_reading(effective, record)["failed"]
        for name, raw in dict(patch).items():
            if name in gaps:
                effective[name] = raw
    return expected_reading(effective, record)
