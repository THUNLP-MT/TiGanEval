"""The rich pane the incident console draws worker output into.

The pane keeps the entries themselves, not the strips it drew them into, and
redraws through the console's own `render_entry` whenever the width or the
reading minimum changes. Every event ends in one place: the entries are drawn,
the top of the viewport is put where the reader left it, and the Live/Paused
state falls out of where that top ended up.
"""

from __future__ import annotations

from .protocol import (
    Entry,
    Extent,
    FollowChanged,
    at_end,
    clamp_scroll,
    extent_of_lines,
    max_scroll_y,
    render_entry,
)


#: The Follow button: go to the newest line, whatever the reader was holding.
_END = object()


class RichPane:
    """One pane of the incident console."""

    def __init__(self, *, height: int, min_width: int = 0,
                 max_entries: int = 0, name: str = "rich"):
        self.name = str(name)
        self.height = max(1, int(height))
        self.min_width = int(min_width)
        self.max_entries = int(max_entries)
        self.width = 0  # the layout has not run yet
        self._entries: list[Entry] = []
        self._pending: list[Entry] = []
        self._strips: list[tuple[str, tuple[str, ...]]] = []
        self._anchor: tuple[str, int] | None = None
        self._scroll_y = 0
        self._following = True
        self._badge = True  # what the audit was last told
        self._posted: list[FollowChanged] = []

    # -- what the scrollbars and the toolbar read --------------------------

    @property
    def scroll_y(self) -> int:
        return self._scroll_y

    @property
    def max_scroll_y(self) -> int:
        return max_scroll_y(len(self._flat()), self.height)

    @property
    def is_following_end(self) -> bool:
        return self._following

    def strips(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Each entry still on the pane with the lines it is drawn as."""
        return tuple(self._strips)

    def extent(self) -> Extent:
        return extent_of_lines(self._flat())

    def messages(self) -> tuple[FollowChanged, ...]:
        return tuple(self._posted)

    def _flat(self) -> list[str]:
        lines: list[str] = []
        for _, strip in self._strips:
            lines.extend(strip)
        return lines

    # -- the workers -------------------------------------------------------

    def write(self, entry_id: str, text: str, full_width: bool = False) -> None:
        entry = Entry(str(entry_id), str(text), bool(full_width))
        if self.width <= 0:
            self._pending.append(entry)  # nothing can be drawn until the layout runs
            return
        self._entries.append(entry)
        self._trim()
        self._settle()

    def _trim(self) -> None:
        while self.max_entries and len(self._entries) > self.max_entries:
            self._entries.pop(0)

    # -- the reader --------------------------------------------------------

    def scroll_to(self, line: int) -> None:
        self._settle(int(line))

    def scroll_by(self, lines: int) -> None:
        self._settle(self._scroll_y + int(lines))

    def follow_end(self) -> None:
        self._settle(_END)

    # -- the layout --------------------------------------------------------

    def resize(self, width: int) -> None:
        self.width = int(width)
        self._flush()
        self._settle()

    def set_min_width(self, min_width: int) -> None:
        self.min_width = int(min_width)
        self._settle()

    def clear(self) -> None:
        self._entries.clear()
        self._pending.clear()
        self._anchor = None
        self._settle(0)

    def _flush(self) -> None:
        if self.width > 0 and self._pending:
            self._entries.extend(self._pending)
            self._pending.clear()
            self._trim()

    # -- the one place the pane settles ------------------------------------

    def _settle(self, target: object = None) -> None:
        drawn_before = dict(self._strips)
        self._draw()
        top = max_scroll_y(len(self._flat()), self.height)
        if target is _END or (target is None and self._following):
            position = top
        elif target is None:
            position = self._held_offset(drawn_before)
        else:
            position = int(target)  # type: ignore[arg-type]
        self._scroll_y = clamp_scroll(position, top)
        self._following = at_end(self._scroll_y, top)
        self._anchor = self._anchor_at(self._scroll_y)
        if self._following != self._badge:
            self._badge = self._following
            self._posted.append(
                FollowChanged(self.name, self._following, self._scroll_y, top)
            )

    def _draw(self) -> None:
        self._strips = [
            (
                entry.entry_id,
                render_entry(entry.text, self.width, self.min_width, entry.full_width),
            )
            for entry in self._entries
        ]

    def _held_offset(self, drawn_before: dict[str, tuple[str, ...]]) -> int:
        """Where the line the reader was holding sits after the redraw.

        While the held entry comes out of `render_entry` the same way it went
        in, the reader stays on the same row of it. The console's house policy
        uses the complete rendered strip as its boundary: once any row of that
        strip changes, the reader returns to the entry's first row.
        """

        if self._anchor is None:
            return self._scroll_y
        entry_id, line = self._anchor
        index = 0
        for held, strip in self._strips:
            if held == entry_id:
                if drawn_before.get(entry_id) != strip:
                    return index
                return index + int(line)
            index += len(strip)
        return 0  # that entry has been dropped; fall back to the oldest one left

    def _anchor_at(self, scroll_y: int) -> tuple[str, int] | None:
        index = 0
        for entry_id, strip in self._strips:
            if index + len(strip) > scroll_y:
                return (entry_id, scroll_y - index)
            index += len(strip)
        return None
