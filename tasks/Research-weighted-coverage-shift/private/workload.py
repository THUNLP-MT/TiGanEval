'The depot the board is being fixed for, and the depots the same notebook runs next.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import world


DEFAULT_FORM = "DP-4"
CONTRACT_FORM = "CF-1"
HANDHELD_FORM = "HH-2"


def _spec(
    depot: str,
    month: str,
    as_of: str,
    job_prefix: str,
    visit_prefix: str,
    seed: int,
    classes: Sequence[tuple[str, float, float, float]],
    pull: Mapping[str, int] | int,
    units_granted: int,
    roster: Mapping[str, Sequence[int]],
    rescoped: str | None = None,
    rescope_week: int = 0,
    rescoped_scale: float = 0.0,
    late_returns: Mapping[str, Sequence[int]] | None = None,
    audit_first_day: str = "2026-05-04",
    visit_first_day: str = "2026-07-06",
) -> dict[str, Any]:
    names = [str(name) for name, _, _, _ in classes]
    if isinstance(pull, int):
        pull_map = {name: int(pull) for name in names}
    else:
        pull_map = {name: int(pull[name]) for name in names}
    forms = {name: DEFAULT_FORM for name in names}
    for name in (late_returns or {}):
        forms[str(name)] = CONTRACT_FORM
    return {
        "depot": depot,
        "month": month,
        "as_of": as_of,
        "job_prefix": job_prefix,
        "visit_prefix": visit_prefix,
        "seed": int(seed),
        "classes": tuple(classes),
        "pull": pull_map,
        "forms": forms,
        "late_returns": {str(k): tuple(v) for k, v in (late_returns or {}).items()},
        "rescoped": rescoped,
        "rescope_week": int(rescope_week),
        "rescoped_scale": float(rescoped_scale),
        "rescope_form": HANDHELD_FORM,
        "month_jobs": 2400,
        "audit_weeks": 8,
        "audit_week_jobs": 560,
        "audit_first_day": audit_first_day,
        "visit_first_day": visit_first_day,
        "visit_weeks": (9, 10, 11, 12),
        "units_granted": int(units_granted),
        "units_per_visit": 3,
        "units_per_refusal": 1,
        "jobs_per_visit": 6,
        "visits_per_week": 2,
        "window_limit_minutes": 180,
        "roster": {str(name): tuple(int(w) for w in weeks) for name, weeks in roster.items()},
    }


CURRENT_SPEC = _spec(
    depot="halstow-2026-07",
    month="2026-07",
    as_of="2026-07-08",
    job_prefix="HAL",
    visit_prefix="HV",
    seed=510_2003,
    classes=(
        ("meter-exchange", 0.28, 21.0, 58.0),
        ("mains-repair", 0.21, 71.0, 205.0),
        ("leak-survey", 0.16, 24.0, 74.0),
        ("pressure-test", 0.14, 34.0, 96.0),
        ("boiler-service", 0.10, 19.0, 66.0),
        ("valve-replacement", 0.07, 20.0, 118.0),
        ("hydrant-check", 0.04, 17.0, 44.0),
    ),
    pull=12,
    units_granted=36,
    roster={
        "meter-exchange": (9, 11),
        "mains-repair": (10, 12),
        "leak-survey": (9, 12),
        "pressure-test": (10, 12),
        "boiler-service": (11, 12),
        "valve-replacement": (9, 10),
        "hydrant-check": (9, 11),
    },
    rescoped="pressure-test",
    rescope_week=3,
    rescoped_scale=66.0,
    late_returns={
        "valve-replacement": (2, 1, 2, 1, 2, 1, 2, 1),
        "hydrant-check": (1, 1, 0, 1, 1, 0, 1, 1),
    },
)


