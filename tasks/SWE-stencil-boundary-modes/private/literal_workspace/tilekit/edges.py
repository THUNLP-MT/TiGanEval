"""How a pass reads its operands while it is producing one cell."""

from __future__ import annotations

from typing import Any

from .contract import Grid, OperandError


class Read:
    """One operand as the kernel sees it at the cell being produced.

    ``mode`` says what to do when the window runs off the tile: ``wrap`` takes
    the index around to the far side instead of filling, and anything else
    leaves the fill value there as before.
    """

    __slots__ = ("grid", "row", "col", "cval", "mode", "absolute")

    def __init__(
        self,
        grid: Grid,
        row: int,
        col: int,
        cval: Any = 0,
        mode: Any = "constant",
        absolute: bool = False,
    ):
        self.grid = grid
        self.row = int(row)
        self.col = int(col)
        self.cval = cval
        self.mode = mode
        self.absolute = bool(absolute)

    def __getitem__(self, offset: Any) -> Any:
        first, second = offset
        row = int(first) if self.absolute else self.row + int(first)
        col = int(second) if self.absolute else self.col + int(second)
        if not (0 <= row < self.grid.height and 0 <= col < self.grid.width):
            if self.mode == "wrap":
                return self.grid.value(row % self.grid.height, col % self.grid.width)
            if self.absolute:
                raise OperandError(
                    f"({row}, {col}) is outside a "
                    f"{self.grid.height}x{self.grid.width} operand"
                )
            return self.cval
        return self.grid.value(row, col)
