'Sandboxed runner for the estate policy audit.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _finding(item: Any) -> dict[str, Any]:
    return {
        "rule": str(getattr(item, "rule_id", "")),
        "line": int(getattr(item, "line", 0)),
        "unit": int(getattr(item, "unit", -1)),
        "path": str(getattr(item, "path", "")),
        "value": str(getattr(item, "value", "")),
    }


def _counters(report: Any) -> dict[str, int]:
    counters = getattr(report, "counters", None)
    return {
        "reported": int(getattr(counters, "reported", -1)),
        "blanket": int(getattr(counters, "blanket", -1)),
        "by_rule": int(getattr(counters, "by_rule", -1)),
    }


def _text(spec: Mapping[str, Any]) -> str:
    raw = spec.get("text")
    if isinstance(raw, str):
        return raw
    return Path(str(spec["file"])).read_text(encoding="utf-8")


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from audit import contract

    module = importlib.reload(importlib.import_module("audit.waivers"))
    rows: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("runs", ())):
            spec = dict(raw)
            row: dict[str, Any] = {
                "index": index,
                "phase": str(spec.get("phase", "")),
                "document": str(spec.get("document", f"document-{index}")),
                "profile": str(spec.get("profile", "release")),
                "ignore_waivers": bool(spec.get("ignore_waivers", False)),
            }
            try:
                document = contract.parse_document(_text(spec), row["document"])
                profile = contract.Profile(
                    name=row["profile"], ignore_waivers=row["ignore_waivers"]
                )
                row["units"] = [
                    {"index": unit.index, "path": unit.path,
                     "lines": [unit.start_line, unit.end_line], "depth": unit.depth}
                    for unit in document.units
                ]
                row["baseline"] = [
                    _finding(item) for item in contract.baseline_findings(document, profile)
                ]
            except BaseException as exc:
                row["error"] = _describe(exc)
                rows.append(row)
                continue
            try:
                report = module.build_report(document, profile)
                row["findings"] = [_finding(item) for item in getattr(report, "findings", ())]
                row["counters"] = _counters(report)
            except BaseException as exc:
                row["error"] = _describe(exc)
            rows.append(row)

    return {"ok": True, "runs": rows, "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
