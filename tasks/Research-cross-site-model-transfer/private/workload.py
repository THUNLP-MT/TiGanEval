'The deployment under review, the pool the pipeline was fitted on, and the centres the same notebook is run on next.'

from __future__ import annotations

from typing import Any, Mapping

from . import world


PORTAL = "portal"
MARKETPLACE = "marketplace"


_WEEK = [900, 880, 850, 830, 800, 700, 640]
BROOKFIELD_ARRIVALS = (_WEEK * 5)[:30]

_SMALL_WEEK = [520, 505, 495, 480, 460, 400, 370]
SMALL_ARRIVALS = (_SMALL_WEEK * 3)[:18]


def _spec(
    deployment: str,
    site: str,
    ticket_prefix: str,
    first_day: str,
    days: int,
    arrivals: list[int],
    seed: int,
    label_offset: float,
    marketplace_share: float,
    portal_contacts: float,
    marketplace_contacts: float,
    history_panel_from_contact: int,
    units_granted: int,
    model: str,
    snapshot_id: str,
    queue_name: str,
    export_name: str,
    as_of: str,
) -> dict[str, Any]:
    return {
        "deployment": deployment,
        "site": site,
        "ticket_prefix": ticket_prefix,
        "first_day": first_day,
        "days": int(days),
        "arrivals": list(arrivals),
        "seed": int(seed),
        "label_offset": float(label_offset),
        "marketplace_share": float(marketplace_share),
        "portal_contacts": float(portal_contacts),
        "marketplace_contacts": float(marketplace_contacts),
        "portal_base_contacts": 3,
        "marketplace_base_contacts": 0,
        "history_panel_from_contact": int(history_panel_from_contact),
        "units_granted": int(units_granted),
        "model": model,
        "snapshot_id": snapshot_id,
        "queue_name": queue_name,
        "export_name": export_name,
        "as_of": as_of,
        "surfaces": [PORTAL, MARKETPLACE],
        "marketplace_shift": {"account_age_months": -2.1, "product_breadth": -1.6},
    }


RIDGELINE_POOL_SPEC = _spec(
    deployment="ridgeline-pool-v3",
    site="ridgeline",
    ticket_prefix="RD",
    first_day="2026-01-05",
    days=10,
    arrivals=[700] * 10,
    seed=110_5001,
    label_offset=0.41,
    marketplace_share=0.05,
    portal_contacts=20.0,
    marketplace_contacts=2.5,
    history_panel_from_contact=4,
    units_granted=0,
    model="ridgeline-2026-03",
    snapshot_id="ridgeline_pool_v3",
    queue_name="ridgeline-review-queue",
    export_name="ridgeline-reconciliation",
    as_of="2026-03-11",
)


BROOKFIELD_SNAPSHOT_SPEC = _spec(
    deployment="brookfield-march",
    site="brookfield",
    ticket_prefix="BFM",
    first_day="2026-02-16",
    days=14,
    arrivals=SMALL_ARRIVALS,
    seed=220_7003,
    label_offset=0.28,
    marketplace_share=0.2213,
    portal_contacts=20.0,
    marketplace_contacts=2.5,
    history_panel_from_contact=4,
    units_granted=0,
    model="ridgeline-2026-03",
    snapshot_id="brookfield_queue_snapshot_v1",
    queue_name="brookfield-review-queue",
    export_name="brookfield-reconciliation",
    as_of="2026-03-11",
)


CURRENT_SPEC = _spec(
    deployment="brookfield-q3",
    site="brookfield",
    ticket_prefix="BF",
    first_day="2026-08-03",
    days=30,
    arrivals=BROOKFIELD_ARRIVALS,
    seed=330_9011,
    label_offset=0.53,
    marketplace_share=0.2213,
    portal_contacts=20.0,
    marketplace_contacts=2.5,
    history_panel_from_contact=4,
    units_granted=600,
    model="ridgeline-2026-03",
    snapshot_id="brookfield_export_2026w35",
    queue_name="brookfield-review-queue",
    export_name="brookfield-reconciliation",
    as_of="2026-09-02",
)


