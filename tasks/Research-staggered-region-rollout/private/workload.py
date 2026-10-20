"The network under study, the ones the same notebook runs next, and the draws the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import build, days_from, shift


HALCOMBE_REGIONS = (
    ("Harrow Bay", "core", 0.94, 86.5, 0.5, 1500, 0.052),
    ("Ostley", "core", 0.91, 85.0, 1.3, 1200, 0.038),
    ("Cardean", "inner", 0.88, 85.4, 0.7, 1000, 0.061),
    ("Millgate", "inner", 0.85, 84.0, 1.3, 900, 0.044),
    ("Thrushwood", "outer", 0.82, 82.6, 3.4, 700, 0.075),
    ("Riverbend", "outer", 0.79, 82.0, 4.6, 3000, 0.031),
    ("Alder", "coastal", 0.75, 84.9, 0.6, 1100, 0.058),
    ("Kingsmere", "coastal", 0.72, 83.1, 1.2, 800, 0.067),
    ("Balnaby", "ring", 0.64, 83.3, 0.5, 950, 0.041),
    ("Evermoor", "ring", 0.60, 81.6, 4.5, 3000, 0.036),
    ("Vell", "coastal", 0.55, 80.6, 3.1, 1200, 0.049),
    ("Fennhaven", "core", 0.51, 81.9, 0.7, 1400, 0.055),
    ("Draymoor", "inner", 0.47, 80.0, 1.5, 1100, 0.080),
    ("Sculthorpe", "ring", 0.43, 79.2, 2.9, 900, 0.070),
    ("Corbel Ness", "outer", 0.38, 78.4, 3.0, 1000, 0.063),
    ("Wraymouth", "ring", 0.33, 80.6, 0.8, 300, 0.046),
)

DRIFT = {"core": 0.034, "inner": 0.028, "outer": 0.016, "coastal": 0.022, "ring": 0.010}


def _spec(
    network: str,
    first_day: str,
    regions: Sequence[Sequence[Any]],
    live_offsets: Sequence[int],
    book_regions: Sequence[str],
    book_counted_on: str,
    window_closes_on: str,
    bookable_weeks: Sequence[str],
    *,
    days: int = 126,
    clock_lift_points: float = 5.4,
    migration_lead_days: Sequence[int] = (3, 2, 5, 4),
    january_wave: Mapping[str, int] | None = None,
    rollback: Mapping[str, Any] | None = None,
    incidents: Sequence[Sequence[Any]] = (),
    band_drift_points: Mapping[str, float] | None = None,
    region_weeks_granted: int = 12,
    region_weeks_per_week: int = 3,
    holdback_share_band: Sequence[int] = (20, 40),
    minimum_orders_per_day: int = 400,
    board_bar_points: float = 1.5,
    networks_reviewed: int = 4,
    exposure_days: int = 28,
    baseline_days: int = 28,
    settle_days: int = 7,
    settle_penalty_points: float = 0.0,
    order_growth: float = 0.0008,
    ceiling_points: float = 99.0,
) -> dict[str, Any]:
    return {
        "network": network,
        "first_day": first_day,
        "days": int(days),
        "regions": [
            {
                "name": name,
                "band": band,
                "readiness": readiness,
                "level_points": level,
                "effect_points": effect,
                "orders_per_day": orders,
                "sample_rate": rate,
            }
            for name, band, readiness, level, effect, orders, rate in regions
        ],
        "live_offsets": tuple(int(value) for value in live_offsets),
        "migration_lead_days": tuple(int(value) for value in migration_lead_days),
        "january_wave": dict(january_wave or {}),
        "rollback": dict(rollback or {}),
        "incidents": tuple(tuple(item) for item in incidents),
        "band_drift_points": dict(band_drift_points or DRIFT),
        "clock_lift_points": float(clock_lift_points),
        "settle_days": int(settle_days),
        "settle_penalty_points": float(settle_penalty_points),
        "order_growth": float(order_growth),
        "ceiling_points": float(ceiling_points),
        "exposure_days": int(exposure_days),
        "baseline_days": int(baseline_days),
        "book_regions": tuple(book_regions),
        "book_counted_on": str(book_counted_on),
        "window_closes_on": str(window_closes_on),
        "board_bar_points": float(board_bar_points),
        "networks_reviewed": int(networks_reviewed),
        "region_weeks_granted": int(region_weeks_granted),
        "region_weeks_per_week": int(region_weeks_per_week),
        "holdback_share_band": tuple(int(value) for value in holdback_share_band),
        "minimum_orders_per_day": int(minimum_orders_per_day),
        "bookable_weeks": tuple(bookable_weeks),
    }


