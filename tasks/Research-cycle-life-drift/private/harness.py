'Run the delivered notebook against the world and bucket what it got wrong.'

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import lab, oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-cycle-life-",
    timeout=40.0,
)

CAMPAIGN = workload.campaign_of(workload.CURRENT_LOT)

RUBRICS = (
    "session_retirement_cycles",
    "qualification_difference",
    "supported_effect_range",
    "collection_plan",
    "booking_decision",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "session_retirement_cycles": (
        "candidate_execution_failed",
        "sessions_do_not_match_the_receipts",
        "cells_do_not_match_the_receipts",
        "drift_left_in_the_readings",
        "retirement_cycles_disagree",
    ),
    "qualification_difference": (
        "candidate_execution_failed",
        "difference_claimed_without_a_stepped_run",
        "difference_claimed_without_a_standard_run",
        "cells_from_another_chamber_counted",
        "temperature_taken_from_the_chamber_trace",
        "scale_left_in_the_difference",
        "qualification_difference_disagrees",
    ),
    "supported_effect_range": (
        "candidate_execution_failed",
        "range_missing",
        "range_is_the_figure_repeated",
        "range_narrower_than_the_evidence",
        "range_wider_than_the_evidence",
    ),
    "collection_plan": (
        "candidate_execution_failed",
        "session_did_not_advance_the_open_question",
        "settling_session_took_more_channels_than_the_question_needed",
        "session_ran_after_the_question_was_closed",
        "plan_books_a_run_we_already_have",
        "plan_exceeds_the_booking",
        "plan_takes_more_channels_than_the_question_needs",
        "plan_stops_with_the_question_open",
        "collection_plan_disagrees",
    ),
    "booking_decision": (
        "candidate_execution_failed",
        "no_measurement_at_the_qualification_temperature",
        "decision_called_on_an_open_question",
        "booking_decision_disagrees",
    ),
}

_CACHE = AnalysisCache()


def _number(value: Any) -> Fraction | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
        return None
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def _close(value: Any, wanted: Fraction | int, tolerance: Fraction | int) -> bool:
    read = _number(value)
    return read is not None and abs(read - Fraction(wanted)) <= Fraction(tolerance)


def display(value: Any) -> str:
    read = _number(value)
    if read is None:
        return "nothing" if value is None else str(value)[:60]
    if read.denominator == 1:
        return str(read.numerator)
    return f"{float(read):.6g}"


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


HELD = "campaign"


def _where(state: Mapping[str, Any]) -> dict[str, str]:
    "The lot a failure happened on, in the lab lead's words and in the file's."

    lot_id = str(state["lot"])
    return {"campaign": str(state["context"]["campaign"]),
            "lot": str(world.LOTS[lot_id]["label"]),
            "state": str(state["label"])}


def _on_the_sheets_she_holds(record: Mapping[str, Any]) -> bool:
    'This incident happened on a session whose receipt is in the drawer.'

    return record.get("campaign") == CAMPAIGN and record.get("state", HELD) == HELD


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident the lab lead can open sheets for first.'

    return (0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
            0 if _on_the_sheets_she_holds(record) else 1)


