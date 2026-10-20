'Read one delivered sweep notebook against the world it is a readout of.'

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    CANDIDATE_FAILURE,
    SandboxedProject,
    failed_analysis,
)

from . import oracle, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-sweep-",
    timeout=120.0,
)
_CACHE = AnalysisCache()

CURRENT = workload.CURRENT

REPORTED = (CURRENT, *workload.FOLLOWING)

BUCKETS: Mapping[str, str] = {
    "ten_times_loss_prediction": "prediction_failures",
    "runs_accounted_for": "accounting_failures",
    "loss_interval_is_honest": "interval_failures",
    "next_run_booking": "booking_failures",
    "prediction_holds_across_the_queue": "invariance_failures",
}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "ten_times_loss_prediction": (
        "target_compute_disagrees",
        "prediction_missing",
        "mixed_block_runs_kept",
        "late_rise_runs_kept",
        "supported_run_set_aside",
        "reading_disagrees_with_the_rows_it_kept",
        "prediction_disagrees",
        "comparison_prediction_readout_invalid",
        "candidate_execution_failed",
    ),
    "runs_accounted_for": (
        "receipt_stream_unreadable",
        "runs_are_not_a_ledger",
        "run_missing_from_the_report",
        "run_reported_twice",
        "run_not_on_the_table_or_the_receipts",
        "run_not_marked_used_or_set_aside",
        "run_marked_used_and_set_aside",
        "run_set_aside_without_reason",
        "run_set_aside_without_record_reason",
        "compute_units_do_not_reconcile",
        "compute_left_does_not_reconcile",
        "comparison_accounting_readout_invalid",
        "candidate_execution_failed",
    ),
    "loss_interval_is_honest": (
        "interval_is_not_a_range",
        "interval_excludes_reported_prediction",
        "interval_misses_the_loss_the_sweep_reaches",
        "interval_narrower_than_a_repeat_allows",
        "interval_wider_than_the_runs_support",
        "comparison_interval_readout_invalid",
        "candidate_execution_failed",
    ),
    "next_run_booking": (
        "paid_job_scored_on_a_training_block",
        "paid_job_rate_lacked_curve_support",
        "paid_job_repeated_the_sweep_lane",
        "plan_is_not_a_job_or_a_stop",
        "outside_queue_shape_limits",
        "exceeds_the_per_job_cap",
        "under_the_minimum_reservation",
        "no_reservation_days_left",
        "exceeds_the_compute_left",
        "shard_shares_a_training_block",
        "rate_above_published_curve_support",
        "sits_on_the_sweep_band",
        "stopped_with_compute_left",
        "candidate_execution_failed",
    ),
    "prediction_holds_across_the_queue": (
        "comparison_prediction_missing",
        "shifts_when_nothing_was_set_aside",
        "shifts_with_the_shard_offsets",
        "shifts_with_the_rate_that_comes_apart",
        "candidate_execution_failed",
    ),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def display(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "nothing"
    return str(value)[:80]


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{value[0]:.3f} to {value[1]:.3f}"
    return display(value)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident the group can open the summary table for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0
        if record.get("sweep") == CURRENT.sweep and not record.get("comparison")
        else 1,
    )


