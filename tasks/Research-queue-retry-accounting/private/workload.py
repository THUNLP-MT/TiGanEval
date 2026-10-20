'The review under way, and the reviews the same notebook has to serve next.'

from __future__ import annotations

from typing import Any, Mapping

from .world import build


POOL_NAMES = ("edge-ams", "edge-fra", "edge-lhr", "edge-dub")


def _pools(probes: int, thresholds: tuple[int, int, int, int],
           shares: tuple[str, str, str, str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "probes_per_minute": probes, "threshold": threshold,
         "traffic_share": share}
        for name, threshold, share in zip(POOL_NAMES, thresholds, shares)
    ]


def _spec(
    review: str,
    route: str,
    first_day: str,
    as_of: str,
    day_scale: list[str],
    peak_operations: int,
    fleets: list[Mapping[str, Any]],
    pools: list[Mapping[str, Any]],
    retry_cap: int,
    attempt_failure: tuple[str, str],
    final_share: tuple[str, str],
    probe_expiry: tuple[str, str],
    spill_fraction: tuple[str, str],
    units_granted: int,
    variation: str,
    releases: list[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "review": review,
        "route": route,
        "first_day": first_day,
        "as_of": as_of,
        "block_start": "18:00",
        "minutes_per_day": 180,
        "retention_hours": 72,
        "day_scale": list(day_scale),
        "peak_operations": int(peak_operations),
        "fleets": [dict(fleet) for fleet in fleets],
        "pools": [dict(pool) for pool in pools],
        "retry_cap": int(retry_cap),
        "attempt_failure": tuple(attempt_failure),
        "final_share": tuple(final_share),
        "probe_expiry": tuple(probe_expiry),
        "spill_fraction": tuple(spill_fraction),
        "unit_cost": 1,
        "units_granted": int(units_granted),
        "variation": variation,
        "releases": [dict(entry) for entry in releases],
    }


CURRENT_SPEC = _spec(
    review="quote-api-september",
    route="/v1/quote",
    first_day="2026-09-21",
    as_of="2026-09-27T10:00",
    day_scale=["1.26", "1.44", "1.38", "1.04", "1.01", "0.98"],
    peak_operations=900,
    fleets=[
        {"name": "checkout-web", "share": "3/10", "moved_on": "2026-09-22"},
        {"name": "checkout-app", "share": "1/4", "moved_on": "2026-09-22"},
        {"name": "partner-api", "share": "1/4", "moved_on": "2026-09-23"},
        {"name": "internal-tools", "share": "1/5", "moved_on": "2026-09-23"},
    ],
    pools=_pools(190, (453, 457, 446, 434), ("7/25", "27/100", "6/25", "21/100")),
    retry_cap=3,
    attempt_failure=("1/25", "7/50"),
    final_share=("1/5", "3/10"),
    probe_expiry=("7/25", "19/50"),
    spill_fraction=("2/5", "1/2"),
    units_granted=12,
    variation="current",
    releases=[
        {"day": "2026-09-22", "note": "checkout-web and checkout-app took 2.4.0 overnight."},
        {"day": "2026-09-23", "note": "partner-api and internal-tools took 2.4.0 overnight."},
    ],
)


SIBLING_SPECS = (
    _spec(
        review="quote-api-october",
        route="/v1/quote",
        first_day="2026-10-19",
        as_of="2026-10-25T10:00",
        day_scale=["1.30", "1.30", "1.24", "0.90", "0.86", "0.83"],
        peak_operations=980,
        fleets=[
            {"name": "checkout-web", "share": "3/10", "moved_on": "2026-10-20"},
            {"name": "checkout-app", "share": "1/4", "moved_on": "2026-10-20"},
            {"name": "partner-api", "share": "1/4", "moved_on": "2026-10-21"},
            {"name": "internal-tools", "share": "1/5", "moved_on": "2026-10-21"},
        ],
        pools=_pools(120, (392, 400, 388, 376), ("7/25", "27/100", "6/25", "21/100")),
        retry_cap=3,
        attempt_failure=("1/25", "3/20"),
        final_share=("1/5", "3/10"),
        probe_expiry=("1/5", "17/50"),
        spill_fraction=("3/5", "9/10"),
        units_granted=12,
        variation="spill",
        releases=[
            {"day": "2026-10-20", "note": "checkout-web and checkout-app took 2.4.0 overnight."},
            {"day": "2026-10-21", "note": "partner-api and internal-tools took 2.4.0 overnight."},
        ],
    ),
    _spec(
        review="quote-api-november",
        route="/v1/quote",
        first_day="2026-11-16",
        as_of="2026-11-22T10:00",
        day_scale=["1.34", "1.38", "1.32", "0.62", "0.59", "0.57"],
        peak_operations=860,
        fleets=[
            {"name": "checkout-web", "share": "3/10", "moved_on": "2026-11-17"},
            {"name": "checkout-app", "share": "1/4", "moved_on": "2026-11-17"},
            {"name": "partner-api", "share": "1/4", "moved_on": "2026-11-18"},
            {"name": "internal-tools", "share": "1/5", "moved_on": "2026-11-18"},
        ],
        pools=_pools(60, (250, 262, 275, 292), ("7/25", "27/100", "6/25", "21/100")),
        retry_cap=2,
        attempt_failure=("1/25", "1/5"),
        final_share=("1/10", "3/20"),
        probe_expiry=("6/25", "9/25"),
        spill_fraction=("2/5", "1/2"),
        units_granted=12,
        variation="cap",
        releases=[
            {"day": "2026-11-17", "note": "checkout-web and checkout-app took 2.4.0 overnight."},
            {"day": "2026-11-18", "note": "partner-api and internal-tools took 2.4.0 overnight."},
        ],
    ),
    _spec(
        review="quote-api-august",
        route="/v1/quote",
        first_day="2026-08-17",
        as_of="2026-08-23T10:00",
        day_scale=["1.22", "1.06", "1.34", "1.30", "0.88", "0.84"],
        peak_operations=940,
        fleets=[
            {"name": "partner-api", "share": "1/4", "moved_on": "2026-08-19"},
            {"name": "internal-tools", "share": "1/5", "moved_on": "2026-08-19"},
            {"name": "checkout-web", "share": "3/10", "moved_on": "2026-08-20"},
            {"name": "checkout-app", "share": "1/4", "moved_on": "2026-08-20"},
        ],
        pools=_pools(70, (270, 284, 298, 316), ("7/25", "27/100", "6/25", "21/100")),
        retry_cap=3,
        attempt_failure=("5/200", "1/10"),
        final_share=("9/50", "6/25"),
        probe_expiry=("11/50", "19/50"),
        spill_fraction=("2/5", "1/2"),
        units_granted=12,
        variation="rollout",
        releases=[
            {"day": "2026-08-19", "note": "partner-api and internal-tools took 2.4.0 overnight."},
            {"day": "2026-08-20", "note": "checkout-web and checkout-app took 2.4.0 overnight."},
        ],
    ),
)


STALLED_SPEC = _spec(
    review="quote-api-december",
    route="/v1/quote",
    first_day="2026-12-14",
    as_of="2026-12-20T10:00",
    day_scale=["1.28", "1.40", "1.34", "1.06", "1.03", "1.00"],
    peak_operations=920,
    fleets=[
        {"name": "checkout-web", "share": "3/10", "moved_on": "2026-12-15"},
        {"name": "checkout-app", "share": "1/4", "moved_on": "2026-12-16"},
        {"name": "partner-api", "share": "1/4", "moved_on": None},
        {"name": "internal-tools", "share": "1/5", "moved_on": None},
    ],
    pools=_pools(190, (453, 457, 446, 434), ("7/25", "27/100", "6/25", "21/100")),
    retry_cap=3,
    attempt_failure=("1/25", "7/50"),
    final_share=("1/5", "3/10"),
    probe_expiry=("7/25", "19/50"),
    spill_fraction=("2/5", "1/2"),
    units_granted=12,
    variation="stalled",
    releases=[
        {"day": "2026-12-15", "note": "checkout-web took 2.4.0 overnight."},
        {"day": "2026-12-16", "note": "checkout-app took 2.4.0 overnight."},
    ],
)


CURRENT = build(CURRENT_SPEC)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
STALLED = build(STALLED_SPEC)
LATER_REVIEWS = (*SIBLINGS, STALLED)


SPENT_TRACES = (
    ("2026-09-22T19:31", "edge-ams"),
    ("2026-09-22T19:34", "edge-fra"),
    ("2026-09-23T19:28", "edge-ams"),
    ("2026-09-25T18:14", "edge-lhr"),
    ("2026-09-24T19:26", "edge-ams"),
)
SPENT_IDS = ("mr-0922-a", "mr-0922-b", "mr-0923-a", "mr-0925-a", "mr-0924-a")
