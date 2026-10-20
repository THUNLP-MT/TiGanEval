"""The plate format and the parts of the compositor that ship with the design tool.

A plate is one product shot: an opaque backdrop with a stack of layers
composited onto it, bottom layer first. Everything in this module is shared
with the design tool the studio draws in and with the page exporter that
publishes the finished plates, so it ships in their release rather than ours
and stays as it is.

Pixels are whole numbers 0 to 255. A layer declares the channels it stores in
``channels``: the colour channels ``r``, ``g`` and ``b`` in some order, and,
when the layer was drawn with soft edges, the transparency channel ``a`` as
well. One stored pixel carries one number per declared channel, in the order
the layer declares them.

Each layer also carries the range work the designers do with the sliders in
the tool, stored in ``block``: a flat list of 16-bit words, read four words to
an entry, or ``None`` on a layer whose sliders nobody has ever moved. One word
holds two grips of one slider, the low byte first and the high byte second
(``unpack_handles``), so a slider whose grips were dragged apart stores two
different bytes in the one word. Within an entry the first two words are one
pair of sliders and the last two are another pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

#: The colour channels every layer stores, whatever order it declares them in.
COLOUR_CHANNELS = ("r", "g", "b")

#: The channel id of the transparency channel, on the layers that store one.
TRANSPARENCY = "a"

#: One stored range entry is four words: two sliders, two grips each.
WORDS_PER_ENTRY = 4

#: The entry a layer carries where nobody has moved its sliders: both grips of
#: the first slider of each pair at 0, both grips of the second at 255.
DEFAULT_ENTRY = (0, 65535, 0, 65535)

#: The largest value one stored word can hold.
MAX_WORD = 0xFFFF


class PlateError(ValueError):
    """A stored plate does not match the format the design tool writes."""


def unpack_handles(word: int) -> tuple[int, int]:
    """The two grips one stored word carries: low byte first, high byte second.

    Both grips sit on the same 0..255 scale as a pixel. A slider nobody has
    split stores the same byte twice.
    """

    value = int(word)
    if not 0 <= value <= MAX_WORD:
        raise PlateError(f"a stored word must be 0..{MAX_WORD}: {value}")
    return value & 0xFF, (value >> 8) & 0xFF


def pack_handles(left: int, right: int) -> int:
    """The stored word for one slider's two grips."""

    low, high = int(left), int(right)
    for grip in (low, high):
        if not 0 <= grip <= 255:
            raise PlateError(f"a grip must be 0..255: {grip}")
    return low | (high << 8)


def entries(block: Sequence[int] | None) -> tuple[tuple[int, int, int, int], ...]:
    """Split one stored block into its four-word entries, in stored order."""

    if block is None:
        return ()
    words = [int(word) for word in block]
    if len(words) % WORDS_PER_ENTRY:
        raise PlateError(
            f"a stored block holds whole entries of {WORDS_PER_ENTRY} words: {len(words)}"
        )
    return tuple(
        (words[at], words[at + 1], words[at + 2], words[at + 3])
        for at in range(0, len(words), WORDS_PER_ENTRY)
    )


def luminosity(colour: Sequence[int]) -> float:
    """The grey value of one colour, on the studio's own weighting."""

    red, green, blue = (int(value) for value in colour)
    return (299 * red + 587 * green + 114 * blue) / 1000.0


def combine(weights: Iterable[float]) -> float:
    """Fold the weights a layer's range work produces into one coverage weight."""

    total = 1.0
    for weight in weights:
        total *= float(weight)
    return 0.0 if total < 0.0 else 1.0 if total > 1.0 else total


def quantize(value: float) -> int:
    """Round one channel value back to the stored 0..255, half upwards.

    The small tolerance keeps two arithmetically equivalent routes to the same
    value on the same side of a boundary, so the studio's tool and the pipeline
    publish the same bytes.
    """

    number = float(value)
    if number <= 0.0:
        return 0
    if number >= 255.0:
        return 255
    return int(number + 0.5 + 1e-9)


def channel_value(pixel: Sequence[int], channels: Sequence[str], channel: str) -> int:
    """The value one stored pixel holds for one declared channel."""

    order = tuple(channels)
    if channel not in order:
        raise PlateError(f"this layer does not declare channel {channel!r}: {order}")
    return int(pixel[order.index(channel)])


