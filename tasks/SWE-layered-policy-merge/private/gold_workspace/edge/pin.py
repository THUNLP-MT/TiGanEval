"""The pin key of one request against the plan its route serves.

The proxy calls this once per request, folds what it gets back with
`protocol.fold` and sends the request to `protocol.choose_pod` of that digest.
A step whose value the request does not carry contributes nothing, so an
anonymous basket falls through to the next step instead of pinning on an empty
value; a value is rewritten before it is folded, so a rotating token suffix
does not move the shopper; and the walk ends after a step that contributed and
is marked stop.
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
        if value is None:
            continue
        parts.append(protocol.part(step, protocol.apply_rewrite(step.rewrite, value)))
        if step.stop:
            break
    return tuple(parts)
