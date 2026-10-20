'Sandboxed runner for one night of the rating run.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _reload_delivered_modules() -> None:
    'Take the delivered `recovery` and `triage` rather than an imported copy.'

    for name in ("pricing.triage", "pricing.recovery"):
        importlib.reload(importlib.import_module(name))


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    'Price the night in `payload` against the workspace on PYTHONPATH.'

    from pricing import protocol

    _reload_delivered_modules()
    rulebook = protocol.load_rulebook()
    captured = io.StringIO()
    try:
        with redirect_stdout(captured):
            night = protocol.run_night(dict(payload), rulebook)
    except BaseException as exc:
        return {"ok": False, "error": f"the run stopped on {_describe(exc)}"}
    return {
        "ok": True,
        "orders": list(night.get("orders", ())),
        "effects": list(night.get("effects", ())),
        "faults": list(night.get("faults", ())),
        "leases": list(night.get("leases", ())),
        "open_leases": list(night.get("open_leases", ())),
        "leases_held_at_once": dict(night.get("leases_held_at_once", {})),
        "labels": dict(night.get("labels", {})),
        "limits": dict(rulebook.limits),
        "guards": {name: rule.guard for name, rule in rulebook.rules.items()},
        "stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
