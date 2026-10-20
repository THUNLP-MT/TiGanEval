'`run_project` for the estate compliance service: status and console replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.taskkit import artifact_hash
from tiganeval.tools import TaskToolResult


def _private() -> tuple[Any, Any]:
    from .private import harness, workload

    return harness, workload


def _scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _record_path(workspace: Path, arguments: Mapping[str, Any]) -> Path:
    raw = arguments.get("record")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("run_project replay requires a record path")
    path = (workspace / raw).resolve()
    if workspace not in path.parents or path.suffix != ".json" or not path.is_file():
        raise ValueError("record must name an existing JSON file inside the workspace")
    return path


def _block(title: str, value: Any) -> str:
    return f"\n\n{title}:\n" + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _status(workspace: Path) -> Mapping[str, Any]:
    "The service's files and the recorded runs the team replays."

    harness, workload = _private()
    records = []
    for path in sorted((workspace / "project_records").glob("*.json")):
        raw = _scene(path)
        record_id = str(raw.get("record_id", path.stem))
        profile = harness.PUBLIC_RECORDS.get(record_id)
        program = workload.build_program(profile) if profile else {}
        records.append({
            "record": f"project_records/{path.name}", "scene": raw.get("scene"),
            "environments": workload.program_environments(program) if program else {},
            "operations": len(program.get("operations", ())) if program else 0,
        })
    return {
        "summary": "The compliance service's files and the recorded runs the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "estate_files": sorted(path.relative_to(workspace).as_posix()
                                   for path in (workspace / "estate").glob("*.py")),
            "editable_files": list(harness.EDITABLE_FILES),
        },
        "records": records,
    }


def _short(row: Mapping[str, Any]) -> str:
    'One row of the record ledger as the console prints it on one line.'

    text = (f"{row.get('key')} [{row.get('severity')}] {row.get('status')}"
            f" first seen {row.get('detected_on')}")
    if row.get("resolved_on"):
        text += f", resolved {row.get('resolved_on')}"
    return f"{text} :: declared {row.get('expected')!r} / read {row.get('actual')!r} (id {row.get('id')})"


def _console_rows(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Every operation the console drove, and what it answered.'

    names = ("label", "op", "on", "environment", "ok", "error", "baseline",
             "services_declared", "services_scanned", "refused", "action",
             "service", "drift_type", "applied", "drift")
    rows = []
    for record in candidate.get("operations", ()):
        row = {name: record.get(name) for name in names if record.get(name) is not None}
        if str(record.get("op")) in ("capture", "activate", "delete"):
            row["in_force_after_this"] = sorted(
                f"{item.get('environment')}: {item.get('id')} ({item.get('service_count')} services)"
                for item in record.get("baselines", ())
                if isinstance(item, Mapping) and item.get("active"))
            row["rows_held_after_this"] = len(record.get("ledger", ()))
            row["nights_of_numbers_after_this"] = len(record.get("history", ()))
        rows.append(row)
    return rows


def _nightly_rows(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Each night: its numbers, durable ledger and detected action queue.'

    rows = []
    for record in candidate.get("operations", ()):
        if str(record.get("op")) != "scan":
            continue
        ledger = [dict(row) for row in record.get("ledger", ()) if isinstance(row, Mapping)]
        unresolved = [row for row in ledger if str(row.get("status")) != "resolved"]
        actionable = [row for row in ledger if str(row.get("status")) == "detected"]
        rows.append({
            "night": record.get("label"), "on": record.get("on"),
            "environment": record.get("environment"),
            "services_scanned": record.get("services_scanned"),
            "the_console_refused_to_compare": bool(record.get("refused")),
            "error": record.get("error"),
            "numbers_this_build_produced": record.get("snapshot"),
            "numbers_the_old_script_wrote": record.get("recorded"),
            "unresolved_records_after_this_night": len(unresolved),
            "actionable_rows_after_this_night": len(actionable),
            "resolved_records_after_this_night": len(ledger) - len(unresolved),
            "rows_written_on_this_night": [
                _short(row) for row in ledger
                if int(row.get("detected_at", -1)) == int(record.get("at", 0))][:12],
            "the_record_ledger_after_this_night": [_short(row) for row in ledger][:20],
            "the_operator_queue_after_this_night": [_short(row) for row in actionable][:20],
        })
    return rows


def _replay(workspace: Path, path: Path) -> Mapping[str, Any]:
    'Drive one recorded console run against this build and report what it printed.'

    harness, workload = _private()
    raw = _scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = workload.build_program(harness.PUBLIC_RECORDS[record_id])
    candidate = harness.PROJECT.invoke(workspace, dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} run could not be replayed against this build.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {"execution_error": candidate.get("error", "unknown failure"),
                       "diagnostic": candidate.get("diagnostic")},
        }
    return {
        "summary": f"The {record_id} run replayed against this build.",
        "measurements": {
            "record_id": record_id, "scene": raw.get("scene"),
            "environments": workload.program_environments(program),
            "operation_count": len(candidate.get("operations", ())),
        },
        "public": {
            "what_the_console_did": _console_rows(candidate),
            "what_each_night_produced": _nightly_rows(candidate),
            "the_list_at_the_end": [_short(row) for row in candidate.get("ledger", ())][:60],
            "the_numbers_at_the_end": list(candidate.get("history", ())),
            "the_baselines_at_the_end": list(candidate.get("baselines", ())),
        },
    }


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))

    if action == "status":
        outcome = _status(workspace)
        content = str(outcome["summary"])
        content += _block("Workspace", outcome["measurements"])
        content += _block("Recorded runs", outcome["records"])
        return TaskToolResult(
            content=content,
            data={"action": "status", "measurements": dict(outcome["measurements"]),
                  "records": list(outcome["records"])},
        )

    if action == "replay":
        path = _record_path(workspace, arguments)
        outcome = _replay(workspace, path)
        content = str(outcome["summary"])
        content += _block("Run", outcome["measurements"])
        content += _block("Console", outcome["public"])
        return TaskToolResult(
            content=content,
            data={"action": "replay", "record": path.relative_to(workspace).as_posix(),
                  "measurements": dict(outcome["measurements"]),
                  "public": dict(outcome["public"])},
        )

    raise ValueError("run_project.action must be status or replay")
