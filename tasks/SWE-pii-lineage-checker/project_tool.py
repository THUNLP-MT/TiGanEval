'`run_project` for the lineage checker: status and drill replay.'

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
    "audit-baseline": ("existing",),
    "checkout-order-drill": ("order",),
    "extract-step-regression": ("tags",),
    "field-review": ("reviewed", "rows"),
}


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
    protocol = harness.frozen_protocol()
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The lineage checker and the drills security replays before a release.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "lineage_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "lineage").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "personal_fields": sorted(protocol.PERSONAL_FIELDS),
            "masking_helpers": sorted(protocol.MASKS),
            "export_sinks": {
                name: sink.check for name, sink in sorted(protocol.EXPORT_SINKS.items())
            },
            "check_the_audit_already_had": protocol.BASELINE_CHECK,
            "expression_nodes_one_pass_may_read": protocol.STEP_BUDGET,
        },
        "records": records,
    }


def _step_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    harness = _harness()
    view: dict[str, Any] = {
        "scan": step.get("label"),
        "modules_handed_over": len(dict(step.get("modules") or {})),
    }
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    view["report_row_count"] = len(step["rows"])
    if not step.get("report_shape_ok"):
        view["report_gate_error"] = step.get("report_shape_error")
    if "existing" in columns:
        view.update(harness.existing_rows_view(step))
    if "reviewed" in columns:
        view["how_many_exports_the_office_marked"] = harness.reviewer_marks(step)
    if "rows" in columns:
        view["report_rows_this_build_produced"] = harness.report_rows(step)
    if "tags" in columns:
        view["exports_this_build_flagged"] = harness.flagged_tags(step)
    if "order" in columns:
        view["module_order_handed_over"] = step.get("module_order")
        view["report_in_the_order_this_build_returned_it"] = harness.report_in_order(step)
    return view


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(str(case["profile"]), int(case["number"]))
    candidate = harness.PROJECT.invoke(workspace, {"events": list(program)})
    measurements = {"record_id": record_id, "scene": raw.get("scene")}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} drill could not read this pipeline to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    columns = _VIEWS[record_id]
    timeline = [_step_view(step, columns) for step in harness.read_steps(candidate, program)]
    return {
        "summary": f"The {record_id} drill ran against this checker.",
        "measurements": {**measurements, "scan_count": len(timeline)},
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
        content += _block("What this checker did", outcome["public"])
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
