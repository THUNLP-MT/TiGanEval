'Sandboxed runner for one Kerbside handset session.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _states(cache: Any, protocol: Any) -> dict[str, Any]:
    'Every query the process holds, field by field.'

    rows: dict[str, Any] = {}
    for key in cache.keys():
        state = cache.state(key)
        rows[protocol.cache_key(key)] = {
            name: getattr(state, name) for name in protocol.STATE_FIELDS
        }
    return rows


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from handset import protocol

    module = importlib.reload(importlib.import_module("handset.persister"))
    clock = protocol.Clock(int(payload.get("start_ms", 0)))
    depot = protocol.Depot(dict(payload.get("depot", {})), clock)
    events = protocol.EventLog()
    config = protocol.PersistConfig()
    store = protocol.DeviceStore()
    cache: Any = protocol.QueryCache()
    persister: Any = None
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    def watch(key: Any, state: Any) -> None:
        events.settled.append({"key": protocol.cache_key(key), "at_ms": clock.now_ms()})

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
            loads, calls, restores = (
                len(events.load_completed), len(depot.log), len(events.restored)
            )
            try:
                if kind == "device":
                    store = protocol.DeviceStore()
                    saved = {}
                    for slot in op.get("slots", ()):
                        key = [str(part) for part in slot["key"]]
                        state = protocol.QueryState(**dict(slot.get("state", {})))
                        name = protocol.slot_name(config.prefix, protocol.cache_key(key))
                        payload_for_slot = protocol.snapshot_payload(key, state)
                        store.write(name, payload_for_slot)
                        saved[name] = payload_for_slot
                    persister = None
                    record["saved_on_the_device"] = saved
                elif kind == "clock":
                    clock.set(int(op["to"]))
                elif kind == "wait":
                    clock.advance(int(op["ms"]))
                elif kind == "open":
                    cache = protocol.QueryCache()
                    cache.on_settled.append(watch)
                    persister = module.Persister(store, config)
                elif kind == "rebuild":
                    record["queries_before"] = _states(cache, protocol)
                    record["rebuilt"] = persister.restore_all(
                        cache, clock=clock, events=events
                    )
                    record["queries_after"] = _states(cache, protocol)
                elif kind in ("mount", "refresh"):
                    key = [str(part) for part in op["key"]]
                    record["key"] = protocol.cache_key(key)
                    record["screen"] = protocol.run_query(
                        cache, key, depot=depot, clock=clock, events=events,
                        persister=persister if kind == "mount" else None,
                    )
                elif kind == "save":
                    key = [str(part) for part in op["key"]]
                    state = cache.state(key)
                    if state is None:
                        raise ValueError("cannot save a query the process does not hold")
                    record["key"] = protocol.cache_key(key)
                    record["screen"] = protocol.derive_result(state)
                    persister.save(key, state)
                elif kind == "read":
                    key = [str(part) for part in op["key"]]
                    state = cache.state(key)
                    record["key"] = protocol.cache_key(key)
                    record["screen"] = None if state is None else protocol.derive_result(state)
                else:
                    record["error"] = f"unknown operation: {kind}"
            except BaseException as exc:
                record["error"] = _describe(exc)
            record["loads_completed_here"] = len(events.load_completed) - loads
            record["depot_calls_here"] = len(depot.log) - calls
            record["restored_here"] = len(events.restored) - restores
            record["clock_after_ms"] = clock.now_ms()
            records.append(record)

    return {
        "ok": True,
        "operations": records,
        "events": {
            "load_completed": list(events.load_completed),
            "settled": list(events.settled),
            "restored": list(events.restored),
        },
        "depot_log": list(depot.log),
        "totals": {
            "loads_completed": len(events.load_completed),
            "depot_calls": len(depot.log),
            "restored": len(events.restored),
        },
        "clock_ms": clock.now_ms(),
        "stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
