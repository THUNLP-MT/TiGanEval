'Deterministic gateway traffic: client topologies, upstream schedules, call schedules.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

def origin_key(url_text: str) -> str:
    'The origin a URL belongs to, with the port its scheme implies.'
    scheme, _, rest = str(url_text).partition("://")
    host, colon, port = rest.partition("/")[0].partition(":")
    number = port if colon else ("443" if scheme.lower() == "https" else "80")
    return f"{scheme.lower()}://{host.lower()}:{number}"


FAIL: Mapping[str, Any] = {"status": 503, "cost_ms": 200.0}
NO_ANSWER: Mapping[str, Any] = {"kind": "error", "cost_ms": 200.0}
GONE: Mapping[str, Any] = {"status": 404, "cost_ms": 40.0}
GOOD: Mapping[str, Any] = {"status": 200, "body": '{"ok": true}', "cost_ms": 20.0}
TORN: Mapping[str, Any] = {"status": 200, "body": '{"ok"', "cost_ms": 20.0}

def _run(steps: Sequence[Mapping[str, Any]], tail: Mapping[str, Any]) -> list[dict[str, Any]]:
    'A schedule that answers `steps` in order and then `tail` for ever.'
    return [dict(step) for step in steps] + [dict(tail)]

def _client(name: str, **config: Any) -> dict[str, Any]:
    return {"op": "client", "name": name, "label": f"client-{name}", "config": {"name": name, **config}}

def _derived(name: str, parent: str, **overrides: Any) -> dict[str, Any]:
    return {"op": "client", "name": name, "from": parent, "label": f"client-{name}",
            "overrides": {"name": name, **overrides}}

def _start(label: str, client: str, target: str, **options: Any) -> dict[str, Any]:
    return {"op": "start", "call": label, "label": label, "client": client, "target": target, **options}

def _call(label: str, client: str, target: str, **options: Any) -> list[dict[str, Any]]:
    return [_start(label, client, target, **options), {"op": "run", "call": label, "label": label}]

def _step(label: str, op: str = "step") -> dict[str, Any]:
    return {"op": op, "call": label, "label": f"{op}-{label}"}

def _finish(label: str) -> dict[str, Any]:
    return _step(label, "run")

def _at(ms: float) -> dict[str, Any]:
    return {"op": "clock", "to": float(ms), "label": f"clock-{int(ms)}"}

def _wait(ms: float) -> dict[str, Any]:
    return {"op": "advance", "ms": float(ms), "label": f"wait-{int(ms)}"}

def _phase(name: str, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**dict(op), "phase": name} for op in ops]


def _hosts(*names: str) -> tuple[str, ...]:
    return tuple(f"https://{name}.internal" for name in names)

BILLING, ROSTER, DISPATCH, WAREHOUSE, LEDGER = _hosts(
    "billing-api", "roster-api", "dispatch-api", "warehouse-api", "ledger-api")
PICK_HUB, PAIR_HUB, PARCEL_HUB = _hosts("pick-hub", "pair-hub", "parcel-hub")
CATALOG, LOOKUP, PRICING, FEED, NOTIFY, MESH = _hosts(
    "catalog-api", "lookup-api", "pricing-api", "feed-api", "notify-api", "mesh-api")
TRACKING, = _hosts("tracking-api")
WAREHOUSE_ADMIN = f"{WAREHOUSE}:8443"
SCHEME_TLS = "https://dual-scheme.internal:8443"
SCHEME_CLEAR = "http://dual-scheme.internal:8443"


HEALTHY_ORIGIN_BASES = (ROSTER, DISPATCH, WAREHOUSE_ADMIN)
HEALTHY_ORIGINS = tuple(origin_key(base) for base in HEALTHY_ORIGIN_BASES)

