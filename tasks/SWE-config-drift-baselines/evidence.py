'Owner persona, belief, and Observation contexts for SWE-config-drift-baselines.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marek, the platform operator who reviews the estate's configuration. He reads "
    "the durable drift ledger and the detected queue his duty operator works down, "
    "the compliance numbers on the Monday dashboard, and what a replay of a "
    "recorded console run prints; he does not read the compliance service's code."
)

USER_BELIEF = (
    "I want a quarter in which I can say which of our environments are the way we "
    "declared them and be believed. In June somebody moved a service onto a "
    "hand-built image and we only found out when a rollback pulled that build back "
    "in front of customers. What I can see is the record ledger, its detected queue, "
    "the number against each environment on the Monday dashboard, and what a replay "
    "of a recorded run prints. My duty operator opens that list at seven every "
    "morning and the review reads those numbers on Monday, and both of them gave up "
    "on the last thing we had. Done, for me, is a quarter where the detected queue is "
    "not made noisier and the Monday number is not made worse merely because the "
    "collector was silent about one setting, where the detected queue is "
    "short enough that somebody actually works it down, where a ledger row she "
    "looked at on Monday is still the same row on Tuesday, and where two Mondays of "
    "numbers are comparable enough that I can put the chart back up."
)

OBSERVATION_SCENE = (
    "The platform operator's review of a recorded estate run"
)


DID_NOT_RUN = observation(
    first=(
        "One nightly estate rehearsal stopped before its review completed, so I "
        "cannot treat that run as evidence about the ledger or its numbers."
    ),
    second=(
        "The console line from the stopped rehearsal is: {error}. That run needs "
        "to finish before its result can be reviewed."
    ),
    detail="{error}",
)

DUPLICATE_CONDITION_RECORDS = observation(
    first=(
        "The ledger contains more than one non-resolved record for the same baseline "
        "condition."
    ),
    second=(
        "For {condition} on `{service}` in {environment}, the ledger contains "
        "{open_records} non-resolved records after {nights} scanned nights."
    ),
    detail="{open_records}",
)

RECORD_REFERENCE_CHANGED = observation(
    first=(
        "A continuing condition appears under a different ledger record id from "
        "the one established on its earlier nights."
    ),
    second=(
        "For {condition} on `{service}` in {environment}, the record id changed "
        "from `{previous_id}` to `{current_id}` on {on}; its first-seen night is "
        "{first_seen}."
    ),
    detail="{current_id}",
)

RESOLVED_RECORD_REUSED = observation(
    first=(
        "A condition that cleared and later returned is attached to its earlier "
        "ledger record instead of a new incident."
    ),
    second=(
        "For {condition} on `{service}` in {environment}, record `{record_id}` "
        "belongs to an earlier incident but is open again on {on}."
    ),
    detail="{record_id}",
)

IDENTITY_DATE_MISMATCH = observation(
    first=(
        "A continuing condition does not retain the first-seen date established by "
        "its baseline's earlier nights."
    ),
    second=(
        "For {condition} on `{service}` in {environment}, the condition began on "
        "{first_seen}, while the current ledger record is dated {latest_seen}."
    ),
    detail="{latest_seen}",
)

RECORD_SEVERITY_MISMATCH = observation(
    first=(
        "A ledger record's severity does not agree with the estate severity table "
        "for its condition."
    ),
    second=(
        "For {condition} on `{service}` in {environment} on {on}, the ledger says "
        "{written_severity} and the estate table says {expected_severity}."
    ),
    detail="{written_severity}",
)

MISSING_CONDITION_RECORD = observation(
    first=(
        "A condition found by the active baseline comparison has no corresponding "
        "record in the ledger."
    ),
    second=(
        "On {on}, the missing record is {missing_type} for {condition} on "
        "`{service}` in {environment}."
    ),
    detail="{missing_type}",
)

SPURIOUS_CONDITION_RECORD = observation(
    first=(
        "The ledger contains a newly written condition that the canonical baseline "
        "comparison did not find on that night."
    ),
    second=(
        "The first such record on {on} is {condition} on `{service}` in "
        "{environment}. Compare that ledger row with the declaration and scan."
    ),
    detail="{condition}",
)

