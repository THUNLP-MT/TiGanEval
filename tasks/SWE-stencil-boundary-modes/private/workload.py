'Deterministic tiles, job configs and recorded nights for the imaging batch.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


def raster(mark: int, height: int, width: int, dtype: str = "int32") -> dict[str, Any]:
    'One input tile. Values mix both axes, so a tile is not its own transpose.'

    cells = [
        [(row * row * 13 + col * col * 7 + row * col * 5 + mark * 3 + 11) % 199
         for col in range(width)]
        for row in range(height)
    ]
    return {"dtype": dtype, "cells": cells}


def buffer(mark: int, height: int, width: int, dtype: str = "int32") -> dict[str, Any]:
    'A frame buffer the batch box keeps for a region between nights.'

    return {"dtype": dtype, "cells": [[mark] * width for _ in range(height)]}


FULL_TABLE = {"dtype": "int32", "cells": [[1], [2], [2], [2], [1]]}
SHORT_TABLE = {"dtype": "int32", "cells": [[1], [2], [2], [2]]}


def job(name: str, kernel: str, **fields: Any) -> dict[str, Any]:
    document: dict[str, Any] = {"job": name, "kernel": kernel}
    document.update({key: value for key, value in fields.items() if value is not None})
    return document


def rendering(
    label: str,
    document: Mapping[str, Any],
    operands: Mapping[str, Any],
    *,
    frame: Mapping[str, Any] | None = None,
    legacy: bool = False,
    note: str | None = None,
    pair: str | None = None,
) -> dict[str, Any]:
    'One pass of one recorded night.'

    event: dict[str, Any] = {
        "type": "pass",
        "label": label,
        "job": dict(document),
        "operands": {name: dict(grid) for name, grid in operands.items()},
        "legacy": bool(legacy),
    }
    if frame is not None:
        event["frame"] = dict(frame)
    if note is not None:
        event["note"] = note
    if pair is not None:
        event["pair"] = pair
    return event


def _coast(mark: int) -> list[dict[str, Any]]:
    return [
        rendering(
            "harbour-tile",
            job("harbour_blur", "broad_cross", mode="wrap", cval=0, output_dtype="int32"),
            {"a": raster(mark + 5, 9, 9)},
            legacy=True,
            note="the tile the coastline team filed against",
        ),
        rendering(
            "dune-tile",
            job("dune_blur", "cross_blur", cval=4),
            {"a": raster(mark + 12, 8, 8)},
        ),
        rendering(
            "terrain-wide-window",
            job("terrain_blur", "cross_blur", cval=3, neighborhood=[[-2, 2], [-2, 2]]),
            {"a": raster(mark + 23, 8, 8)},
        ),
        rendering(
            "shoal-short-cast",
            job("shoal", "box_mean", cval=0.0, output_dtype="int16"),
            {"a": raster(mark + 29, 6, 6)},
        ),
    ]


def _mirror(mark: int) -> list[dict[str, Any]]:
    return [
        rendering(
            "terrace-reflect",
            job("terrace", "row_smear", mode="reflect", cval=0),
            {"a": raster(mark + 31, 7, 7)},
            legacy=True,
        ),
        rendering(
            "shelf-symmetric",
            job("shelf", "column_smear", mode="symmetric", cval=0),
            {"a": raster(mark + 37, 7, 7)},
        ),
        rendering(
            "ledge-nearest",
            job("ledge", "cross_blur", mode="nearest", cval=0),
            {"a": raster(mark + 41, 6, 6)},
        ),
        rendering(
            "gorge-strip",
            job("gorge", "long_reach", mode="reflect", cval=0),
            {"a": raster(mark + 43, 5, 3)},
        ),
        rendering(
            "ledge-fill",
            job("ledge_edge", "cross_blur", mode="fill", cval=0,
                output_dtype="int16"),
            {"a": raster(mark + 45, 6, 6)},
            legacy=True,
        ),
        rendering(
            "terrace-default",
            job("terrace_plain", "row_smear", cval=2),
            {"a": raster(mark + 47, 6, 6)},
        ),
        rendering(
            "shelf-frame-reuse",
            job("shelf_smear", "row_smear", cval=0),
            {"a": raster(mark + 19, 7, 7)},
            frame=buffer(900, 7, 7),
        ),
        rendering(
            "shelf-band-hold",
            job("shelf_band", "cross_blur", mode=["constant", "wrap"], cval=0),
            {"a": raster(mark + 23, 6, 6)},
            frame=buffer(700, 6, 6),
            legacy=True,
        ),
    ]


