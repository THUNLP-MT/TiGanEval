'Deterministic bundles and drill programs for the decision service.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _body(*specs: str) -> list[list[Any]]:
    'One body, written the way the bundle files read.'

    conjuncts: list[list[Any]] = []
    for spec in specs:
        if spec.startswith("@"):
            target, _, expect = spec[1:].partition(" is ")
            conjuncts.append(["ref", target, None if expect == "nothing" else expect])
            continue
        path, op, operand = spec.split(" ", 2)
        conjuncts.append(
            ["test", path, op, int(operand) if operand.lstrip("-").isdigit() else operand]
        )
    return conjuncts


def _rule(package: str, rule: str, value: Any, body: Sequence[Any]) -> dict[str, Any]:
    return {"package": package, "rule": rule, "value": value, "body": list(body)}


def _default(package: str, rule: str, value: Any) -> dict[str, Any]:
    return {"package": package, "rule": rule, "default": value}


def access_bundle() -> dict[str, Any]:
    'The vendor-access bundle: three limit rules that all read one role rule.'

    return {
        "entry": "data.authz.decision",
        "rules": [
            _rule("roles", "senior", "senior", _body("subject.groups has eng-leads")),
            _rule("roles", "senior", "senior", _body("subject.grade gt 5")),
            _default("roles", "senior", "junior"),
            _rule("roles", "vendor", "vendor", _body("subject.tenant eq vendor")),
            _default("roles", "vendor", "internal"),
            _rule("limits", "quota", "high", _body("@data.roles.senior is senior")),
            _rule("limits", "quota", "high", _body("subject.grade gt 8")),
            _default("limits", "quota", "standard"),
            _rule(
                "limits", "window", "open",
                _body("@data.roles.senior is senior", "action ne purge"),
            ),
            _default("limits", "window", "closed"),
            _rule(
                "limits", "review", "required",
                _body("@data.roles.senior is senior", "resource.tier eq premium"),
            ),
            _default("limits", "review", "none"),
            _rule(
                "authz", "allow", "allow",
                _body("@data.limits.review is none", "action eq read"),
            ),
            _rule(
                "authz", "allow", "allow",
                _body(
                    "@data.limits.window is open",
                    "action eq write",
                    "resource.labels has owned",
                ),
            ),
            _rule(
                "authz", "allow", "allow",
                _body("subject.role eq owner", "resource.labels has owned"),
            ),
            _rule(
                "authz", "block", "block",
                _body("@data.roles.vendor is vendor", "resource.labels has restricted"),
            ),
            _rule(
                "authz", "decision", "allow",
                _body(
                    "@data.limits.quota is high",
                    "@data.authz.allow is allow",
                    "@data.authz.block is nothing",
                ),
            ),
            _rule(
                "authz", "decision", "export",
                _body("action eq export", "@data.billing.allow is allow"),
            ),
            _default("authz", "decision", "deny"),
            _rule(
                "billing", "allow", "allow",
                _body("subject.department eq billing", "resource.labels has invoice"),
            ),
            _rule(
                "billing", "allow", "allow",
                _body("@data.limits.review is required", "action eq export"),
            ),
        ],
    }


def fanout_bundle() -> dict[str, Any]:
    'Eight gate rules that each read the same tier rule.'

    checks = "abcdefgh"
    rules: list[dict[str, Any]] = [
        _rule("roles", "tier", "high", _body("subject.groups has platform")),
        _default("roles", "tier", "low"),
    ]
    rules.extend(
        _rule("checks", name, "ok", _body("@data.roles.tier is high", "action ne purge"))
        for name in checks
    )
    rules.append(
        _rule("gate", "decision", "allow", _body(*(f"@data.checks.{n} is ok" for n in checks)))
    )
    rules.append(_default("gate", "decision", "deny"))
    return {"entry": "data.gate.decision", "rules": rules}


def vault_bundle() -> dict[str, Any]:
    'The bundle the platform swaps in; it shares no rule with the access one.'

    return {
        "entry": "data.vault.decision",
        "rules": [
            _rule("roles", "clearance", "cleared", _body("subject.grade gt 4")),
            _default("roles", "clearance", "none"),
            _rule(
                "vault", "decision", "allow",
                _body("@data.roles.clearance is cleared", "resource.labels has vault"),
            ),
            _default("vault", "decision", "deny"),
        ],
    }


def _groups(seed: int, size: int, *extra: str) -> list[str]:
    return [f"grp-{seed}-{n:03d}" for n in range(size)] + list(extra)


def _labels(seed: int, size: int, *extra: str) -> list[str]:
    return [f"lbl-{seed}-{n:02d}" for n in range(size)] + list(extra)


def _request(
    seed: int,
    *,
    action: str = "read",
    role: str = "member",
    grade: int = 3,
    tenant: str = "internal",
    department: str = "eng",
    tier: str = "basic",
    groups: int = 4,
    senior: bool = False,
    platform: bool = False,
    labels: int = 3,
    marks: Sequence[str] = (),
) -> dict[str, Any]:
    named = (["eng-leads"] if senior else []) + (["platform"] if platform else [])
    return {
        "action": action,
        "subject": {
            "role": role,
            "grade": grade,
            "tenant": tenant,
            "department": department,
            "groups": _groups(seed, groups, *named),
        },
        "resource": {"tier": tier, "labels": _labels(seed, labels, *marks)},
    }


