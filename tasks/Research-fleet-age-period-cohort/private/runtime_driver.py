'Run one fleet notebook over a batch of regions inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _write_csv(name: str, columns: tuple[str, ...], rows) -> None:
    with open(name, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


def _publish_receipts(context: dict, receipts: list) -> None:
    Path("audit_receipts.json").write_text(
        json.dumps({"region": context.get("region"), "entries": receipts},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _publish(context: dict, receipts: list) -> None:
    'Lay the region out on disk the way the fleet system leaves it.'

    _publish_receipts(context, receipts)
    _write_csv(
        "van_register.csv",
        ("van_id", "build_month", "allocated_date", "in_service_date", "depot",
         "transfer_date", "transfer_depot", "off_fleet_date", "lease_ref"),
        context.get("vans", ()),
    )
    _write_csv(
        "fault_log.csv",
        ("fault_id", "van_id", "depot", "raised_date", "walkaround_ref", "fault_code"),
        context.get("faults", ()),
    )
    _write_csv(
        "depot_roster.csv",
        ("month", "build_month", "depot", "vans_on_the_books"),
        context.get("roster", ()),
    )
    _write_csv(
        "build_sheets.csv",
        ("build_month", "body_spec", "lots"),
        [
            {"build_month": row["build_month"], "body_spec": row["body_spec"],
             "lots": " ".join(row["lots"])}
            for row in context.get("build_sheets", ())
        ],
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

            published = None
            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context")
                mark = context if isinstance(context, int) else None
                if isinstance(context, int):
                    context = contexts[context]
                context = context or {}
                receipts = list(request.get("receipts") or ())


                if mark is None or mark != published:
                    _publish(context, receipts)
                    published = mark
                else:
                    _publish_receipts(context, receipts)
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
