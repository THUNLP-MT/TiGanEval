'Sandboxed runner for the fulfilment workflow simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import sys
from typing import Any, Mapping, Sequence


def _pass(chart: Any, steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    from fulfilment.engine import Engine
    from fulfilment.scopes import ScopeManager

    engines: dict[str, Any] = {}
    reports: list[dict[str, Any]] = []
    for step in steps:
        order = str(step["order"])
        event = str(step["event"])
        payload = dict(step.get("payload") or {})
        if order not in engines:
            engines[order] = Engine(chart, ScopeManager(chart), name=order)
        engine = engines[order]
        report = engine.start(payload) if event == "start" else engine.send(event, payload)
        reports.append(json.loads(json.dumps(dict(report), default=str)))
    return reports


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from fulfilment.protocol import Chart

    spec = dict(payload["chart"])
    steps = [dict(step) for step in payload.get("steps", ())]
    captured = io.StringIO()
    with redirect_stdout(captured):
        chart = Chart(deepcopy(spec))
        interleaved = _pass(chart, steps)
        orders = list(dict.fromkeys(str(step["order"]) for step in steps))


        alone = {
            order: _pass(
                Chart(deepcopy(spec)),
                [step for step in steps if str(step["order"]) == order],
            )
            for order in orders
        }
        declarations = {
            str(state): json.loads(json.dumps(dict(chart.declared(state)), default=str))
            for state in chart.states()
        }
    return {
        "ok": True,
        "interleaved": interleaved,
        "alone": alone,
        "orders": orders,
        "declarations_after": declarations,
        "workspace_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
