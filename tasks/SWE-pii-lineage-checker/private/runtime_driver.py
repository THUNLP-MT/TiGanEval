'Sandboxed runner for one lineage drill: scan a module set, keep the report.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _row(value: Any) -> dict[str, Any]:
    def field(name: str, fallback: Any) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, fallback)
        return getattr(value, name, fallback)

    return {
        "module": str(field("module", "")),
        "line": int(field("line", 0) or 0),
        "col": int(field("col", 0) or 0),
        "check": str(field("check", "")),
        "dataset": str(field("dataset", "") or ""),
    }


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from lineage import protocol
    from lineage import tracer

    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            record: dict[str, Any] = {
                "type": str(event.get("type", "")),
                "index": index,
                "label": str(event.get("label", f"step-{index}")),
            }
            try:
                if record["type"] != "scan":
                    raise ValueError(f"unknown drill step: {record['type']}")
                modules = protocol.ModuleSet(
                    dict(event.get("modules") or {}), event.get("order")
                )


                report = list(tracer.scan(modules))
                try:
                    protocol.require_report(report)
                    shape, shape_error = True, ""
                except BaseException as exc:
                    shape, shape_error = False, _describe(exc)
                rows = [_row(item) for item in report]
                record["ok"] = True
                record["rows"] = rows
                record["module_order"] = list(modules.names())
                record["nodes_read"] = int(protocol.nodes_read())
                record["report_shape_ok"] = shape
                record["report_shape_error"] = shape_error
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
