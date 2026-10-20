"""The control plane's route compiler.

What a route serves is whatever this returns: the plan the proxy loads for the
route, built from the policy documents the controller reconciled onto it.

This is where the contractor's first cut stopped. It walks the documents in
the order the controller hands them over and takes the header lines out of
each one; cookies, query parameters and the client address are still on the
floor, and nothing here has ever looked at `disable`.

`documents` are the policy documents the controller reconciled onto this route,
in whatever order it reconciled them. `route` carries the route's name and the
pods behind it.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import protocol


def compile_route(
    route: protocol.Route, documents: Sequence[Mapping[str, Any]]
) -> tuple[protocol.Step, ...]:
    """The pin plan this route should serve."""

    steps: list[protocol.Step] = []
    for document in documents:
        pins = dict(dict(document).get("pins") or {})
        for entry in pins.get("headers") or ():
            steps.append(protocol.Step(kind="header", key=str(dict(entry)["name"])))
    return tuple(steps)
