"""The order platform's storage contract: schema documents, items, and the store.

Everything here ships in the storage client's release and is used by the
checkout API, the fulfilment job, the support dashboard, the reconciliation
worker and the partner importer, so it stays as it is.

An entity is described by a document: one attribute per name, each with a type,
the physical name it is stored under (``stored_as``), whether it is always
required, an optional default the parser fills in, and any number of
``required_when`` declarations naming a sibling and the values it may hold.

The store holds physical names only. ``Store.update`` applies exactly the paths
a patch names, all of them or none, and only while the condition attached to the
write holds against the item the store already has; otherwise it raises
``ConditionalCheckFailed`` and writes nothing. Nothing else in the platform sees
the stored item at write time.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence


class SchemaError(RuntimeError):
    """A schema document declares something this store cannot enforce."""

class ValidationError(RuntimeError):
    """A payload does not satisfy the entity it is written against."""

class ConditionalCheckFailed(RuntimeError):
    """The store refused a write because its condition did not hold."""


# --- Schema documents -----------------------------------------------------

@dataclass(frozen=True, slots=True)
class Requirement:
    """``controller`` is a sibling name; the values that make the pair binding."""
    controller: str
    values: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class Attr:
    """One attribute of an entity or of a map inside one."""
    name: str
    kind: str
    stored_as: str
    required: bool = False
    default: Any = None
    is_key: bool = False
    required_when: tuple[Requirement, ...] = ()
    attributes: Mapping[str, "Attr"] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Schema:
    """One loaded entity document."""
    name: str
    attributes: Mapping[str, Attr]


def _requirements(raw: Any) -> tuple[Requirement, ...]:
    items = [raw] if isinstance(raw, Mapping) else list(raw or ())
    return tuple(Requirement(str(i["attribute"]), tuple(i.get("values", ()))) for i in items)


def _attributes(raw: Mapping[str, Any]) -> dict[str, Attr]:
    return {str(name): _attribute(str(name), dict(spec)) for name, spec in dict(raw).items()}


def _attribute(name: str, spec: Mapping[str, Any]) -> Attr:
    kind = str(spec.get("type", "string"))
    return Attr(
        name=name, kind=kind, stored_as=str(spec.get("stored_as", name)),
        required=bool(spec.get("required", False)), default=spec.get("default"),
        is_key=bool(spec.get("key", False)),
        required_when=_requirements(spec.get("required_when")),
        attributes=_attributes(spec.get("attributes") or {}) if kind == "map" else {},
    )


def load_schema(document: Mapping[str, Any]) -> Schema:
    """Build a schema from one entity document. It checks nothing."""
    return Schema(str(document.get("name", "entity")), _attributes(document.get("attributes") or {}))


def walk(attributes: Mapping[str, Attr], trail: tuple[Attr, ...] = ()) -> Iterator[tuple[Attr, ...]]:
    """Every attribute of a schema, as the trail of attributes that reaches it."""
    for attr in dict(attributes).values():
        here = trail + (attr,)
        yield here
        if attr.kind == "map":
            yield from walk(attr.attributes, here)


def key_attribute(schema: Schema) -> Attr | None:
    """The attribute the store keys items by, if the document declares one."""
    return next((attr for attr in schema.attributes.values() if attr.is_key), None)


def logical_path(trail: Sequence[Attr]) -> str:
    return ".".join(attr.name for attr in trail)


def physical_path(trail: Sequence[Attr]) -> str:
    return ".".join(attr.stored_as for attr in trail)


def stored_paths(schema: Schema, names: Sequence[str]) -> tuple[str, ...]:
    """The physical paths behind dotted logical names, in the order given."""
    index = {logical_path(trail): physical_path(trail) for trail in walk(schema.attributes)}
    return tuple(index[str(name)] for name in names)


def apply_defaults(schema: Schema, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The item the parser hands on: the payload with the document's defaults filled in."""
    return _defaults(schema.attributes, dict(payload or {}))