def _written_off_the_sheets_she_holds(
        records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Which incidents can reach the report at all, before a mode is chosen.'

    visible = [record for record in records if _on_the_sheets_she_holds(record)]
    if not visible:
        return [dict(record) for record in records]
    kinds = {str(record.get("kind")) for record in visible} | {CANDIDATE_FAILURE}
    return [dict(record) for record in records if str(record.get("kind")) in kinds]


def _span(channels: Sequence[Any]) -> str:
    numbers = [int(channel) for channel in channels]
    if not numbers:
        return "none"
    if len(numbers) == 1:
        return str(numbers[0])
    return f"{min(numbers)} to {max(numbers)}"


def _channel_span(receipt: Mapping[str, Any]) -> str:
    return _span(receipt["channels"])


def _setpoint(lot: Mapping[str, Any], bay: str) -> Fraction:
    return Fraction(str(lot["rack"][bay]["setpoint_c"]))


def _sheet_the_rack_disagrees_with(lot_id: str,
                                   receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'The session whose temperature column and channel numbers do not agree.'

    lot = world.LOTS[lot_id]
    for receipt in receipts:
        bay = world.bay_of_channel(lot, int(receipt["channels"][0]))
        logged = _number(receipt["chamber_logged_c"])
        if bay is not None and logged is not None and logged != _setpoint(lot, bay):
            return {"session": str(receipt["session_id"]),
                    "channels": _channel_span(receipt),
                    "logged_c": display(logged),
                    "setpoint_c": display(_setpoint(lot, bay))}
    receipt = receipts[0]
    bay = world.bay_of_channel(lot, int(receipt["channels"][0]))
    return {"session": str(receipt["session_id"]),
            "channels": _channel_span(receipt),
            "logged_c": display(_number(receipt["chamber_logged_c"])),
            "setpoint_c": display(_setpoint(lot, str(bay))) if bay else "none"}


def _sheets_on_two_scales(lot_id: str, receipts: Sequence[Mapping[str, Any]],
                          context: Mapping[str, Any]) -> dict[str, Any]:
    'Two receipts whose sealed-cell readings at the top do not match.'

    lot = world.LOTS[lot_id]
    bay = oracle.qualification_bay(lot_id)
    inside = [receipt for receipt in receipts
              if world.bay_of_channel(lot, int(receipt["channels"][0])) == bay]
    pool = inside or list(receipts)

    def reading(receipt: Mapping[str, Any]) -> tuple[Fraction, str]:
        return (_number(receipt["reference_cell_ah"]) or Fraction(0),
                str(receipt["session_id"]))

    lowest, highest = min(pool, key=reading), max(pool, key=reading)
    return {"session": str(highest["session_id"]),
            "reference_cell_ah": display(_number(highest["reference_cell_ah"])),
            "other_session": str(lowest["session_id"]),
            "other_reference_cell_ah": display(_number(lowest["reference_cell_ah"])),
            "certified_ah": display(_number(context["reference_cell_ah"]))}


def _cells_by_bay(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    lot = world.LOTS[lot_id]
    counted: dict[str, int] = {bay: 0 for bay in lot["rack"]}
    for receipt in receipts:
        bay = world.bay_of_channel(lot, int(receipt["channels"][0]))
        if bay is not None:
            counted[bay] = counted[bay] + len(receipt["observed"]["cells"])
    return counted


def _the_two_bays(lot_id: str, receipts: Sequence[Mapping[str, Any]],
                  other: str | None = None) -> dict[str, Any]:
    "The build's own bay and the one the figure reached into, with cell counts."

    lot = world.LOTS[lot_id]
    bay = oracle.qualification_bay(lot_id)
    counted = _cells_by_bay(lot_id, receipts)
    if other is None:
        others = [name for name in lot["rack"] if name != bay]
        other = max(others, key=lambda name: counted.get(name, 0)) if others else bay
    return {"bay": bay,
            "setpoint_c": display(_setpoint(lot, bay)),
            "cells_in_the_bay": counted.get(bay, 0),
            "other_bay": other,
            "other_setpoint_c": display(_setpoint(lot, other)),
            "cells_outside_the_bay": counted.get(other, 0)}


def _bay_the_figure_came_from(lot_id: str, receipts: Sequence[Mapping[str, Any]],
                              reported: Any) -> str | None:
    'The chamber whose own difference is the figure that came back.'

    lot = world.LOTS[lot_id]
    bay = oracle.qualification_bay(lot_id)
    for other in lot["rack"]:
        if other == bay:
            continue
        stepped = oracle.arm_mean(lot_id, receipts, other, "stepped")
        standard = oracle.arm_mean(lot_id, receipts, other, "standard")
        if stepped is None or standard is None:
            continue
        if _close(reported, stepped - standard, oracle.MISREADING_TOLERANCE):
            return other
    return None


def _band(report: Mapping[str, Any]) -> str:
    'The band the notebook printed above its call, as she reads it.'

    value = report.get("difference_range")
    pair = [_number(item) for item in value] if isinstance(value, list) else []
    if len(pair) != 2 or pair[0] is None or pair[1] is None:
        return "nothing"
    return f"{display(pair[0])} to {display(pair[1])}"


def _certificate(state: Mapping[str, Any]) -> dict[str, Any]:
    low, high = state["context"]["lot_life_window_cycles"]
    return {"certificate_lower": int(low), "certificate_upper": int(high)}


def _state(label: str, lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    context = world.public_context(lot_id)


    context["channel_hours_remaining"] = oracle.hours_left(lot_id, receipts)
    return {
        "label": label,
        "lot": lot_id,
        "context": context,
        "receipts": [dict(receipt) for receipt in receipts],
        "records": {name: dict(record)
                    for name, record in workload.public_records(lot_id).items()},
    }


def _settled(lot_id: str, receipts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]] | None:
    'The same lot after the one booking that would close its question.'

    plans = oracle.allowed_plans(lot_id, receipts)
    if plans == ["stop"]:
        return None
    plan = plans[0]
    return lab.extend(lot_id, receipts, str(plan["bay"]), str(plan["protocol"]),
                      int(plan["cells"]), "settled-1")


def evidence_states(actual: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    archived = lab.archived_receipts(workload.CURRENT_LOT)
    same_as_archive = (
        [entry.get("seal") for entry in actual]
        == [entry.get("seal") for entry in archived]
    )
    states = []
    if not same_as_archive:


        states.append(_state("campaign-opening", workload.CURRENT_LOT, archived))
    states.append(_state("campaign", workload.CURRENT_LOT, actual))
    settled = _settled(workload.CURRENT_LOT, actual)
    if settled is not None:
        states.append(_state("campaign-settled", workload.CURRENT_LOT, settled))
    for lot_id in workload.FOLLOWING_LOTS:
        archived = lab.archived_receipts(lot_id)
        states.append(_state(lot_id, lot_id, archived))
        settled = _settled(lot_id, archived)
        if settled is not None:
            states.append(_state(f"{lot_id}-settled", lot_id, settled))
    return states


class Review:
    'Collects the failures of one delivery across every evidence state.'

    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {rubric: [] for rubric in RUBRICS}

    def add(self, rubric: str, kind: str, **fields: Any) -> None:
        self.failures[rubric].append(_fail(kind, **fields))

    def stopped(self, rubrics: Sequence[str], error: str) -> None:
        'An entry point that raised blocks the products that read it.'

        for rubric in rubrics:
            self.failures[rubric].insert(0, _fail(CANDIDATE_FAILURE, error=error))


def _check_sessions(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    lot_id, receipts = str(state["lot"]), state["receipts"]
    where = _where(state)
    want = oracle.endpoints(lot_id, receipts)
    raw = oracle.raw_endpoints(lot_id, receipts)
    hours = {str(receipt["session_id"]): int(receipt["channel_hours"]) for receipt in receipts}
    receipt_readings = {str(receipt["session_id"]): receipt["reference_cell_ah"]
                        for receipt in receipts}
    reported = report.get("sessions")
    listed = reported if isinstance(reported, dict) else {}
    if set(listed) != set(want):
        adrift = sorted(set(want) ^ set(listed))
        review.add("session_retirement_cycles", "sessions_do_not_match_the_receipts",
                   **where, session=adrift[0] if adrift else "none",
                   reported_sessions=len(listed), receipt_sessions=len(want))
        return
    for session_id in sorted(want):
        entry = listed[session_id]
        cycles = entry.get("retirement_cycles") if isinstance(entry, dict) else None
        counted = len(cycles) if isinstance(cycles, dict) else 0
        if (not isinstance(cycles, dict) or set(cycles) != set(want[session_id])
                or not _close(entry.get("cells"), len(want[session_id]), 0)
                or not _close(entry.get("channel_hours"), hours[session_id], 0)):
            review.add("session_retirement_cycles", "cells_do_not_match_the_receipts",
                       **where, session=session_id,
                       reported_cells=counted, receipt_cells=len(want[session_id]))
            continue
        for cell in sorted(want[session_id]):
            if _close(cycles[cell], want[session_id][cell], 0):
                continue
            left_in = (raw[session_id][cell] != want[session_id][cell]
                       and _close(cycles[cell], raw[session_id][cell], 1))
            review.add(
                "session_retirement_cycles",
                "drift_left_in_the_readings" if left_in else "retirement_cycles_disagree",
                **where, session=session_id, cell=cell,
                reported=display(cycles[cell]),
                reference_cell_ah=display(_number(receipt_readings[session_id])),
                certified_ah=display(_number(state["context"]["reference_cell_ah"])),
                retirement_line_ah=display(
                    Fraction(str(state["context"]["rated_capacity_ah"]))
                    * Fraction(str(state["context"]["retirement_fraction"]))),
                rated_capacity_ah=display(_number(state["context"]["rated_capacity_ah"])))
            break


_DIFFERENCE_MISREADINGS = (
    ("temperature_taken_from_the_chamber_trace", "chamber_trace_differences"),
    ("scale_left_in_the_difference", "uncorrected_differences"),
    ("cells_from_another_chamber_counted", "other_chamber_differences"),
)


def _difference_misreading(state: Mapping[str, Any],
                           reported: Any) -> tuple[str, dict[str, Any]]:
    'Which wrong grouping or wrong scale produces the figure that came back.'

    lot_id, receipts = str(state["lot"]), state["receipts"]
    for mode, family in _DIFFERENCE_MISREADINGS:
        values = getattr(oracle, family)(lot_id, receipts)
        if not any(_close(reported, value, oracle.MISREADING_TOLERANCE)
                   for value in values):
            continue
        if mode == "temperature_taken_from_the_chamber_trace":
            return mode, _sheet_the_rack_disagrees_with(lot_id, receipts)
        if mode == "scale_left_in_the_difference":
            return mode, _sheets_on_two_scales(lot_id, receipts, state["context"])
        return mode, _the_two_bays(lot_id, receipts,
                                   _bay_the_figure_came_from(lot_id, receipts, reported))
    return "qualification_difference_disagrees", _the_two_bays(lot_id, receipts)


def _check_difference(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    lot_id, receipts = str(state["lot"]), state["receipts"]
    where = _where(state)
    lot = world.LOTS[lot_id]
    reported = report.get("qualification_difference")
    if oracle.difference(lot_id, receipts) is None:
        if reported is not None:
            bay = oracle.qualification_bay(lot_id)
            missing = oracle.missing_arms(lot_id, receipts)[0]
            mode = f"difference_claimed_without_a_{missing}_run"
            review.add("qualification_difference", mode,
                       **where, reported=display(reported),
                       protocol=missing,
                       bay=bay,
                       bay_channels=_span(lot["rack"][bay]["channels"]),
                       setpoint_c=display(state["context"]["qualification_temperature_c"]))
        return
    wanted = oracle.truth(lot_id)
    if _close(reported, wanted, 0):
        return
    if _close(reported, wanted, oracle.DIFFERENCE_TOLERANCE):


        band = report.get("difference_range")
        pair = [_number(value) for value in band] if isinstance(band, list) else []
        if (len(pair) == 2 and pair[0] is not None and pair[1] is not None
                and pair[0] == pair[1] and _close(pair[0], reported, 0)):
            return
    mode, measured = _difference_misreading(state, reported)
    review.add("qualification_difference", mode, **where,
               reported=display(reported), **measured)


def _check_range(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    lot_id, receipts = str(state["lot"]), state["receipts"]
    where = _where(state)
    low, high = oracle.supported_range(lot_id, receipts)
    reported = report.get("difference_range")
    pair = [_number(value) for value in reported] if isinstance(reported, list) else [None, None]
    certificate = _certificate(state)
    if len(pair) != 2 or pair[0] is None or pair[1] is None or pair[0] > pair[1]:
        review.add("supported_effect_range", "range_missing", **where, **certificate)
        return
    fields = {**where, **certificate,
              "setpoint_c": display(state["context"]["qualification_temperature_c"]),
              "reported_lower": display(pair[0]), "reported_upper": display(pair[1])}
    if pair[0] > low or pair[1] < high:


        collapsed = (pair[0] == pair[1] and high > low)
        review.add("supported_effect_range",
                   "range_is_the_figure_repeated" if collapsed
                   else "range_narrower_than_the_evidence", **fields)
    elif pair[0] < low or pair[1] > high:
        review.add("supported_effect_range", "range_wider_than_the_evidence", **fields)


def _check_plan(review: Review, state: Mapping[str, Any], offered: Any) -> None:
    lot_id, receipts = str(state["lot"]), state["receipts"]
    lot = world.LOTS[lot_id]
    where = _where(state)
    allowed = oracle.allowed_plans(lot_id, receipts)
    left = oracle.hours_left(lot_id, receipts)
    entries = offered if isinstance(offered, list) else []
    if not entries:
        review.add("collection_plan", "collection_plan_disagrees",
                   **where, offered=display(str(offered)))
        return
    for entry in entries:
        if entry in allowed:
            continue
        if entry == "stop":
            wanted = next(plan for plan in allowed if isinstance(plan, dict))
            review.add("collection_plan", "plan_stops_with_the_question_open",
                       **where, channel_hours_left=left,
                       bay=str(wanted["bay"]), protocol=str(wanted["protocol"]),
                       cells=int(wanted["cells"]),
                       channel_hours_needed=(int(wanted["cells"])
                                             * int(lot["channel_hours_per_cell"])))
            return
        bay = entry.get("bay") if isinstance(entry, dict) else None
        protocol = entry.get("protocol") if isinstance(entry, dict) else None
        cells = _number(entry.get("cells")) if isinstance(entry, dict) else None
        if (not isinstance(bay, str) or bay not in lot["rack"]
                or protocol not in world.PROTOCOLS
                or cells is None or cells.denominator != 1 or cells <= 0):
            review.add("collection_plan", "collection_plan_disagrees",
                       **where, offered=display(str(entry))[:60])
            return
        count = int(cells)
        needed = count * int(lot["channel_hours_per_cell"])
        if count % world.FIXTURE or count > len(lot["rack"][bay]["channels"]) or needed > left:
            review.add("collection_plan", "plan_exceeds_the_booking", **where,
                       bay=bay, protocol=str(protocol),
                       cells=count, channel_hours_needed=needed, channel_hours_left=left)
            return
        if (bay, str(protocol)) in oracle.group_lives(lot_id, receipts):
            review.add("collection_plan", "plan_books_a_run_we_already_have", **where,
                       bay=bay, protocol=str(protocol), cells=count)
            return


        wanted = next((plan for plan in allowed
                       if isinstance(plan, dict) and plan["bay"] == bay
                       and plan["protocol"] == str(protocol)), None)
        if wanted is not None and count > int(wanted["cells"]):
            review.add("collection_plan", "plan_takes_more_channels_than_the_question_needs",
                       **where, bay=bay, protocol=str(protocol), cells=count,
                       cells_the_question_needs=int(wanted["cells"]),
                       channel_hours_needed=needed,
                       channel_hours_the_question_needs=(
                           int(wanted["cells"]) * int(lot["channel_hours_per_cell"])))
            return
        review.add("collection_plan", "collection_plan_disagrees", **where,
                   offered=display(f"{bay} {protocol} {count} cells"))
        return


def _check_decision(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    lot_id, receipts = str(state["lot"]), state["receipts"]
    where = _where(state)
    bar = int(state["context"]["switch_threshold_cycles"])
    allowed = oracle.allowed_decisions(lot_id, receipts)
    offered = [item for item in report.get("decision", ()) if item is not None]


    band = {"reported_range": _band(report), "switch_threshold_cycles": bar}
    if not allowed:
        if offered:
            review.add("booking_decision", "decision_called_on_an_open_question",
                       **where, reported=display(offered[0]), **band)
        return
    if not offered or any(item not in allowed for item in offered):
        review.add("booking_decision", "booking_decision_disagrees", **where,
                   reported=display(offered[0]) if offered else "nothing", **band)


def _receipt_booking(lot_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    'The booking the tester ledger says actually ran.'

    cells = len(receipt["observed"]["cells"])
    return {
        "bay": world.bay_of_channel(world.LOTS[lot_id], int(receipt["channels"][0])),
        "protocol": str(receipt["protocol"]),
        "cells": cells,
        "channel_hours": int(receipt["channel_hours"]),
    }


def _check_executed_collections(review: Review,
                                actual: Sequence[Mapping[str, Any]]) -> None:
    'Audit every newly paid session against the question as it then stood.'

    lot_id = workload.CURRENT_LOT
    archived = lab.archived_receipts(lot_id)
    if (len(actual) < len(archived)
            or [entry.get("seal") for entry in actual[:len(archived)]]
            != [entry.get("seal") for entry in archived]):


        return

    held: list[Mapping[str, Any]] = list(archived)
    closing_session: str | None = None
    for receipt in actual[len(archived):]:
        ran = _receipt_booking(lot_id, receipt)
        if oracle.allowed_decisions(lot_id, held):
            review.add(
                "collection_plan",
                "session_ran_after_the_question_was_closed",
                campaign=CAMPAIGN,
                lot=str(world.LOTS[lot_id]["label"]),
                state=HELD,
                session=str(receipt["session_id"]),
                closing_session=closing_session or "an earlier session",
                bay=str(ran["bay"]),
                protocol=str(ran["protocol"]),
                cells=int(ran["cells"]),
                channel_hours=int(ran["channel_hours"]),
            )
            held.append(receipt)
            continue

        before = list(held)
        plans = [plan for plan in oracle.allowed_plans(lot_id, before)
                 if isinstance(plan, dict)]
        exact = next((plan for plan in plans
                      if plan["bay"] == ran["bay"]
                      and plan["protocol"] == ran["protocol"]
                      and int(plan["cells"]) == int(ran["cells"])), None)
        wanted = next((plan for plan in plans
                       if plan["bay"] == ran["bay"]
                       and plan["protocol"] == ran["protocol"]), None)
        held.append(receipt)
        if exact is not None:
            if oracle.allowed_decisions(lot_id, held):
                closing_session = str(receipt["session_id"])
            continue

        if (wanted is None
                or int(ran["cells"]) <= int(wanted["cells"])
                or not oracle.allowed_decisions(lot_id, held)):
            review.add(
                "collection_plan",
                "session_did_not_advance_the_open_question",
                campaign=CAMPAIGN,
                lot=str(world.LOTS[lot_id]["label"]),
                state=HELD,
                session=str(receipt["session_id"]),
                bay=str(ran["bay"]),
                protocol=str(ran["protocol"]),
                cells=int(ran["cells"]),
                channel_hours=int(ran["channel_hours"]),
                channel_hours_left_after=int(receipt["channel_hours_remaining_after"]),
            )
            continue
        closing_session = str(receipt["session_id"])
        lot = world.LOTS[lot_id]
        review.add(
            "collection_plan",
            "settling_session_took_more_channels_than_the_question_needed",
            campaign=CAMPAIGN,
            lot=str(lot["label"]),
            state=HELD,
            session=closing_session,
            bay=str(ran["bay"]),
            protocol=str(ran["protocol"]),
            cells=int(ran["cells"]),
            channel_hours=int(ran["channel_hours"]),
            cells_the_question_needed=int(wanted["cells"]),
            channel_hours_the_question_needed=(
                int(wanted["cells"]) * int(lot["channel_hours_per_cell"])),
        )


def _check_evidence(review: Review, actual: Sequence[Mapping[str, Any]]) -> None:
    'The September call has to rest on cells that were actually put on the tester.'

    lot_id = workload.CURRENT_LOT
    if oracle.identified(lot_id, actual):
        return


    missing = oracle.missing_arms(lot_id, actual)
    review.add(
        "booking_decision",
        "no_measurement_at_the_qualification_temperature",
        campaign=CAMPAIGN,
        lot=str(world.LOTS[lot_id]["label"]),
        state=HELD,
        bay=oracle.qualification_bay(lot_id),
        protocol=missing[0] if missing else "",
        channel_hours_left=oracle.hours_left(lot_id, actual),
    )


_RUNNER_PHRASES = ("candidate process exited", "project rehearsal exceeded",
                   "candidate returned")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error", "")).strip()
    line = reported or "the notebook ended without saying why"
    if any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the study notebook stopped part way through the review: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    def compute() -> Mapping[str, Any]:
        try:
            actual = lab.read_receipts(artifact_dir, CAMPAIGN)
        except (OSError, ValueError, KeyError, TypeError):
            actual = []
        states = evidence_states(actual)
        run = PROJECT.invoke(Path(artifact_dir), {"states": states})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CAMPAIGN, "states": len(states)}
            return analysis
        answers = {str(entry.get("label")): entry for entry in run.get("states", ())}
        review = Review()
        for state in states:
            entry = answers.get(str(state["label"]), {})
            analysed = entry.get("analyze") or {}
            planned = entry.get("next") or {}
            if analysed.get("ok"):
                report = analysed.get("report") or {}
                _check_sessions(review, state, report)
                _check_difference(review, state, report)
                _check_range(review, state, report)
                _check_decision(review, state, report)
            else:
                review.stopped(
                    ("session_retirement_cycles", "qualification_difference",
                     "supported_effect_range", "booking_decision"),
                    str(analysed.get("error", "the notebook did not return a study")))
            if planned.get("ok"):
                _check_plan(review, state, planned.get("booking"))
            else:
                review.stopped(("collection_plan",),
                               str(planned.get("error", "the notebook did not return a booking")))
        _check_executed_collections(review, actual)
        _check_evidence(review, actual)
        analysis: dict[str, Any] = {
            rubric: _written_off_the_sheets_she_holds(sorted(records, key=_report_order))
            for rubric, records in review.failures.items()
        }
        analysis["case"] = {"campaign": CAMPAIGN, "states": len(states),
                            "sessions_paid_for": len(actual)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _receipt_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sequence": receipt["sequence"],
        "request_id": receipt["request_id"],
        "session_id": receipt["session_id"],
        "started": receipt["started"],
        "firmware": receipt["firmware"],
        "protocol": receipt["protocol"],
        "channels": list(receipt["channels"]),
        "chamber_logged_c": receipt["chamber_logged_c"],
        "reference_cell_ah": receipt["reference_cell_ah"],
        "cycles_run": receipt["cycles_run"],
        "cells": len(receipt["observed"]["cells"]),
        "channel_hours": receipt["channel_hours"],
        "channel_hours_remaining_after": receipt["channel_hours_remaining_after"],
    }


def _held(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return lab.read_receipts(artifact_dir, CAMPAIGN), None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], str(exc)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = world.public_context(workload.CURRENT_LOT)
    receipts, problem = _held(root)
    return {
        "summary": "The tester as it stands today and the sessions this campaign has paid for.",
        "measurements": {
            "campaign": context["campaign"],
            "current_firmware": context["current_firmware"],
            "rack": context["rack"],
            "qualification_temperature_c": context["qualification_temperature_c"],
            "switch_threshold_cycles": context["switch_threshold_cycles"],
            "lot_life_window_cycles": context["lot_life_window_cycles"],
            "rated_capacity_ah": context["rated_capacity_ah"],
            "retirement_fraction": context["retirement_fraction"],
            "checkpoint_every_cycles": context["checkpoint_every_cycles"],
            "reference_cell_ah": context["reference_cell_ah"],
            "cells_per_fixture": context["cells_per_fixture"],
            "channel_hours_per_cell": context["channel_hours_per_cell"],
            "channel_hours_remaining": lab.hours_remaining(workload.CURRENT_LOT, receipts),
            "editable_files": list(EDITABLE_FILES),
            "receipt_file": lab.RECEIPT_FILE,
            "receipt_problem": problem,
        },
        "records": [
            {"record": f"project_records/{name}.json", "record_id": record.get("record_id")}
            for name, record in sorted(workload.public_records(workload.CURRENT_LOT).items())
        ],
        "sessions_paid_for": [_receipt_summary(receipt) for receipt in receipts],
    }


def run_public_replay(artifact_dir: Path, record: Mapping[str, Any]) -> Mapping[str, Any]:
    "Open one record, print the tester's export behind it and run the notebook."

    root = Path(artifact_dir)
    record_id = str(record.get("record_id", ""))
    receipts, problem = _held(root)
    export = next(
        ({"session_id": receipt["session_id"], "firmware": receipt["firmware"],
          "reference_cell_ah": receipt["reference_cell_ah"],
          "chamber_logged_c": receipt["chamber_logged_c"],
          "cycles_run": receipt["cycles_run"], "channel_hours": receipt["channel_hours"],
          "cells": receipt["observed"]["cells"]}
         for receipt in receipts if str(receipt["session_id"]) == record_id),
        None,
    )


    archived = lab.archived_receipts(workload.CURRENT_LOT)
    states = [_state("as the records stand", workload.CURRENT_LOT, archived)]
    if [entry["seal"] for entry in receipts] != [entry["seal"] for entry in archived]:
        states.append(_state("as the tester stands", workload.CURRENT_LOT, receipts))
    run = PROJECT.invoke(root, {"states": states})
    if not run.get("ok"):
        notebook = {"stopped": run.get("error"), "console": run.get("diagnostic")}
    else:
        notebook = {
            str(entry.get("label")): {"analyze": entry.get("analyze"),
                                      "next_collection": entry.get("next")}
            for entry in run.get("states", ())
        }
        notebook["printed"] = run.get("stdout")
    return {
        "summary": f"Record {record_id} of the {CAMPAIGN} campaign, and the notebook on it.",
        "measurements": {
            "record_id": record_id,
            "campaign": CAMPAIGN,
            "channel_hours_remaining": lab.hours_remaining(workload.CURRENT_LOT, receipts),
            "receipt_problem": problem,
        },
        "public": {
            "record": dict(record),
            "instrument_export": export,
            "sessions_paid_for": [_receipt_summary(receipt) for receipt in receipts],
            "notebook": notebook,
        },
    }
