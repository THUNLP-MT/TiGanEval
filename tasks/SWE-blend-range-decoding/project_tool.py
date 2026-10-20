'`run_project` for the catalogue compositor: status and scenario replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import harness

    return harness


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


def _pixel(pixel: Sequence[int]) -> str:
    return ",".join(f"{int(number):>3}" for number in pixel)


def _rows(grid: Any) -> list[str]:
    'One plate as one line per row, so a whole shot fits on a screen.'

    return [" | ".join(_pixel(pixel) for pixel in row) for row in grid]


def _layer_view(harness: Any, layer: Any) -> dict[str, Any]:
    return {
        "layer": layer.name,
        "channels": list(layer.channels),
        "opacity": int(layer.opacity),
        "stored_words": 0 if layer.block is None else len(layer.block),
        "stored_entries_as_grip_pairs": (
            "this layer stores no range work at all"
            if layer.block is None
            else harness.entry_grips(layer.block)
        ),
    }


def _shot_view(harness: Any, document: Any) -> dict[str, Any]:
    return {
        "shot": document.shot,
        "size": f"{document.rows} rows x {document.columns} columns",
        "layers": [_layer_view(harness, layer) for layer in document.layers],
    }


def _scenario_view(harness: Any, path: Path, record_id: str) -> dict[str, Any]:
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(str(case["profile"]), int(case["offset"]))
    protocol = harness.frozen_protocol()
    shots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in program:
        document = protocol.read_document(dict(event["document"]))
        if document.shot in seen:
            continue
        seen.add(document.shot)
        shots.append(_shot_view(harness, document))
    return {
        "record": f"project_records/{path.name}",
        "scene": _record_scene(path).get("scene"),
        "steps": [f"{event['type']} {event['label']}" for event in program],
        "shots": shots,
    }


def _status(workspace: Path) -> Mapping[str, Any]:
    harness = _harness()
    records = sorted((workspace / "project_records").glob("*.json"))
    return {
        "summary": (
            "The catalogue compositor and the scenarios the pipeline replays "
            "before an export goes out."
        ),
        "measurements": {
            "compositor_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "plate").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
        },
        "records": [
            _scenario_view(harness, path, _scenario_id(harness, path)) for path in records
        ],
    }


def _scenario_id(harness: Any, path: Path) -> str:
    record_id = str(_record_scene(path).get("record_id", path.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    return record_id


def _render_view(harness: Any, step: Mapping[str, Any]) -> dict[str, Any]:
    view: dict[str, Any] = {"shot": step.get("label")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    view["plate_this_build_published"] = _rows(step["produced"])
    view["plate_the_design_tool_publishes"] = _rows(step["reference"])
    return view


def _resave_view(harness: Any, step: Mapping[str, Any]) -> dict[str, Any]:
    view: dict[str, Any] = {"shot": step.get("label")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    written = list(step.get("written") or ())
    layers = []
    for index, layer in enumerate(step["document"].layers):
        entry = dict(written[index]) if index < len(written) else {}
        block = entry.get("block")
        layers.append(
            {
                "layer": layer.name,
                "grips_in_the_source_file": (
                    "no range work stored"
                    if layer.block is None
                    else harness.entry_grips(layer.block)
                ),
                "grips_written_back": (
                    "no range work stored"
                    if block is None
                    else _safe_grips(harness, block)
                ),
            }
        )
    view["layers"] = layers
    return view


def _safe_grips(harness: Any, block: Sequence[int]) -> Any:
    try:
        return harness.entry_grips(block)
    except Exception as exc:
        return f"the studio's tool cannot read this back: {exc}"


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    record_id = _scenario_id(harness, specification)
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(str(case["profile"]), int(case["offset"]))
    candidate = harness.PROJECT.invoke(workspace, {"events": list(program)})
    measurements = {"record_id": record_id, "scene": _record_scene(specification).get("scene")}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} scenario could not run this build to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    timeline: list[dict[str, Any]] = []
    for step in harness.read_steps(candidate, program):
        if str(step.get("type")) == "render":
            timeline.append(_render_view(harness, step))
        else:
            timeline.append(_resave_view(harness, step))
    return {
        "summary": f"The {record_id} scenario ran against this build.",
        "measurements": {**measurements, "step_count": len(timeline)},
        "public": {"export_timeline": timeline},
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
        content += _block("Recorded scenarios", outcome["records"])
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
        content += _block("Scenario", outcome["measurements"])
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