CURRENT_SPEC = _spec(
    network="halcombe",
    first_day="2026-01-05",
    regions=HALCOMBE_REGIONS,
    live_offsets=(20, 26, 34, 40, 50, 58, 66, 74, 93, 110),
    book_regions=(
        "Harrow Bay", "Ostley", "Cardean", "Millgate", "Thrushwood", "Riverbend",
        "Alder", "Kingsmere", "Evermoor", "Sculthorpe", "Fennhaven", "Draymoor",
    ),
    book_counted_on="2026-02-01",
    window_closes_on="2026-04-20",
    bookable_weeks=("2026-05-11", "2026-05-18", "2026-05-25", "2026-06-01"),
    january_wave={"Alder": 3, "Kingsmere": 12, "Vell": 8},
    rollback={"region": "Riverbend", "on_day": 65, "note": "batching disabled"},
    incidents=(
        ("Millgate", 33, "22:05", "paged", "dispatch queue depth alarm, cleared on its own"),
        ("Riverbend", 64, "23:50", "paged", "assignment workers in a crash loop, restarted twice"),
        ("Riverbend", 65, "02:15", "restarted", "third restart of the assignment workers"),
        ("Harrow Bay", 71, "14:20", "reloaded", "routing table reload after the depot move"),
        ("Cardean", 88, "06:40", "degraded", "label printer out at the north depot, 90 minutes"),
        ("Kingsmere", 101, "19:10", "paged", "courier sign-in errors, cleared by 20:00"),
    ),
)


HISTORY_BOOKINGS = (
    {"region": "Sculthorpe", "week": "2026-04-27", "holdback_share": 25},
    {"region": "Balnaby", "week": "2026-05-04", "holdback_share": 30},
)


ASHGATE_REGIONS = (
    ("Bellwether", "core", 0.93, 86.2, 0.6, 1400, 0.045),
    ("Netherfold", "core", 0.89, 84.8, 1.4, 1150, 0.052),
    ("Oxcombe", "inner", 0.86, 85.1, 0.5, 980, 0.039),
    ("Marlbrook", "inner", 0.82, 83.6, 1.6, 860, 0.064),
    ("Hallowfield", "outer", 0.78, 80.9, 2.9, 720, 0.071),
    ("Starling Green", "outer", 0.74, 80.1, 3.2, 2600, 0.058),
    ("Tarnish Row", "coastal", 0.70, 82.7, 1.6, 940, 0.055),
    ("Ember Vale", "coastal", 0.66, 79.9, 2.2, 640, 0.068),
    ("Quintrell", "core", 0.58, 83.4, 0.9, 1250, 0.047),
    ("Whitcombe", "inner", 0.52, 81.8, 0.8, 1050, 0.043),
    ("Larkhollow", "outer", 0.45, 78.8, 2.6, 1100, 0.076),
    ("Sedgeworth", "coastal", 0.38, 79.6, 1.7, 380, 0.079),
)

ASHGATE_SPEC = _spec(
    network="ashgate",
    first_day="2025-11-17",
    regions=ASHGATE_REGIONS,
    live_offsets=(18, 24, 32, 38, 48, 56, 70, 78),
    book_regions=(
        "Bellwether", "Netherfold", "Oxcombe", "Marlbrook", "Hallowfield",
        "Starling Green", "Quintrell", "Whitcombe", "Larkhollow",
    ),
    book_counted_on="2025-12-15",
    window_closes_on="2026-01-20",
    bookable_weeks=("2026-03-09", "2026-03-16", "2026-03-23"),
    days=112,
    clock_lift_points=3.9,
    migration_lead_days=(4, 3, 2, 5),
    rollback={"region": "Starling Green", "on_day": 63, "time": "07:15"},
    incidents=(
        ("Oxcombe", 29, "05:40", "paged", "depot scanner offline for the early wave"),
        ("Starling Green", 62, "21:30", "paged", "assignment workers timing out on the batch call"),
        ("Marlbrook", 84, "11:05", "reloaded", "routing table reload, planned"),
    ),
    region_weeks_granted=9,
    board_bar_points=1.2,
)

