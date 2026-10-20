"""What the platform publishes out of one entity document.

`to_contract` is what the partner importer and the checkout form validate
against through `protocol.validate_contract`. `to_dto` / `from_dto` carry a
schema across a process boundary into the reconciliation worker.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import Attr, Schema, load_schema


def to_contract(schema: Schema) -> dict[str, Any]:
    return _contract(schema.attributes)


def _contract(attributes: Mapping[str, Attr]) -> dict[str, Any]:
    document: dict[str, Any] = {"attributes": {}, "required": [], "maps": {}}
    for name, attr in dict(attributes).items():
        document["attributes"][name] = {"type": attr.kind}
        if attr.required or attr.required_when:
            document["required"].append(name)
        if attr.kind == "map":
            document["maps"][name] = _contract(attr.attributes)
    return document


def to_dto(schema: Schema) -> dict[str, Any]:
    return {"name": schema.name, "attributes": _dto(schema.attributes)}


def _dto(attributes: Mapping[str, Attr]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, attr in dict(attributes).items():
        spec: dict[str, Any] = {
            "type": attr.kind,
            "stored_as": attr.stored_as,
            "required": attr.required,
            "key": attr.is_key,
        }
        if attr.default is not None:
            spec["default"] = attr.default
        if attr.kind == "map":
            spec["attributes"] = _dto(attr.attributes)
        document[name] = spec
    return document


def from_dto(document: Mapping[str, Any]) -> Schema:
    return load_schema(document)
