"""Flatten one plate: composite every layer onto the backdrop, bottom layer first.

Each layer is drawn through the range work stored on it. The first entry is the
grey one: it is read against the luminosity of the layer and of the plate
beneath. Every entry after it belongs to one channel the layer declares, in
declared order; the transparency channel's entry is stored but drawn through
nothing, because a pixel's transparency already reaches the plate through
`mix`. A block a later release of the tool wrote runs past the last channel the
layer declares, and an entry that addresses no channel this layer stores is
drawn through nothing for the same reason: there is nothing to read it against.
What the entries produce multiplies together into one coverage weight.
"""

from __future__ import annotations

from typing import Any, Sequence

from . import bands
from .protocol import (
    COLOUR_CHANNELS,
    TRANSPARENCY,
    Document,
    channel_value,
    colour_of,
    combine,
    luminosity,
    mix,
)


def _samples(
    layer: Any, index: int, pixel: Sequence[int], beneath: Sequence[int]
) -> tuple[float, float] | None:
    """What one stored entry is read against: on the layer, on the plate beneath."""

    if index == 0:
        return (
            luminosity(colour_of(pixel, layer.channels)),
            luminosity(beneath),
        )
    position = index - 1
    if position >= len(layer.channels):
        return None
    channel = layer.channels[position]
    if channel == TRANSPARENCY:
        return None
    return (
        float(channel_value(pixel, layer.channels, channel)),
        float(beneath[COLOUR_CHANNELS.index(channel)]),
    )


def weight(
    layer: Any, model: Any, pixel: Sequence[int], beneath: Sequence[int]
) -> float:
    """How much of one layer pixel reaches the plate under its stored range work."""

    if model is None:
        return 1.0
    weights: list[float] = []
    for index, entry in enumerate(model.entries):
        samples = _samples(layer, index, pixel, beneath)
        if samples is None:
            continue
        weights.extend(entry.weights(*samples))
    return combine(weights)


def flatten(document: Document) -> list[list[tuple[int, int, int]]]:
    """The plate the exporter publishes for one shot."""

    plate = [list(row) for row in document.backdrop]
    for layer in document.layers:
        model = bands.decode(layer.block)
        for row in range(document.rows):
            for column in range(document.columns):
                pixel = layer.pixel(row, column)
                beneath = plate[row][column]
                plate[row][column] = mix(
                    beneath,
                    pixel,
                    layer.channels,
                    weight(layer, model, pixel, beneath),
                    layer.opacity,
                )
    return plate
