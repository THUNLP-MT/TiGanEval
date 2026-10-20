"Sandboxed runner for the storage engine's write path."

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


class ProtocolMutationError(RuntimeError):
    'The editable tracker changed the engine that is meant to drive it.'


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _protocol_surface(protocol: Any) -> tuple[Any, ...]:
    'Objects from the frozen module whose identity must survive tracker calls.'

    module_members = (
        "Record",
        "SyncResult",
        "DurableState",
        "DurabilityEvent",
        "Waiter",
        "WriteAheadLog",
        "Engine",
        "encode_batch",
        "key_count",
        "recover",
        "durable_watermark",
    )
    engine_members = (
        "run",
        "_dispatch",
        "_sync",
        "_observe",
        "_ask",
        "_read_state",
        "_collect_released",
    )
    log_members = ("append", "arm_fault", "sync", "durable_offset")
    return (
        *(getattr(protocol, name) for name in module_members),
        *(getattr(protocol.Engine, name) for name in engine_members),
        *(getattr(protocol.WriteAheadLog, name) for name in log_members),
    )


def _require_protocol_surface(protocol: Any, expected: tuple[Any, ...]) -> None:
    if _protocol_surface(protocol) != expected:
        raise ProtocolMutationError("the editable tracker modified engine.protocol")


def _run_session(
    protocol: Any,
    session: Mapping[str, Any],
    protocol_surface: tuple[Any, ...],
) -> dict[str, Any]:
    module = importlib.reload(importlib.import_module("engine.durability"))
    _require_protocol_surface(protocol, protocol_surface)
    tracker = module.DurabilityTracker()
    _require_protocol_surface(protocol, protocol_surface)
    engine = protocol.Engine(
        tracker,
        listener=bool(session.get("listener", True)),
        sync_grouping=int(session.get("sync_grouping", 1)),
    )
    steps = engine.run(list(session.get("timeline", ())))
    _require_protocol_surface(protocol, protocol_surface)
    return {
        "steps": [json.loads(json.dumps(step, default=str)) for step in steps],
        "error": None,
    }


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from engine import protocol

    protocol_surface = _protocol_surface(protocol)
    sessions: dict[str, Any] = {}
    order: list[str] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for raw in payload.get("sessions", ()):
            session = dict(raw)
            name = str(session.get("name", f"session-{len(order)}"))
            order.append(name)
            try:
                sessions[name] = _run_session(protocol, session, protocol_surface)
            except BaseException as exc:
                sessions[name] = {"steps": [], "error": _describe(exc)}
            sessions[name]["listener"] = bool(session.get("listener", True))
            sessions[name]["sync_grouping"] = int(session.get("sync_grouping", 1))
    return {
        "ok": True,
        "order": order,
        "sessions": sessions,
        "tracker_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
