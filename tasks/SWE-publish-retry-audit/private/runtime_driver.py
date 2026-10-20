'Sandboxed runner for the release console.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _plain(value: Any) -> Any:
    'Whatever the publishing step returned, as something JSON can carry.'

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _items(items: Any) -> list[dict[str, Any]]:
    return [
        {
            "publisher": str(item.publisher),
            "instance": str(item.instance),
            "target": str(item.target),
            "artifact": str(item.artifact.name),
            "kind": str(item.artifact.kind),
            "bytes": int(item.artifact.size),
            "digest": str(item.artifact.digest),
        }
        for item in items
    ]


def _objects(host: Any, instances: Any) -> list[dict[str, Any]]:
    rows = []
    for instance in sorted(set(instances)):
        for target in host.objects(instance):
            size, digest = host.stored(instance, target)
            rows.append(
                {
                    "instance": instance,
                    "target": target,
                    "bytes": int(size),
                    "digest": str(digest),
                }
            )
    return rows


def _one_release(spec: Mapping[str, Any], protocol: Any, module: Any, config: Any) -> dict[str, Any]:
    clock = protocol.Clock(float(spec.get("start_ms", 0.0)))
    host = protocol.Host(dict(spec.get("script", {})), clock)
    stop_at = spec.get("stop_at_ms")
    stop = protocol.StopSignal(clock, None if stop_at is None else float(stop_at))
    manifest = dict(spec["manifest"])
    instances = [str(entry["instance"]) for entry in manifest.get("publishers", ())]
    record: dict[str, Any] = {
        "phase": str(spec.get("phase", "")),
        "version": str(manifest.get("version", "")),
        "order": [str(name) for name in spec.get("order", ())],
        "stop_at_ms": None if stop_at is None else float(stop_at),
    }
    try:
        items = protocol.plan_items(manifest, spec.get("order"))
        record["items"] = _items(items)
        record["report"] = _plain(module.Release(config, clock, host, stop).publish(items))
    except BaseException as exc:
        record["error"] = _describe(exc)
    record.setdefault("items", [])
    record["log"] = [dict(entry) for entry in host.log]
    record["objects"] = _objects(host, instances)
    record["clock_ms"] = clock.now_ms()
    return record


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from publish import protocol

    module = importlib.reload(importlib.import_module("publish.uploader"))
    config = protocol.load_release_config("release.toml")
    releases: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for spec in payload.get("releases", ()):
            releases.append(_one_release(dict(spec), protocol, module, config))
    return {
        "ok": True,
        "settings": {
            "attempts": int(config.attempts),
            "delay_ms": float(config.delay_ms),
            "max_delay_ms": float(config.max_delay_ms),
        },
        "releases": releases,
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
