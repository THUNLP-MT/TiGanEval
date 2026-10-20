'Run the delivered notebook once per evidence state, inside the sandbox.'

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


RECORDS = Path("project_records")


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:220]}"


def _lay_out(state) -> None:
    RECORDS.mkdir(exist_ok=True)
    for path in RECORDS.glob("*.json"):
        path.unlink()
    for name, record in dict(state.get("records", {})).items():
        (RECORDS / f"{name}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    Path("session_receipts.json").write_text(
        json.dumps({"campaign": state["context"]["campaign"],
                    "entries": state["receipts"]}, indent=2, sort_keys=True),
        encoding="utf-8")


def run(payload) -> dict:
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        import analysis
        from protocol import booking, study_view

        results = []
        for state in payload.get("states", ()):
            _lay_out(state)
            context, receipts = state["context"], state["receipts"]
            entry = {"label": state["label"]}
            try:
                entry["analyze"] = {
                    "ok": True,
                    "report": study_view(analysis.analyze(context, receipts)),
                }
            except BaseException as exc:
                entry["analyze"] = {"ok": False, "error": _describe(exc)}
            try:
                entry["next"] = {
                    "ok": True,
                    "booking": booking(analysis.next_collection(context, receipts)),
                }
            except BaseException as exc:
                entry["next"] = {"ok": False, "error": _describe(exc)}
            results.append(entry)
    return {"ok": True, "states": results, "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
        json.dumps(result, allow_nan=False)
    except BaseException as exc:
        result = {"ok": False, "error": _describe(exc)}
    sys.stdout.write(json.dumps(result, allow_nan=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
