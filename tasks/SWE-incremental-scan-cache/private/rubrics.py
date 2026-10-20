"Five binary project rubrics for the incremental scan-cache project."

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tiganeval.protocol import RubricResult
from tiganeval.taskkit import RubricSet

from .harness import BUCKETS, evaluate_project


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "clean_scan_finding_equivalence": (
        "candidate_execution_failed",
        "nightly_scan_failed",
        "stale_findings_reported",
        "findings_missing_after_change",
        "findings_differ_from_clean_scan",
    ),
    "fail_closed_cache_integrity": (
        "candidate_execution_failed",
        "cache_failure_aborted_scan",
        "import_aborted_the_run",
        "damaged_entry_served",
        "import_poisoned_cache",
        "stale_bundle_served",
    ),
    "honest_cache_accounting": (
        "candidate_execution_failed",
        "scan_run_failed",
        "report_contract_incomplete",
        "accounting_totals_inconsistent",
        "reuse_claim_contradicts_analysis",
        "cache_inventory_misreported",
    ),
    "bounded_cache_growth": (
        "candidate_execution_failed",
        "capacity_run_failed",
        "cache_size_limit_exceeded",
        "unreclaimed_entries_retained",
        "expired_entries_retained",
        "steady_state_write_amplification",
        "warm_start_rewrites_the_store",
        "reusable_entry_evicted",
        "unexpired_entry_discarded",
    ),
    "portable_cache_exchange": (
        "candidate_execution_failed",
        "handoff_scan_failed",
        "export_contract_incomplete",
        "export_not_deterministic",
        "unsupported_bundle_import_failed",
        "unsupported_bundle_accepted",
        "warm_bundle_not_accepted",
        "warm_import_not_reused",
        "warm_import_findings_wrong",
    ),
}


_PRIORITY: Mapping[str, tuple[str, ...]] = {
    "clean_scan_finding_equivalence": (
        "nightly_scan_failed",
        "stale_findings_reported",
        "findings_missing_after_change",
        "findings_differ_from_clean_scan",
    ),
    "fail_closed_cache_integrity": (
        "cache_failure_aborted_scan",
        "import_aborted_the_run",
        "damaged_entry_served",
        "import_poisoned_cache",
        "stale_bundle_served",
    ),
    "honest_cache_accounting": (
        "scan_run_failed",
        "report_contract_incomplete",
        "accounting_totals_inconsistent",
        "reuse_claim_contradicts_analysis",
        "cache_inventory_misreported",
    ),
    "bounded_cache_growth": (
        "capacity_run_failed",
        "cache_size_limit_exceeded",
        "unreclaimed_entries_retained",
        "expired_entries_retained",
        "steady_state_write_amplification",
        "warm_start_rewrites_the_store",
        "reusable_entry_evicted",
        "unexpired_entry_discarded",
    ),
    "portable_cache_exchange": (
        "handoff_scan_failed",
        "export_contract_incomplete",
        "export_not_deterministic",
        "warm_bundle_not_accepted",
        "warm_import_not_reused",
        "warm_import_findings_wrong",
        "unsupported_bundle_import_failed",
        "unsupported_bundle_accepted",
    ),
}

RUBRICS = RubricSet(
    failure_modes=FAILURE_MODES,
    priority=_PRIORITY,
    buckets=BUCKETS,
    analyse=evaluate_project,
)


def clean_scan_finding_equivalence(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def fail_closed_cache_integrity(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def honest_cache_accounting(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def bounded_cache_growth(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)


def portable_cache_exchange(artifact_dir: Path, context: Any) -> RubricResult:
    return RUBRICS.evaluate(artifact_dir, context)
