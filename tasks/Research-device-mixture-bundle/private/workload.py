'The campaign under review, the fleets the same notebook runs next, and the two ways this export is reissued.'

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from . import world


def _profile(
    units: int,
    reached_units: int,
    log_rows_each: int,
    raised_units: int,
    raised_reached_units: int,
    shares: tuple[float, float, float, float],
    unit_model: str,
) -> dict[str, Any]:
    return {
        "units": int(units),
        "reached_units": int(reached_units),
        "log_rows_each": int(log_rows_each),
        "raised_units": int(raised_units),
        "raised_reached_units": int(raised_reached_units),
        "shares": tuple(float(value) for value in shares),
        "unit_model": str(unit_model),
    }


def _spec(
    campaign: str,
    fleet: str,
    unit_prefix: str,
    request_prefix: str,
    first_day: str,
    days: int,
    seed: int,
    label_offset: float,
    gain: float,
    rollout_from: str,
    credits_granted: int,
    profiles: Mapping[str, Any],
    as_of: str = "2026-09-04",
    promise_points: float = 16.0,
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "fleet": fleet,
        "unit_prefix": unit_prefix,
        "request_prefix": request_prefix,
        "first_day": first_day,
        "days": int(days),
        "seed": int(seed),
        "label_offset": float(label_offset),
        "share_jitter": 0.0,
        "truth_captures": 72,
        "gain": float(gain),
        "raised_firmware": "4.2",
        "earlier_firmware": "4.1",
        "rollout_from": rollout_from,
        "credits_granted": int(credits_granted),
        "promise_points": float(promise_points),
        "as_of": as_of,
        "reach_offset": 0,
        "rollout_offset": 0,
        "profiles": dict(profiles),
    }


HARROWGATE_MIX = {
    "counter": (0.90, 0.00, 0.10, 0.00),
    "backroom": (0.25, 0.55, 0.05, 0.15),
    "yard": (0.10, 0.10, 0.75, 0.05),
    "night": (0.05, 0.72, 0.05, 0.18),
}
LEDBURY_MIX = {
    "counter": (0.88, 0.00, 0.12, 0.00),
    "backroom": (0.30, 0.50, 0.08, 0.12),
    "yard": (0.35, 0.30, 0.25, 0.10),
    "night": (0.06, 0.66, 0.06, 0.22),
}
ASHFIELD_MIX = {
    "counter": (0.85, 0.00, 0.15, 0.00),
    "backroom": (0.30, 0.45, 0.10, 0.15),
    "yard": (0.05, 0.05, 0.85, 0.05),
    "night": (0.05, 0.78, 0.05, 0.12),
}
PENHALE_MIX = {
    "counter": (0.92, 0.00, 0.08, 0.00),
    "backroom": (0.25, 0.55, 0.05, 0.15),
    "yard": (0.30, 0.30, 0.30, 0.10),
    "night": (0.05, 0.55, 0.25, 0.15),
}
FERRERS_MIX = {profile: (0.72, 0.12, 0.12, 0.04) for profile in world.PROFILES}


CURRENT_SPEC = _spec(
    campaign="harrowgate-q3",
    fleet="harrowgate",
    unit_prefix="HG",
    request_prefix="HGR",
    first_day="2026-06-15",
    days=82,
    seed=511_0007,
    label_offset=0.37,
    gain=1.6,
    rollout_from="2026-07-13",
    credits_granted=1200,
    profiles={
        "counter": _profile(300, 90, 72, 36, 4, HARROWGATE_MIX["counter"], "hs-410"),
        "backroom": _profile(200, 20, 45, 81, 5, HARROWGATE_MIX["backroom"], "hs-410"),
        "yard": _profile(180, 24, 60, 94, 15, HARROWGATE_MIX["yard"], "hs-620"),
        "night": _profile(100, 18, 60, 54, 13, HARROWGATE_MIX["night"], "hs-620"),
    },
)


