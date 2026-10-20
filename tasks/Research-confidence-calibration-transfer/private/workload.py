'The queue under review, the queues the same notebook runs next, and the two re-presentations of this export the desk can reissue.'

from __future__ import annotations

from typing import Any, Mapping

from . import world


def _spec(
    queue: str,
    desk: str,
    listing_prefix: str,
    first_day: str,
    days: int,
    router_day: int,
    periods: tuple[str, ...],
    per_day_before: Mapping[str, int],
    per_day_after: Mapping[str, int],
    close_lag: Mapping[str, int],
    overstatement: Mapping[str, float],
    cut_in_force: float,
    bar_points: float,
    credits_granted: int,
    partner_channels: tuple[str, ...] = ("partner_feed", "reseller_import"),
) -> dict[str, Any]:
    return {
        "queue": queue,
        "desk": desk,
        "listing_prefix": listing_prefix,
        "first_day": first_day,
        "days": int(days),
        "router_day": int(router_day),
        "periods": tuple(periods),
        "per_day_before": dict(per_day_before),
        "per_day_after": dict(per_day_after),
        "close_lag": dict(close_lag),
        "partner_channels": tuple(partner_channels),
        "overstatement": dict(overstatement),
        "cut_in_force": float(cut_in_force),
        "bar_points": float(bar_points),
        "credits_granted": int(credits_granted),
        "max_listings_per_batch": 150,
        "credit_cost": {"web": 1, "mobile": 1, "partner_feed": 2, "reseller_import": 2},
        "empty_cell_charge": 20,
    }


CURRENT_SPEC = _spec(
    queue="marketplace-listings-q3",
    desk="marketplace listing review",
    listing_prefix="MK",
    first_day="2026-05-06",
    days=120,
    router_day=52,
    periods=("route-2025-11", "route-2026-04"),
    per_day_before={"web": 22, "mobile": 15, "partner_feed": 6, "reseller_import": 7},
    per_day_after={"web": 16, "mobile": 11, "partner_feed": 17, "reseller_import": 6},
    close_lag={"web": 2, "mobile": 3, "partner_feed": 42, "reseller_import": 30},
    overstatement={
        "web": 0.80,
        "mobile": 1.10,
        "partner_feed": 7.5,
        "reseller_import": 3.6,
    },
    cut_in_force=0.06,
    bar_points=3.0,
    credits_granted=1200,
)


FOLLOWING_SPECS = (
    _spec(
        queue="collectables-listings-q3",
        desk="collectables listing review",
        listing_prefix="CL",
        first_day="2026-05-25",
        days=104,
        router_day=40,
        periods=("route-2025-09", "route-2026-05"),
        per_day_before={"web": 24, "mobile": 14, "partner_feed": 5, "reseller_import": 7},
        per_day_after={"web": 15, "mobile": 10, "partner_feed": 19, "reseller_import": 6},
        close_lag={"web": 3, "mobile": 1, "partner_feed": 33, "reseller_import": 38},
        overstatement={
            "web": 0.85,
            "mobile": 1.15,
            "partner_feed": 6.4,
            "reseller_import": 3.2,
        },
        cut_in_force=0.04,
        bar_points=2.6,
        credits_granted=900,
    ),
    _spec(
        queue="homeware-listings-q3",
        desk="homeware listing review",
        listing_prefix="HW",
        first_day="2026-04-27",
        days=128,
        router_day=60,
        periods=("route-2025-12", "route-2026-03"),
        per_day_before={"web": 20, "mobile": 17, "partner_feed": 6, "reseller_import": 7},
        per_day_after={"web": 14, "mobile": 12, "partner_feed": 18, "reseller_import": 6},
        close_lag={"web": 2, "mobile": 2, "partner_feed": 38, "reseller_import": 27},
        overstatement={
            "web": 0.75,
            "mobile": 1.05,
            "partner_feed": 5.0,
            "reseller_import": 2.6,
        },
        cut_in_force=0.08,
        bar_points=4.0,
        credits_granted=1500,
    ),
    _spec(
        queue="ticketing-listings-q3",
        desk="ticketing listing review",
        listing_prefix="TK",
        first_day="2026-05-18",
        days=116,
        router_day=48,
        periods=("route-2025-10", "route-2026-06"),
        per_day_before={"web": 23, "mobile": 16, "partner_feed": 5, "reseller_import": 6},
        per_day_after={"web": 17, "mobile": 12, "partner_feed": 15, "reseller_import": 6},
        close_lag={"web": 1, "mobile": 3, "partner_feed": 44, "reseller_import": 34},
        overstatement={
            "web": 0.90,
            "mobile": 1.20,
            "partner_feed": 6.5,
            "reseller_import": 4.0,
        },
        cut_in_force=0.06,
        bar_points=2.5,
        credits_granted=800,
    ),
)


NIGHTLY_SPEC = _spec(
    queue="supplies-listings-q3",
    desk="supplies listing review",
    listing_prefix="SP",
    first_day="2026-06-01",
    days=96,
    router_day=96,
    periods=("route-2025-08", "route-2025-08"),
    per_day_before={"web": 20, "mobile": 15, "partner_feed": 9, "reseller_import": 6},
    per_day_after={"web": 20, "mobile": 15, "partner_feed": 9, "reseller_import": 6},
    close_lag={"web": 0, "mobile": 0, "partner_feed": 0, "reseller_import": 0},
    overstatement={
        "web": 0.80,
        "mobile": 1.10,
        "partner_feed": 2.25,
        "reseller_import": 1.3,
    },
    partner_channels=(),
    cut_in_force=0.06,
    bar_points=2.3,
    credits_granted=700,
)


def _reissue(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    return dict(spec, **changes)


LAG_REISSUE_SPEC = _reissue(
    CURRENT_SPEC,
    queue="marketplace-listings-q3-reissue-lag",
    close_lag={"web": 1, "mobile": 2, "partner_feed": 18, "reseller_import": 10},
)


ROUTER_REISSUE_SPEC = _reissue(
    CURRENT_SPEC,
    queue="marketplace-listings-q3-reissue-router",
    router_day=88,
)


_CACHE: dict[str, world.Queue] = {}


def queue(spec: Mapping[str, Any]) -> world.Queue:
    key = str(spec["queue"])
    if key not in _CACHE:
        _CACHE[key] = world.build(spec)
    return _CACHE[key]


def current() -> world.Queue:
    return queue(CURRENT_SPEC)


def following() -> tuple[world.Queue, ...]:
    return tuple(queue(spec) for spec in FOLLOWING_SPECS)


def nightly() -> world.Queue:
    return queue(NIGHTLY_SPEC)


def reissues() -> tuple[world.Queue, ...]:
    return (queue(LAG_REISSUE_SPEC), queue(ROUTER_REISSUE_SPEC))


SAMPLE_CUT_DAY = 62


def sample_rows() -> list[dict[str, Any]]:
    'The rows behind the chart, in the shape the file carries them.'

    stream = current()
    rows: list[dict[str, Any]] = []
    for index in range(stream.size()):
        if stream.day_of[index] >= int(CURRENT_SPEC["router_day"]):
            continue
        written = stream.closed_on[index] <= SAMPLE_CUT_DAY
        rows.append(
            {
                "listing_id": stream.listing_ids[index],
                "channel": stream.channel[index],
                "intake_date": stream.days[stream.day_of[index]],
                "intake_period": stream.period[index],
                "stated_confidence": stream.confidence[index],
                "auto_cleared": "yes" if stream.auto_cleared(index) else "no",
                "review_outcome": (
                    ("violating" if stream.violating[index] else "clean") if written else ""
                ),
            }
        )
    return rows
