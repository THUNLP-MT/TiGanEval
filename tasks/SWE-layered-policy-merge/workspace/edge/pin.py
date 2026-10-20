"""The pin key of one request against the plan its route serves.

The proxy calls this once per request, folds what it gets back with
`protocol.fold` and sends the request to `protocol.choose_pod` of that digest.
"""

from __future__ import annotations

from typing import Sequence

from . import protocol


def pin_parts(
    request: protocol.Request, steps: Sequence[protocol.Step]
) -> tuple[str, ...]:
    """The contributions this request makes to its pin digest."""

    parts: list[str] = []
    for step in steps:
        value = protocol.read_value(request, step)
        parts.append(protocol.part(step, "" if value is None else value))
    return tuple(parts)
