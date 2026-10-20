"The watch under study, the ones the same notebook is used on next, and the partner draws the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping

from .world import build, days_from, ramp_shares


PUBLICATION_WEIGHTS = (
    0.10, 0.11, 0.10, 0.09, 0.08, 0.08, 0.07,
    0.07, 0.06, 0.06, 0.06, 0.05, 0.04, 0.03,
)

SESSIONS = {"heavy": (26, 34), "medium": (8, 14), "light": (1, 3)}
REORDER_RATE = {"heavy": 0.31, "medium": 0.12, "light": 0.045}
DEFAULTS = (21000, 45000, 42000)


def _spec(
    watch: str,
    first_day: str,
    ramp: list[tuple[int, int]],
    base_mix: Mapping[str, float],
    daily_enrolments: int,
    lift_points: Mapping[str, float],
    reindex: Mapping[str, int],
    ship_line_points: float,
    points_left: int,
    base_users: int = 8200000,
    reorder_surface_rate: float = 0.13,
    reorder_rate: Mapping[str, float] | None = None,
    base_events: int = 21000,
    per_share_events: int = 45000,
    ceiling_events: int = 42000,
    share_cap_pct: int = 50,
    ramp_step_pct: int = 5,
    reorder_window_days: int = 14,
    looks_granted: int = 9,
    topic: str = "orders.reorder-confirmed",
    assignment_topic: str = "experiments.assignment",
) -> dict[str, Any]:
    length = sum(count for count, _share in ramp)
    days = days_from(first_day, length)
    spec: dict[str, Any] = {
        "watch": watch,
        "first_day": first_day,
        "ramp": [(int(count), int(share)) for count, share in ramp],
        "ramp_step_pct": ramp_step_pct,
        "bookings": (),
        "base_users": int(base_users),
        "base_mix": dict(base_mix),
        "sessions_28d": {tier: tuple(values) for tier, values in SESSIONS.items()},
        "reorder_surface_rate": float(reorder_surface_rate),
        "daily_enrolments": int(daily_enrolments),
        "reorder_rate": dict(reorder_rate or REORDER_RATE),
        "lift_points": dict(lift_points),
        "publication_weights": PUBLICATION_WEIGHTS,
        "reorder_window_days": int(reorder_window_days),
        "reindex_events": dict(reindex),
        "base_events": int(base_events),
        "per_share_events": int(per_share_events),
        "ceiling_events": int(ceiling_events),
        "topic": topic,
        "assignment_topic": assignment_topic,
        "ship_line_points": float(ship_line_points),
        "share_cap_pct": int(share_cap_pct),
        "cap_review_day": days_from(first_day, 56)[-1],
        "points_granted": 0,
        "looks": [days[index] for index in range(6, length, 7)],
        "looks_granted": int(looks_granted),
        "audience_counted_on": days_from(first_day, 1)[0],
    }
    spec["points_granted"] = int(sum(ramp_shares(spec))) + int(points_left)
    return spec


def _reindex(share_pct: int, fraction: float) -> int:
    "The extra events a republish has to put on the topic for that day's loss."

    base_events, per_share_events, ceiling = DEFAULTS
    offered = ceiling / (1.0 - fraction)
    return int(round(offered - base_events - round(per_share_events * share_pct / 100.0)))


CURRENT_SPEC = _spec(
    watch="one-tap-reorder",
    first_day="2026-07-06",
    ramp=[(7, 3), (7, 12), (7, 40), (7, 45), (7, 45)],
    base_mix={"heavy": 0.18, "medium": 0.34, "light": 0.48},
    daily_enrolments=5000,
    lift_points={"heavy": 2.78, "medium": 1.92, "light": 0.20},
    reindex={
        "2026-07-14": _reindex(12, 0.45),
        "2026-07-15": _reindex(12, 0.45),
        "2026-07-16": _reindex(12, 0.45),
    },
    ship_line_points=2.0,
    points_left=540,
)


