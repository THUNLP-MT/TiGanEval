"""The rich pane the incident console draws worker output into.

Each write is drawn once, there and then, and the drawn strip is kept; behind
it the pane holds the flat list of display lines, an integer index of the line
at the top of the viewport, and the widest line it has drawn. Once
``max_entries`` is reached the oldest strip goes and its lines come off the
head of the list.

The pane now keeps a follow flag. Scrolling up off the newest line clears it,
the Follow button sets it, and only a write that arrives while it is set jumps
to the end, so a reader who has scrolled up is left where they are. The
toolbar's badge reads the flag, and the pane posts a FollowChanged whenever it
changes so the session audit has it.
"""

from __future__ import annotations

from .protocol import Extent, FollowChanged, max_scroll_y, render_entry


class RichPane:
    """One pane of the incident console."""

    def __init__(self, *, height: int, min_width: int = 0,
                 max_entries: int = 0, name: str = "rich"):
        self.name = str(name)
        self.height = max(1, int(height))
        self.min_width = int(min_width)
        self.max_entries = int(max_entries)
        self.width = 0  # the layout has not run yet
        self.following = True
        self._strips: list[tuple[str, tuple[str, ...]]] = []
        self._lines: list[str] = []
        self._content_width = 0
        self._scroll_y = 0
        self._posted: list[FollowChanged] = []

    # -- what the scrollbars and the toolbar read --------------------------

    @property
    def scroll_y(self) -> int:
        return self._scroll_y

    @property
    def max_scroll_y(self) -> int:
        return max_scroll_y(len(self._lines), self.height)

    @property
    def is_following_end(self) -> bool:
        return self.following

    def strips(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each entry still on the pane with the lines it is drawn as."""
        return tuple(self._strips)

    def extent(self) -> Extent:
        return Extent(widest=self._content_width, line_count=len(self._lines))

    def messages(self) -> tuple[FollowChanged, ...]:
        return tuple(self._posted)

    def _set_following(self, value: bool) -> None:
        if bool(value) == self.following:
            return
        self.following = bool(value)
        self._posted.append(
            FollowChanged(self.name, self.following, self._scroll_y, self.max_scroll_y)
        )

    # -- the workers -------------------------------------------------------

    def write(self, entry_id: str, text: str, full_width: bool = False) -> None:
        lines = render_entry(text, self.width, self.min_width, full_width)
        self._strips.append((str(entry_id), lines))
        self._lines.extend(lines)
        self._content_width = max(
            self._content_width, max((len(line) for line in lines), default=0)
        )
        while self.max_entries and len(self._strips) > self.max_entries:
            _, dropped = self._strips.pop(0)
            del self._lines[: len(dropped)]
        if self.following:
            self._scroll_y = self.max_scroll_y

    # -- the reader --------------------------------------------------------

    def scroll_to(self, line: int) -> None:
        self._scroll_y = max(0, min(int(line), self.max_scroll_y))
        if self._scroll_y < self.max_scroll_y:
            self._set_following(False)

    def scroll_by(self, lines: int) -> None:
        self.scroll_to(self._scroll_y + int(lines))

    def follow_end(self) -> None:
        self._set_following(True)
        self._scroll_y = self.max_scroll_y

    # -- the layout --------------------------------------------------------

    def resize(self, width: int) -> None:
        self.width = int(width)

    def set_min_width(self, min_width: int) -> None:
        self.min_width = int(min_width)

    def clear(self) -> None:
        self._strips.clear()
        self._lines.clear()
        self._content_width = 0
        self._scroll_y = 0
