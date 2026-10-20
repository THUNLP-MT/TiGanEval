'Deterministic start-ups: service manifests, connect schedules, console scripts.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _service(name: str, depends_on: Sequence[str] = (), *, ticks: int | None = None,
             acquire: bool = False, returns: str | None = None, fails_after: int | None = None,
             error: str = "the handshake was refused", guard: str | None = None,
             stop_error: str | None = None, session_once: str | None = None) -> dict[str, Any]:
    'One manifest entry. Without `ticks` the service has no connect step.'

    entry: dict[str, Any] = {"name": name, "depends_on": list(depends_on)}
    if ticks is not None:
        start: dict[str, Any] = {"ticks": int(ticks), "acquire": bool(acquire)}
        if returns is not None:
            start["returns"] = str(returns)
        if session_once is not None:
            start["session_once"] = str(session_once)
        if fails_after is not None:
            start["fails_after"] = int(fails_after)
            start["error"] = str(error)
        entry["start"] = start
        stop: dict[str, Any] = {"release": bool(acquire)}
        if guard is not None:
            stop["guard"] = str(guard)
        if stop_error is not None:
            stop["error"] = str(stop_error)
        entry["stop"] = stop
    return entry


def _config(max_parallel_starts: int = 4, deploy_window_ticks: int = 300) -> dict[str, Any]:
    return {"name": "api", "max_parallel_starts": int(max_parallel_starts),
            "deploy_window_ticks": int(deploy_window_ticks)}


