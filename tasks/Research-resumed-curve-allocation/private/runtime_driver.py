'Run one allocation notebook over a batch of sweep windows in the sandbox.'

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
            from analysis import report as notebook
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context") or {}
                ledger = list(request.get("ledger") or ())


                Path("collection_receipts.json").write_text(
                    json.dumps(
                        {"campaign": context.get("campaign"), "entries": ledger}, indent=2
                    ),
                    encoding="utf-8",
                )
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(notebook.next_collection(context, ledger))
                    else:
                        answer = report_view(notebook.analyze(context, ledger))
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
