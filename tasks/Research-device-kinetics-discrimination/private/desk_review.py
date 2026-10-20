'The desk side of the review: what the notebook books next, and its accounting.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import chamber, oracle
from . import world as w
from .review import Review, _show, near, number


UNIT_SOURCES = w.UNIT_SOURCES


def check_standing_laws(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> None:
    'The laws the report leaves standing against the ones the rows leave.'

    read = oracle.reading_of(world, stream)
    standing = set(read["standing"])
    named = report.get("standing_laws")
    if not isinstance(named, list) or not named or any(
        item not in world.spec["catalogue"] for item in named
    ):
        review.add(
            "plan_failures",
            "block_names_a_law_the_rows_reject",
            campaign=world.campaign,
            named_law=_show(named),
            laws_named=len(named) if isinstance(named, list) else 0,
        )
        return
    rejected = [item for item in named if item not in standing]
    if rejected:
        review.add(
            "plan_failures",
            "block_names_a_law_the_rows_reject",
            campaign=world.campaign,
            named_law=str(sorted(rejected)[0]),
            laws_named=len(named),
        )
        return
    if len(set(named)) < len(standing):
        review.add(
            "plan_failures",
            "block_names_one_law",
            campaign=world.campaign,
            named_law=str(sorted(set(named))[0]),
            laws_named=len(set(named)),
        )


def check_plan(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    answer: Any,
) -> None:
    "One next-block answer, against the campaign and the desk's terms."

    read = oracle.reading_of(world, stream)
    days = world.days_left(stream)
    spares = world.spares_left(stream)
    shared = {
        "campaign": world.campaign,
        "days_left": days,
        "ports_per_block": int(world.spec["ports_cap"]),
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "block_is_not_a_block_or_a_stop", **shared,
                   reported=_show(answer))
        return


    nothing_left = oracle.nothing_left_to_book(world, stream)
    stop_only = oracle.stop_is_the_only_answer(world, stream, read)
    best = oracle.best_separation(world, stream, read)
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "block_is_not_a_block_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not stop_only:
                review.add("plan_failures", "stopped_with_days_left", **shared,
                           spares_left=sum(spares.values()))
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "block_is_not_a_block_or_a_stop", **shared,
                       reported=_show(choice))
            return
        drive = number(choice.get("drive_a"))
        temp = number(choice.get("case_temp_c"))
        ports = number(choice.get("ports"))
        chamber_days = number(choice.get("chamber_days"))
        lot = choice.get("lot")
        if (
            drive is None
            or temp is None
            or ports is None
            or chamber_days is None
            or not isinstance(lot, str)
            or ports != int(ports)
            or chamber_days != int(chamber_days)
            or ports < 1
        ):
            review.add("plan_failures", "block_is_not_a_block_or_a_stop", **shared,
                       reported=_show(
                           f"{_show(ports)} ports of {_show(lot)} at {_show(drive)} A and "
                           f"{_show(temp)} C for {_show(chamber_days)} days"
                       ))
            return
        ports, chamber_days = int(ports), int(chamber_days)
        booking = {
            "drive_a": drive,
            "case_temp_c": temp,
            "ports": ports,
            "chamber_days": chamber_days,
            "lot": lot,
        }
        named = {**shared, "drive_a": drive, "case_temp_c": temp, "ports": ports,
                 "chamber_days": chamber_days, "lot": lot}
        if nothing_left:
            window = list(world.spec["rig_out"])
            review.add("plan_failures", "block_booked_with_nothing_the_desk_will_take",
                       **named, served_on=str(world.served_on(stream)),
                       rig_out_of_service=(
                           f"{window[0]} to {window[1]}" if window else "no days at all"
                       ),
                       spares_left=sum(spares.values()))
            return
        if stop_only:
            review.add("plan_failures", "block_booked_with_the_range_closed", **named,
                       range_the_review_acts_on_h=float(world.spec["review_acts_within_h"]))
            return
        refusal = chamber.refusal_for(
            world, stream, charged=world.days_charged(chamber_days), **booking
        )
        if refusal:
            review.add("plan_failures", "block_infeasible", **named, refusal=refusal,
                       served_on=str(world.served_on(stream)))
            return


        room = min(int(world.spec["ports_cap"]), int(spares.get(lot, 0)))
        if ports != room:
            review.add("plan_failures", "block_leaves_the_ports_empty", **named,
                       ports_free=room)
            return
        separation = oracle.separation(world, stream, booking, read)
        if best > 0 and separation < oracle.PARTING_SHARE * best:
            if separation <= 1e-9:
                review.add(
                    "plan_failures",
                    "block_at_a_setting_that_parts_nothing",
                    **named,
                    separation_share="0%",
                )
            else:
                review.add(
                    "plan_failures",
                    "block_parts_too_little",
                    **named,
                    separation_share=format(100.0 * separation / best, ".0f") + "%",
                    required_share=format(100.0 * oracle.PARTING_SHARE, ".0f") + "%",
                )
            return