PELL_REGIONS = (
    ("Cawthorne", "core", 0.92, 86.0, 0.7, 1250, 0.041),
    ("Ashcott", "core", 0.88, 84.6, 1.5, 890, 0.050),
    ("Thelbury", "inner", 0.84, 84.2, 0.8, 1020, 0.057),
    ("Winterslow", "inner", 0.80, 82.9, 1.9, 1180, 0.062),
    ("Ravensmoor", "outer", 0.76, 80.4, 3.4, 2300, 0.036),
    ("Dunmere", "outer", 0.72, 79.7, 3.0, 760, 0.073),
    ("Farrowgate", "coastal", 0.68, 83.3, 0.9, 1330, 0.044),
    ("Nettlebed", "coastal", 0.64, 81.5, 1.7, 700, 0.066),
    ("Coldbrook", "ring", 0.58, 82.0, 1.1, 830, 0.053),
    ("Tarrow End", "ring", 0.54, 80.2, 2.0, 540, 0.070),
    ("Hesketh Lea", "core", 0.47, 80.9, 0.6, 1150, 0.081),
    ("Sparrowhill", "inner", 0.43, 78.9, 2.7, 1000, 0.078),
    ("Wexmoor", "outer", 0.39, 78.2, 3.2, 1200, 0.059),
    ("Marrowdale", "coastal", 0.34, 80.1, 1.4, 900, 0.051),
    ("Brinscombe", "ring", 0.30, 79.4, 1.0, 350, 0.067),
)

PELL_SPEC = _spec(
    network="pell",
    first_day="2026-02-02",
    regions=PELL_REGIONS,
    live_offsets=(22, 28, 36, 42, 52, 59, 70, 76, 92, 106),
    book_regions=(
        "Cawthorne", "Ashcott", "Thelbury", "Winterslow", "Ravensmoor", "Dunmere",
        "Farrowgate", "Nettlebed", "Hesketh Lea", "Sparrowhill", "Wexmoor", "Marrowdale",
    ),
    book_counted_on="2026-03-01",
    window_closes_on="2026-04-25",
    bookable_weeks=("2026-06-15", "2026-06-22", "2026-06-29"),
    days=133,
    clock_lift_points=3.6,
    migration_lead_days=(2, 5, 3, 4),
    january_wave={"Farrowgate": 4, "Nettlebed": 9, "Marrowdale": 14},
    rollback={"region": "Ravensmoor", "on_day": 59, "time": "08:05"},
    incidents=(
        ("Thelbury", 44, "16:50", "degraded", "van tracker feed stale for four hours"),
        ("Ravensmoor", 58, "22:40", "paged", "batch assignment queue backing up"),
        ("Winterslow", 95, "07:25", "restarted", "dispatch service restarted after a config push"),
    ),
    region_weeks_granted=10,
    holdback_share_band=(15, 35),
    board_bar_points=1.8,
)

WICKHAM_REGIONS = (
    ("Braemount", "core", 0.95, 86.8, 3.4, 4200, 0.122),
    ("Holmfirth", "core", 0.90, 85.3, 3.4, 3500, 0.110),
    ("Salterton", "inner", 0.86, 84.6, 3.4, 3800, 0.116),
    ("Verity Park", "inner", 0.81, 83.2, 3.4, 4100, 0.120),
    ("Kestrel Way", "outer", 0.76, 80.8, 3.4, 4600, 0.128),
    ("Lockridge", "outer", 0.71, 80.0, 3.4, 3900, 0.134),
    ("Ferrensby", "coastal", 0.66, 83.8, 3.4, 3300, 0.104),
    ("Marchbank", "coastal", 0.61, 82.4, 3.4, 4400, 0.126),
    ("Cortham", "core", 0.52, 82.6, 3.4, 3100, 0.114),
    ("Weyburn", "inner", 0.46, 81.1, 3.4, 2900, 0.132),
    ("Ainsdale", "outer", 0.40, 79.3, 3.4, 3600, 0.140),
    ("Nordhaven", "coastal", 0.34, 78.8, 3.4, 340, 0.146),
)

