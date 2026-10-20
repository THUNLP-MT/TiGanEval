'Sandboxed runner for one ingress drill against the workspace under review.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _scalar(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def _step_row(step: Any) -> dict[str, Any]:
    rewrite = getattr(step, "rewrite", None)
    return {
        "kind": _scalar(getattr(step, "kind", "?")),
        "key": _scalar(getattr(step, "key", "")),
        "rewrite": (
            None
            if rewrite is None
            else {
                "pattern": _scalar(getattr(rewrite, "pattern", rewrite)),
                "substitution": _scalar(getattr(rewrite, "substitution", "")),
            }
        ),
        "ttl": _scalar(getattr(step, "ttl", None)),
        "path": _scalar(getattr(step, "path", "/")),
        "flags": [_scalar(flag) for flag in tuple(getattr(step, "flags", ()) or ())],
        "stop": bool(getattr(step, "stop", False)),
    }


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    os.environ["EDGE_CONTROLLER_INSTANCE"] = str(
        payload.get("controller_instance", "local-drill")
    )
    from edge import compile as compiler
    from edge import pin as pinner
    from edge import protocol

    serving: dict[str, tuple[Any, ...]] = {}
    pods: dict[str, tuple[str, ...]] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            record: dict[str, Any] = {
                "type": kind,
                "index": index,
                "label": str(event.get("label", f"{kind}-{index}")),
            }
            try:
                if kind == "push":
                    route_spec = dict(event["route"])
                    name = str(route_spec["name"])
                    pods[name] = tuple(str(pod) for pod in route_spec.get("pods", ()))
                    route = protocol.Route(name=name, pods=pods[name])
                    record["route"] = name
                    try:
                        plan = tuple(compiler.compile_route(route, list(event["documents"])))
                        protocol.check_plan(plan)
                    except protocol.EdgeError as exc:
                        record["accepted"] = False
                        record["refusal"] = _describe(exc)
                        record["refused_by"] = (
                            "plane" if isinstance(exc, protocol.PolicyRefused) else "proxy"
                        )
                    else:
                        serving[name] = plan
                        record["accepted"] = True
                        record["plan"] = [_step_row(step) for step in plan]
                    record["serving"] = [_step_row(step) for step in serving.get(name, ())]
                    record["ok"] = True
                elif kind == "traffic":
                    name = str(event["route"])
                    plan = serving.get(name, ())
                    rows: list[dict[str, Any]] = []
                    load: dict[str, int] = {pod: 0 for pod in sorted(pods.get(name, ()))}
                    ring = sorted(pods.get(name, ()))
                    for position, raw_request in enumerate(event["requests"]):
                        request = protocol.build_request(dict(raw_request))
                        if plan:
                            parts = [str(item) for item in pinner.pin_parts(request, plan)]
                            pod = protocol.choose_pod(protocol.fold(parts), pods.get(name, ()))
                        else:


                            parts = []
                            pod = ring[position % len(ring)]
                        load[pod] = load.get(pod, 0) + 1
                        rows.append(
                            {"request": str(request.label), "parts": parts, "pod": str(pod)}
                        )
                    record["route"] = name
                    record["requests"] = rows
                    record["load"] = load
                    record["ok"] = True
                elif kind == "cookies":
                    name = str(event["route"])
                    lines: list[dict[str, Any]] = []
                    for step in serving.get(name, ()):
                        if str(getattr(step, "kind", "")) != "cookie":
                            continue
                        entry = {"key": _scalar(getattr(step, "key", "")), "ttl": _scalar(getattr(step, "ttl", None))}
                        try:
                            entry["line"] = protocol.cookie_line(step)
                        except BaseException as exc:
                            entry["line"] = None
                            entry["refusal"] = _describe(exc)
                        lines.append(entry)
                    record["route"] = name
                    record["cookie_lines"] = lines
                    record["ok"] = True
                else:
                    record["ok"] = False
                    record["error"] = f"unknown drill step: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            records.append(record)

    return {"ok": True, "records": records, "console": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
