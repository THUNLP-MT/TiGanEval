"""The control plane's route compiler.

What a route serves is whatever this returns: the plan the proxy loads for the
route, built from the policy documents the controller reconciled onto it.

Nothing the controller happens to do reaches the proxy. The documents are read
through `protocol.admit`, so a document the plane cannot apply as written stops
the push instead of being applied in part. A policy that turns pinning off
empties the route rather than merely adding nothing to it. What is left is
grouped by kind in the order the proxy requires, and inside a kind the more
specific policy's entries come first and are ordered by key, so neither the
reconcile order nor the order the entries are written in can move a shopper.
Each key survives once, in the definition of the policy that outranks the rest.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import protocol


def _step(kind: str, entry: Mapping[str, Any]) -> protocol.Step:
    """One authored entry as the step the proxy is given."""

    body = dict(entry)
    stop = bool(body.get("stop", False))
    if kind == "header":
        return protocol.Step(
            kind="header",
            key=protocol.normalise_key("header", body["name"]),
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


def compile_route(
    route: protocol.Route, documents: Sequence[Mapping[str, Any]]
) -> tuple[protocol.Step, ...]:
    """The pin plan this route should serve."""

    policies = [protocol.admit(document) for document in documents]
    if any(policy.disabled for policy in policies):
        return ()

    ordered: list[tuple[Any, str, Mapping[str, Any]]] = []
    for policy in policies:
        for kind, index, entry in policy.entries:
            place = (
                protocol.CANONICAL_KINDS.index(kind),
                protocol.rank(policy),
                protocol.normalise_key(kind, dict(entry).get("name", "")),
                index,
            )
            ordered.append((place, kind, entry))
    ordered.sort(key=lambda item: item[0])

    steps: list[protocol.Step] = []
    seen: set[tuple[str, str]] = set()
    for _place, kind, entry in ordered:
        identity = (kind, protocol.normalise_key(kind, dict(entry).get("name", "")))
        if identity in seen:
            continue
        seen.add(identity)
        steps.append(_step(kind, entry))

    plan = tuple(steps)
    protocol.check_plan(plan)
    return plan