WICKHAM_SPEC = _spec(
    network="wickham",
    first_day="2025-10-06",
    regions=WICKHAM_REGIONS,
    live_offsets=(21, 27, 35, 41, 51, 59, 72, 80),
    book_regions=(
        "Braemount", "Holmfirth", "Salterton", "Verity Park", "Kestrel Way",
        "Lockridge", "Cortham", "Weyburn", "Ainsdale",
    ),
    book_counted_on="2025-11-03",
    window_closes_on="2025-12-10",
    bookable_weeks=("2026-02-02", "2026-02-09"),
    days=119,
    clock_lift_points=2.8,
    migration_lead_days=(5, 4, 3, 2),
    rollback={"region": "Lockridge", "on_day": 66, "time": "10:20"},
    incidents=(
        ("Braemount", 30, "13:15", "reloaded", "routing table reload after the depot split"),
        ("Lockridge", 65, "23:05", "paged", "assignment workers restarting on their own"),
        ("Salterton", 90, "09:00", "degraded", "handheld fleet update, slow scans all morning"),
    ),
    region_weeks_granted=6,
    board_bar_points=2.0,
)


MARCHANT_REGIONS = (
    ("Hobbsleigh", "core", 0.94, 79.4, 4.7, 1720, 0.058),
    ("Ilberry", "core", 0.90, 85.8, 2.2, 1600, 0.048),
    ("Petherwin", "inner", 0.86, 84.0, 3.0, 1250, 0.056),
    ("Golant", "inner", 0.81, 80.2, 4.2, 1850, 0.062),
    ("Marrowby", "outer", 0.76, 82.4, 2.5, 1400, 0.044),
    ("Ockley", "outer", 0.71, 78.9, 4.4, 1740, 0.066),
    ("Trewick", "coastal", 0.66, 84.2, 2.8, 1130, 0.051),
    ("Danesford", "coastal", 0.61, 83.1, 3.6, 1860, 0.074),
    ("Selkirk Row", "core", 0.52, 82.6, 2.8, 980, 0.069),
    ("Skelwith", "inner", 0.46, 81.3, 3.3, 1120, 0.077),
    ("Nantwood", "outer", 0.40, 79.8, 3.9, 1040, 0.071),
    ("Braithe", "coastal", 0.34, 82.7, 2.5, 1090, 0.059),
)

MARCHANT_SPEC = _spec(
    network="marchant",
    first_day="2026-01-12",
    regions=MARCHANT_REGIONS,
    live_offsets=(24, 30, 40, 46, 58, 64, 76, 84),
    book_regions=(
        "Hobbsleigh", "Ilberry", "Petherwin", "Golant", "Marrowby", "Ockley",
        "Trewick", "Danesford", "Selkirk Row", "Skelwith", "Nantwood", "Braithe",
    ),
    book_counted_on="2026-02-09",
    window_closes_on="2026-04-13",
    bookable_weeks=("2026-05-25", "2026-06-01"),
    days=126,
    january_wave={name: 2 for name, *_rest in MARCHANT_REGIONS},
    settle_penalty_points=2.5,
    incidents=(
        ("Golant", 51, "18:30", "paged", "depot wifi outage, handhelds offline for an hour"),
        ("Trewick", 88, "12:10", "reloaded", "routing table reload, planned"),
    ),
    region_weeks_granted=8,
)

def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


OFFSET_PARTNER_SPEC = _variant(
    CURRENT_SPEC,
    network="halcombe-offsets",
    migration_lead_days=(9, 12, 7, 11),
    january_wave={"Alder": 2, "Kingsmere": 14, "Vell": 6},
)

ROLLBACK_PARTNER_SPEC = _variant(
    CURRENT_SPEC,
    network="halcombe-rollback",
    rollback={"region": "Riverbend", "on_day": 79},
)

CURRENT = build(CURRENT_SPEC)
SIBLINGS = tuple(build(spec) for spec in (ASHGATE_SPEC, PELL_SPEC, WICKHAM_SPEC))
OUT_OF_REGIME = build(MARCHANT_SPEC)
PARTNERS = tuple(build(spec) for spec in (OFFSET_PARTNER_SPEC, ROLLBACK_PARTNER_SPEC))


OFFSET_PARTNER, ROLLBACK_PARTNER = PARTNERS


NAMING_ORDER = tuple(network.network for network in SIBLINGS)


STABILITY_PAIRS = (
    (CURRENT, OFFSET_PARTNER, "moves_with_migration_offset"),
    (CURRENT, ROLLBACK_PARTNER, "moves_with_rollback_week"),
)
