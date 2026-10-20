"""The three bundles as they run on a unit.

This is the vendor's own scorer, the one the exporter runs over every capture
it carries. It ships with the bundle drop and stays as it is.

`decide(bundle, capture)` takes a bundle name and a capture as a mapping from
column name to value, and returns 1 when the bundle reads the capture and 0
when it sends it back for a rescan. `cards.json` holds each bundle's front end
and its weights exactly as the vendor published them.
"""

import json
from pathlib import Path


COLUMNS = (
    "refl_a",
    "refl_b",
    "refl_c",
    "edge_density",
    "skew",
    "contrast",
    "blur",
    "tilt",
)
REFLECTANCE = ("refl_a", "refl_b", "refl_c")

CARDS = json.loads((Path(__file__).resolve().with_name("cards.json")).read_text(encoding="utf-8"))


def front_end(bundle, values):
    """The capture as this bundle's front end hands it to the rule."""

    card = CARDS[str(bundle)]
    row = [float(item) for item in values]
    span = card.get("window_span")
    if span is not None:
        for index in range(len(REFLECTANCE)):
            row[index] = min(row[index], float(span))
    return row


def score(bundle, capture):
    """The bundle's own score for one capture."""

    card = CARDS[str(bundle)]
    values = [float(capture[name]) for name in COLUMNS]
    row = front_end(bundle, values)
    total = float(card["intercept"])
    for weight, value in zip(card["weights"], row):
        total += float(weight) * value
    return total


def decide(bundle, capture):
    """1 when the bundle reads the capture, 0 when it sends it back."""

    return 1 if score(bundle, capture) >= 0.0 else 0
