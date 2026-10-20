"""The five binary project checks for the checkout hint readout."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Sequence
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import CANDIDATE_FAILURE, EXECUTION_FAILURE_MODE, RubricSet
from .harness import BUCKETS, CURRENT, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "conversion_lift_estimate": (
        "returning_sessions_counted_in_the_cohort",
        "crawler_sessions_left_in_the_cohort",
        "shed_confirmations_not_restored",
        "cohort_or_lift_disagrees",
        EXECUTION_FAILURE_MODE,
    ),
    "lift_bounds_are_honest": (
        "bounds_are_not_an_interval",
        "bounds_narrower_than_the_shed_confirmations_allow",
        "bounds_wider_than_the_counters_support",
        EXECUTION_FAILURE_MODE,
    ),
    "measurements_reconcile_with_the_receipts": (
        "receipt_stream_unreadable",
        "measurements_are_not_a_ledger",
        "paid_rescan_missing_from_the_readout",
        "rescan_not_on_the_receipt_stream",
        "rescan_reported_twice",
        EXECUTION_FAILURE_MODE,
    ),
    "rollout_decision": (
        "decision_is_not_a_release_action",
        "expansion_recommended_without_clearing_the_gate",
        "hold_recommended_after_clearing_the_gate",
        EXECUTION_FAILURE_MODE,
    ),
    "next_collection_plan": (
        "paid_rescan_could_not_change_the_readout",
        "plan_did_not_name_a_slice_or_a_stop",
        "scan_outside_the_retained_archive",
        "scan_beyond_the_remaining_units",
        "scan_of_a_slice_already_paid_for",
        "scan_that_cannot_change_the_readout",
        "stopped_with_slices_still_unmeasured",
        EXECUTION_FAILURE_MODE,
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    name: tuple((mode for mode in modes if mode != EXECUTION_FAILURE_MODE))
    for name, modes in FAILURE_MODES.items()
}


class LiveReadoutFirstRubricSet(RubricSet):
    """Report the live readout before failures found only in reuse checks."""

    def select_mode(
        self,
        rubric_id: str,
        analysis: Mapping[str, Any],
        failures: Sequence[Mapping[str, Any]],
    ) -> str:
        if analysis.get("harness_error") or any(
            (str(item.get("kind", "")) == CANDIDATE_FAILURE for item in failures)
        ):
            return super().select_mode(rubric_id, analysis, failures)
        live = [
            item for item in failures if str(item.get("readout", "")) == CURRENT.readout
        ]
        return super().select_mode(rubric_id, analysis, live or failures)


RUBRICS = LiveReadoutFirstRubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def conversion_lift_estimate(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def lift_bounds_are_honest(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def measurements_reconcile_with_the_receipts(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def rollout_decision(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def next_collection_plan(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