def counted_by_source(
    world: w.World, stream: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[int, int]]:
    'The rows behind the figure and the modules they came from, by source.'

    totals: dict[str, list[Any]] = {}
    for row in oracle.counted_rows(world, stream):
        entry = totals.setdefault(str(row["source"]), [0, set()])
        entry[0] += 1
        entry[1].add(str(row["module_id"]))
    return {source: (count, len(modules)) for source, (count, modules) in totals.items()}


def reference_rows(world: w.World) -> int:
    return sum(
        1 for row in world.trace_rows() if str(row["module_id"]) == w.REFERENCE_MODULE
    )


def check_ledger(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    error: str | None,
) -> None:
    if error:
        review.add("ledger_failures", "receipts_unreadable", campaign=world.campaign,
                   reason=str(error))
        return
    rows = report.get("blocks")
    if not isinstance(rows, list):
        review.add("ledger_failures", "blocks_are_not_a_ledger", campaign=world.campaign,
                   reported=_show(rows), charged=len(stream))
        return
    billed = {str(item["block_id"]): item for item in stream}
    seen: dict[str, int] = {}
    for row in rows:
        block_id = str(row.get("block_id"))
        seen[block_id] = seen.get(block_id, 0) + 1
        if seen[block_id] > 1:
            review.add("ledger_failures", "block_counted_twice", campaign=world.campaign,
                       block_id=block_id, times_reported=seen[block_id])
            return
        entry = billed.get(block_id)
        if entry is None or not all(
            near(row.get(field), float(entry[wanted]), 1e-9)
            for field, wanted in (
                ("drive_a", "drive_a"),
                ("case_temp_c", "case_temp_c"),
                ("ports", "ports_asked"),
                ("modules", "modules_returned"),
                ("rows", "rows_returned"),
                ("days_charged", "days_charged"),
            )
        ):
            review.add("ledger_failures", "block_not_on_the_receipts",
                       campaign=world.campaign, block_id=block_id, charged=len(stream))
            return
    for block_id, entry in billed.items():
        if block_id in seen:
            continue
        kind = (
            "handed_back_block_left_out"
            if str(entry.get("refusal") or "")
            else "charged_block_missing"
        )
        review.add("ledger_failures", kind, campaign=world.campaign, block_id=block_id,
                   days_charged=int(entry["days_charged"]),
                   served_on=str(entry["served_on"]), charged=len(stream))
        return
    counted = report.get("counted_rows")
    if not isinstance(counted, list) or not counted or any(
        not isinstance(item, dict)
        or item.get("source") not in UNIT_SOURCES
        or number(item.get("rows")) is None
        or number(item.get("modules")) is None
        for item in counted
    ):
        review.add("ledger_failures", "counted_rows_carry_no_source",
                   campaign=world.campaign, reported=_show(counted),
                   sources=", ".join(UNIT_SOURCES))
        return
    reported: dict[str, list[float]] = {}
    for item in counted:
        entry = reported.setdefault(str(item["source"]), [0.0, 0.0])
        entry[0] += float(item["rows"])
        entry[1] += float(item["modules"])
    wanted = counted_by_source(world, stream)
    export_rows = float(reported.get("trace_export", [0.0, 0.0])[0])
    counted_export = float(wanted.get("trace_export", (0, 0))[0])
    reference = reference_rows(world)
    if reference and abs(export_rows - (counted_export + reference)) < 1e-9:
        review.add("ledger_failures", "reference_reads_counted_as_modules",
                   campaign=world.campaign, reported_rows=int(export_rows),
                   counted_rows=int(counted_export), reference_rows=reference,
                   reference_module_id=w.REFERENCE_MODULE)
        return


    for source in UNIT_SOURCES:
        got = reported.get(source, [0.0, 0.0])
        want = wanted.get(source, (0, 0))
        if abs(got[0] - want[0]) > 1e-9 or abs(got[1] - want[1]) > 1e-9:
            review.add(
                "ledger_failures",
                "counted_rows_disagree",
                campaign=world.campaign,
                source=source,
                reported_rows=got[0],
                counted_rows=want[0],
                reported_modules=got[1],
                counted_modules=want[1],
            )
            return
