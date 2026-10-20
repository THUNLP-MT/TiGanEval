"""The incident console's rendering contract.

This module ships with the console release and the incident exporter reads the
same file, so an entry drawn on the pane and the same entry written into an
exported incident file are the same text. It owns how an entry becomes display
lines, how the scroll bounds are derived from what is on the pane, what "the
reader is on the newest line" means, the record the toolbar's badge consumes,
and `PlainPane`, the plain-text pane the console has shipped for years.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


#: What a full-width entry is padded out to the edge with.
FILL = "="


@dataclass(frozen=True, slots=True)
class Entry:
    """One thing a worker wrote, before it is drawn at any particular width."""

    entry_id: str
    text: str
    full_width: bool = False


@dataclass(frozen=True, slots=True)
class Extent:
    """How wide and how tall the drawn log is right now.

    ``widest`` drives the horizontal bar and ``line_count`` the vertical one.
    """

    widest: int
    line_count: int


@dataclass(frozen=True, slots=True)
class FollowChanged:
    """What the pane posts when it starts or stops sitting on the newest line.

    The toolbar reads ``is_following_end`` for its Live/Paused badge and the
    session audit keeps every one of these with the position it carried.
    """

    pane: str
    is_following_end: bool
    scroll_y: int
    max_scroll_y: int


def effective_width(width: int, min_width: int = 0) -> int:
    """The number of columns an entry is actually drawn across.

    The pane never draws narrower than ``min_width``; below that the console
    gives the reader a horizontal bar instead of breaking the text further.
    """

    return max(1, int(width), int(min_width))


def wrap_text(text: str, cell: int) -> tuple[str, ...]:
    """Break one entry's text across ``cell`` columns, on spaces where it can."""

    cell = max(1, int(cell))
    lines: list[str] = []
    current = ""
    for word in str(text).split():
        while len(word) > cell:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:cell])
            word = word[cell:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= cell:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current or not lines:
        lines.append(current)
    return tuple(lines)


def _to_the_edge(line: str, cell: int) -> str:
    """One full-width line, padded with FILL so it reaches both edges."""

    if not line:
        return FILL * cell
    room = cell - len(line) - 2
    if room < 2:
        return line[:cell]
    left = room // 2
    return f"{FILL * left} {line} {FILL * (room - left)}"


def render_entry(
    text: str, width: int, min_width: int = 0, full_width: bool = False
) -> tuple[str, ...]:
    """The display lines one entry occupies at this width.

    A full-width entry is what the console writes for the rule and banner lines
    that separate one incident from the next: every line of it reaches both
    edges of the pane, so its text is broken narrower to leave room for the
    padding. An ordinary entry is wrapped and left as it is.
    """

    cell = effective_width(width, min_width)
    if not full_width:
        return wrap_text(text, cell)
    lines = wrap_text(text, cell - 4 if cell > 8 else cell)
    return tuple(_to_the_edge(line, cell) for line in lines)


def render_all(
    entries: Sequence[Entry], width: int, min_width: int = 0
) -> tuple[str, ...]:
    """Every display line of ``entries``, top to bottom."""

    lines: list[str] = []
    for entry in entries:
        lines.extend(render_entry(entry.text, width, min_width, entry.full_width))
    return tuple(lines)


def extent_of_lines(lines: Iterable[str]) -> Extent:
    """The extent of display lines that have already been drawn."""

    drawn = [str(line) for line in lines]
    return Extent(
        widest=max((len(line) for line in drawn), default=0),
        line_count=len(drawn),
    )


def content_extent(
    entries: Sequence[Entry], width: int, min_width: int = 0
) -> Extent:
    """The extent of ``entries`` drawn at this width.

    The exporter reports the same two numbers for the entries it wrote, so a
    pane and an exported incident file describe the same log.
    """

    return extent_of_lines(render_all(entries, width, min_width))


def max_scroll_y(line_count: int, height: int) -> int:
    """The largest top-of-viewport line index that still shows the last line."""

    return max(0, int(line_count) - max(1, int(height)))


def at_end(scroll_y: int, max_scroll_y: int) -> bool:
    """Whether the viewport is sitting on the newest line."""

    return int(scroll_y) >= int(max_scroll_y)


def clamp_scroll(scroll_y: int, max_scroll: int) -> int:
    """A top-of-viewport line index the pane can actually show."""

    return max(0, min(int(scroll_y), int(max_scroll)))


class PlainPane:
    """The plain-text pane in the console's left column.

    It has been in the console since before the rich pane existed and the shift
    leads still read it during a page. It keeps one line per entry, never drops
    anything, never redraws when the divider moves, and posts nothing to the
    toolbar; what it does have is a reader who stays where they put themselves
    and a Live/Paused state the console reads straight off the pane.
    """

    def __init__(self, *, height: int, name: str = "plain"):
        self.name = str(name)
        self.height = max(1, int(height))
        self._lines: list[str] = []
        self._scroll_y = 0
        self._following = True

    @property
    def scroll_y(self) -> int:
        return self._scroll_y

    @property
    def max_scroll_y(self) -> int:
        return max_scroll_y(len(self._lines), self.height)

    @property
    def is_following_end(self) -> bool:
        return self._following

    def lines(self) -> tuple[str, ...]:
        return tuple(self._lines)

    def write(self, entry_id: str, text: str) -> None:
        self._lines.append(str(text))
        self._settle()

    def scroll_to(self, line: int) -> None:
        self._settle(int(line))

    def scroll_by(self, lines: int) -> None:
        self._settle(self._scroll_y + int(lines))

    def follow_end(self) -> None:
        self._settle(to_end=True)

    def clear(self) -> None:
        self._lines.clear()
        self._settle(0)

    def _settle(self, target: int | None = None, *, to_end: bool = False) -> None:
        top = self.max_scroll_y
        if to_end or (target is None and self._following):
            position = top
        elif target is None:
            position = self._scroll_y
        else:
            position = int(target)
        self._scroll_y = clamp_scroll(position, top)
        self._following = at_end(self._scroll_y, top)
