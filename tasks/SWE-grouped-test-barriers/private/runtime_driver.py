'Sandboxed runner for one recorded night against a delivered workspace.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _runner_module() -> Any:
    'Reload both delivered files, so a stale import cannot answer for them.'

    importlib.reload(importlib.import_module("harness.rendezvous"))
    return importlib.reload(importlib.import_module("harness.sequencing"))


def _inventory_rows(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"handset": handset.id, "bench": handset.bench, "model": handset.model}
            for handset in inventory.values()]


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from harness import protocol

    inventory = protocol.load_inventory(Path("lab_devices.json"))
    session = protocol.load_session(dict(payload["session"]), inventory)
    module = _runner_module()
    captured = io.StringIO()
    runner_error: str | None = None

    with redirect_stdout(captured):
        try:
            module.SuiteRunner(session).run()
        except BaseException as exc:
            runner_error = _describe(exc)

    report = dict(session.report())
    report.update({
        "ok": True,
        "runner_error": runner_error,
        "inventory": _inventory_rows(inventory),
        "handsets": [handset.id for handset in session.handsets],
        "stdout": captured.getvalue()[-2000:],
    })
    return report


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
