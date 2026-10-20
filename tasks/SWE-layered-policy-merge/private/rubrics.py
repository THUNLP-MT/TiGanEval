"The five binary project rubrics for the ingress control plane."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "merged_plan_matches_the_policies": (
        "candidate_execution_failed",
        "edge_operation_failed",
        "plan_refused_by_proxy",
        "inherited_entry_dropped",
        "entry_not_in_any_policy",
        "entries_out_of_precedence_order",
    ),
    "each_key_pins_once": (
        "candidate_execution_failed",
        "edge_operation_failed",
        "key_pins_twice",
        "lower_precedence_definition_kept",
        "authored_definition_changed",
        "key_never_pins",
    ),
    "pinning_survives_a_repush": (
        "candidate_execution_failed",
        "edge_operation_failed",
        "plan_depends_on_reconcile_order",
        "plan_depends_on_authoring_order",
        "plan_depends_on_process_start",
        "shopper_moved_by_repush",
    ),
    "opt_out_clears_inherited_pinning": (
        "candidate_execution_failed",
        "edge_operation_failed",
        "inherited_pinning_survives_opt_out",
        "contradictory_policy_reached_proxy",
        "contradictory_policy_half_applied",
        "contradictory_policy_accepted",
    ),
    "pin_key_matches_the_reference": (
        "candidate_execution_failed",
        "edge_operation_failed",
        "absent_value_folded",
        "rewritten_value_not_used",
        "stop_ignored",
        "cookie_ttl_not_normalised",
        "cookie_line_wrong",
        "request_sent_to_wrong_pod",
        "pin_part_wrong",
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


def merged_plan_matches_the_policies(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def each_key_pins_once(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def pinning_survives_a_repush(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def opt_out_clears_inherited_pinning(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def pin_key_matches_the_reference(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
