"""How a pass reads its operands while it is producing one cell."""

from __future__ import annotations

from typing import Any

from .contract import Grid, OperandError


class Read:
    """One operand as the kernel sees it at the cell being produced.

    ``absolute`` marks an operand addressed by its own coordinates rather than
    by offsets from the cell.
    """

    __slots__ = ("grid", "row", "col", "cval", "absolute")

    def __init__(
        self,
        grid: Grid,
        row: int,
        col: int,
        cval: Any = 0,
        absolute: bool = False,
    ):
        self.grid = grid
        self.row = int(row)
        self.col = int(col)
        self.cval = cval
        self.absolute = bool(absolute)

    def __getitem__(self, offset: Any) -> Any:
        first, second = offset
        row = int(first) if self.absolute else self.row + int(first)
        col = int(second) if self.absolute else self.col + int(second)
        if not (0 <= row < self.grid.height and 0 <= col < self.grid.width):
            if self.absolute:
                raise OperandError(
                    f"({row}, {col}) is outside a "
                    f"{self.grid.height}x{self.grid.width} operand"
                )
            return self.cval
        return self.grid.value(row, col)