RELEASE_UPSTREAMS: Mapping[str, Any] = {
    **{origin_key(base): [dict(GOOD)] for base in HEALTHY_ORIGIN_BASES},
    origin_key(SCHEME_CLEAR): [dict(GOOD)],
    origin_key(BILLING): _run([FAIL] * 8, GOOD),
    origin_key(WAREHOUSE): _run([FAIL] * 8, GOOD),
    origin_key(LEDGER): _run([FAIL] * 30, GOOD),
    origin_key(PICK_HUB): _run([FAIL, FAIL, FAIL, GOOD, GOOD, GOOD, FAIL], GOOD),
    origin_key(PAIR_HUB): _run([FAIL] * 4, GOOD),
    origin_key(PARCEL_HUB): _run([FAIL, FAIL, FAIL, TORN], GOOD),
    origin_key(CATALOG): _run([FAIL, GONE, FAIL, GONE, FAIL, GONE, FAIL, GONE], GOOD),
    origin_key(LOOKUP): [dict(GONE)],
    origin_key(PRICING): [dict(FAIL)],
    origin_key(FEED): _run([FAIL, FAIL, GONE, FAIL, FAIL], GOOD),
    origin_key(NOTIFY): _run([FAIL, FAIL], GOOD),
    origin_key(MESH): _run([FAIL] * 8, GOOD),
    origin_key(SCHEME_TLS): _run([FAIL] * 8, GOOD),
    origin_key(TRACKING): _run([NO_ANSWER, NO_ANSWER], GOOD),
}

def _topology_ops() -> list[dict[str, Any]]:
    'One host unwell while the rest of the fleet works, reached by every caller     shape and through four clients built from one base client.'
    ops = [
        _at(0.0),
        _client("edge", threshold=5, cooldown_ms=30000.0, half_open_max=1),
        _derived("stock", "edge", base_url=WAREHOUSE),
        _derived("filing", "edge", base_url=f"{WAREHOUSE}/filing"),
        _derived("estate", "edge", base_url=WAREHOUSE_ADMIN),
    ]
    charge, shifts, plan, stock = (f"{BILLING}/v2/charge", f"{ROSTER}/shifts",
                                   f"{DISPATCH}/plan", f"{WAREHOUSE}/v3/stock")
    for row in (
        ("charge-1", "edge", charge), ("roster-1", "edge", shifts),
        ("charge-2", "edge", charge), ("charge-3", "edge", charge),
        ("dispatch-1", "edge", plan), ("charge-4", "edge", charge),
        ("charge-5", "edge", charge), ("charge-after-five", "edge", charge),
        ("roster-2", "edge", shifts), ("stock-1", "edge", stock),
        ("stock-2", "edge", stock, {"shape": "url"}), ("stock-3", "stock", "/v3/stock"),
        ("pallets-1", "stock", "/v3/pallets"), ("filing-1", "filing", "/daily"),
        ("estate-health", "estate", "/health"),
        ("stock-after-five", "edge", stock, {"shape": "request"}),
        ("dispatch-2", "edge", plan),
    ):
        ops += _call(row[0], row[1], row[2], **(row[3] if len(row) > 3 else {}))
    for index in range(1, 6):
        ops += _call(f"scheme-tls-{index}", "edge", f"{SCHEME_TLS}/health")
    ops += _call("scheme-tls-after-five", "edge", f"{SCHEME_TLS}/health")
    ops += _call("scheme-clear-after-five", "edge", f"{SCHEME_CLEAR}/health")
    return ops

def _retry_ops() -> list[dict[str, Any]]:
    'One upstream failing under a client that retries inside every call.'
    ops = [_at(100000.0), _client("batch", base_url=LEDGER, threshold=5, cooldown_ms=30000.0, half_open_max=1)]
    for label, retries in (("post-1", 2), ("post-2", 2), ("post-after-two", 0),
                           ("post-3", 2), ("post-4", 2), ("post-after-five", 0)):
        ops += _call(label, "batch", "/post", retries=retries)
    ops += [_wait(29995.0)] + _call("post-just-inside", "batch", "/post")
    return ops

def _recovery_ops() -> list[dict[str, Any]]:
    'Three ways an upstream is asked whether it has come back.'
    ops = [
        _at(200000.0),
        _client("pickers", base_url=PICK_HUB, threshold=3, cooldown_ms=10000.0, half_open_max=1),
        _client("pairs", base_url=PAIR_HUB, threshold=3, cooldown_ms=10000.0, half_open_max=2),
        _client("parcels", base_url=PARCEL_HUB, threshold=3, cooldown_ms=10000.0, half_open_max=1),
    ]
    for index in (1, 2, 3):
        ops += _call(f"pick-{index}", "pickers", "/pick")
    burst = [f"pick-wave-{index}" for index in range(1, 7)]
    ops += [_wait(10005.0)] + [_start(label, "pickers", "/pick") for label in burst]
    ops += [_step(label) for label in burst] * 2
    ops += [_finish(label) for label in burst]
    normal = ("pick-normal-1", "pick-normal-2")
    ops += [_start(label, "pickers", "/pick") for label in normal]
    ops += [_step(label) for label in normal] * 2
    ops += [_finish(label) for label in normal]
    ops += _call("pick-new-failure", "pickers", "/pick")
    ops += _call("pick-after-new-failure", "pickers", "/pick")
    for index in (1, 2, 3):
        ops += _call(f"pair-{index}", "pairs", "/roster")
    ops += [_wait(10005.0), _start("pair-wave-1", "pairs", "/roster", retries=1),
            _start("pair-wave-2", "pairs", "/roster"),
            _step("pair-wave-1"), _step("pair-wave-2"), _step("pair-wave-1"),
            _start("pair-wave-3", "pairs", "/roster"), _step("pair-wave-3"),
            _finish("pair-wave-2"), _finish("pair-wave-1"),
            _finish("pair-wave-3")]
    for index in (1, 2, 3):
        ops += _call(f"parcel-{index}", "parcels", "/scan")
    ops += [_wait(10005.0)] + _call("parcel-wave-1", "parcels", "/scan", transform="json")
    ops += [_wait(5000.0)] + _call("parcel-inside-new-wait", "parcels", "/scan")
    ops += [_wait(5050.0)] + _call("parcel-after-wait", "parcels", "/scan")
    return ops

