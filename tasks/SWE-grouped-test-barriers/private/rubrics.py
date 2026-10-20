"The five binary project checks for the device lab's night runner."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "record_attribution": (
        "candidate_execution_failed",
        "case_not_run_for_handset",
        "row_on_wrong_bench",
        "no_row_for_a_handset",
        "two_rows_for_one_handset",
        "row_for_a_case_the_bench_did_not_run",
        "flag_landed_on_another_handset",
        "flag_landed_on_several_records",
        "flag_lost_between_records",
        "unexpected_flag_on_report",
        "wrong_case_outcome",
    ),
    "gate_scope_and_lifetime": (
        "candidate_execution_failed",
        "gate_did_not_hold",
        "gate_reused_inside_the_case",
        "gate_reused_across_the_night",
    ),
    "gate_party_from_bench": (
        "candidate_execution_failed",
        "handsets_left_waiting",
        "bench_gate_blocked",
        "bench_did_not_all_meet",
        "bench_phase_ran_on_every_handset",
        "bench_phase_run_count_wrong",
    ),
    "context_binding_contract": (
        "candidate_execution_failed",
        "context_answered_outside_its_phase",
        "context_alert_was_the_wrong_kind",
        "alert_missing_its_details",
        "wrong_handset_reported",
        "no_handset_reported_inside_its_phase",
        "gate_request_outside_its_phase",
        "timeout_sign_not_told_apart",
        "probe_not_run",
    ),
    "night_envelope": (
        "candidate_execution_failed",
        "scheduler_turn_limit_exhausted",
        "night_left_unfinished_work",
        "night_never_closed",
        "benches_after_a_failure_never_ran",
        "bench_close_skipped",
        "handsets_left_checked_out",
        "pool_event_order_wrong",
        "night_opened_out_of_turn",
        "night_phase_ran_twice",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple(mode for mode in modes if mode != "candidate_execution_failed")
    for rubric_id, modes in FAILURE_MODES.items()
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def record_attribution(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def gate_scope_and_lifetime(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def gate_party_from_bench(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def context_binding_contract(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def night_envelope(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
