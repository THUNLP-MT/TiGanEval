'Deterministic estate traffic: baselines, nightly scans, triage, baseline events.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

def cfg(image: str, *, env: Sequence[str] = (), ports: Sequence[str] = (), memory: int = 512,
        mounts: Sequence[str] = (), labels: Mapping[str, str] | None = None, cpu: float = 1.0,
        restart: str = "always", network: str = "mesh") -> dict[str, Any]:
    return {"image": image, "restart_policy": restart, "network": network,
            "env": list(env), "ports": list(ports), "mounts": list(mounts),
            "labels": dict(labels or {}), "memory_mb": memory, "cpu_share": cpu}

def _permuted(config: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(config)
    for key in ("env", "ports", "mounts"):
        if key in out:
            out[key] = list(reversed(list(out[key])))
    if "labels" in out:
        out["labels"] = dict(reversed(list(dict(out["labels"]).items())))
    return out

def _observe(baseline: Mapping[str, Any], changes: Mapping[str, Any] | None = None, *,
             drop: Sequence[tuple[str, str]] = (), gone: Sequence[str] = (),
             extra: Mapping[str, Any] | None = None, reordered: bool = False) -> dict[str, Any]:
    observed = {name: dict(config) for name, config in baseline.items()}
    for service, fields in dict(changes or {}).items():
        observed[service] = dict(observed[service], **dict(fields))
    for service, key in drop:
        observed[service] = {k: v for k, v in observed[service].items() if k != key}
    for service in gone:
        observed.pop(service, None)
    observed.update({name: dict(config) for name, config in dict(extra or {}).items()})
    if reordered:
        observed = {name: _permuted(config) for name, config in observed.items()}
    return observed

def _capture(label: str, at: int, environment: str, name: str,
             services: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "capture", "label": label, "at": at, "environment": environment,
            "name": name, "services": dict(services)}

def _scan(label: str, at: int, environment: str, services: Mapping[str, Any],
          recorded: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row = {"op": "scan", "label": label, "at": at, "environment": environment,
           "services": dict(services)}
    return row if recorded is None else dict(row, recorded=dict(recorded))

def _baseline_op(kind: str, label: str, at: int, baseline: str) -> dict[str, Any]:
    return {"op": kind, "label": label, "at": at, "baseline": baseline}

def _triage(label: str, at: int, action: str, environment: str, service: str,
            drift_type: str, field: str = "") -> dict[str, Any]:
    return {"op": "triage", "label": label, "at": at, "action": action,
            "environment": environment, "service": service, "drift_type": drift_type,
            "field": field}

def _old(score: float, listed: int) -> dict[str, Any]:
    return {"compliance": score, "services_listed": listed}


US = {
    "web-api": cfg("registry/web-api:4.2.0", env=["LOG=info", "REGION=us", "TIER=edge"],
                   ports=["8080:80", "9090:90"], mounts=["/srv/web:/data"], memory=1024,
                   cpu=1.5, labels={"team": "web", "tier": "edge"}),
    "worker": cfg("registry/worker:2.9.1", env=["QUEUE=jobs", "LOG=info"], memory=2048,
                  mounts=["/srv/jobs:/jobs", "/srv/tmp:/tmp"], labels={"team": "batch"}, cpu=2.0),
    "queue": cfg("registry/queue:1.4.0", env=["NODE=1", "CLUSTER=us"], cpu=0.5,
                 ports=["5672:5672", "15672:15672"], labels={"team": "platform"}),
    "search": cfg("registry/search:3.0.4", env=["SHARDS=4", "HEAP=2g"], memory=4096, cpu=3.0,
                  ports=["9200:9200", "9300:9300"], mounts=["/srv/idx:/idx"],
                  labels={"team": "search"}),
    "mailer": cfg("registry/mailer:0.8.2", env=["SMTP=relay", "FROM=noreply"], memory=256,
                  ports=["2525:25"], labels={"team": "comms"}, cpu=0.25),
    "gateway": cfg("registry/gateway:5.1.0", env=["UPSTREAM=web-api", "TIMEOUT=30"],
                   ports=["443:443", "80:80"], labels={"team": "platform", "tier": "edge"}),
}
EU = {
    "web-api": cfg("registry/web-api:4.2.0", env=["LOG=info", "REGION=eu"], memory=1024,
                   ports=["8080:80"], labels={"team": "web"}, cpu=1.5),
    "worker": cfg("registry/worker:2.9.1", env=["QUEUE=jobs", "LOG=info"], memory=2048,
                  labels={"team": "batch"}, cpu=2.0),
    "queue": cfg("registry/queue:1.4.0", env=["NODE=1"], ports=["5672:5672"],
                 labels={"team": "platform"}, cpu=0.5),
    "archive": cfg("registry/archive:1.0.9", env=["BUCKET=eu-cold"], memory=1024,
                   mounts=["/srv/cold:/cold"], labels={"team": "data"}, cpu=0.5),
    "legacy-sync": cfg("registry/legacy-sync:0.4.1", env=["PEER=us"], memory=256,
                       labels={"team": "data"}, cpu=0.25),
}
EDGE_A = {
    "router": cfg("registry/router:2.0.0", env=["ZONE=a", "MODE=edge"], ports=["443:443"],
                  labels={"team": "edge"}),
    "cache": cfg("registry/cache:1.7.2", env=["SIZE=4g"], mounts=["/srv/cache:/cache"],
                 labels={"team": "edge"}, memory=2048),
}
EDGE_A_LATER = {**EDGE_A, "router": dict(EDGE_A["router"], image="registry/router:2.1.0")}
EDGE_B = {
    "probe": cfg("registry/probe:0.9.0", env=["ZONE=b"], labels={"team": "edge"},
                 memory=256, cpu=0.25),
    "relay": cfg("registry/relay:3.3.1", env=["PEER=a", "MODE=relay"], ports=["9000:9000"],
                 labels={"team": "edge"}, cpu=0.5),
}
LAB_EXTRA = {
    "probe-a": cfg("registry/probe:0.9.0", env=["ZONE=lab"], memory=256, cpu=0.25),
    "sampler": cfg("registry/sampler:0.2.0", env=["RATE=5"], memory=256, cpu=0.25)}


_US_DRIFT = {"web-api": {"image": "registry/web-api:4.3.0-hotfix",
                         "labels": {"team": "web", "tier": "core"}},
             "search": {"memory_mb": 6144, "cpu_share": 4.0}}
_US_SETTLED = {**_US_DRIFT, "web-api": {"image": "registry/web-api:4.3.0-hotfix"}}
_US_NIGHTS = ((4, 3072, False), (5, 3584, False), (6, 3072, False), (7, 3072, False),
              (8, 2048, False), (9, 2048, True), (10, 3072, True))

def _us_night(memory: int, *, settled: bool = False, reordered: bool = False) -> dict[str, Any]:
    changes = {**(_US_SETTLED if settled else _US_DRIFT), "worker": {"memory_mb": memory}}
    return _observe(US, changes, drop=(("mailer", "labels"),), reordered=reordered)

def _audit_operations() -> list[dict[str, Any]]:
    'One review of the whole estate: a pilot environment with nothing declared, a     fortnight with a triage pass, a region that loses and gains a service, baseline events.'
    ops = [_capture("lab-capture", 1, "lab", "pilot intake", {}),
           _scan("lab-night", 2, "lab", LAB_EXTRA),
           _capture("us-capture", 3, "prod-us", "March declaration", US)]
    for index, (at, memory, settled) in enumerate(_US_NIGHTS, start=1):
        ops.append(_scan(f"us-night-{index}", at, "prod-us",
                         _us_night(memory, settled=settled, reordered=at == 6)))
        if at == 6:
            ops += [_triage("us-hold-image", 6, "acknowledge", "prod-us", "web-api",
                            "image_changed"),
                    _triage("us-hold-label", 6, "ignore", "prod-us", "web-api",
                            "label_changed")]
    patched = {"web-api": {"image": "registry/web-api:4.5.0-patch"}}
    eu_later = _observe(EU, patched, gone=("archive",))
    cache_over = _observe(EDGE_A_LATER, {"cache": {"memory_mb": 3072}})
    ops += [
        _capture("eu-capture", 11, "prod-eu", "March declaration", EU),
        _scan("eu-night-1", 12, "prod-eu",
              _observe(EU, {**patched, "queue": {"labels": {"team": "infra"}}})),
        _scan("eu-night-2", 13, "prod-eu", eu_later),
        _scan("eu-night-3", 14, "prod-eu",
              dict(eu_later, **{"debug-shell": cfg("registry/debug:0.1.0", env=["TTL=1h"])})),
        _capture("edge-a-first", 15, "edge-a", "edge intake", EDGE_A),
        _capture("edge-b-only", 15, "edge-b", "edge intake", EDGE_B),
        _scan("edge-a-night-1", 16, "edge-a",
              _observe(EDGE_A, {"router": {"image": "registry/router:2.1.0"}})),
        _scan("edge-b-night-1", 16, "edge-b",
              _observe(EDGE_B, {"probe": {"image": "registry/probe:0.9.1"}})),
        _capture("edge-a-second", 17, "edge-a", "edge re-declaration", EDGE_A_LATER),
        _scan("edge-a-night-2", 18, "edge-a", cache_over),
        _baseline_op("activate", "edge-a-back-to-first", 19, "edge-a-first"),
        _scan("edge-a-night-3", 20, "edge-a", cache_over),
        _baseline_op("delete", "edge-a-drop-second", 21, "edge-a-second"),
        _scan("edge-a-night-4", 22, "edge-a", cache_over),
        _baseline_op("delete", "edge-a-drop-first", 23, "edge-a-first"),
        _scan("edge-a-night-5", 24, "edge-a", cache_over),
    ]
    return ops


STAGING = {
    "web-api": cfg("registry/web-api:4.1.0", env=["LOG=info", "REGION=eu", "TIER=edge"],
                   ports=["8080:80", "9090:90"], mounts=["/srv/web:/data"], memory=1024,
                   labels={"team": "web"}, cpu=1.5),
    "billing": cfg("registry/billing:2.2.0", env=["LEDGER=on", "LOG=info"], memory=1024,
                   ports=["7000:7000"], labels={"team": "fin"}),
    "metrics": cfg("registry/metrics:1.1.4", env=["SCRAPE=30s", "RETAIN=15d"], memory=2048,
                   ports=["9090:9090"], mounts=["/srv/tsdb:/tsdb"], labels={"team": "platform"}),
    "notify": cfg("registry/notify:0.6.0", env=["SMTP=relay", "FROM=alerts"], memory=256,
                  ports=["2525:25"], labels={"team": "comms"}, cpu=0.25),
    "session": cfg("registry/session:3.4.2", env=["TTL=30m", "STORE=redis"], cpu=0.5,
                   ports=["6379:6379"], labels={"team": "web"}),
}
UK = {
    "orders": cfg("registry/orders:5.2.0", env=["LOG=info", "REGION=uk"], memory=1024,
                  ports=["8080:80"], labels={"team": "sales", "tier": "core"}, cpu=1.5),
    "billing": cfg("registry/billing:2.2.0", env=["LEDGER=on"], ports=["7000:7000"],
                   labels={"team": "fin"}, memory=1024),
    "search": cfg("registry/search:3.0.4", env=["SHARDS=2"], ports=["9200:9200"],
                  labels={"team": "search"}, memory=2048, cpu=2.0),
    "archive-worker": cfg("registry/archive:1.0.9", env=["BUCKET=uk-cold"], memory=1024,
                          labels={"team": "data"}, cpu=0.5),
    "notify": cfg("registry/notify:0.6.0", env=["SMTP=relay"], ports=["2525:25"],
                  labels={"team": "comms"}, memory=256, cpu=0.25),
    "session": cfg("registry/session:3.4.2", env=["TTL=30m"], ports=["6379:6379"],
                   labels={"team": "web"}, cpu=0.5),
}
EDGE_UK = {
    "edge-router": cfg("registry/router:2.0.0", env=["ZONE=uk"], ports=["443:443"],
                       labels={"team": "edge"}),
    "edge-cache": cfg("registry/cache:1.7.2", env=["SIZE=4g", "EVICT=lru"], memory=2048,
                      labels={"team": "edge"}),
    "edge-auth": cfg("registry/auth:1.2.0", env=["ISSUER=uk"], labels={"team": "edge"},
                     memory=256, cpu=0.5),
    "edge-log": cfg("registry/log:0.5.0", env=["SINK=s3"], labels={"team": "edge"},
                    memory=256, cpu=0.25),
}
SANDBOX = {
    "api": cfg("registry/api:1.0.0", env=["MODE=sandbox"], ports=["8080:80"],
               labels={"team": "dev"}),
    "cache": cfg("registry/cache:1.7.2", env=["SIZE=1g"], labels={"team": "dev"}, cpu=0.5),
    "jobs": cfg("registry/jobs:0.3.0", env=["QUEUE=dev"], labels={"team": "dev"}, cpu=0.5),
}
SANDBOX_LATER = {**SANDBOX, "api": dict(SANDBOX["api"], image="registry/api:1.1.0")}
SANDBOX_EU = {name: dict(SANDBOX[name]) for name in ("api", "cache")}
PILOT_EXTRA = {
    "pilot-api": cfg("registry/api:1.0.0", env=["MODE=pilot"], memory=256, cpu=0.25),
    "pilot-jobs": cfg("registry/jobs:0.3.0", env=["QUEUE=pilot"], memory=256, cpu=0.25)}

def _reboot_operations() -> list[dict[str, Any]]:
    bumped = {"web-api": {"image": "registry/web-api:4.4.0-build"}}
    quiet = _observe(STAGING, bumped, drop=(("metrics", "labels"),))
    reordered = _observe(STAGING, bumped, drop=(("metrics", "labels"),), reordered=True)
    return [_capture("staging-capture", 1, "staging", "February declaration", STAGING),
            _scan("staging-quiet", 2, "staging", quiet, _old(80.0, 1)),
            _scan("staging-after-the-reboot", 3, "staging", reordered, _old(0.0, 5))]

def _nightly_operations() -> list[dict[str, Any]]:
    drift = {"orders": {"image": "registry/orders:5.3.0-hotfix",
                        "labels": {"team": "sales", "tier": "edge"}},
             "archive-worker": {"network": "host"}}
    over = {**drift, "billing": {"memory_mb": 3072}}
    over_later = {**drift, "billing": {"memory_mb": 3584}}
    shell = {"debug-shell": cfg("registry/debug:0.1.0", env=["TTL=1h"])}
    nights = [
        ("uk-night-1", 2, _observe(UK, over), _old(50.0, 3)),
        ("uk-night-2", 3, _observe(UK, over_later), _old(50.0, 3)),
        ("uk-night-3", 4, _observe(UK, drift), _old(66.7, 2)),
        ("uk-night-4", 5, _observe(UK, drift), _old(66.7, 2)),
        ("uk-night-5", 6, _observe(UK, drift, gone=("archive-worker",)), _old(80.0, 1)),
        ("uk-night-6", 7, _observe(UK, drift, gone=("archive-worker",), extra=shell),
         _old(83.3, 1)),
        ("uk-night-7", 8, _observe(UK, over, gone=("archive-worker",)), _old(66.7, 2)),
    ]
    return [_capture("uk-capture", 1, "prod-uk", "March declaration", UK)] + [
        _scan(label, at, "prod-uk", services, recorded)
        for label, at, services, recorded in nights]

def _triage_operations() -> list[dict[str, Any]]:
    drift = {"edge-router": {"image": "registry/router:2.1.0"},
             "edge-cache": {"env": ["SIZE=8g", "EVICT=lru"]}}
    settled = {"edge-router": {"image": "registry/router:2.1.0"}}
    return [
        _capture("edge-uk-capture", 1, "edge-uk", "edge declaration", EDGE_UK),
        _scan("edge-uk-night-1", 2, "edge-uk", _observe(EDGE_UK, drift), _old(50.0, 2)),
        _scan("edge-uk-night-2", 3, "edge-uk", _observe(EDGE_UK, drift), _old(50.0, 2)),
        _triage("edge-uk-hold-image", 3, "acknowledge", "edge-uk", "edge-router",
                "image_changed"),
        _triage("edge-uk-hold-env", 3, "ignore", "edge-uk", "edge-cache", "env_changed"),
        _scan("edge-uk-night-3", 4, "edge-uk", _observe(EDGE_UK, drift), _old(50.0, 2)),
        _scan("edge-uk-night-4", 5, "edge-uk", _observe(EDGE_UK, settled), _old(75.0, 1)),
        _scan("edge-uk-night-5", 6, "edge-uk", _observe(EDGE_UK, settled), _old(75.0, 1)),
    ]

def _baseline_operations() -> list[dict[str, Any]]:
    bumped = _observe(SANDBOX, {"api": {"image": "registry/api:1.1.0"}})
    jobs_drift = _observe(SANDBOX_LATER, {"jobs": {"env": ["QUEUE=dev", "RETRY=3"]}})
    return [
        _capture("sandbox-first", 1, "sandbox", "sandbox intake", SANDBOX),
        _capture("sandbox-eu-only", 1, "sandbox-eu", "sandbox intake", SANDBOX_EU),
        _scan("sandbox-night-1", 2, "sandbox", bumped, _old(66.7, 1)),
        _scan("sandbox-eu-night-1", 2, "sandbox-eu",
              _observe(SANDBOX_EU, {"cache": {"memory_mb": 1024}}), _old(50.0, 1)),
        _capture("sandbox-second", 3, "sandbox", "sandbox re-declaration", SANDBOX_LATER),
        _scan("sandbox-night-2", 4, "sandbox", jobs_drift, _old(66.7, 1)),
        _baseline_op("activate", "sandbox-back-to-first", 5, "sandbox-first"),
        _scan("sandbox-night-3", 6, "sandbox", jobs_drift, _old(66.7, 1)),
        _baseline_op("activate", "sandbox-back-to-second", 7, "sandbox-second"),
        _baseline_op("delete", "sandbox-drop-first", 8, "sandbox-first"),
        _scan("sandbox-night-4", 9, "sandbox", jobs_drift, _old(66.7, 1)),
        _baseline_op("delete", "sandbox-drop-second", 10, "sandbox-second"),
        _scan("sandbox-night-5", 11, "sandbox", jobs_drift, _old(100.0, 0)),
        _capture("pilot-capture", 11, "pilot", "pilot intake", {}),
        _scan("pilot-night-1", 12, "pilot", PILOT_EXTRA, _old(100.0, 0)),
    ]

PUBLIC_PROGRAMS = {"reboot": _reboot_operations, "nightly": _nightly_operations,
                   "triage": _triage_operations, "baselines": _baseline_operations}
PRIVATE_PROFILE = "audit"

def build_program(profile: str) -> dict[str, Any]:
    "The console's schedule of baseline events, nights and triage decisions."
    if profile == PRIVATE_PROFILE:
        return {"start_at": 0, "operations": _audit_operations()}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown estate profile: {profile}")
    return {"start_at": 0, "operations": builder()}

def program_environments(program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    'Every environment the program touches, with its declared size and nights.'
    rows: dict[str, dict[str, Any]] = {}
    for op in program.get("operations", ()):
        environment = str(op.get("environment", ""))
        if not environment:
            continue
        row = rows.setdefault(environment, {"baselines_captured": 0, "nights": 0,
                                            "services_declared": []})
        if str(op.get("op")) == "capture":
            row["baselines_captured"] += 1
            row["services_declared"] = sorted(dict(op.get("services", {})))
        row["nights"] += int(str(op.get("op")) == "scan")
    return rows
