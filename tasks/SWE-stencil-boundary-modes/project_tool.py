'`run_project` for the imaging batch: status and recorded-night replay.'

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
    "coast-blur-rerender": (),
    "globe-swath-nightly": (),
    "quarantine-review": ("frame",),
    "terrace-mirror-pass": ("frame",),
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
    contract = harness.frozen_contract()
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The tile rendering package and the nights the batch box keeps.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "package_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "tilekit").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "boundary_vocabulary": list(contract.MODES),
            "kernel_library": sorted(contract.KERNELS),
            "cell_types": list(contract.DTYPES),
        },
        "records": records,
    }


def _tile(rows: Any) -> Any:
    'One raster as the console shows it: one line per row, columns aligned.'

    if not isinstance(rows, (list, tuple)) or not rows:
        return rows
    width = max((len(str(cell)) for row in rows for cell in row), default=1)
    return [" ".join(str(cell).rjust(width) for cell in row) for row in rows]


def _pass_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    harness = _harness()
    event = dict(step.get("event") or {})
    reference = dict(step.get("reference") or {})
    view: dict[str, Any] = {
        "pass": step.get("label"),
        "job_config": event.get("job"),
        "operand_shapes": {
            name: f"{len(doc['cells'])}x{len(doc['cells'][0])}"
            for name, doc in dict(event.get("operands") or {}).items()
        },
        "operands": {
            name: _tile(doc["cells"]) for name, doc in dict(event.get("operands") or {}).items()
        },
    }
    if event.get("note"):
        view["operator_note"] = event["note"]
    if not step.get("ok"):
        view["error"] = step.get("error")
        view["write_log"] = harness.write_counts(step)
    else:
        view["tile_this_build_produced"] = _tile(step.get("cells"))
        view["output_cell_type"] = step.get("dtype")
        view["write_log"] = harness.write_counts(step)
    if event.get("legacy") and "cells" in reference:
        view["tile_the_legacy_renderer_kept"] = _tile(reference["cells"])
    if "frame" in columns and event.get("frame"):
        view["frame_buffer_before"] = _tile(event["frame"]["cells"])
        view["frame_buffer_after"] = _tile(step.get("frame_after"))
    return view


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(
        str(case["profile"]), int(case["mark"]), int(case["scale"])
    )
    candidate = harness.PROJECT.invoke(workspace, {"passes": list(program)})
    measurements = {"record_id": record_id, "scene": raw.get("scene")}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} night could not be run to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    columns = _VIEWS[record_id]
    timeline = [
        _pass_view(step, columns) for step in harness.read_steps(candidate, program)
    ]
    return {
        "summary": f"The {record_id} night ran against this build.",
        "measurements": {**measurements, "pass_count": len(timeline)},
        "public": {"night": timeline},
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
        content += _block("Recorded nights", outcome["records"])
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
        content += _block("Night", outcome["measurements"])
        content += _block("What this build did", outcome["public"])
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
