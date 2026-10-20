'Deterministic source trees and scan programs for the scan-cache project.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


CACHE_BYTES_PER_FILE = 5000


CAPACITY_EXPIRY_DAYS = 10.0


STEADY_STATE_WRITE_BYTES_PER_FILE = 256
STEADY_STATE_WRITE_BASE_BYTES = 512
OPEN_LIMIT_BYTES = 10**9
OPEN_EXPIRY_DAYS = 3650.0
DAY = 86_400.0

_SNIPPETS: tuple[str, ...] = (
    '    assert value is not None',
    '    password = "hunter-{tag}"',
    '    result = eval(expression)',
    '    digest = hashlib.md5(payload).hexdigest()',
    '    subprocess.run(command, shell=True)',
    '    cursor.execute("select * from ledger where id = " + ident)',
)
_PACKAGES = ("core", "api", "jobs")


LARGE_MODULE_PATH = "jobs/legacy_dispatch.py"
LARGE_MODULE_HANDLERS = 20
LARGE_MODULE_MTIME = 1_601_501.0


REVISIT_LABEL = "day-8-back-to-the-upgrade"


AGGREGATE_CURRENT_LABEL = "cap-aggregate-current"
AGGREGATE_CURRENT_FILE_COUNT = 3
AGGREGATE_CURRENT_FINDING_LINES = 40


def _module_text(index: int, seed: int, *, variant: str = "original") -> str:
    rotation = (seed + 3 * index) % len(_SNIPPETS)
    tag = f"{seed}-{index:02d}"
    body = [
        _SNIPPETS[(rotation + offset) % len(_SNIPPETS)].format(tag=tag)
        for offset in range(len(_SNIPPETS))
    ]
    if variant == "fixed":
        body = [
            line.replace(
                "    subprocess.run(command, shell=True)",
                "    subprocess.run(command)",
            )
            for line in body
        ]
    elif variant == "regressed":
        body.append("    fallback = eval(command)")
    lines = [
        f'"""Handler {index:02d} for the {_PACKAGES[index % 3]} package."""',
        "",
        "import hashlib",
        "import subprocess",
        "",
        "",
        f"def handle_{index:02d}(value, expression, payload, command, cursor, ident):",
        *body,
        "    return value",
        "",
    ]
    return "\n".join(lines)


def _large_module_text(seed: int) -> str:
    'The legacy dispatch table: many handlers, and a finding on most lines.'

    lines = [
        '"""Legacy dispatch table for the jobs package."""',
        "",
        "import hashlib",
        "import subprocess",
        "",
        "",
    ]
    for block in range(LARGE_MODULE_HANDLERS):
        rotation = (seed + 5 * block) % len(_SNIPPETS)
        tag = f"{seed}-legacy-{block:02d}"
        lines.extend(
            [
                f"def dispatch_{block:02d}(value, expression, payload, command, cursor, ident):",
                *[
                    _SNIPPETS[(rotation + offset) % len(_SNIPPETS)].format(tag=tag)
                    for offset in range(len(_SNIPPETS))
                ],
                "    return value",
                "",
                "",
            ]
        )
    return "\n".join(lines)


def module_path(index: int) -> str:
    return f"{_PACKAGES[index % 3]}/handler_{index:02d}.py"


def handler_count(scale: int) -> int:
    'The handler modules of a tree, which the edit programs index into.'

    return 6 + 3 * int(scale)


def has_large_module(scale: int) -> bool:
    "The legacy dispatch table belongs to the release week's checkout only."

    return int(scale) >= 2


def file_count(scale: int) -> int:
    "Every file in the tree, which is what the volume's budgets are sized by."

    return handler_count(scale) + (1 if has_large_module(scale) else 0)


def build_tree(seed: int, scale: int) -> dict[str, dict[str, Any]]:
    'Return the fixture checkout for one case.'

    tree = {
        module_path(index): {
            "content": _module_text(index, seed),
            "mtime": 1_600_000.0 + 137.0 * index,
        }
        for index in range(handler_count(scale))
    }
    if has_large_module(scale):
        tree[LARGE_MODULE_PATH] = {
            "content": _large_module_text(seed),
            "mtime": LARGE_MODULE_MTIME,
        }
    return tree


def _options(
    *,
    analyzer_version: str = "3.2.0",
    severity_floor: str = "low",
    confidence_floor: str = "low",
    profile_name: str = "default",
    profile_checks: Sequence[str] = (),
    selected_checks: Sequence[str] | None = None,
    skipped_checks: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "analyzer_version": analyzer_version,
        "severity_floor": severity_floor,
        "confidence_floor": confidence_floor,
        "profile_name": profile_name,
        "profile_checks": list(profile_checks),
        "selected_checks": None if selected_checks is None else list(selected_checks),
        "skipped_checks": list(skipped_checks),
    }


def cache_size_limit(scale: int) -> int:
    'The published byte budget for a tree of this size.'

    return CACHE_BYTES_PER_FILE * file_count(scale)


