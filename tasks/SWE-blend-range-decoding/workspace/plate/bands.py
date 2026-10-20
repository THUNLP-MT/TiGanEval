"""First cut at reading the range sliders the design tool stores on a layer.

`decode` turns the words stored on one layer into the numbers its sliders sit
at, so the compositor has something to work with. `encode` is not written.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import entries, unpack_handles


def decode(block: Sequence[int] | None) -> Any:
    """The two numbers on this layer's first pair of sliders."""

    if block is None:
        return None
    first = entries(block)[0]
    return (unpack_handles(first[0])[0], unpack_handles(first[1])[0])


def encode(model: Any) -> Any:
    """Turn what `decode` produced back into the words a layer stores."""

    raise NotImplementedError("the export path does not write slider values back yet")
