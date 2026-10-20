'The month under review, the months held back, and the office out of regime.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import world


ESTATES = (
    "arbourfield", "beckwith", "cairnlow", "dunmarsh", "eastrow", "fernhale",
    "gullen", "harrowgate", "inglemere", "kestrel", "lowfield", "marchbank",
    "netherby", "oakhurst",
)


ADDRESS_SIZES = (0.18, 0.22, 0.22, 0.18, 0.13, 0.07)


def spec(
    campaign: str,
    office: str,
    account_prefix: str,
    address_prefix: str,
    ticket_prefix: str,
    first_day: str,
    as_of: str,
    target_day: str,
    cut_off: str,
    seed: int,
    addresses: int,
    base_rate: float,
    ticket_lift: float,
    tag_lift: float,
    household_share: float,
    waitlist_names: int,
    prices: Mapping[str, int],
    estate_ticket_cap: int,
    credits_granted: int,
    credits_reserve: int,
    target_activations: int,
    counter_lag: int,
    late_share: float = 0.36,
    estates: Sequence[str] = ESTATES,
    counter_backfilled: bool = False,
    days: int = 30,
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "office": office,
        "account_prefix": account_prefix,
        "address_prefix": address_prefix,
        "ticket_prefix": ticket_prefix,
        "first_day": first_day,
        "days": int(days),
        "as_of": as_of,
        "target_day": target_day,
        "cut_off": cut_off,
        "seed": int(seed),
        "addresses": int(addresses),
        "address_size_weights": ADDRESS_SIZES,
        "estates": tuple(estates),
        "base_rate": float(base_rate),
        "ticket_lift": float(ticket_lift),
        "tag_lift": float(tag_lift),
        "household_share": float(household_share),
        "waitlist_names": int(waitlist_names),
        "prices_per_hundred": dict(prices),
        "estate_ticket_cap": int(estate_ticket_cap),
        "setup_charge": 40,
        "credits_granted": int(credits_granted),
        "credits_reserve": int(credits_reserve),
        "target_activations": int(target_activations),
        "baseline_days": 20,
        "counter_lag": int(counter_lag),
        "late_share": float(late_share),
        "counter_skips_weekend": True,
        "counter_backfilled": bool(counter_backfilled),
    }


PRICES = {"citywide": 55, "estate": 38, "waitlist": 24}


CURRENT_SPEC = spec(
    campaign="ashwell-september",
    office="Ashwell housing office",
    account_prefix="AC",
    address_prefix="AD",
    ticket_prefix="GP",
    first_day="2026-09-01",
    as_of="2026-09-21",
    target_day="2026-09-29",
    cut_off="2026-09-27",
    seed=910_2603,
    addresses=4_300,
    base_rate=0.031,
    ticket_lift=0.075,
    tag_lift=0.021,
    household_share=1.0,
    waitlist_names=900,
    prices=PRICES,
    estate_ticket_cap=1_200,
    credits_granted=5_913,
    credits_reserve=2_400,
    target_activations=1_000,
    counter_lag=2,
)


HISTORY_BOOKINGS: tuple[dict[str, Any], ...] = (
    {"receipt_id": "GP-0913-01", "drum": "citywide", "tickets": 1_500, "sent_on": "2026-09-04"},
    {"receipt_id": "GP-0913-02", "drum": "estate:beckwith", "tickets": 900, "sent_on": "2026-09-09"},
    {"receipt_id": "GP-0913-03", "drum": "waitlist", "tickets": 400, "sent_on": "2026-09-14"},
    {"receipt_id": "GP-0913-04", "drum": "citywide", "tickets": 2_600, "sent_on": "2026-09-18"},
    {"receipt_id": "GP-0913-05", "drum": "estate:beckwith", "tickets": 400, "sent_on": "2026-09-20"},
)


