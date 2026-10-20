"Sandboxed runner for the delivery portal's request surface."

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


_RAN: list[dict[str, Any]] = []
_WATCHING = False


def _watch_the_meter(protocol: Any) -> None:
    'Copy every meter line into `_RAN` as it is written. Installed once.'

    global _WATCHING
    if _WATCHING:
        return
    written = protocol.Meter.record

    def record(self: Any, endpoint: Any, request: Any) -> None:
        written(self, endpoint, request)
        _RAN.append({
            "label": str(getattr(request, "label", "")),
            "operation": str(getattr(endpoint, "name", "")),
            "units": int(getattr(endpoint, "cost", 0)),
        })

    protocol.Meter.record = record
    _WATCHING = True


def _fresh_surface() -> Any:
    'Load the delivered surface again for the next stretch of traffic.'

    stale = [
        item for item in list(sys.modules)
        if item.startswith("surface.") and item != "surface.protocol"
    ]
    for name in stale:
        sys.modules.pop(name, None)
        holder, _, child = name.rpartition(".")
        package = sys.modules.get(holder)


        if package is not None and hasattr(package, child):
            delattr(package, child)
    return importlib.import_module("surface.routing")


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _assemble(assembly: Mapping[str, Any], routing: Any, protocol: Any) -> Any:
    'Build one surface exactly in the order the steps are written.'

    parts: dict[str, Any] = {}
    for step in assembly.get("steps", ()):
        op = str(step["op"])
        settings = dict(step.get("settings") or {})
        if op == "service":
            parts["app"] = routing.Service(**settings)
        elif op == "router":
            parts[str(step["name"])] = routing.Router(**settings)
        elif op == "route":
            parts[str(step["router"])].add_route(
                str(step["path"]), str(step["method"]),
                protocol.make_handler(dict(step.get("answers") or {})),
                name=str(step.get("name", "")), summary=str(step.get("summary", "")),
                guard=str(step.get("guard", "")), cost=int(step.get("cost", 1)),
                params=dict(step.get("params") or {}), **settings,
            )
        elif op == "include":
            parts[str(step.get("into", "app"))].include(
                parts[str(step["router"])], prefix=str(step["prefix"]), **settings
            )
        else:
            raise ValueError(f"unknown assembly step: {op}")
    return parts["app"]


def _endpoint_rows(service: Any) -> list[dict[str, Any]]:
    listing = getattr(service, "endpoints", None)
    if listing is None:
        return []
    return [
        {
            "path": str(item.path), "local_path": str(getattr(item, "local_path", "")),
            "method": str(item.method), "operation": str(item.name),
            "summary": str(item.summary), "cost": int(item.cost),
            "published": bool(item.published), "generated": bool(item.generated),
        }
        for item in listing()
    ]


def _answer(response: Any) -> dict[str, Any]:
    if response is None:
        return {"answered": False, "status": None, "headers": {}, "body": "", "body_length": 0}
    body = str(getattr(response, "body", ""))
    headers = {str(k).lower(): str(v) for k, v in dict(getattr(response, "headers", {})).items()}
    return {
        "answered": True, "status": int(getattr(response, "status", 0)), "headers": headers,
        "body": body[:2000], "body_length": len(body),
    }


def _usage(service: Any) -> Any:
    report = getattr(service, "usage_report", None)
    if report is None:
        return None
    value = report()
    return {str(path): dict(row) for path, row in dict(value).items()}


def _run_assembly(assembly: Mapping[str, Any], routing: Any, protocol: Any) -> dict[str, Any]:
    protocol.METER.reset()
    _RAN.clear()
    service = _assemble(assembly, routing, protocol)
    rows: list[dict[str, Any]] = []
    for ask in assembly.get("requests", ()):
        request = protocol.Request(
            method=str(ask["method"]), path=str(ask["path"]),
            token=ask.get("token"), label=str(ask["label"]), kind=str(ask.get("kind", "request")),
        )
        seen = len(_RAN)
        row: dict[str, Any] = {
            "label": request.label, "method": request.method, "path": request.path,
            "kind": request.kind,
        }
        row.update(_answer(service.handle(request)))
        spent = _RAN[seen:]
        row["work_units"] = sum(int(entry["units"]) for entry in spent)
        row["operations_run"] = [str(entry["operation"]) for entry in spent]
        rows.append(row)
    result = {
        "name": str(assembly["name"]), "requests": rows,
        "endpoints": _endpoint_rows(service), "usage": _usage(service),
        "usage_after_mutation": None,
    }
    if assembly.get("snapshot_probe"):
        held = _usage(service)
        loose = getattr(service, "usage_report", lambda: {})()
        try:
            for value in dict(loose).values():
                value["head_hits"] = int(value.get("head_hits", 0)) + 500
            loose["/mutation-check"] = {"head_hits": 7, "options_hits": 7}
        except BaseException:
            pass
        result["usage"] = held
        result["usage_after_mutation"] = _usage(service)
    return result


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from surface import protocol

    _watch_the_meter(protocol)
    captured = io.StringIO()
    assemblies: list[dict[str, Any]] = []
    with redirect_stdout(captured):
        for assembly in payload.get("assemblies", ()):
            try:
                assemblies.append(_run_assembly(assembly, _fresh_surface(), protocol))
            except BaseException as exc:
                return {
                    "ok": False, "assemblies": assemblies,
                    "error": f"{assembly.get('name')}: {_describe(exc)}",
                    "stdout": captured.getvalue()[-2000:],
                }
    return {"ok": True, "assemblies": assemblies, "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
