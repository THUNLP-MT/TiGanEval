"The desk under review, the desks the same notebook is used on next, and the partner draws the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping

from .world import booked, build, days_from, history_stream


ERROR_VALUES = (0.5, 0.8, 1.1, 1.5)
TIERS = ("standard", "premier")


WAIT_WEIGHTS = {
    2: 0.14, 3: 0.19, 4: 0.16, 5: 0.12, 6: 0.07,
    7: 0.11, 8: 0.08, 9: 0.06, 10: 0.04, 11: 0.02, 12: 0.01,
    13: 0.0, 14: 0.0, 15: 0.0, 16: 0.0,
}


WAIT_WEIGHTS_SHORT = {
    2: 0.18, 3: 0.24, 4: 0.20, 5: 0.14, 6: 0.06,
    7: 0.07, 8: 0.05, 9: 0.03, 10: 0.02, 11: 0.01, 12: 0.0,
    13: 0.0, 14: 0.0, 15: 0.0, 16: 0.0,
}


WAIT_WEIGHTS_REDRAWN = {
    2: 0.14, 3: 0.19, 4: 0.16, 5: 0.12, 6: 0.07,
    7: 0.0, 8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0,
    13: 0.10, 14: 0.10, 15: 0.08, 16: 0.04,
}


def _spec(
    desk: str,
    first_day: str,
    book: Mapping[tuple[float, str], int],
    flag_base: float,
    hazard: Mapping[float, float],
    effect: Mapping[str, float],
    bar_before: float,
    bar_after: float,
    bar_move_day: int,
    migration_day: int,
    grace_window_days: int,
    slots_granted: int,
    calls: tuple[Mapping[str, Any], ...],
    *,
    window_days: int = 91,
    wait_weights: Mapping[int, float] | None = None,
    week_load: tuple[float, ...] = (1.0, 1.06, 0.94, 1.11, 0.97, 1.03, 1.14,
                                    0.92, 1.08, 0.96, 1.12, 0.98, 1.05),
    same_day_share_above: float = 0.78,
    same_day_share_below: float = 0.32,
    state_shares: Mapping[str, float] | None = None,
    flag_power: float = 0.9,
    flag_tier_rate: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    days = days_from(first_day, window_days)
    return {
        "desk": desk,
        "first_day": first_day,
        "window_days": int(window_days),
        "error_values": ERROR_VALUES,
        "tiers": TIERS,
        "book": {(float(key[0]), str(key[1])): int(value) for key, value in book.items()},
        "book_counted_on": days[0],
        "flag_base": float(flag_base),
        "flag_power": float(flag_power),
        "flag_tier_rate": dict(flag_tier_rate or {"standard": 1.0, "premier": 4.0}),
        "hazard": {float(key): float(value) for key, value in hazard.items()},
        "effect": {str(key): float(value) for key, value in effect.items()},
        "state_shares": dict(
            state_shares or {"active": 0.90, "trial": 0.06, "suspended": 0.04}
        ),
        "state_hazard_mult": {"active": 1.0, "trial": 1.35, "suspended": 1.6},
        "prior_trial_share": 0.11,
        "bar_before": float(bar_before),
        "bar_after": float(bar_after),
        "bar_move_day": int(bar_move_day),
        "same_day_share_above": float(same_day_share_above),
        "same_day_share_below": float(same_day_share_below),
        "wait_weights": dict(wait_weights or WAIT_WEIGHTS),
        "week_load": tuple(week_load),
        "deep_week_load": 1.05,
        "deep_week_push": 0.45,
        "grace_window_days": int(grace_window_days),
        "risk_window_days": 28,
        "migration_day": int(migration_day),
        "record_lag_days": 2,
        "slots_granted": int(slots_granted),
        "slots_per_week": 40,
        "hold_cap": 0.6,
        "handed_back_charge": 10,
        "smallest_week_slots": 10,
        "review_bar_points": 4.0,
        "review_day": days[-1],
        "bookings": tuple(
            {
                "segment": str(call.get("segment", "all")),
                "hold_share": float(call.get("hold_share", 0.0)),
                "slots": int(call.get("slots", 0)),
                "accepted": not str(call.get("refusal", "")),
            }
            for call in calls
        ),
        "calls": tuple(dict(call) for call in calls),
    }


def _book(total: int, bands: Mapping[float, float], premier: float) -> dict:
    'The accounts a desk carries at each error rate and plan tier.'

    return {
        (float(band), tier): int(round(total * share * (premier if tier == "premier"
                                                        else 1.0 - premier)))
        for band, share in bands.items()
        for tier in TIERS
    }


BOOK = _book(14000, {0.5: 0.34, 0.8: 0.30, 1.1: 0.22, 1.5: 0.14}, 0.30)

HAZARD = {0.5: 0.0120, 0.8: 0.0190, 1.1: 0.0280, 1.5: 0.0380}
EFFECT = {"standard": 0.28, "premier": 0.82}


CURRENT_CALLS = (
    {"receipt_id": "wk11-hold-all", "segment": "all", "hold_share": 0.75, "slots": 40,
     "refusal": "the desk holds at most 60 percent of a week's flags and this call "
                "asked to hold 75"},
    {"receipt_id": "wk12-premier-only", "segment": "plan_tier=premier",
     "hold_share": 0.5, "slots": 45,
     "refusal": "the desk books at most 40 slots in a week and this call asked for 45"},
)

CURRENT_SPEC = _spec(
    desk="northfield-managed",
    first_day="2026-01-05",
    book=BOOK,
    flag_base=0.0026,
    hazard=HAZARD,
    effect=EFFECT,
    bar_before=1.2,
    bar_after=0.9,
    bar_move_day=35,
    migration_day=78,
    grace_window_days=6,
    slots_granted=240,
    calls=CURRENT_CALLS,
)


SIBLING_SPECS = (
    _spec(
        desk="calder-managed",
        first_day="2025-11-17",
        book=_book(12500, {0.5: 0.30, 0.8: 0.30, 1.1: 0.24, 1.5: 0.16}, 0.36),
        flag_base=0.0034,
        hazard={0.5: 0.0145, 0.8: 0.0215, 1.1: 0.0310, 1.5: 0.0420},
        effect={"standard": 0.33, "premier": 0.77},
        bar_before=1.0,
        bar_after=0.8,
        bar_move_day=28,
        migration_day=71,
        grace_window_days=5,
        slots_granted=240,
        calls=(
            {"receipt_id": "cal-w1", "segment": "all", "hold_share": 0.4, "slots": 40},
            {"receipt_id": "cal-w2", "segment": "plan_tier=standard",
             "hold_share": 0.55, "slots": 35},
            {"receipt_id": "cal-w3", "segment": "error_rate_7d=9.9", "hold_share": 0.4,
             "slots": 20,
             "refusal": "no flags fell in that segment that week, so there was nothing "
                        "to serve"},
        ),
        same_day_share_above=0.72,
        same_day_share_below=0.40,
    ),
    _spec(
        desk="brayside-managed",
        first_day="2025-12-01",
        book=_book(16000, {0.5: 0.40, 0.8: 0.28, 1.1: 0.20, 1.5: 0.12}, 0.26),
        flag_base=0.0041,
        hazard={0.5: 0.0098, 0.8: 0.0160, 1.1: 0.0240, 1.5: 0.0330},
        effect={"standard": 0.24, "premier": 0.86},
        bar_before=1.4,
        bar_after=1.1,
        bar_move_day=42,
        migration_day=83,
        grace_window_days=7,
        slots_granted=240,
        calls=(
            {"receipt_id": "bray-w1", "segment": "all", "hold_share": 0.5, "slots": 40},
        ),
        same_day_share_above=0.75,
        same_day_share_below=0.35,
    ),
    _spec(
        desk="dunmoor-managed",
        first_day="2025-10-06",
        book=_book(13000, {0.5: 0.28, 0.8: 0.30, 1.1: 0.26, 1.5: 0.16}, 0.34),
        flag_base=0.0019,
        hazard={0.5: 0.0138, 0.8: 0.0205, 1.1: 0.0300, 1.5: 0.0405},
        effect={"standard": 0.35, "premier": 0.75},
        bar_before=1.2,
        bar_after=0.9,
        bar_move_day=49,
        migration_day=76,
        grace_window_days=6,
        slots_granted=240,
        calls=(
            {"receipt_id": "dun-w1", "segment": "all", "hold_share": 0.45, "slots": 40},
            {"receipt_id": "dun-w2", "segment": "all", "hold_share": 0.5, "slots": 40},
            {"receipt_id": "dun-w3", "segment": "plan_tier=premier", "hold_share": 0.5,
             "slots": 30},
            {"receipt_id": "dun-w4", "segment": "all", "hold_share": 0.8, "slots": 30,
             "refusal": "the desk holds at most 60 percent of a week's flags and this "
                        "call asked to hold 80"},
        ),
        same_day_share_above=0.82,
        same_day_share_below=0.28,
        wait_weights=WAIT_WEIGHTS_SHORT,
    ),
)


OUT_OF_REGIME_SPEC = _spec(
    desk="stanhope-managed",
    first_day="2025-09-15",
    book=_book(15000, {0.5: 0.33, 0.8: 0.31, 1.1: 0.22, 1.5: 0.14}, 0.31),
    flag_base=0.0026,
    hazard={0.5: 0.0110, 0.8: 0.0175, 1.1: 0.0260, 1.5: 0.0350},
    effect={"standard": 0.27, "premier": 0.80},
    bar_before=0.0,
    bar_after=0.0,
    bar_move_day=0,
    migration_day=80,
    grace_window_days=6,
    slots_granted=240,
    calls=(
        {"receipt_id": "stan-w1", "segment": "all", "hold_share": 0.4, "slots": 40},
    ),
    same_day_share_above=0.60,
    same_day_share_below=0.60,
    wait_weights={
        1: 0.26, 2: 0.30, 3: 0.22, 4: 0.14, 5: 0.08, 6: 0.0,
        7: 0.0, 8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0,
        13: 0.0, 14: 0.0, 15: 0.0, 16: 0.0,
    },
)


def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


PARTNER_SPECS = (
    _variant(
        CURRENT_SPEC,
        desk="northfield-managed-queue-reissue",
        wait_weights=dict(WAIT_WEIGHTS_REDRAWN),
    ),
    _variant(
        CURRENT_SPEC,
        desk="northfield-managed-export-reissue",
        migration_day=88,
    ),
)

def _served(spec):
    "The desk's window with the weeks it has already booked served on to it."

    return booked(build(spec), spec["bookings"])


CURRENT_BASE = build(CURRENT_SPEC)
CURRENT = booked(CURRENT_BASE, CURRENT_SPEC["bookings"])
SIBLING_BASES = tuple(build(spec) for spec in SIBLING_SPECS)
SIBLINGS = tuple(
    booked(base, spec["bookings"]) for base, spec in zip(SIBLING_BASES, SIBLING_SPECS)
)
OUT_OF_REGIME_BASE = build(OUT_OF_REGIME_SPEC)
OUT_OF_REGIME = booked(OUT_OF_REGIME_BASE, OUT_OF_REGIME_SPEC["bookings"])
PARTNER_BASES = tuple(build(spec) for spec in PARTNER_SPECS)
PARTNERS = tuple(
    booked(base, spec["bookings"]) for base, spec in zip(PARTNER_BASES, PARTNER_SPECS)
)
BASES = {
    world.desk: base
    for world, base in zip(
        (CURRENT, *SIBLINGS, OUT_OF_REGIME, *PARTNERS),
        (CURRENT_BASE, *SIBLING_BASES, OUT_OF_REGIME_BASE, *PARTNER_BASES),
    )
}


QUEUE_PARTNER, EXPORT_PARTNER = PARTNERS

HISTORY_CALLS = CURRENT_SPEC["calls"]


def opening_receipts(world) -> list[dict[str, Any]]:
    'The receipt stream a desk starts the review with.'

    return history_stream(world, world.spec["calls"])
