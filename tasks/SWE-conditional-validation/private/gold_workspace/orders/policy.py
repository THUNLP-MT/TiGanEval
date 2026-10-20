"""The order write path: what we accept, what we hand the store, what we show.

The `required_when` declarations in the entity documents are the one place a
pair is written down. Each surface reads them with the information it has: the
write path sees the whole item, the update path sees only the change set and so
hands the store a condition it evaluates against the stored item, and the read
path sees an item that may predate the declaration entirely.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Sequence

from .protocol import (
    ABSENT, And, Attr, Equals, Exists, Missing, Not, OneOf, Schema, SchemaError,
    ValidationError, apply_defaults, from_stored, logical_path, physical_path,
    read_stored, stored_paths, walk, write_path,
)


def check_schema(schema: Schema) -> None:
    """Refuse an entity document the store could not honour."""

    physical: dict[str, str] = {}
    keys: list[str] = []
    for trail in walk(schema.attributes):
        attr = trail[-1]
        stored, logical = physical_path(trail), logical_path(trail)
        if stored in physical:
            raise SchemaError(f"{logical} is stored as {stored}, which {physical[stored]} already uses")
        physical[stored] = logical
        if attr.is_key:
            keys.append(logical)
        siblings = schema.attributes if len(trail) == 1 else trail[-2].attributes
        for rule in attr.required_when:
            if attr.is_key:
                raise SchemaError(f"{logical} is the key attribute and cannot be conditional")
            if rule.controller == attr.name:
                raise SchemaError(f"{logical} is declared against itself")
            if rule.controller not in dict(siblings):
                raise SchemaError(
                    f"{logical} is declared against {rule.controller}, which is not beside it"
                )
    if len(keys) != 1:
        raise SchemaError(f"{schema.name} declares {len(keys)} key attributes, not one")


def admit(schema: Schema, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept one payload for writing, or raise ValidationError."""

    item = apply_defaults(schema, dict(payload or {}))
    owed = _owed(schema.attributes, item, "")
    if owed:
        raise ValidationError(f"{schema.name} is missing {', '.join(owed)}")
    return item


def build_update(
    schema: Schema, changes: Mapping[str, Any], condition: Any = None
) -> tuple[dict[str, Any], Any]:
    """Turn one change set into the patch and the condition the store is given."""

    setting = {str(name): value for name, value in dict(changes.get("set") or {}).items()}
    removing = [str(name) for name in (changes.get("remove") or ())]
    patch: dict[str, Any] = {"set": {}, "remove": []}
    for name, value in setting.items():
        trail = _trail(schema, name)
        stored = physical_path(trail)
        if value is None:
            patch["remove"].append(stored)
        else:
            patch["set"][stored] = _stored_value(trail[-1], value, name)
    patch["remove"].extend(stored_paths(schema, removing))
    parts: list[Any] = [] if condition is None else [condition]
    parts.extend(_guards(schema, setting, removing))
    if not parts:
        return patch, None
    return patch, parts[0] if len(parts) == 1 else And(tuple(parts))


def read_view(
    schema: Schema, stored: Mapping[str, Any], projection: Sequence[str] | None = None
) -> dict[str, Any]:
    """One stored item as the dashboard and the support tool read it."""

    view = from_stored(schema, dict(stored or {}))
    if projection is None:
        return view
    projected: dict[str, Any] = {}
    for name in projection:
        value = read_stored(view, str(name))
        if value is not ABSENT:
            write_path(projected, str(name), value)
    return projected


def _trail(schema: Schema, name: str) -> tuple[Attr, ...]:
    for trail in walk(schema.attributes):
        if logical_path(trail) == name:
            return tuple(trail)
    raise ValidationError(f"{schema.name} has no attribute at {name}")


def _stored_value(attr: Attr, value: Any, where: str) -> Any:
    if attr.kind != "map":
        return value
    if not isinstance(value, Mapping):
        raise ValidationError(f"{where} must be a map")
    stored: dict[str, Any] = {}
    for name, child_value in dict(value).items():
        child = attr.attributes.get(str(name))
        if child is None:
            raise ValidationError(f"{where} has no attribute called {name}")
        if child_value is not None:
            stored[child.stored_as] = _stored_value(child, child_value, f"{where}.{name}")
    return stored


def _owed(attributes: Mapping[str, Attr], scope: Mapping[str, Any], prefix: str) -> list[str]:
    """Which attributes this scope still owes, its own siblings deciding."""

    owed: list[str] = []
    for name, attr in dict(attributes).items():
        value = scope.get(name)
        if attr.kind == "map" and isinstance(value, Mapping):
            owed.extend(_owed(attr.attributes, value, f"{prefix}{name}."))
        if (attr.required or _binding(attr, scope)) and value is None:
            owed.append(f"{prefix}{name}")
    return owed


def _binding(attr: Attr, scope: Mapping[str, Any]) -> bool:
    for rule in attr.required_when:
        held = scope.get(rule.controller)
        if held is not None and held in tuple(rule.values):
            return True
    return False


_UNCHANGED = object()
_REMOVED = object()


def _changed_value(
    path: str, setting: Mapping[str, Any], removing: Sequence[str]
) -> Any:
    if path in removing or any(path.startswith(f"{name}.") for name in removing):
        return _REMOVED
    if path in setting:
        value = setting[path]
        return _REMOVED if value is None else value
    for ancestor, value in setting.items():
        if not path.startswith(f"{ancestor}."):
            continue
        nested: Any = value
        for part in path[len(ancestor) + 1 :].split("."):
            if not isinstance(nested, Mapping) or part not in nested:
                return _REMOVED
            nested = nested[part]
        return _REMOVED if nested is None else nested
    return _UNCHANGED


def _guards(
    schema: Schema, setting: Mapping[str, Any], removing: Sequence[str]
) -> Iterator[Any]:
    """One condition per pair this change set could break, in store terms.

    `build_update` never sees the stored item, so every pair the change set
    touches becomes a condition the store checks against it at write time.
    """

    for trail in walk(schema.attributes):
        attr = trail[-1]
        prefix = logical_path(trail[:-1])
        dependent = logical_path(trail)
        dependent_stored = physical_path(trail)
        for rule in attr.required_when:
            controller = f"{prefix}.{rule.controller}" if prefix else rule.controller
            controller_stored = stored_paths(schema, [controller])[0]
            controller_change = _changed_value(controller, setting, removing)
            dependent_change = _changed_value(dependent, setting, removing)
            if controller_change is _UNCHANGED and dependent_change is _UNCHANGED:
                continue
            if controller_change is _UNCHANGED:
                if dependent_change is _REMOVED:
                    yield Not(OneOf(controller_stored, tuple(rule.values)))
                continue
            heading_for = (
                controller_change is not _REMOVED
                and controller_change in tuple(rule.values)
            )
            if not heading_for or dependent_change is not _UNCHANGED:
                if heading_for and dependent_change is _REMOVED:
                    yield And((Exists(dependent_stored), Missing(dependent_stored)))
                continue
            yield And((Exists(dependent_stored), Not(Equals(dependent_stored, None))))