def _status_ops() -> list[dict[str, Any]]:
    'Upstreams that answer three different ways about themselves.'
    ops = [
        _at(400000.0),
        _client("catalog", base_url=CATALOG, threshold=3, cooldown_ms=20000.0, half_open_max=1),
        _client("lookup", base_url=LOOKUP, threshold=3, cooldown_ms=20000.0, half_open_max=1),
        _client("pricing", base_url=PRICING, threshold=3, cooldown_ms=20000.0, half_open_max=1),
        _client("feed", base_url=FEED, threshold=2, cooldown_ms=8000.0, half_open_max=1),
        _client("tracking", base_url=TRACKING, threshold=2, cooldown_ms=8000.0, half_open_max=1),
    ]
    for labels, client, path, options in (
        ([f"catalog-{i}" for i in range(1, 6)] + ["catalog-after-three"], "catalog", "/item", {}),
        ([f"lookup-{i}" for i in range(1, 5)] + ["lookup-after-four"], "lookup", "/charge", {}),
        ([f"pricing-{i}" for i in range(1, 4)] + ["pricing-after-three"], "pricing", "/quote",
         {"ignore_errors": True}),
        (["feed-1", "feed-2"], "feed", "/poll", {}),
    ):
        for label in labels:
            ops += _call(label, client, path, **options)


    ops.append(_wait(8005.0))
    for label in ("feed-probe", "feed-after-probe", "feed-after-that"):
        ops += _call(label, "feed", "/poll")
    for label in ("tracking-1", "tracking-2", "tracking-after-two"):
        ops += _call(label, "tracking", "/poll")
    return ops

def _block_ops() -> list[dict[str, Any]]:
    'Steady traffic against an upstream the gateway has stopped calling.'
    ops = [
        _at(500000.0),
        _client("notify", base_url=NOTIFY, threshold=2, cooldown_ms=20000.0, half_open_max=1),
        _client("mesh", base_url=MESH, threshold=2, cooldown_ms=20000.0, half_open_max=1),
    ]
    ops += _call("notify-1", "notify", "/send") + _call("notify-2", "notify", "/send")
    for index in range(1, 13):
        ops.append(_wait(1000.0))
        ops += _call(f"notify-inside-{index}", "notify", "/send")
    ops.append(_wait(8001.0))
    ops += _call("notify-just-outside", "notify", "/send")
    for index in (1, 2, 3):
        ops += _call(f"mesh-internal-{index}", "mesh", "/sync", guarded=False)
    ops += _call("mesh-guarded-1", "mesh", "/sync") + _call("mesh-guarded-2", "mesh", "/sync")
    return ops + _call("mesh-health", "mesh", "/health", guarded=False)


PAYMENTS, CART, SEARCH, INVENTORY, POSTINGS, REPORTS, SHELVES, EXPORTS = _hosts(
    "payments", "cart-api", "search", "inventory", "ledger", "reports", "catalog", "exports")
ROUTING, TICKETS = _hosts("routing", "tickets")
SEARCH_ADMIN = f"{SEARCH}:9443"
MIGRATION_TLS = "https://migration.internal:8080"
MIGRATION_CLEAR = "http://migration.internal:8080"

def _program(upstreams: Mapping[str, Any], phase: str, ops: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"start_ms": 0.0, "upstreams": dict(upstreams), "operations": _phase(phase, ops)}

