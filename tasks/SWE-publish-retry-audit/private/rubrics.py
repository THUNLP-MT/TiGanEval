"The five binary project rubrics for the release job's publishing step."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "published_bytes_match_the_build": (
        "candidate_execution_failed",
        "artifact_never_landed",
        "stored_body_is_not_the_artifact",
    ),
    "attempt_ledger_matches_the_host_log": (
        "candidate_execution_failed",
        "attempt_missing_from_the_ledger",
        "ledger_recorded_an_attempt_that_never_happened",
        "ledger_called_a_refused_attempt_a_success",
        "attempt_numbers_do_not_match_the_tries",
        "ledger_line_disagrees_with_host",
    ),
    "refusals_are_answered_not_retried": (
        "candidate_execution_failed",
        "refusal_retried",
        "mirror_answer_retried",
        "transient_failure_abandoned",
        "host_message_replaced",
        "planned_item_was_skipped",
    ),
    "waits_follow_the_hosts_direction": (
        "candidate_execution_failed",
        "retried_before_the_host_allowed_it",
        "one_wait_ran_past_the_release_window",
        "retried_without_the_configured_pause",
        "kept_publishing_after_the_stop",
    ),
    "release_is_independent_of_publish_order": (
        "candidate_execution_failed",
        "what_shipped_depends_on_the_order",
        "ledger_order_follows_the_run",
        "release_made_no_attempt_before_stop",
        "ledger_not_in_vendor_order",
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


def published_bytes_match_the_build(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def attempt_ledger_matches_the_host_log(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def refusals_are_answered_not_retried(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def waits_follow_the_hosts_direction(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def release_is_independent_of_publish_order(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
