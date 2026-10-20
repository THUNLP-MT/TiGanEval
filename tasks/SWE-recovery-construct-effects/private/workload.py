'Deterministic nights for the rating run: orders, vendor answers, halts.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


NO_RATE: Mapping[str, Any] = {"message": "the rating vendor answered 'unavailable'"}


def order(
    identifier: str,
    rule: str,
    *,
    lines: Sequence[float] = (),
    base: float = 40.0,
    fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {"id": identifier, "rule": rule, "lines": list(lines), "base": base,
            "fields": dict(fields or {})}


def _night(orders: Sequence[Mapping[str, Any]], vendor: Sequence[Any] = (),
           halt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    night: dict[str, Any] = {"orders": [dict(item) for item in orders],
                             "vendor": list(vendor)}
    if halt is not None:
        night["halt"] = dict(halt)
    return night


THREE = (12.0, 18.0, 24.0)
FOUR = (11.0, 15.0, 21.0, 26.0)
TWO = (14.0, 19.0)


def _invoices_night() -> dict[str, Any]:
    'The 14 July run: ordinary bundle pricing, two orders short a third line.'
    return _night([
        order("4903", "bundle_discount", lines=THREE, base=40.0),
        order("4907", "bundle_discount", lines=FOUR, base=52.0),
        order("4909", "bundle_discount", lines=THREE, base=36.0),
        order("4912", "bundle_discount", lines=TWO, base=44.0),
        order("4915", "bundle_discount", lines=THREE, base=48.0),
        order("4918", "bundle_discount", lines=TWO, base=30.0),
        order("4921", "bundle_discount", lines=THREE, base=41.0),
    ])


def _board_night() -> dict[str, Any]:
    "The 22 July run behind last month's triage board."
    return _night([
        order("5061", "pallet_rebate", lines=FOUR),
        order("5062", "pallet_rebate", lines=TWO),
        order("5068", "pallet_rebate", lines=THREE),
        order("5077", "pallet_rebate", lines=()),
        order("5081", "pallet_rebate", lines=THREE),
        order("5085", "dock_rebate", fields={"weight": "heavy"}),
        order("5089", "dock_rebate", fields={}),
        order("5093", "dock_rebate", fields={"weight": "31"}),
    ])


def _vendor_night() -> dict[str, Any]:
    'The 26 July run: the rating vendor half down, and three weighed orders.'
    return _night(
        [
            order("5311", "vendor_quote"),
            order("5314", "vendor_quote"),
            order("5317", "vendor_quote"),
            order("5320", "handling_fee", lines=THREE),
            order("5323", "handling_fee", lines=TWO),
            order("5326", "handling_fee", lines=FOUR),
        ],
        vendor=[NO_RATE, NO_RATE, NO_RATE, NO_RATE, 7.5],
    )


def _tier_night() -> dict[str, Any]:
    'The 3 August run: the runaway tier rule, and two closed-ledger orders.'
    return _night([
        order("5401", "bundle_discount", lines=THREE, base=39.0),
        order("5404", "tier_pricing", base=55.0),
        order("5407", "bundle_discount", lines=THREE, base=43.0),
        order("5410", "tier_pricing", base=61.0),
        order("5413", "settlement_close", base=47.0),
        order("5416", "settlement_close", base=52.0),
    ])


def _release_night() -> dict[str, Any]:
    'Orders no recorded night uses, over every rule in the rulebook.'
    orders = [
        order("6101", "bundle_discount", lines=THREE, base=45.0),
        order("6103", "bundle_discount", lines=FOUR, base=58.0),
        order("6105", "bundle_discount", lines=TWO, base=37.0),
        order("6107", "bundle_discount", lines=THREE, base=42.0),
        order("6109", "bundle_discount", lines=TWO, base=50.0),
        order("6201", "pallet_rebate", lines=FOUR),
        order("6203", "pallet_rebate", lines=TWO),
        order("6207", "pallet_rebate", lines=()),
        order("6211", "dock_rebate", fields={"weight": "heavy"}),
        order("6213", "dock_rebate", fields={}),
        order("6301", "vendor_quote"),
        order("6303", "vendor_quote"),
        order("6305", "nested_estimate"),
        order("6307", "depot_reweigh", lines=FOUR),
        order("6401", "handling_fee", lines=THREE),
        order("6403", "handling_fee", lines=FOUR),
        order("6405", "manual_reweigh", lines=THREE),
        order("6407", "manual_reweigh", lines=FOUR),
        order("6409", "manual_reweigh", lines=FOUR, base="n/a"),
        order("6501", "settlement_close", base=64.0),
        order("6601", "tier_pricing", base=57.0),
        order("6701", "lane_totals", lines=THREE, base=46.0),
        order("6703", "bundle_discount", lines=THREE, base=33.0),
        order("6705", "pallet_rebate", lines=THREE),
    ]


    return _night(orders,
                  vendor=[NO_RATE, NO_RATE, NO_RATE, 7.5, NO_RATE, NO_RATE, NO_RATE, 7.5],
                  halt={"order": "6701", "step": 20})


def _closing_halt_night() -> dict[str, Any]:
    'A closing rule halted after its body wrote, before the fourth line.'

    return _night(
        [order("6801", "manual_reweigh", lines=FOUR, base=46.0)],
        halt={"order": "6801", "step": 6},
    )


PAIRED_ORDERS = ("6203", "6207")
UNNAMED_LABEL_ORDER = "6213"
NESTED_ORDER = "6305"
CLEANUP_ORDER = "6501"
RUNAWAY_ORDER = "6601"
HALT_ORDER = "6701"
HALTED_CLOSING_ORDER = "6801"


FAULTED_LEASE_ORDER = "6401"
PRICED_LEASE_ORDER = "6403"


GUARDED_ORDERS = ("6203", "6207", "6211")


RETRY_FALLBACK_ORDER = "6301"


RETRY_PRICED_ORDERS = ("6303", "6307")


BRANCH_LEASE_ORDER = "6405"
CLOSING_LEASE_ORDER = "6407"


UNPRICED_CLOSING_ORDER = "6409"

CLOSING_ORDERS = ("6405", "6407", UNPRICED_CLOSING_ORDER)

PUBLIC_NIGHTS: Mapping[str, Any] = {
    "invoices": _invoices_night,
    "board": _board_night,
    "vendor": _vendor_night,
    "tier": _tier_night,
}


def build_night(profile: str) -> dict[str, Any]:
    'The orders, vendor answers and halt clause for one night.'
    if profile == "release":
        return _release_night()
    if profile == "closing-halt":
        return _closing_halt_night()
    builder = PUBLIC_NIGHTS.get(profile)
    if builder is None:
        raise ValueError(f"unknown rating night: {profile}")
    return builder()
