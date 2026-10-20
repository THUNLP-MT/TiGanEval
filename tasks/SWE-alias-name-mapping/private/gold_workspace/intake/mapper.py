"""Loaders for one shape under one partner's mapping configuration.

`build_loader` turns a shape and a merged configuration into the object intake
uses for that partner: `load` reads one posted payload into a record, `dump`
writes a record back out, and `input_schema` is what the partner fetches before
they post. A field may be posted under more than one key; the set of keys that
carry it is settled once, when the loader is built, and every surface that
names a key reads it from there.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    COLLECT,
    FORBID,
    AmbiguousKeysError,
    ConfigError,
    ExtraFieldsError,
    FieldSpec,
    MappingConfig,
    MissingFieldError,
    Shape,
    coerce,
    convert_name,
    declared_aliases,
    declared_styles,
    schema_property,
    unwrap_payload,
)


def primary_key(field: FieldSpec, config: MappingConfig) -> str:
    """The key this field is published under and written back out under."""

    key = str(field.id)
    if config.trim_trailing_underscore:
        key = key.rstrip("_")
    if config.name_style:
        key = convert_name(key, config.name_style)
    return str(dict(config.rename or {}).get(field.id, key))


def alias_keys(field: FieldSpec, config: MappingConfig) -> tuple[str, ...]:
    """The further keys a partner may post this field under.

    A listed alias is a key an outside system already spells that way, so it is
    taken exactly as written. A generated one is the field's own name in the
    asked-for style, whatever the field is published under.
    """

    spelled = [str(alias) for alias in declared_aliases(config, field.id)]
    spelled += [convert_name(field.id, style) for style in declared_styles(config)]
    return tuple(spelled)


class Loader:
    """One partner's view of one shape."""

    def __init__(self, shape: Shape, config: MappingConfig):
        self.shape = shape
        self.config = config
        self.primary = {field.id: primary_key(field, config) for field in shape.fields}
        self.accepted: dict[str, tuple[str, ...]] = {}
        self.owner: dict[str, str] = {}
        for field in shape.fields:
            keys = tuple(
                dict.fromkeys((self.primary[field.id], *alias_keys(field, config)))
            )
            for key in keys:
                held = self.owner.get(key)
                if held is not None and held != field.id:
                    raise ConfigError(
                        f"{shape.name}: {held} and {field.id} both accept {key!r}"
                    )
                self.owner[key] = field.id
            self.accepted[field.id] = keys
        self.known = frozenset(self.owner)

    def load(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        payload = unwrap_payload(raw)
        record: dict[str, Any] = {}
        for field in self.shape.fields:
            present = [key for key in self.accepted[field.id] if key in payload]
            if len(present) > 1:
                named = ", ".join(sorted(present))
                raise AmbiguousKeysError(
                    f"{field.id} arrived under more than one name: {named}",
                    trail=tuple(sorted(present)),
                )
            if present:
                record[field.id] = coerce(field, payload[present[0]], present[0])
            elif field.required:
                key = self.primary[field.id]
                raise MissingFieldError(f"{self.shape.name} needs {key}", trail=(key,))
            else:
                record[field.id] = field.default
        unknown = sorted(key for key in payload if key not in self.known)
        if unknown and self.config.extra_policy == FORBID:
            raise ExtraFieldsError(
                f"{self.shape.name} does not know {', '.join(unknown)}", trail=tuple(unknown)
            )
        if self.config.extra_policy == COLLECT:
            record[self.config.extra_in] = {key: payload[key] for key in unknown}
        return record

    def dump(self, record: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            self.primary[field.id]: record[field.id]
            for field in self.shape.fields
            if field.id in record
        }
        if self.config.extra_policy == COLLECT:
            payload.update(dict(record.get(self.config.extra_in) or {}))
        return payload

    def input_schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        for field in self.shape.fields:
            fragment = schema_property(field)
            for key in self.accepted[field.id]:
                properties[key] = dict(fragment)
        return {
            "title": self.shape.name,
            "type": "object",
            "properties": properties,
            "required": [
                self.primary[field.id]
                for field in self.shape.fields
                if field.required and len(self.accepted[field.id]) == 1
            ],
        }


def build_loader(shape: Shape, config: MappingConfig) -> Loader:
    """The loader intake uses for one partner."""

    return Loader(shape, config)
