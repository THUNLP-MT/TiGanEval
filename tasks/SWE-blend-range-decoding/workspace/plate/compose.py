"""Flatten one plate: composite every layer onto the backdrop, bottom layer first."""

from __future__ import annotations

from typing import Any, Sequence

from . import bands
from .protocol import Document, colour_of, luminosity, mix


def weight(layer: Any, pixel: Sequence[int]) -> float:
    """How much of one layer pixel is drawn, on the numbers its sliders carry."""

    numbers = bands.decode(layer.block)
    if numbers is None:
        return 1.0
    dark, light = numbers
    grey = luminosity(colour_of(pixel, layer.channels))
    return 1.0 if dark < grey < light else 0.0


def flatten(document: Document) -> list[list[tuple[int, int, int]]]:
    """The plate the exporter publishes for one shot."""

    plate = [list(row) for row in document.backdrop]
    for layer in document.layers:
        for row in range(document.rows):
            for column in range(document.columns):
                pixel = layer.pixel(row, column)
                plate[row][column] = mix(
                    plate[row][column],
                    pixel,
                    layer.channels,
                    weight(layer, pixel),
                    layer.opacity,
                )
    return plate
