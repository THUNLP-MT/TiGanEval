'Sandboxed runner for the relay client simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from relay import vault, wire

    clock = wire.Clock(float(payload.get("start_s", 0.0)))
    hosts = {
        str(origin): wire.Host(str(origin), clock, dict(spec))
        for origin, spec in dict(payload.get("hosts", {})).items()
    }
    journey = wire.Journey(clock, hosts)
    profile = wire.JobProfile(**dict(payload.get("profile", {})))
    captured = io.StringIO()

    with redirect_stdout(captured):
        store = vault.GrantStore(profile, clock)
        for raw in payload.get("operations", ()):
            op = dict(raw)
            kind = str(op.get("op", ""))
            if kind == "at":
                clock.set(float(op["to"]))
            elif kind == "wait":
                clock.advance(float(op["s"]))
            elif kind == "get":
                request = wire.Request(
                    url=str(op["url"]),


                    label="",
                    method=str(op.get("method", "GET")),
                )
                journey.go(store, request, entered_as=str(op.get("entered_as", "")))
                journey.log[-1]["label"] = str(op.get("label", ""))
                journey.log[-1]["phase"] = str(op.get("phase", ""))
            else:
                raise ValueError(f"unknown operation: {kind}")

    return {
        "ok": True,
        "steps": list(journey.log),
        "clock_s": clock.now(),
        "stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": _describe(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
