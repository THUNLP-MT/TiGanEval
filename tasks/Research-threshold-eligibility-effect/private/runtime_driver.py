'Run one campaign notebook over a batch of markets inside the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _rows(name: str, columns: tuple[str, ...], rows) -> None:
    'Write one table the way the weekly job leaves it on disk.'

    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(key, "")) for key in columns))
    Path(name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _publish(context: dict, receipts: list, tables: bool) -> None:
    "Lay one market out on disk the way the campaign's own files sit."

    terms = {key: value for key, value in context.items() if key not in ("register", "recompute")}
    Path("campaign_context.json").write_text(
        json.dumps(terms, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("review_receipts.json").write_text(
        json.dumps({"market": context.get("market"), "lots": receipts}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not tables:
        return
    records = Path("project_records")
    records.mkdir(exist_ok=True)
    _rows(
        "project_records/offer_register.csv",
        ("account_id", "run_week", "run_status", "standing_score", "credits_filed",
         "offer_flag", "offer_date", "first_order_date", "last_observed_date"),
        context.get("register", ()),
    )
    _rows(
        "project_records/recompute_log.csv",
        ("account_id", "refresh_batch", "refresh_date", "score_before"),
        context.get("recompute", ()),
    )


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        contexts = list(payload.get("contexts") or ())
        results = []
        published: int | None = None
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context")
                index = context if isinstance(context, int) else None
                if index is not None:
                    context = contexts[index]
                context = context or {}
                receipts = list(request.get("receipts") or ())


                _publish(context, receipts, index is None or index != published)
                published = index
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_review(context, receipts))
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
