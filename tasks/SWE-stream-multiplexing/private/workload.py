'Deterministic drill programs for the telemetry uplink.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


LINK = {"side": "station", "max_frame_size": 256, "send_window": 1024, "recv_window": 1024}

HIGH, NORMAL, BULK = 2, 1, 0


def _session(**over: Any) -> dict[str, Any]:
    return {"type": "session", "label": "link-up", "config": {**LINK, **over}}


def _open(stream: str, priority: int = NORMAL, drains: bool = True) -> dict[str, Any]:
    return {
        "type": "open", "label": f"open-{stream}", "stream": stream,
        "priority": int(priority), "drains": bool(drains),
    }


def _write(stream: str, chunks: Sequence[int], seed: int, index: int = 1) -> dict[str, Any]:
    return {
        "type": "write", "label": f"write-{stream}-{index}", "stream": stream,
        "chunks": [int(size) for size in chunks], "token": f"{stream}-{seed}-{index}",
    }


def _pump(label: str, budget: int, **flags: Any) -> dict[str, Any]:
    return {"type": "pump", "label": label, "budget": int(budget), **flags}


def _drain(stream: str, size: int, index: int = 1) -> dict[str, Any]:
    return {
        "type": "drain", "label": f"{stream}-consumer-{index}",
        "stream": stream, "size": int(size),
    }


def _read(stream: str, index: int = 1, after_close: bool = False) -> dict[str, Any]:
    return {
        "type": "read", "label": f"read-{stream}-{index}", "stream": stream,
        "after_close": bool(after_close),
    }


def _report(label: str, **flags: Any) -> dict[str, Any]:
    return {"type": "report", "label": label, **flags}


