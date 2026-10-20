'Sandboxed runner for the edge gateway simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _request(op: Mapping[str, Any], protocol: Any) -> Any:
    "One caller's request, in the shape that caller happens to hold."

    text = str(op["target"])
    shape = str(op.get("shape", "absolute"))
    if shape == "url":
        target: Any = protocol.parse_url(text)
    elif shape == "request":
        target = protocol.Request(target=text, label=str(op.get("label", "")))
    else:
        target = text
    return protocol.Request(
        target=target, label=str(op.get("label", "")),
        guarded=bool(op.get("guarded", True)), retries=int(op.get("retries", 0)),
        ignore_errors=bool(op.get("ignore_errors", False)),
        transform=str(op.get("transform", "text")))


def _call_state(call: Any, protocol: Any) -> dict[str, Any]:
    error = call.error
    response = getattr(call, "response", None)
    status = None if response is None else int(getattr(response, "status", 0))
    if isinstance(error, protocol.UpstreamError):
        outcome = "rejected"
    elif isinstance(error, protocol.GatewayBlocked):
        outcome = "blocked"
    else:
        outcome = "failed" if error is not None else ("ok" if call.done else "in_flight")
    return {
        "done": bool(call.done),
        "outcome": outcome,
        "status": status,
        "attempts": int(getattr(call, "attempts", 0)),
        "error": None if error is None else _describe(error),
    }


def _candidate_clock(start_ms: float, protocol: Any) -> Any:
    "A Clock-shaped, read-only view of the runner's authoritative clock."

    class ReadOnlyClock(protocol.Clock):
        __slots__ = ()

        def now_ms(self) -> float:
            return float(self._now)

        def _sync(self, value: float) -> None:
            object.__setattr__(self, "_now", float(value))

        def set(self, value: float) -> None:
            raise TypeError("the gateway cannot move the operator's clock")

        def advance(self, value: float) -> None:
            raise TypeError("the gateway cannot move the operator's clock")

    return ReadOnlyClock(float(start_ms))


class _CandidateTransport:
    'Constructor compatibility without access to the audited transport.'

    __slots__ = ()

    def send(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("only Session may send gateway traffic")


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from gateway import protocol

    clock = protocol.Clock(float(payload.get("start_ms", 0.0)))
    transport = protocol.Transport(dict(payload.get("upstreams", {})), clock)
    clock_view = _candidate_clock(clock.now_ms(), protocol)
    audit: list[dict[str, Any]] = []
    authoritative_send = transport.send

    def audited_send(*args: Any, **kwargs: Any) -> Any:
        before = len(transport.log)
        try:
            return authoritative_send(*args, **kwargs)
        finally:
            audit.extend(dict(row) for row in transport.log[before:])
            clock_view._sync(clock.now_ms())

    transport.send = audited_send
    session = protocol.Session(clock, transport)
    transport_view = _CandidateTransport()
    module = importlib.reload(importlib.import_module("gateway.breaker"))
    clients: dict[str, Any] = {}
    calls: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            kind = str(op.get("op", ""))
            record: dict[str, Any] = {
                "index": index,
                "op": kind,
                "label": str(op.get("label", f"{kind}-{index}")),
                "phase": str(op.get("phase", "")),
                "clock_ms": clock.now_ms(),
            }
            clock_view._sync(clock.now_ms())
            try:
                if kind == "client":
                    name = str(op["name"])
                    parent = op.get("from")
                    if parent is None:
                        config = protocol.ClientConfig(**dict(op.get("config", {})))
                        clients[name] = module.Gateway(config, clock_view, transport_view)
                    else:
                        clients[name] = clients[str(parent)].create(**dict(op.get("overrides", {})))
                    record["ok"] = True
                elif kind in ("clock", "advance"):
                    if kind == "clock":
                        clock.set(float(op["to"]))
                    else:
                        clock.advance(float(op["ms"]))
                    record["ok"] = True
                    record["clock_ms"] = clock.now_ms()
                elif kind == "start":
                    request = _request(op, protocol)
                    call = session.start(clients[str(op["client"])], request)
                    calls[str(op["call"])] = call
                    record["ok"] = True
                    record["call"] = call.id
                    record["client"] = str(op["client"])
                    record["guarded"] = bool(request.guarded)
                    record["state"] = _call_state(call, protocol)
                elif kind in ("step", "run"):
                    call = calls[str(op["call"])]
                    if kind == "step":
                        call.step()
                    else:
                        session.run(call)
                    record["ok"] = True
                    record["call"] = call.id
                    record["state"] = _call_state(call, protocol)
                else:
                    record["ok"] = False
                    record["error"] = f"unknown operation: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            record["clock_after_ms"] = clock.now_ms()
            records.append(record)

    return {
        "ok": True,
        "operations": records,
        "transport": audit,
        "calls": {
            call.id: {
                "label": str(call.request.label),
                "guarded": bool(call.request.guarded),
                **_call_state(call, protocol),
            }
            for call in session.calls
        },
        "clock_ms": clock.now_ms(),
        "stdout": captured.getvalue()[-2000:],
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