def _globe(mark: int) -> list[dict[str, Any]]:
    swath = raster(mark + 59, 7, 5)
    return [
        rendering(
            "polar-band",
            job("polar_band", "box_mean", mode=["nearest", "wrap"], cval=0),
            {"a": raster(mark + 53, 6, 8)},
            legacy=True,
        ),
        rendering(
            "swath-scalar",
            job("swath", "cross_blur", mode="wrap", cval=0),
            {"a": dict(swath)},
            pair="swath",
        ),
        rendering(
            "swath-pair",
            job("swath", "cross_blur", mode=["wrap", "wrap"], cval=0),
            {"a": dict(swath)},
            pair="swath",
        ),
    ]


def _quarantine(mark: int) -> list[dict[str, Any]]:
    return [
        rendering(
            "harbour-nearset",
            job("harbour_blur", "broad_cross", mode="nearset", cval=0),
            {"a": raster(mark + 61, 7, 7)},
            frame=buffer(500, 7, 7),
        ),
        rendering(
            "ridge-list-edit",
            job("ridge_blur", "cross_blur", mode=["reflect", "reflect", "nearest"], cval=0),
            {"a": raster(mark + 59, 6, 6)},
        ),
        rendering(
            "cove-frame-misfit",
            job("cove_blur", "cross_blur", cval=0),
            {"a": raster(mark + 73, 6, 6)},
            frame=buffer(800, 5, 5),
        ),
        rendering(
            "cove-frame-cell-type",
            job("cove_cast", "cross_blur", cval=0, output_dtype="int16"),
            {"a": raster(mark + 79, 6, 6)},
            frame=buffer(800, 6, 6, dtype="int32"),
        ),
        rendering(
            "weighted-short",
            job("weighted", "weighted_cross", mode="wrap", cval=0,
                operands=["a", "w"], standard_indexing=["w"]),
            {"a": raster(mark + 67, 6, 6), "w": dict(SHORT_TABLE)},
        ),
        rendering(
            "weighted-full",
            job("weighted", "weighted_cross", mode="wrap", cval=0,
                operands=["a", "w"], standard_indexing=["w"]),
            {"a": raster(mark + 67, 6, 6), "w": dict(FULL_TABLE)},
        ),
        rendering(
            "weighted-default",
            job("weighted_plain", "weighted_cross", cval=0,
                operands=["a", "w"], standard_indexing=["w"]),
            {"a": raster(mark + 71, 6, 6), "w": dict(FULL_TABLE)},
        ),
    ]