def history() -> list[dict[str, Any]]:
    'The five bookings with their charges, as the mail house billed them.'

    held: list[dict[str, Any]] = []
    for booking in HISTORY_BOOKINGS:
        campaign = world.build(CURRENT_SPEC, held)
        refused = world.refusal_for(
            campaign, booking["drum"], booking["tickets"], booking["sent_on"]
        )
        held.append(
            world.booking_record(
                campaign,
                str(booking["receipt_id"]),
                str(booking["drum"]),
                int(booking["tickets"]),
                str(booking["sent_on"]),
                refused,
            )
        )
    return held


def current() -> world.Campaign:
    return world.build(CURRENT_SPEC, history())


FOLLOWING_SPECS = (
    spec(
        campaign="ashwell-october",
        office="Ashwell housing office",
        account_prefix="AC",
        address_prefix="AD",
        ticket_prefix="GP",
        first_day="2026-10-01",
        as_of="2026-10-21",
        target_day="2026-10-29",
        cut_off="2026-10-27",
        seed=101_4409,
        addresses=4_600,
        base_rate=0.034,
        ticket_lift=0.082,
        tag_lift=0.026,
        household_share=1.0,
        waitlist_names=760,
        prices={"citywide": 52, "estate": 41, "waitlist": 27},
        estate_ticket_cap=1_000,
        credits_granted=6_400,
        credits_reserve=2_400,
        target_activations=1_050,
        counter_lag=1,
    ),
    spec(
        campaign="brightmoor-september",
        office="Brightmoor housing office",
        account_prefix="BC",
        address_prefix="BD",
        ticket_prefix="BP",
        first_day="2026-09-01",
        as_of="2026-09-21",
        target_day="2026-09-29",
        cut_off="2026-09-26",
        seed=220_7717,
        addresses=3_900,
        base_rate=0.030,
        ticket_lift=0.068,
        tag_lift=0.041,
        household_share=1.0,
        waitlist_names=1_050,
        prices={"citywide": 61, "estate": 35, "waitlist": 21},
        estate_ticket_cap=1_400,
        credits_granted=5_200,
        credits_reserve=2_200,
        target_activations=820,
        counter_lag=2,
    ),
    spec(
        campaign="calder-september",
        office="Calder housing office",
        account_prefix="CC",
        address_prefix="CD",
        ticket_prefix="CP",
        first_day="2026-09-01",
        as_of="2026-09-22",
        target_day="2026-09-29",
        cut_off="2026-09-27",
        seed=331_9021,
        addresses=4_800,
        base_rate=0.036,
        ticket_lift=0.090,
        tag_lift=0.024,
        household_share=0.92,
        waitlist_names=880,
        prices={"citywide": 58, "estate": 44, "waitlist": 30},
        estate_ticket_cap=900,
        credits_granted=6_900,
        credits_reserve=2_800,
        target_activations=1_100,
        counter_lag=1,
        counter_backfilled=True,
    ),
    spec(
        campaign="dunmoor-october",
        office="Dunmoor housing office",
        account_prefix="DC",
        address_prefix="DD",
        ticket_prefix="DP",
        first_day="2026-10-01",
        as_of="2026-10-20",
        target_day="2026-10-29",
        cut_off="2026-10-27",
        seed=442_1133,
        addresses=4_400,
        base_rate=0.032,
        ticket_lift=0.071,
        tag_lift=0.035,
        household_share=1.0,
        waitlist_names=940,
        prices={"citywide": 49, "estate": 39, "waitlist": 26},
        estate_ticket_cap=1_100,
        credits_granted=5_500,
        credits_reserve=2_300,
        target_activations=880,
        counter_lag=2,
    ),
    spec(
        campaign="everleigh-september",
        office="Everleigh housing office",
        account_prefix="EC",
        address_prefix="ED",
        ticket_prefix="EP",
        first_day="2026-09-01",
        as_of="2026-09-21",
        target_day="2026-09-29",
        cut_off="2026-09-27",
        seed=553_2247,
        addresses=4_150,
        base_rate=0.033,
        ticket_lift=0.077,
        tag_lift=0.032,
        household_share=1.0,
        waitlist_names=820,
        prices={"citywide": 57, "estate": 37, "waitlist": 23},
        estate_ticket_cap=1_250,
        credits_granted=5_900,
        credits_reserve=2_500,
        target_activations=950,
        counter_lag=1,
    ),
)


