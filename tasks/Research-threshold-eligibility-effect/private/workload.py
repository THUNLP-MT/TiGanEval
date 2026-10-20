"The market under study, the markets the same notebook is run over next, and the two re-presentations of this one the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping

from .world import build


TIER_MIX = (0.15, 0.20, 0.30, 0.20, 0.15)
TIER_BUMP = (-0.06, -0.03, 0.0, 0.03, 0.06)

CARRIED_BY_TIER = (1.6, 1.3, 1.0, 0.7, 0.4)

REFRESH_DRIFT = (0.0, 0.0, 4.0, 6.0, 8.0)

CREDIT_OVER = (0.0, 0.25, 0.5, 0.75)


def _spec(
    market: str,
    first_day: str,
    accounts: int,
    cut: float,
    effect: float,
    *,
    account_prefix: str,
    credit_ceiling: float = 1.0,
    credit_share: float = 0.050,
    carried_share: float = 0.11,
    refresh_share: float = 0.42,
    credit_favour: float = 0.22,
    refresh_batches: tuple[tuple[str, int], ...] = (("R-1", 33), ("R-2", 39)),
    export_stop_day: int = 84,
    run_weeks: int = 10,
    core_share: float = 0.55,
    core_sd: float = 4.0,
    spread_sd: float = 14.0,
    rate_floor: float = 0.21,
    rate_span: float = 0.28,
    rate_knee: float = 14.0,
    rate_width: float = 4.5,
    effect_reach: float | None = None,
    files_granted: int = 300,
    opening_lots: tuple[Mapping[str, Any], ...] = (),
) -> dict[str, Any]:
    return {
        "market": market,
        "account_prefix": account_prefix,
        "first_day": first_day,
        "window_days": 90,
        "export_stop_day": int(export_stop_day),
        "publication_lag_days": 2,
        "order_window_days": 60,
        "run_weeks": int(run_weeks),
        "accounts": int(accounts),
        "cut": float(cut),
        "band_points": 5.0,
        "credit_ceiling": float(credit_ceiling),
        "credit_share": float(credit_share),
        "credit_tier_floor": 0,
        "credit_over": CREDIT_OVER,
        "credit_cutoff_day": 1,
        "carried_share": float(carried_share),
        "carried_by_tier": CARRIED_BY_TIER,
        "carried_penalty": 0.22,
        "week_lift": 0.55,
        "refresh_gain": 0.025,
        "credit_favour": float(credit_favour),
        "tier_mix": TIER_MIX,
        "tier_bump": TIER_BUMP,
        "refresh_share": float(refresh_share),
        "refresh_batches": refresh_batches,
        "refresh_drift": REFRESH_DRIFT,
        "score_low": 30.0,
        "score_high": 92.0,
        "core_share": float(core_share),
        "core_sd": float(core_sd),
        "spread_sd": float(spread_sd),
        "rate_floor": float(rate_floor),
        "rate_span": float(rate_span),
        "rate_knee": float(rate_knee),
        "rate_width": float(rate_width),
        "rate_middle": float(cut),
        "effect": float(effect),
        "effect_reach": effect_reach,
        "files_granted": int(files_granted),
        "files_per_booking": 60,
        "smallest_lot": 20,
        "above_share_low": 0.3,
        "above_share_high": 0.7,
        "markets_on_the_slide": 7,
        "range_bar_points": 5.0,
        "opening_lots": opening_lots,
    }


CURRENT_SPEC = _spec(
    market="northgate",
    account_prefix="NG",
    first_day="2026-03-02",
    accounts=11000,
    cut=61.0,
    effect=1.80,
    opening_lots=(
        {"receipt_id": "RL-0117", "week": 3, "band": 2.0, "above_share": 0.5, "files": 40},
        {"receipt_id": "RL-0118", "week": 4, "band": 2.0, "above_share": 0.85, "files": 25},
    ),
)


SIBLING_SPECS = (
    _spec(
        market="westmoor",
        account_prefix="WM",
        first_day="2026-02-09",
        accounts=22000,
        cut=58.5,
        effect=2.30,
        credit_ceiling=0.75,
        credit_share=0.038,
        carried_share=0.09,
        refresh_share=0.34,
        refresh_batches=(("W-1", 30), ("W-2", 37)),
        export_stop_day=86,
        core_share=0.92,
        core_sd=3.0,
        files_granted=180,
        opening_lots=(
            {"receipt_id": "WM-0043", "week": 2, "band": 1.5, "above_share": 0.5, "files": 45},
        ),
    ),
    _spec(
        market="fairholm",
        account_prefix="FH",
        first_day="2026-01-19",
        accounts=9000,
        cut=63.25,
        effect=0.70,
        credit_ceiling=1.5,
        credit_share=0.105,
        carried_share=0.14,
        refresh_share=0.46,
        refresh_batches=(("F-1", 26), ("F-2", 34)),
        export_stop_day=80,
        core_share=0.50,
        core_sd=4.6,
        files_granted=240,
        opening_lots=(
            {"receipt_id": "FH-0088", "week": 5, "band": 3.0, "above_share": 0.6, "files": 55},
        ),
    ),
    _spec(
        market="lindale",
        account_prefix="LD",
        first_day="2026-02-23",
        accounts=9000,
        cut=59.75,
        effect=1.95,
        credit_ceiling=0.5,
        credit_share=0.041,
        carried_share=0.08,
        refresh_share=0.38,
        refresh_batches=(("L-1", 36), ("L-2", 43)),
        export_stop_day=82,
        core_share=0.62,
        core_sd=3.6,
        files_granted=120,
        opening_lots=(
            {"receipt_id": "LD-0021", "week": 6, "band": 2.5, "above_share": 0.4, "files": 30},
        ),
    ),
)


OUT_OF_REGIME_SPEC = _spec(
    market="easthaven",
    account_prefix="EH",
    first_day="2025-12-01",
    accounts=7000,
    cut=60.5,
    effect=22.0,
    effect_reach=1.0,
    credit_ceiling=0.0,
    credit_share=0.0,
    carried_share=0.10,
    refresh_share=0.40,
    refresh_batches=(("E-1", 1), ("E-2", 1)),
    export_stop_day=84,
    core_share=0.58,
    core_sd=4.2,
    files_granted=200,
    opening_lots=(
        {"receipt_id": "EH-0009", "week": 2, "band": 2.0, "above_share": 0.5, "files": 35},
    ),
)


def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


REISSUE_SPECS = (
    _variant(
        CURRENT_SPEC,
        market="northgate-batch-redrawn",
        account_prefix="NB",
        refresh_batches=(("R-3", 26), ("R-4", 45)),
    ),
    _variant(
        CURRENT_SPEC,
        market="northgate-stop-moved",
        account_prefix="NS",
        export_stop_day=74,
    ),
)


CURRENT = build(CURRENT_SPEC)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
OUT_OF_REGIME = build(OUT_OF_REGIME_SPEC)
REISSUES = tuple(build(spec) for spec in REISSUE_SPECS)


BATCH_REISSUE, STOP_REISSUE = REISSUES

PRECISE = SIBLINGS[0]