FOLLOWING_SPECS = (
    _spec(
        deployment="ashcombe-q3",
        site="ashcombe",
        ticket_prefix="AS",
        first_day="2026-08-10",
        days=18,
        arrivals=SMALL_ARRIVALS,
        seed=441_2017,
        label_offset=0.17,
        marketplace_share=0.34,
        portal_contacts=18.0,
        marketplace_contacts=2.2,
        history_panel_from_contact=4,
        units_granted=540,
        model="ridgeline-2026-03",
        snapshot_id="ashcombe_export_2026w34",
        queue_name="ashcombe-review-queue",
        export_name="ashcombe-reconciliation",
        as_of="2026-09-02",
    ),
    _spec(
        deployment="delford-q3",
        site="delford",
        ticket_prefix="DF",
        first_day="2026-08-17",
        days=18,
        arrivals=SMALL_ARRIVALS,
        seed=552_4021,
        label_offset=0.71,
        marketplace_share=0.11,
        portal_contacts=24.0,
        marketplace_contacts=2.8,
        history_panel_from_contact=4,
        units_granted=480,
        model="ridgeline-2026-03",
        snapshot_id="delford_export_2026w35",
        queue_name="delford-review-queue",
        export_name="delford-reconciliation",
        as_of="2026-09-02",
    ),
    _spec(
        deployment="marren-q3",
        site="marren",
        ticket_prefix="MR",
        first_day="2026-08-10",
        days=18,
        arrivals=SMALL_ARRIVALS,
        seed=663_6029,
        label_offset=0.09,
        marketplace_share=0.26,
        portal_contacts=16.0,
        marketplace_contacts=2.4,
        history_panel_from_contact=6,
        units_granted=600,
        model="ridgeline-2026-03",
        snapshot_id="marren_export_2026w34",
        queue_name="marren-review-queue",
        export_name="marren-reconciliation",
        as_of="2026-09-02",
    ),
    _spec(
        deployment="pellwood-q3",
        site="pellwood",
        ticket_prefix="PW",
        first_day="2026-08-17",
        days=18,
        arrivals=SMALL_ARRIVALS,
        seed=774_8033,
        label_offset=0.63,
        marketplace_share=0.29,
        portal_contacts=19.0,
        marketplace_contacts=2.6,
        history_panel_from_contact=3,
        units_granted=510,
        model="brookfield-2026-06",
        snapshot_id="pellwood_export_2026w35",
        queue_name="pellwood-review-queue",
        export_name="pellwood-reconciliation",
        as_of="2026-09-02",
    ),
)


LIFTED_SPEC = _spec(
    deployment="tarnbrook-q3",
    site="tarnbrook",
    ticket_prefix="TB",
    first_day="2026-08-24",
    days=18,
    arrivals=SMALL_ARRIVALS,
    seed=885_0037,
    label_offset=0.85,
    marketplace_share=0.24,
    portal_contacts=20.0,
    marketplace_contacts=2.5,
    history_panel_from_contact=0,
    units_granted=450,
    model="ridgeline-2026-03",
    snapshot_id="tarnbrook_export_2026w36",
    queue_name="tarnbrook-review-queue",
    export_name="tarnbrook-reconciliation",
    as_of="2026-09-02",
)


_CACHE: dict[str, world.Stream] = {}


def stream(spec: Mapping[str, Any]) -> world.Stream:
    key = str(spec["deployment"])
    if key not in _CACHE:
        _CACHE[key] = world.build(spec)
    return _CACHE[key]


def current() -> world.Stream:
    return stream(CURRENT_SPEC)


def following() -> tuple[world.Stream, ...]:
    return tuple(stream(spec) for spec in FOLLOWING_SPECS)


def lifted() -> world.Stream:
    return stream(LIFTED_SPEC)


def ridgeline_pool() -> world.Stream:
    return stream(RIDGELINE_POOL_SPEC)


def brookfield_snapshot() -> world.Stream:
    return stream(BROOKFIELD_SNAPSHOT_SPEC)


TRAIN_ROWS = 5600
RESERVED_ROWS = 1400


def reserved_rows() -> list[int]:
    'Indices of the Ridgeline rows the March fit did not train on.'

    pool = ridgeline_pool()
    return list(range(TRAIN_ROWS, TRAIN_ROWS + RESERVED_ROWS))


def training_rows() -> list[int]:
    return list(range(TRAIN_ROWS))


def snapshot_rows(mixed: bool = False) -> list[int]:
    "The 1,400 Brookfield rows that went into a fit's column statistics."

    snapshot = brookfield_snapshot()
    if mixed:
        frame = list(snapshot.order)
    else:
        frame = [index for index in snapshot.order if snapshot.in_queue(index)]
    return snapshot.systematic(frame, 1400)
