'Run one gate-pass readout notebook over a batch of months in the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


REGISTER_HEADER = "account_id,address_id,estate,joined_on,activated_at\n"
RECEIPT_HEADER = "ticket_id,receipt_id,drum_id,account_id,sent_on\n"
COUNTER_HEADER = "day,signups_to_date\n"


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _write_files(base: dict, request: dict) -> None:
    accounts = base["accounts"]
    stamps = request["stamps"].split(";") if request["stamps"] else []
    lines = [REGISTER_HEADER]
    for row, stamp in zip(accounts, stamps):
        lines.append(row + stamp + "\n")
    Path("account_register.csv").write_text("".join(lines), encoding="utf-8")
    Path("invitation_receipts.csv").write_text(
        RECEIPT_HEADER + base["receipts"] + request.get("receipts_extra", ""),
        encoding="utf-8",
    )
    Path("signup_counter.csv").write_text(
        COUNTER_HEADER + request["counter"], encoding="utf-8"
    )
    Path("ledger").mkdir(exist_ok=True)
    Path("ledger/receipts.jsonl").write_text(request["ledger"], encoding="utf-8")


def main() -> int:
    captured = io.StringIO()
    try:
        payload = json.load(sys.stdin)
        bases = {
            key: {"accounts": value["accounts"].split("\n"), "receipts": value["receipts"]}
            for key, value in payload.get("campaigns", {}).items()
        }
        results = []
        with contextlib.redirect_stdout(captured):
            import report
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context") or {}
                _write_files(bases[str(request["campaign"])], request)
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(report.next_collection(context))
                    else:
                        answer = report_view(report.analyze(context))
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
