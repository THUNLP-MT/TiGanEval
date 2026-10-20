'`run_project` for the decision service: status and drill replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import artifact_hash
from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import harness

    return harness


_VIEWS: Mapping[str, tuple[str, ...]] = {
    "authz-latency-review": ("decision", "rows"),
    "role-reference-fanout": ("decision", "traffic", "rows"),
    "peak-hour-replay": ("parity", "totals", "report_when_off"),
    "nightly-rollup": ("decision", "totals"),
}


_NIGHTLY_FIELDS = (
    "label", "type", "ok", "error", "rows", "source", "totals", "rates",
    "left_before", "right_before", "merged", "left_after", "right_after",
    "what_the_nightly_job_did",
)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
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


def _status(workspace: Path) -> Mapping[str, Any]:
    harness = _harness()
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The decision service and the drills the platform replays before a change goes out.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "policy_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "policy").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "work_unit_budget_per_decision": harness.frozen_protocol().DEFAULT_BUDGET,
        },
        "records": records,
    }


def _decision_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    harness = _harness()
    plain, profiled = dict(step.get("plain") or {}), dict(step.get("profiled") or {})
    truth = dict(step.get("truth") or {})
    view: dict[str, Any] = {"request": step.get("label")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    if "decision" in columns:
        view["decision"] = profiled.get("outcome")
    if "parity" in columns:
        view["decision_without_report"] = plain.get("outcome")
        view["decision_with_report"] = profiled.get("outcome")
        view["work_units_without_report"] = plain.get("work")
        view["work_units_with_report"] = profiled.get("work")
        view["work_unit_budget"] = harness.frozen_protocol().DEFAULT_BUDGET
        view["expressions_without_report"] = list(plain.get("ops") or ())
        view["expressions_with_report"] = list(profiled.get("ops") or ())
    if "totals" in columns:
        view["report_totals"] = harness.row_totals(profiled.get("rows"))
        view["report_row_count"] = len(dict(profiled.get("rows") or {}))
    if "traffic" in columns:
        view["bodies_that_ran"] = dict(truth.get("entries") or {})
        view["rule_references_resolved"] = dict(truth.get("asks") or {})
    if "rows" in columns:
        view["report_rows_this_build_produced"] = profiled.get("rows")
    if "report_when_off" in columns:
        view["report_on_the_unprofiled_decision"] = plain.get("rows")
    return view


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(
        str(case["profile"]), int(case["seed"]), int(case["scale"])
    )
    candidate = harness.PROJECT.invoke(workspace, {"events": list(program)})
    measurements = {
        "record_id": record_id,
        "scene": raw.get("scene"),
        "work_unit_budget_per_decision": harness.frozen_protocol().DEFAULT_BUDGET,
    }
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} drill could not run this service to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    columns = _VIEWS[record_id]
    timeline: list[dict[str, Any]] = []
    for step in harness.read_steps(candidate, program):
        kind = str(step.get("type"))
        if kind == "decide":
            timeline.append(_decision_view(step, columns))
        elif kind == "load":
            timeline.append(
                {
                    "loaded_bundle": step.get("label"),
                    "definitions_in_source_order": step.get("definitions"),
                }
            )
        else:
            timeline.append({k: v for k, v in step.items() if k in _NIGHTLY_FIELDS})
    return {
        "summary": f"The {record_id} drill ran against this service.",
        "measurements": {**measurements, "step_count": len(timeline)},
        "public": {"drill_timeline": timeline},
    }


def _block(title: str, value: Any) -> str:
    return f"\n\n{title}:\n" + json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))

    if action == "status":
        outcome = _status(workspace)
        content = str(outcome["summary"])
        content += _block("Workspace", outcome["measurements"])
        content += _block("Drills", outcome["records"])
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
        outcome = _replay(workspace, path)
        content = str(outcome["summary"])
        content += _block("Drill", outcome["measurements"])
        content += _block("What this service did", outcome["public"])
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
