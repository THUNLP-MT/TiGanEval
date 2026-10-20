'Deterministic sandbox runs: plugin sets, queued pipeline work, console scripts.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _plugin(key: str, label: str, layout: str, capacity: int, cells: Sequence[int]) -> dict[str, Any]:
    return {"key": key, "label": label, "layout": layout, "capacity": int(capacity),
            "cells": list(cells)}


def _handoff(amount: int) -> dict[str, Any]:
    return {"kind": "handoff", "amount": int(amount)}


def _write(key: str, offset: int, values: Sequence[int]) -> dict[str, Any]:
    return {"kind": "write", "key": key, "offset": int(offset), "values": list(values)}


def _resize(key: str, length: int) -> dict[str, Any]:
    return {"kind": "resize", "key": key, "length": int(length)}


def _host(plugins: Sequence[Mapping[str, Any]], queued: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    return {"op": "host", "label": "load-the-sandbox", "plugins": list(plugins),
            "queued": list(queued)}


def _pipeline(label: str, *steps: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "pipeline", "label": label, "steps": list(steps)}


def _capture(name: str, targets: Sequence[str] | None = None) -> dict[str, Any]:
    return {"op": "capture", "label": f"capture-{name}", "name": name, "targets": targets}


def _incremental(name: str, baseline: str, targets: Sequence[str] | None = None) -> dict[str, Any]:
    return {"op": "incremental", "label": f"capture-{name}", "name": name,
            "baseline": baseline, "targets": targets}


def _probe(name: str, label: str | None = None) -> dict[str, Any]:
    return {"op": "probe", "label": label or f"read-{name}", "capture": name}


def _edit(name: str, key: str) -> dict[str, Any]:
    return {"op": "edit_probe", "label": f"edit-{name}-{key}", "capture": name, "key": key}


def _restore(name: str, label: str, targets: Sequence[str] | None = None, *,
             detached_targets: Sequence[str] = (),
             alien_targets: Sequence[str] = ()) -> dict[str, Any]:
    return {"op": "restore", "label": label, "capture": name, "targets": targets,
            "detached_targets": list(detached_targets),
            "alien_targets": list(alien_targets)}


def _report(label: str) -> dict[str, Any]:
    return {"op": "report", "label": label}


def _rotate(offset: int = 1) -> dict[str, Any]:
    return {"op": "rotate", "label": f"reload-order-{offset}", "offset": int(offset)}


def _detach(key: str) -> dict[str, Any]:
    return {"op": "detach", "label": f"unload-{key}", "key": key}


def _install(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "install", "label": f"load-{spec['key']}", "plugin": dict(spec)}


def _alien(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "alien", "label": f"make-unloaded-{spec['key']}", "plugin": dict(spec)}


def _phase(name: str, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**dict(op), "phase": name} for op in ops]


def _program(roll: str, meter: str, declared: int, ops: Sequence[Mapping[str, Any]],
             phase: str = "run") -> dict[str, Any]:
    return {"roll_key": roll, "meter_key": meter, "declared_total": int(declared),
            "operations": _phase(phase, ops)}


def _handoff_burst() -> dict[str, Any]:
    'A dump taken while the pipeline is still moving batches across.'

    plugins = [
        _plugin("meter", "usage meter", "meter.v4", 48, [1200, 900, 700, 400]),
        _plugin("roll", "roll-up", "roll.v2", 16, [1000, 0]),
        _plugin("dedupe", "duplicate sketch", "sketch.v1", 32, [7, 7, 7, 7]),
    ]
    ops = [
        _host(plugins, [_handoff(300) for _ in range(8)]),
        _report("before-the-dump"),
        _capture("morning"),
        _probe("morning", "read-the-dump"),
        _report("after-the-dump"),
        _pipeline("let-the-rest-of-the-batch-through"),
        _report("once-the-batch-is-through"),
    ]
    return _program("roll", "meter", 4200, ops, "handoff")


def _overnight_review() -> dict[str, Any]:
    'A dump taken in the evening and read again after a night of pipeline work.'

    plugins = [
        _plugin("meter", "usage meter", "meter.v4", 48, [800, 600, 600]),
        _plugin("roll", "roll-up", "roll.v2", 16, [400, 0]),
        _plugin("dedupe", "duplicate sketch", "sketch.v1", 32, [3, 1, 4, 1, 5]),
    ]
    ops = [
        _host(plugins),
        _report("end-of-day"),
        _capture("evening"),
        _probe("evening", "read-it-that-evening"),
        _pipeline("overnight", _handoff(500), _write("dedupe", 4, [9, 2, 6]), _handoff(500),
                  _write("dedupe", 0, [8]), _handoff(400), _write("dedupe", 12, [5, 3])),
        _report("next-morning"),
        _probe("evening", "read-it-next-morning"),
        _edit("evening", "dedupe"),
        _probe("evening", "read-it-after-the-edit"),
    ]
    return _program("roll", "meter", 2400, ops, "overnight")


