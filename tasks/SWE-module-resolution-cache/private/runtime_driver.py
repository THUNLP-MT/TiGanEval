'Sandboxed runner for the scripting runtime simulator.'

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


RECURSION_LIMIT = 300
CONSOLE_CHARS = 4000


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    from runtime import protocol

    module = importlib.reload(importlib.import_module("runtime.loader"))
    scenario = dict(payload.get("scenario", {}))
    console = io.StringIO()
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(RECURSION_LIMIT)
    try:
        with redirect_stdout(console), redirect_stderr(console):
            try:
                outcome = protocol.simulate(scenario, module.Loader)
                failure = None
            except BaseException as exc:
                outcome, failure = {"runs": []}, f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        sys.setrecursionlimit(previous)

    result: dict[str, Any] = {
        "ok": failure is None,
        "process_console": console.getvalue()[-CONSOLE_CHARS:],
        "runs": list(outcome.get("runs", ())),
        "store_tree": list(outcome.get("store_tree", ())),
    }
    if failure is not None:
        result["error"] = failure
    return result


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
