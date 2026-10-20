'Run one desk notebook over a batch of desks inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys
from typing import Any


FLAG_COLUMNS = (
    "flag_id", "account_id", "flag_date", "error_rate_7d", "plan_tier",
    "start_date", "start_queue", "escalation_date", "last_observed_date",
)
STATE_COLUMNS = ("account_id", "state", "effective_from", "effective_to")


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def expand(table, columns):
    'A table sent over the wire as columns and rows, back as dictionaries.'

    if isinstance(table, dict) and "rows" in table:
        names = list(table.get("columns") or columns)
        return [dict(zip(names, row)) for row in table["rows"]]
    return [dict(row) for row in (table or ())]


def _publish(context: dict, receipts: list, tables: bool = True) -> None:
    'Lay the desk out on disk the way the weekly export leaves it.'

    Path("booking_receipts.json").write_text(
        json.dumps({"desk": context.get("desk"), "entries": receipts},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not tables:
        return
    Path("desk_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("desk_book.json").write_text(
        json.dumps(context.get("book", {}), indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_csv("flag_ledger.csv", FLAG_COLUMNS, context.get("flags", ()))
    _write_csv("account_state.csv", STATE_COLUMNS, context.get("account_states", ()))


def _write_csv(name: str, columns, rows) -> None:
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

            opened: dict[Any, dict] = {}
            published = [None]
            for raw in payload.get("requests", ()):
                request = dict(raw)
                handle = request.get("context")
                if isinstance(handle, int):
                    context = opened.get(handle)
                    if context is None:
                        context = dict(contexts[handle])
                        context["flags"] = expand(context.get("flags"), FLAG_COLUMNS)
                        context["account_states"] = expand(
                            context.get("account_states"), STATE_COLUMNS
                        )
                        opened[handle] = context
                else:
                    handle = None
                    context = dict(request.get("context") or {})
                    context["flags"] = expand(context.get("flags"), FLAG_COLUMNS)
                    context["account_states"] = expand(
                        context.get("account_states"), STATE_COLUMNS
                    )
                receipts = list(request.get("receipts") or ())


                _publish(context, receipts, published[0] != handle or handle is None)
                published[0] = handle
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
