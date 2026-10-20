'Sandboxed runner for the plugin sandbox and the dump tool under review.'

from __future__ import annotations

import importlib
import json
import sys
from typing import Any, Mapping


def _say(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"

def _live(plugin: Any) -> bytes:
    return bytes(plugin._arena[: plugin._length])

def _state(plugin: Any) -> dict[str, Any]:
    return {"key": plugin.key, "layout": plugin.layout, "capacity": int(plugin.capacity),
            "length": int(plugin.length), "write_seq": int(plugin.write_seq),
            "detached": bool(plugin.detached)}

def _image(protocol: Any, data: bytes) -> dict[str, Any]:
    return {"length": len(data), "digest": protocol.digest(data),
            "cells": list(protocol.cells(data)), "hex": bytes(data).hex()}

def _delta(delta: Any) -> Any:
    return None if delta is None else {"length": int(delta.length),
        "edits": [[int(e.offset), int(e.before), int(e.after)] for e in delta.edits]}

def _make(protocol: Any, spec: Mapping[str, Any]) -> Any:
    return protocol.Plugin(str(spec["key"]), str(spec.get("label", spec["key"])),
                           str(spec["layout"]), int(spec["capacity"]),
                           protocol.pack(spec.get("cells", ())))

def _targets(host: Any, op: Mapping[str, Any], detached: Mapping[str, Any],
             aliens: Mapping[str, Any]) -> list[Any]:
    keys = op.get("targets")
    if keys is None:
        return host.plugins()
    detached_targets = {str(key) for key in op.get("detached_targets", ())}
    alien_targets = {str(key) for key in op.get("alien_targets", ())}
    return [aliens[str(key)] if str(key) in alien_targets
            else detached[str(key)] if str(key) in detached_targets
            else host.plugin(str(key)) for key in keys]


def _offered_state(plugin: Any, live: Mapping[str, Any]) -> dict[str, Any]:
    return {**_state(plugin), "is_live": live.get(plugin.key) is plugin}

def _read(protocol: Any, capture: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    'What the console can print out of one dump right now.'
    row: dict[str, Any] = {"recorded_epoch": getattr(capture, "epoch", None)}
    try:
        keys = [str(key) for key in capture.keys()]
    except BaseException as exc:
        return {**row, "read_error": _say(exc)}
    images: dict[str, Any] = {}
    deltas: dict[str, Any] = {}
    for key in keys:
        for holder, reader in ((images, capture.image), (deltas, capture.delta)):
            try:
                value = reader(key)
                holder[key] = _image(protocol, bytes(value)) if holder is images else _delta(value)
            except BaseException as exc:
                holder[key] = {"error": _say(exc)}
    row.update({"keys": keys, "images": images, "deltas": deltas})
    roll, meter = str(payload.get("roll_key", "")), str(payload.get("meter_key", ""))
    if "hex" in images.get(roll, {}) and "hex" in images.get(meter, {}):
        row["book_in_the_capture"] = protocol.book(
            bytes.fromhex(images[roll]["hex"]), bytes.fromhex(images[meter]["hex"]))
    return row


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from plugins import protocol

    coordinator = importlib.reload(importlib.import_module("plugins.coordinator")).Coordinator()
    host: Any = None
    captures: dict[str, Any] = {}
    detached: dict[str, Any] = {}
    aliens: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("operations", ())):
        op = dict(raw)
        kind = str(op.get("op", ""))
        record: dict[str, Any] = {"index": index, "op": kind, "phase": str(op.get("phase", "")),
                                  "label": str(op.get("label", f"{kind}-{index}"))}
        try:
            if kind == "host":
                host = protocol.PluginHost(
                    [_make(protocol, spec) for spec in op.get("plugins", ())],
                    queued=list(op.get("queued", ())),
                    declared_total=int(payload.get("declared_total", 0)),
                    roll_key=str(payload.get("roll_key", "roll")),
                    meter_key=str(payload.get("meter_key", "meter")))
            elif kind == "pipeline":
                host.enqueue(list(op.get("steps", ())))
                while op.get("run", True) and host.step():
                    pass
            elif kind == "rotate":
                host.rotate(int(op.get("offset", 1)))
            elif kind == "install":
                plugin = _make(protocol, op["plugin"])
                detached.pop(plugin.key, None)
                host.install(plugin, op.get("position"))
            elif kind == "detach":
                key = str(op["key"])
                detached[key] = host.detach(key)
            elif kind == "alien":
                plugin = _make(protocol, op["plugin"])
                aliens[plugin.key] = plugin
            elif kind in ("capture", "incremental"):
                name, targets = str(op["name"]), _targets(host, op, detached, aliens)
                before: dict[str, Any] = {"epoch": host.epoch(), "pending": host.pending(),
                                          "state": {p.key: _state(p) for p in targets},
                                          "images": {p.key: _live(p).hex() for p in targets}}


                record.update({"capture": name, "baseline": op.get("baseline"),
                               "host_epoch_before": before["epoch"],
                               "targets": [p.key for p in targets]})
                capture = (coordinator.capture(host, list(targets)) if kind == "capture"
                           else coordinator.capture_incremental(
                               host, captures[str(op["baseline"])], list(targets)))
                captures[name], expected[name] = capture, before
                record.update({"host_epoch_after": host.epoch(),
                               **_read(protocol, capture, payload)})
            elif kind == "probe":
                record["capture"] = str(op["capture"])
                record.update(_read(protocol, captures[str(op["capture"])], payload))
            elif kind == "edit_probe":
                capture, key = captures[str(op["capture"])], str(op["key"])
                record.update({"capture": str(op["capture"]), "key": key,
                               "before_edit": _image(protocol, bytes(capture.image(key)))})
                handed = capture.image(key)
                handed[:] = bytes([255] * len(handed))
                record["after_edit"] = _image(protocol, bytes(capture.image(key)))
            elif kind == "restore":
                name, targets = str(op["capture"]), _targets(host, op, detached, aliens)
                try:
                    held = [str(key) for key in captures[name].keys()]
                except BaseException:
                    held = None
                live = {p.key: p for p in host.plugins()}
                record.update({"capture": name, "keys": held,
                               "targets": [p.key for p in targets],
                               "plugins_before": {key: _state(p) for key, p in live.items()},
                               "targets_before": {p.key: _offered_state(p, live) for p in targets},
                               "arenas_before": {key: _image(protocol, _live(p))
                                                 for key, p in live.items()},
                               "target_arenas_before": {p.key: _image(protocol, _live(p))
                                                        for p in targets},
                               "raised": None, "refusal": None})
                try:
                    coordinator.restore(host, captures[name], list(targets))
                except BaseException as exc:
                    record["raised"] = _say(exc)
                    record["refusal"] = {
                        "exception": type(exc).__name__,
                        "reason": getattr(exc, "reason", None),
                        "plugin": getattr(exc, "plugin", None),
                    }
                live = {p.key: p for p in host.plugins()}
                record["plugins_after"] = {key: _state(p) for key, p in live.items()}
                record["targets_after"] = {p.key: _offered_state(p, live) for p in targets}
                record["target_arenas_after"] = {p.key: _image(protocol, _live(p))
                                                 for p in targets}
                record["arenas_after"] = {p.key: _image(protocol, _live(p)) for p in host.plugins()}
                record["balance"] = host.balance()
            elif kind == "report":
                record.update({"epoch": host.epoch(), "pending": host.pending(),
                               "balance": host.balance(),
                               "plugins": [{**_state(p), **_image(protocol, _live(p))}
                                           for p in host.plugins()]})
            else:
                raise ValueError(f"unknown operation: {kind}")
            record["ok"] = True
        except BaseException as exc:
            record["ok"] = False
            record["error"] = _say(exc)
        records.append(record)

    return {"ok": True, "operations": records, "expected": expected,
            "epoch": host.epoch() if host is not None else 0}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
