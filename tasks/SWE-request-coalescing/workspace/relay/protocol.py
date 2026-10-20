"""Runtime contract for the document summary relay.

The relay sits between the desks that ask for a summary and the model backend
that renders one. The front door, the backend, the usage ledger and the replay
substrate are built against this module and ship it with the release. Nothing
here reads a clock or runs in a second thread, so a window replays to the same
bytes every time.

The relay you write
-------------------

``relay/dispatcher.py`` must expose ``build_dispatcher(runtime)``, which returns
one object that lives for the whole replay and receives these callbacks::

    on_call(call)                            one caller arrived at the front door
    on_chunk(execution_id, index, chunk)     the backend produced the next piece
    on_upstream_complete(execution_id)       that rendering finished
    on_upstream_error(execution_id, reason)  that rendering failed outright
    on_abandon(call_id)                      that caller hung up
    statistics()                             the counters the capacity review reads

A callback that raises is caught by the substrate and recorded against the
event; the replay carries on and the caller it was handling is never answered.

A call is a mapping with exactly ``CALL_FIELDS``. ``request_id`` and
``trace_id`` are stamped by the front door for tracing and ``retry_budget`` is
the client library's own knob, so they differ between two desks asking for the
same thing.

The backend
-----------

``runtime.begin_upstream(document_id, principal)`` asks the backend for one
rendering of ``document_id`` for ``principal`` and returns its ``execution_id``.
What the backend produces for a document under one scope is
``reference_summary(document_id, scope)``, and ``summary_scope(tenant,
clearance)`` is the scope of a desk with that tenant and that clearance.

Every rendering in flight shares one connection back from the backend. A piece
reaches ``on_chunk`` carrying the ``index`` it occupies in its own rendering,
and the rendering then either completes or fails. None of that timing is the
relay's to choose.

Answering, billing, reporting
-----------------------------

``runtime.deliver(call_id, chunks)`` answers a caller with the pieces of a
summary and ``runtime.refuse(call_id, reason)`` answers it with a refusal, the
two ``OUTCOME_KINDS`` the replay records against the caller each one names. The
front door holds that caller's connection open until one of them lands.
``runtime.is_authorized(principal, document_id)`` says whether the directory
has given that principal that document, and ``tenant_of`` and ``clearance_of``
read the rest of that desk's directory entry.

``runtime.record_usage(entry)`` appends one entry to the usage ledger: a mapping
with exactly ``USAGE_FIELDS``. ``statistics()`` returns a mapping with exactly
``STATISTIC_FIELDS``, the three counters the capacity review reads off this
service.

The relay is handed a ``RelayRuntime`` and nothing else. It is a handle on the
front door, the backend and the ledger; the record those three keep of a replay
is not on it.

Recorded windows
----------------

A window is a list of events replayed in order against one relay. ``call``
carries ``CALL_FIELDS`` and brings a caller in. ``advance`` has every running
rendering produce its next ``chunks`` pieces. ``finish`` completes every running
rendering that has produced all of its pieces, and ``fail`` fails every running
rendering with ``reason``. ``abandon`` hangs ``call_id`` up. ``drain`` runs
every rendering to its end and completes it.

A window also says how the connection handed that hour's pieces over, one of
``HANDOVER_ORDERS``: ``"in-turn"``, the default, gives each rendering's pieces
to ``on_chunk`` in the order the backend produced them, and ``"out-of-turn"``
gives them in the reverse of that order. Every piece carries its own ``index``
either way, and a rendering started in a window is handed over the way that
window says for as long as it runs.

``simulate(programme, factory=...)`` replays a whole programme of windows
against one relay and returns raw telemetry: what each caller was answered with,
which renderings the backend ran, what went into the ledger, and what the relay
reported. It judges nothing.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Callable, Mapping, Sequence


CALL_FIELDS: tuple[str, ...] = (
    "call_id", "principal", "document_id", "request_id", "trace_id", "retry_budget",
)
USAGE_FIELDS: tuple[str, ...] = (
    "call_id", "principal", "tenant", "request_id", "document_id", "outcome",
)
STATISTIC_FIELDS: tuple[str, ...] = (
    "calls_accepted", "upstream_executions", "calls_answered",
)
EVENT_TYPES: tuple[str, ...] = ("call", "advance", "finish", "fail", "abandon", "drain")
OUTCOME_KINDS: tuple[str, ...] = ("summary", "refused")
HANDOVER_ORDERS: tuple[str, ...] = ("in-turn", "out-of-turn")
MAX_CHUNKS = 6


class RelayError(RuntimeError):
    """The relay used the runtime in a way the front door cannot carry out."""


def summary_scope(tenant: str, clearance: str) -> str:
    """Name the scope the backend renders a summary for."""
    return f"{str(tenant)}/{str(clearance)}"


def reference_summary(document_id: str, scope: str) -> tuple[str, ...]:
    """The pieces the backend produces for one document under one scope.

    This is the renderer itself, not a description of it.
    """
    salt = hashlib.sha256(f"{str(document_id)}\x1f{str(scope)}".encode("utf-8")).hexdigest()
    pieces = 3 + int(salt[:2], 16) % (MAX_CHUNKS - 2)
    return tuple(
        f"{document_id}|{scope}|{index}|{salt[8 * index : 8 * index + 8]}"
        for index in range(pieces)
    )


def body_digest(chunks: Sequence[str]) -> str:
    """A stable digest of one delivered summary."""
    joined = "\n".join(str(chunk) for chunk in chunks).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:16]


class _Execution:
    """One rendering the backend is running."""

    def __init__(self, execution_id, document_id, principal, scope, window, started_by,
                 handover="in-turn"):
        self.execution_id = execution_id
        self.document_id = str(document_id)
        self.principal = str(principal)
        self.chunks = reference_summary(document_id, scope)
        positions = tuple(range(len(self.chunks)))
        self.handover = tuple(reversed(positions)) if handover == "out-of-turn" else positions
        self.produced = 0
        self.state = "running"
        self.started_by = started_by
        self.window = window

    @property
    def exhausted(self) -> bool:
        return self.produced >= len(self.chunks)

    def row(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "document_id": self.document_id,
            "rendered_for": self.principal,
            "started_by": self.started_by,
            "window": self.window,
            "pieces_produced": self.produced,
            "pieces_in_the_rendering": len(self.chunks),
            "state": self.state,
        }


class _Wire:
    """What the front door, the backend and the ledger recorded during one
    replay. The substrate owns this; the relay is handed a ``RelayRuntime``."""

    def __init__(self, directory: Mapping[str, Mapping[str, Any]]):
        self.directory = {
            str(principal): {
                "tenant": str(desk["tenant"]),
                "clearance": str(desk["clearance"]),
                "documents": tuple(str(item) for item in desk.get("documents", ())),
            }
            for principal, desk in dict(directory).items()
        }
        self.calls: dict[str, dict[str, Any]] = {}
        self.arrival_order: list[str] = []
        self.settlements: dict[str, list[dict[str, Any]]] = {}
        self.abandoned: list[str] = []
        self.executions: list[_Execution] = []
        self.usage_entries: list[dict[str, Any]] = []
        self.notes: list[str] = []
        self.window = ""
        self.handover = HANDOVER_ORDERS[0]
        self.current_call: str | None = None

    def desk(self, principal: str) -> Mapping[str, Any]:
        desk = self.directory.get(str(principal))
        if desk is None:
            raise RelayError(f"no directory entry for principal {principal!r}")
        return desk

    def accept(self, call: Mapping[str, Any]) -> None:
        key = str(call["call_id"])
        self.calls[key] = {**dict(call), "window": self.window}
        self.arrival_order.append(key)
        self.settlements.setdefault(key, [])

    def settle(self, call_id: str, outcome: Mapping[str, Any]) -> None:
        key = str(call_id)
        if key not in self.calls:
            raise RelayError(f"no caller {key!r} is waiting at the front door")
        self.settlements.setdefault(key, []).append(dict(outcome))

    def running(self) -> list[_Execution]:
        return [item for item in self.executions if item.state == "running"]


class RelayRuntime:
    """Everything the relay may do.

    One handle on the front door, the backend and the ledger.
    """

    __slots__ = ("__operations",)

    def __init__(self, directory: Mapping[str, Mapping[str, Any]], *,
                 _wire: _Wire | None = None):
        wire = _Wire(directory) if _wire is None else _wire

        def begin(document_id: str, principal: str) -> str:
            desk = wire.desk(principal)
            execution = _Execution(
                f"x{len(wire.executions) + 1}",
                document_id,
                principal,
                summary_scope(desk["tenant"], desk["clearance"]),
                wire.window,
                wire.current_call,
                wire.handover,
            )
            wire.executions.append(execution)
            return execution.execution_id

        object.__setattr__(self, "_RelayRuntime__operations", (
            lambda principal: wire.desk(principal)["tenant"],
            lambda principal: wire.desk(principal)["clearance"],
            lambda principal, document_id: (
                str(document_id) in wire.desk(principal)["documents"]
            ),
            begin,
            lambda call_id, outcome: wire.settle(call_id, outcome),
            lambda entry: wire.usage_entries.append({
                "window": wire.window,
                "entry": {str(key): deepcopy(value) for key, value in entry.items()},
            }),
            lambda message: wire.notes.append(str(message)[:200]),
        ))

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "_wire", "_RelayRuntime__wire",
            "_operations", "_RelayRuntime__operations",
        }:
            raise AttributeError(
                "RelayRuntime is an operation handle and does not expose replay telemetry"
            )
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(
            f"RelayRuntime has no attribute {name!r}: it is a handle on the front "
            "door, the backend and the ledger, and carries no record of the replay"
        )

    def tenant_of(self, principal: str) -> str:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        return operations[0](principal)

    def clearance_of(self, principal: str) -> str:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        return operations[1](principal)

    def is_authorized(self, principal: str, document_id: str) -> bool:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        return operations[2](principal, document_id)

    def begin_upstream(self, document_id: str, principal: str) -> str:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        return operations[3](document_id, principal)

    def deliver(self, call_id: str, chunks: Sequence[str]) -> None:
        if isinstance(chunks, (str, bytes)) or not isinstance(chunks, Sequence):
            raise RelayError("a delivered summary must be a sequence of pieces")
        pieces = tuple(str(piece) for piece in chunks)
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        operations[4](call_id, {
            "kind": "summary", "digest": body_digest(pieces), "pieces": len(pieces),
            "first_piece": pieces[0] if pieces else "",
        })

    def refuse(self, call_id: str, reason: str) -> None:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        operations[4](call_id, {"kind": "refused", "reason": str(reason)})

    def record_usage(self, entry: Mapping[str, Any]) -> None:
        if not isinstance(entry, Mapping):
            raise RelayError("a usage entry must be a mapping")
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        operations[5](entry)

    def note(self, message: str) -> None:
        operations = object.__getattribute__(self, "_RelayRuntime__operations")
        operations[6](message)


def _guard(errors: list[dict[str, Any]], window: str, what: str,
           call: Callable[..., Any], *args: Any) -> None:
    try:
        call(*args)
    except BaseException as exc:  # the front door survives a relay defect
        errors.append({"window": window, "callback": what,
                       "error": f"{type(exc).__name__}: {str(exc)[:200]}"})


def _complete(wire: _Wire, dispatcher: Any,
              errors: list[dict[str, Any]], label: str) -> None:
    for execution in wire.running():
        if execution.exhausted:
            execution.state = "complete"
            _guard(errors, label, "on_upstream_complete",
                   dispatcher.on_upstream_complete, execution.execution_id)


def simulate(programme: Mapping[str, Any], *,
             factory: Callable[[RelayRuntime], Any]) -> dict[str, Any]:
    """Replay one programme of windows against one relay and report what happened."""
    wire = _Wire(programme["directory"])
    runtime = RelayRuntime(programme["directory"], _wire=wire)
    errors: list[dict[str, Any]] = []
    dispatcher = factory(runtime)
    for window in programme["windows"]:
        label = str(window.get("label", ""))
        wire.window = label
        handover = str(window.get("handover", HANDOVER_ORDERS[0]))
        if handover not in HANDOVER_ORDERS:
            raise ValueError(f"unknown piece handover: {handover!r}")
        wire.handover = handover
        for raw in window.get("events", ()):
            event = dict(raw)
            kind = str(event.get("type", ""))
            if kind == "call":
                call = {field: event[field] for field in CALL_FIELDS}
                wire.accept(call)
                wire.current_call = str(call["call_id"])
                _guard(errors, label, "on_call", dispatcher.on_call, deepcopy(call))
                wire.current_call = None
            elif kind in ("advance", "drain"):
                steps = MAX_CHUNKS if kind == "drain" else int(event.get("chunks", 1))
                for _ in range(steps):
                    for execution in wire.running():
                        if execution.exhausted:
                            continue
                        index = execution.handover[execution.produced]
                        execution.produced += 1
                        _guard(errors, label, "on_chunk", dispatcher.on_chunk,
                               execution.execution_id, index, execution.chunks[index])
                if kind == "drain":
                    _complete(wire, dispatcher, errors, label)
            elif kind == "finish":
                _complete(wire, dispatcher, errors, label)
            elif kind == "fail":
                reason = str(event.get("reason", "backend_unavailable"))
                for execution in wire.running():
                    execution.state = "failed"
                    _guard(errors, label, "on_upstream_error",
                           dispatcher.on_upstream_error, execution.execution_id, reason)
            elif kind == "abandon":
                call_id = str(event["call_id"])
                wire.abandoned.append(call_id)
                _guard(errors, label, "on_abandon", dispatcher.on_abandon, call_id)
            else:
                raise ValueError(f"unknown window event: {kind!r}")
    return _report(wire, dispatcher, errors)


def _report(wire: _Wire, dispatcher: Any,
            errors: list[dict[str, Any]]) -> dict[str, Any]:
    # Freeze substrate telemetry before asking relay code for its own
    # counters. ``statistics`` is observational: work or answers attempted from
    # inside it must not rewrite the replay that the substrate already saw.
    calls = [
        {
            "call_id": call_id,
            "window": wire.calls[call_id].get("window", ""),
            "principal": wire.calls[call_id]["principal"],
            "document_id": wire.calls[call_id]["document_id"],
            "request_id": wire.calls[call_id]["request_id"],
            "hung_up": call_id in wire.abandoned,
            "answers": [dict(item) for item in wire.settlements.get(call_id, ())],
        }
        for call_id in wire.arrival_order
    ]
    arrival_order = list(wire.arrival_order)
    executions = [deepcopy(execution.row()) for execution in wire.executions]
    usage_entries = deepcopy(wire.usage_entries)
    notes = list(wire.notes[:20])
    try:
        reported = dict(dispatcher.statistics())
    except BaseException as exc:
        reported = {}
        errors.append({"window": wire.window, "callback": "statistics",
                       "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    return {
        "calls": calls,
        "arrival_order": arrival_order,
        "executions": executions,
        "usage_entries": usage_entries,
        "reported_statistics": reported,
        "relay_errors": errors,
        "notes": notes,
    }


__all__ = (
    "CALL_FIELDS", "EVENT_TYPES", "HANDOVER_ORDERS", "MAX_CHUNKS", "OUTCOME_KINDS",
    "STATISTIC_FIELDS", "USAGE_FIELDS", "RelayError", "RelayRuntime", "body_digest",
    "reference_summary", "simulate", "summary_scope",
)