SINGLE_OCCUPANCY_SPEC = spec(
    campaign="fenwick-september",
    office="Fenwick housing office",
    account_prefix="FC",
    address_prefix="FD",
    ticket_prefix="FP",
    first_day="2026-09-01",
    as_of="2026-09-21",
    target_day="2026-09-29",
    cut_off="2026-09-27",
    seed=664_3351,
    addresses=9_800,
    base_rate=0.032,
    ticket_lift=0.079,
    tag_lift=0.030,
    household_share=1.0,
    waitlist_names=900,
    prices={"citywide": 54, "estate": 40, "waitlist": 25},
    estate_ticket_cap=1_200,
    credits_granted=5_600,
    credits_reserve=2_400,
    target_activations=780,
    counter_lag=2,
)
SINGLE_OCCUPANCY_SPEC["address_size_weights"] = (1.0,)


FRESH_ESTATE_SPEC = spec(
    campaign="garrowhill-october",
    office="Garrowhill housing office",
    account_prefix="HC",
    address_prefix="HD",
    ticket_prefix="HP",
    first_day="2026-10-01",
    as_of="2026-10-21",
    target_day="2026-10-29",
    cut_off="2026-10-27",
    seed=775_4463,
    addresses=4_400,
    base_rate=0.030,
    ticket_lift=0.074,
    tag_lift=0.033,
    household_share=1.0,
    waitlist_names=700,
    prices={"citywide": 56, "estate": 36, "waitlist": 25},
    estate_ticket_cap=1_200,
    credits_granted=5_800,
    credits_reserve=2_400,
    target_activations=770,
    counter_lag=2,
    estates=(
        "ravensmuir", "sallowfield", "tinnock", "underhill", "wharfside",
        "yarrowdean",
    ),
)


