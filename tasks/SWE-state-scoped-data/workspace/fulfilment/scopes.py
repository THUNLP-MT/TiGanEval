"""Where a running order's data lives.

The generic runner keeps one bag of notes per order. It is filled with every
declared default when the order starts and the handlers read and write names
out of it from wherever they run.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import Chart


class ScopeManager:
    """The data of one running order.

    ``Engine`` reaches this class through ``begin_event``, ``enter``,
    ``leave``, ``read``, ``write``, ``values`` and ``changes``.
    """

    def __init__(self, chart: Chart):
        self.chart = chart
        self.notes: dict[str, Any] = {}
        self.active: list[str] = []
        for state in chart.states():
            self.notes.update(chart.declared(state))

    def begin_event(self, event: str) -> None:
        """A new event is starting."""

    def enter(self, path: Sequence[str], resume: str | None = None) -> None:
        for state in path:
            if state not in self.active:
                self.active.append(state)

    def leave(self, path: Sequence[str]) -> None:
        """The order has left these states."""

    def read(self, state: str, field: str) -> Any:
        return self.notes.get(field)

    def write(self, state: str, field: str, value: Any) -> None:
        self.notes[field] = value

    def values(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            state: {field: self.notes.get(field) for field in self.chart.declared(state)}
            for state in self.active
            if self.chart.declared(state)
        }

    def changes(self) -> Sequence[Any]:
        return ()


__all__ = ("ScopeManager",)
