"""The tile contract the mosaic service and the legacy renderer are built on.

This module ships in the mosaic service's release. It owns the raster types
(`Grid`, `Canvas`), the boundary vocabulary (`MODES`, `map_index`), the window
a kernel reaches over (`Window`, `infer_window`), the kernel library the
nightly job draws from (`KERNELS`), and the job-config reader (`load_job`).
Everything here is integer arithmetic; there is no clock, no randomness and no
tolerance anywhere, so two renders of the same pass are the same tile.

A pass produces its tile through a `Canvas`. Every `set` is noted, so
`trace_writes()` returns the cells a block of passes wrote, in order. A cell no
`set` names holds whatever the canvas started with.

An operand is read through an accessor the pass builds for the cell it is
producing. `Probe` and `Anchor` are the stand-ins `infer_window` measures a
kernel against.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Sequence

#: The boundary rules the mosaic service and the legacy renderer both name.
MODES = ("constant", "fill", "wrap", "nearest", "reflect", "symmetric")

#: The cell types a rendered tile may declare.
DTYPES = ("int16", "int32")


class TileError(RuntimeError):
    """Something about this pass cannot be honoured."""


class ModeError(TileError):
    """A boundary setting this vocabulary does not contain."""


class OperandError(TileError):
    """A read that lands outside the operand it was addressed to."""


def map_index(length: int, index: int, mode: str) -> int | None:
    """Where an access at ``index`` along an axis of ``length`` cells reads from.

    ``None`` means the access takes the pass's fill value rather than a cell of
    the operand: under ``constant`` and ``fill`` for anything off the axis, and
    under ``reflect`` or ``symmetric`` when the mirrored position is itself off
    the axis. ``reflect`` mirrors about the outermost cell without repeating
    it; ``symmetric`` mirrors about the outer edge, so the outermost cell is
    repeated.
    """

    size, position = int(length), int(index)
    if size <= 0:
        raise TileError("an axis must have at least one cell")
    if mode == "constant" or mode == "fill":
        return position if 0 <= position < size else None
    if mode == "wrap":
        return position % size
    if mode == "nearest":
        return 0 if position < 0 else (size - 1 if position >= size else position)
    if mode == "reflect":
        mirrored = -position if position < 0 else (
            2 * size - 2 - position if position >= size else position
        )
        return mirrored if 0 <= mirrored < size else None
    if mode == "symmetric":
        mirrored = -position - 1 if position < 0 else (
            2 * size - 1 - position if position >= size else position
        )
        return mirrored if 0 <= mirrored < size else None
    raise ModeError(f"the boundary vocabulary has no {mode!r}")


def cast(dtype: str, value: Any) -> int:
    """One cell value as the declared cell type stores it."""

    if dtype not in DTYPES:
        raise TileError(f"unknown cell type: {dtype!r}")
    return int(value)


@dataclass(frozen=True, slots=True)
class Grid:
    """One rendered raster: a cell type and its rows, immutable once frozen."""

    dtype: str
    cells: tuple[tuple[int, ...], ...]

    @property
    def height(self) -> int:
        return len(self.cells)

    @property
    def width(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    def value(self, row: int, col: int) -> int:
        """One cell. A position outside this raster is a read that cannot stand."""

        if not (0 <= int(row) < self.height and 0 <= int(col) < self.width):
            raise OperandError(
                f"({int(row)}, {int(col)}) is outside a "
                f"{self.height}x{self.width} operand"
            )
        return self.cells[int(row)][int(col)]

    def rows(self) -> list[list[int]]:
        return [list(row) for row in self.cells]

    @classmethod
    def of(cls, rows: Sequence[Sequence[Any]], dtype: str = "int32") -> "Grid":
        return cls(dtype, tuple(tuple(cast(dtype, v) for v in row) for row in rows))


_WRITE_LOGS: list[list[tuple[int, int]]] = []


@contextmanager
def trace_writes() -> Iterator[list[tuple[int, int]]]:
    """Collect every cell any canvas is written at inside this block, in order."""

    log: list[tuple[int, int]] = []
    _WRITE_LOGS.append(log)
    try:
        yield log
    finally:
        _WRITE_LOGS.remove(log)


class Canvas:
    """The tile a pass writes into, and the record of what it wrote.

    The mosaic service hands a pass a canvas when it wants a frame buffer
    reused; otherwise a pass makes its own with :meth:`blank`.
    """

    __slots__ = ("dtype", "_cells")

    def __init__(self, dtype: str, cells: Sequence[Sequence[Any]]):
        if dtype not in DTYPES:
            raise TileError(f"unknown cell type: {dtype!r}")
        self.dtype = str(dtype)
        self._cells = [list(row) for row in cells]

    @classmethod
    def blank(cls, height: int, width: int, dtype: str, fill: Any = 0) -> "Canvas":
        """A canvas whose every cell starts at ``fill``."""

        return cls(dtype, [[fill] * int(width) for _ in range(int(height))])

    @property
    def height(self) -> int:
        return len(self._cells)

    @property
    def width(self) -> int:
        return len(self._cells[0]) if self._cells else 0

    def set(self, row: int, col: int, value: Any) -> None:
        """Put one produced cell on the canvas and note that the pass made it."""

        position = (int(row), int(col))
        if not (0 <= position[0] < self.height and 0 <= position[1] < self.width):
            raise TileError(f"a pass wrote at {position}, which is off the tile")
        self._cells[position[0]][position[1]] = value
        for log in _WRITE_LOGS:
            log.append(position)

    def value(self, row: int, col: int) -> Any:
        return self._cells[int(row)][int(col)]

    def freeze(self) -> Grid:
        """The finished tile, every cell stored as the declared cell type."""

        return Grid(
            self.dtype,
            tuple(tuple(cast(self.dtype, v) for v in row) for row in self._cells),
        )


@dataclass(frozen=True, slots=True)
class Window:
    """How far a kernel reaches from the cell it is producing, per side."""

    top: int
    bottom: int
    left: int
    right: int

    @classmethod
    def around(cls, offsets: Sequence[tuple[int, int]]) -> "Window":
        rows = [int(dr) for dr, _ in offsets] or [0]
        cols = [int(dc) for _, dc in offsets] or [0]
        return cls(max(0, -min(rows)), max(0, max(rows)), max(0, -min(cols)), max(0, max(cols)))

    @classmethod
    def spanning(cls, extents: Sequence[Sequence[int]]) -> "Window":
        """The window a job config spells out, as ``[[-2, 2], [-1, 1]]``."""

        (first, last), (start, end) = (tuple(part) for part in extents)
        return cls(max(0, -int(first)), max(0, int(last)), max(0, -int(start)), max(0, int(end)))


def _offset(value: Any) -> tuple[int, int]:
    pair = tuple(value) if isinstance(value, tuple) else (value,)
    if len(pair) != 2:
        raise TileError("a tile access is addressed by a row and a column")
    return int(pair[0]), int(pair[1])


class Probe:
    """Stands in for a relatively indexed operand while a window is inferred."""

    def __init__(self) -> None:
        self.offsets: list[tuple[int, int]] = []

    def __getitem__(self, offset: Any) -> int:
        self.offsets.append(_offset(offset))
        return 0


class Anchor:
    """Stands in for an absolutely indexed operand while a window is inferred.

    Its coordinates say nothing about how far the kernel reaches, so nothing it
    is asked for is collected.
    """

    def __getitem__(self, offset: Any) -> int:
        _offset(offset)
        return 0


def infer_window(kernel: Callable[..., Any], kinds: Sequence[str]) -> Window:
    """Run ``kernel`` once against stand-ins to learn how far it reaches."""

    views: list[Any] = []
    probes: list[Probe] = []
    for kind in kinds:
        if str(kind) == "absolute":
            views.append(Anchor())
        else:
            probe = Probe()
            probes.append(probe)
            views.append(probe)
    kernel(*views)
    return Window.around([offset for probe in probes for offset in probe.offsets])


@dataclass(frozen=True, slots=True)
class JobSpec:
    """One nightly job as its config file spells it out."""

    name: str
    kernel: str
    operands: tuple[str, ...]
    standard_indexing: tuple[str, ...]
    mode: Any
    cval: Any
    neighborhood: Any
    output_dtype: str | None


def load_job(document: Mapping[str, Any]) -> JobSpec:
    """Read one job config. Values are carried through exactly as written."""

    raw_mode = document.get("mode", "constant")
    mode = tuple(raw_mode) if isinstance(raw_mode, (list, tuple)) else raw_mode
    neighborhood = document.get("neighborhood")
    dtype = document.get("output_dtype")
    return JobSpec(
        name=str(document.get("job", "unnamed")),
        kernel=str(document["kernel"]),
        operands=tuple(str(item) for item in document.get("operands", ("a",))),
        standard_indexing=tuple(str(item) for item in document.get("standard_indexing", ())),
        mode=mode,
        cval=document.get("cval", 0),
        neighborhood=None if neighborhood is None else tuple(tuple(part) for part in neighborhood),
        output_dtype=None if dtype is None else str(dtype),
    )


def _broad_cross(a: Any) -> int:
    return (
        a[-2, 0] + a[-1, 0] + a[0, 0] + a[1, 0] + a[2, 0]
        + a[0, -2] + a[0, -1] + a[0, 1] + a[0, 2]
    ) // 9


def _cross_blur(a: Any) -> int:
    return (a[-1, 0] + a[0, -1] + a[0, 0] + a[0, 1] + a[1, 0]) // 5


def _row_smear(a: Any) -> int:
    return (a[0, -2] + a[0, -1] + a[0, 0] + a[0, 1] + a[0, 2]) // 5


def _column_smear(a: Any) -> int:
    return (a[-2, 0] + a[-1, 0] + a[0, 0] + a[1, 0] + a[2, 0]) // 5


def _box_mean(a: Any) -> int:
    return sum(a[dr, dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1)) // 9


def _long_reach(a: Any) -> int:
    return (a[-1, 0] + a[0, -3] + a[0, 0] + a[0, 3] + a[1, 0]) // 5


def _weighted_cross(a: Any, w: Any) -> int:
    return (
        a[-1, 0] * w[0, 0] + a[0, -1] * w[1, 0] + a[0, 0] * w[2, 0]
        + a[0, 1] * w[3, 0] + a[1, 0] * w[4, 0]
    ) // 8


#: The kernels the nightly job configs name. Every offset in them is constant.
KERNELS: Mapping[str, Callable[..., Any]] = {
    "broad_cross": _broad_cross,
    "cross_blur": _cross_blur,
    "row_smear": _row_smear,
    "column_smear": _column_smear,
    "box_mean": _box_mean,
    "long_reach": _long_reach,
    "weighted_cross": _weighted_cross,
}


__all__ = (
    "Anchor", "Canvas", "DTYPES", "Grid", "JobSpec", "KERNELS", "MODES",
    "ModeError", "OperandError", "Probe", "TileError", "Window", "cast",
    "infer_window", "load_job", "map_index", "trace_writes",
)
