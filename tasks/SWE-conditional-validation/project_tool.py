'`run_project` for the order platform: status and record replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tiganeval.taskkit import artifact_hash
from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import harness

    return harness


_VIEWS: Mapping[str, tuple[str, ...]] = {
    "checkout-admissions": ("documents", "admissions"),
    "fulfilment-escalation": ("documents", "writes"),
    "support-dashboard-sweep": ("documents", "reads", "writes"),
    "schema-publication": ("documents", "publication", "queue"),
}

_ADMIT_FIELDS = ("label", "accepted", "refusal", "error", "item", "hand_written_guard_says")
_WRITE_FIELDS = (
    "label", "committed", "refused_by", "refusal", "error", "patch", "caller_condition",
    "condition_handed_to_the_store", "item_afterwards",
)
_READ_FIELDS = ("label", "projection", "stored_item", "view", "error")
_PUBLICATION_FIELDS = (
    "label", "contract", "contract_verdicts", "write_path_verdicts", "carried_document",
    "round_trip", "error",
)
_QUEUE_FIELDS = ("label", "verdict", "error_kind", "error", "document")
_DOCUMENT_FIELDS = ("label", "verdict", "error_kind", "error")

_COLUMNS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "admissions": ("admit", _ADMIT_FIELDS),
    "writes": ("update", _WRITE_FIELDS),
    "reads": ("read", _READ_FIELDS),
    "publication": ("publish", _PUBLICATION_FIELDS),
    "queue": ("review", _QUEUE_FIELDS),
    "documents": ("load", _DOCUMENT_FIELDS),
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
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The order platform and the scenes it replays before a write-path change goes out.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "modules": sorted(
                item.relative_to(workspace).as_posix() for item in (workspace / "orders").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "entity_documents": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "orders" / "entities").glob("*.json")
            ),
        },
        "records": records,
    }


def _step_view(step: Mapping[str, Any], columns: tuple[str, ...]) -> dict[str, Any] | None:
    kind = str(step.get("type"))
    for column in columns:
        wanted, fields = _COLUMNS[column]
        if kind == wanted or (column == "publication" and kind == "rebuild"):
            view = {key: step[key] for key in fields if key in step}
            if not step.get("ok"):
                view["error"] = step.get("error")
            return view
    return None


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(str(case["profile"]), int(case["variant"]))
    candidate = harness.PROJECT.invoke(workspace, {"events": list(program)})
    measurements = {"record_id": record_id, "scene": raw.get("scene")}

    history = {"recorded_reviews": raw["recorded_reviews"]} if "recorded_reviews" in raw else {}
    if not candidate.get("ok"):
        return {
            **history,
            "summary": f"The {record_id} record could not run this build to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    columns = _VIEWS[record_id]
    timeline: list[dict[str, Any]] = []
    for step in harness.read_steps(candidate, program):
        view = _step_view(step, columns)
        if view is not None:
            timeline.append(view)
    return {
        "summary": f"The {record_id} record ran against this build.",
        **history,
        "measurements": {**measurements, "step_count": len(timeline)},
        "public": {"replay_timeline": timeline},
    }


def _block(title: str, value: Any) -> str:
    return f"\n\n{title}:\n" + json.dumps(
        value, indent=2, ensure_ascii=False, sort_keys=True, default=str
    )


def run_project(arguments: Mapping[str, Any], context: Any) -> TaskToolResult:
    workspace = Path(context.workspace).resolve()
    action = str(arguments.get("action", "status"))

    if action == "status":
        outcome = _status(workspace)
        content = str(outcome["summary"])
        content += _block("Workspace", outcome["measurements"])
        content += _block("Records", outcome["records"])
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
        content += _block("Record", outcome["measurements"])
        if "recorded_reviews" in outcome:
            content += _block("Recorded publication reviews (before this build)", outcome["recorded_reviews"])
        content += _block("What this build did", outcome["public"])
        return TaskToolResult(
            content=content,
            data={
                "action": "replay",
                "record": path.relative_to(workspace).as_posix(),
                "measurements": dict(outcome["measurements"]),
                "public": dict(outcome["public"]),
                **({"recorded_reviews": outcome["recorded_reviews"]} if "recorded_reviews" in outcome else {}),
            },
        )

    raise ValueError("run_project.action must be status or replay")