def _defaults(attributes: Mapping[str, Attr], scope: Mapping[str, Any]) -> dict[str, Any]:
    item = deepcopy(dict(scope))
    for name, attr in dict(attributes).items():
        if attr.kind == "map":
            nested = item.get(name)
            if isinstance(nested, Mapping):
                item[name] = _defaults(attr.attributes, nested)
            elif isinstance(attr.default, Mapping):
                item[name] = _defaults(attr.attributes, attr.default)
        elif item.get(name) is None and attr.default is not None:
            item[name] = deepcopy(attr.default)
    return item


def to_stored(schema: Schema, item: Mapping[str, Any]) -> dict[str, Any]:
    """One logical item as the store holds it, under physical names."""
    return _rename(schema.attributes, dict(item or {}), physical=True)


def from_stored(schema: Schema, stored: Mapping[str, Any]) -> dict[str, Any]:
    """One stored item as the platform reads it, under the document's names."""
    return _rename(schema.attributes, dict(stored or {}), physical=False)


def _rename(attributes: Mapping[str, Attr], scope: Mapping[str, Any], *, physical: bool) -> dict[str, Any]:
    renamed: dict[str, Any] = {}
    for attr in dict(attributes).values():
        source = attr.name if physical else attr.stored_as
        target = attr.stored_as if physical else attr.name
        if source not in scope:
            continue
        value = scope[source]
        if attr.kind == "map" and isinstance(value, Mapping):
            renamed[target] = _rename(attr.attributes, value, physical=physical)
        else:
            renamed[target] = deepcopy(value)
    return renamed


# --- Conditions the store evaluates against a stored item -----------------

@dataclass(frozen=True, slots=True)
class Exists:
    path: str

@dataclass(frozen=True, slots=True)
class Missing:
    path: str

@dataclass(frozen=True, slots=True)
class Equals:
    path: str
    value: Any

@dataclass(frozen=True, slots=True)
class OneOf:
    path: str
    values: tuple[Any, ...]

@dataclass(frozen=True, slots=True)
class Not:
    part: Any

@dataclass(frozen=True, slots=True)
class And:
    parts: tuple[Any, ...]

@dataclass(frozen=True, slots=True)
class Or:
    parts: tuple[Any, ...]


ABSENT = object()


def read_stored(stored: Mapping[str, Any], path: str) -> Any:
    """The value at one dotted physical path, or ``ABSENT``."""
    value: Any = stored
    for part in str(path).split("."):
        if not isinstance(value, Mapping) or part not in value:
            return ABSENT
        value = value[part]
    return value


def evaluate(condition: Any, stored: Mapping[str, Any]) -> bool:
    """Whether one condition holds against the item the store has."""
    if condition is None:
        return True
    if isinstance(condition, Exists):
        return read_stored(stored, condition.path) is not ABSENT
    if isinstance(condition, Missing):
        return read_stored(stored, condition.path) is ABSENT
    if isinstance(condition, Equals):
        value = read_stored(stored, condition.path)
        return value is not ABSENT and value == condition.value
    if isinstance(condition, OneOf):
        value = read_stored(stored, condition.path)
        return value is not ABSENT and value in tuple(condition.values)
    if isinstance(condition, Not):
        return not evaluate(condition.part, stored)
    if isinstance(condition, And):
        return all(evaluate(part, stored) for part in condition.parts)
    if isinstance(condition, Or):
        return any(evaluate(part, stored) for part in condition.parts)
    raise TypeError(f"the store was handed something that is not a condition: {condition!r}")


def describe(condition: Any) -> Any:
    """One condition as the write log prints it."""
    if condition is None:
        return None
    if isinstance(condition, (Exists, Missing)):
        return {type(condition).__name__.lower(): condition.path}
    if isinstance(condition, Equals):
        return {"equals": [condition.path, condition.value]}
    if isinstance(condition, OneOf):
        return {"one_of": [condition.path, list(condition.values)]}
    if isinstance(condition, Not):
        return {"not": describe(condition.part)}
    if isinstance(condition, (And, Or)):
        return {type(condition).__name__.lower(): [describe(part) for part in condition.parts]}
    return {"not a condition": repr(condition)[:120]}


# --- The store ------------------------------------------------------------

