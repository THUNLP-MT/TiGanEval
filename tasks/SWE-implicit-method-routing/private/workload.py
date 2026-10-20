'Deterministic portal traffic: how each surface is assembled and what is sent at it.'

from __future__ import annotations

import json
from typing import Any, Mapping

def _payload(kind: str, size: int) -> str:
    return json.dumps({"kind": kind, "chunk": "x" * int(size)})

NOT_FOUND = json.dumps({"detail": "no such record"})
BUNDLE, MANIFEST, FEED = _payload("bundle", 480), _payload("manifest", 96), _payload("feed", 64)
EXPORT, DIGEST, ORDER = _payload("export", 640), _payload("digest", 128), _payload("order", 72)


INDEX_SIZE, RELEASE_INDEX_SIZE = "97312", "58204"

def _service(**settings: Any) -> dict[str, Any]:
    return {"op": "service", "settings": dict(settings)}

def _router(name: str, **settings: Any) -> dict[str, Any]:
    return {"op": "router", "name": name, "settings": dict(settings)}

def _route(
    router: str, method: str, path: str, name: str, *, answers: Mapping[str, Any] | None = None,
    settings: Mapping[str, Any] | None = None, **spec: Any,
) -> dict[str, Any]:
    return {
        "op": "route", "router": router, "method": method, "path": path, "name": name,
        "summary": spec.pop("summary", f"{name.replace('_', ' ')}"),
        "guard": spec.pop("guard", ""), "cost": int(spec.pop("cost", 1)),
        "params": dict(spec.pop("params", {})), "answers": dict(answers or {"-": {"status": 200}}),
        "settings": dict(settings or {}),
    }

def _include(router: str, prefix: str, into: str = "app", **settings: Any) -> dict[str, Any]:
    return {"op": "include", "router": router, "into": into, "prefix": prefix,
            "settings": dict(settings)}

def _ask(label: str, method: str, path: str, token: str | None = None,
         kind: str = "request") -> dict[str, Any]:
    return {"label": label, "method": method, "path": path, "token": token, "kind": kind}

