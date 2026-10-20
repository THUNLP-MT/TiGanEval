"""The order write path: what we accept, what we hand the store, what we show.

Half-way through the cutover from the hand-written pair checks in
`retiring_guards.py` to the `required_when` declarations in the entity
documents.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    Attr, Schema, SchemaError, ValidationError, apply_defaults, from_stored,
    logical_path, physical_path, stored_paths, walk,
)


def check_schema(schema: Schema) -> None:
    """Refuse an entity document the store could not honour."""

    physical: dict[str, str] = {}
    keys: list[str] = []
    for trail in walk(schema.attributes):
        stored, logical = physical_path(trail), logical_path(trail)
        if stored in physical:
            raise SchemaError(f"{logical} is stored as {stored}, which {physical[stored]} already uses")
        physical[stored] = logical
        if trail[-1].is_key:
            keys.append(logical)
    if len(keys) != 1:
        raise SchemaError(f"{schema.name} declares {len(keys)} key attributes, not one")


def admit(schema: Schema, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept one payload for writing, or raise ValidationError."""

    owed = _owed(schema.attributes, dict(payload or {}), dict(payload or {}), "")
    if owed:
        raise ValidationError(f"{schema.name} is missing {', '.join(owed)}")
    return apply_defaults(schema, payload)


def build_update(
    schema: Schema, changes: Mapping[str, Any], condition: Any = None
) -> tuple[dict[str, Any], Any]:
    """Turn one change set into the patch and the condition the store is given."""

    patch: dict[str, Any] = {"set": {}, "remove": []}
    for name, value in dict(changes.get("set") or {}).items():
        patch["set"][stored_paths(schema, [name])[0]] = value
    for name in changes.get("remove") or ():
        patch["remove"].append(stored_paths(schema, [name])[0])
    return patch, condition


def read_view(
    schema: Schema, stored: Mapping[str, Any], projection: Sequence[str] | None = None
) -> dict[str, Any]:
    """One stored item as the dashboard and the support tool read it."""

    view = from_stored(schema, dict(stored or {}))
    owed = _owed(schema.attributes, view, view, "")
    if owed:
        raise ValidationError(f"{schema.name} is missing {', '.join(owed)}")
    if projection is None:
        return view
    return {name: view[name] for name in projection if name in view}


def _owed(
    attributes: Mapping[str, Attr], scope: Mapping[str, Any], item: Mapping[str, Any], prefix: str
) -> list[str]:
    """Which attributes this scope still owes."""

    owed: list[str] = []
    for name, attr in dict(attributes).items():
        value = scope.get(name)
        if attr.kind == "map" and isinstance(value, Mapping):
            owed.extend(_owed(attr.attributes, value, item, f"{prefix}{name}."))
        binding = any(item.get(rule.controller) is not None for rule in attr.required_when)
        if (attr.required or binding) and value is None:
            owed.append(f"{prefix}{name}")
    return owed