FOLLOWING_SPECS = (
    _spec(
        campaign="ledbury-q3",
        fleet="ledbury",
        unit_prefix="LB",
        request_prefix="LBR",
        first_day="2026-06-22",
        days=74,
        seed=622_0013,
        label_offset=0.19,
        gain=1.35,
        rollout_from="2026-07-27",
        credits_granted=900,
        profiles={
            "counter": _profile(300, 64, 66, 22, 3, LEDBURY_MIX["counter"], "hs-410"),
            "backroom": _profile(120, 18, 50, 34, 5, LEDBURY_MIX["backroom"], "hs-410"),
            "yard": _profile(150, 26, 55, 62, 16, LEDBURY_MIX["yard"], "hs-620"),
            "night": _profile(60, 20, 55, 34, 13, LEDBURY_MIX["night"], "hs-620"),
        },
    ),
    _spec(
        campaign="ashfield-q3",
        fleet="ashfield",
        unit_prefix="AF",
        request_prefix="AFR",
        first_day="2026-07-06",
        days=68,
        seed=733_0019,
        label_offset=0.61,
        gain=1.8,
        rollout_from="2026-07-06",
        credits_granted=1500,
        profiles={
            "counter": _profile(380, 96, 70, 96, 24, ASHFIELD_MIX["counter"], "hs-410"),
            "backroom": _profile(90, 16, 50, 44, 9, ASHFIELD_MIX["backroom"], "hs-410"),
            "yard": _profile(100, 22, 55, 76, 18, ASHFIELD_MIX["yard"], "hs-620"),
            "night": _profile(110, 24, 55, 92, 21, ASHFIELD_MIX["night"], "hs-620"),
        },
    ),
    _spec(
        campaign="penhale-q3",
        fleet="penhale",
        unit_prefix="PH",
        request_prefix="PHR",
        first_day="2026-07-13",
        days=64,
        seed=844_0029,
        label_offset=0.83,
        gain=1.5,
        rollout_from="2026-08-10",
        credits_granted=1050,
        profiles={
            "counter": _profile(260, 52, 60, 21, 3, PENHALE_MIX["counter"], "hs-410"),
            "backroom": _profile(200, 22, 50, 62, 7, PENHALE_MIX["backroom"], "hs-410"),
            "yard": _profile(190, 28, 55, 108, 17, PENHALE_MIX["yard"], "hs-620"),
            "night": _profile(70, 20, 55, 48, 14, PENHALE_MIX["night"], "hs-620"),
        },
    ),
)


UNIFORM_SPEC = _spec(
    campaign="ferrers-q3",
    fleet="ferrers",
    unit_prefix="FR",
    request_prefix="FRR",
    first_day="2026-07-20",
    days=58,
    seed=955_0037,
    label_offset=0.29,
    gain=1.55,
    rollout_from="2026-09-30",
    credits_granted=155,
    profiles={
        "counter": _profile(240, 44, 60, 0, 0, FERRERS_MIX["counter"], "hs-410"),
        "backroom": _profile(150, 24, 55, 0, 0, FERRERS_MIX["backroom"], "hs-410"),
        "yard": _profile(150, 24, 55, 0, 0, FERRERS_MIX["yard"], "hs-620"),
        "night": _profile(100, 22, 55, 0, 0, FERRERS_MIX["night"], "hs-620"),
    },
)


def _reissued(
    campaign: str,
    reach_offset: int,
    reach: Mapping[str, tuple[int, int]] | None = None,
    rollout: Mapping[str, tuple[int, int]] | None = None,
    rollout_from: str | None = None,
) -> dict[str, Any]:
    "This fleet's export written again with the reach or the rollout redrawn."

    spec = deepcopy(CURRENT_SPEC)
    spec["campaign"] = campaign
    spec["reach_offset"] = int(reach_offset)
    if reach is not None:
        for profile, (units, raised_reached) in reach.items():
            spec["profiles"][profile]["reached_units"] = int(units)
            spec["profiles"][profile]["raised_reached_units"] = int(raised_reached)
    if rollout is not None:
        spec["rollout_offset"] = 5
        spec["rollout_from"] = str(rollout_from or spec["rollout_from"])
        for profile, (units, raised_reached) in rollout.items():
            spec["profiles"][profile]["raised_units"] = int(units)
            spec["profiles"][profile]["raised_reached_units"] = int(raised_reached)
    return spec


REACH_REDRAWN_SPEC = _reissued(
    "harrowgate-q3-reach",
    0,
    reach={"counter": (170, 8)},
)


ROLLOUT_REDRAWN_SPEC = _reissued(
    "harrowgate-q3-rollout",
    0,
    rollout={"counter": (12, 1), "backroom": (28, 1), "yard": (74, 5), "night": (42, 4)},
    rollout_from="2026-08-17",
)


_CACHE: dict[str, world.Fleet] = {}


def fleet(spec: Mapping[str, Any]) -> world.Fleet:
    key = str(spec["campaign"])
    if key not in _CACHE:
        _CACHE[key] = world.build(spec)
    return _CACHE[key]


def current() -> world.Fleet:
    return fleet(CURRENT_SPEC)


def following() -> tuple[world.Fleet, ...]:
    return tuple(fleet(spec) for spec in FOLLOWING_SPECS)


def uniform() -> world.Fleet:
    return fleet(UNIFORM_SPEC)


def reach_redrawn() -> world.Fleet:
    return fleet(REACH_REDRAWN_SPEC)


def rollout_redrawn() -> world.Fleet:
    return fleet(ROLLOUT_REDRAWN_SPEC)