def colour_of(pixel: Sequence[int], channels: Sequence[str]) -> tuple[int, int, int]:
    """The r, g, b of one stored pixel, whatever else the layer declares."""

    red, green, blue = (
        channel_value(pixel, channels, channel) for channel in COLOUR_CHANNELS
    )
    return red, green, blue


def coverage(
    weight: float, pixel: Sequence[int], channels: Sequence[str], opacity: int
) -> float:
    """How much of one layer pixel reaches the plate: its weight, the layer's
    opacity, and the pixel's own transparency where the layer stores one."""

    fraction = float(weight) * (int(opacity) / 255.0)
    if TRANSPARENCY in tuple(channels):
        fraction *= channel_value(pixel, channels, TRANSPARENCY) / 255.0
    return fraction


def mix(
    beneath: Sequence[int],
    pixel: Sequence[int],
    channels: Sequence[str],
    weight: float,
    opacity: int,
) -> tuple[int, int, int]:
    """Composite one layer pixel onto what the plate already holds there."""

    fraction = coverage(weight, pixel, channels, opacity)
    source = colour_of(pixel, channels)
    under = tuple(int(value) for value in beneath)
    return tuple(
        quantize(low + (high - low) * fraction) for low, high in zip(under, source)
    )


@dataclass(frozen=True, slots=True)
class Layer:
    """One layer of a plate as the design tool stored it."""

    name: str
    channels: tuple[str, ...]
    opacity: int
    pixels: tuple[tuple[tuple[int, ...], ...], ...]
    block: tuple[int, ...] | None

    def pixel(self, row: int, column: int) -> tuple[int, ...]:
        return self.pixels[row][column]


@dataclass(frozen=True, slots=True)
class Document:
    """One product shot: a backdrop and the layers drawn over it."""

    shot: str
    backdrop: tuple[tuple[tuple[int, int, int], ...], ...]
    layers: tuple[Layer, ...]

    @property
    def rows(self) -> int:
        return len(self.backdrop)

    @property
    def columns(self) -> int:
        return len(self.backdrop[0]) if self.backdrop else 0


def _pixels(raw: Any, width: int) -> tuple[tuple[tuple[int, ...], ...], ...]:
    rows = []
    for row in raw:
        pixels = tuple(tuple(int(value) for value in pixel) for pixel in row)
        if len(pixels) != width:
            raise PlateError(f"a layer row holds {len(pixels)} pixels, not {width}")
        rows.append(pixels)
    return tuple(rows)


def read_document(payload: Mapping[str, Any]) -> Document:
    """Read one stored plate as the exporter reads it off disk."""

    backdrop = tuple(
        tuple(tuple(int(value) for value in pixel) for pixel in row)
        for row in payload["backdrop"]
    )
    if not backdrop:
        raise PlateError("a plate has at least one row")
    width = len(backdrop[0])
    layers = []
    for raw in payload.get("layers", ()):
        block = raw.get("block")
        layers.append(
            Layer(
                name=str(raw["name"]),
                channels=tuple(str(channel) for channel in raw["channels"]),
                opacity=int(raw.get("opacity", 255)),
                pixels=_pixels(raw["pixels"], width),
                block=None if block is None else tuple(int(word) for word in block),
            )
        )
    return Document(str(payload.get("shot", "plate")), backdrop, tuple(layers))


def plain_stack(document: Document) -> list[list[tuple[int, int, int]]]:
    """The plate this compositor published before any layer stored range work.

    Every layer covers what is beneath it in full, so nothing in ``block`` is
    read. The exporter still runs this for the plates it has to reproduce
    exactly as they went out.
    """

    plate = [list(row) for row in document.backdrop]
    for layer in document.layers:
        for row in range(document.rows):
            for column in range(document.columns):
                pixel = layer.pixel(row, column)
                plate[row][column] = mix(
                    plate[row][column], pixel, layer.channels, 1.0, layer.opacity
                )
    return plate


__all__ = (
    "COLOUR_CHANNELS",
    "DEFAULT_ENTRY",
    "Document",
    "Layer",
    "MAX_WORD",
    "PlateError",
    "TRANSPARENCY",
    "WORDS_PER_ENTRY",
    "channel_value",
    "colour_of",
    "combine",
    "coverage",
    "entries",
    "luminosity",
    "mix",
    "pack_handles",
    "plain_stack",
    "quantize",
    "read_document",
    "unpack_handles",
)