def _visible_first(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The incidents on the sweep the group holds, when there are any.'

    ordered = sorted(records, key=_report_order)
    here = [
        dict(record)
        for record in ordered
        if str(record.get("kind")) == CANDIDATE_FAILURE
        or (
            record.get("sweep") == CURRENT.sweep
            and not record.get("comparison")
        )
    ]
    return here if here else [dict(record) for record in ordered]


def _where(world: w.World) -> dict[str, str]:
    'The table a failure happened on, named the way the group names it.'

    return {"sweep": world.sweep}


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The jobs this delivery paid for, or the reason the stream will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


EARLIER_JOBS: Mapping[str, tuple[Mapping[str, Any], ...]] = {
    "borealis-spring": (
        {"job_id": "bs-recheck-1", "width": 256, "data": 70000, "learning_rate": 0.02,
         "val_shard": "val-e"},
        {"job_id": "bs-recheck-2", "width": 320, "data": 60000, "learning_rate": 0.02,
         "val_shard": "val-a"},
    ),
    "cirrus-winter": (
        {"job_id": "cw-recheck-1", "width": 288, "data": 60000, "learning_rate": 0.016,
         "val_shard": "val-b"},
    ),
}


def held_receipts(world: w.World) -> list[dict[str, Any]]:
    return w.extend(world, [], EARLIER_JOBS.get(world.sweep, ()))


def mirrored_receipts(
    world: w.World, source: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The same booked settings, observed in the paired world.'

    jobs = [
        {
            "job_id": str(item["job_id"]),
            "width": int(item["width"]),
            "data": int(item["data"]),
            "learning_rate": float(item["learning_rate"]),
            "val_shard": str(item["val_shard_id"]),
        }
        for item in source
    ]
    return w.extend(world, [], jobs)


def _filler_jobs(world: w.World) -> list[dict[str, Any]]:
    'Jobs on the band the sweep already covers, biggest charge first.'

    low, high = world.ratio_band()
    middle = (low * high) ** 0.5
    jobs = []
    for width in range(8, 800, 4):
        data = int(round(width * middle))
        if data < 500:
            continue
        cost = world.charge(width, data)
        if 1 <= cost <= int(world.spec["job_cap_units"]):
            jobs.append({"width": width, "data": data, "learning_rate": 0.02,
                         "val_shard": sorted(world.spec["shards"])[0], "charge": cost})
    return sorted(jobs, key=lambda job: -int(job["charge"]))


def _spend_down(
    world: w.World, entries: Sequence[Mapping[str, Any]], wanted_left: int
) -> list[Mapping[str, Any]]:
    'The stream with enough further jobs on it to leave about `wanted_left`.'

    granted = int(world.spec["units_granted"])
    stream = [dict(entry) for entry in entries]
    jobs = _filler_jobs(world)
    index = 0
    while True:
        if oracle.reservation_days_left(world, stream) <= 0:
            return stream
        left = granted - w.units_spent(stream)
        choice = next(
            (job for job in jobs if int(job["charge"]) <= left - wanted_left), None
        )
        if choice is None:
            return stream
        index += 1
        stream = w.extend(
            world,
            stream,
            [{**{k: v for k, v in choice.items() if k != "charge"},
              "job_id": f"filler-{index:02d}"}],
        )


def _spend_reservation_days(world: w.World) -> list[Mapping[str, Any]]:
    'A reachable stream that has used every reservation day.'

    stream: list[Mapping[str, Any]] = []
    floor_units = int(world.spec["job_floor_units"])
    jobs = [
        job for job in reversed(_filler_jobs(world))
        if int(job["charge"]) >= floor_units
    ]
    for index in range(int(world.spec["reservation_days"])):
        choice = next(
            job
            for job in jobs
            if int(job["charge"]) <= oracle.units_left(world, stream)
        )
        stream = w.extend(
            world,
            stream,
            [{**{key: value for key, value in choice.items() if key != "charge"},
              "job_id": f"day-filler-{index + 1:02d}"}],
        )
    return stream


def plan_states(
    world: w.World, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every state of the grant a booking has to answer from.'

    granted = int(world.spec["units_granted"])
    cheapest = oracle.cheapest_admissible(world)
    states = [{"label": "now", "receipts": [dict(item) for item in entries]}]
    for label, wanted in (
        ("half the grant spent", granted // 2),


        ("one small job left", oracle.cheapest_findable(world) + 1),
        ("the grant spent", max(0, cheapest - 1)),
    ):
        states.append(
            {"label": label, "receipts": _spend_down(world, entries, wanted)}
        )
    states.append(
        {"label": "reservation days spent", "receipts": _spend_reservation_days(world)}
    )
    return states


def requests_for(artifact_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    'The batch the notebook is run over, and the index back into it.'

    entries, stream_error = live_receipts(Path(artifact_dir))
    requests: list[dict[str, Any]] = []
    reports: list[tuple[w.World, list[dict[str, Any]], int]] = []
    pair_reports: list[
        tuple[w.World, w.World, list[dict[str, Any]], str, int]
    ] = []
    plans: list[tuple[w.World, dict[str, Any], int]] = []
    seen: dict[str, int] = {}

    def report_for(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> int:
        if world.sweep in seen:
            return seen[world.sweep]
        index = len(requests)
        seen[world.sweep] = index
        requests.append(
            {
                "kind": "report",
                "label": world.sweep,
                "context": world.context(),
                "receipts": [dict(item) for item in receipts],
            }
        )
        return index

    for world in REPORTED:
        receipts = entries if world is CURRENT else held_receipts(world)
        reports.append((world, [dict(item) for item in receipts], report_for(world, receipts)))
    for base, variant, mode in workload.PAIRS:
        base_receipts = entries if base is CURRENT else held_receipts(base)
        receipts = mirrored_receipts(variant, base_receipts)
        pair_reports.append(
            (base, variant, receipts, mode, report_for(variant, receipts))
        )
    for world in REPORTED:
        receipts = entries if world is CURRENT else held_receipts(world)
        if world is CURRENT and receipts:
            opening = {"label": "quarter opening", "receipts": []}
            plans.append((world, opening, len(requests)))
            requests.append(
                {
                    "kind": "plan",
                    "label": f"{world.sweep}: quarter opening",
                    "context": world.context(),
                    "receipts": [],
                }
            )
        for state in plan_states(world, receipts):
            plans.append((world, state, len(requests)))
            requests.append(
                {
                    "kind": "plan",
                    "label": f"{world.sweep}: {state['label']}",
                    "context": world.context(),
                    "receipts": [dict(item) for item in state["receipts"]],
                }
            )
    index = {
        "entries": entries,
        "stream_error": stream_error,
        "reports": reports,
        "pair_reports": pair_reports,
        "plans": plans,
        "report_index": dict(seen),
    }
    return requests, index


def _prediction_failures(
    world: w.World,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    where = _where(world)
    wanted_target = oracle.target_units(world)
    target = _number(report.get("target_compute_units"))
    if target is None or abs(target - wanted_target) > 0.5:
        return [
            _fail(
                "target_compute_disagrees",
                **where,
                reported=display(report.get("target_compute_units")),
                biggest_run_units=world.largest_units(),
                target_multiple=int(world.spec["target_multiple"]),
            )
        ]
    predicted = _number(report.get("predicted_loss"))
    if predicted is None:
        return [
            _fail(
                "prediction_missing",
                **where,
                reported=display(report.get("predicted_loss")),
            )
        ]
    reference = oracle.truth(world)
    told = {**where, "reported": display(predicted)}


    measured = _measured_rows(world, receipts)
    kept, set_aside = _reported_selection(report, measured)
    if kept:
        on_a_training_block = [
            run_id
            for run_id, row in kept.items()
            if str(row["shard_lineage"]) in world.training_blocks()
        ]
        if on_a_training_block:
            run_id = on_a_training_block[0]
            return [
                _fail("mixed_block_runs_kept", **told, run_id=run_id,
                      block=str(kept[run_id]["shard_lineage"]))
            ]
        that_turned = [
            run_id for run_id, row in kept.items() if _curve_turned(row.get("curve"))
        ]
        if that_turned:
            return [
                _fail("late_rise_runs_kept", **told, run_id=that_turned[0],
                      runs_that_turned=len(that_turned))
            ]
    unsupported = {
        run_id
        for run_id, row in measured.items()
        if str(row["shard_lineage"]) in world.training_blocks()
        or _curve_turned(row.get("curve"))
    }
    supported_left_out = [run_id for run_id in set_aside if run_id not in unsupported]
    if supported_left_out:
        run_id = supported_left_out[0]
        row = measured[run_id]
        losses = [float(point[1]) for point in row["curve"]]
        return [
            _fail(
                "supported_run_set_aside",
                **told,
                run_id=run_id,
                block=str(row["shard_lineage"]),
                final_loss=format(float(row["final_val_loss"]), ".4f"),
                lowest_loss=format(min(losses), ".4f"),
                record=str(row["record"]),
            )
        ]
    if kept:
        if abs(predicted - reference) <= oracle.TOLERANCE:
            return []
        rows = [kept[run_id] for run_id in kept]
        residual_swing, repeat_spread = _log_compute_residual_detail(rows)
        return [
            _fail(
                "reading_disagrees_with_the_rows_it_kept",
                **told,
                jobs_behind_the_number=len(rows),
                narrowest_width=min(int(row["width"]) for row in rows),
                widest_width=max(int(row["width"]) for row in rows),
                fewest_examples=min(int(row["data"]) for row in rows),
                most_examples=max(int(row["data"]) for row in rows),
                residual_swing=format(residual_swing, ".4f"),
                repeat_spread=format(repeat_spread, ".4f"),
            )
        ]
    return [_fail("prediction_disagrees", **told)]


def _measured_rows(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    'Every measured job, normalized across the table and receipt stream.'

    curves = world.curves()
    measured = {
        str(row["run_id"]): {
            **dict(row),
            "curve": curves[str(row["run_id"])],
            "record": "summary table",
        }
        for row in world.ledger()
    }
    for receipt in receipts:
        observed = receipt.get("observed") or {}
        measured[str(receipt["run_id"])] = {
            "run_id": str(receipt["run_id"]),
            "width": int(receipt["width"]),
            "data": int(receipt["data"]),
            "learning_rate": float(receipt["learning_rate"]),
            "final_val_loss": float(observed["final_val_loss"]),
            "val_shard_id": str(receipt["val_shard_id"]),
            "shard_lineage": str(receipt["shard_lineage"]),
            "compute_units": int(receipt["compute_units_charged"]),
            "curve": list(observed["curve"]),
            "record": "receipt stream",
        }
    return measured


def _reported_selection(
    report: Mapping[str, Any], measured: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    'Known jobs explicitly marked used and set aside by the delivery.'

    rows = report.get("runs")
    if not isinstance(rows, list):
        return {}, {}
    kept: dict[str, Mapping[str, Any]] = {}
    set_aside: dict[str, Mapping[str, Any]] = {}
    for entry in rows:
        if not isinstance(entry, Mapping):
            continue
        run_id = str(entry.get("run_id"))
        if run_id not in measured:
            continue
        if entry.get("used") is True:
            kept.setdefault(run_id, measured[run_id])
        elif entry.get("used") is False:
            set_aside.setdefault(run_id, measured[run_id])
    return kept, set_aside


def _set_aside_reason_matches_record(
    world: w.World, row: Mapping[str, Any], reason: str
) -> bool:
    'Whether a free-text reason names a public fact that excludes this job.'


    text = re.sub(r"[^a-z0-9]+", " ", str(reason).casefold()).strip()
    matches: list[bool] = []
    raw_lineage = str(row.get("shard_lineage", ""))
    lineage = re.sub(r"[^a-z0-9]+", " ", raw_lineage.casefold()).strip()
    if raw_lineage in world.training_blocks():
        matches.append(
            lineage.casefold() in text
            or any(
                token in text
                for token in (
                    "training mixture",
                    "training block",
                    "train on",
                    "trains on",
                    "trained on",
                    "contaminat",
                    "leak",
                    "data manifest",
                )
            )
        )
    if _curve_turned(row.get("curve")):
        matches.append(
            any(
                token in text
                for token in (
                    "curve",
                    "turn",
                    "rose",
                    "rise",
                    "came apart",
                    "unstable",
                    "diverg",
                    "not settle",
                    "did not settle",
                    "lowest checkpoint",
                    "above its minimum",
                    "tail minimum",
                    "final checkpoint",
                )
            )
        )
    return any(matches)


def _curve_turned(curve: Any) -> bool:
    if not isinstance(curve, list) or not curve:
        return False
    losses = [float(point[1]) for point in curve]
    return losses[-1] - min(losses) > 0.005


def _log_compute_residual_detail(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    'Public residual structure left by a one-dimensional log-compute line.'

    points = [
        (math.log(float(row["compute_units"])), float(row["final_val_loss"]))
        for row in rows
        if float(row["compute_units"]) > 0.0
    ]
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
        if denominator > 0.0
        else 0.0
    )
    residuals = [y - (mean_y + slope * (x - mean_x)) for x, y in points]
    groups: dict[tuple[int, int, float], list[float]] = {}
    for row in rows:
        key = (int(row["width"]), int(row["data"]), float(row["learning_rate"]))
        groups.setdefault(key, []).append(float(row["final_val_loss"]))
    spreads = [max(values) - min(values) for values in groups.values() if len(values) > 1]
    return max(residuals) - min(residuals), max(spreads, default=0.0)


def _interval_failures(world: w.World, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    where = _where(world)
    bounds = report.get("loss_interval")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(_number(value) is None for value in bounds)
        or bounds[0] > bounds[1]
    ):
        return [_fail("interval_is_not_a_range", **where, reported_range=_pair(bounds))]
    low, high = float(bounds[0]), float(bounds[1])
    half = (high - low) / 2.0
    spread = world.repeat_spread()
    told = {
        **where,
        "reported_range": _pair(bounds),
        "repeat_spread": format(spread, ".4f"),
    }
    predicted = _number(report.get("predicted_loss"))
    if predicted is not None and not low <= predicted <= high:
        return [
            _fail(
                "interval_excludes_reported_prediction",
                **told,
                reported=format(predicted, ".4f"),
            )
        ]
    reference = oracle.truth(world)
    if reference < low or reference > high:
        return [_fail("interval_misses_the_loss_the_sweep_reaches", **told)]
    if half < oracle.floor_half_width(world) - 1e-9:
        return [_fail("interval_narrower_than_a_repeat_allows", **told)]
    if half > oracle.ceiling_half_width(world) + 1e-9:
        return [_fail("interval_wider_than_the_runs_support", **told)]
    return []


def _accounting_failures(
    world: w.World,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    stream_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(world)
    if stream_error:
        return [_fail("receipt_stream_unreadable", **where, reason=str(stream_error))]
    charged = {
        str(row["run_id"]): int(row["compute_units"]) for row in world.ledger()
    }
    for item in receipts:
        charged[str(item["run_id"])] = int(item["compute_units_charged"])
    rows = report.get("runs")
    if not isinstance(rows, list):
        return [_fail("runs_are_not_a_ledger", **where, reported=display(rows),
                      jobs_to_account_for=len(charged))]
    seen: dict[str, int] = {}
    measured = _measured_rows(world, receipts)
    for row in rows:
        run_id = str(row.get("run_id"))
        seen[run_id] = seen.get(run_id, 0) + 1
        if seen[run_id] > 1:
            return [_fail("run_reported_twice", **where, run_id=run_id,
                          times_reported=seen[run_id])]
        if run_id not in charged:
            return [_fail("run_not_on_the_table_or_the_receipts", **where, run_id=run_id,
                          jobs_to_account_for=len(charged))]
        used = row.get("used")
        if not isinstance(used, bool):
            return [_fail("run_not_marked_used_or_set_aside", **where, run_id=run_id,
                          reported=display(row.get("used")))]
        reason = str(row.get("set_aside") or "").strip()
        if used is True and reason:
            return [_fail("run_marked_used_and_set_aside", **where, run_id=run_id,
                          reported=display(row.get("set_aside")))]
        if used is False:
            if not reason:
                return [_fail("run_set_aside_without_reason", **where, run_id=run_id,
                              reported=display(row.get("set_aside")))]
            measured_row = measured.get(run_id)
            is_excluded = measured_row is not None and (
                str(measured_row.get("shard_lineage")) in world.training_blocks()
                or _curve_turned(measured_row.get("curve"))
            )
            if is_excluded and not _set_aside_reason_matches_record(
                world, measured_row, reason
            ):
                return [_fail("run_set_aside_without_record_reason", **where,
                              run_id=run_id, reported=display(row.get("set_aside")))]
        units = _number(row.get("compute_units"))
        if units is None or abs(units - charged[run_id]) > 0.5:
            return [_fail("compute_units_do_not_reconcile", **where, run_id=run_id,
                          reported=display(row.get("compute_units")),
                          charged=charged[run_id])]
    for run_id in charged:
        if run_id not in seen:
            return [_fail("run_missing_from_the_report", **where, run_id=run_id,
                          jobs_to_account_for=len(charged))]
    left = _number(report.get("compute_units_left"))
    wanted_left = int(world.spec["units_granted"]) - w.units_spent(receipts)
    if left is None or abs(left - wanted_left) > 0.5:
        return [_fail("compute_left_does_not_reconcile", **where,
                      reported=display(report.get("compute_units_left")),
                      expected_left=wanted_left,
                      units_spent=w.units_spent(receipts))]
    return []


def _paid_job_failures(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Scientific booking errors already committed by this delivery.'

    failures: list[dict[str, Any]] = []
    prefix: list[Mapping[str, Any]] = []
    for receipt in receipts:
        booking = {
            "width": int(receipt["width"]),
            "data": int(receipt["data"]),
            "learning_rate": float(receipt["learning_rate"]),
            "val_shard": str(receipt["val_shard_id"]),
        }
        reason = oracle.booking_is_admissible(world, prefix, booking)
        common = {
            **_where(world),
            "run_id": str(receipt["run_id"]),
            "width": int(receipt["width"]),
            "data": int(receipt["data"]),
            "learning_rate": format(float(receipt["learning_rate"]), ".4g"),
            "val_shard": str(receipt["val_shard_id"]),
            "charged": int(receipt["compute_units_charged"]),
        }
        if reason == "shard_shares_a_training_block":
            failures.append(
                _fail(
                    "paid_job_scored_on_a_training_block",
                    **common,
                    block=world.shard_lineage(str(receipt["val_shard_id"])),
                )
            )
        elif reason == "rate_above_published_curve_support":
            failures.append(
                _fail(
                    "paid_job_rate_lacked_curve_support",
                    **common,
                    supported_rate=format(oracle.supported_rate(world), ".4g"),
                )
            )
        elif reason == "sits_on_the_sweep_band":
            below, above = oracle.band_edges(world)
            failures.append(
                _fail(
                    "paid_job_repeated_the_sweep_lane",
                    **common,
                    examples_per_width=format(
                        float(receipt["data"]) / float(receipt["width"]), ".0f"
                    ),
                    comparison_low=format(below, ".0f"),
                    comparison_high=format(above, ".0f"),
                )
            )
        prefix.append(receipt)
    return failures


def _booking_failures(
    world: w.World, state: Mapping[str, Any], offered: Any
) -> list[dict[str, Any]]:
    receipts = state["receipts"]
    left = oracle.units_left(world, receipts)
    stop_is_right = oracle.must_stop(world, receipts)
    told = {
        **_where(world),
        "queue_state": str(state.get("label", "an unnamed queue state")),
        "compute_left": left,
        "reservation_days_left": oracle.reservation_days_left(world, receipts),
        "jobs_booked": len(receipts),
        "job_cap": int(world.spec["job_cap_units"]),
        "smallest_reservation": int(world.spec["job_floor_units"]),
    }
    if not isinstance(offered, list) or not offered:
        return [_fail("plan_is_not_a_job_or_a_stop", **told, reported=display(offered))]
    for choice in offered:
        if isinstance(choice, str):
            if choice != "stop":
                return [_fail("plan_is_not_a_job_or_a_stop", **told, reported=display(choice))]
            if not stop_is_right:


                return [_fail("stopped_with_compute_left", **told)]
            continue
        if not isinstance(choice, dict):
            return [_fail("plan_is_not_a_job_or_a_stop", **told, reported=display(choice))]
        reason = oracle.booking_is_admissible(world, receipts, choice)
        if reason is None:
            continue
        if reason == "plan_is_not_a_job_or_a_stop":
            return [_fail(reason, **told, reported=display(choice))]
        width = choice.get("width")
        data = choice.get("data")
        named = {
            **told,
            "width": display(width),
            "data": display(data),
            "charged": world.charge(int(width), int(data)),
        }
        if reason == "outside_queue_shape_limits":
            return [
                _fail(
                    reason,
                    **named,
                    width_min=w.WIDTH_MIN,
                    width_max=w.WIDTH_MAX,
                    data_min=w.DATA_MIN,
                    data_max=w.DATA_MAX,
                )
            ]
        if reason == "no_reservation_days_left":
            return [_fail(reason, **named)]
        if reason == "shard_shares_a_training_block":
            shard = str(choice.get("val_shard"))
            return [_fail(reason, **named, val_shard=shard,
                          block=world.shard_lineage(shard))]
        if reason == "rate_above_published_curve_support":
            return [_fail(reason, **named, learning_rate=display(choice.get("learning_rate")))]
        if reason == "sits_on_the_sweep_band":
            below, above = oracle.band_edges(world)
            return [_fail(reason, **named,
                          examples_per_width=format(float(data) / float(width), ".0f"),
                          comparison_low=format(below, ".0f"),
                          comparison_high=format(above, ".0f"))]
        return [_fail(reason, **named)]
    return []


def _comparison_report_failures(
    base: w.World,
    variant: w.World,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    'Apply each report check to a pair without exposing its private table.'

    failures = {
        "prediction_failures": _prediction_failures(variant, report, receipts),
        "accounting_failures": _accounting_failures(variant, report, receipts, None),
        "interval_failures": _interval_failures(variant, report),
    }
    modes = {
        "prediction_failures": (
            "comparison_prediction_readout_invalid",
            "target, number or job selection",
        ),
        "accounting_failures": (
            "comparison_accounting_readout_invalid",
            "job list or grant balance",
        ),
        "interval_failures": (
            "comparison_interval_readout_invalid",
            "loss range",
        ),
    }
    generic: dict[str, list[dict[str, Any]]] = {name: [] for name in failures}
    for bucket, records in failures.items():
        if records:
            mode, part = modes[bucket]
            generic[bucket].append(
                _fail(mode, sweep=base.sweep, comparison=True, part=part)
            )
    return generic


_PAID_JOB_MODES = {
    "paid_job_scored_on_a_training_block",
    "paid_job_rate_lacked_curve_support",
    "paid_job_repeated_the_sweep_lane",
}


def _booking_visible_first(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'Prefer an irreversible action, then a real current state, to a rehearsal.'

    paid = [dict(record) for record in records if record.get("kind") in _PAID_JOB_MODES]
    if paid:
        return _visible_first(paid)
    actual = [dict(record) for record in records if record.get("queue_state") == "now"]
    if actual:
        return _visible_first(actual)
    return _visible_first(records)


def _invariance_failures(
    base: w.World, variant: w.World, mode: str, reports: Mapping[str, Any]
) -> list[dict[str, Any]]:
    raw_first = (reports.get(base.sweep) or {}).get("predicted_loss")
    raw_second = (reports.get(variant.sweep) or {}).get("predicted_loss")
    first = _number(raw_first)
    second = _number(raw_second)
    if first is None or second is None:
        return [
            _fail(
                "comparison_prediction_missing",
                sweep=base.sweep,
                reported=display(raw_first),
                reported_on_the_other=display(raw_second),
            )
        ]
    gap = abs(first - second)
    if gap <= oracle.INVARIANCE_TOLERANCE:
        return []
    return [
        _fail(
            mode,
            sweep=base.sweep,
            other_sweep=variant.sweep,
            reported=format(first, ".4f"),
            reported_on_the_other=format(second, ".4f"),
            gap=format(gap, ".4f"),
        )
    ]


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
            f"{reported[len(_TIMEOUT_PHRASE):].strip()} and the queue console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the sweep notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every sweep and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        requests, index = requests_for(Path(artifact_dir))
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {
                "sweep": CURRENT.sweep,
                "jobs_paid_for": len(index["entries"]),
            }
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(position: int) -> tuple[Any, str | None]:
            if position >= len(results):
                return None, "the notebook returned no answer for one of the sweeps"
            item = dict(results[position])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        broke = False
        reported: dict[str, Mapping[str, Any]] = {}
        for world, receipts, position in index["reports"]:
            value, error = answer(position)
            if error is not None:
                broke = True
                for bucket in ("prediction_failures", "accounting_failures",
                               "interval_failures"):
                    failures[bucket].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            reported[world.sweep] = report
            failures["prediction_failures"].extend(
                _prediction_failures(world, report, receipts)
            )
            failures["interval_failures"].extend(_interval_failures(world, report))
            failures["accounting_failures"].extend(
                _accounting_failures(
                    world, report, receipts,
                    index["stream_error"] if world is CURRENT else None,
                )
            )
        for base, variant, receipts, _mode, position in index["pair_reports"]:
            value, error = answer(position)
            if error is not None:
                broke = True
                failures["invariance_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            reported[variant.sweep] = report
            comparison = _comparison_report_failures(base, variant, report, receipts)
            for bucket, records in comparison.items():
                failures[bucket].extend(records)
        for base, variant, _receipts, mode, _position in index["pair_reports"]:
            failures["invariance_failures"].extend(
                _invariance_failures(base, variant, mode, reported)
            )
        failures["booking_failures"].extend(
            _paid_job_failures(CURRENT, index["entries"])
        )
        for world, state, position in index["plans"]:
            value, error = answer(position)
            if error is not None:
                broke = True
                failures["booking_failures"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        error=error,
                        **_where(world),
                        queue_state=str(state.get("label", "an unnamed queue state")),
                    )
                )
                continue
            failures["booking_failures"].extend(_booking_failures(world, state, value))

        analysis: dict[str, Any] = {}
        for name, records in failures.items():
            analysis[name] = (
                _booking_visible_first(records)
                if name == "booking_failures"
                else _visible_first(records)
            )
        analysis["case"] = {
            "sweep": CURRENT.sweep,
            "jobs_paid_for": len(index["entries"]),
            "sweeps_reviewed": len(index["report_index"]),
            "notebook_stopped": broke,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a session record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    'The sweep evidence as it stood at the end of one recorded session.'

    through = str(record["through_date"])
    context = world.context()
    context["runs"] = [row for row in context["runs"] if row["date"] <= through]
    kept = {row["run_id"] for row in context["runs"]}
    context["curves"] = {
        run_id: curve for run_id, curve in context["curves"].items() if run_id in kept
    }
    context["changes"] = [
        entry for entry in context["changes"] if entry["day"] <= str(record["date"])
    ]
    return context


def _summary(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    "The summary table for that session's jobs, as the operator saw it."

    return [
        {
            key: row[key]
            for key in (
                "run_id",
                "date",
                "width",
                "data",
                "learning_rate",
                "steps",
                "final_val_loss",
                "val_shard_id",
                "shard_lineage",
                "compute_units",
                "loader_version",
            )
        }
        for row in context["runs"]
    ]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = CURRENT.context()
    entries, error = live_receipts(root)
    granted = int(CURRENT.spec["units_granted"])
    queue = dict(context["queue"])
    queue["reservation_days_left"] = w.reservation_days_left(CURRENT, entries)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{
                    key: raw.get(key)
                    for key in ("record_id", "date", "operator", "through_date")
                },
            }
        )
    return {
        "summary": f"The {context['sweep']} sweep, the queue's terms and the sessions on record.",
        "measurements": {
            "sweep": context["sweep"],
            "target_multiple": context["target_multiple"],
            "queue": queue,
            "compute_units_spent": w.units_spent(entries),
            "compute_units_left": granted - w.units_spent(entries),
            "jobs_in_the_summary_table": len(context["runs"]),
            "biggest_job_units": CURRENT.largest_units(),
            "shards": context["shards"],
            "blocks": context["blocks"],
            "jobs_on_the_receipt_stream": [
                {
                    "job_id": item["job_id"],
                    "run_id": item["run_id"],
                    "width": item["width"],
                    "data": item["data"],
                    "learning_rate": item["learning_rate"],
                    "val_shard_id": item["val_shard_id"],
                    "compute_units_charged": item["compute_units_charged"],
                    "final_val_loss": item["observed"]["final_val_loss"],
                }
                for item in entries
            ],
            "receipt_stream": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that session's operator ran it."

    record = _record(record_path)
    context = snapshot(CURRENT, record)
    entries, error = live_receipts(Path(artifact_dir))
    kept = {str(row["run_id"]) for row in context["runs"]}
    receipts = [item for item in entries if str(item["run_id"]) in kept]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "requests": [
                {"kind": "report", "context": context, "receipts": receipts},
                {"kind": "plan", "context": context, "receipts": receipts},
            ]
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_date"),
        "summary_table": _summary(context),
        "changes": context["changes"],
        "jobs_on_the_receipt_stream": [
            {"job_id": item["job_id"], "run_id": item["run_id"],
             "compute_units_charged": item["compute_units_charged"],
             "final_val_loss": item["observed"]["final_val_loss"]}
            for item in receipts
        ],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "sweep": context["sweep"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "sweep": context["sweep"],
            "jobs_in_the_summary_table": len(context["runs"]),
            "biggest_job_units": max(
                int(row["compute_units"]) for row in context["runs"]
            ),
            "receipt_stream": error or "reads back in order",
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_run_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_job(
    artifact_dir: Path,
    width: Any,
    data: Any,
    learning_rate: Any,
    val_shard: Any,
    job_id: Any,
) -> Mapping[str, Any]:
    return w.collect(
        Path(artifact_dir), CURRENT, width, data, learning_rate, val_shard, job_id
    )


def starting_stream() -> dict[str, Any]:
    'The receipt stream the sweep starts from: nothing bought since it closed.'

    return w.empty_stream(CURRENT)
