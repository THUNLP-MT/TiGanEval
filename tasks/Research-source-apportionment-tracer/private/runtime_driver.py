'Run one apportionment notebook over a batch of windows inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


SAMPLE_COLUMNS = (
    "sample_id", "taken_at", "point", "cond_uScm", "mark_muL", "mark_flag", "dwell_min",
)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _publish(context: dict, ledger: list) -> None:
    'Lay the window out on disk the way the estates office leaves it.'

    Path("header_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("sample_ledger.json").write_text(
        json.dumps({"lot": context.get("lot"), "entries": ledger}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_csv("header_samples.csv", SAMPLE_COLUMNS, context.get("samples", ()))
    _write_csv("weather_log.csv", ("day", "outdoor_C"), context.get("weather", ()))
    _write_csv(
        "heat_meter_daily.csv", ("day", "delivered_kwh"), context.get("heat_meter", ())
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
        results = []
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context") or {}
                ledger = list(request.get("ledger") or ())


                _publish(context, ledger)
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
