'`run_project` for the telemetry uplink: status and drill replay.'

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
    "depot-slow-drain": ("slots", "counters", "window"),
    "field-swap-teardown": ("teardown", "counters", "refusals"),
    "nightly-log-upload": ("traffic", "counters", "refusals"),
    "tuesday-link-silence": ("slots", "isolation"),
}

_PRIORITY_NAMES = {0: "bulk", 1: "normal", 2: "high"}


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
    from .private.workload import LINK

    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((workspace / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The station's uplink and the drills the team replays before a change goes out.",
        "measurements": {
            "workspace_hash": artifact_hash(workspace),
            "link_files": sorted(
                item.relative_to(workspace).as_posix()
                for item in (workspace / "link").glob("*.py")
            ),
            "editable_files": list(harness.EDITABLE_FILES),
            "link_settings_every_drill_uses": dict(LINK),
        },
        "records": records,
    }


def _rows(step: Mapping[str, Any], fields: Sequence[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in step.get("streams") or ():
        row = dict(raw)
        entry: dict[str, Any] = {"stream": row.get("stream"), "stream_id": row.get("id")}
        for name in fields:
            if name == "priority":
                entry["priority"] = _PRIORITY_NAMES.get(int(row.get("priority", 1)), "normal")
            elif name == "drains":
                entry["the_units_consumer_takes_bytes"] = bool(row.get("drains"))
            else:
                entry[name] = row.get(name)
        out.append(entry)
    return out


def _report_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    view: dict[str, Any] = {
        "link_report": step.get("label"),
        "streams_still_on_the_link": step.get("open_streams"),
    }
    if "counters" in columns:
        view["the_six_counters_this_build_kept"] = step.get("counters")
        view["the_same_six_read_off_the_radio"] = step.get("measured")
    if "traffic" in columns:
        view["per_stream"] = _rows(
            step,
            ("handed_over", "put_on_the_radio", "arrived_at_the_unit", "arrived_in_order",
             "sent_by_the_unit", "read_here", "read_in_order"),
        )
    if "window" in columns:
        view["room_the_unit_has_per_stream"] = step.get("send_window")
        view["per_stream"] = _rows(
            step,
            ("put_on_the_radio", "taken_by_the_units_consumer",
             "peak_standing_at_the_unit", "owed"),
        )
    if "isolation" in columns:
        view["per_stream"] = _rows(
            step, ("priority", "drains", "handed_over", "put_on_the_radio", "owed")
        )
    if "teardown" in columns:
        view["writes_handed_to_the_link"] = step.get("tickets")
        view["per_stream"] = _rows(step, ("handed_over", "sent_by_the_unit", "read_here"))
    if "refusals" in columns:
        view["frames_the_unit_refused"] = step.get("frames_the_unit_refused")
        view["streams_the_unit_opened_itself"] = step.get("streams_the_unit_opened")
    return view


def _step_view(step: Mapping[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    kind = str(step.get("type"))
    label = step.get("label")
    if not step.get("ok"):
        return {"step": label, "error": step.get("error")}
    if kind == "session":
        return {"link_up": step.get("config")}
    if kind == "open":
        return {"the_station_opened": step.get("stream"), "stream_id": step.get("id")}
    if kind == "peer_open":
        return {"the_unit_opened": step.get("stream"), "stream_id": step.get("id")}
    if kind == "accept":
        return {"the_station_accepted": step.get("stream"), "stream_id": step.get("id")}
    if kind == "write":
        return {"handed_to": step.get("stream"), "bytes_handed_over_so_far": step.get("handed_over")}
    if kind == "peer_push":
        return {"the_unit_sent_on": step.get("stream"), "bytes": step.get("size")}
    if kind == "pump":
        view: dict[str, Any] = {
            "radio_slot": label,
            "bytes_the_slot_allows": step.get("budget"),
            "bytes_put_on_the_radio": step.get("wire_bytes"),
        }
        if "slots" in columns:
            view["payload_put_on_the_radio"] = step.get("delivered")
            view["frames_in_this_slot"] = step.get("frames")
        else:
            view["frames_in_this_slot"] = len(step.get("frames") or ())
        return view
    if kind == "drain":
        return {"the_units_consumer_took_from": step.get("stream"), "bytes": step.get("took")}
    if kind == "read":
        return {"the_station_read": step.get("stream"), "bytes": step.get("read_bytes"),
                "after_this_end_closed_it": step.get("after_close")}
    if kind == "close_stream":
        return {"the_station_closed": step.get("stream")}
    if kind == "peer_close":
        return {"the_unit_closed": step.get("stream")}
    if kind == "present":
        return {"stream": step.get("stream"), "still_on_the_link": step.get("present"),
                "bytes_it_holds_unread": step.get("unread_here")}
    if kind == "probe":
        return {"tried_after_closing": step.get("kind"), "stream": step.get("stream"),
                "what_it_raised": step.get("raised")}
    if kind == "close_session":
        return {"closed_the_link": label, "the_radio_was_refusing_bytes": step.get("refusing"),
                "what_it_raised": step.get("raised")}
    if kind == "report":
        return _report_view(step, columns)
    return {"step": label}


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
    measurements = {"record_id": record_id, "scene": raw.get("scene")}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} drill could not run this station to the end.",
            "measurements": measurements,
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    columns = _VIEWS[record_id]
    timeline = [
        _step_view(step, columns) for step in harness.read_steps(candidate, program)
    ]
    return {
        "summary": f"The {record_id} drill ran against this station.",
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
        content += _block("What this station did", outcome["public"])
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
