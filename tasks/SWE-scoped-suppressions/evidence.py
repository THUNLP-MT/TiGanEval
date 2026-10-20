'Owner persona, belief, and factual Observation contexts for this task.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rota, the security champion who runs the estate's policy review. She reads "
    "the weekly open list the platform teams work from, the reconciliation sheet "
    "the review signs off each quarter, and what a replay of a recorded review "
    "prints; she does not read the audit's code."
)

USER_BELIEF = (
    "I want a quarter in which an accepted finding is one somebody actually "
    "accepted, in writing, and nothing else has gone quiet alongside it. "
    "Reviewers accept a finding by writing a comment next to it, and on the "
    "payments gateway that meant eleven identical comments in a row that nobody "
    "in the room could check. What I can see is the weekly open list, the sheet "
    "the review signs off each quarter, and what the run prints when I replay a "
    "recorded review. The platform teams read the list too, and they push back "
    "on it. Done, for me, is a quarter in which nobody finds a real finding "
    "sitting under a waiver that was never argued for, the teams stop writing to "
    "ask why the things they waived are still on the list, and the review can "
    "close its numbers document by document without arguing about arithmetic."
)

OBSERVATION_SCENE = "The weekly estate review of open policy findings"


DID_NOT_RUN = observation(
    first=(
        "The measured estate review ended before it returned a complete result, "
        "so this run cannot be reviewed as complete."
    ),
    second="The measured estate review ended with: {error}.",
    detail="{error}",
)

EXPECTED_OPEN_MISSING = observation(
    first="A finding expected in the weekly open list is absent from the report.",
    second=(
        "In {document} under {profile}, {rule_name} at line {line} in {entry} "
        "is absent although the review expects it to remain open."
    ),
    detail="{entry}",
)

EXPECTED_WAIVER_STILL_OPEN = observation(
    first="A finding expected to be waived is still present in the weekly report.",
    second=(
        "In {document} under {profile}, {rule_name} at line {line} in {entry} "
        "is present although the review expects it to be waived."
    ),
    detail="{entry}",
)

LAYOUT_COUNTS_DIFFER = observation(
    first=(
        "Two exports of the same policy produce different open occurrence counts "
        "for one entry and rule."
    ),
    second=(
        "For {rule_name} in {entry}, {document} reports {document_count} open "
        "occurrence(s) and {other_document} reports {other_count}."
    ),
    detail="{other_document}",
)

REPORT_FILTER_MISMATCH = observation(
    first="A weekly report differs from the review record for one finding.",
    second=(
        "In {document}, {rule_name} at line {line} in {entry} occurs "
        "{actual_count} time(s) in the report; the review record expects "
        "{expected_count}."
    ),
    detail="{entry}",
)

TOTALS_MISMATCH = observation(
    first="A document's three report counters do not add up to its baseline total.",
    second=(
        "For {document}, baseline is {baseline_total}; reported {open_count}, "
        "blanket {blanket}, and by-rule {by_rule} add up to {counted_total}."
    ),
    detail="{counted_total}",
)

BLANKET_SPLIT_MISMATCH = observation(
    first="A document's blanket-waiver count is lower than the review record.",
    second=(
        "For {document}, blanket is {blanket} rather than {expected_blanket}; "
        "the build reports {by_rule} by-rule waivers."
    ),
    detail="{expected_blanket}",
)

REPORTED_COUNT_MISMATCH = observation(
    first="A report's `reported` counter differs from the number of listed findings.",
    second=(
        "For {document}, the `reported` counter is {open_count} and the list "
        "contains {listed} findings."
    ),
    detail="{listed}",
)

COUNTER_SPLIT_MISMATCH = observation(
    first="A report's three counters differ from the review record.",
    second=(
        "For {document}, the build reports ({open_count}, {blanket}, {by_rule}); "
        "the review record expects ({expected_open}, {expected_blanket}, "
        "{expected_by_rule})."
    ),
    detail="{document}",
)

AUDIT_MISSING_FINDING = observation(
    first="An ignore-waivers run omits findings from the detector baseline.",
    second=(
        "For {document}, the detector baseline contains {baseline_total} findings "
        "and the ignore-waivers report contains {open_count}; {missing} baseline "
        "finding(s) are absent. The first missing one is {rule_name} at line "
        "{line} in {entry}."
    ),
    detail="{missing}",
)

REPORT_SEQUENCE_DIVERGED = observation(
    first=(
        "A report's finding sequence cannot be reconciled with the detector's "
        "required order."
    ),
    second=(
        "In {document}, report position {position} cannot be reconciled with "
        "the detector order; its item is {rule_name}, unit {unit}, line {line}, "
        "path {path}, value {value}."
    ),
    detail="{position}",
)


OBSERVATIONS = {
    "unit_scope_coverage": {
        "candidate_execution_failed": DID_NOT_RUN,
        "waiver_covered_a_second_unit": EXPECTED_OPEN_MISSING,
        "waiver_missed_its_unit": EXPECTED_WAIVER_STILL_OPEN,
        "waiver_covered_part_of_its_unit": EXPECTED_WAIVER_STILL_OPEN,
        "coverage_changed_with_layout": LAYOUT_COUNTS_DIFFER,
        "report_filter_disagreed": REPORT_FILTER_MISMATCH,
    },
    "region_extent": {
        "candidate_execution_failed": DID_NOT_RUN,
        "region_outlived_its_block": EXPECTED_OPEN_MISSING,
        "region_did_not_cover_its_block": EXPECTED_WAIVER_STILL_OPEN,
        "nested_end_cleared_the_outer_waiver": EXPECTED_WAIVER_STILL_OPEN,
        "file_wide_region_stopped_early": EXPECTED_WAIVER_STILL_OPEN,
        "unmatched_end_started_region": EXPECTED_OPEN_MISSING,
    },
    "selector_resolution": {
        "candidate_execution_failed": DID_NOT_RUN,
        "unknown_selector_waived_the_unit": EXPECTED_OPEN_MISSING,
        "disabled_selector_waived_the_unit": EXPECTED_OPEN_MISSING,
        "named_selector_waived_another_rule": EXPECTED_OPEN_MISSING,
        "resolvable_selector_waived_nothing": EXPECTED_WAIVER_STILL_OPEN,
    },
    "suppression_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "counts_do_not_sum": TOTALS_MISMATCH,
        "blanket_booked_as_specific": BLANKET_SPLIT_MISMATCH,
        "reported_count_disagrees": REPORTED_COUNT_MISMATCH,
        "counter_split_disagreed": COUNTER_SPLIT_MISMATCH,
    },
    "audit_run_equality": {
        "candidate_execution_failed": DID_NOT_RUN,
        "audit_hid_findings": AUDIT_MISSING_FINDING,
        "report_altered_a_finding": REPORT_SEQUENCE_DIVERGED,
    },
}