def write_path(item: dict[str, Any], path: str, value: Any) -> None:
    parts = str(path).split(".")
    scope = item
    for part in parts[:-1]:
        if not isinstance(scope.get(part), dict):
            scope[part] = {}
        scope = scope[part]
    scope[parts[-1]] = value


def remove_path(item: dict[str, Any], path: str) -> None:
    parts = str(path).split(".")
    scope: Any = item
    for part in parts[:-1]:
        scope = scope.get(part) if isinstance(scope, dict) else None
        if not isinstance(scope, dict):
            return
    scope.pop(parts[-1], None)


class Store:
    """The single table behind every entity, keyed by the entity's key value."""
    def __init__(self, items: Mapping[str, Mapping[str, Any]] | None = None):
        self._items = {str(key): deepcopy(dict(value)) for key, value in dict(items or {}).items()}

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))

    def get(self, key: str, projection: Sequence[str] | None = None) -> dict[str, Any] | None:
        """The stored item, or only the physical paths a projection names."""
        item = self._items.get(str(key))
        if item is None or projection is None:
            return deepcopy(item) if item is not None else None
        picked: dict[str, Any] = {}
        for path in projection:
            value = read_stored(item, path)
            if value is not ABSENT:
                write_path(picked, path, deepcopy(value))
        return picked

    def put(self, key: str, item: Mapping[str, Any], condition: Any = None) -> None:
        stored = self._items.get(str(key))
        if not evaluate(condition, stored if stored is not None else {}):
            raise ConditionalCheckFailed(f"the condition on {key} did not hold")
        self._items[str(key)] = deepcopy(dict(item))

    def update(self, key: str, patch: Mapping[str, Any], condition: Any = None) -> None:
        """Apply exactly the paths this patch names, or nothing at all."""
        stored = self._items.get(str(key))
        if stored is None:
            raise ConditionalCheckFailed(f"nothing is stored at {key}")
        if not evaluate(condition, stored):
            raise ConditionalCheckFailed(f"the condition on {key} did not hold")
        updated = deepcopy(stored)
        for path, value in dict(patch.get("set") or {}).items():
            write_path(updated, str(path), deepcopy(value))
        for path in patch.get("remove") or ():
            remove_path(updated, str(path))
        self._items[str(key)] = updated


# --- The published contract -----------------------------------------------

def validate_contract(document: Mapping[str, Any], item: Mapping[str, Any]) -> tuple[str, ...]:
    """What the partner importer and the checkout form say about one item.

    A contract document holds ``attributes``, ``required``, a ``required_when``
    list of ``{attribute, controller, values}`` implications, and ``maps`` for
    the nested contracts. An empty result means both ends would take the item.
    """

    return tuple(_complaints(dict(document or {}), dict(item or {}), ""))


def _complaints(document: Mapping[str, Any], scope: Mapping[str, Any], prefix: str) -> list[str]:
    found = [
        f"{prefix}{name} is required"
        for name in document.get("required") or ()
        if scope.get(str(name)) is None
    ]
    for rule in document.get("required_when") or ():
        controller = str(dict(rule).get("controller"))
        held = scope.get(controller)
        if held is not None and held in list(dict(rule).get("values") or ()):
            attribute = str(dict(rule).get("attribute"))
            if scope.get(attribute) is None:
                found.append(f"{prefix}{attribute} is required while {controller} is {held}")
    for name, nested in dict(document.get("maps") or {}).items():
        value = scope.get(str(name))
        if isinstance(value, Mapping):
            found.extend(_complaints(dict(nested), dict(value), f"{prefix}{name}."))
    return found


__all__ = (
    "ABSENT", "And", "Attr", "ConditionalCheckFailed", "Equals", "Exists", "Missing",
    "Not", "OneOf", "Or", "Requirement", "Schema", "SchemaError", "Store", "ValidationError",
    "apply_defaults", "describe", "evaluate", "from_stored", "key_attribute", "load_schema",
    "logical_path", "physical_path", "read_stored", "remove_path", "stored_paths",
    "to_stored", "validate_contract", "walk", "write_path",
)
