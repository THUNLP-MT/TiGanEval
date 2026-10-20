'The five checks the EM-9 review puts one delivered notebook through.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from tiganeval.taskkit import CANDIDATE_FAILURE

from . import chamber, oracle
from . import world as w


BUCKETS: Mapping[str, str] = {
    "hours_to_loss_within_tolerance": "hours_failures",
    "range_covers_and_spans_the_standing_laws": "range_failures",
    "hours_invariant_to_logger_cadence": "stability_failures",
    "next_block_parts_the_standing_laws": "plan_failures",
    "report_reconciles_receipts": "ledger_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "hours_to_loss_within_tolerance": (
        "hours_read_off_the_pinned_start",
        "hours_read_off_the_rows_on_the_sticker",
        "hours_read_off_the_elapsed_hours_column",
        "hours_absent",
        "hours_disagrees",
        "hours_wrong_on_another_campaign",
        "candidate_execution_failed",
    ),
    "range_covers_and_spans_the_standing_laws": (
        "range_is_not_a_pair",
        "range_does_not_hold_reported_hours",
        "range_narrower_than_the_laws_leave",
        "range_wider_than_the_laws_leave",
        "range_misses_the_hours",
        "range_wrong_on_another_campaign",
        "candidate_execution_failed",
    ),
    "hours_invariant_to_logger_cadence": (
        "hours_carried_over_from_this_campaign",
        "hours_track_the_elapsed_hours_column",
        "hours_track_which_rack_was_rebuilt",
        "candidate_execution_failed",
    ),
    "next_block_parts_the_standing_laws": (
        "block_is_not_a_block_or_a_stop",
        "block_names_one_law",
        "block_names_a_law_the_rows_reject",
        "block_infeasible",
        "block_leaves_the_ports_empty",
        "block_at_a_setting_that_parts_nothing",
        "block_parts_too_little",
        "stopped_with_days_left",
        "block_booked_with_nothing_the_desk_will_take",
        "block_booked_with_the_range_closed",
        "block_wrong_on_another_campaign",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "blocks_are_not_a_ledger",
        "block_counted_twice",
        "block_not_on_the_receipts",
        "handed_back_block_left_out",
        "charged_block_missing",
        "counted_rows_carry_no_source",
        "reference_reads_counted_as_modules",
        "counted_rows_disagree",
        "report_wrong_on_another_campaign",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "hours_failures": ("hours_wrong_on_another_campaign",),
    "range_failures": ("range_wrong_on_another_campaign",),
    "plan_failures": ("block_wrong_on_another_campaign",),
    "ledger_failures": ("report_wrong_on_another_campaign",),
}

def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _hours(value: Any) -> str:
    return format(float(value), ".0f")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_hours(value[0])} to {_hours(value[1])} hours"
    return _show(value)


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def near(value: Any, wanted: float, slack: float) -> bool:
    read = number(value)
    return read is not None and abs(read - wanted) <= slack


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(0, _fail(CANDIDATE_FAILURE, error=error))


_MISREADINGS = (
    ("hours_read_off_the_pinned_start", ("pinned_start", "both")),
    ("hours_read_off_the_elapsed_hours_column", ("elapsed_hours",)),
    ("hours_read_off_the_rows_on_the_sticker", ("sticker_rows_kept",)),
)


_STICKER_MODES = (
    "hours_read_off_the_pinned_start",
    "hours_read_off_the_rows_on_the_sticker",
)


def explanation(
    readings: Mapping[str, float],
    worlds: Mapping[str, w.World],
    streams: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str | None:
    'The one misreading that accounts for this delivery on most campaigns.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = 0
        for campaign, value in readings.items():
            if campaign not in worlds:
                continue
            misread = oracle.misreadings(worlds[campaign], streams.get(campaign, ()))
            if any(
                near(value, misread[family], oracle.CLASSIFY_SLACK)
                for family in families
                if family in misread
            ):
                hits += 1
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def sticker_rows(world: w.World) -> tuple[int, str, float]:
    "How many module rows sit on the meter's full scale, and one module there."

    span = world.full_scale_mw
    count = 0
    named = ""
    for row in world.trace_rows():
        if str(row["module_id"]) == w.REFERENCE_MODULE:
            continue
        if float(row["output_mw"]) >= span - 1e-9:
            count += 1
            named = named or str(row["module_id"])
    incoming = {
        str(item["module_id"]): float(item["incoming_mw"]) for item in world.spec["modules"]
    }
    return count, named, incoming.get(named, span)


def rebuilt_rack(world: w.World) -> tuple[str, str, float, float]:
    "The rack whose column runs off its own clock, and one module's two spans."

    hourly = 60
    racks = {name: int(value) for name, value in world.spec["racks"].items()}
    rack = min(racks, key=lambda name: (racks[name], name))
    if racks[rack] == hourly:
        return "", "", 0.0, 0.0
    module = ""
    column = stamps = 0.0
    for row in world.trace_rows():
        if str(row["rack"]) != rack or str(row["module_id"]) == w.REFERENCE_MODULE:
            continue
        if not module:
            module = str(row["module_id"])
        if str(row["module_id"]) == module:
            column = max(column, float(row["elapsed_h"]))
            stamps = max(stamps, float(row["elapsed_h"]) * racks[rack] / 60.0)
    return rack, module, column, stamps


def check_figure(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    mode: str | None,
) -> None:
    truth = oracle.truth(world)
    reported = report.get("hours_to_loss")
    if near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "campaign": world.campaign,
        "reported_hours": (
            _hours(reported) if number(reported) is not None else _show(reported)
        ),
    }
    if number(reported) is None:
        review.add(
            "hours_failures",
            "hours_absent",
            **shared,
            field_drive_a=world.field_drive_a,
            hold_temp_c=world.hold_temp_c,
        )
        return
    if mode is None:
        review.add(
            "hours_failures",
            "hours_disagrees",
            **shared,
            field_drive_a=world.field_drive_a,
            hold_temp_c=world.hold_temp_c,
            counted_rows=len(oracle.counted_rows(world, stream)),
        )
        return
    if mode in _STICKER_MODES:
        count, module, incoming = sticker_rows(world)
        review.add(
            "hours_failures",
            mode,
            **shared,
            sticker_rows=count,
            module_id=module,
            incoming_mw=format(incoming, ".1f"),
            full_scale_mw=format(world.full_scale_mw, ".1f"),
        )
        return
    rack, module, column, stamps = rebuilt_rack(world)
    review.add(
        "hours_failures",
        mode,
        **shared,
        rack=rack,
        module_id=module,
        column_hours=_hours(column),
        stamp_hours=_hours(stamps),
    )


