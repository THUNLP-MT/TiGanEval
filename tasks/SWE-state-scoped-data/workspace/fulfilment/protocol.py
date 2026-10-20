"""The chart a workflow is declared in, and what the audit reader consumes.

Frozen: the floor tooling and the audit reader are built against these names.
:mod:`fulfilment.engine` drives a chart; the scope layer in
``fulfilment.scopes`` is the part of the runtime this project owns.

A chart is plain data, so several runs of one chart can share a process.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


FIELD_TYPES: Mapping[str, type] = {"str": str, "int": int, "list": list}
"""The declared types a chart may give a field."""

RESUME_KINDS: tuple[str, ...] = ("full", "direct")
"""How far below its own state a resume point reaches."""

SCOPE_ERROR_CODES: tuple[str, ...] = (
    "inactive_state",
    "undeclared_field",
    "wrong_type",
)


class ChartError(ValueError):
    """The chart itself is malformed."""


class ScopeError(RuntimeError):
    """A handler operation the scope layer would not serve.

    ``code`` is one of :data:`SCOPE_ERROR_CODES`:

    ``inactive_state``
        the named state is not part of the order's current configuration;
    ``undeclared_field``
        no state on the named state's chain declares that field;
    ``wrong_type``
        the value does not match the type the declaring state gave the field.
    """

    def __init__(self, code: str, detail: str = ""):
        if code not in SCOPE_ERROR_CODES:
            raise ValueError(f"unknown scope error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = str(code)
        self.detail = str(detail)


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    """One value change in the audit trail of a single event.

    ``state`` is the state that declares ``field`` -- the state whose data
    actually moved, not the state whose handler asked for the write.
    """

    state: str
    field: str
    before: Any
    after: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "field": self.field,
            "before": deepcopy(self.before),
            "after": deepcopy(self.after),
        }


class Chart:
    """One workflow definition: states, declared data, transitions, handlers."""

    def __init__(self, spec: Mapping[str, Any]):
        raw_states = dict(spec.get("states") or {})
        if not raw_states:
            raise ChartError("a chart needs at least one state")
        self.id = str(spec.get("id", "chart"))
        self._parent: dict[str, str | None] = {}
        self._initial_child: dict[str, str] = {}
        self._declared: dict[str, dict[str, Any]] = {}
        self._types: dict[str, dict[str, type]] = {}
        for name, body in raw_states.items():
            parent = body.get("parent")
            self._parent[str(name)] = None if parent is None else str(parent)
            if body.get("initial"):
                self._initial_child[str(name)] = str(body["initial"])
            declared: dict[str, Any] = {}
            types: dict[str, type] = {}
            for field, declaration in dict(body.get("data") or {}).items():
                kind, default = declaration[0], declaration[1]
                if str(kind) not in FIELD_TYPES:
                    raise ChartError(f"{name}.{field} declares unknown type {kind!r}")
                declared[str(field)] = default
                types[str(field)] = FIELD_TYPES[str(kind)]
            self._declared[str(name)] = declared
            self._types[str(name)] = types
        for name, parent in self._parent.items():
            if parent is not None and parent not in self._parent:
                raise ChartError(f"{name} names an unknown parent {parent!r}")
        self._initial = str(spec.get("initial") or next(iter(raw_states)))
        self._transitions = tuple(dict(item) for item in spec.get("transitions") or ())
        self._callbacks = {
            str(key): tuple(tuple(op) for op in ops)
            for key, ops in dict(spec.get("callbacks") or {}).items()
        }
        self._resume = {
            str(name): {"state": str(body["state"]), "kind": str(body["kind"])}
            for name, body in dict(spec.get("resume_points") or {}).items()
        }
        for name, body in self._resume.items():
            if body["kind"] not in RESUME_KINDS:
                raise ChartError(f"resume point {name} declares unknown kind {body['kind']!r}")

    # -- structure ---------------------------------------------------------

    def states(self) -> tuple[str, ...]:
        return tuple(self._parent)

    def parent_of(self, state: str) -> str | None:
        return self._parent[str(state)]

    def children(self, state: str | None) -> tuple[str, ...]:
        return tuple(name for name, parent in self._parent.items() if parent == state)

    def scope_chain(self, state: str) -> tuple[str, ...]:
        """``state`` and its ancestors, innermost first.

        A handler running in ``state`` resolves a field name along this chain.
        """

        chain: list[str] = []
        current: str | None = str(state)
        while current is not None:
            chain.append(current)
            current = self._parent[current]
        return tuple(chain)

    def descendants(self, state: str) -> tuple[str, ...]:
        return tuple(
            name for name in self._parent if str(state) in self.scope_chain(name)[1:]
        )

    def depth(self, state: str) -> int:
        return len(self.scope_chain(state))

    # -- declared data -----------------------------------------------------

    def declared(self, state: str) -> Mapping[str, Any]:
        """The fields ``state`` declares, mapped to the defaults it declares.

        This is the declaration itself, shared by every order the chart runs.
        """

        return self._declared[str(state)]

    def field_type(self, state: str, field: str) -> type | None:
        return self._types[str(state)].get(str(field))

    def declaring_state(self, state: str, field: str) -> str | None:
        """The innermost state on ``state``'s chain that declares ``field``."""

        for name in self.scope_chain(state):
            if str(field) in self._declared[name]:
                return name
        return None

    # -- transitions -------------------------------------------------------

    def transitions(self) -> tuple[Mapping[str, Any], ...]:
        return self._transitions

    def select(self, event: str, config: Sequence[str]) -> Mapping[str, Any] | None:
        """The transition ``event`` fires from ``config``, innermost source wins."""

        active = list(config)
        enabled = [
            item
            for item in self._transitions
            if str(item.get("event")) == str(event) and str(item.get("source")) in active
        ]
        if not enabled:
            return None
        return max(enabled, key=lambda item: self.depth(str(item["source"])))

    @staticmethod
    def is_internal(transition: Mapping[str, Any]) -> bool:
        """An internal transition runs its step and leaves the configuration alone."""

        return bool(transition.get("internal"))

    def domain(self, source: str, target: str) -> str | None:
        """The innermost state a transition from ``source`` to ``target`` stays inside."""

        if str(source) == str(target):
            return self.parent_of(source)
        upward = set(self.scope_chain(target))
        for name in self.scope_chain(source):
            if name in upward:
                return name
        return None

    def exit_path(
        self, config: Sequence[str], source: str, target: str
    ) -> tuple[str, ...]:
        """The active states this transition leaves, innermost first."""

        boundary = self.domain(source, target)
        inside = [
            name
            for name in config
            if boundary is None or boundary in self.scope_chain(name)[1:]
        ]
        return tuple(reversed(inside))

    def entry_path(self, source: str, target: str, *, descend: bool = True) -> tuple[str, ...]:
        """The states this transition enters, outermost first."""

        boundary = self.domain(source, target)
        path: list[str] = []
        for name in self.scope_chain(target):
            if name == boundary:
                break
            path.append(name)
        path.reverse()
        return tuple(path) + (self.descend(target) if descend else ())

    def descend(self, state: str) -> tuple[str, ...]:
        """The default child chain below ``state``, outermost first."""

        path: list[str] = []
        current = self._initial_child.get(str(state))
        while current is not None:
            path.append(current)
            current = self._initial_child.get(current)
        return tuple(path)

    def initial_path(self) -> tuple[str, ...]:
        return (self._initial,) + self.descend(self._initial)

    # -- resume points -----------------------------------------------------

    def resume_points(self) -> tuple[str, ...]:
        """The routes work that was put aside comes back in through."""

        return tuple(self._resume)

    def resume_state(self, point: str) -> str:
        """The state ``point`` is declared at.

        :class:`~fulfilment.engine.Engine` remembers the states below this one
        at the moment it is left, and takes the work back in through it.
        """

        return self._resume[str(point)]["state"]

    def resume_kind(self, point: str) -> str:
        """How far below its own state ``point`` reaches: one of :data:`RESUME_KINDS`."""

        return self._resume[str(point)]["kind"]

    # -- handlers ----------------------------------------------------------

    def callbacks(self, key: str) -> tuple[tuple[Any, ...], ...]:
        """The steps the floor's handlers run at ``enter:<state>``, ``exit:<state>``
        or ``on:<event>``."""

        return self._callbacks.get(str(key), ())

__all__ = (
    "Chart",
    "ChartError",
    "ChangeRecord",
    "FIELD_TYPES",
    "RESUME_KINDS",
    "SCOPE_ERROR_CODES",
    "ScopeError",
)