def _scene(name: str, manifest: Sequence[Mapping[str, Any]],
           operations: Sequence[Mapping[str, Any]], *,
           config: Mapping[str, Any] | None = None,
           timers: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    return {
        "name": name,
        "config": dict(config or _config()),
        "manifest": [dict(entry) for entry in manifest],
        "timers": [dict(timer) for timer in timers],
        "operations": [dict(op) for op in operations],
    }


def _reorder(manifest: Sequence[Mapping[str, Any]], order: Sequence[str]) -> list[dict[str, Any]]:
    'The same manifest as the console would register it on another host.'

    by_name = {str(entry["name"]): dict(entry) for entry in manifest}
    return [by_name[name] for name in order]


BRING_UP = {"op": "bring_up"}


BOOT_SCENE = "settlements-boot"
FAILING_SCENE = "settlements-lease-refused"
TYPO_SCENE = "settlements-manifest-typo"
UNKNOWN_SCENE = "settlements-missing-edge"
FAILING_SERVICE = "invoice-writer"


def _probes(*names: str) -> list[dict[str, Any]]:
    return [{"op": "probe", "name": name} for name in names]


SETTLEMENTS = (
    _service("quote-service", ["pool-handle", "lookup-index"], ticks=80, acquire=True),
    _service("session-cache", ["config-store"], ticks=25, acquire=True),
    _service("ledger-pool", ["config-store"], ticks=60, acquire=True, returns="ledger-pool/ready"),
    _service("config-store"),
    _service("invoice-writer", ["pool-handle"], ticks=40, acquire=True),
    _service("document-store", ["config-store"], ticks=90, acquire=True),
    _service("pool-handle", ["ledger-pool"]),
    _service("metrics-sink", ["config-store"], ticks=20, acquire=True),
    _service("lookup-index", ["session-cache"], ticks=35, acquire=True, guard="session-cache"),
    _service(
        "token-issuer",
        ["config-store"],
        ticks=45,
        acquire=True,
        stop_error="the revoke call timed out on the way down",
    ),
)

SETTLEMENTS_STARTED = tuple(
    str(entry["name"]) for entry in SETTLEMENTS if "start" in entry
)


SETTLEMENTS_FAILING = tuple(
    _service(
        "invoice-writer",
        ["pool-handle"],
        ticks=40,
        acquire=True,
        fails_after=15,
        error="the ledger refused the write lease",
    )
    if str(entry["name"]) == "invoice-writer"
    else dict(entry)
    for entry in SETTLEMENTS
)

TYPO_MANIFEST = (
    _service("config-store"),
    _service("audit-trail", ["config-store"], ticks=20, acquire=True),
    _service("queue-reader", ["dispatch-log"], ticks=30, acquire=True),
    _service("dispatch-log", ["queue-reader"], ticks=25, acquire=True),
)

UNKNOWN_MANIFEST = (
    _service("config-store"),
    _service("session-log", ["config-store"], ticks=20, acquire=True),
    _service("receipt-writer", ["archive-pool"], ticks=35, acquire=True),
)

_HOST_ORDER = (
    "token-issuer", "lookup-index", "metrics-sink", "pool-handle", "document-store",
    "invoice-writer", "config-store", "ledger-pool", "session-cache", "quote-service",
)
_ROTATED_ORDER = (
    "config-store", "quote-service", "invoice-writer", "lookup-index", "ledger-pool",
    "pool-handle", "session-cache", "token-issuer", "metrics-sink", "document-store",
)


def _release_scenes() -> list[dict[str, Any]]:
    settled = _scene(
        "settlements-boot",
        SETTLEMENTS,
        [BRING_UP, BRING_UP, *_probes(*SETTLEMENTS_STARTED, "config-store")],
        timers=[{"at": 5, "resolve": "session-cache"}, {"at": 5, "resolve": "config-store"}],
    )
    failing = _scene("settlements-lease-refused", SETTLEMENTS_FAILING, [BRING_UP, BRING_UP])
    typo = _scene(
        "settlements-manifest-typo",
        TYPO_MANIFEST,
        [
            BRING_UP,
            {"op": "amend", "name": "queue-reader", "depends_on": ["audit-trail"]},
            BRING_UP,
            *_probes("audit-trail", "queue-reader", "dispatch-log"),
        ],
    )
    unknown = _scene(
        "settlements-missing-edge",
        UNKNOWN_MANIFEST,
        [
            BRING_UP,
            {"op": "amend", "name": "receipt-writer", "depends_on": ["config-store"]},
            BRING_UP,
            *_probes("session-log", "receipt-writer"),
        ],
    )
    one_slot = _scene(
        "settlements-single-slot",
        _reorder(SETTLEMENTS, _HOST_ORDER),
        [BRING_UP],
        config=_config(max_parallel_starts=1, deploy_window_ticks=600),
    )
    wide = _scene(
        "settlements-wide-open",
        _reorder(SETTLEMENTS, _ROTATED_ORDER),
        [BRING_UP],
        config=_config(max_parallel_starts=8, deploy_window_ticks=300),
    )
    return [settled, failing, typo, unknown, one_slot, wide]


MORNING = (
    _service("app-settings"),
    _service("request-log", ["app-settings"], ticks=40, acquire=True),
    _service("billing-pool", ["app-settings"], ticks=120, acquire=True,
             returns="billing-pool/ready"),
    _service("rate-limiter", ["app-settings"], ticks=30, acquire=True),
    _service("mail-queue", ["app-settings"], ticks=90, acquire=True),
    _service("price-cache", ["app-settings"], ticks=60, acquire=True),
    _service("price-index", ["price-cache"], ticks=50, acquire=True),
)

WAVE = (
    _service("app-settings"),
    _service("shard-router", ["app-settings"], ticks=25, acquire=True,
             session_once="the warehouse will not open a second session for this process",
             stop_error="the close receipt could not be written"),
    _service("settlement-pool", ["app-settings"], ticks=45, acquire=True),
    _service("pool-lease", ["settlement-pool"]),
    _service("batch-writer", ["pool-lease"], ticks=20, acquire=True, fails_after=10,
             error="the ledger refused the write lease"),
    _service("archive-store", ["pool-lease"], ticks=130, acquire=True),
    _service("audit-shipper", ["shard-router"], ticks=35, acquire=True, guard="shard-router"),
)

DIGEST = (
    _service("app-settings"),
    _service("digest-service", ["stats-view"], ticks=30, acquire=True),
    _service("stats-pool", ["app-settings"], ticks=70, acquire=True),
    _service("stats-view", ["stats-pool"]),
    _service("session-store", ["app-settings"], ticks=40, acquire=True),
)

RELAY = (
    _service("app-settings"),
    _service("session-log", ["app-settings"], ticks=15, acquire=True),
    _service("event-relay", ["notice-log"], ticks=30, acquire=True),
    _service("notice-log", ["event-relay"], ticks=20, acquire=True),
    _service("digest-mailer", ["event-relay"], ticks=25, acquire=True),
)


def _cold_start_scene() -> dict[str, Any]:
    return _scene(
        "morning-cold-start",
        MORNING,
        [BRING_UP, BRING_UP, *_probes("billing-pool", "price-index", "app-settings")],
    )


def _wave_scene() -> dict[str, Any]:
    return _scene(
        "settlement-wave-failure",
        WAVE,
        [BRING_UP, BRING_UP],
        config=_config(max_parallel_starts=4, deploy_window_ticks=400),
    )


def _digest_scene() -> dict[str, Any]:
    return _scene(
        "digest-cold-start",
        DIGEST,
        [BRING_UP, *_probes("digest-service", "stats-pool", "app-settings")],
        timers=[{"at": 10, "resolve": "stats-pool"}],
    )


def _relay_scene() -> dict[str, Any]:
    return _scene(
        "manifest-typo-retry",
        RELAY,
        [
            BRING_UP,
            {"op": "amend", "name": "notice-log", "depends_on": ["app-settings"]},
            BRING_UP,
            *_probes("event-relay", "notice-log", "digest-mailer"),
        ],
    )


PUBLIC_PROGRAMS = {
    "cold-start": _cold_start_scene,
    "wave-failure": _wave_scene,
    "start-less-chain": _digest_scene,
    "typo-retry": _relay_scene,
}


def build_program(profile: str) -> dict[str, Any]:
    'Every scene one start-up review runs, in order.'

    if profile == "release":
        return {"profile": profile, "scenes": _release_scenes()}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown start-up profile: {profile}")
    return {"profile": profile, "scenes": [builder()]}


def manifest_edges(scene: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    'What each service in one scene declares it is built on.'

    return {
        str(entry["name"]): tuple(str(item) for item in entry.get("depends_on", ()))
        for entry in scene.get("manifest", ())
    }


def connecting(scene: Mapping[str, Any]) -> tuple[str, ...]:
    'The services of one scene that have a connect step, in manifest order.'

    return tuple(str(entry["name"]) for entry in scene.get("manifest", ()) if "start" in entry)


def serial_ticks(scene: Mapping[str, Any]) -> int:
    'How long the scene takes when every connect step waits for the last.'

    return sum(
        int(dict(entry["start"]).get("ticks", 0))
        for entry in scene.get("manifest", ())
        if "start" in entry
    )
