"""Loaders for one shape under one partner's mapping configuration.

`build_loader` turns a shape and a merged configuration into the object intake
uses for that partner: `load` reads one posted payload into a record, `dump`
writes a record back out, and `input_schema` is what the partner fetches before
they post. The configuration's `aliases` and `alias_style` are carried through
the platform release but nothing below reads them yet.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    COLLECT,
    FORBID,
    ExtraFieldsError,
    FieldSpec,
    MappingConfig,
    MissingFieldError,
    Shape,
    coerce,
    convert_name,
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


class Loader:
    """One partner's view of one shape."""

    def __init__(self, shape: Shape, config: MappingConfig):
        self.shape = shape
        self.config = config
        self.primary = {field.id: primary_key(field, config) for field in shape.fields}
        self.owner = {key: field_id for field_id, key in self.primary.items()}

    def load(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        payload = unwrap_payload(raw)
        record: dict[str, Any] = {}
        for field in self.shape.fields:
            key = self.primary[field.id]
            if key in payload:
                record[field.id] = coerce(field, payload[key], key)
            elif field.required:
                raise MissingFieldError(f"{self.shape.name} needs {key}", trail=(key,))
            else:
                record[field.id] = field.default
        unknown = sorted(key for key in payload if key not in self.owner)
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
        return {
            "title": self.shape.name,
            "type": "object",
            "properties": {
                self.primary[field.id]: schema_property(field) for field in self.shape.fields
            },
            "required": [
                self.primary[field.id] for field in self.shape.fields if field.required
            ],
        }


def build_loader(shape: Shape, config: MappingConfig) -> Loader:
    """The loader intake uses for one partner."""

    return Loader(shape, config)
