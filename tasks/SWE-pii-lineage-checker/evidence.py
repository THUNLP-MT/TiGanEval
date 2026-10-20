'Owner persona, belief, and Observation contexts for SWE-pii-lineage-checker.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rhea, the security engineer who owns the lineage audit; she reads the audit "
    "report, the release gate and what the privacy office and the pipeline teams "
    "send back to her, not the checker's code."
)

USER_BELIEF = """The privacy office ran their own pass over the record pipeline on Tuesday and found an export we ship every night that hands out a subject's email address. Ours had nothing on it, and three teams have been reading a clean report from us as proof that their steps are fine.

What I want is an audit that follows the field itself, out of the record, through whatever the step builds with it, into the calls that put data outside the company, so that when the office comes back in six weeks they find nothing we missed. The rows they signed off last quarter have to survive it: the release gate fails on those, and every team has already triaged them.

Done, for me, is the office's next pass finding nothing ours did not, and a pipeline team acting on a row instead of asking me whether they can trust it."""

OBSERVATION_SCENE = "Morning check of the lineage audit"


_NOTHING_RAN = observation(
    first=(
        "The audit did not get through the pipeline at all last night. There is no report "
        "and no gate result this morning, and the release train has been sitting since six "
        "with two teams waiting on it."
    ),
    second=(
        "I ran it myself on your build and it gives up before it has read the pipeline. The "
        "console holds one line where the report should be: {error}"
    ),
    detail="{error}",
)

_SCAN_STOPPED = observation(
    first=(
        "The audit stopped part way through last night's pipeline, so the gate had a report "
        "covering some of the modules and nothing at all for the rest. Nobody could tell me "
        "which teams the missing part belonged to."
    ),
    second=(
        "Ran the pipeline through your build again: it stops at the same scan, {label}, and "
        "this is what the console has for it: {error}"
    ),
    detail="{label}",
)


