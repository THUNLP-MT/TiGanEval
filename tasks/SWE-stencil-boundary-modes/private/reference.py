'What the tile contract says one pass produces.'

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

TASK_ROOT = Path(__file__).resolve().parents[1]
_FROZEN: Any = None


def frozen_contract() -> Any:
    'The tile contract as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "tilekit" / "contract.py"
        spec = importlib.util.spec_from_file_location("_frozen_tile_contract", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


class _OutOfReach(Exception):
    'An absolutely indexed read that lands outside its own operand.'

    def __init__(self, row: int, col: int, height: int, width: int):
        super().__init__(f"({row}, {col}) outside {height}x{width}")
        self.fields = {
            "asked_row": int(row), "asked_col": int(col),
            "table_rows": int(height), "table_cols": int(width),
        }


def normalise_modes(mode: Any, rank: int = 2) -> tuple[str, ...]:
    'The boundary setting of one job as one name per axis.'

    protocol = frozen_contract()
    if isinstance(mode, str):
        names = (mode,) * int(rank)
    elif isinstance(mode, (list, tuple)):
        names = tuple(str(item) for item in mode)
    else:
        raise protocol.ModeError(f"a boundary setting cannot be {mode!r}")
    if len(names) != int(rank):
        raise protocol.ModeError(f"{len(names)} boundary names for {rank} axes")
    for name in names:
        if name not in protocol.MODES:
            raise protocol.ModeError(f"the boundary vocabulary has no {name!r}")
    return names


def setting_text(mode: Any) -> str:
    'The boundary setting as the config file spells it out.'

    if isinstance(mode, (list, tuple)):
        return ", ".join(str(item) for item in mode)
    return str(mode)


def modes_text(modes: Sequence[str]) -> str:
    'One boundary setting in the words the operations console uses.'

    return f"{modes[0]} from row to row and {modes[1]} from column to column"


def _frame_conflict(frame: Mapping[str, Any], spec: Any, field: Any) -> dict[str, Any] | None:
    "Why the buffer the box handed back cannot hold this job's tile, if it cannot."

    cells = frame["cells"]
    height, width = len(cells), (len(cells[0]) if cells else 0)
    if (height, width) != (field.height, field.width):
        return {
            "raised": "frame_shape",
            "buffer_shape": f"{height}x{width}",
            "tile_shape": f"{field.height}x{field.width}",
        }
    declared = spec.output_dtype
    held = str(frame["dtype"])
    if declared is not None and held != str(declared):
        return {"raised": "cell_type", "declared_dtype": str(declared), "buffer_dtype": held}
    return None


class _View:
    'One operand read the way the contract says it resolves.'

    def __init__(self, grid, row, col, cval, modes, absolute, flags):
        self.grid, self.row, self.col = grid, row, col
        self.cval, self.modes, self.absolute, self.flags = cval, modes, absolute, flags

    def __getitem__(self, offset: Any) -> Any:
        protocol = frozen_contract()
        first, second = offset
        if self.absolute:
            row, col = int(first), int(second)
            if not (0 <= row < self.grid.height and 0 <= col < self.grid.width):
                raise _OutOfReach(row, col, self.grid.height, self.grid.width)
            return self.grid.value(row, col)
        row = protocol.map_index(self.grid.height, self.row + int(first), self.modes[0])
        if row is None:
            self.flags["filled"] = True
            return self.cval
        col = protocol.map_index(self.grid.width, self.col + int(second), self.modes[1])
        if col is None:
            self.flags["filled"] = True
            return self.cval
        return self.grid.value(row, col)


def _grid(document: Mapping[str, Any]) -> Any:
    protocol = frozen_contract()
    return protocol.Grid.of(document["cells"], str(document.get("dtype", "int32")))


def _render(spec, arrays, kinds, modes, window, start, dtype) -> dict[str, Any]:
    'Produce one tile from the contract, cell by cell.'

    protocol = frozen_contract()
    kernel = protocol.KERNELS[spec.kernel]
    field = next(
        (array for array, kind in zip(arrays, kinds) if kind == "relative"), arrays[0]
    )
    height, width = field.height, field.width
    cells = [list(row) for row in start]
    applied = [[False] * width for _ in range(height)]
    filled = [[False] * width for _ in range(height)]
    edges = [[(False, False)] * width for _ in range(height)]
    for row in range(height):
        for col in range(width):
            row_out = row - window.top < 0 or row + window.bottom >= height
            col_out = col - window.left < 0 or col + window.right >= width
            edges[row][col] = (row_out, col_out)
            if (row_out and modes[0] == "constant") or (col_out and modes[1] == "constant"):
                continue
            flags = {"filled": False}
            views = [
                _View(array, row, col, spec.cval, modes, kind == "absolute", flags)
                for array, kind in zip(arrays, kinds)
            ]
            cells[row][col] = kernel(*views)
            applied[row][col] = True
            filled[row][col] = bool(flags["filled"])
    return {
        "cells": [[protocol.cast(dtype, value) for value in row] for row in cells],
        "applied": applied,
        "filled": filled,
        "edges": edges,
        "dtype": dtype,
    }


def render_reference(event: Mapping[str, Any]) -> dict[str, Any]:
    'What the mosaic service says this pass produces, or why it cannot run.'

    protocol = frozen_contract()
    spec = protocol.load_job(dict(event["job"]))
    kinds = tuple(
        "absolute" if name in spec.standard_indexing else "relative"
        for name in spec.operands
    )
    arrays = tuple(_grid(dict(event["operands"])[name]) for name in spec.operands)
    try:
        modes = normalise_modes(spec.mode)
    except protocol.ModeError:
        return {"raised": "mode", "setting": setting_text(spec.mode)}
    kernel = protocol.KERNELS[spec.kernel]
    window = (
        protocol.Window.spanning(spec.neighborhood)
        if spec.neighborhood is not None
        else protocol.infer_window(kernel, kinds)
    )
    field = next(
        (array for array, kind in zip(arrays, kinds) if kind == "relative"), arrays[0]
    )
    frame = event.get("frame")
    if frame is not None:
        conflict = _frame_conflict(frame, spec, field)
        if conflict is not None:
            return conflict
    dtype = str(frame["dtype"]) if frame else (spec.output_dtype or field.dtype)
    start = (
        [list(row) for row in frame["cells"]]
        if frame
        else [[spec.cval] * field.width for _ in range(field.height)]
    )
    try:
        outcome = _render(spec, arrays, kinds, modes, window, start, dtype)
    except _OutOfReach as exc:
        return {"raised": "operand", **exc.fields}
    outcome["modes"] = tuple(modes)
    outcome["constant_only"] = set(modes) == {"constant"}
    outcome["swapped"] = None
    if modes[0] != modes[1] and "constant" not in modes:
        try:
            outcome["swapped"] = _render(
                spec, arrays, kinds, (modes[1], modes[0]), window, start, dtype
            )["cells"]
        except _OutOfReach:
            outcome["swapped"] = None
    return outcome