def _sweep(prefix: str, path: str) -> list[dict[str, Any]]:
    'One request per method at one path, so the routable set is readable.'
    return [_ask(f"{prefix}-{method.lower()}", method, path)
            for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE")]

def _pairs(rows: Any) -> list[dict[str, Any]]:
    'A size probe beside the fetch it decides on, for each row given.'
    return [ask for label, path, token in rows
            for ask in (_ask(f"fetch-{label}", "GET", path, token),
                        _ask(f"probe-{label}", "HEAD", path, token))]

ACME = "acme-live"


def _probes_assembly() -> dict[str, Any]:
    'A partner mirror sizing what it is about to pull.'

    steps = [
        _service(auto_head=True, auto_options=False),
        _router("deliveries"), _router("standby"),
        _route("deliveries", "GET", "/deliveries/{delivery_id}", "read_delivery", guard="partner",
               cost=40, params={"delivery_id": "whole"},
               answers={"7741": {"status": 200, "body": BUNDLE}, "*": {"status": 404, "body": NOT_FOUND}}),
        _route("deliveries", "GET", "/manifests", "list_manifests", cost=5,
               answers={"-": {"status": 200, "body": MANIFEST}}),
        _route("deliveries", "GET", "/rollup", "settle_rollup", cost=90,
               answers={"-": {"status": 200, "body": DIGEST}}, settings={"auto_head": False}),
        _route("standby", "GET", "/rollup", "read_rollup_copy", cost=3,
               answers={"-": {"status": 200, "body": FEED}}),
        _include("deliveries", "/v2"), _include("standby", "/v2"),
    ]
    requests = _pairs((
        ("open", "/v2/manifests", ACME), ("sized", "/v2/deliveries/7741", ACME),
        ("locked", "/v2/deliveries/7741", None), ("missing", "/v2/deliveries/9002", ACME),
        ("odd", "/v2/deliveries/spring", ACME), ("rollup", "/v2/rollup", ACME)))
    return {"name": "probes", "steps": steps, "requests": requests}

def _sweep_assembly() -> dict[str, Any]:
    'One path served by two routers, one of whose operations is unpublished.'

    steps = [
        _service(auto_head=True, auto_options=True),
        _router("catalogue"), _router("stewardship"),
        _route("catalogue", "GET", "/deliveries/{delivery_id}", "read_delivery", cost=12,
               params={"delivery_id": "whole"}, answers={"*": {"status": 200, "body": BUNDLE}}),
        _route("catalogue", "PUT", "/deliveries/{delivery_id}", "replace_delivery", guard="partner",
               cost=20, params={"delivery_id": "whole"}),
        _route("stewardship", "DELETE", "/deliveries/{delivery_id}", "retire_delivery",
               guard="steward", cost=8, params={"delivery_id": "whole"}),
        _route("stewardship", "PATCH", "/deliveries/{delivery_id}", "repair_delivery",
               guard="steward", cost=8, params={"delivery_id": "whole"},
               settings={"in_catalogue": False}),
        _include("catalogue", "/v3"), _include("stewardship", "/v3"),
        _include("catalogue", "/v4"),
    ]
    requests = (
        _sweep("sweep", "/v3/deliveries/7741")
        + [_ask("summary-shared", "OPTIONS", "/v3/deliveries/7741", ACME)]
        + _sweep("later", "/v4/deliveries/7741")
        + [_ask("summary-later", "OPTIONS", "/v4/deliveries/7741", ACME)]
    )
    return {"name": "sweep", "steps": steps, "requests": requests}

def _mounts_assembly() -> dict[str, Any]:
    'One router mounted twice, with the two mounts asking for different things.'

    steps = [
        _service(),
        _router("reports", auto_head=True, auto_options=False),
        _route("reports", "GET", "/summary", "read_summary", cost=6,
               answers={"-": {"status": 200, "body": DIGEST}}),
        _route("reports", "GET", "/ledger", "rebuild_ledger", cost=90,
               answers={"-": {"status": 200, "body": DIGEST}}, settings={"auto_head": False}),
        _route("reports", "POST", "/ledger", "queue_ledger", guard="steward", cost=15),
        _include("reports", "/api/v1", auto_options=True),
        _include("reports", "/internal"),
    ]
    requests = [_ask(f"{mount}-{page}-{kind}", method, f"{prefix}/{page}", ACME)
                for mount, prefix in (("api", "/api/v1"), ("internal", "/internal"))
                for page in ("summary", "ledger")
                for kind, method in (("probe", "HEAD"), ("list", "OPTIONS"))]
    return {"name": "mounts", "steps": steps, "requests": requests}

def _mirror_routes(router: str) -> list[dict[str, Any]]:
    return [
        _route(router, "GET", "/bundles/{bundle_id}", "build_bundle", guard="partner", cost=60,
               params={"bundle_id": "whole"}, answers={"*": {"status": 200, "body": BUNDLE}}),
        _route(router, "GET", "/bundles", "list_bundles", cost=4,
               answers={"-": {"status": 200, "body": MANIFEST}}),
        _route(router, "GET", "/receipts/{receipt_id}", "read_receipt", cost=7,
               params={"receipt_id": "whole"}, answers={"*": {"status": 200, "body": MANIFEST}}),
    ]

def _mirror_probe_routes(router: str) -> list[dict[str, Any]]:
    return [
        _route(router, "HEAD", "/bundles/{bundle_id}", "size_bundle", guard="partner", cost=2,
               params={"bundle_id": "whole"},
               answers={"*": {"status": 200, "headers": {"content-length": RELEASE_INDEX_SIZE}}}),
        _route(router, "OPTIONS", "/bundles", "bundle_terms", cost=1,
               answers={"-": {"status": 200, "body": json.dumps(
                   {"path": "/mirror/bundles", "methods": ["GET", "OPTIONS"], "operations": {},
                    "contact": "partner-desk@portal.example"}, sort_keys=True)}}),
    ]

def _explicit_assemblies() -> list[dict[str, Any]]:
    'The same mirror surface assembled in two orders.'

    first = {"name": "mirror-probes-first", "steps": [
        _service(auto_head=True, auto_options=True), _router("mirror"),
        *_mirror_probe_routes("mirror"), *_mirror_routes("mirror"), _include("mirror", "/mirror")]}
    last = {"name": "mirror-probes-last", "steps": [
        _service(auto_head=True, auto_options=True), _router("reads"), _router("probes"),
        *_mirror_routes("reads"), *_mirror_probe_routes("probes"),
        _include("reads", "/mirror"), _include("probes", "/mirror")]}
    for assembly in (first, last):
        assembly["requests"] = [
            _ask("probe-bundle", "HEAD", "/mirror/bundles/5501", ACME),
            _ask("list-bundles", "OPTIONS", "/mirror/bundles", ACME),
            _ask("probe-receipt", "HEAD", "/mirror/receipts/88", ACME),
        ]
    return [first, last]

def _usage_assembly() -> dict[str, Any]:
    'Two partner mounts of one feed router, and a week of their traffic.'

    steps = [
        _service(auto_head=True, auto_options=True),
        _router("feeds"), _router("acme_desk"),
        _route("feeds", "GET", "/feed", "read_feed", cost=3,
               answers={"-": {"status": 200, "body": FEED}}),
        _route("feeds", "GET", "/feed/{item_id}", "read_item", cost=4,
               params={"item_id": "whole"}, answers={"*": {"status": 200, "body": FEED}}),
        _route("acme_desk", "HEAD", "/feed", "size_feed", cost=1,
               answers={"-": {"status": 200, "headers": {"content-length": RELEASE_INDEX_SIZE}}}),
        _include("feeds", "/partner/acme"), _include("acme_desk", "/partner/acme"),
        _include("feeds", "/partner/borealis"),
    ]
    borealis = "borealis-live"
    requests = [
        _ask("acme-feed-probe", "HEAD", "/partner/acme/feed", ACME),
        _ask("acme-item-probe", "HEAD", "/partner/acme/feed/12", ACME),
        _ask("acme-item-probe-again", "HEAD", "/partner/acme/feed/13", ACME),
        _ask("acme-feed-list", "OPTIONS", "/partner/acme/feed", ACME),
        _ask("acme-item-read", "GET", "/partner/acme/feed/12", ACME),
        _ask("acme-archive-probe", "HEAD", "/partner/acme/archive", ACME),
        _ask("borealis-feed-probe", "HEAD", "/partner/borealis/feed", borealis),
        _ask("borealis-item-probe", "HEAD", "/partner/borealis/feed/12", borealis),
        _ask("borealis-feed-list", "OPTIONS", "/partner/borealis/feed", borealis),
        _ask("borealis-feed-list-again", "OPTIONS", "/partner/borealis/feed", borealis),
        _ask("borealis-stream-open", "HEAD", "/partner/borealis/feed/12", borealis, "upgrade")]
    return {"name": "usage", "steps": steps, "requests": requests, "snapshot_probe": True}


def _mirror_log_record() -> dict[str, Any]:
    steps = [
        _service(auto_head=True, auto_options=False),
        _router("exports"),
        _route("exports", "GET", "/exports/{export_id}", "read_export", guard="partner", cost=55,
               params={"export_id": "whole"},
               answers={"4410": {"status": 200, "body": EXPORT}, "*": {"status": 404, "body": NOT_FOUND}}),
        _route("exports", "GET", "/schedules", "list_schedules", cost=4,
               answers={"-": {"status": 200, "body": MANIFEST}}),
        _include("exports", "/v1"),
    ]
    requests = _pairs((
        ("export", "/v1/exports/4410", ACME), ("schedules", "/v1/schedules", ACME),
        ("locked", "/v1/exports/4410", None), ("gone", "/v1/exports/9999", ACME),
        ("odd", "/v1/exports/autumn", ACME)))
    return {"name": "mirror-probe-log", "steps": steps, "requests": requests}

def _method_sweep_record() -> dict[str, Any]:
    steps = [
        _service(auto_head=True, auto_options=True),
        _router("orders"), _router("backoffice"),
        _route("orders", "GET", "/orders/{order_id}", "read_order", cost=9,
               params={"order_id": "whole"}, answers={"*": {"status": 200, "body": ORDER}}),
        _route("orders", "POST", "/orders", "place_order", guard="partner", cost=11),
        _route("orders", "OPTIONS", "/orders", "order_terms", cost=1,
               answers={"-": {"status": 200, "body": json.dumps(
                   {"path": "/v1/orders", "methods": ["POST", "OPTIONS"], "operations": {},
                    "contact": "partner-desk@portal.example"}, sort_keys=True)}}),
        _route("backoffice", "DELETE", "/orders/{order_id}", "cancel_order", guard="steward",
               cost=6, params={"order_id": "whole"}),
        _route("backoffice", "PATCH", "/orders/{order_id}", "repair_order", guard="steward",
               cost=6, params={"order_id": "whole"}, settings={"in_catalogue": False}),
        _include("orders", "/v1"), _include("backoffice", "/v1"),
    ]
    requests = _sweep("item", "/v1/orders/33") + _sweep("collection", "/v1/orders")
    return {"name": "method-sweep", "steps": steps, "requests": requests}

def _mounting_map_record() -> dict[str, Any]:
    steps = [
        _service(),
        _router("digests", in_catalogue=False, auto_head=True, auto_options=False),
        _route("digests", "GET", "/digest", "read_digest", cost=5,
               answers={"-": {"status": 200, "body": DIGEST}}, settings={"in_catalogue": True}),
        _route("digests", "GET", "/rebuild", "rebuild_digest", cost=120,
               answers={"-": {"status": 200, "body": DIGEST}}, settings={"auto_head": False}),
        _route("digests", "POST", "/rebuild", "queue_rebuild", guard="steward", cost=10),
        _include("digests", "/public", in_catalogue=True, auto_options=True),
        _include("digests", "/ops"),
    ]
    requests = [_ask(f"{mount}-{page}-{kind}", method, f"{prefix}/{page}", ACME)
                for mount, prefix in (("public", "/public"), ("ops", "/ops"))
                for page in ("digest", "rebuild")
                for kind, method in (("read", "GET"), ("probe", "HEAD"), ("list", "OPTIONS"))]
    return {"name": "mounting-map", "steps": steps, "requests": requests}

def _usage_week_record() -> dict[str, Any]:
    steps = [
        _service(auto_head=True, auto_options=True),
        _router("streams"),
        _route("streams", "GET", "/stream", "read_stream", cost=46,
               answers={"-": {"status": 200, "body": FEED}}),
        _route("streams", "GET", "/stream/{chunk_id}", "read_chunk", cost=4,
               params={"chunk_id": "whole"}, answers={"*": {"status": 200, "body": FEED}}),
        _route("streams", "HEAD", "/stream", "size_stream", cost=1,
               answers={"-": {"status": 200, "headers": {"content-length": INDEX_SIZE}}}),
        _include("streams", "/tenant/northwind"), _include("streams", "/tenant/pinehurst"),
    ]
    days = tuple(enumerate(("northwind", "pinehurst", "northwind", "pinehurst"), start=1))
    requests = [_ask(f"day{day}-{tenant}-{kind}", method,
                     f"/tenant/{tenant}/stream{suffix.format(day=day)}", ACME)
                for day, tenant in days
                for kind, method, suffix in (("chunk-probe", "HEAD", "/{day}"),
                                             ("stream-probe", "HEAD", ""),
                                             ("terms", "OPTIONS", ""),
                                             ("read", "GET", "/{day}"))]
    requests.append(_ask("stream-channel-open", "HEAD", "/tenant/northwind/stream", ACME, "upgrade"))
    return {"name": "usage-week", "steps": steps, "requests": requests, "snapshot_probe": True}

def _ledger_cutover_record() -> dict[str, Any]:
    'Two routers holding the same page, and which of the two a partner reaches.'

    steps = [
        _service(auto_head=True, auto_options=False),
        _router("reconciliation"), _router("holdover"),
        _route("reconciliation", "GET", "/ledger", "close_ledger", cost=88,
               answers={"-": {"status": 200, "body": DIGEST}}, settings={"auto_head": False}),
        _route("reconciliation", "GET", "/ledger/{day_id}", "read_ledger_day", cost=6,
               params={"day_id": "whole"}, answers={"*": {"status": 200, "body": MANIFEST}}),
        _route("holdover", "GET", "/ledger", "read_ledger_holdover", cost=3,
               answers={"-": {"status": 200, "body": FEED}}, settings={"in_catalogue": False}),
        _include("reconciliation", "/v1"), _include("holdover", "/v1"),
    ]
    requests = _pairs((("ledger", "/v1/ledger", ACME), ("day", "/v1/ledger/12", ACME)))
    return {"name": "ledger-cutover", "steps": steps, "requests": requests}

RELEASE = (_probes_assembly, _sweep_assembly, _mounts_assembly, _usage_assembly)
RECORDS = {"mirror-probe-log": _mirror_log_record, "method-sweep": _method_sweep_record,
           "mounting-map": _mounting_map_record, "usage-week": _usage_week_record,
           "ledger-cutover": _ledger_cutover_record}

def build_program(profile: str) -> dict[str, Any]:
    'The surfaces one stretch of portal traffic assembles, and what it sends.'
    if profile == "release":
        assemblies = [builder() for builder in RELEASE]
        assemblies[3:3] = _explicit_assemblies()
        return {"assemblies": assemblies}
    builder = RECORDS.get(profile)
    if builder is None:
        raise ValueError(f"unknown portal traffic profile: {profile}")
    return {"assemblies": [builder()]}

def _step_line(step: Mapping[str, Any]) -> str:
    op, settings = str(step["op"]), dict(step["settings"])
    if op == "service":
        return f"service settings={settings}"
    if op == "router":
        return f"router {step['name']} settings={settings}"
    if op == "route":
        return (f"{step['router']}: {step['method']} {step['path']} ({step['name']}) "
                f"cost={step['cost']} guard={step['guard'] or 'none'} settings={settings}")
    return (f"mount {step['router']} into {step['into']} at {step['prefix']} "
            f"settings={settings}")

def outline(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'How each surface in this program is put together, layer settings included.'
    return [{"surface": str(assembly["name"]),
             "assembled_in_this_order": [_step_line(step) for step in assembly["steps"]],
             "requests_sent": [f"{ask['method']} {ask['path']} ({ask['label']})"
                               for ask in assembly.get("requests", ())]}
            for assembly in program.get("assemblies", ())]