def _grow_then_capture() -> dict[str, Any]:
    'A chain of dumps over arenas that grow, shrink, move and stand still.'

    plugins = [
        _plugin("meter", "usage meter", "meter.v4", 48, [500, 500, 500, 500]),
        _plugin("roll", "roll-up", "roll.v2", 16, [200, 0]),
        _plugin("dedupe", "duplicate sketch", "sketch.v1", 64, [9, 9, 9, 9, 9, 9]),
        _plugin("audit", "audit trail", "trail.v1", 16, [42]),
    ]
    ops = [
        _host(plugins),
        _report("start-of-the-batch"),
        _capture("base"),
        _pipeline("first-window", _handoff(500), _resize("dedupe", 40),
                  _write("dedupe", 24, [11, 12, 13, 14])),
        _rotate(1),
        _incremental("inc1", "base"),
        _probe("inc1", "read-the-first-incremental"),
        _pipeline("second-window", _resize("dedupe", 16)),


        _incremental("inc2", "inc1", ["dedupe", "audit"]),
        _probe("inc2", "read-the-second-incremental"),
        _capture("full-at-the-same-moment"),
        _probe("full-at-the-same-moment", "read-the-full-dump"),
        _pipeline("after-the-batch", _handoff(500), _write("audit", 0, [43])),
        _probe("base", "read-the-baseline-again"),
        _report("end-of-the-batch"),
    ]
    return _program("roll", "meter", 2200, ops, "chain")


def _restore_drill() -> dict[str, Any]:
    'Putting a dump back over a grown arena, and into a reloaded plugin.'

    plugins = [
        _plugin("meter", "usage meter", "meter.v4", 48, [300, 300, 300]),
        _plugin("roll", "roll-up", "roll.v2", 16, [100, 0]),
        _plugin("dedupe", "duplicate sketch", "sketch.v1", 64, [5, 5, 5, 5]),
    ]
    ops = [
        _host(plugins),
        _capture("before-the-run"),
        _pipeline("the-bad-run", _handoff(300), _resize("dedupe", 32),
                  _write("dedupe", 16, [99, 98, 97, 96])),
        _report("after-the-bad-run"),
        _restore("before-the-run", "put-it-back"),
        _report("after-putting-it-back"),
        _detach("roll"),
        _install(_plugin("roll", "roll-up", "roll.v3", 12, [0, 0])),
        _report("after-the-reload"),
        _restore("before-the-run", "put-it-back-into-the-reloaded-sandbox"),
        _report("after-the-second-attempt"),
        _detach("roll"),
        _install(_plugin("roll", "roll-up", "roll.v2", 4, [0])),
        _report("after-the-second-reload"),
        _restore("before-the-run", "put-it-back-into-the-smaller-block"),
        _report("after-the-last-attempt"),
    ]
    return _program("roll", "meter", 1000, ops, "restore")


def _release_plugins() -> list[dict[str, Any]]:
    return [
        _plugin("pending", "pending usage", "pending.v7", 64, [700, 700, 700, 700, 700]),
        _plugin("settled", "settled roll-up", "settled.v3", 16, [500, 0]),
        _plugin("sketch", "duplicate sketch", "sketch.v2", 96, [1, 2, 3, 4, 5, 6]),
        _plugin("trail", "audit trail", "trail.v4", 48, [11, 22]),
        _plugin("window", "late window", "window.v1", 32, [0, 0, 0, 0]),
    ]


