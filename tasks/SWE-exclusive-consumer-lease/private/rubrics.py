"Five binary project judgements for the fleet job scheduler."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "single_holder_job_conservation": (
        "candidate_execution_failed",
        "job_run_without_submission",
        "job_payload_changed",
        "job_run_on_wrong_class_claim",
        "job_run_more_than_once",
        "job_run_by_a_released_worker",
        "job_run_beside_the_holder",
        "job_never_run",
        "scheduler_raised_at_the_caller",
        "worker_could_not_take_the_class",
    ),
    "fleet_wide_claim_registry": (
        "candidate_execution_failed",
        "deliveries_depend_on_the_link_split",
        "stale_worker_ran_after_a_restart",
        "stale_waiting_job_ran_after_a_restart",
        "class_silent_after_a_restart",
    ),
    "exclusivity_survives_reregistration": (
        "candidate_execution_failed",
        "exclusivity_lost_after_a_plain_registration",
        "lease_moved_on_a_plain_registration",
    ),
    "revocation_notice_completeness": (
        "candidate_execution_failed",
        "removal_error_reached_the_caller",
        "notice_named_the_wrong_claim",
        "worker_not_told_when_its_link_dropped",
        "demoted_worker_not_told",
        "worker_not_told_when_the_class_was_retired",
        "notice_delivered_twice",
        "worker_told_after_releasing_the_class",
        "worker_told_it_lost_a_class_it_still_had",
    ),
    "rank_and_window_discipline": (
        "candidate_execution_failed",
        "lower_ranked_worker_ran_the_class",
        "worker_held_more_than_its_window",
        "lease_moved_to_an_equal_ranked_newcomer",
        "job_waited_while_a_worker_had_room",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "single_holder_job_conservation": (
        "job_run_without_submission",
        "job_payload_changed",
        "job_run_on_wrong_class_claim",
        "job_run_more_than_once",
        "job_run_by_a_released_worker",
        "job_run_beside_the_holder",
        "scheduler_raised_at_the_caller",
        "worker_could_not_take_the_class",
        "job_never_run",
    ),
    "fleet_wide_claim_registry": (
        "deliveries_depend_on_the_link_split",
        "stale_worker_ran_after_a_restart",
        "stale_waiting_job_ran_after_a_restart",
        "class_silent_after_a_restart",
    ),
    "exclusivity_survives_reregistration": (
        "exclusivity_lost_after_a_plain_registration",
        "lease_moved_on_a_plain_registration",
    ),
    "revocation_notice_completeness": (
        "removal_error_reached_the_caller",
        "notice_named_the_wrong_claim",
        "worker_not_told_when_its_link_dropped",
        "demoted_worker_not_told",
        "worker_not_told_when_the_class_was_retired",
        "notice_delivered_twice",
        "worker_told_after_releasing_the_class",
        "worker_told_it_lost_a_class_it_still_had",
    ),
    "rank_and_window_discipline": (
        "lower_ranked_worker_ran_the_class",
        "worker_held_more_than_its_window",
        "lease_moved_to_an_equal_ranked_newcomer",
        "job_waited_while_a_worker_had_room",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def single_holder_job_conservation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def fleet_wide_claim_registry(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def exclusivity_survives_reregistration(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def revocation_notice_completeness(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def rank_and_window_discipline(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