def _release(mark: int) -> list[dict[str, Any]]:
    plateau = raster(mark + 113, 8, 5)
    coefficients = raster(mark + 151, 6, 6)
    return [
        rendering("harbour-wrap",
                  job("harbour_blur", "broad_cross", mode="wrap", cval=0,
                      output_dtype="int16"),
                  {"a": raster(mark + 101, 9, 9)}),
        rendering("ridge-reflect", job("ridge", "row_smear", mode="reflect", cval=0),
                  {"a": raster(mark + 103, 7, 7)}),
        rendering("shelf-symmetric", job("shelf", "column_smear", mode="symmetric", cval=0),
                  {"a": raster(mark + 107, 7, 7)}),
        rendering("narrow-swath",
                  job("narrow", "long_reach", mode=["symmetric", "reflect"], cval=0),
                  {"a": raster(mark + 109, 6, 3)}),
        rendering("plateau-scalar", job("plateau", "cross_blur", mode="nearest", cval=0),
                  {"a": dict(plateau)}, pair="plateau"),
        rendering("plateau-pair",
                  job("plateau", "cross_blur", mode=["nearest", "nearest"], cval=0),
                  {"a": dict(plateau)}, pair="plateau"),
        rendering("orbit-band", job("orbit", "box_mean", mode=["nearest", "wrap"], cval=0),
                  {"a": raster(mark + 127, 6, 8)}),
        rendering("survey-edge", job("survey", "cross_blur", mode="fill", cval=0),
                  {"a": raster(mark + 173, 7, 7)}),
        rendering("bay-band", job("bay", "box_mean", mode=["fill", "nearest"], cval=0),
                  {"a": raster(mark + 179, 6, 8)}),
        rendering("night-default", job("night", "cross_blur", cval=7, output_dtype="int32"),
                  {"a": raster(mark + 131, 8, 8)}),
        rendering("frame-reuse", job("frame", "row_smear", cval=0),
                  {"a": raster(mark + 137, 6, 6)}, frame=buffer(900, 6, 6)),
        rendering("bight-fill-frame", job("bight", "row_smear", mode="fill", cval=0),
                  {"a": raster(mark + 181, 6, 6)}, frame=buffer(600, 6, 6)),
        rendering("strait-mixed-frame",
                  job("strait", "cross_blur", mode=["constant", "wrap"], cval=0),
                  {"a": raster(mark + 191, 6, 6)}, frame=buffer(300, 6, 6)),
        rendering("frame-cell-type",
                  job("inlet", "row_smear", cval=0, output_dtype="int16"),
                  {"a": raster(mark + 197, 6, 6)}, frame=buffer(400, 6, 6)),
        rendering("frame-shape",
                  job("cove", "cross_blur", mode="wrap", cval=0),
                  {"a": raster(mark + 199, 6, 6)}, frame=buffer(800, 5, 5)),
        rendering("coarse-window",
                  job("coarse", "cross_blur", cval=3, neighborhood=[[-2, 2], [-2, 2]]),
                  {"a": raster(mark + 139, 7, 7)}),
        rendering("short-cast", job("short", "box_mean", cval=0.0, output_dtype="int16"),
                  {"a": raster(mark + 149, 5, 5)}),
        rendering("coefficients-full",
                  job("weighted", "weighted_cross", mode="wrap", cval=0,
                      operands=["a", "w"], standard_indexing=["w"]),
                  {"a": dict(coefficients), "w": dict(FULL_TABLE)}),
        rendering("coefficients-short",
                  job("weighted", "weighted_cross", mode="wrap", cval=0,
                      operands=["a", "w"], standard_indexing=["w"]),
                  {"a": dict(coefficients), "w": dict(SHORT_TABLE)}),
        rendering("typo-mode", job("harbour_blur", "broad_cross", mode="nearset", cval=0),
                  {"a": raster(mark + 157, 7, 7)}, frame=buffer(500, 7, 7)),
        rendering("wrong-arity",
                  job("orbit", "cross_blur", mode=["wrap", "nearest", "reflect"], cval=0),
                  {"a": raster(mark + 163, 7, 7)}),
    ]


PROGRAM_BUILDERS = {
    "coast": _coast,
    "mirror": _mirror,
    "globe": _globe,
    "quarantine": _quarantine,
    "release": _release,
}


def build_program(profile: str, mark: int, scale: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown recorded night: {profile}")
    return [{"phase": profile, **event} for event in builder(int(mark))]


def spelling_pairs(program: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    'The passes a night runs twice with the boundary setting written two ways.'

    groups: dict[str, list[str]] = {}
    for event in program:
        name = event.get("pair")
        if name:
            groups.setdefault(str(name), []).append(str(event.get("label")))
    return [(labels[0], labels[1]) for labels in groups.values() if len(labels) == 2]