def steady_state_write_allowance(scale: int) -> int:
    'The published byte budget for a run in which nothing changed.'

    return STEADY_STATE_WRITE_BYTES_PER_FILE * file_count(scale) + STEADY_STATE_WRITE_BASE_BYTES


def _config(
    *,
    limit: int = OPEN_LIMIT_BYTES,
    expiry: float = OPEN_EXPIRY_DAYS,
    incremental: bool = True,
) -> dict[str, Any]:
    return {
        "cache_size_limit_bytes": int(limit),
        "cache_expiry_days": float(expiry),
        "incremental": bool(incremental),
    }


def _scan(
    label: str,
    phase: str,
    *,
    options: Mapping[str, Any],
    config: Mapping[str, Any],
    now: float,
    machine: str = "ci-1",
) -> dict[str, Any]:
    return {
        "type": "scan",
        "label": label,
        "phase": phase,
        "options": dict(options),
        "config": dict(config),
        "now": float(now),
        "machine": machine,
    }


def _edit(
    seed: int,
    indexes: Sequence[int],
    variant: str,
    *,
    keep_mtime: bool,
    mtime: float | None = None,
) -> dict[str, Any]:
    return {
        "type": "edit",
        "files": {
            module_path(index): {
                "content": _module_text(index, seed, variant=variant),
                "mtime": None if keep_mtime else mtime,
            }
            for index in indexes
        },
    }


def _nightly(
    seed: int, scale: int, *, revisit_an_earlier_configuration: bool = False
) -> list[dict[str, Any]]:
    handlers = handler_count(scale)
    fixed = [0, min(2, handlers - 1)]
    regressed = [min(1, handlers - 1), handlers - 1]
    baseline = _options(analyzer_version="3.1.0")
    tightened = _options(analyzer_version="3.1.0", severity_floor="medium")
    upgraded = _options(analyzer_version="3.2.0", severity_floor="medium")
    profiled = _options(
        analyzer_version="3.2.0",
        severity_floor="medium",
        profile_name="release",
        profile_checks=["SEC307", "SEC602", "SEC608"],
    )
    config = _config()
    events = [
        {"type": "reset", "root": "/srv/ci-1/checkout"},
        _scan("day-1", "nightly", options=baseline, config=config, now=10.0 * DAY),
        _edit(seed, fixed, "fixed", keep_mtime=True),
        _scan("day-2-after-fix", "nightly", options=baseline, config=config, now=11.0 * DAY),
        _edit(seed, regressed, "regressed", keep_mtime=True),
        _scan("day-3-after-regression", "nightly", options=baseline, config=config, now=12.0 * DAY),
        _scan("day-4-tightened-floor", "nightly", options=tightened, config=config, now=13.0 * DAY),
        _scan("day-5-analyzer-upgrade", "nightly", options=upgraded, config=config, now=14.0 * DAY),
        _scan("day-6-release-profile", "nightly", options=profiled, config=config, now=15.0 * DAY),
        _scan("day-7-unchanged", "nightly", options=profiled, config=config, now=16.0 * DAY),
    ]
    if revisit_an_earlier_configuration:


        events.append(
            _scan(
                REVISIT_LABEL, "nightly", options=upgraded, config=config, now=17.0 * DAY
            )
        )
    return events


def _damage(seed: int, scale: int) -> list[dict[str, Any]]:
    handlers = handler_count(scale)
    stale = [0, min(1, handlers - 1)]
    options = _options()
    config = _config()
    return [
        {"type": "reset", "root": "/srv/ci-1/checkout"},
        _scan("warm", "damage", options=options, config=config, now=20.0 * DAY),
        {"type": "export", "label": "stale-bundle", "phase": "damage", "now": 20.0 * DAY},
        {"type": "damage", "mode": "truncate", "fraction": 0.5},
        _scan("after-truncation", "damage", options=options, config=config, now=21.0 * DAY),
        {"type": "damage", "mode": "garbage", "fraction": 1.0},
        _scan("after-corruption", "damage", options=options, config=config, now=22.0 * DAY),
        {"type": "damage", "mode": "flip_byte", "fraction": 1.0},
        _scan("after-bit-flip", "damage", options=options, config=config, now=23.0 * DAY),


        {"type": "damage", "mode": "misdirected_write", "fraction": 0.5},
        _scan("after-misdirected-write", "damage", options=options, config=config, now=23.5 * DAY),
        {"type": "import", "label": "stale-bundle", "phase": "damage", "mutate": "garbage", "now": 24.0 * DAY},
        _scan("after-malformed-import", "damage", options=options, config=config, now=24.0 * DAY),
        _edit(seed, stale, "fixed", keep_mtime=True),
        _scan("after-fix", "damage", options=options, config=config, now=25.0 * DAY),
        {"type": "import", "label": "stale-bundle", "phase": "damage", "mutate": "none", "now": 26.0 * DAY},
        _scan("after-stale-bundle-import", "damage", options=options, config=config, now=26.0 * DAY),
    ]


