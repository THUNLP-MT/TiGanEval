'Read one delivered allocation note against the sweep it is a note about.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis/report.py", "analysis/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-curve-allocation-",


    timeout=240.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "funded_run_end_loss_within_tolerance",
    "range_covers_and_meets_floor",
    "choice_invariant_to_node_history",
    "next_booking_feasible_and_separating",
    "report_reconciles_stream",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "funded_run_end_loss_within_tolerance": (
        "report_names_no_run_on_the_board",
        "estimate_uses_last_logged_row",
        "estimate_reads_a_shorter_run",
        "funded_run_is_not_the_one_the_hours_buy",
        "end_loss_disagrees",
        "landing_wrong_on_a_later_window",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "range_excludes_reported_loss",
        "range_tighter_than_the_rows_carry",
        "range_wider_than_the_note_allows",
        "range_wider_than_the_rows_carry",
        "range_undercovers",
        "range_does_not_move_with_the_rows",
        "range_wrong_on_a_later_window",
        "candidate_execution_failed",
    ),
    "choice_invariant_to_node_history": (
        "choice_tracks_node_history",
        "choice_tracks_logging_interval",
        "choice_moves_on_a_later_window",
        "candidate_execution_failed",
    ),
    "next_booking_feasible_and_separating": (
        "executed_allocation_disagrees",
        "plan_is_not_a_booking_or_a_stop",
        "booking_names_a_run_the_window_does_not_carry",
        "booking_uses_unavailable_node",
        "booking_outside_job_window",
        "booking_over_the_hours_left",
        "booking_not_on_reckoning_node",
        "booking_not_separating",
        "booking_steps_not_matched",
        "stop_premature",
        "booking_wrong_on_a_later_window",
        "candidate_execution_failed",
    ),
    "report_reconciles_stream": (
        "receipt_stream_unreadable",
        "segments_are_not_a_list",
        "segment_not_on_ledger",
        "segment_missing",
        "segment_reported_twice",
        "line_disagrees_with_record",
        "segment_usage_disagrees",
        "collection_not_on_the_stream",
        "collection_reported_twice",
        "refusal_uncounted",
        "collection_missing_from_the_report",
        "hours_do_not_reconcile",
        "stream_wrong_on_a_later_window",
        "candidate_execution_failed",
    ),
}

CURRENT_CAMPAIGN = str(workload.CURRENT_SPEC["campaign"])
COARSE_LEADER_CAMPAIGN = str(workload.COARSE_LEADER_SPEC["campaign"])


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "funded_run_end_loss_within_tolerance": ("landing_wrong_on_a_later_window",),
    "range_covers_and_meets_floor": (
        "range_wrong_on_a_later_window",
        "range_does_not_move_with_the_rows",
    ),
    "choice_invariant_to_node_history": ("choice_moves_on_a_later_window",),
    "next_booking_feasible_and_separating": ("booking_wrong_on_a_later_window",),
    "report_reconciles_stream": ("stream_wrong_on_a_later_window",),
}


SPACING_KINDS: tuple[str, ...] = ("range_does_not_move_with_the_rows",)


_NAMING_ORDER: tuple[str, ...] = tuple(
    str(spec["campaign"])
    for spec in (*workload.FOLLOWING_SPECS, workload.LIFTED_SPEC)
)


def _naming_rank(campaign_id: str) -> int:
    return (
        _NAMING_ORDER.index(campaign_id)
        if campaign_id in _NAMING_ORDER
        else len(_NAMING_ORDER)
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float | None, slack: float) -> bool:
    read = _number(value)
    if read is None or wanted is None or wanted != wanted:
        return False
    return abs(read - float(wanted)) <= slack


def _loss(value: Any) -> str:
    read = _number(value)
    return _show(value) if read is None else format(read, ".3f")


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        _number(item) is not None for item in value
    ):
        return f"{_loss(value[0])} to {_loss(value[1])}"
    return _show(value)


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        if not value:
            return "no entries at all"
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _job_text(job: Any) -> str:
    if not isinstance(job, Mapping):
        return _show(job)
    return (
        f"{job.get('hours')} hours of {job.get('node_type')} on {job.get('config_id')}"
    )