FOLLOWING_SPECS = (
    _spec(
        depot="bewick-2026-07",
        month="2026-07",
        as_of="2026-07-08",
        job_prefix="BEW",
        visit_prefix="BV",
        seed=621_4007,
        classes=(
            ("meter-exchange", 0.31, 22.0, 60.0),
            ("mains-repair", 0.24, 68.0, 198.0),
            ("leak-survey", 0.19, 26.0, 70.0),
            ("hydrant-check", 0.16, 18.0, 44.0),
            ("regulator-swap", 0.10, 61.0, 176.0),
        ),
        pull=10,
        units_granted=30,
        roster={
            "meter-exchange": (9, 11),
            "mains-repair": (10, 12),
            "leak-survey": (9, 10),
            "hydrant-check": (11, 12),
            "regulator-swap": (9, 12),
        },
        rescoped="leak-survey",
        rescope_week=4,
        rescoped_scale=58.0,
    ),
    _spec(
        depot="cranmoor-2026-07",
        month="2026-07",
        as_of="2026-07-08",
        job_prefix="CRA",
        visit_prefix="CV",
        seed=732_6011,
        classes=(
            ("meter-exchange", 0.24, 20.0, 56.0),
            ("mains-repair", 0.19, 70.0, 202.0),
            ("leak-survey", 0.16, 25.0, 72.0),
            ("boiler-service", 0.14, 19.0, 64.0),
            ("pressure-test", 0.12, 33.0, 94.0),
            ("hydrant-check", 0.09, 17.0, 42.0),
            ("valve-replacement", 0.06, 21.0, 116.0),
        ),
        pull={
            "meter-exchange": 9,
            "mains-repair": 16,
            "leak-survey": 12,
            "boiler-service": 10,
            "pressure-test": 12,
            "hydrant-check": 8,
            "valve-replacement": 12,
        },
        units_granted=44,
        roster={
            "meter-exchange": (9, 12),
            "mains-repair": (10, 11),
            "leak-survey": (9, 11),
            "boiler-service": (9, 10),
            "pressure-test": (10, 12),
            "hydrant-check": (11, 12),
            "valve-replacement": (10, 11),
        },
        rescoped="pressure-test",
        rescope_week=2,
        rescoped_scale=64.0,
        late_returns={"valve-replacement": (1, 1, 0, 1, 1, 0, 1, 1)},
    ),
    _spec(
        depot="dorley-2026-06",
        month="2026-06",
        as_of="2026-06-10",
        job_prefix="DOR",
        visit_prefix="DV",
        seed=843_8017,
        classes=(
            ("meter-exchange", 0.27, 23.0, 59.0),
            ("mains-repair", 0.21, 66.0, 200.0),
            ("leak-survey", 0.18, 25.0, 73.0),
            ("pressure-test", 0.15, 32.0, 95.0),
            ("hydrant-check", 0.12, 18.0, 43.0),
            ("valve-replacement", 0.07, 20.0, 117.0),
        ),
        pull=16,
        units_granted=40,
        roster={
            "meter-exchange": (9, 10),
            "mains-repair": (11, 12),
            "leak-survey": (9, 12),
            "pressure-test": (9, 11),
            "hydrant-check": (10, 12),
            "valve-replacement": (10, 11),
        },
        rescoped="pressure-test",
        rescope_week=3,
        rescoped_scale=62.0,
        late_returns={"valve-replacement": (1, 1, 0, 1, 1, 0, 1, 1)},
        audit_first_day="2026-04-06",
        visit_first_day="2026-06-01",
    ),
    _spec(
        depot="elverton-2026-06",
        month="2026-06",
        as_of="2026-06-10",
        job_prefix="ELV",
        visit_prefix="EV",
        seed=954_0023,
        classes=(
            ("meter-exchange", 0.30, 21.0, 57.0),
            ("mains-repair", 0.20, 69.0, 203.0),
            ("boiler-service", 0.17, 20.0, 65.0),
            ("regulator-swap", 0.14, 60.0, 174.0),
            ("leak-survey", 0.12, 24.0, 71.0),
            ("hydrant-check", 0.07, 18.0, 41.0),
        ),
        pull=8,
        units_granted=48,
        roster={
            "meter-exchange": (9, 11),
            "mains-repair": (10, 12),
            "boiler-service": (9, 12),
            "regulator-swap": (9, 10),
            "leak-survey": (11, 12),
            "hydrant-check": (10, 11),
        },
        rescoped="regulator-swap",
        rescope_week=5,
        rescoped_scale=70.0,
        audit_first_day="2026-04-06",
        visit_first_day="2026-06-01",
    ),
    _spec(
        depot="fairhaven-2026-06",
        month="2026-06",
        as_of="2026-06-10",
        job_prefix="FAI",
        visit_prefix="FV",
        seed=106_5029,
        classes=(
            ("mains-repair", 0.29, 67.0, 201.0),
            ("meter-exchange", 0.25, 22.0, 58.0),
            ("pressure-test", 0.20, 33.0, 93.0),
            ("leak-survey", 0.14, 25.0, 72.0),
            ("hydrant-check", 0.06, 18.0, 42.0),
            ("valve-replacement", 0.06, 21.0, 115.0),
        ),
        pull={
            "mains-repair": 16,
            "meter-exchange": 8,
            "pressure-test": 12,
            "leak-survey": 10,
            "hydrant-check": 14,
            "valve-replacement": 12,
        },
        units_granted=33,
        roster={
            "mains-repair": (9, 11),
            "meter-exchange": (9, 10),
            "pressure-test": (10, 12),
            "leak-survey": (11, 12),
            "hydrant-check": (10, 11),
            "valve-replacement": (9, 12),
        },
        rescoped="pressure-test",
        rescope_week=3,
        rescoped_scale=65.0,
        late_returns={"valve-replacement": (1, 1, 0, 1, 1, 0, 1, 1)},
        audit_first_day="2026-04-06",
        visit_first_day="2026-06-01",
    ),
)


