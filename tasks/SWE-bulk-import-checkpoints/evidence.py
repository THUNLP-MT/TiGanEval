'The owner of the nightly catalogue load, and what she reports seeing.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Priya, who runs the data platform team and owns the nightly catalogue "
    "load; she reads the scheduler's log, the replays of a recorded night, "
    "and the warehouse row counts, and does not work in the loader's code."
)

USER_BELIEF = """I want the nightly catalogue load to be a job nobody babysits. It has to get the export into the warehouse and finish on its own, and when it dies at three in the morning the restart should carry on from where it got to instead of loading the whole export again at nine. I have been treating the scheduler's file choice as enough context for a restart, so I think the checkpoint itself only needs to mean a row number. When it is done, the catalogue that merchandising and the pricing feed read has to be what the export says: nothing upstream sent missing, nothing in there that the export does not say, nothing reading differently from the export. The warehouse team also want their load window back, so we cannot hold the whole export open in one transaction any more. Done is a week of nights where nobody is paged and the morning reports are right."""

OBSERVATION_SCENE = "Nightly catalogue load review"


_DID_NOT_RUN = observation(
    first=(
        "The replay of last night's load produced no usable run timeline, so "
        "the scheduler has no report it can act on and I cannot verify from "
        "that run whether the catalogue finished."
    ),
    second=(
        "I replayed the night myself with your loader in the tree and there "
        "is no usable run timeline in it, just `{error}`. Whatever happened "
        "inside that process, the replay gives the scheduler no report and "
        "gives me no run record to reconcile with the warehouse."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "exactly_once_import_completion": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "run_raised_the_feed_error": observation(
            first=(
                "One attempt ended by handing a source-interruption error to "
                "the scheduler instead of returning a report. The scheduler "
                "treats that as a crashed job, so it cannot use the run's "
                "result to arrange the next attempt."
            ),
            second=(
                "I replayed that night against your loader and read the log "
                "for the {label} run: it comes back with `{error}` and no "
                "report behind it, so the scheduler has nothing to restart "
                "from and the night stops there."
            ),
            detail="{error}",
        ),
        "run_raised_the_warehouse_error": observation(
            first=(
                "One attempt ended by handing a storage-failure error to the "
                "scheduler instead of returning a report. Whether it happened "
                "while loading rows or while finishing the run, the scheduler "
                "only sees a crashed job and has no interrupted report to act on."
            ),
            second=(
                "I ran that night through again with your loader in the tree: "
                "the {label} run ends with `{error}` "
                "and hands the scheduler no report, so it pages on-call "
                "instead of queueing another attempt."
            ),
            detail="{error}",
        ),
        "run_raised_its_own_error": observation(
            first=(
                "One of last night's attempts came back with no report and an "
                "error other than the source interruption or storage failure "
                "the scheduler knows how to route. From that log alone I cannot "
                "tell which stage of the load had been reached."
            ),
            second=(
                "I went back and replayed that night after your change: the "
                "{label} run returns no report, and what is logged beside it "
                "is `{error}`. It is not one of the two substrate failures the "
                "run is expected to turn into an interrupted report, and the "
                "scheduler receives no report it can act on."
            ),
            detail="{error}",
        ),
        "import_did_not_complete": observation(
            first=(
                "A fault-free attempt that should have closed its part of the "
                "night returned a report without saying the export was "
                "complete. The scheduler therefore cannot treat that attempt "
                "as the end of the load."
            ),
            second=(
                "I put the night through again on your build and read the "
                "{label} attempt: it comes back reporting `{status}` "
                "rather than a finish, so the schedule sends it round again. It "
                "only stops for the night when a run tells it the export is "
                "loaded."
            ),
            detail="{status}",
        ),
        "rows_missing_after_resume": observation(
            first=(
                "I checked the catalogue left by the restarted night against "
                "its export and rows that the export admits are absent. Any "
                "missing product or variant is then absent from what "
                "merchandising and pricing read in the morning."
            ),
            second=(
                "I ran last night's sequence again on your build and counted "
                "the catalogue afterwards: the export admits "
                "{rows_the_export_admits} rows, the table is holding "
                "{rows_in_the_catalogue}, and rows the export admits are "
                "simply not among them. A night with a restart in it still "
                "loses part of the export."
            ),
            detail="{rows_in_the_catalogue}",
        ),
        "rows_duplicated_after_resume": observation(
            first=(
                "A buyer brought me a listing on the site that our export "
                "does not put in the catalogue. The row is sitting in the "
                "table and it is not one of the rows that export gives us, so "
                "there is nothing to reconcile it against. Merchandising "
                "price off that table and they are the ones who take the "
                "complaint."
            ),
            second=(
                "I ran the night again with your loader in the tree and "
                "counted the catalogue against the export: the export admits "
                "{rows_the_export_admits} rows and the table is holding "
                "{rows_in_the_catalogue}. The extra ones are on no list the "
                "export gives us, and everything downstream reads that table."
            ),
            detail="{rows_in_the_catalogue}",
        ),
        "rows_incorrect_after_resume": observation(
            first=(
                "The restarted night left all the expected identifiers in the "
                "catalogue, but at least one stored row does not read the way "
                "the export gives it. Downstream therefore sees catalogue data "
                "that upstream did not publish."
            ),
            second=(
                "I replayed the night on your build and went through the "
                "catalogue against the export line by line: all "
                "{rows_the_export_admits} rows the export admits are in "
                "there, and some of them read differently from the way the "
                "export has them. A finished load has to leave every row "
                "reading the way the export sends it."
            ),
            detail="{rows_the_export_admits}",
        ),
    },
    "invalid_row_rejection_integrity": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "invariant_violated_in_committed_state": observation(
            first=(
                "The replay found a committed point in the load where the "
                "catalogue breaks its own row rules. The warehouse is live "
                "between our commits, so merchandising or pricing can read "
                "that invalid state before a later transaction changes it."
            ),
            second=(
                "I ran that export through again on your build and read what "
                "the replay lists for each commit under "
                "`invariant_violations_in_committed_snapshots`: the {label} "
                "run leaves a state the rules refuse on "
                "{commits_with_violations} of its commits. Anything reading "
                "the catalogue in between sees that state."
            ),
            detail="{commits_with_violations}",
        ),
        "invalid_row_not_reported": observation(
            first=(
                "Upstream's correction list for last night is incomplete. "
                "Some source positions the catalogue rules refused are absent "
                "from the combined rejected entries, so they cannot open the "
                "correction work for those positions."
            ),
            second=(
                "I combined the reports for `{night}` and counted their rejected "
                "positions against the export rules: the rules refuse "
                "{rejections_the_rules_give} rows of that export and the reports account for "
                "{rejections_the_report_gets_right} of them. Upstream needs "
                "every row we would not take listed once, with the reason the "
                "rules give that row."
            ),
            detail="{rejections_the_rules_give}",
        ),
        "rejection_reason_incorrect": observation(
            first=(
                "Upstream came back annoyed this morning: our report told "
                "them a row was refused for something the rules do not say "
                "about that row. The row may have another defect or may be "
                "admissible, but the reason we sent cannot tell them what to "
                "correct."
            ),
            second=(
                "I checked the report your build hands back against the rules "
                "row by row: the rules refuse {rejections_the_rules_give} "
                "rows of that export, and {rejections_the_rules_do_not_give} "
                "of the refusals the report names are not among them. Each "
                "one has to name a row the rules really do refuse, with the "
                "reason they give it."
            ),
            detail="{rejections_the_rules_do_not_give}",
        ),
        "invalid_row_reported_more_than_once": observation(
            first=(
                "The support thread for one night's export lists the same "
                "rejected source position more than once. Upstream treats each "
                "entry as work to do, so repeated entries create duplicate "
                "investigation for one bad row."
            ),
            second=(
                "I combined the reports from the {night} runs and compared "
                "their source positions: {rejections_reported_more_than_once} "
                "rejected rows occur more than once, adding "
                "{duplicate_rejection_occurrences} duplicate report entries. "
                "Each inadmissible position belongs in that night's reports "
                "once with its own reason."
            ),
            detail="{duplicate_rejection_occurrences}",
        ),
    },
    "resume_state_integrity": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "progress_not_checkpointed": observation(
            first=(
                "When the source stopped, the warehouse did not yet contain "
                "enough of the prefix that the export was about to stop "
                "retaining. A restart cannot recover that gap from the retained "
                "stream alone."
            ),
            second=(
                "I replayed the interrupted night on your build: when the "
                "feed cut out the export still held everything from row "
                "{retention_boundary_row} onward, and the {label} run had "
                "{committed_rows} rows durable behind it. The first "
                "{retention_boundary_row} rows of that export admit "
                "{durable_rows_required} rows into the catalogue, so a restart "
                "picking up there needs those {durable_rows_required} committed "
                "already; the rows in between cannot be read again by anything."
            ),
            detail="{committed_rows}",
        ),
        "foreign_source_changed_state": observation(
            first=(
                "A run handed an export that did not match the recorded "
                "progress still changed durable warehouse state. Declining the "
                "job is not safe once the store handed to later runs no longer "
                "matches the state this run received."
            ),
            second=(
                "I re-ran that mix-up with your loader in the tree: the {label} "
                "run handed `{export}` changed "
                "{durable_state_changes} durable entries before returning "
                "`{status}` — {catalogue_rows_changed} catalogue rows and "
                "{metadata_entries_changed} metadata entries. A foreign export "
                "has to leave both parts of the store exactly as it found them."
            ),
            detail="{durable_state_changes}",
        ),
        "foreign_source_returned_no_report": observation(
            first=(
                "A run handed an export that did not match the recorded "
                "progress returned no report. The scheduler therefore cannot "
                "record the job as mis-pointed or distinguish it from a crash."
            ),
            second=(
                "I replayed the {label} run with `{export}` and it returned no "
                "report; the scheduler logged `{error}` instead. It needs an "
                "explicit refusal before it can close the mis-pointed job."
            ),
            detail="{error}",
        ),
        "foreign_source_not_refused": observation(
            first=(
                "A run handed an export that did not match the recorded "
                "progress returned a report, but it did not decline the job. "
                "The scheduler therefore treats a mis-pointed export as part "
                "of the catalogue load."
            ),
            second=(
                "I replayed the {label} run with `{export}` and the scheduler "
                "received `{status}` rather than `refused`. Recorded progress "
                "from one export cannot be continued under another export's "
                "identity."
            ),
            detail="{status}",
        ),
        "committed_work_repeated": observation(
            first=(
                "The warehouse team brought me the write volume for the "
                "nights we had restarts: the runs leading to a finish wrote "
                "more rows than the published restart allowance. Their window "
                "is sized for one pass plus the interrupted batch from each "
                "stopped run."
            ),
            second=(
                "I added up what the runs before the finish wrote, from the "
                "replay of that night on your build: "
                "{rows_written_before_completion} rows written into a "
                "catalogue the export fills with {rows_the_export_admits}, "
                "where the window allows {allowance} counting the batch each "
                "restart was in the middle of when it died."
            ),
            detail="{rows_written_before_completion}",
        ),
    },
    "bounded_transaction_work": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "durable_state_changed_without_transaction": observation(
            first=(
                "The warehouse ledger changed even though its transaction log "
                "has no matching committed change. That bypasses the write-lock "
                "window and the rollback boundary the warehouse relies on."
            ),
            second=(
                "I replayed the {label} run and compared the durable store with "
                "the transaction log: {durable_entries_changed_without_transaction} "
                "entries changed without a matching commit — "
                "{catalogue_rows_changed_without_transaction} catalogue rows and "
                "{metadata_entries_changed_without_transaction} metadata entries. "
                "Durable changes have to go through the transaction interface."
            ),
            detail="{durable_entries_changed_without_transaction}",
        ),
        "source_buffered_before_first_commit": observation(
            first=(
                "The load read beyond the warehouse team's first-checkpoint "
                "boundary before making any part of the export durable. That "
                "leaves too much source work exposed to one interruption and "
                "breaks the published load envelope."
            ),
            second=(
                "I watched the run through again on your loader: the {label} "
                "run had read {rows_read_at_first_commit} rows of the "
                "{rows_in_the_export}-row export before any of it was durable, "
                "and we settled on committing every 25."
            ),
            detail="{rows_read_at_first_commit}",
        ),
        "transaction_batch_too_large": observation(
            first=(
                "The warehouse team came to me with the lock trace from last "
                "night. One of our transactions held the write lock long "
                "enough for their morning reports to pile up behind it, and "
                "they want the load out of that window."
            ),
            second=(
                "I took the biggest transaction out of the lock trace on your "
                "build: the {label} run changes {rows_in_largest_transaction} "
                "rows in one of them, where the warehouse team allows 25, so "
                "the reports sit behind our lock for the same stretch as "
                "before."
            ),
            detail="{rows_in_largest_transaction}",
        ),
        "transaction_count_exceeded": observation(
            first=(
                "The warehouse team's transaction count for one run is above "
                "the allowance they publish for an export of that size. The "
                "cluster bills this job per transaction, so the excess is "
                "visible even when the final catalogue is correct."
            ),
            second=(
                "I counted the transactions one run opens on your build: the "
                "{label} run opens {transactions_opened} of them, where the "
                "warehouse team allows {transaction_allowance} for an export "
                "that size, one per batch of 25 plus four for the run's own "
                "bookkeeping and the odd retry."
            ),
            detail="{transactions_opened}",
        ),
    },
    "clean_idempotent_completion": {
        "candidate_execution_failed": _DID_NOT_RUN,
        "next_export_did_not_complete": observation(
            first=(
                "The run handed the next night's export did not report that it "
                "completed, even though no feed or storage fault was injected. "
                "The scheduler therefore cannot close that night's load."
            ),
            second=(
                "I replayed the {label} run over `{export}` and it returned "
                "`{status}` instead of `completed`. A new nightly export has to "
                "finish on the same warehouse the prior night left behind."
            ),
            detail="{status}",
        ),
        "next_export_rows_missing": observation(
            first=(
                "The catalogue left by the next night's complete export is "
                "missing rows that export admits. From the missing count alone "
                "I cannot tell whether they were newly published rows or rows "
                "that should have remained from the prior night."
            ),
            second=(
                "I ran those nights through again on your build and counted the "
                "catalogue after the last one: the run handed the new export "
                "comes back `{status}` and the catalogue is holding "
                "{rows_in_the_catalogue} rows where that export admits "
                "{rows_the_new_export_admits}, with "
                "{rows_missing_from_the_catalogue} admitted rows absent. "
                "Upstream publishes a new file "
                "most nights, under the same name as the night before, and it "
                "has to land on the catalogue the finished nights left behind."
            ),
            detail="{rows_missing_from_the_catalogue}",
        ),
        "next_export_rows_unexpected": observation(
            first=(
                "After the next night's export completed, the catalogue still "
                "contained rows that the export does not give us. Everything "
                "downstream reads that table as the current catalogue."
            ),
            second=(
                "I compared the catalogue after the {label} run with its full "
                "export and found {rows_unexpected_in_the_catalogue} rows that "
                "the export does not contain. A completed night cannot leave "
                "rows of its own outside the published catalogue."
            ),
            detail="{rows_unexpected_in_the_catalogue}",
        ),
        "next_export_rows_incorrect": observation(
            first=(
                "After the next night's export completed, the expected row "
                "identifiers were present but some stored values differed from "
                "the export. The warehouse therefore was not the catalogue "
                "upstream published for that night."
            ),
            second=(
                "I compared the {label} run's catalogue with the full export: "
                "{rows_incorrect_in_the_catalogue} rows have the right identity "
                "but different stored values. Loading onto yesterday's warehouse "
                "must not change what today's export says."
            ),
            detail="{rows_incorrect_in_the_catalogue}",
        ),
        "import_bookkeeping_retained": observation(
            first=(
                "A run told the scheduler its export was complete, but the "
                "night-close handoff was held for review because the shared "
                "metadata no longer matched the snapshot from the start of "
                "that night."
            ),
            second=(
                "I checked the handoff after your {label} run came back saying "
                "it had finished. It is `{handoff_status}`, and "
                "`{bookkeeping_key_left_behind}` is one of the metadata entries "
                "that differs from the start-of-night snapshot. Interrupted "
                "attempts can carry progress within a night; a completed one "
                "has to hand the shared metadata back as it received it."
            ),
            detail="{bookkeeping_key_left_behind}",
        ),
        "completion_metadata_not_restored": observation(
            first=(
                "A run told the scheduler its export was complete, but the "
                "night-close handoff was held because metadata that belonged "
                "to the store before the load no longer matched."
            ),
            second=(
                "I checked the handoff after your {label} run. It is "
                "`{handoff_status}` because the pre-existing metadata entry "
                "`{metadata_key_not_restored}` was {metadata_change_kind} "
                "during the night. Completing the catalogue load cannot alter "
                "the scheduler's state around it."
            ),
            detail="{metadata_key_not_restored}",
        ),
        "repeat_import_did_not_complete": observation(
            first=(
                "Upstream published nothing new, so the schedule loaded the "
                "same export again, and the run came back saying it was not "
                "finished. The schedule kept retrying a job that had nothing "
                "to do and the six o'clock reports waited on it."
            ),
            second=(
                "I ran that night again on your build: the scheduled-rerun of "
                "an export that is already in the warehouse still does not "
                "report `completed`, the scheduler gets `{status}`, so the "
                "schedule cannot tell that there is nothing left for it to "
                "do."
            ),
            detail="{status}",
        ),
        "repeat_import_rewrote_database": observation(
            first=(
                "Upstream published nothing new and the schedule loaded the "
                "same export a second time, and the catalogue came out "
                "different afterwards. Nothing upstream had changed, so the "
                "second run had no catalogue difference to introduce."
            ),
            second=(
                "I loaded the same export twice through your loader and "
                "compared the warehouse before and after the second run: the "
                "table does not read the same afterwards, with "
                "{catalogue_differences_after_repeat} rows missing, added, or "
                "changed. It held "
                "{rows_in_the_catalogue_before} rows going into that run and "
                "{rows_in_the_catalogue_after} coming out, against an export "
                "that admits {rows_the_export_admits}. A night that loads an "
                "export already in the warehouse has to leave the catalogue "
                "exactly as it found it."
            ),
            detail="{catalogue_differences_after_repeat}",
        ),
    },
}