def _plan_text(answer: Any) -> str:
    if isinstance(answer, list):
        return ", ".join(_job_text(job) for job in answer) or "no entries at all"
    return _show(answer)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(campaign: world.Campaign) -> dict[str, str]:
    return {"campaign": campaign.campaign_id, "window": campaign.campaign_id}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    "Put the incident she can open this window's own files for first."

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign") == CURRENT_CAMPAIGN else 1,
    )


def _carry_over_mode(modes: Sequence[str], kind: str) -> str:
    'Which carry-over incident a record of this kind belongs to.'

    if len(modes) == 1:
        return modes[0]
    return modes[1] if kind in SPACING_KINDS else modes[0]


def _written_off_the_live_window(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the window Nadia can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE
        or record.get("campaign") == CURRENT_CAMPAIGN
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    declared = FAILURE_MODES.get(bucket, ())

    def _declared_rank(record: Mapping[str, Any]) -> int:
        kind = str(record.get("kind"))
        return declared.index(kind) if kind in declared else len(declared)

    mode = _carry_over_mode(modes, str(min(rows, key=_declared_rank).get("kind")))
    same = [
        record
        for record in rows
        if _carry_over_mode(modes, str(record.get("kind"))) == mode
    ]
    named = min(
        (record for record in same if record.get("campaign")),
        key=lambda record: _naming_rank(str(record["campaign"])),
        default=same[0],
    )
    elsewhere = sorted({str(record["campaign"]) for record in same if record.get("campaign")})
    return [
        _fail(
            mode,
            campaign=CURRENT_CAMPAIGN,
            window=CURRENT_CAMPAIGN,
            other_window=str(named.get("campaign")),
            other_windows=len(elsewhere),
        )
    ]


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return world.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def board_leader(campaign: world.Campaign) -> str:
    'The run with the lowest row on the board.'

    return min(
        campaign.runs, key=lambda run: (oracle.last_row_reading(campaign, run), run.config_id)
    ).config_id


def plan_states(
    spec: Mapping[str, Any], live: Sequence[Mapping[str, Any]], shipped: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "Every state of one window's grant a next booking can be asked for in."

    base = workload.campaign(spec)
    states = [{"label": "now", "receipts": [dict(item) for item in live]}]
    held = [dict(item) for item in shipped]
    for step in range(6):
        campaign = world.build(spec, held)
        plan = oracle.one_allowed_plan(campaign)
        if plan == "stop":
            break
        for job in plan:
            held = world.review(
                base, held, job["config_id"], job["node_type"], job["hours"],
                f"walk-{step + 1}-{job['config_id']}", str(spec["as_of"]),
            )
        states.append(
            {"label": f"after {len(held)} bookings", "receipts": [dict(item) for item in held]}
        )
    leader = world.review(
        base, [dict(item) for item in shipped], board_leader(base), "n-b", 12,
        "board-leader", str(spec["as_of"]),
    )
    states.append({"label": "the grant went to the board leader", "receipts": leader})
    refused = world.review(
        base, [dict(item) for item in shipped], base.runs[0].config_id, "n-a", 8,
        "held-node", str(spec["as_of"]),
    )
    states.append({"label": "carrying a charged refusal", "receipts": refused})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The window on the board with the bookings it holds, then the ones after it.'

    rows = [
        {
            "spec": workload.CURRENT_SPEC,
            "campaign": workload.current(live),
            "receipts": [dict(item) for item in live],
            "shipped": workload.opening_receipts(),
            "presentations": world.PRESENTATIONS,
            "walk": True,
        }
    ]
    for spec in (*workload.FOLLOWING_SPECS, workload.LIFTED_SPEC):
        archived = workload.archived_receipts(spec)
        rows.append(
            {
                "spec": spec,
                "campaign": world.build(spec, archived),
                "receipts": archived,
                "shipped": archived,
                "presentations": (
                    world.PRESENTATIONS
                    if spec in (workload.LIFTED_SPEC, workload.COARSE_LEADER_SPEC)
                    else ("as recorded",)
                ),
                "walk": False,
            }
        )
    return rows


def _estimate_failures(
    campaign: world.Campaign, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    where = _where(campaign)
    wanted = oracle.funded(campaign)
    named = report.get("funded_run")
    run = campaign.run(str(named)) if isinstance(named, str) else None
    if run is None:
        return [
            _fail(
                "report_names_no_run_on_the_board", **where,
                reported_run=_show(named), runs_on_the_board=len(campaign.runs),
                hours_left=campaign.hours_left(),
            )
        ]
    reported = report.get("end_loss")
    truth = oracle.end_level(campaign, run)
    told = {
        **where,
        "reported_run": run.config_id,
        "reported": _loss(reported),
        "last_row": _loss(oracle.last_row_reading(campaign, run)),
        "steps_so_far": run.steps_so_far(),
        "last_segment_steps": int(run.segments[-1].last_step),
        "segments_behind_it": len(run.segments),
        "hours_left": campaign.hours_left(),
    }
    right_run = run.config_id == wanted.config_id
    right_number = _near(reported, truth, oracle.TOLERANCE)
    if right_run and right_number:
        return []
    if not right_number:
        if _near(reported, oracle.last_row_reading(campaign, run), oracle.DECOY_SLACK):
            return [_fail("estimate_uses_last_logged_row", **told)]
        if any(
            _near(reported, reading, oracle.DECOY_SLACK)
            for reading in oracle.shorter_run_readings(campaign, run)
        ):
            return [_fail("estimate_reads_a_shorter_run", **told)]
    if not right_run:
        return [_fail("funded_run_is_not_the_one_the_hours_buy", **told)]
    return [_fail("end_loss_disagrees", **told)]


def _range_shape(
    campaign: world.Campaign, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'Everything about a published range except whether it holds the level.'

    where = _where(campaign)
    published = report.get("end_loss_range")
    named = report.get("funded_run")
    run = campaign.run(str(named)) if isinstance(named, str) else oracle.funded(campaign)
    if run is None:
        run = oracle.funded(campaign)
    told = {
        **where,
        "reported_run": run.config_id,
        "reported_range": _pair(published),
        "rows_behind": len(oracle.steps_of(campaign, run)),
        "widest_allowed": format(oracle.RANGE_CEILING, ".2f"),
        "reported_loss": _loss(_number(report.get("end_loss"))),
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [_fail("range_is_not_an_interval", **told, reported=_show(published))]
    reported_loss = _number(report.get("end_loss"))
    if reported_loss is not None and not (
        float(published[0]) <= reported_loss <= float(published[1])
    ):
        return [_fail("range_excludes_reported_loss", **told)]
    width = float(published[1]) - float(published[0])
    supported = 2.0 * oracle.supported_half(campaign, run)
    told["published_width"] = format(width, ".3f")
    if width < supported * oracle.RANGE_FLOOR - 1e-12:
        return [_fail("range_tighter_than_the_rows_carry", **told)]
    if width > oracle.RANGE_CEILING + 1e-12:
        return [_fail("range_wider_than_the_note_allows", **told)]
    if width > supported * oracle.RANGE_SLACK + 1e-12:
        return [_fail("range_wider_than_the_rows_carry", **told)]
    return []


def _interval_width(published: Any) -> float | None:
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return None
    return float(published[1]) - float(published[0])


def _spacing_failures(
    campaign: world.Campaign,
    report: Mapping[str, Any],
    at_one_spacing: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'A band that does not move when the rows behind the curve do.'

    here = _interval_width(report.get("end_loss_range"))
    there = _interval_width(at_one_spacing.get("end_loss_range"))
    if here is None or there is None or here <= 0.0:
        return []
    if there <= here * oracle.RANGE_SPACING_RATIO + 1e-12:
        return []
    named = report.get("funded_run")
    run = campaign.run(str(named)) if isinstance(named, str) else None
    if run is None:
        run = oracle.funded(campaign)
    return [
        _fail(
            "range_does_not_move_with_the_rows",
            **_where(campaign),
            reported_run=run.config_id,
            reported_range=_pair(report.get("end_loss_range")),
            published_width=format(here, ".3f"),
            width_at_one_spacing=format(there, ".3f"),
            rows_behind=len(oracle.steps_of(campaign, run)),
        )
    ]


def _range_covers(campaign: world.Campaign, report: Mapping[str, Any]) -> bool:
    published = report.get("end_loss_range")
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
    ):
        return False
    named = report.get("funded_run")
    run = campaign.run(str(named)) if isinstance(named, str) else None
    if run is None:
        run = oracle.funded(campaign)
    truth = oracle.end_level(campaign, run)
    return float(published[0]) <= truth <= float(published[1])


def _move_failures(
    campaign: world.Campaign,
    base: Mapping[str, Any],
    others: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    where = _where(campaign)
    anchor = _number(base.get("end_loss"))
    named = base.get("funded_run")
    found: list[dict[str, Any]] = []
    for presentation, kind in (
        ("nodes", "choice_tracks_node_history"),
        ("logging", "choice_tracks_logging_interval"),
    ):
        if presentation not in others:
            continue
        other = others.get(presentation) or {}
        again = _number(other.get("end_loss"))
        again_named = other.get("funded_run")
        moved = (
            abs(again - anchor)
            if anchor is not None and again is not None
            else None
        )
        if again_named == named and (moved is not None and moved <= oracle.MOVE_TOLERANCE):
            continue
        found.append(
            _fail(
                kind,
                **where,
                reported_run=_show(named),
                reported_run_again=_show(again_named),
                reported=_loss(anchor),
                reported_again=_loss(again),
                moved=_loss(moved) if moved is not None else "empty",
                what_changed=world.presentation_note(presentation),
            )
        )
    return found


def _plan_failures(
    campaign: world.Campaign, state: Mapping[str, Any], answer: Any
) -> list[dict[str, Any]]:
    low, high = oracle.job_window(campaign)
    jobs = answer if isinstance(answer, list) else []
    asked = sum(int(job.get("hours") or 0) for job in jobs if isinstance(job, Mapping))
    first = next((job for job in jobs if isinstance(job, Mapping)), {})
    told = {
        **_where(campaign),
        "state": str(state["label"]),
        "hours_left": campaign.hours_left(),
        "hours_asked_for": asked,
        "job_min": low,
        "job_max": high,
        "node_asked": _show(first.get("node_type")),
        "run_asked": _show(first.get("config_id")),
        "reported": _plan_text(answer),
        "free_nodes": ", ".join(campaign.free_nodes()),
        "reckoning_node": oracle.reckoning_node(campaign),
    }
    problem = oracle.plan_is_allowed(campaign, answer)
    if problem is None:
        return []
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        if problem == "booking_uses_unavailable_node" and (
            str(job.get("node_type")) not in campaign.free_nodes()
        ):
            told["node_asked"] = _show(job.get("node_type"))
            break
        if problem == "booking_not_on_reckoning_node" and (
            str(job.get("node_type")) != oracle.reckoning_node(campaign)
        ):
            told["node_asked"] = _show(job.get("node_type"))
            break
        if problem == "booking_names_a_run_the_window_does_not_carry" and (
            campaign.run(str(job.get("config_id"))) is None
        ):
            told["run_asked"] = _show(job.get("config_id"))
            break
        hours = job.get("hours")
        if problem == "booking_outside_job_window" and (
            not isinstance(hours, int) or hours < low or hours > high
        ):
            told["hours_asked_for"] = _show(hours)
            break
    if problem == "booking_steps_not_matched":
        steps = oracle.booked_steps(campaign, jobs)
        told["steps_booked"] = ", ".join(
            f"{name}: {steps[name]}" for name in sorted(steps)
        )
    return [_fail(problem, **told)]


def _executed_allocation_failures(
    spec: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    shipped: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'Check successful console work added after the task was opened.'

    opening_ids = {str(item.get("receipt_id")) for item in shipped}
    added = [
        dict(item)
        for item in receipts
        if str(item.get("receipt_id")) not in opening_ids
    ]
    refused = [
        item
        for item in added
        if (_number(item.get("steps_returned")) or 0.0) <= 0.0
        and (_number(item.get("hours_charged")) or 0.0) > 0.0
    ]
    if len(refused) > 1:
        charged = sum(_number(item.get("hours_charged")) or 0.0 for item in refused)
        bookings = "; ".join(
            f"{item.get('receipt_id')}: {item.get('config_id')} on "
            f"{item.get('node_type')}, refused and charged "
            f"{_show(item.get('hours_charged'))} hours"
            for item in refused
        )
        return [
            _fail(
                "executed_allocation_disagrees",
                **_where(world.build(spec, receipts)),
                executed_bookings=bookings,
                executed_steps=(
                    f"no returned training; {len(refused)} refused requests charged "
                    f"{_show(charged)} hours"
                ),
            )
        ]
    executed = [
        item
        for item in added
        if (_number(item.get("steps_returned")) or 0.0) > 0.0
    ]
    if not executed:
        return []

    opening = world.build(spec, shipped)
    wanted = oracle.contender_ids(opening)
    reckoning_node = oracle.reckoning_node(opening)
    totals: dict[str, float] = {}
    for item in executed:
        config = str(item.get("config_id"))
        steps = _number(item.get("steps_returned")) or 0.0
        totals[config] = totals.get(config, 0.0) + steps

    matched = (
        set(totals) == wanted
        and all(total > 0.0 for total in totals.values())
        and len(set(totals.values())) == 1
        and all(str(item.get("node_type")) == reckoning_node for item in executed)
    )
    if matched:
        return []

    bookings = "; ".join(
        f"{item.get('receipt_id')}: {item.get('config_id')} on "
        f"{item.get('node_type')}, {_show(item.get('steps_returned'))} steps"
        for item in executed
    )
    steps = ", ".join(
        f"{config}: {_show(total)}" for config, total in sorted(totals.items())
    )
    return [
        _fail(
            "executed_allocation_disagrees",
            **_where(opening),
            executed_bookings=bookings,
            executed_steps=steps,
        )
    ]


def _stream_failures(
    campaign: world.Campaign,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    stream_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(campaign)
    if stream_error:
        return [_fail("receipt_stream_unreadable", **where, reason=str(stream_error))]
    ledger = campaign.ledger_rows()
    told = {
        **where,
        "segments_on_the_ledger": len(ledger),
        "bookings_on_the_stream": len(receipts),
    }
    lines = report.get("segments")
    if not isinstance(lines, list):
        return [_fail("segments_are_not_a_list", **told, reported=_show(lines))]
    wanted = {str(row["segment_id"]): row for row in ledger}
    seen: dict[str, int] = {}
    for line in lines:
        if not isinstance(line, Mapping):
            return [_fail("segments_are_not_a_list", **told, reported=_show(line))]
        key = str(line.get("segment_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [_fail("segment_reported_twice", **told, segment_id=key,
                          times_reported=seen[key])]
        if key not in wanted:
            return [_fail("segment_not_on_ledger", **told, segment_id=key,
                          run_of_the_segment=_show(line.get("config_id")))]
        expected_config = str(wanted[key]["config_id"])
        if line.get("config_id") != expected_config:
            return [_fail(
                "line_disagrees_with_record", **told, record_kind="segment",
                record_id=key, field="config_id",
                reported_value=_show(line.get("config_id")),
                recorded_value=expected_config,
            )]
        if line.get("used") is not True or line.get("set_aside_reason") is not None:
            return [_fail(
                "segment_usage_disagrees", **told, segment_id=key,
                run_of_the_segment=expected_config,
                reported_used=_show(line.get("used")),
                reported_reason=_show(line.get("set_aside_reason")),
            )]
    for key, row in wanted.items():
        if key not in seen:
            return [_fail("segment_missing", **told, segment_id=key,
                          run_of_the_segment=str(row["config_id"]))]

    rows = report.get("collections")
    if not isinstance(rows, list):
        return [_fail("segments_are_not_a_list", **told, reported=_show(rows))]
    billed = {str(entry["receipt_id"]): entry for entry in receipts}
    counted: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [_fail("segments_are_not_a_list", **told, reported=_show(row))]
        key = str(row.get("receipt_id"))
        counted[key] = counted.get(key, 0) + 1
        entry = billed.get(key)
        if entry is None:
            return [_fail("collection_not_on_the_stream", **told, receipt_id=key,
                          times_reported=counted[key])]
        if counted[key] > 1:
            return [_fail("collection_reported_twice", **told, receipt_id=key,
                          times_reported=counted[key])]
        charged = _number(row.get("hours_charged"))
        if charged is None or abs(charged - int(entry["hours_charged"])) > 0.0:
            if entry.get("refusal"):
                return [_fail(
                    "refusal_uncounted", **told, receipt_id=key,
                    reported_hours=_show(row.get("hours_charged")),
                    stream_hours=int(entry["hours_charged"]),
                )]
            return [_fail(
                "line_disagrees_with_record", **told, record_kind="booking",
                record_id=key, field="hours_charged",
                reported_value=_show(row.get("hours_charged")),
                recorded_value=_show(entry.get("hours_charged")),
            )]
        for field in ("config_id", "node_type", "steps_returned"):
            reported_value = row.get(field)
            recorded_value = entry.get(field)
            if field == "steps_returned":
                matches = _number(reported_value) == _number(recorded_value)
            else:
                matches = reported_value == recorded_value
            if not matches:
                return [_fail(
                    "line_disagrees_with_record", **told, record_kind="booking",
                    record_id=key, field=field,
                    reported_value=_show(reported_value),
                    recorded_value=_show(recorded_value),
                )]
    for key, entry in billed.items():
        if key in counted:
            continue
        kind = "refusal_uncounted" if entry.get("refusal") else "collection_missing_from_the_report"
        return [_fail(kind, **told, receipt_id=key,
                      reported_hours="nothing at all",
                      stream_hours=int(entry["hours_charged"]))]

    spent = campaign.hours_charged()
    granted = int(campaign.spec["grant_node_hours"])
    used = _number(report.get("hours_used"))
    left = _number(report.get("hours_left"))
    if used is None or abs(used - spent) > 0.0 or left is None or abs(
        left - (granted - spent)
    ) > 0.0:
        return [_fail("hours_do_not_reconcile", **told, reported_hours=_show(
            report.get("hours_used")), stream_hours=spent, granted=granted,
            reported_left=_show(report.get("hours_left")))]
    return []


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (
            "it was still running after "
            f"{reported[len(_TIMEOUT_PHRASE):].strip()} and the console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the allocation notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every window and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        receipts, stream_error = live_receipts(Path(artifact_dir))
        rows = cases(receipts)
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], dict[str, int]]] = []
        plans: list[tuple[world.Campaign, dict[str, Any], int]] = []
        for row in rows:
            spec, campaign = row["spec"], row["campaign"]
            index: dict[str, int] = {}
            for presentation in row["presentations"]:
                shown = world.build(
                    world.presented(spec, presentation), row["receipts"]
                )
                index[presentation] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": shown.context(),
                        "ledger": [dict(item) for item in row["receipts"]],
                    }
                )
            reports.append((row, index))
            states = (
                plan_states(spec, row["receipts"], row["shipped"])
                if row["walk"]
                else [{"label": "now", "receipts": [dict(i) for i in row["receipts"]]}]
            )
            for state in states:
                for presentation in row["presentations"]:
                    held = world.build(
                        world.presented(spec, presentation), state["receipts"]
                    )
                    shown_state = dict(state)
                    if presentation != "as recorded":
                        shown_state["label"] = (
                            f"{state['label']}, with "
                            f"{world.presentation_note(presentation)}"
                        )
                    plans.append((held, shown_state, len(requests)))
                    requests.append(
                        {
                            "kind": "plan",
                            "context": held.context(),
                            "ledger": [dict(item) for item in state["receipts"]],
                        }
                    )
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {
                "campaign": CURRENT_CAMPAIGN, "bookings_on_the_stream": len(receipts)
            }
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}
        current = rows[0]
        failures["next_booking_feasible_and_separating"].extend(
            _executed_allocation_failures(
                current["spec"], current["receipts"], current["shipped"]
            )
        )

        def answer(position: int) -> tuple[Any, str | None]:
            if position >= len(results):
                return None, "the notebook returned no answer for one of the windows"
            item = dict(results[position])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        uncovered: list[dict[str, Any]] = []
        for row, index in reports:
            campaign = row["campaign"]
            value, error = answer(index["as recorded"])
            if error is not None:
                stopped = True
                for bucket in (
                    "funded_run_end_loss_within_tolerance",
                    "range_covers_and_meets_floor",
                    "choice_invariant_to_node_history",
                    "report_reconciles_stream",
                ):
                    failures[bucket].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            failures["funded_run_end_loss_within_tolerance"].extend(
                _estimate_failures(campaign, report)
            )
            shape = _range_shape(campaign, report)
            failures["range_covers_and_meets_floor"].extend(shape)
            if not shape and not _range_covers(campaign, report):
                uncovered.append(
                    _fail(
                        "range_undercovers",
                        **_where(campaign),
                        reported_run=_show(report.get("funded_run")),
                        reported_range=_pair(report.get("end_loss_range")),
                        rows_behind=len(
                            oracle.steps_of(
                                campaign,
                                campaign.run(str(report.get("funded_run")))
                                or oracle.funded(campaign),
                            )
                        ),
                        widest_allowed=format(oracle.RANGE_CEILING, ".2f"),
                    )
                )
            failures["report_reconciles_stream"].extend(
                _stream_failures(
                    campaign, row["receipts"], report,
                    stream_error if campaign.campaign_id == CURRENT_CAMPAIGN else None,
                )
            )
            others: dict[str, Mapping[str, Any]] = {}
            for presentation in row["presentations"]:
                if presentation == "as recorded":
                    continue
                shown, shown_error = answer(index[presentation])
                if shown_error is not None:
                    stopped = True
                    failures["choice_invariant_to_node_history"].append(
                        _fail(CANDIDATE_FAILURE, error=shown_error)
                    )
                else:
                    others[presentation] = dict(shown or {})
            if others:
                failures["choice_invariant_to_node_history"].extend(
                    _move_failures(campaign, report, others)
                )
            if campaign.campaign_id == COARSE_LEADER_CAMPAIGN and "logging" in others:
                failures["range_covers_and_meets_floor"].extend(
                    _spacing_failures(campaign, report, others["logging"])
                )


        if uncovered:
            failures["range_covers_and_meets_floor"].extend(uncovered)

        for campaign, state, position in plans:
            value, error = answer(position)
            if error is not None:
                stopped = True
                failures["next_booking_feasible_and_separating"].append(
                    _fail(CANDIDATE_FAILURE, error=error)
                )
                continue
            failures["next_booking_feasible_and_separating"].extend(
                _plan_failures(campaign, state, value)
            )

        analysis: dict[str, Any] = {
            rubric: _written_off_the_live_window(
                rubric, sorted(records, key=_report_order)
            )
            for rubric, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT_CAMPAIGN,
            "bookings_on_the_stream": len(receipts),
            "windows_read": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "receipt_id", "day", "config_id", "node_type", "hours_requested",
            "steps_returned", "schedule_restarted", "hours_charged", "hours_remaining",
            "refusal",
        )
    }


def board(campaign: world.Campaign) -> list[dict[str, Any]]:
    'The last-loss column the sweep board prints, in the order it prints it.'

    rows = []
    for run in campaign.runs:
        last = campaign.last_row(run)
        rows.append(
            {
                "config_id": run.config_id,
                "segments": len(run.segments),
                "last_step": int(last["step"]) if last else 0,
                "last_loss": float(last["loss"]) if last else None,
            }
        )
    rows.sort(key=lambda row: (row["last_loss"] is None, row["last_loss"]))
    return rows


def snapshot(campaign: world.Campaign, record: Mapping[str, Any]) -> dict[str, Any]:
    'The evidence as it stood at the end of one past working session.'

    through = str(record["through_day"])
    context = campaign.context()
    context["as_of"] = str(record["date"])
    kept = {
        str(row["segment_id"])
        for row in context["ledger"]
        if str(row["started_on"]) <= through
    }
    context["ledger"] = [row for row in context["ledger"] if row["segment_id"] in kept]
    context["curves"] = {
        config_id: [row for row in rows if str(row["segment_id"]) in kept]
        for config_id, rows in context["curves"].items()
    }
    context["curves"] = {
        config_id: rows for config_id, rows in context["curves"].items() if rows
    }
    return context


def _record_receipts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = workload.opening_receipts()
    keep = {str(item) for item in record.get("receipts", ())}
    return [dict(entry) for entry in held if str(entry["receipt_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    receipts, error = live_receipts(root)
    campaign = workload.current(receipts)
    context = campaign.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_day")},
            }
        )
    return {
        "summary": (
            f"The {context['campaign']} window, the cluster terms and the working "
            "records on file."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "as_of": context["as_of"],
            "cluster": context["cluster"],
            "budget": context["budget"],
            "runs_on_the_board": board(campaign),
            "segments_on_the_ledger": len(context["ledger"]),
            "bookings_on_the_stream": [_receipt_summary(entry) for entry in receipts],
            "receipt_stream": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    base = workload.current()
    context = snapshot(base, record)
    receipts = _record_receipts(record)
    context["budget"] = {
        "grant_node_hours": int(workload.CURRENT_SPEC["grant_node_hours"]),
        "hours_charged": sum(int(entry["hours_charged"]) for entry in receipts),
        "hours_left": int(workload.CURRENT_SPEC["grant_node_hours"])
        - sum(int(entry["hours_charged"]) for entry in receipts),
    }
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "requests": [
                {"kind": "report", "context": context, "ledger": receipts},
                {"kind": "plan", "context": context, "ledger": receipts},
            ]
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_day"),
        "segments_then": [
            {key: row[key] for key in ("segment_id", "config_id", "node_type", "wall_hours",
                                       "first_step", "last_step", "resumed_from")}
            for row in context["ledger"]
        ],
        "last_row_then": {
            config_id: rows[-1] for config_id, rows in context["curves"].items() if rows
        },
        "bookings_then": [_receipt_summary(entry) for entry in receipts],
        "budget_then": context["budget"],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name,
                             "campaign": context["campaign"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "evidence_through": record.get("through_day"),
            "segments_then": len(context["ledger"]),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_booking(
    artifact_dir: Path, config_id: Any, node_type: Any, hours: Any, receipt_id: Any
) -> Mapping[str, Any]:
    return world.collect(
        Path(artifact_dir), workload.current(), config_id, node_type, hours, receipt_id
    )


def starting_stream() -> dict[str, Any]:
    return workload.opening_document()