def _capacity(seed: int, scale: int) -> list[dict[str, Any]]:
    handlers = handler_count(scale)
    removed = [module_path(index) for index in range(min(3, handlers - 3))]
    config = _config(limit=cache_size_limit(scale), expiry=CAPACITY_EXPIRY_DAYS)


    generations = (
        _options(),
        _options(skipped_checks=["SEC101"]),
        _options(analyzer_version="3.1.0"),
        _options(confidence_floor="high"),
        _options(analyzer_version="3.0.0"),
        _options(severity_floor="high"),
        _options(profile_name="hotpath", profile_checks=["SEC307", "SEC602"]),
        _options(selected_checks=["SEC307", "SEC324", "SEC608"]),
    )
    steady = generations[-1]
    events: list[dict[str, Any]] = [{"type": "reset", "root": "/srv/ci-1/checkout"}]
    for index, options in enumerate(generations, start=1):
        events.append(
            _scan(
                f"cap-day-{index}",
                "capacity",
                options=options,
                config=config,
                now=(29.0 + index) * DAY,
            )
        )
    events.extend(
        [
            _scan("cap-unchanged", "capacity", options=steady, config=config, now=37.5 * DAY),
            {"type": "edit", "files": {}, "remove": removed},
            _scan("cap-after-removal", "capacity", options=steady, config=config, now=38.0 * DAY),


            {
                "type": "edit",
                "files": {
                    path: {
                        "content": _module_text(index, seed),
                        "mtime": 1_600_000.0 + 137.0 * index,
                    }
                    for index, path in enumerate(removed)
                },
            },
            _scan("cap-after-restore", "capacity", options=steady, config=config, now=38.5 * DAY),


            _scan("cap-after-idle", "capacity", options=steady, config=config, now=55.0 * DAY),
            _scan("cap-repeat", "capacity", options=steady, config=config, now=55.0 * DAY),
        ]
    )
    if has_large_module(scale):
        current_paths = [
            module_path(index)
            for index in range(min(AGGREGATE_CURRENT_FILE_COUNT, handlers))
        ]
        events.extend(
            [
                {
                    "type": "edit",
                    "files": {
                        path: {
                            "content": 'password = "x"\n' * AGGREGATE_CURRENT_FINDING_LINES,
                            "mtime": 1_700_000.0 + index,
                        }
                        for index, path in enumerate(current_paths)
                    },
                    "remove": sorted(set(build_tree(seed, scale)).difference(current_paths)),
                },
                _scan(
                    AGGREGATE_CURRENT_LABEL,
                    "capacity",
                    options=_options(),
                    config=_config(
                        limit=CACHE_BYTES_PER_FILE * len(current_paths),
                        expiry=CAPACITY_EXPIRY_DAYS,
                    ),
                    now=56.0 * DAY,
                ),
            ]
        )
    return events


def _handoff(
    seed: int, scale: int, *, ship_after_the_nightly: bool = False
) -> list[dict[str, Any]]:
    options = _options()
    config = _config()
    events: list[dict[str, Any]] = [
        {"type": "reset", "root": "/srv/ci-1/checkout"},
        _scan("ci-1-warm", "handoff", options=options, config=config, now=60.0 * DAY),
        {"type": "export", "label": "warm", "phase": "handoff", "now": 60.0 * DAY},
    ]
    if ship_after_the_nightly:


        events.append(
            _scan("ci-1-quiet", "handoff", options=options, config=config, now=61.0 * DAY)
        )
    events += [


        {"type": "export", "label": "warm-repeat", "phase": "handoff", "now": 61.0 * DAY},
        {"type": "relocate", "root": "/opt/agents/ci-2/src", "mtime_shift": 90_000.0},
        {"type": "clear_store"},
        {"type": "import", "label": "warm", "phase": "handoff", "mutate": "bad_version", "now": 61.0 * DAY},
        _scan("ci-2-after-rejected-bundle", "handoff", options=options, config=config, now=61.0 * DAY, machine="ci-2"),
        {"type": "clear_store"},
        {"type": "import", "label": "warm", "phase": "handoff", "mutate": "none", "now": 61.0 * DAY},


        _scan("ci-2-warm", "handoff", options=options, config=config, now=61.0 * DAY, machine="ci-2"),
    ]
    return events


PHASE_BUILDERS = {
    "nightly": _nightly,
    "damage": _damage,
    "capacity": _capacity,
    "handoff": _handoff,
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    'Return one deterministic event program.'

    if profile == "release":


        return [
            *_nightly(seed, scale, revisit_an_earlier_configuration=True),
            *_damage(seed, scale),
            *_capacity(seed, scale),
            *_handoff(seed, scale, ship_after_the_nightly=True),
        ]
    builder = PHASE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown scan program profile: {profile}")
    return builder(seed, scale)