def _rounds(prefix: str, count: int, budget: int, drains: Sequence[tuple[str, int]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for number in range(1, count + 1):
        steps.append(_pump(f"{prefix}-{number}", budget))
        steps.extend(_drain(stream, size, number) for stream, size in drains)
    return steps


def _upload(seed: int, scale: int) -> list[dict[str, Any]]:
    'Traffic in both directions with the counters read part way through.'

    return [
        _session(),
        {"type": "peer_open", "label": "unit-opens-its-own", "stream": "unit-log"},
        {"type": "accept", "label": "take-the-units-stream", "stream": "unit-log"},
        _open("status", HIGH),
        _open("log", NORMAL),
        _write("log", [320, 320, 320], seed),
        _write("status", [180], seed),
        {"type": "peer_push", "label": "unit-sends-its-log", "stream": "unit-log",
         "size": 480, "token": f"unit-log-{seed}"},
        {"type": "peer_push", "label": "unit-answers-status", "stream": "status",
         "size": 240, "token": f"status-back-{seed}"},
        _pump("slot-1", 600),
        _drain("status", 180),
        _drain("log", 300),
        _read("unit-log"),
        _read("status"),
        _pump("slot-2", 600),
        _drain("log", 400),
        _report("link-report-at-midnight"),
        _pump("slot-3", 900),
        _drain("log", 400),
        _pump("slot-4", 900),
        _drain("log", 400),
        _read("unit-log", 2),
        _read("status", 2),
        _report("link-report-in-the-morning", expect_delivered=True),
    ]


def _slowdrain(seed: int, scale: int) -> list[dict[str, Any]]:
    'One transfer bigger than the room the unit has, its consumer plodding.'

    total = 2400 + 200 * int(scale)
    return [
        _session(),
        _open("bulk", NORMAL),
        _write("bulk", [total], seed),
        *_rounds("slot", 12, 700, [("bulk", 200)]),
        _report("link-report", expect_delivered=False),
    ]


def _silence(seed: int, scale: int) -> list[dict[str, Any]]:
    'The Tuesday shape: one stream whose consumer has stopped, two that must land.'

    return [
        _session(),
        _open("log-upload", NORMAL, drains=False),
        _open("operator-cancel", HIGH),
        _open("status-poll", NORMAL),
        _write("log-upload", [250] * 9, seed),
        _write("operator-cancel", [210], seed),
        _write("status-poll", [260], seed),
        *_rounds("slot", 4, 500, [("operator-cancel", 210), ("status-poll", 260)]),
        _report("link-report", expect_ready_complete=True),
    ]


def _teardown(seed: int, scale: int) -> list[dict[str, Any]]:
    'A field swap: streams closed from both ends while the link is busy.'

    return [
        _session(),
        _open("console"),
        _open("upload"),
        _open("probe"),
        _open("beacon"),
        _write("upload", [1100], seed),
        _write("console", [160], seed),
        _write("beacon", [320], seed),
        {"type": "peer_push", "label": "unit-answers-the-console", "stream": "console",
         "size": 400, "token": f"console-back-{seed}"},
        _pump("slot-1", 600),
        _drain("console", 160),
        _drain("upload", 300),
        {"type": "close_stream", "label": "operator-hangs-up-console", "stream": "console"},
        _pump("console-close-signal", 7, expect_shut="console"),
        {"type": "probe", "label": "console-write-after-hangup", "kind": "write",
         "stream": "console"},
        {"type": "peer_push", "label": "unit-answers-after-the-hangup", "stream": "console",
         "size": 220, "token": f"console-late-{seed}"},
        {"type": "present", "label": "console-still-listed", "stream": "console"},
        {"type": "peer_close", "label": "unit-shuts-console", "stream": "console"},
        {"type": "present", "label": "console-with-both-ends-shut",
         "stream": "console", "must_be_listed": True},
        _read("console", 1, after_close=True),
        {"type": "present", "label": "console-once-it-is-drained",
         "stream": "console", "must_be_gone": True},
        {"type": "peer_close", "label": "unit-shuts-upload", "stream": "upload"},
        {"type": "present", "label": "upload-while-station-still-has-it-open",
         "stream": "upload", "must_be_listed": True, "one_end_open": "station"},
        {"type": "close_stream", "label": "station-shuts-upload", "stream": "upload"},
        {"type": "present", "label": "upload-after-both-ends",
         "stream": "upload", "must_be_gone": True},
        {"type": "close_stream", "label": "station-shuts-probe", "stream": "probe"},
        {"type": "present", "label": "probe-while-unit-still-has-it-open",
         "stream": "probe", "must_be_listed": True, "one_end_open": "unit"},
        {"type": "peer_close", "label": "unit-shuts-probe", "stream": "probe"},
        {"type": "present", "label": "probe-after-both-ends",
         "stream": "probe", "must_be_gone": True},
        _report("link-report-before-the-swap", expect_open=["beacon"]),
        {"type": "close_session", "label": "kill-the-link", "refusing": True},
        {"type": "probe", "label": "beacon-write-after-kill", "kind": "write",
         "stream": "beacon"},
        {"type": "probe", "label": "open-after-kill", "kind": "open"},
        _report("link-report-after-the-swap", settled=True),
    ]


def _release(seed: int, scale: int) -> list[dict[str, Any]]:
    upload = [
        _session(),
        {"type": "peer_open", "label": "unit-opens-its-own", "stream": "unit-log"},
        {"type": "accept", "label": "take-the-units-stream", "stream": "unit-log"},
        _open("night-status", HIGH),
        _open("night-log", NORMAL),
        _write("night-log", [280, 280, 280, 280], seed),
        _write("night-status", [150], seed),
        {"type": "peer_push", "label": "unit-sends-its-log", "stream": "unit-log",
         "size": 520, "token": f"unit-log-{seed}"},
        {"type": "peer_push", "label": "unit-answers-status", "stream": "night-status",
         "size": 210, "token": f"status-back-{seed}"},
        _pump("slot-1", 600),
        _drain("night-status", 150),
        _drain("night-log", 300),
        _read("unit-log"),
        _read("night-status"),
        _pump("slot-2", 600),
        _drain("night-log", 400),
        _report("link-report-at-midnight"),
        _pump("slot-3", 900),
        _drain("night-log", 400),
        _pump("slot-4", 900),
        _drain("night-log", 400),
        _read("unit-log", 2),
        _read("night-status", 2),
        _report("link-report-in-the-morning", expect_delivered=True),
    ]
    slowdrain = [
        _session(),
        _open("archive-push", NORMAL),
        _write("archive-push", [2600], seed),
        *_rounds("slot", 12, 700, [("archive-push", 220)]),
        _report("link-report", expect_delivered=False),
    ]
    silence = [
        _session(),
        _open("depot-log", NORMAL),
        _open("firmware-push", BULK),
        _open("alarm-relay", HIGH, drains=False),
        _write("alarm-relay", [250] * 16, seed),
        _write("depot-log", [320], seed),
        _write("firmware-push", [480], seed),
        *_rounds("slot", 6, 500, [("depot-log", 320), ("firmware-push", 480)]),
        _report("link-report", expect_ready_complete=True),
    ]
    teardown = [
        _session(),
        _open("relay"),
        _open("dump"),
        _open("ping"),
        _open("watch"),
        _write("dump", [1300], seed),
        _write("relay", [140], seed),
        _write("watch", [300], seed),
        {"type": "peer_push", "label": "unit-answers-the-relay", "stream": "relay",
         "size": 360, "token": f"relay-back-{seed}"},
        _pump("slot-1", 600),
        _drain("relay", 140),
        _drain("dump", 300),
        {"type": "close_stream", "label": "station-shuts-relay", "stream": "relay"},
        _pump("relay-close-signal", 7, expect_shut="relay"),
        {"type": "probe", "label": "relay-write-after-shut", "kind": "write", "stream": "relay"},
        {"type": "peer_push", "label": "unit-answers-after-the-shut", "stream": "relay",
         "size": 180, "token": f"relay-late-{seed}"},
        {"type": "peer_close", "label": "unit-shuts-relay", "stream": "relay"},
        {"type": "present", "label": "relay-with-both-ends-shut",
         "stream": "relay", "must_be_listed": True},
        _read("relay", 1, after_close=True),
        {"type": "present", "label": "relay-once-it-is-drained",
         "stream": "relay", "must_be_gone": True},
        {"type": "peer_close", "label": "unit-shuts-dump", "stream": "dump"},
        {"type": "present", "label": "dump-while-station-still-has-it-open",
         "stream": "dump", "must_be_listed": True, "one_end_open": "station"},
        {"type": "probe", "label": "dump-write-after-shut", "kind": "write", "stream": "dump"},
        {"type": "close_stream", "label": "station-shuts-dump", "stream": "dump"},
        {"type": "present", "label": "dump-after-both-ends",
         "stream": "dump", "must_be_gone": True},
        {"type": "close_stream", "label": "station-shuts-ping", "stream": "ping"},
        {"type": "present", "label": "ping-while-unit-still-has-it-open",
         "stream": "ping", "must_be_listed": True, "one_end_open": "unit"},
        {"type": "peer_close", "label": "unit-shuts-ping", "stream": "ping"},
        {"type": "present", "label": "ping-after-both-ends",
         "stream": "ping", "must_be_gone": True},
        _report("link-report-before-the-swap", expect_open=["watch"]),
        {"type": "close_session", "label": "kill-the-link", "refusing": True},
        {"type": "probe", "label": "watch-write-after-kill", "kind": "write",
         "stream": "watch"},
        {"type": "probe", "label": "open-after-kill", "kind": "open"},
        _report("link-report-after-the-swap", settled=True),
    ]
    return (
        [{**event, "phase": "upload"} for event in upload]
        + [{**event, "phase": "slowdrain"} for event in slowdrain]
        + [{**event, "phase": "silence"} for event in silence]
        + [{**event, "phase": "teardown"} for event in teardown]
    )


PROGRAM_BUILDERS = {
    "upload": _upload,
    "slowdrain": _slowdrain,
    "silence": _silence,
    "teardown": _teardown,
    "release": _release,
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown drill profile: {profile}")
    return [{"phase": profile, **event} for event in builder(seed, scale)]
