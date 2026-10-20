'Run one review notebook over a batch of desks and ledgers inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


EXPORTS = (
    ("intake_last30.csv", "intake",
     ("ticket_id", "arrived_on", "channel", "product_line", "segment", "priority",
      "predicted_queue")),
    ("label_pool.csv", "pool",
     ("item_id", "channel", "product_line", "segment", "priority", "predicted_queue",
      "model_margin")),
    ("adjudication_round.csv", "adjudication",
     ("item_id", "settled_on", "settled_queue", "panel")),
)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _write_exports(context, ledger) -> None:
    "Put this desk's own exports on disk, where the desk's files live."

    for name, key, fields in EXPORTS:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in context.get(key, ()):
            writer.writerow({field: row.get(field, "") for field in fields})
        Path(name).write_text(buffer.getvalue(), encoding="utf-8")
    Path("label_ledger.jsonl").write_text(
        "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n"
                for entry in ledger),
        encoding="utf-8",
    )


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = payload.get("contexts") or {}
        results = []
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = dict(contexts.get(str(request.get("context"))) or {})
                ledger = list(request.get("ledger") or ())
                _write_exports(context, ledger)
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_collection(context, ledger))
                    else:
                        answer = report_view(analysis.analyze(context, ledger))
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
