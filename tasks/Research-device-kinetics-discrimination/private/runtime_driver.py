'Run one soak notebook over a batch of campaigns inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


TRACE_COLUMNS = (
    "module_id",
    "lot",
    "rack",
    "drive_a",
    "sample_index",
    "logged_at",
    "elapsed_h",
    "output_mw",
)
MODULE_COLUMNS = ("module_id", "lot", "rack", "drive_a", "incoming_mw", "started_on")


def _table(path: str, columns, rows) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


_PUBLISHED: dict[str, int] = {}


def _publish(context: dict, receipts: list) -> None:
    'Lay the campaign out on disk the way the reporting job leaves it.'

    if _PUBLISHED.get("campaign") != id(context):
        _PUBLISHED["campaign"] = id(context)
        Path("soak_context.json").write_text(
            json.dumps(context, sort_keys=True), encoding="utf-8"
        )
        _table("project_records/soak_traces.csv", TRACE_COLUMNS, context.get("traces", ()))
        _table("module_index.csv", MODULE_COLUMNS, context.get("modules", ()))
    Path("soak_receipts.json").write_text(
        json.dumps({"campaign": context.get("campaign"), "entries": receipts}, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = list(payload.get("contexts") or ())
        results = []
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context")
                if isinstance(context, int):
                    context = contexts[context]
                context = context or {}
                receipts = list(request.get("receipts") or ())


                _publish(context, receipts)
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_block(context, receipts))
                    else:
                        answer = report_view(analysis.analyze(context, receipts))
                    json.dumps(answer, allow_nan=False)
                    results.append({"ok": True, "answer": answer})
                except BaseException as exc:
                    results.append({"ok": False, "error": _describe(exc)})
        result = {"ok": True, "results": results, "stdout": captured.getvalue()[-2000:]}
        json.dumps(result, allow_nan=False)
    except BaseException as exc:
        result = {"ok": False, "error": _describe(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
