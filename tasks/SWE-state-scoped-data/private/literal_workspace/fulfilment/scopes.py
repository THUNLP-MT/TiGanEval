"""Where a running order's data lives.

Every state gets its own data bag: the defaults are declared on the state, the
bag is filled when the order enters the state, and the bag is dropped when the
order leaves it. The counters live on the bag.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import Chart


class ScopeManager:
    """One data bag per state of the running order."""

    def __init__(self, chart: Chart):
        self.chart = chart
        self.bags: dict[str, dict[str, Any]] = {}

    def begin_event(self, event: str) -> None:
        """A new event is starting."""

    def enter(self, path: Sequence[str], resume: str | None = None) -> None:
        for state in path:
            self.bags[state] = dict(self.chart.declared(state))

    def leave(self, path: Sequence[str]) -> None:
        for state in path:
            self.bags.pop(state, None)

    def read(self, state: str, field: str) -> Any:
        return self.bags.get(state, {}).get(field)

    def write(self, state: str, field: str, value: Any) -> None:
        self.bags.setdefault(state, {})[field] = value

    def values(self) -> Mapping[str, Mapping[str, Any]]:
        return {state: dict(bag) for state, bag in self.bags.items() if bag}

    def changes(self) -> Sequence[Any]:
        return ()


__all__ = ("ScopeManager",)
