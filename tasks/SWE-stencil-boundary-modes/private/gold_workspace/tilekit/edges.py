"""How a pass reads its operands while it is producing one cell."""

from __future__ import annotations

from typing import Any, Sequence

from .contract import Grid, MODES, ModeError, OperandError, map_index


def boundary_names(mode: Any, rank: int = 2) -> tuple[str, ...]:
    """One boundary name per axis, whichever way the config spelled it.

    A single name stands for every axis; a list or tuple gives one name per
    axis in row-then-column order. Anything the vocabulary does not contain,
    and any spelling that does not carry exactly one name per axis, is refused
    here, before the pass has produced anything.
    """

    if isinstance(mode, str):
        names = (mode,) * int(rank)
    elif isinstance(mode, (list, tuple)):
        names = tuple(str(item) for item in mode)
    else:
        raise ModeError(f"a boundary setting cannot be {mode!r}")
    if len(names) != int(rank):
        raise ModeError(
            f"the boundary setting carries {len(names)} names for {rank} axes"
        )
    for name in names:
        if name not in MODES:
            raise ModeError(f"the boundary vocabulary has no {name!r}")
    return names


class Read:
    """One operand as the kernel sees it at the cell being produced.

    ``absolute`` marks an operand addressed by its own coordinates rather than
    by offsets from the cell: its coordinates mean the same thing everywhere on
    the tile, so no boundary rule is applied to them and a coordinate outside
    the operand is refused rather than moved somewhere it does exist.
    """

    __slots__ = ("grid", "row", "col", "cval", "modes", "absolute")

    def __init__(
        self,
        grid: Grid,
        row: int,
        col: int,
        cval: Any = 0,
        modes: Sequence[str] = ("constant", "constant"),
        absolute: bool = False,
    ):
        self.grid = grid
        self.row = int(row)
        self.col = int(col)
        self.cval = cval
        self.modes = tuple(modes)
        self.absolute = bool(absolute)

    def __getitem__(self, offset: Any) -> Any:
        first, second = offset
        if self.absolute:
            row, col = int(first), int(second)
            if not (0 <= row < self.grid.height and 0 <= col < self.grid.width):
                raise OperandError(
                    f"({row}, {col}) is outside a "
                    f"{self.grid.height}x{self.grid.width} operand"
                )
            return self.grid.value(row, col)
        row = map_index(self.grid.height, self.row + int(first), self.modes[0])
        if row is None:
            return self.cval
        col = map_index(self.grid.width, self.col + int(second), self.modes[1])
        if col is None:
            return self.cval
        return self.grid.value(row, col)
