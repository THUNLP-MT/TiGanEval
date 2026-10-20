"The five binary project rubrics for the API service's start-up."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "unwind_releases_started_services": (
        "candidate_execution_failed",
        "failing_service_was_not_attempted",
        "handle_taken_after_the_teardown",
        "handle_never_given_back",
        "released_a_service_before_its_dependents",
        "stopped_the_same_service_twice",
        "released_something_it_had_not_started",
        "failure_named_the_wrong_service",
        "stop_error_not_recorded",
    ),
    "startup_order_follows_dependencies": (
        "candidate_execution_failed",
        "dependent_started_before_its_dependency",
        "order_ignored_a_service_without_a_connect_step",
    ),
    "each_service_starts_once": (
        "candidate_execution_failed",
        "service_never_started",
        "service_started_more_than_once",
        "retry_after_a_failed_start_restarted_services",
        "started_services_before_rejecting_the_manifest",
        "unknown_dependency_was_not_rejected",
        "retry_after_a_manifest_typo_refused",
        "retry_after_an_unknown_dependency_refused",
    ),
    "resolution_serves_started_instances": (
        "candidate_execution_failed",
        "unstarted_service_handed_out",
        "service_missing_after_boot",
        "started_service_not_resolvable",
        "replacement_not_installed",
    ),
    "start_up_within_the_deploy_window": (
        "candidate_execution_failed",
        "boot_did_not_finish",
        "deploy_window_overrun",
        "too_many_connects_at_once",
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


def unwind_releases_started_services(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def startup_order_follows_dependencies(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def each_service_starts_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def resolution_serves_started_instances(
    artifact_dir: Path, context: Any
) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def start_up_within_the_deploy_window(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
