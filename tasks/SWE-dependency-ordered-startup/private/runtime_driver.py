"Sandboxed console for the API service's start-up simulator."

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Callable, Mapping


class Part:
    'One component object, named so the ledger can tell two of them apart.'
    def __init__(self, token: str):
        self.token = str(token)


def _connect(
    name: str,
    spec: Mapping[str, Any],
    ledger: Any,
    contract: Any,
    record: Callable[..., None],
    held: dict[str, int],
) -> Any:


    attempts: list[int] = []

    def start() -> Any:
        record("start_begin", name)
        attempts.append(1)
        once = spec.get("session_once")
        if once and len(attempts) > 1:
            yield contract.Pause(int(spec.get("ticks", 1)))
            error = RuntimeError(f"{name}: {once}")
            record("start_error", name, error=contract.describe(error))
            raise error
        fails_after = spec.get("fails_after")
        if fails_after is not None:
            yield contract.Pause(int(fails_after))
            error = RuntimeError(f"{name}: {spec.get('error', 'the handshake was refused')}")
            record("start_error", name, error=contract.describe(error))
            raise error
        yield contract.Pause(int(spec.get("ticks", 1)))
        if spec.get("acquire"):
            held[name] = held.get(name, 0) + 1
            record("acquire", name, held=held[name])
            ledger.acquire(name)
        returns = spec.get("returns")
        value = Part(str(returns)) if returns else None
        record("start_end", name, returned=contract.identity(value))
        return value
    return start


def _disconnect(
    name: str,
    spec: Mapping[str, Any],
    ledger: Any,
    contract: Any,
    record: Callable[..., None],
    held: dict[str, int],
) -> Any:
    def stop() -> None:
        if spec.get("release"):
            count = held.get(name, 0)
            if count > 0:
                held[name] = count - 1
            record("release", name, was_holding=count > 0)
            ledger.release(name)
        guard = spec.get("guard")
        if guard and held.get(str(guard), 0) <= 0:
            error = RuntimeError(f"{name} could not flush: {guard} is already closed")
            record("stop_error", name, error=contract.describe(error))
            raise error
        if spec.get("error"):
            error = RuntimeError(f"{name}: {spec['error']}")
            record("stop_error", name, error=contract.describe(error))
            raise error
    return stop


def _register(
    registry: Any,
    ledger: Any,
    entry: Mapping[str, Any],
    contract: Any,
    record: Callable[..., None],
    held: dict[str, int],
) -> None:
    name = str(entry["name"])
    start = stop = None
    if "start" in entry:
        start = _connect(name, dict(entry["start"]), ledger, contract, record, held)
        stop = _disconnect(
            name, dict(entry.get("stop", {})), ledger, contract, record, held
        )
    registry.register(name, Part(name), start=start, stop=stop,
                      depends_on=[str(item) for item in entry.get("depends_on", ())])


def _probe(
    registry: Any,
    ledger: Any,
    name: str,
    when: str,
    contract: Any,
    record: Callable[..., None],
) -> Any:
    def action() -> None:
        try:
            value = registry.resolve(name)
        except BaseException as exc:
            record(
                "probe", name, when=when, served=False, error=contract.describe(exc)
            )
            ledger.note("probe", name, when=when, served=False, error=contract.describe(exc))
        else:
            record(
                "probe", name, when=when, served=True, token=contract.identity(value)
            )
            ledger.note("probe", name, when=when, served=True, token=contract.identity(value))
    return action


def _run_scene(spec: Mapping[str, Any], contract: Any, module: Any) -> dict[str, Any]:
    clock = contract.Clock(0)
    ledger, registry = contract.Ledger(clock), contract.Registry()
    scheduler = contract.Scheduler(clock, ledger)
    audit: list[dict[str, Any]] = []
    held: dict[str, int] = {}
    attempt = {"index": -1}

    def audit_event(event: str, name: str = "", **fields: Any) -> None:
        audit.append(
            {
                "seq": len(audit),
                "at": clock.now(),
                "attempt": int(attempt["index"]),
                "event": str(event),
                "name": str(name),
                **fields,
            }
        )

    for entry in spec.get("manifest", ()):
        _register(registry, ledger, entry, contract, audit_event, held)
    for timer in spec.get("timers", ()):
        action = _probe(
            registry,
            ledger,
            str(timer["resolve"]),
            "during bring-up",
            contract,
            audit_event,
        )
        scheduler.at(int(timer["at"]), action)
    config = contract.DeployConfig(**dict(spec.get("config", {})))
    operations: list[dict[str, Any]] = []
    try:
        start_up = module.StartUp(registry, scheduler, ledger, config)
    except BaseException as exc:
        ledger.note("console_error", "", error=contract.describe(exc))
        start_up = None
    for index, raw in enumerate(spec.get("operations", ()) if start_up else ()):
        op = dict(raw)
        kind = str(op.get("op", ""))
        operation: dict[str, Any] = {"index": index, "op": kind, "at": clock.now()}
        try:
            if kind == "bring_up":
                began = clock.now()
                attempt["index"] = len(
                    [item for item in operations if item.get("op") == "bring_up"]
                )
                ledger.note("bring_up_begin")
                try:
                    start_up.bring_up()
                    operation["ok"] = True
                except BaseException as exc:
                    operation["ok"], operation["error"] = False, contract.describe(exc)
                scheduler.drain()
                ledger.note("bring_up_end", error=operation.get("error"))
                operation["elapsed_ticks"] = clock.now() - began
            elif kind == "probe":
                _probe(
                    registry,
                    ledger,
                    str(op["name"]),
                    "after bring-up",
                    contract,
                    audit_event,
                )()
                operation["ok"], operation["name"] = True, str(op["name"])
            elif kind == "amend":
                name = str(op["name"])
                was = registry.registration(name)
                edges = [str(item) for item in op.get("depends_on", ())]
                registry.register(name, was.instance, depends_on=edges,
                                  start=was.start, stop=was.stop)
                ledger.note("amend", name, depends_on=edges)
                operation["ok"] = True
            else:
                operation["ok"], operation["error"] = False, f"unknown operation: {kind}"
        except BaseException as exc:
            operation["ok"], operation["error"] = False, contract.describe(exc)
        if kind == "bring_up":
            attempt["index"] = -1
        operation["at_after"] = clock.now()
        operations.append(operation)
    return {"name": str(spec.get("name", "")),
            "config": {"max_parallel_starts": int(config.max_parallel_starts),
                       "deploy_window_ticks": int(config.deploy_window_ticks)},
            "operations": operations, "ledger": list(ledger.entries), "audit": audit,
            "open_handles": list(ledger.open_handles()),
            "actual_open_handles": sorted(name for name, count in held.items() if count > 0),
            "clock": clock.now()}


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from bootstrap import contract
    module = importlib.reload(importlib.import_module("bootstrap.startup"))
    captured = io.StringIO()
    with redirect_stdout(captured):
        scenes = [_run_scene(dict(spec), contract, module) for spec in payload.get("scenes", ())]
    return {"ok": True, "scenes": scenes, "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
