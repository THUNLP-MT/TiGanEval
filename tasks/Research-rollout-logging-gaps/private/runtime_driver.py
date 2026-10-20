'Run one readout notebook over a batch of readouts inside the sandbox.'

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
            from protocol import plan_view, readout_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context") or {}
                receipts = list(request.get("receipts") or ())


                Path("readout_context.json").write_text(
                    json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
                )
                Path("audit_receipts.json").write_text(
                    json.dumps(
                        {"readout": context.get("readout"), "entries": receipts},
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_collection(context, receipts))
                    else:
                        answer = readout_view(analysis.analyze(context, receipts))
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