def _checkout_program() -> dict[str, Any]:
    ops = [_at(0.0), _client("edge", threshold=5, cooldown_ms=30000.0, half_open_max=1)]
    for index in range(1, 9):
        ops += _call(f"charge-{index}", "edge", f"{PAYMENTS}/v2/charge")
        if index % 3 == 0:
            ops += _call(f"cart-{index}", "edge", f"{CART}/basket")
    ops += [_wait(31000.0)] + _call("charge-after-the-wait", "edge", f"{PAYMENTS}/v2/charge")
    upstreams = {origin_key(PAYMENTS): _run([NO_ANSWER] * 12, GOOD), origin_key(CART): [dict(GOOD)]}
    return _program(upstreams, "checkout", ops)

def _fleet_program() -> dict[str, Any]:
    ops = [
        _at(0.0),
        _client("core", threshold=4, cooldown_ms=30000.0, half_open_max=1),
        _derived("payments", "core", base_url=PAYMENTS),
        _derived("search", "core", base_url=SEARCH),
        _derived("inventory", "core", base_url=INVENTORY),
        _derived("searchops", "core", base_url=SEARCH_ADMIN),
    ]
    query = f"{SEARCH}/query"
    for row in (
        ("query-1", "core", query), ("charge-1", "payments", "/v2/charge"),
        ("query-2", "core", query, {"shape": "url"}), ("stock-1", "inventory", "/stock"),
        ("query-3", "search", "/query"), ("index-health", "searchops", "/health"),
        ("query-4", "core", query, {"shape": "request"}), ("query-5", "search", "/query"),
        ("charge-2", "payments", "/v2/charge"), ("stock-2", "inventory", "/stock"),
    ):
        ops += _call(row[0], row[1], row[2], **(row[3] if len(row) > 3 else {}))
    for index in range(1, 5):
        ops += _call(f"migration-tls-{index}", "core", f"{MIGRATION_TLS}/health")
    ops += _call("migration-tls-after-four", "core", f"{MIGRATION_TLS}/health")
    ops += _call("migration-clear-after-four", "core", f"{MIGRATION_CLEAR}/health")
    upstreams = {origin_key(SEARCH): _run([FAIL] * 10, GOOD),
                 origin_key(MIGRATION_TLS): _run([FAIL] * 8, GOOD),
                 **{origin_key(base): [dict(GOOD)] for base in
                    (SEARCH_ADMIN, PAYMENTS, INVENTORY, MIGRATION_CLEAR)}}
    return _program(upstreams, "fleet", ops)

def _ledger_program() -> dict[str, Any]:
    ops = [_at(0.0), _client("posting", base_url=POSTINGS, threshold=3, cooldown_ms=15000.0, half_open_max=1)]
    for index in (1, 2, 3):
        ops += _call(f"post-{index}", "posting", "/post", retries=2)
    for index in (1, 2, 3, 4):
        ops.append(_wait(2000.0))
        ops += _call(f"post-inside-{index}", "posting", "/post")
        if index % 2 == 0:
            ops += _call(f"ledger-health-{index}", "posting", "/health", guarded=False)
    ops += [_wait(8000.0)] + _call("post-after-the-wait", "posting", "/post")
    return _program({origin_key(POSTINGS): _run([FAIL] * 14, GOOD)}, "ledger", ops)