ACCESS_ORDER = (
    "junior-read", "senior-read", "owner-write", "vendor-read", "premium-read",
    "export-owner", "wide-read", "widest-read",
)


def _decide(label: str, request: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"type": "decide", "label": label, "request": dict(request), **extra}


def _access_requests(seed: int) -> dict[str, dict[str, Any]]:
    return {
        "junior-read": _request(seed),
        "senior-read": _request(seed, senior=True),
        "owner-write": _request(seed, action="write", role="owner", grade=9, marks=("owned",)),
        "vendor-read": _request(seed, tenant="vendor", senior=True, marks=("restricted",)),
        "premium-read": _request(seed, senior=True, tier="premium"),
        "export-owner": _request(
            seed, action="export", role="owner", grade=9,
            department="billing", marks=("owned", "invoice"),
        ),
        "wide-read": _request(seed, senior=True, groups=70),
        "widest-read": _request(seed, senior=True, groups=210),
    }


def _authz_program(seed: int, scale: int) -> list[dict[str, Any]]:
    requests = _access_requests(seed)
    program: list[dict[str, Any]] = [
        {"type": "load", "label": "load-access", "bundle": access_bundle()}
    ]
    for label in ACCESS_ORDER[:6]:
        program.append(_decide(label, requests[label]))
    return program


def _fanout_program(seed: int, scale: int) -> list[dict[str, Any]]:
    return [
        {"type": "load", "label": "load-gate", "bundle": fanout_bundle()},
        _decide("premium-caller", _request(seed, groups=12, platform=True)),
        _decide("basic-caller", _request(seed, groups=9)),
    ]


def _peak_program(seed: int, scale: int) -> list[dict[str, Any]]:
    requests = _access_requests(seed)
    return [
        {"type": "load", "label": "load-access", "bundle": access_bundle()},
        _decide("busy-1", requests["senior-read"]),
        _decide("busy-2", requests["wide-read"]),
        _decide("busy-3", requests["widest-read"]),
        _decide("busy-4", requests["senior-read"], same_as="busy-1"),
        {"type": "load", "label": "load-vault", "bundle": vault_bundle()},
        _decide("after-swap", _request(seed, grade=6, marks=("vault",))),
        {"type": "recheck", "label": "recheck-busy-1", "of": "busy-1"},
    ]


def _rollup_program(seed: int, scale: int) -> list[dict[str, Any]]:
    requests = _access_requests(seed)
    return [
        {"type": "load", "label": "load-access", "bundle": access_bundle()},
        _decide("night-1", requests["senior-read"]),
        _decide("night-2", requests["junior-read"]),
        _decide("night-3", requests["owner-write"]),
        _decide("night-4", requests["premium-read"]),
        {"type": "merge", "label": "shard-1", "left": "night-1", "right": "night-2", "into": "shard-1"},
        {"type": "merge", "label": "shard-2", "left": "night-3", "right": "night-4", "into": "shard-2"},
        {"type": "rollup", "label": "packages-shard-1", "of": "shard-1"},
        {"type": "rate", "label": "rates-shard-1", "of": "shard-1"},
        {"type": "merge", "label": "baseline", "left": "shard-1",
         "right": "shard-2", "into": "baseline", "probe": True},
        {"type": "recheck", "label": "recheck-shard-1", "of": "shard-1"},
    ]


def _release_program(seed: int, scale: int) -> list[dict[str, Any]]:
    requests = _access_requests(seed)
    service = [{"type": "load", "label": "load-access", "bundle": access_bundle()}]
    for label in ACCESS_ORDER:
        service.append(_decide(label, requests[label]))
    service.append(_decide("senior-read-again", requests["senior-read"], same_as="senior-read"))
    fanout = [
        {"type": "load", "label": "load-gate", "bundle": fanout_bundle()},
        _decide("gate-premium", _request(seed, groups=11, platform=True)),
        _decide("gate-basic", _request(seed, groups=7)),
    ]
    swap = [
        {"type": "load", "label": "load-vault", "bundle": vault_bundle()},
        _decide("vault-open", _request(seed, grade=6, marks=("vault",))),
        _decide("vault-shut", _request(seed, grade=2)),
        {"type": "recheck", "label": "recheck-junior-read", "of": "junior-read"},
    ]
    rollup = _rollup_program(seed + 1, scale)
    return (
        [{**event, "phase": "service"} for event in service]
        + [{**event, "phase": "fanout"} for event in fanout]
        + [{**event, "phase": "swap"} for event in swap]
        + [{**event, "phase": "rollup"} for event in rollup]
    )


PROGRAM_BUILDERS = {
    "authz": _authz_program,
    "fanout": _fanout_program,
    "peak": _peak_program,
    "rollup": _rollup_program,
    "release": _release_program,
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown drill profile: {profile}")
    program = builder(seed, scale)
    return [{"phase": profile, **event} for event in program]
