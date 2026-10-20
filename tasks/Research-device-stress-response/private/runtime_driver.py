'Run one qualification notebook over a batch of lots inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


RUN_COLUMNS = ("unit_id", "batch", "bench", "cartridge", "reading_bar", "dwell_min", "result")


def _publish(context: dict, receipts: list) -> None:
    'Lay the lot out on disk the way the reporting job leaves it.'

    Path("stress_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("session_receipts.json").write_text(
        json.dumps({"lot": context.get("lot"), "entries": receipts}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with open("burst_runs.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RUN_COLUMNS))
        writer.writeheader()
        for row in context.get("runs", ()):
            writer.writerow({key: row.get(key) for key in RUN_COLUMNS})


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