def _recovery_program() -> dict[str, Any]:
    ops = [
        _at(0.0),
        _client("workers", base_url=REPORTS, threshold=3, cooldown_ms=12000.0, half_open_max=1),
        _client("shelves", base_url=SHELVES, threshold=3, cooldown_ms=12000.0, half_open_max=1),
        _client("exports", base_url=EXPORTS, threshold=3, cooldown_ms=12000.0, half_open_max=1),
        _client("search-recovery", base_url=SEARCH, threshold=3, cooldown_ms=12000.0, half_open_max=2),
    ]
    for index in (1, 2, 3):
        ops += _call(f"report-{index}", "workers", "/render")
    ops.append(_wait(12005.0))
    wave = [f"report-wave-{index}" for index in range(1, 6)]
    ops += [_start(label, "workers", "/render") for label in wave]
    ops += [_step(label) for label in wave] * 2
    ops += [_finish(label) for label in wave]
    normal = ("report-normal-1", "report-normal-2")
    ops += [_start(label, "workers", "/render") for label in normal]
    ops += [_step(label) for label in normal] * 2
    ops += [_finish(label) for label in normal]
    ops += _call("report-strict", "workers", "/render", transform="json")
    ops += _call("report-after-bad-body", "workers", "/render")
    ops += [_wait(12050.0)] + _call("report-after-the-wait", "workers", "/render")


    for index in (1, 2, 3):
        ops += _call(f"export-{index}", "exports", "/bundle")
    ops += [_wait(12005.0)] + _call("export-probe", "exports", "/bundle", transform="json")
    ops += [_wait(6000.0)] + _call("export-inside-new-wait", "exports", "/bundle")
    ops += [_wait(6050.0)] + _call("export-after-the-wait", "exports", "/bundle")
    for index in (1, 2, 3, 4, 5):
        ops += _call(f"shelf-{index}", "shelves", "/item", ignore_errors=index == 3)
    ops += _call("shelf-after-the-mix", "shelves", "/item")
    for index in (1, 2, 3):
        ops += _call(f"search-{index}", "search-recovery", "/query")
    pair = ("search-probe-1", "search-probe-2")
    ops += [_wait(12005.0)] + [_start(label, "search-recovery", "/query") for label in pair]
    ops += [_step(label) for label in pair] * 2
    ops += [_finish(label) for label in pair]
    upstreams = {origin_key(REPORTS): _run([FAIL, FAIL, FAIL, GOOD, GOOD, GOOD, TORN], GOOD),
                 origin_key(EXPORTS): _run([FAIL, FAIL, FAIL, TORN], GOOD),
                 origin_key(SHELVES): _run([FAIL, GONE, FAIL, GONE, FAIL, GONE], GOOD),
                 origin_key(SEARCH): _run([FAIL, FAIL, FAIL, GOOD, GOOD], GOOD)}
    return _program(upstreams, "recovery", ops)

def _reroute_program() -> dict[str, Any]:
    'A night of two hosts flapping, timed around the wait each client is set to.'
    ops = [
        _at(0.0),
        _client("routing", base_url=ROUTING, threshold=3, cooldown_ms=10000.0, half_open_max=1),
        _client("tickets", base_url=TICKETS, threshold=2, cooldown_ms=8000.0, half_open_max=1),
    ]
    for index in (1, 2, 3):
        ops += _call(f"route-{index}", "routing", "/plan", retries=1)
    ops += [_wait(9800.0)] + _call("route-inside-the-wait", "routing", "/plan")
    ops += [_wait(400.0)] + _call("route-after-the-wait", "routing", "/plan", retries=1)
    ops += [_wait(10050.0)] + _call("route-last-of-the-night", "routing", "/plan")
    for index in (1, 2):
        ops += _call(f"ticket-{index}", "tickets", "/assign")
    ops += [_wait(8005.0)] + _call("ticket-after-the-wait", "tickets", "/assign")
    ops += _call("ticket-after-that", "tickets", "/assign")
    ops += [_wait(1000.0)] + _call("ticket-straight-after", "tickets", "/assign")
    ops += [_wait(8005.0)] + _call("ticket-last-of-the-night", "tickets", "/assign")
    upstreams = {origin_key(ROUTING): _run([FAIL] * 8, GOOD),
                 origin_key(TICKETS): _run([FAIL, FAIL, GONE, FAIL], GOOD)}
    return _program(upstreams, "reroute", ops)

PUBLIC_PROGRAMS = {"checkout": _checkout_program, "fleet": _fleet_program,
                   "ledger": _ledger_program, "recovery": _recovery_program,
                   "reroute": _reroute_program}
RELEASE_PHASES = (("topology", _topology_ops), ("retry", _retry_ops),
                  ("recovery", _recovery_ops), ("status", _status_ops), ("block", _block_ops))

def build_program(profile: str) -> dict[str, Any]:
    'The upstream schedule and the schedule of calls for one stretch of traffic.'
    if profile == "release":
        operations: list[dict[str, Any]] = []
        for name, builder in RELEASE_PHASES:
            operations.extend(_phase(name, builder()))
        return {"start_ms": 0.0, "upstreams": dict(RELEASE_UPSTREAMS), "operations": operations}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown gateway traffic profile: {profile}")
    return builder()

def client_configs(program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    'Every client the program builds, with the settings it ends up holding.'
    configs: dict[str, dict[str, Any]] = {}
    for op in program.get("operations", ()):
        if str(op.get("op")) != "client":
            continue
        parent = op.get("from")
        base = dict(configs.get(str(parent), {})) if parent else {}
        base.update(dict(op.get("config") or op.get("overrides") or {}))
        configs[str(op["name"])] = base
    return configs
