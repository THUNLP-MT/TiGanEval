"""The engine that drives one run of a chart through its events.

Frozen: the floor tooling raises the events and reads what comes back. The
engine reaches the scope layer only through the hooks listed on :class:`Engine`.
Everything here is deterministic: no clock, no threads, no input.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .protocol import Chart, ChartError, ScopeError


class Context:
    """What one handler step may do with the running order's data."""

    __slots__ = ("_scopes", "state", "payload")

    def __init__(self, scopes: Any, state: str, payload: Mapping[str, Any]):
        self._scopes = scopes
        self.state = str(state)
        self.payload = dict(payload)

    def read(self, field: str) -> Any:
        return self._scopes.read(self.state, str(field))

    def write(self, field: str, value: Any) -> None:
        self._scopes.write(self.state, str(field), value)

    def read_in(self, state: str, field: str) -> Any:
        return self._scopes.read(str(state), str(field))

    def write_in(self, state: str, field: str, value: Any) -> None:
        self._scopes.write(str(state), str(field), value)


def _value(raw: Any, payload: Mapping[str, Any]) -> Any:
    if isinstance(raw, str) and raw.startswith("@"):
        return deepcopy(payload.get(raw[1:]))
    return deepcopy(raw)


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _apply(op: Sequence[Any], context: Context) -> None:
    name = str(op[0])
    if name == "set":
        context.write(op[1], _value(op[2], context.payload))
    elif name == "bump":
        context.write(op[1], _as_int(context.read(op[1])) + int(op[2]))
    elif name == "append":
        # The handler works the list it was given and hands it back.
        bucket = context.read(op[1])
        bucket = bucket if isinstance(bucket, list) else []
        bucket.append(_value(op[2], context.payload))
        context.write(op[1], bucket)
    elif name == "touch":
        context.write(op[1], context.read(op[1]))
    elif name == "carry":
        bucket = context.read(op[1])
        bucket = bucket if isinstance(bucket, list) else []
        bucket.extend(_as_list(context.read(op[2])))
        context.write(op[1], bucket)
    elif name == "set_in":
        context.write_in(op[1], op[2], _value(op[3], context.payload))
    elif name == "bump_in":
        context.write_in(op[1], op[2], _as_int(context.read_in(op[1], op[2])) + int(op[3]))
    elif name == "append_in":
        context.write_in(
            op[1], op[2], _as_list(context.read_in(op[1], op[2])) + [_value(op[3], context.payload)]
        )
    else:
        raise ChartError(f"unknown handler step: {name}")


def step_site(op: Sequence[Any], state: str) -> tuple[str, str]:
    """The state and field one handler step names."""

    name = str(op[0])
    if name.endswith("_in"):
        return str(op[1]), str(op[2])
    return str(state), str(op[1])


class Engine:
    """Drives one order through the chart, calling the scope layer's hooks.

    The scope layer is asked for exactly seven things:
    ``begin_event(event)`` at the start of every event, ``leave(path)`` once
    the exit handlers of ``path`` have run, ``enter(path, resume)`` before the
    entry handlers of ``path`` run, ``read(state, field)`` and
    ``write(state, field, value)`` for each handler step, ``values()`` for the
    order's data as it stands, and ``changes()`` for the audit trail.

    One event runs in this order: the transition's own step in the innermost
    active state, then the exit handlers innermost first, then ``leave``, then
    ``enter``, then the entry handlers outermost first.
    """

    def __init__(self, chart: Chart, scopes: Any, *, name: str = "order"):
        self.chart = chart
        self.scopes = scopes
        self.name = str(name)
        self.config: tuple[str, ...] = ()
        self.remembered: dict[str, tuple[str, ...]] = {}

    def start(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        report = self._report("start")
        self.scopes.begin_event("start")
        path = self.chart.initial_path()
        self.config = path
        self._enter(path, None, dict(payload or {}), report)
        return self._finish(report)

    def send(self, event: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = dict(payload or {})
        report = self._report(event)
        self.scopes.begin_event(str(event))
        transition = self.chart.select(event, self.config)
        if transition is None:
            report["ignored"] = True
            return self._finish(report)
        source, target = str(transition["source"]), str(transition["target"])
        report["source"], report["target"] = source, target
        scope = self.config[-1] if self.config else source
        self._run(self.chart.callbacks(f"on:{event}"), scope, data, report)
        if self.chart.is_internal(transition):
            report["internal"] = True
            return self._finish(report)
        exiting = self.chart.exit_path(self.config, source, target)
        for state in exiting:
            self._run(self.chart.callbacks(f"exit:{state}"), state, data, report)
        for point in self.chart.resume_points():
            anchor = self.chart.resume_state(point)
            if anchor in exiting:
                self.remembered[point] = tuple(
                    name for name in self.config if anchor in self.chart.scope_chain(name)[1:]
                )
        self.scopes.leave(exiting)
        resume = transition.get("resume")
        entering = self.chart.entry_path(source, target, descend=resume is None)
        if resume is not None:
            entering = entering + self.remembered.get(str(resume), self.chart.descend(target))
        self.config = tuple(name for name in self.config if name not in exiting) + entering
        report["left"] = list(exiting)
        self._enter(entering, None if resume is None else str(resume), data, report)
        return self._finish(report)

    # -- internals ---------------------------------------------------------

    def _report(self, event: str) -> dict[str, Any]:
        return {
            "order": self.name,
            "event": str(event),
            "config_before": list(self.config),
            "entered": [],
            "refusals": [],
            "step_errors": [],
        }

    def _enter(
        self,
        path: Sequence[str],
        resume: str | None,
        payload: Mapping[str, Any],
        report: dict[str, Any],
    ) -> None:
        self.scopes.enter(tuple(path), resume)
        filled = self._values()
        report["resume"] = resume
        report["entered"] = [
            {"state": state, "values": deepcopy(filled.get(state, {}))} for state in path
        ]
        for state in path:
            self._run(self.chart.callbacks(f"enter:{state}"), state, payload, report)

    def _run(
        self,
        ops: Sequence[Sequence[Any]],
        state: str,
        payload: Mapping[str, Any],
        report: dict[str, Any],
    ) -> None:
        for op in ops:
            named_state, named_field = step_site(op, state)
            try:
                _apply(op, Context(self.scopes, state, payload))
            except ScopeError as exc:
                report["refusals"].append(
                    {"state": named_state, "field": named_field, "code": exc.code}
                )
            except Exception as exc:  # a handler step the scope layer could not serve
                report["step_errors"].append(
                    {
                        "state": named_state,
                        "field": named_field,
                        "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                    }
                )

    def _values(self) -> dict[str, dict[str, Any]]:
        raw = self.scopes.values()
        return {
            str(state): {str(field): deepcopy(value) for field, value in dict(body).items()}
            for state, body in dict(raw).items()
        }

    def _finish(self, report: dict[str, Any]) -> dict[str, Any]:
        report["config"] = list(self.config)
        report["values"] = self._values()
        report["changes"] = [
            record.as_dict() if hasattr(record, "as_dict") else dict(record)
            for record in self.scopes.changes()
        ]
        return report


__all__ = ("Context", "Engine", "step_site")
