'Sandboxed candidate runner for the migration-formatter simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from ddl import protocol

    records: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            module = importlib.reload(importlib.import_module("ddl.formatter"))
            options = protocol.FormatOptions.from_mapping(dict(event.get("options", {})))
            record: dict[str, Any] = {
                "type": "format",
                "index": index,
                "label": str(event.get("label", f"case-{index}")),
                "source": str(event.get("text", "")),
                "options": {"line_width": options.line_width, "indent": options.indent},
            }

            def once(text: str) -> tuple[Mapping[str, Any] | None, str | None]:
                try:
                    report = module.format_statements(text, options)
                    protocol.require_report(report)
                    return (
                        {
                            "formatted": str(report["formatted"]),
                            "statements": [
                                {
                                    "index": row.get("index"),
                                    "status": str(row.get("status")),
                                    "reason": row.get("reason"),
                                }
                                for row in report["statements"]
                            ],
                        },
                        None,
                    )
                except BaseException as exc:
                    return None, _describe(exc)

            first, error = once(record["source"])
            record["first"] = first
            record["error"] = error
            if first is not None:
                repeat, repeat_error = once(record["source"])
                second, second_error = once(first["formatted"])
                record["repeat"] = repeat
                record["repeat_error"] = repeat_error
                record["second"] = second
                record["second_error"] = second_error
            records.append(record)

    return {
        "ok": True,
        "records": records,
        "candidate_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload)
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
