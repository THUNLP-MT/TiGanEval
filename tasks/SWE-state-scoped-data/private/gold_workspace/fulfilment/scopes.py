"""Where a running order's data lives.

Each state owns the fields it declares. A state's bag is filled when the order
enters that state and dropped when the order leaves it; a handler resolves a
name along the chain of the state it runs in, so the innermost state that
declares the name owns the value. Leaving a state that carries a resume point
puts that state and the data below it aside, and coming back in through that
point restores as much of it as the point reaches; a state above the point's
own state is an ordinary entry and starts from what it declares.

The audit reader reconciles one event's lines against the order itself: what a
state was holding when the event began, plus that event's lines for it, is what
it is holding when the event ends. A state the order walked into opens at
nothing and a state it left closes at nothing, so filling a bag and dropping
one are both movements the account carries.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .protocol import Chart, ChangeRecord, ScopeError


class ScopeManager:
    """The data of one running order."""

    def __init__(self, chart: Chart):
        self.chart = chart
        self._bags: dict[str, dict[str, Any]] = {}
        self._put_aside: dict[str, dict[str, dict[str, Any]]] = {}
        self._changes: list[ChangeRecord] = []

    # -- the engine's hooks -------------------------------------------------

    def begin_event(self, event: str) -> None:
        self._changes = []

    def enter(self, path: Sequence[str], resume: str | None = None) -> None:
        coming_back = self._restored(resume)
        for state in path:
            bag = deepcopy(dict(self.chart.declared(state)))
            bag.update(deepcopy(coming_back.get(state, {})))
            self._bags[state] = bag
            for field, value in bag.items():
                self._changes.append(ChangeRecord(state, field, None, deepcopy(value)))

    def leave(self, path: Sequence[str]) -> None:
        for point in self.chart.resume_points():
            anchor = self.chart.resume_state(point)
            if anchor in path:
                self._put_aside[point] = {
                    state: deepcopy(bag)
                    for state, bag in self._bags.items()
                    if state == anchor or anchor in self.chart.scope_chain(state)[1:]
                }
        for state in path:
            bag = self._bags.pop(str(state), None)
            for field, value in dict(bag or {}).items():
                self._changes.append(ChangeRecord(str(state), field, deepcopy(value), None))

    def read(self, state: str, field: str) -> Any:
        return deepcopy(self._bags[self._owner(state, field)][str(field)])

    def write(self, state: str, field: str, value: Any) -> None:
        owner = self._owner(state, field)
        name = str(field)
        declared = self.chart.field_type(owner, name)
        if declared is not None and not _matches(value, declared):
            raise ScopeError(
                "wrong_type", f"{owner}.{name} holds {declared.__name__}, not {type(value).__name__}"
            )
        before = self._bags[owner][name]
        if before == value and type(before) is type(value):
            return
        self._bags[owner][name] = deepcopy(value)
        self._changes.append(ChangeRecord(owner, name, deepcopy(before), deepcopy(value)))

    def values(self) -> Mapping[str, Mapping[str, Any]]:
        return {state: deepcopy(bag) for state, bag in self._bags.items() if bag}

    def changes(self) -> Sequence[ChangeRecord]:
        return tuple(self._changes)

    # -- internals ----------------------------------------------------------

    def _restored(self, resume: str | None) -> dict[str, dict[str, Any]]:
        """The data a resume point brings back, by state."""

        if resume is None:
            return {}
        anchor = self.chart.resume_state(resume)
        kind = self.chart.resume_kind(resume)
        reaches = {anchor, *self.chart.descendants(anchor)}
        if kind == "direct":
            reaches = {anchor, *self.chart.children(anchor)}
        return {
            state: deepcopy(bag)
            for state, bag in self._put_aside.get(str(resume), {}).items()
            if state in reaches
        }

    def _owner(self, state: str, field: str) -> str:
        """The state whose bag holds ``field`` for a handler running in ``state``."""

        name = str(state)
        if name not in self._bags:
            raise ScopeError("inactive_state", f"{name} is not part of this order right now")
        owner = self.chart.declaring_state(name, str(field))
        if owner is None:
            raise ScopeError("undeclared_field", f"nothing on {name}'s chain declares {field}")
        if owner not in self._bags:
            raise ScopeError("inactive_state", f"{owner} is not part of this order right now")
        return owner


def _matches(value: Any, declared: type) -> bool:
    if isinstance(value, bool) and declared is not bool:
        return False
    return isinstance(value, declared)


__all__ = ("ScopeManager",)
