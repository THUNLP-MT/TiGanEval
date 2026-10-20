'Run one planning notebook over a batch of desk states, inside the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:220]}"


def _write_state(context, receipts) -> None:
    'The ordinary file reads show one state of one campaign.'

    Path("desk_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )
    ledger = Path("ledger")
    ledger.mkdir(exist_ok=True)
    header = {"campaign": context.get("campaign"), "record": "settlement ledger"}
    lines = [json.dumps(header, sort_keys=True)]
    lines.extend(json.dumps(entry, sort_keys=True) for entry in receipts)
    (ledger / "receipts.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = dict(payload.get("contexts") or {})
        results = []
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = contexts.get(str(request.get("context")), {})
                receipts = list(request.get("receipts") or ())
                _write_state(context, receipts)
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_collection(context, receipts))
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