def _release_ops() -> list[dict[str, Any]]:
    cut = [
        _host(_release_plugins(), [_handoff(350) for _ in range(10)]),
        _report("before-the-first-dump"),
        _capture("cut"),
        _probe("cut", "read-the-first-dump"),
        _report("after-the-first-dump"),
        _pipeline("let-the-rest-of-the-batch-through"),
        _report("once-the-batch-is-through"),
        {**_pipeline("queue-the-next-window", _write("sketch", 0, [91])), "run": False},
        _capture("cut-after-progress"),
        _probe("cut-after-progress", "read-the-progressed-dump"),
        _pipeline("let-the-next-window-through"),
        _report("after-the-progressed-dump"),
    ]
    hold = [
        _capture("hold"),
        _probe("hold", "read-it-straight-away"),
        _pipeline("a-night-of-work", _write("sketch", 0, [61, 62]), _handoff(350),
                  _write("trail", 0, [31]), _write("window", 8, [7]), _handoff(350),
                  _write("sketch", 12, [63])),
        _probe("hold", "read-it-the-next-day"),
        _edit("hold", "sketch"),
        _probe("hold", "read-it-after-the-edit"),
        _report("after-the-night"),
    ]
    chain = [
        _capture("chain-0"),
        _pipeline("window-one", _resize("sketch", 40), _write("sketch", 24, [71, 72, 73, 74]),
                  _write("trail", 4, [41])),
        _rotate(2),
        _incremental("chain-1", "chain-0"),
        _probe("chain-1", "read-chain-1"),
        _pipeline("window-two", _resize("sketch", 20), _handoff(350),
                  _write("window", 0, [5])),
        _install(_plugin("ledger", "late ledger", "ledger.v1", 32, [17, 18])),
        _incremental("chain-2", "chain-1"),
        _probe("chain-2", "read-chain-2"),
        _pipeline("window-three", _write("window", 12, [3]), _resize("trail", 4),
                  _write("ledger", 0, [19])),
        _detach("ledger"),
        _rotate(3),
        _incremental("chain-3", "chain-2"),
        _probe("chain-3", "read-chain-3"),
        _capture("chain-full"),
        _probe("chain-full", "read-the-full-dump"),
        _pipeline("after-the-chain", _handoff(350), _write("trail", 0, [51])),
        _probe("chain-0", "read-the-baseline-again"),
        _report("end-of-the-chain"),
    ]
    recovery = [
        _capture("recovery"),
        _pipeline("the-bad-run", _handoff(350), _resize("sketch", 48),
                  _write("sketch", 20, [81, 82, 83, 84, 85, 86, 87]), _write("window", 0, [9])),
        _report("after-the-bad-run"),


        _alien(_plugin("window", "late window", "window.v1", 32, [1, 1, 1, 1])),
        _restore("recovery", "put-it-back-with-an-unloaded-lookalike",
                 ["pending", "settled", "sketch", "trail", "window"],
                 alien_targets=["window"]),
        _report("after-the-unloaded-lookalike-attempt"),
        _restore("recovery", "put-the-sandbox-back"),
        _report("after-putting-it-back"),
        _detach("sketch"),
        _install(_plugin("sketch", "duplicate sketch", "sketch.v2", 32, [0])),
        _report("after-the-sketch-came-back"),
        _restore("recovery", "put-it-back-after-the-sketch-came-back"),
        _report("after-the-second-recovery"),


        _install(_plugin("gauge", "late gauge", "gauge.v1", 16, [0])),
        _report("after-the-gauge-came-up"),
        _restore("recovery", "put-it-back-with-another-plugin-loaded"),
        _report("after-the-third-recovery"),


        _detach("window"),
        _restore("recovery", "put-it-back-with-the-window-detached",
                 ["pending", "settled", "sketch", "trail", "window"],
                 detached_targets=["window"]),
        _install(_plugin("window", "late window", "window.v1", 32, [0, 0, 0, 0])),
        _report("after-the-detached-target-attempt"),
    ]
    refuse = [
        _detach("trail"),
        _install(_plugin("trail", "audit trail", "trail.v9", 48, [0])),
        _report("after-the-reload"),
        _restore("recovery", "put-it-back-into-the-reloaded-sandbox"),
        _report("after-the-reloaded-attempt"),
        _detach("window"),
        _report("after-unloading-the-window"),
        _restore("recovery", "put-it-back-with-a-plugin-gone"),
        _report("after-the-last-attempt"),
    ]
    return (_phase("cut", cut) + _phase("hold", hold) + _phase("chain", chain)
            + _phase("recovery", recovery) + _phase("refuse", refuse))


PUBLIC_PROGRAMS = {
    "handoff": _handoff_burst,
    "overnight": _overnight_review,
    "chain": _grow_then_capture,
    "restore": _restore_drill,
}


def build_program(profile: str) -> dict[str, Any]:
    'The plugin set, the queued pipeline work and the console script of one run.'

    if profile == "release":
        return {"roll_key": "settled", "meter_key": "pending", "declared_total": 4000,
                "operations": _release_ops()}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown sandbox run profile: {profile}")
    return builder()


def plugin_specs(program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    'Every plugin the run loads, as the console lists them.'

    specs: dict[str, dict[str, Any]] = {}
    for op in program.get("operations", ()):
        if str(op.get("op")) == "host":
            for spec in op.get("plugins", ()):
                specs[str(spec["key"])] = dict(spec)
        elif str(op.get("op")) == "install":
            specs[str(op["plugin"]["key"])] = dict(op["plugin"])
    return specs