FOLLOWING_BOOKINGS: Mapping[str, tuple[dict[str, Any], ...]] = {
    "ashwell-october": (
        {"receipt_id": "GP-1013-01", "drum": "citywide", "tickets": 1_400, "sent_on": "2026-10-05"},
        {"receipt_id": "GP-1013-02", "drum": "waitlist", "tickets": 760, "sent_on": "2026-10-12"},
        {"receipt_id": "GP-1013-03", "drum": "estate:cairnlow", "tickets": 1_000, "sent_on": "2026-10-16"},
        {"receipt_id": "GP-1013-04", "drum": "citywide", "tickets": 1_800, "sent_on": "2026-10-19"},
        {"receipt_id": "GP-1013-05", "drum": "estate:cairnlow", "tickets": 400, "sent_on": "2026-10-20"},
    ),
    "brightmoor-september": (
        {"receipt_id": "BP-0913-01", "drum": "estate:dunmarsh", "tickets": 1_400, "sent_on": "2026-09-03"},
        {"receipt_id": "BP-0913-02", "drum": "citywide", "tickets": 2_100, "sent_on": "2026-09-10"},
        {"receipt_id": "BP-0913-03", "drum": "waitlist", "tickets": 1_050, "sent_on": "2026-09-17"},
        {"receipt_id": "BP-0913-04", "drum": "citywide", "tickets": 900, "sent_on": "2026-09-15"},
        {"receipt_id": "BP-0913-05", "drum": "citywide", "tickets": 900, "sent_on": "2026-09-28"},
    ),
    "calder-september": (
        {"receipt_id": "CP-0913-01", "drum": "citywide", "tickets": 2_600, "sent_on": "2026-09-06"},
        {"receipt_id": "CP-0913-02", "drum": "estate:eastrow", "tickets": 900, "sent_on": "2026-09-11"},
        {"receipt_id": "CP-0913-03", "drum": "waitlist", "tickets": 880, "sent_on": "2026-09-16"},
        {"receipt_id": "CP-0913-04", "drum": "citywide", "tickets": 1_500, "sent_on": "2026-09-20"},
        {"receipt_id": "CP-0913-05", "drum": "estate:eastrow", "tickets": 900, "sent_on": "2026-09-21"},
    ),
    "dunmoor-october": (
        {"receipt_id": "DP-1013-01", "drum": "citywide", "tickets": 1_200, "sent_on": "2026-10-04"},
        {"receipt_id": "DP-1013-02", "drum": "estate:fernhale", "tickets": 1_100, "sent_on": "2026-10-08"},
        {"receipt_id": "DP-1013-03", "drum": "citywide", "tickets": 2_000, "sent_on": "2026-10-15"},
        {"receipt_id": "DP-1013-04", "drum": "waitlist", "tickets": 940, "sent_on": "2026-10-13"},
        {"receipt_id": "DP-1013-05", "drum": "estate:fernhale", "tickets": 600, "sent_on": "2026-10-19"},
    ),
    "everleigh-september": (
        {"receipt_id": "EP-0913-01", "drum": "waitlist", "tickets": 820, "sent_on": "2026-09-05"},
        {"receipt_id": "EP-0913-02", "drum": "citywide", "tickets": 2_200, "sent_on": "2026-09-09"},
        {"receipt_id": "EP-0913-03", "drum": "estate:gullen", "tickets": 1_250, "sent_on": "2026-09-15"},
        {"receipt_id": "EP-0913-04", "drum": "citywide", "tickets": 1_600, "sent_on": "2026-09-13"},
        {"receipt_id": "EP-0913-05", "drum": "estate:gullen", "tickets": 500, "sent_on": "2026-09-20"},
    ),
    "fenwick-september": (
        {"receipt_id": "FP-0913-01", "drum": "citywide", "tickets": 1_600, "sent_on": "2026-09-05"},
        {"receipt_id": "FP-0913-02", "drum": "estate:harrowgate", "tickets": 1_200, "sent_on": "2026-09-10"},
        {"receipt_id": "FP-0913-03", "drum": "waitlist", "tickets": 900, "sent_on": "2026-09-15"},
        {"receipt_id": "FP-0913-04", "drum": "citywide", "tickets": 2_000, "sent_on": "2026-09-12"},
        {"receipt_id": "FP-0913-05", "drum": "estate:harrowgate", "tickets": 800, "sent_on": "2026-09-20"},
    ),
    "garrowhill-october": (
        {"receipt_id": "HP-1013-01", "drum": "citywide", "tickets": 700, "sent_on": "2026-10-03"},
        {"receipt_id": "HP-1013-02", "drum": "estate:ravensmuir", "tickets": 600, "sent_on": "2026-10-08"},
        {"receipt_id": "HP-1013-03", "drum": "waitlist", "tickets": 700, "sent_on": "2026-10-12"},
        {"receipt_id": "HP-1013-04", "drum": "estate:sallowfield", "tickets": 500, "sent_on": "2026-10-16"},
        {"receipt_id": "HP-1013-05", "drum": "estate:ravensmuir", "tickets": 700, "sent_on": "2026-10-19"},
    ),
}


def booked(campaign_spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    "One month's own bookings, charged or turned back as the desk found them."

    held: list[dict[str, Any]] = []
    for booking in FOLLOWING_BOOKINGS[str(campaign_spec["campaign"])]:
        campaign = world.build(campaign_spec, held)
        refused = world.refusal_for(
            campaign, booking["drum"], booking["tickets"], booking["sent_on"]
        )
        held.append(
            world.booking_record(
                campaign,
                str(booking["receipt_id"]),
                str(booking["drum"]),
                int(booking["tickets"]),
                str(booking["sent_on"]),
                refused,
            )
        )
    return held


def following() -> tuple[world.Campaign, ...]:
    return tuple(world.build(item, booked(item)) for item in FOLLOWING_SPECS)


def single_occupancy() -> world.Campaign:
    return world.build(SINGLE_OCCUPANCY_SPEC, booked(SINGLE_OCCUPANCY_SPEC))


def fresh_estate() -> world.Campaign:
    return world.build(FRESH_ESTATE_SPEC, booked(FRESH_ESTATE_SPEC))