STORED_VALUE_PAIR_MISMATCH = observation(
    first=(
        "A standing ledger record's stored expected/actual pair does not agree with "
        "the current canonical comparison."
    ),
    second=(
        "The first pair to inspect is {condition} on `{service}` in {environment} "
        "on {on}. Its stored actual is `{written}` and the current canonical actual "
        "is `{canonical}`; compare both sides of the row with that scan."
    ),
    detail="{condition}",
)

RESOLUTION_STATE_MISMATCH = observation(
    first=(
        "A condition's resolution account does not agree with the "
        "nights on which that condition was present."
    ),
    second=(
        "The first lifecycle mismatch is {condition} on `{service}` in "
        "{environment} at {on}. Compare its ledger history with the condition in "
        "the nightly replay."
    ),
    detail="{on}",
)

TRIAGE_STATE_MISMATCH = observation(
    first=(
        "A decision made by the duty operator does not reconcile with the later "
        "non-resolved records for that condition."
    ),
    second=(
        "For {condition} on `{service}` in {environment}, the operator set "
        "{decision}; on {on} the ledger contains {open_rows} non-resolved records "
        "for that condition."
    ),
    detail="{decision}",
)

SNAPSHOT_MISSING = observation(
    first=(
        "A completed scan with an active baseline did not return a record-shaped "
        "nightly snapshot. The omission I am reporting concerns that snapshot."
    ),
    second=(
        "The missing snapshot is for {environment} on {on}, whose active baseline "
        "declares {services_in_baseline} services. The omission I am reporting "
        "concerns that snapshot."
    ),
    detail="{on}",
)

MISSING_SERVICE_COUNT_MISMATCH = observation(
    first=(
        "The nightly snapshot's missing-service count does not agree with the "
        "services absent from that scan. The discrepancy I am reporting concerns "
        "that snapshot counter."
    ),
    second=(
        "The first absent service to trace is `{service}` in {environment} on {on}. "
        "Compare the snapshot with the declaration and scan in the replay. "
        "The discrepancy I am reporting concerns that snapshot counter."
    ),
    detail="{service}",
)

BASELINE_POPULATION_MISMATCH = observation(
    first=(
        "The service population used by one nightly snapshot does not agree with "
        "the active baseline's population. The discrepancy I am reporting "
        "concerns that snapshot's total-service count."
    ),
    second=(
        "For {environment} on {on}, the snapshot counts {counted} total services "
        "while the active baseline declares {services_in_baseline}. The discrepancy "
        "I am reporting concerns that snapshot's total-service count."
    ),
    detail="{counted}",
)

SERVICE_COUNTER_MISMATCH = observation(
    first=(
        "One service-classification counter in a nightly snapshot does not agree "
        "with the active baseline comparison. The discrepancy I am reporting "
        "concerns that snapshot counter."
    ),
    second=(
        "For {environment} on {on}, the {counter} count is {counted}; the declaration "
        "and scan make it {expected_count}. The discrepancy I am reporting "
        "concerns that snapshot counter."
    ),
    detail="{counter}",
)

SEVERITY_COUNTER_MISMATCH = observation(
    first=(
        "One severity counter in a nightly snapshot does not agree with the current "
        "conditions found against the active baseline. The discrepancy I am "
        "reporting concerns that snapshot's severity counter."
    ),
    second=(
        "For {environment} on {on}, the {level} count is {counted}; the current "
        "conditions make it {rows_written}. The discrepancy I am reporting "
        "concerns that snapshot's severity counter."
    ),
    detail="{level}",
)

SCORE_MISMATCH = observation(
    first=(
        "A nightly compliance score does not agree with the score produced from the "
        "snapshot's service counts. The discrepancy I am reporting concerns "
        "that snapshot's compliance score."
    ),
    second=(
        "For {environment} on {on}, the recorded score is {recorded_score} and the "
        "reference calculation gives {expected_score}. The discrepancy I am "
        "reporting concerns that snapshot's compliance score."
    ),
    detail="{recorded_score}",
)

