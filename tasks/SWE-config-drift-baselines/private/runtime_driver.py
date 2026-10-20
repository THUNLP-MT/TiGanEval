'Sandboxed runner for the estate compliance console.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _rows(engine: Any, protocol: Any) -> dict[str, Any]:
    'Everything the console can list right now.'

    state: dict[str, Any] = {}
    for name, accessor, render in (
        ("ledger", "drift_records", protocol.drift_row),
        ("history", "compliance_snapshots", protocol.snapshot_row),
        ("baselines", "baseline_records", protocol.baseline_row),
    ):
        try:
            state[name] = [render(item) for item in getattr(engine, accessor)()]
        except BaseException as exc:
            state[name] = []
            state.setdefault("listing_errors", {})[name] = _describe(exc)
    state["ledger"] = protocol.sort_records(state["ledger"])
    return state


def _drift_to_triage(state: Mapping[str, Any], op: Mapping[str, Any]) -> str | None:
    'The row the operator clicked, found again by what the row is about.'

    wanted = (str(op.get("environment", "")), str(op.get("service", "")),
              str(op.get("drift_type", "")), str(op.get("field", "")))
    for row in state.get("ledger", ()):
        if str(row.get("status")) == "resolved":
            continue
        if (str(row.get("environment")), str(row.get("service")),
                str(row.get("drift_type")), str(row.get("field"))) == wanted:
            return str(row.get("id"))
    return None


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from estate import protocol

    clock = protocol.Clock(int(payload.get("start_at", 0)))
    module = importlib.reload(importlib.import_module("estate.reconcile"))
    engine = module.DriftEngine(clock)
    baseline_ids: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            kind = str(op.get("op", ""))
            clock.set(int(op.get("at", clock.now())))
            record: dict[str, Any] = {
                "index": index, "op": kind, "label": str(op.get("label", f"{kind}-{index}")),
                "at": clock.now(), "on": protocol.stamp(clock.now()),
                "environment": str(op.get("environment", "")), "ok": True,
            }
            try:
                if kind == "capture":
                    identifier = engine.capture_baseline(
                        str(op["environment"]), str(op.get("name", "")),
                        dict(op.get("services", {})))
                    baseline_ids[record["label"]] = str(identifier)
                    record["baseline"] = str(identifier)
                    record["services_declared"] = len(dict(op.get("services", {})))
                elif kind == "delete":
                    record["baseline"] = baseline_ids.get(str(op["baseline"]), "")
                    engine.delete_baseline(record["baseline"])
                elif kind == "activate":
                    record["baseline"] = baseline_ids.get(str(op["baseline"]), "")
                    engine.activate_baseline(record["baseline"])
                elif kind == "scan":
                    try:
                        snapshot = engine.scan(str(op["environment"]),
                                               dict(op.get("services", {})))
                    except protocol.NoActiveBaseline as exc:
                        record["refused"] = True
                        record["error"] = _describe(exc)
                    else:
                        record["refused"] = False
                        record["snapshot"] = protocol.snapshot_row(snapshot)
                    record["services_scanned"] = len(dict(op.get("services", {})))
                    if op.get("recorded") is not None:
                        record["recorded"] = dict(op["recorded"])
                elif kind == "triage":
                    record["action"] = str(op.get("action", ""))
                    record["service"] = str(op.get("service", ""))
                    record["drift_type"] = str(op.get("drift_type", ""))
                    target = _drift_to_triage(_rows(engine, protocol), op)
                    record["applied"] = target is not None
                    if target is not None:
                        record["drift"] = target
                        handler = (engine.acknowledge if record["action"] == "acknowledge"
                                   else engine.ignore)
                        handler(target)
                else:
                    record["ok"] = False
                    record["error"] = f"unknown operation: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            record.update(_rows(engine, protocol))
            records.append(record)

    final = _rows(engine, protocol)
    return {"ok": True, "operations": records, "clock": clock.now(),
            "ledger": final["ledger"], "history": final["history"],
            "baselines": final["baselines"], "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