OBSERVATIONS = {
    "flow_matches_the_field_rules": {
        "candidate_execution_failed": _NOTHING_RAN,
        "scan_step_failed": _SCAN_STOPPED,
        "leaking_export_missed": observation(
            first=(
                "The office re-read one of our step files by hand this week and found an "
                "export we ship that hands a personal field out of the company, with nothing "
                "from us anywhere near it. That is twice in a month they have found something "
                "in a file our report calls clean, and they have started re-reading the files "
                "themselves rather than taking ours."
            ),
            second=(
                "I went through {module} on your build with them: the export to {dataset} at "
                "line {line} sends a personal field out and no row of ours mentions it."
            ),
            detail="{dataset}",
        ),
        "clean_export_flagged": observation(
            first=(
                "A pipeline team spent a morning on a row of ours and found nothing wrong with "
                "the export: what goes out of it never had a personal field in it in the first "
                "place. They have asked to be taken off the audit, which is how a check like "
                "this dies."
            ),
            second=(
                "Checked it on your build myself: the row against {dataset} on {module} line "
                "{line} sits on an export that sends nothing personal."
            ),
            detail="{module}",
        ),
    },
    "one_row_per_leaking_export": {
        "candidate_execution_failed": _NOTHING_RAN,
        "scan_step_failed": _SCAN_STOPPED,
        "leaking_export_unreported": observation(
            first=(
                "The privacy queue is missing a row for an export that sends a personal "
                "field. The team responsible for that destination has no review to act on."
            ),
            second=(
                "Checked the report from your build against the export itself: {module} line "
                "{line} sends a personal field to {dataset}, but the queue has no row for it."
            ),
            detail="{dataset}",
        ),
        "export_flagged_twice": observation(
            first=(
                "The triage queue has the same export in it several times over and the team "
                "working it has spent the week closing copies of a row they had already "
                "answered. The number at the top of the report is what I send upward every "
                "Monday, and it is not a count of anything real."
            ),
            second=(
                "Counted the rows on your build: the export to {dataset} on {module} line "
                "{line} comes back {rows} times."
            ),
            detail="{rows}",
        ),
        "clean_export_reported": observation(
            first=(
                "A team was sent a row for an export that carries no personal field. They "
                "have stopped treating the queue as a list of work they actually need to do."
            ),
            second=(
                "Read the row and the export together on your build: {module} line {line} "
                "points to {dataset}, but nothing personal reaches that export."
            ),
            detail="{dataset}",
        ),
        "report_row_mislabels_export": observation(
            first=(
                "A reviewer followed a row to its destination and found that the report names "
                "a different table or channel from the export on that line. Their response is "
                "now attached to the wrong destination."
            ),
            second=(
                "Checked {module} line {line} on your build: the export names {dataset}, while "
                "the report row calls it {reported_dataset}."
            ),
            detail="{reported_dataset}",
        ),
        "report_row_is_not_an_export": observation(
            first=(
                "A reviewer opened a row of ours and could not match the check it names to an "
                "export at that location. Whatever they write against a row like that lands "
                "on work nobody can reconcile, and the row itself never gets closed."
            ),
            second=(
                "Opened the same row on your build: it points at {module} line {line} and names "
                "check {check}, but no export at that location is keyed under that check."
            ),
            detail="{check}",
        ),
    },
    "verdict_survives_step_extraction": {
        "candidate_execution_failed": _NOTHING_RAN,
        "scan_step_failed": _SCAN_STOPPED,
        "export_lost_when_the_step_moved": observation(
            first=(
                "The pipeline team split the case handler up last week and our report lost a "
                "row over it. Same program, same export, same field going out of it, and the "
                "audit changed its mind because somebody moved a few lines into a helper. I "
                "cannot gate a release on a check that a tidy-up disarms."
            ),
            second=(
                "Put the two shapes of the handler side by side on your build: {inline_label} "
                "flags the export to {dataset} and {extracted_label} says nothing about it."
            ),
            detail="{dataset}",
        ),
        "export_appeared_when_the_step_moved": observation(
            first=(
                "The report grew a row the week the case handler was split up, against an "
                "export nobody has touched since March. The team asked me what they had done "
                "wrong and all I could tell them was that the audit reads the two shapes of "
                "their code differently."
            ),
            second=(
                "Ran both shapes on your build: {extracted_label} flags the export to "
                "{dataset} where {inline_label} has nothing on it."
            ),
            detail="{dataset}",
        ),
    },
    "report_independent_of_scan_order": {
        "candidate_execution_failed": _NOTHING_RAN,
        "scan_step_failed": _SCAN_STOPPED,
        "finding_lost_in_one_order": observation(
            first=(
                "The same commit was audited twice yesterday, on the two build workers, and "
                "came back as two different reports. One of them was short a row the other "
                "had, so whether an export gets flagged now comes down to which worker "
                "happened to be free."
            ),
            second=(
                "Ran both workers again on your build: {other_label} has a row for {dataset} "
                "on {module} and {label} does not."
            ),
            detail="{dataset}",
        ),
        "rows_ordered_by_scan_order": observation(
            first=(
                "Every run of the audit comes back as a fresh diff against the last one, even "
                "on a commit nobody touched, because the rows turn up in a different order "
                "each time. The gate has become something people re-run until it looks "
                "familiar."
            ),
            second=(
                "Ran it twice on your build: the same {rows} rows come back both times, one "
                "run starting at {first_module} and the other at {other_first_module}."
            ),
            detail="{other_first_module}",
        ),
        "report_out_of_gate_order": observation(
            first=(
                "The gate would not take last night's report at all. It reads a report the "
                "one way it reads them and it stopped on the first row, so the release went "
                "out with no audit result against it and I found out from the office rather "
                "than from us."
            ),
            second=(
                "Put the report from your build through the gate myself: it gives up on the "
                "{rows} rows of the {label} scan before it has diffed one of them, and the "
                "line it prints is: {error}"
            ),
            detail="{error}",
        ),
    },
    "existing_audit_rows_unchanged": {
        "candidate_execution_failed": _NOTHING_RAN,
        "scan_step_failed": _SCAN_STOPPED,
        "existing_row_dropped": observation(
            first=(
                "The gate went red this morning on rows that have nothing to do with the new "
                "work: the audit came back with fewer of the office's own rows than it was "
                "handed. The release train is held, and the teams that triaged those rows last "
                "quarter want to know what happened to their sign-off."
            ),
            second=(
                "Ran the gate on your build: it keeps {kept} of the {expected} rows the office "
                "signed off, and the one on {module} line {line} against {dataset} is gone."
            ),
            detail="{kept}",
        ),
        "existing_row_changed": observation(
            first=(
                "One of the rows the office signed off came back attached to a different "
                "destination. The existing review no longer describes the row in this report."
            ),
            second=(
                "Checked the signed-off row on {module} line {line}: it names {dataset}, but "
                "your build returns it as {reported_dataset}."
            ),
            detail="{reported_dataset}",
        ),
        "unexpected_existing_row": observation(
            first=(
                "The gate went red the other way round: the audit reported one of the office's "
                "own checks against an export that was never on their list, so the diff reads "
                "as though our report and last quarter's are two different documents."
            ),
            second=(
                "Ran the gate on your build: it returns {kept} of those rows against the "
                "{expected} on the list, with one on {module} line {line} against {dataset} "
                "that the office never signed off."
            ),
            detail="{line}",
        ),
    },
}
