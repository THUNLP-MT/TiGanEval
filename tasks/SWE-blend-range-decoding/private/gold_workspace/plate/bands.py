"""The range work the designers store on a layer, as numbers the exporter can use.

One stored entry carries four sliders: a dark and a light slider read against
the layer itself, then a dark and a light slider read against whatever the
plate already holds beneath it. Each slider carries two grips; where they were
dragged apart the layer fades between them instead of stopping at one of them.
The model keeps every grip it read, so a file that goes back to the studio goes
back with the designer's work on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .protocol import entries, pack_handles, unpack_handles


@dataclass(frozen=True, slots=True)
class Slider:
    """One slider's two grips, on the same 0..255 scale as a pixel."""

    left: int
    right: int

    @classmethod
    def read(cls, word: int) -> "Slider":
        left, right = unpack_handles(word)
        return cls(left, right)

    def word(self) -> int:
        return pack_handles(self.left, self.right)

    def dark_weight(self, value: float) -> float:
        """Nothing below the left grip, everything from the right grip up."""

        if value >= self.right:
            return 1.0
        if value <= self.left:
            return 0.0
        return (value - self.left) / (self.right - self.left)

    def light_weight(self, value: float) -> float:
        """Everything up to the left grip, nothing above the right grip."""

        if value <= self.left:
            return 1.0
        if value >= self.right:
            return 0.0
        return (self.right - value) / (self.right - self.left)


@dataclass(frozen=True, slots=True)
class Entry:
    """The four sliders of one stored entry, in the order they are stored."""

    own_dark: Slider
    own_light: Slider
    under_dark: Slider
    under_light: Slider

    @classmethod
    def read(cls, words: Sequence[int]) -> "Entry":
        first, second, third, fourth = (Slider.read(word) for word in words)
        return cls(first, second, third, fourth)

    def words(self) -> tuple[int, int, int, int]:
        return (
            self.own_dark.word(),
            self.own_light.word(),
            self.under_dark.word(),
            self.under_light.word(),
        )

    def weights(self, own: float, under: float) -> tuple[float, float, float, float]:
        """What this entry contributes, read against the layer and against the
        plate beneath it."""

        return (
            self.own_dark.dark_weight(own),
            self.own_light.light_weight(own),
            self.under_dark.dark_weight(under),
            self.under_light.light_weight(under),
        )


@dataclass(frozen=True, slots=True)
class LayerBands:
    """Every stored entry of one layer, in stored order."""

    entries: tuple[Entry, ...]


def decode(block: Sequence[int] | None) -> LayerBands | None:
    """Read one layer's stored block. A layer that carries none keeps none."""

    if block is None:
        return None
    return LayerBands(tuple(Entry.read(words) for words in entries(block)))


def encode(model: LayerBands | None) -> list[int] | None:
    """Write one layer's range work back into the words it was stored as."""

    if model is None:
        return None
    words: list[int] = []
    for entry in model.entries:
        words.extend(entry.words())
    return words
