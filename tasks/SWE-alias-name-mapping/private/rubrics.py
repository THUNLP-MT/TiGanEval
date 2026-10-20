"The five binary project checks for partner payload intake."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "single_key_consumption": (
        "candidate_execution_failed",
        "two_spellings_one_field_accepted",
        "refusal_named_the_wrong_keys",
        "one_spelling_payload_refused",
        "missing_required_field_not_refused",
    ),
    "key_partition_accounting": (
        "candidate_execution_failed",
        "alias_key_not_recognised",
        "alias_collected_as_extra",
        "unknown_key_not_reported",
        "unknown_key_not_collected",
        "unknown_key_was_invented",
    ),
    "namespace_validation": (
        "candidate_execution_failed",
        "colliding_fields_built_anyway",
        "live_config_refused_at_build",
        "live_config_refused_every_payload",
        "collision_refused_outside_the_error_family",
    ),
    "client_contract_agreement": (
        "candidate_execution_failed",
        "schema_omits_an_accepted_key",
        "error_trail_named_an_unsent_key",
        "schema_demanded_one_spelling",
        "schema_key_typed_unlike_the_field",
        "schema_key_published_unlike_the_field",
        "schema_published_an_unaccepted_key",
        "schema_omitted_a_required_key",
    ),
    "alias_derivation": (
        "candidate_execution_failed",
        "generated_alias_not_accepted",
        "explicit_alias_was_rewritten",
        "alias_leaked_into_the_output",
        "dump_record_disagrees",
        "dump_did_not_write_a_record",
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


def single_key_consumption(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def key_partition_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def namespace_validation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def client_contract_agreement(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def alias_derivation(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
