'`run_project` for the Kerbside handset: status and session replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.taskkit import artifact_hash
from tiganeval.tools import TaskToolResult


PUBLIC_RECORDS = (
    "reopen-after-decline",
    "overnight-shift-start",
    "saved-mid-refresh",
    "depot-came-back-first",
    "writer-round-trip",
)


def _harness() -> Any:
    from .private import harness

    return harness


def _workload() -> Any:
    from .private import workload

    return workload


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _program(record_id: str) -> dict[str, Any]:
    return _workload().build_program(record_id)


def public_status(workspace: Path) -> Mapping[str, Any]:
    'The handset files and the sessions the team can replay.'

    workload, harness = _workload(), _harness()
    records = []
    for path in sorted((workspace / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = _program(record_id) if record_id in PUBLIC_RECORDS else {}
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "queries_on_the_device": (
                    sorted(workload.all_slots(program)) if program else []
                ),
                "operations": len(program.get("operations", ())) if program else 0,
            }
        )
    return {
        "summary": "The handset workspace and the recorded sessions the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "handset_files": sorted(
                path.relative_to(workspace).as_posix()
                for path in (workspace / "handset").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
        },
        "records": records,
    }


def _console_rows(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Every operation the console drove, and what it left on the screen.'

    rows: list[dict[str, Any]] = []
    for record in session.get("operations", ()):
        row: dict[str, Any] = {
            "label": record.get("label"),
            "operation": record.get("op"),
            "phase": record.get("phase"),
            "clock_ms": record.get("clock_ms"),
            "loads_completed_here": record.get("loads_completed_here"),
            "depot_calls_here": record.get("depot_calls_here"),
            "restored_here": record.get("restored_here"),
            "error": record.get("error"),
        }
        for name in ("key", "screen", "rebuilt", "saved_on_the_device",
                     "queries_before", "queries_after"):
            if record.get(name) is not None:
                row[name] = record[name]
        rows.append(row)
    return rows


def replay_record(workspace: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded session and report what the console saw.'

    workload, harness = _workload(), _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = _program(record_id)
    session = harness.PROJECT.invoke(workspace, dict(program))
    if not session.get("ok"):
        return {
            "summary": f"The {record_id} session could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": session.get("error", "unknown failure"),
                "diagnostic": session.get("diagnostic"),
            },
        }
    return {
        "summary": f"The {record_id} session ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "queries_on_the_device": sorted(workload.all_slots(program)),
            "totals": session.get("totals"),
        },
        "public": {
            "what_the_console_drove": _console_rows(session),
            "what_reached_the_depot": list(session.get("depot_log", ())),
            "what_the_app_reported": session.get("events"),
        },
    }


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


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))

    if action == "status":
        outcome = public_status(workspace)
        content = str(outcome["summary"])
        content += _block("Workspace", outcome["measurements"])
        content += _block("Recorded sessions", outcome["records"])
        return TaskToolResult(
            content=content,
            data={
                "action": "status",
                "measurements": dict(outcome["measurements"]),
                "records": list(outcome["records"]),
            },
        )

    if action == "replay":
        path = _record_path(workspace, arguments)
        outcome = replay_record(workspace, path)
        content = str(outcome["summary"])
        content += _block("Session", outcome["measurements"])
        content += _block("Console log", outcome["public"])
        return TaskToolResult(
            content=content,
            data={
                "action": "replay",
                "record": path.relative_to(workspace).as_posix(),
                "measurements": dict(outcome["measurements"]),
                "public": dict(outcome["public"]),
            },
        )

    raise ValueError("run_project.action must be status or replay")
