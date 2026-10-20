'Sandboxed runner for one console session against the delivered files.'

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
from typing import Any, Mapping

def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error)[:200]}"

def _prepare(path: Any) -> str:
    target = Path(str(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)

def _plain(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, (list, tuple)):
        return all(_plain(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _plain(item) for key, item in value.items())
    return False

def _namespace(shell: Any) -> dict[str, Any]:
    return {name: value for name, value in shell.user_ns.items()
            if name not in ("__builtins__", "Out") and _plain(value)}

def _inspect(path: Any, protocol: Any) -> dict[str, Any]:
    target = Path(str(path))
    if not target.is_file():
        return {"exists": False}
    digest = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    try:
        metadata, events = protocol.read_bundle(target)
    except BaseException as exc:
        return {"exists": True, "digest": digest, "unreadable": _describe(exc)}
    return {"exists": True, "digest": digest, "metadata": metadata, "events": events}

def _recorder(entry: Mapping[str, Any], op: Mapping[str, Any], recorders: Any) -> Any:
    'The recorder this operation was aimed at.'
    name = str(op.get("recorder", "main"))
    built = entry["recorders"]
    if name not in built:
        built[name] = recorders.SessionRecorder(entry["shell"])
    return built[name]

def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from bundle import protocol

    recorders = importlib.reload(importlib.import_module("bundle.recorder"))
    replays = importlib.reload(importlib.import_module("bundle.replay"))
    protocol.reset_time()
    consoles: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            kind = str(op.get("op", ""))
            name = str(op.get("console", ""))
            entry = consoles.get(name)
            record: dict[str, Any] = {
                "index": index, "op": kind, "label": str(op.get("label", f"{kind}-{index}")),
                "phase": str(op.get("phase", "")), "console": name or None}
            try:
                if kind == "console":
                    shell = protocol.Shell(execution_count=int(op.get("execution_count", 1)))
                    toolbar = recorders.SessionRecorder(shell)
                    entry = {"shell": shell, "recorder": toolbar,
                             "recorders": {"main": toolbar}, "runs": 0}
                    consoles[name] = entry
                    original = shell.run_cell

                    def counted(code, store_history=True, _entry=entry, _original=original):
                        _entry["runs"] += 1
                        return _original(code, store_history=store_history)

                    shell.run_cell = counted
                elif kind == "cell":
                    shell = entry["shell"]
                    mark = shell.history.count
                    result = shell.run_cell(str(op["code"]), bool(op.get("store_history", True)))
                    record.update(
                        code=str(op["code"]), counter=int(result.counter),
                        execution_count=result.execution_count, success=bool(result.success),
                        cell_error=None if result.error is None else _describe(result.error),
                        printed=[{"kind": item.kind, "text": item.text}
                                 for item in shell.history.since(mark)])
                elif kind == "start":
                    record["recorder_name"] = str(op.get("recorder", "main"))
                    record["returned"] = str(_recorder(entry, op, recorders).start(
                        _prepare(op["path"]), overwrite=bool(op.get("overwrite", False)),
                        redact=tuple(op.get("redact", ()))))
                elif kind == "stop":
                    record["recorder_name"] = str(op.get("recorder", "main"))
                    record["returned"] = str(_recorder(entry, op, recorders).stop())
                elif kind == "status":
                    pass
                elif kind == "fixture":
                    protocol.write_bundle(
                        _prepare(op["path"]), dict(op["metadata"]), overwrite=True,
                        events=[dict(event) for event in op.get("events", ())])
                elif kind == "inspect":
                    record["file"] = _inspect(op["path"], protocol)
                elif kind == "load":
                    metadata, events = replays.load_bundle(str(op["path"]))
                    record["loaded"] = {"metadata": metadata, "events": events}
                elif kind == "replay":
                    shell = entry["shell"]
                    before, runs = int(shell.execution_count), int(entry["runs"])
                    try:
                        report = replays.replay_bundle(
                            shell, str(op["path"]),
                            stop_on_error=bool(op.get("stop_on_error", True)),
                            store_history=bool(op.get("store_history", True)),
                        )
                        record["report"] = {
                            "executed": list(getattr(report, "executed", ()) or ()),
                            "stopped_at": getattr(report, "stopped_at", None)}
                    finally:
                        record.update(
                            counter_before=before, counter_after=int(shell.execution_count),
                            cells_run=int(entry["runs"]) - runs, namespace=_namespace(shell))
                else:
                    raise ValueError(f"unknown console operation: {kind}")
                record["ok"] = True
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                codes = getattr(exc, "errors", None)
                if codes is not None:
                    record["error_codes"] = [str(code) for code in codes]
            if entry is not None:
                try:
                    record["recording"] = dict(entry["recorder"].status())
                    record["hooks"] = entry["shell"].events.registered()
                    record["console_counter"] = int(entry["shell"].execution_count)
                except BaseException as exc:
                    record["recording"] = {"unreadable": _describe(exc)}
            records.append(record)

    return {"ok": True, "operations": records, "stdout": captured.getvalue()[-2000:]}

def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
