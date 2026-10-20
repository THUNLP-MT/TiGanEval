'run_project for the fleet scheduler: status and replay, telemetry only.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.tools import TaskToolResult


PUBLIC_RECORDS: tuple[str, ...] = (
    "handover-drill", "rollout-duplicate", "old-build-window", "canary-window",
)


def _private_harness() -> Any:
    from .private import harness

    return harness


def _classes(specs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "one_worker_at_a_time": bool(spec["exclusive"]),
            "max_in_flight": int(spec["max_in_flight"]),
        }
        for name, spec in sorted(specs.items())
    }


def _status(harness: Any, workspace: Path) -> Mapping[str, Any]:
    "The fleet's classes, their windows and the shifts on file."

    from .private.workload import WINDOWS

    records = sorted((workspace / "project_records").glob("*.json"))
    specs = {
        name: {"exclusive": name == "partner-settlement", "max_in_flight": window}
        for name, window in WINDOWS.items()
    }
    return {
        "summary": "The fleet scheduler and the recorded shifts are available.",
        "measurements": {
            "project_records": [f"project_records/{path.name}" for path in records],
            "job_classes": _classes(specs),
            "canary_node_rank": 10, "ordinary_replica_rank": 0,
        },
        "observed": {},
    }


def _replay(harness: Any, workspace: Path, record_path: Path) -> Mapping[str, Any]:
    'One recorded shift against the scheduler in the tree: raw telemetry.'

    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    payload = {"processes": harness.build_programme(record_id)}
    outcome = harness.PROJECT.invoke(workspace, payload)
    if not outcome.get("ok"):
        return {
            "summary": "The recorded shift could not be run against this workspace.",
            "measurements": {"record_id": record_id},
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    run = harness.Run(outcome, payload["processes"])
    jobs = [
        {
            "job": str(op["job"]), "job_class": str(op["class"]),
            "submitted_account": str(op.get("account", "")),
            "process": str(op["process"]), "submitted_at_operation": int(op["index"]),
            "ran_on": [str(x["worker"]) for x in run.ran(op)],
            "accounts_received": [str(x.get("account", "")) for x in run.ran(op)],
            "times_run": len(run.ran(op)),
        }
        for op in run.submits
    ]
    workers = [
        {
            "worker": worker, "process": process, "link": str(entry["link"]),
            "job_class": str(entry["job_class"]), "rank": int(entry["rank"]),
            "jobs_run": len([
                x for x in run.deliveries
                if str(x["worker"]) == worker and str(x["process"]) == process
            ]),
            "most_jobs_held_at_once": int(run.peak.get((process, worker), 0)),
            "window_the_class_allows": run.window(str(entry["job_class"])),
            "notices_it_received": run.notice_ops(process, worker),
        }
        for (process, worker), entry in sorted(run.claims.items())
    ]
    return {
        "summary": "The recorded shift ran against this workspace.",
        "measurements": {
            "record_id": record_id, "operations": len(run.ops),
            "job_classes": _classes(run.specs), "jobs_submitted": len(jobs),
            "jobs_run_at_least_once": len([job for job in jobs if job["times_run"]]),
        },
        "observed": {
            "jobs": jobs,
            "worker_deliveries": list(run.deliveries),
            "workers": workers,
            "timeline": list(outcome.get("ops", ())),
            "operator_console_at_the_end": outcome.get("consoles", {}),
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


def _rendered(outcome: Mapping[str, Any], action: str) -> TaskToolResult:
    summary = str(outcome.get("summary", "The project tool ran."))
    measurements = dict(outcome.get("measurements", {}) or {})
    observed = dict(outcome.get("observed", {}) or {})
    content = summary
    if measurements:
        content += "\n\nMeasurements:\n" + json.dumps(
            measurements, indent=2, ensure_ascii=False, sort_keys=True
        )
    if observed:
        content += "\n\nWhat the fleet did:\n" + json.dumps(
            observed, indent=2, ensure_ascii=False, sort_keys=True
        )
    return TaskToolResult(
        content=content,
        data={"action": action, "measurements": measurements, "observed": observed},
    )


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))
    harness = _private_harness()
    if action == "status":
        outcome = _status(harness, workspace)
    elif action == "replay":
        outcome = _replay(harness, workspace, _record_path(workspace, arguments))
    else:
        raise ValueError("run_project.action must be status or replay")
    if not isinstance(outcome, Mapping):
        raise TypeError("the fleet scheduler project tool must return a mapping")
    return _rendered(outcome, action)
