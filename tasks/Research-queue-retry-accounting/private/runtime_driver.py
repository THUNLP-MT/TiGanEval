'Run one delivered notebook over a batch of reviews inside the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _publish(context: dict) -> None:
    'Lay the export files out the way the platform share drive holds them.'

    body = {key: value for key, value in context.items()
            if key not in ("rollup", "pool_counters")}
    Path("service_context.json").write_text(
        json.dumps(body, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("request_rollup.json").write_text(
        json.dumps({"review": context.get("review"), "rows": context.get("rollup", [])},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    Path("edge_pool_counters.json").write_text(
        json.dumps({"review": context.get("review"), "rows": context.get("pool_counters", [])},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = dict(payload.get("contexts") or {})
        results = []
        published = None
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = contexts.get(str(request.get("context")), {})
                receipts = list(request.get("receipts") or ())


                if published != request.get("context"):
                    _publish(context)
                    published = request.get("context")
                Path("trace_receipts.json").write_text(
                    json.dumps({"review": context.get("review"), "entries": receipts},
                               indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_trace(context, receipts))
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