UNBASELINED_SCAN_LEFT_OUTPUT = observation(
    first=(
        "A scan with no active baseline left persisted estate state where the "
        "estate contract calls for a clean refusal."
    ),
    second=(
        "The first such scan is {environment} on {on}; the output available there "
        "carries a score of {recorded_score}."
    ),
    detail="{recorded_score}",
)

UNBASELINED_SCAN_NOT_REFUSED = observation(
    first=(
        "A scan with no active baseline stopped as an ordinary console error "
        "instead of the estate's clean refusal."
    ),
    second=(
        "The unbaselined scan is {environment} on {on}; the console reported "
        "`{error}` instead of the estate's no-active-baseline refusal."
    ),
    detail="{error}",
)

ACTIVE_BASELINE_COUNT_MISMATCH = observation(
    first=(
        "After a baseline capture or activation, the environment does not have "
        "exactly one declaration in force."
    ),
    second=(
        "For {environment} on {on}, the console lists {active_count} active "
        "declarations."
    ),
    detail="{active_count}",
)

DELETED_BASELINE_RESIDUE = observation(
    first=(
        "Deleting a baseline left state belonging to that baseline visible in the "
        "estate."
    ),
    second=(
        "After the deletion in {environment} on {on}, {orphan_rows} ledger records "
        "and {orphan_snapshots} snapshots still belong to the deleted baseline."
    ),
    detail="{orphan_rows}",
)

DELETE_DAMAGED_OTHER_STATE = observation(
    first=(
        "Deleting one baseline also removed estate state belonging elsewhere."
    ),
    second=(
        "At the deletion in {environment} on {on}, {lost_rows} other ledger records "
        "and {lost_snapshots} other snapshots disappear."
    ),
    detail="{lost_rows}",
)


OBSERVATIONS = {
    "drift_record_identity": {
        "candidate_execution_failed": DID_NOT_RUN,
        "duplicate_open_records": DUPLICATE_CONDITION_RECORDS,
        "record_reference_changed": RECORD_REFERENCE_CHANGED,
        "resolved_record_reused": RESOLVED_RECORD_REUSED,
        "record_identity_reset": IDENTITY_DATE_MISMATCH,
        "record_reopened_after_redeclaration": IDENTITY_DATE_MISMATCH,
        "record_severity_disagrees": RECORD_SEVERITY_MISMATCH,
        "change_not_on_the_list": MISSING_CONDITION_RECORD,
    },
    "observed_config_normalisation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "unchanged_field_reported": SPURIOUS_CONDITION_RECORD,
        "absent_field_reported": SPURIOUS_CONDITION_RECORD,
        "stored_values_not_canonical": STORED_VALUE_PAIR_MISMATCH,
    },
    "drift_lifecycle": {
        "candidate_execution_failed": DID_NOT_RUN,
        "cleared_drift_not_resolved": RESOLUTION_STATE_MISMATCH,
        "resolved_while_still_true": RESOLUTION_STATE_MISMATCH,
        "triage_decision_dropped": TRIAGE_STATE_MISMATCH,
        "triage_decision_reopened": TRIAGE_STATE_MISMATCH,
        "resolution_restamped": RESOLUTION_STATE_MISMATCH,
    },
    "compliance_accounting": {
        "candidate_execution_failed": DID_NOT_RUN,
        "nightly_number_missing": SNAPSHOT_MISSING,
        "missing_service_uncounted": MISSING_SERVICE_COUNT_MISMATCH,
        "population_not_the_baseline": BASELINE_POPULATION_MISMATCH,
        "service_counts_disagree": SERVICE_COUNTER_MISMATCH,
        "severity_counters_disagree": SEVERITY_COUNTER_MISMATCH,
        "score_off_the_reference": SCORE_MISMATCH,
    },
    "baseline_state_integrity": {
        "candidate_execution_failed": DID_NOT_RUN,
        "scan_without_a_baseline_not_refused": UNBASELINED_SCAN_NOT_REFUSED,
        "scan_without_a_baseline_scored": UNBASELINED_SCAN_LEFT_OUTPUT,
        "two_active_baselines": ACTIVE_BASELINE_COUNT_MISMATCH,
        "deleted_baseline_left_records": DELETED_BASELINE_RESIDUE,
        "delete_removed_other_records": DELETE_DAMAGED_OTHER_STATE,
    },
}