LIFTED_SPEC = _spec(
    depot="garrow-2026-06",
    month="2026-06",
    as_of="2026-06-10",
    job_prefix="GAR",
    visit_prefix="GV",
    seed=217_7031,
    classes=(
        ("meter-exchange", 0.28, 21.0, 58.0),
        ("mains-repair", 0.21, 70.0, 204.0),
        ("leak-survey", 0.17, 24.0, 74.0),
        ("pressure-test", 0.14, 33.0, 95.0),
        ("boiler-service", 0.12, 19.0, 66.0),
        ("valve-replacement", 0.08, 20.0, 118.0),
    ),
    pull={
        "meter-exchange": 20,
        "mains-repair": 15,
        "leak-survey": 12,
        "pressure-test": 10,
        "boiler-service": 9,
        "valve-replacement": 6,
    },
    units_granted=36,
    roster={
        "meter-exchange": (9, 11),
        "mains-repair": (10, 12),
        "leak-survey": (9, 12),
        "pressure-test": (10, 12),
        "boiler-service": (11, 12),
        "valve-replacement": (9, 10),
    },
    audit_first_day="2026-04-06",
    visit_first_day="2026-06-01",
)


_CACHE: dict[str, world.Depot] = {}


def depot(spec: Mapping[str, Any]) -> world.Depot:
    key = str(spec["depot"])
    if key not in _CACHE:
        _CACHE[key] = world.build(spec)
    return _CACHE[key]


def current() -> world.Depot:
    return depot(CURRENT_SPEC)


def following() -> tuple[world.Depot, ...]:
    return tuple(depot(item) for item in FOLLOWING_SPECS)


def lifted() -> world.Depot:
    return depot(LIFTED_SPEC)


def with_pull(spec: Mapping[str, Any], pull: Mapping[str, int]) -> dict[str, Any]:
    'The same depot with the audit desk drawing a different pull.'

    changed = dict(spec)
    changed["depot"] = f"{spec['depot']}-pull"
    changed["pull"] = {str(name): int(size) for name, size in pull.items()}
    return changed


def with_rescoped(spec: Mapping[str, Any], job_class: str, scale: float) -> dict[str, Any]:
    'The same depot with the release landing on a different class.'

    changed = dict(spec)
    changed["depot"] = f"{spec['depot']}-swap"
    changed["rescoped"] = str(job_class)
    changed["rescoped_scale"] = float(scale)
    changed["rescope_week"] = int(spec["rescope_week"]) or 3
    return changed
