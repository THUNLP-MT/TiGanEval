"""The nightly kernel pass: one job config, one tile out."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import contract
from .contract import Canvas, Grid, JobSpec, TileError, Window
from .edges import Read, boundary_names


def _off_the_axes(window: Window, height: int, width: int, row: int, col: int):
    """Whether the kernel reaches past the top or bottom, and past the sides."""

    return (
        row - window.top < 0 or row + window.bottom >= height,
        col - window.left < 0 or col + window.right >= width,
    )


def _produces(
    window: Window, modes: Sequence[str], height: int, width: int, row: int, col: int
) -> bool:
    """Whether the kernel runs at this cell, or the cell keeps what it holds.

    Only a `constant` axis stops the kernel: on that axis anything the window
    reaches past the edge for is left as the canvas started. Every other rule
    resolves an out-of-range read to a cell that does exist, so the kernel runs
    on the whole field, border rows and border columns included.
    """

    row_out, col_out = _off_the_axes(window, height, width, row, col)
    if row_out and modes[0] == "constant":
        return False
    return not (col_out and modes[1] == "constant")


def run(
    spec: JobSpec,
    operands: Mapping[str, Grid],
    out: Canvas | None = None,
) -> Grid:
    """Produce one tile from one job config.

    ``operands`` holds every raster the job's kernel names, and ``out`` is the
    frame buffer the mosaic service hands back when it wants one reused; the
    cells this pass does not produce keep whatever that buffer already held.
    """

    kernel = contract.KERNELS[spec.kernel]
    kinds = tuple(
        "absolute" if name in spec.standard_indexing else "relative"
        for name in spec.operands
    )
    arrays = tuple(operands[name] for name in spec.operands)
    modes = boundary_names(spec.mode, 2)
    field = next(
        (array for array, kind in zip(arrays, kinds) if kind == "relative"), arrays[0]
    )
    window = (
        Window.spanning(spec.neighborhood)
        if spec.neighborhood is not None
        else contract.infer_window(kernel, kinds)
    )
    dtype = spec.output_dtype or field.dtype
    if out is not None:
        if (out.height, out.width) != (field.height, field.width):
            raise TileError("the frame buffer has the wrong shape for this tile")
        if spec.output_dtype is not None and out.dtype != spec.output_dtype:
            raise TileError("the frame buffer holds a different cell type")
        canvas = out
    else:
        canvas = Canvas.blank(field.height, field.width, dtype, spec.cval)

    for row in range(field.height):
        for col in range(field.width):
            if not _produces(window, modes, field.height, field.width, row, col):
                continue
            views = tuple(
                Read(array, row, col, spec.cval, modes, kind == "absolute")
                for array, kind in zip(arrays, kinds)
            )
            canvas.set(row, col, kernel(*views))
    return canvas.freeze()
