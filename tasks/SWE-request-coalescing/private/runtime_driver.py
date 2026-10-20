'Sandboxed runner for the relay under ``relay/``.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
import threading
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def _fresh_dispatcher_factory() -> Any:
    'Reload the relay so no state survives from the previous programme.'

    sharing = importlib.import_module("relay.sharing")
    importlib.reload(sharing)
    dispatcher = importlib.import_module("relay.dispatcher")
    return importlib.reload(dispatcher).build_dispatcher


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from relay import protocol

    reports: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for raw in payload.get("programmes", ()):
            programme = dict(raw)
            label = str(programme.get("variant", programme.get("profile", "")))
            try:
                factory = _fresh_dispatcher_factory()
                report = dict(protocol.simulate(programme, factory=factory))
                report["ok"] = True
            except BaseException as exc:
                report = {"ok": False, "error": _describe(exc)}
            report["variant"] = label
            report["profile"] = str(programme.get("profile", ""))
            reports.append(report)

    if threading.active_count() > 1:


        return {
            "ok": False,
            "error": "the relay left a second thread running after the replay",
        }
    return {
        "ok": True,
        "reports": reports,
        "relay_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload)
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
