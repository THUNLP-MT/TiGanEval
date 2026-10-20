'The live readout, and the three others running on the same stack.'

from __future__ import annotations

from typing import Any, Mapping

from .world import build


def _spec(
    readout: str,
    first_day: str,
    as_of: str,
    retained_from: str,
    new_visits: list[int],
    return_visits: list[int],
    treated_share: list[str],
    visitors_before: int,
    first_conversion: str,
    return_conversion: str,
    effect: str,
    crawler_visits: Mapping[str, int],
    filter_live: Mapping[str, str | None],
    shed: Mapping[str, Mapping[str, int]],
    gate: str,
    units_granted: int,
    serving: Mapping[str, Mapping[str, str]],
    changes: list[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "readout": readout,
        "first_day": first_day,
        "as_of": as_of,
        "retained_from": retained_from,
        "new_visits": new_visits,
        "return_visits": return_visits,
        "treated_share": treated_share,
        "visitors_before": visitors_before,
        "first_conversion": first_conversion,
        "return_conversion": return_conversion,
        "effect": effect,
        "crawler_visits": dict(crawler_visits),
        "filter_live": dict(filter_live),
        "shed": {day: dict(value) for day, value in shed.items()},
        "gate": gate,
        "unit_cost": 1,
        "units_granted": units_granted,
        "serving": {arm: dict(value) for arm, value in serving.items()},
        "changes": [dict(entry) for entry in changes],
    }


CHECKOUT = {
    "control": {"service": "checkout-legacy", "topic": "checkout.v1"},
    "treatment": {"service": "checkout-v2", "topic": "checkout.v2"},
}
SEARCH = {
    "control": {"service": "search-legacy", "topic": "search.v1"},
    "treatment": {"service": "search-v2", "topic": "search.v2"},
}
BASKET = {
    "control": {"service": "basket-legacy", "topic": "basket.v1"},
    "treatment": {"service": "basket-v2", "topic": "basket.v2"},
}

CURRENT_SPEC = _spec(
    readout="checkout-hint-september",
    first_day="2026-08-19",
    as_of="2026-09-04",
    retained_from="2026-08-28",
    new_visits=[13200, 12800, 15600, 17400, 11900, 12600, 13400,
                13100, 12700, 16100, 18200, 12300, 12900, 13600],
    return_visits=[8600, 8900, 10200, 11100, 7800, 8100, 8700,
                   8800, 9000, 10500, 11600, 8200, 8500, 8900],
    treated_share=["1/5"] * 4 + ["1/2"] * 10,
    visitors_before=42000,
    first_conversion="3/50",
    return_conversion="17/100",
    effect="7/2000",
    crawler_visits={
        "2026-08-28": 2800,
        "2026-08-29": 3200,
        "2026-08-30": 3400,
        "2026-08-31": 3000,
        "2026-09-01": 3300,
    },
    filter_live={"control": "2026-08-29", "treatment": None},
    shed={
        "2026-08-25": {"treatment": 120},
        "2026-08-26": {"treatment": 110, "control": 40},
        "2026-08-27": {"treatment": 70},
    },
    gate="3/1000",
    units_granted=10,
    serving=CHECKOUT,
    changes=[
        {"day": "2026-08-19", "kind": "ramp", "note": "Hint variant opened at a fifth of new visitors on the v2 checkout path."},
        {"day": "2026-08-23", "kind": "ramp", "note": "Hint variant opened to half of new visitors; no other serving change."},
        {"day": "2026-08-25", "kind": "queue_quota", "note": "checkout.v2 crossed its queue quota during the evening push and stayed over it for three days."},
        {"day": "2026-08-28", "kind": "crawler_surge", "note": "Crawler surge on the sitemap paths from the early hours; support raised it at 21:40."},
        {"day": "2026-08-29", "kind": "rule_set", "note": "Crawler rule set 12 enabled on the legacy serving path. The v2 path is booked for 2026-09-05."},
        {"day": "2026-09-01", "kind": "window_close", "note": "Readout window closed."},
    ],
)


SIBLING_SPECS = (
    _spec(
        readout="search-ranking-august",
        first_day="2026-08-17",
        as_of="2026-09-04",
        retained_from="2026-08-28",
        new_visits=[9400, 9900, 11200, 12600, 8800, 9100, 9600,
                    9800, 10400, 12100, 13000, 9200, 9500, 9900],
        return_visits=[6200, 6400, 7100, 7600, 5800, 6000, 6300,
                       6500, 6700, 7400, 7900, 6100, 6300, 6600],
        treated_share=["1/4"] * 5 + ["3/5"] * 9,
        visitors_before=31000,
        first_conversion="9/200",
        return_conversion="3/20",
        effect="9/1000",
        crawler_visits={"2026-08-28": 2100, "2026-08-29": 2400, "2026-08-30": 2600},
        filter_live={"control": "2026-08-29", "treatment": None},
        shed={"2026-08-21": {"treatment": 60}, "2026-08-22": {"treatment": 45, "control": 30}},
        gate="1/500",
        units_granted=8,
        serving=SEARCH,
        changes=[
            {"day": "2026-08-17", "kind": "ramp", "note": "Re-ranker opened at a quarter of new visitors on the v2 search path."},
            {"day": "2026-08-21", "kind": "queue_quota", "note": "Re-ranker opened to three fifths of new visitors; search.v2 ran past its queue quota that evening and the next."},
            {"day": "2026-08-28", "kind": "crawler_surge", "note": "Crawler surge on the category paths from the early hours."},
            {"day": "2026-08-29", "kind": "rule_set", "note": "Crawler rule set 12 enabled on the legacy serving path only."},
            {"day": "2026-08-30", "kind": "window_close", "note": "Readout window closed."},
        ],
    ),
    _spec(
        readout="delivery-promise-august",
        first_day="2026-08-20",
        as_of="2026-09-04",
        retained_from="2026-08-28",
        new_visits=[16800, 17400, 19600, 21200, 15400, 15900, 16600,
                    16900, 17300, 20400, 22100, 15800, 16200, 17000],
        return_visits=[10800, 11200, 12600, 13400, 10100, 10400, 10900,
                       11000, 11300, 13100, 14200, 10400, 10700, 11100],
        treated_share=["3/10"] * 3 + ["1/2"] * 11,
        visitors_before=55000,
        first_conversion="7/100",
        return_conversion="19/100",
        effect="1/1000",
        crawler_visits={
            "2026-08-28": 3600, "2026-08-29": 3900, "2026-08-30": 4100,
            "2026-08-31": 3500, "2026-09-01": 3700, "2026-09-02": 3400,
        },
        filter_live={"control": "2026-08-29", "treatment": None},
        shed={"2026-08-24": {"treatment": 95}, "2026-08-25": {"treatment": 80, "control": 55}},
        gate="3/1000",
        units_granted=9,
        serving=BASKET,
        changes=[
            {"day": "2026-08-20", "kind": "ramp", "note": "Promise banner opened at three tenths of new visitors on the v2 basket path."},
            {"day": "2026-08-23", "kind": "ramp", "note": "Promise banner opened to half of new visitors."},
            {"day": "2026-08-24", "kind": "queue_quota", "note": "basket.v2 ran past its queue quota on two evenings."},
            {"day": "2026-08-28", "kind": "crawler_surge", "note": "Crawler surge on the sitemap paths from the early hours."},
            {"day": "2026-08-29", "kind": "rule_set", "note": "Crawler rule set 12 enabled on the legacy serving path only."},
            {"day": "2026-09-02", "kind": "window_close", "note": "Readout window closed."},
        ],
    ),
    _spec(
        readout="basket-nudge-august",
        first_day="2026-08-13",
        as_of="2026-09-04",
        retained_from="2026-08-28",
        new_visits=[11600, 12100, 13800, 15100, 10800, 11200, 11800,
                    12000, 12400, 14600, 15800, 11300, 11700, 12200],
        return_visits=[7400, 7700, 8600, 9200, 6900, 7100, 7500,
                       7600, 7800, 9000, 9700, 7100, 7300, 7600],
        treated_share=["1/5"] * 4 + ["1/2"] * 10,
        visitors_before=28000,
        first_conversion="1/20",
        return_conversion="4/25",
        effect="1/500",
        crawler_visits={},
        filter_live={"control": "2026-08-29", "treatment": None},
        shed={
            "2026-08-21": {"treatment": 300},
            "2026-08-22": {"treatment": 280, "control": 35},
            "2026-08-23": {"treatment": 250},
        },
        gate="1/1000",
        units_granted=6,
        serving=BASKET,
        changes=[
            {"day": "2026-08-13", "kind": "ramp", "note": "Nudge opened at a fifth of new visitors on the v2 basket path."},
            {"day": "2026-08-17", "kind": "ramp", "note": "Nudge opened to half of new visitors."},
            {"day": "2026-08-21", "kind": "queue_quota", "note": "basket.v2 ran past its queue quota for three evenings running."},
            {"day": "2026-08-26", "kind": "window_close", "note": "Readout window closed."},
        ],
    ),
)

CURRENT = build(CURRENT_SPEC)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)


SPENT_SLICES = (
    ("2026-08-29", "control"),
    ("2026-08-30", "control"),
    ("2026-08-28", "treatment"),
)
