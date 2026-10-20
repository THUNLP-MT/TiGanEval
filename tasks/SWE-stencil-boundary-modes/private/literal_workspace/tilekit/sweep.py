"""The nightly kernel pass: one job config, one tile out."""

from __future__ import annotations

from typing import Any, Mapping

from . import contract
from .contract import Canvas, Grid, JobSpec, TileError, Window
from .edges import Read


def run(
    spec: JobSpec,
    operands: Mapping[str, Grid],
    out: Canvas | None = None,
) -> Grid:
    """Produce one tile from one job config.

    ``spec.mode`` is passed down to the accessor, so a job that asks for `wrap`
    takes an out-of-range index around the tile instead of filling with `cval`.
    """

    kernel = contract.KERNELS[spec.kernel]
    kinds = tuple(
        "absolute" if name in spec.standard_indexing else "relative"
        for name in spec.operands
    )
    arrays = tuple(operands[name] for name in spec.operands)
    field = next(
        (array for array, kind in zip(arrays, kinds) if kind == "relative"), arrays[0]
    )
    window = (
        Window.spanning(spec.neighborhood)
        if spec.neighborhood is not None
        else contract.infer_window(kernel, kinds)
    )
    dtype = spec.output_dtype or field.dtype
    if out is not None and (out.height, out.width) != (field.height, field.width):
        raise TileError("the frame buffer has the wrong shape for this tile")

    canvas = Canvas.blank(field.height, field.width, dtype, spec.cval)
    for row in range(window.top, field.height - window.bottom):
        for col in range(window.left, field.width - window.right):
            views = tuple(
                Read(array, row, col, spec.cval, spec.mode, kind == "absolute")
                for array, kind in zip(arrays, kinds)
            )
            canvas.set(row, col, kernel(*views))
    return canvas.freeze()
