'`run_project` for the ingress control plane: status and drill replay.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.tools import TaskToolResult


def _harness() -> Any:
    from .private import harness

    return harness


_VIEWS: Mapping[str, tuple[str, ...]] = {
    "checkout-session-drops": ("plan", "cookies", "parts", "pods", "load"),
    "controller-restart-resync": ("plan", "pods"),
    "guest-checkout-surge": ("plan", "cookies", "parts", "load"),
    "reporting-export-window": ("plan", "load"),
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
    policies = []
    for path in sorted((workspace / "config" / "policies").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        policies.append(
            {
                "file": path.relative_to(workspace).as_posix(),
                "scope": document.get("scope"),
                "routes": document.get("routes"),
            }
        )
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The ingress control plane and the drills the platform replays before a push.",
        "measurements": {
            "edge_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "edge").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "routes_and_pods": {
                name: list(pods) for name, pods in sorted(harness.PODS.items())
            },
            "kind_order_the_proxy_requires": list(
                harness.frozen_protocol().CANONICAL_KINDS
            ),
            "committed_policies": policies,
        },
        "records": records,
    }


def _push_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    harness = _harness()
    view: dict[str, Any] = {"push": step.get("label"), "route": step.get("route")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    view["proxy_took_the_plan"] = bool(step.get("accepted"))
    if not step.get("accepted"):


        refused = "plane_refused_the_policy" if step.get("refused_by") == "plane" else "proxy_refused"
        view[refused] = step.get("refusal")
    if "plan" in columns:
        view["plan_the_route_now_serves"] = harness.plan_view(step.get("serving") or ())
    return view


def _traffic_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    view: dict[str, Any] = {"traffic": step.get("label"), "route": step.get("route")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    rows = [dict(row) for row in step.get("requests") or ()]
    if "load" in columns:
        view["requests_per_pod"] = dict(step.get("load") or {})
    if "pods" in columns or "parts" in columns:
        view["where_each_request_landed"] = [
            {
                "request": row.get("request"),
                "pod": row.get("pod"),
                **({"parts_folded": row.get("parts")} if "parts" in columns else {}),
            }
            for row in rows
        ]
    return view


def _cookies_view(step: Mapping[str, Any]) -> dict[str, Any]:
    view: dict[str, Any] = {"cookies": step.get("label"), "route": step.get("route")}
    if not step.get("ok"):
        return {**view, "error": step.get("error")}
    view["set_cookie_lines"] = [dict(row) for row in step.get("cookie_lines") or ()]
    return view


def _replay(workspace: Path, specification: Path) -> Mapping[str, Any]:
    harness = _harness()
    raw = _record_scene(specification)
    record_id = str(raw.get("record_id", specification.stem))
    if record_id not in harness.PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = harness.PUBLIC_RECORDS[record_id]
    program = harness.build_program(str(case["profile"]), int(case["scale"]))
    candidate = harness.PROJECT.invoke(workspace, {"events": list(program)})
    measurements = {"record_id": record_id, "scene": raw.get("scene")}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} drill could not run this control plane to the end.",
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
        if kind == "push":
            timeline.append(_push_view(step, columns))
        elif kind == "traffic":
            timeline.append(_traffic_view(step, columns))
        elif kind == "cookies":
            timeline.append(_cookies_view(step))
    return {
        "summary": f"The {record_id} drill ran against this control plane.",
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
        content += _block("What the edge did", outcome["public"])
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
