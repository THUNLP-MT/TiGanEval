"""The control plane's route compiler.

Joana's plan, written out: take the fleet policy's entries for a kind, lay the
route policy's entries over them key by key so the route wins, and hand the
proxy the result grouped in the order it insists on.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import protocol


def _step(kind: str, entry: Mapping[str, Any]) -> protocol.Step:
    body = dict(entry)
    stop = bool(body.get("stop", False))
    if kind == "header":
        return protocol.Step(
            kind="header",
            key=str(body["name"]),
            rewrite=protocol.read_rewrite(body),
            stop=stop,
        )
    if kind == "cookie":
        return protocol.Step(
            kind="cookie",
            key=str(body["name"]),
            ttl=protocol.ttl_seconds(body.get("ttl", 0)),
            path=str(body.get("path", "/")),
            flags=tuple(str(flag) for flag in body.get("flags", ()) or ()),
            stop=stop,
        )
    if kind == "query":
        return protocol.Step(kind="query", key=str(body["name"]), stop=stop)
    return protocol.Step(kind="client", key="", stop=stop)


def _entries(document: Mapping[str, Any], kind: str) -> dict[str, Mapping[str, Any]]:
    pins = dict(dict(document).get("pins") or {})
    if kind == "client":
        return {"": dict(pins["client"] or {})} if "client" in pins else {}
    field = {"header": "headers", "cookie": "cookies", "query": "query"}[kind]
    return {str(dict(item)["name"]): dict(item) for item in pins.get(field) or ()}


def compile_route(
    route: protocol.Route, documents: Sequence[Mapping[str, Any]]
) -> tuple[protocol.Step, ...]:
    """The pin plan this route should serve."""

    ordered = sorted(
        documents,
        key=lambda document: 0 if str(dict(document).get("scope")) == "fleet" else 1,
    )
    steps: list[protocol.Step] = []
    for kind in protocol.CANONICAL_KINDS:
        merged: dict[str, Mapping[str, Any]] = {}
        for document in ordered:
            merged.update(_entries(document, kind))
        steps.extend(_step(kind, entry) for entry in merged.values())
    plan = tuple(steps)
    protocol.check_plan(plan)
    return plan