def range_of(report: Mapping[str, Any]) -> tuple[float, float] | None:
    bounds = report.get("hours_range")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(number(item) is None for item in bounds)
        or float(bounds[0]) > float(bounds[1])
    ):
        return None
    return float(bounds[0]), float(bounds[1])


def rows_the_report_counted(
    world: w.World, stream: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> int:
    'How many rows the delivery says its figure was worked out of.'

    counted = report.get("counted_rows")
    if isinstance(counted, list) and counted:
        total = 0.0
        for item in counted:
            value = number(item.get("rows")) if isinstance(item, dict) else None
            if value is None:
                total = -1.0
                break
            total += value
        if total >= 0:
            return int(total)
    return len(oracle.counted_rows(world, stream))


def check_range(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> bool:
    'The width the standing laws and the counted rows leave. Returns coverage.'

    bounds = range_of(report)
    if bounds is None:
        review.add(
            "range_failures",
            "range_is_not_a_pair",
            campaign=world.campaign,
            reported=_pair(report.get("hours_range")),
        )
        return True
    reported = number(report.get("hours_to_loss"))
    if reported is None or not bounds[0] <= reported <= bounds[1]:
        review.add(
            "range_failures",
            "range_does_not_hold_reported_hours",
            campaign=world.campaign,
            reported_hours=(
                _hours(reported) if reported is not None else _show(report.get("hours_to_loss"))
            ),
            reported_range=_pair(list(bounds)),
        )
    floor = oracle.supported_half_width(world, stream)
    half = (bounds[1] - bounds[0]) / 2.0
    fields = {
        "campaign": world.campaign,
        "reported_range": _pair(list(bounds)),
        "reported_half_width": f"{_hours(half)} hours",
        "required_half_width": f"{_hours(floor)} hours",
        "counted_rows": rows_the_report_counted(world, stream, report),
    }
    if half < floor * oracle.NARROW_FACTOR:
        review.add("range_failures", "range_narrower_than_the_laws_leave", **fields)
    elif half > floor * oracle.WIDE_FACTOR:
        review.add("range_failures", "range_wider_than_the_laws_leave", **fields)
    truth = oracle.truth(world)
    return bounds[0] <= truth <= bounds[1]


def check_stability(review: Review, readings: Mapping[str, float], live: str) -> None:
    from . import workload

    here = readings.get(live)
    if here is None:
        return
    carried = workload.SIBLINGS[0].campaign
    other = readings.get(carried)
    if (
        other is not None
        and abs(here - other) < 1e-6
        and abs(oracle.truth(workload.CURRENT) - oracle.truth(workload.SIBLINGS[0]))
        > oracle.CARRIED_OVER_GAP
    ):
        review.add(
            "stability_failures",
            "hours_carried_over_from_this_campaign",
            campaign=live,
            other_campaign=carried,
            reported_hours=_hours(here),
        )
        return
    for mode, partner in (
        ("hours_track_the_elapsed_hours_column", workload.CADENCE_PARTNER),
        ("hours_track_which_rack_was_rebuilt", workload.REBUILD_PARTNER),
    ):
        value = readings.get(partner.campaign)
        if value is None:
            continue
        if abs(here - value) > oracle.INVARIANCE_SLACK:
            review.add(
                "stability_failures",
                mode,
                campaign=live,
                other_campaign=partner.campaign,
                reported_hours=_hours(here),
                other_hours=_hours(value),
                moved_by=_hours(abs(here - value)),
            )
            return
