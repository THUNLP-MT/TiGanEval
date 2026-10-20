'Run one watch notebook over a batch of watches inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _publish(context: dict, ledger: list) -> None:
    'Lay the watch out on disk the way the weekly job leaves it.'

    Path("watch_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("collection_ledger.json").write_text(
        json.dumps({"watch": context.get("watch"), "entries": ledger}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    Path("ingestion_receipts.json").write_text(
        json.dumps({"watch": context.get("watch"), "days": context.get("ingestion", [])},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    Path("base_audience.json").write_text(
        json.dumps(context.get("base_audience", {}), indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_csv("enrolment_snapshot.csv", ("day", "arm", "sessions_28d", "users"),
               context.get("enrolment", ()))
    _write_csv(
        "reorder_publications.csv",
        ("enrolled_on", "arm", "sessions_28d", "published_on", "reorders"),
        context.get("reorders", ()),
    )


def _write_csv(name: str, columns: tuple[str, ...], rows) -> None:
    with open(name, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


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
                ledger = list(request.get("ledger") or ())


                _publish(context, ledger)
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_collection(context, ledger))
                    elif request.get("kind") == "decision_boundary":
                        first = report_view(analysis.analyze(context, ledger))
                        interval = first.get("lift_interval_points")
                        line = (
                            float(interval[0])
                            if isinstance(interval, list)
                            and len(interval) == 2
                            and isinstance(interval[0], (int, float))
                            and not isinstance(interval[0], bool)
                            else None
                        )
                        if line is None:
                            answer = {"line_points": None, "report": first}
                        else:
                            probe_context = json.loads(json.dumps(context))
                            probe_context["ship_line_points"] = line
                            _publish(probe_context, ledger)
                            answer = {
                                "line_points": line,
                                "report": report_view(
                                    analysis.analyze(probe_context, ledger)
                                ),
                            }
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
