"""The five binary project rubrics for the delivery portal's request surface."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet
from .harness import BUCKETS, evaluate_project

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "body_free_projection": (
        "candidate_execution_failed",
        "probe_answer_missing",
        "probe_ignored_the_gate",
        "probe_returned_the_record",
        "probe_refusal_carried_its_text",
        "probe_lost_the_size",
    ),
    "path_method_advertisement": (
        "candidate_execution_failed",
        "summary_answer_missing",
        "advertised_methods_disagree",
        "advertised_methods_incomplete",
        "published_operations_disagree",
    ),
    "layered_defaults_resolution": (
        "candidate_execution_failed",
        "router_setting_never_inherited",
        "route_override_ignored",
        "mount_settings_bled_across",
    ),
    "explicit_operations_win": (
        "candidate_execution_failed",
        "explicit_probe_shadowed",
        "explicit_document_shadowed",
        "neighbouring_probe_unanswered",
    ),
    "generated_traffic_accounting": (
        "candidate_execution_failed",
        "counts_not_keyed_by_mount",
        "generated_traffic_uncounted",
        "ordinary_traffic_counted",
        "report_shared_its_own_counters",
    ),
}
_PRIORITY: Mapping[str, tuple[str, ...]] = {
    rubric_id: tuple((mode for mode in modes if mode != "candidate_execution_failed"))
    for rubric_id, modes in FAILURE_MODES.items()
}
RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def body_free_projection(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def path_method_advertisement(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def layered_defaults_resolution(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def explicit_operations_win(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def generated_traffic_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