HISTORY_BOOKINGS = (
    {"call_id": "ramp-w1", "share_pct": 3, "days": 7, "hold_ramp": True},
    {"call_id": "ramp-w2", "share_pct": 12, "days": 7, "hold_ramp": True},
    {"call_id": "ramp-w3", "share_pct": 40, "days": 7, "hold_ramp": True},
    {"call_id": "ramp-w4", "share_pct": 45, "days": 7, "hold_ramp": True},
    {"call_id": "ramp-w5", "share_pct": 45, "days": 7, "hold_ramp": True},
)


SIBLING_SPECS = (
    _spec(
        watch="saved-card-checkout",
        first_day="2026-06-15",
        ramp=[(7, 5), (7, 18), (7, 35), (7, 45), (7, 45)],
        base_mix={"heavy": 0.24, "medium": 0.32, "light": 0.44},
        daily_enrolments=6200,
        lift_points={"heavy": 3.40, "medium": 2.10, "light": 0.15},
        reindex={"2026-06-24": _reindex(18, 0.42), "2026-06-25": _reindex(18, 0.42)},
        ship_line_points=0.5,
        points_left=280,
    ),
    _spec(
        watch="address-book-refresh",
        first_day="2026-06-01",
        ramp=[(7, 8), (7, 20), (7, 30), (7, 40), (7, 40)],
        base_mix={"heavy": 0.12, "medium": 0.36, "light": 0.52},
        daily_enrolments=4400,
        lift_points={"heavy": 1.60, "medium": 0.90, "light": 0.05},
        reindex={},
        ship_line_points=1.5,
        points_left=190,
    ),
    _spec(
        watch="basket-reminder",
        first_day="2026-05-18",
        ramp=[(7, 6), (7, 14), (7, 38), (7, 45), (7, 45)],
        base_mix={"heavy": 0.20, "medium": 0.30, "light": 0.50},
        daily_enrolments=5600,
        lift_points={"heavy": 3.10, "medium": 1.60, "light": 0.30},
        reindex={
            "2026-05-27": _reindex(14, 0.38),
            "2026-05-28": _reindex(14, 0.38),
            "2026-05-29": _reindex(14, 0.38),
        },
        ship_line_points=2.0,
        points_left=430,
    ),
    _spec(
        watch="search-suggestions",
        first_day="2026-05-04",
        ramp=[(7, 5), (7, 16), (7, 36), (7, 45), (7, 45),
              (7, 45), (7, 45), (7, 45), (7, 45)],
        base_mix={"heavy": 0.15, "medium": 0.33, "light": 0.52},
        daily_enrolments=12000,
        lift_points={"heavy": 1.10, "medium": 1.10, "light": 1.10},
        reindex={},
        ship_line_points=1.0,
        points_left=300,
        looks_granted=14,
    ),
)


OUT_OF_REGIME_SPEC = _spec(
    watch="weekend-delivery-slots",
    first_day="2026-04-06",
    ramp=[(7, 4), (7, 15), (7, 38), (7, 45), (7, 45)],
    base_mix={"heavy": 0.16, "medium": 0.35, "light": 0.49},
    daily_enrolments=5200,
    lift_points={"heavy": 2.60, "medium": 1.70, "light": 0.15},
    reindex={
        "2026-05-05": _reindex(45, 0.45),
        "2026-05-06": _reindex(45, 0.45),
        "2026-05-07": _reindex(45, 0.45),
    },
    ship_line_points=1.5,
    points_left=360,
)


def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


PARTNER_SPECS = (
    _variant(CURRENT_SPEC, watch="one-tap-reorder-tablet", reindex_events={}),
    _variant(CURRENT_SPEC, watch="one-tap-reorder-web", ramp=[(35, 25)]),
)

CURRENT = build(CURRENT_SPEC)


LOOK_BUDGET_PROBE_LOOKS = (20, 40)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
OUT_OF_REGIME = build(OUT_OF_REGIME_SPEC)
PARTNERS = tuple(build(spec) for spec in PARTNER_SPECS)


SHED_PARTNER, RAMP_PARTNER = PARTNERS
