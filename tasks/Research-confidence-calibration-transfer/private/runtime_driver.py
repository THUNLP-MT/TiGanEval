'Run one auto-clear readout notebook over a batch of queues in the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        results = []
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("states", ()):
                state = dict(raw)
                context = state.get("context") or {}


                Path(str(context.get("intake_log_file") or "intake_log.csv")).write_text(
                    str(state.get("log_csv") or ""), encoding="utf-8"
                )
                for item in state.get("requests", ()):
                    request = dict(item)
                    receipts = list(request.get("receipts") or ())
                    Path("audit_receipts.json").write_text(
                        json.dumps(
                            {"queue": context.get("queue"), "batches": receipts}, indent=2
                        ),
                        encoding="utf-8",
                    )
                    try:
                        if request.get("kind") == "plan":
                            answer = plan_view(analysis.next_batch(context, receipts))
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
