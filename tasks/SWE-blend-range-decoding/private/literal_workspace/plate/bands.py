"""The range sliders the designers set, read as the numbers they sit at.

Each layer stores a dark number and a light number. The block they were read
from is carried along with them, and the two numbers go back into the two words
they came out of, so a file written back is the file that was read.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import entries, pack_handles, unpack_handles


def decode(block: Sequence[int] | None) -> Any:
    """The dark and light numbers on this layer, and the block they came from."""

    if block is None:
        return None
    first = entries(block)[0]
    return {
        "dark": unpack_handles(first[0])[0],
        "light": unpack_handles(first[1])[0],
        "block": [int(word) for word in block],
    }


def encode(model: Any) -> Any:
    """Put the two numbers back on the layer and leave the rest of the block alone."""

    if model is None:
        return None
    words = list(model["block"])
    words[0] = pack_handles(model["dark"], model["dark"])
    words[1] = pack_handles(model["light"], model["light"])
    return words
