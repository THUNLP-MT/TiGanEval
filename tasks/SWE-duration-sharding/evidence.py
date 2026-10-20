'Owner persona, belief, and Observation contexts for SWE-duration-sharding.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marta, who runs CI for the platform team. She reads the run log, the shard "
    "timing board, the retry log and `duration-history.json`, and the tickets "
    "engineers open when a train misbehaves; she does not read the planner's code."
)

USER_BELIEF = (
    "I want release week to stop being a queue. We rent four machines for every "
    "run and then wait for whichever one drew the slow files, so a train that "
    "should take six minutes takes fifteen, and by Thursday afternoon people are "
    "sitting on finished work waiting for a train that started an hour ago. "
    "Finance has the four-machine bill and asks me every month what it bought. "
    "Done, for me, is a release week where the four machines come in within a "
    "few minutes of each other, where I can hold what a run was expected to cost "
    "against what it cost, and where a green train is something I can tell an "
    "engineer to trust."
)

OBSERVATION_SCENE = "The CI lead's morning look at the shard timing board and last night's runs"


DID_NOT_RUN = observation(
    first=(
        "I started a CI run with your planner and it stopped before the runner "
        "returned a complete result. This morning's board has no complete run I "
        "can review, so I cannot report what the change did to the platform team."
    ),
    second=(
        "I repeated the same CI review on the changed build and it still does not "
        "return a complete run result. The console ends with this line: {error}. "
        "Until the run completes I cannot judge anything else about it."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "whole_suite_assigned_once": {
        "candidate_execution_failed": DID_NOT_RUN,
        "planner_call_failed": observation(
            first=(
                "A machine came up, asked the planner for its files, and the call "
                "raised instead of returning a plan. The runner cannot start that "
                "machine, so the train and everything behind it stay queued."
            ),
            second=(
                "I ran the same thing again this morning. The machine at `{label}` "
                "still ends in an exception instead of a plan, so the runner has "
                "nothing to start it with and everything queued behind that train "
                "stays where it is. A machine has to come back with a list, "
                "whatever it finds in the tree."
            ),
            detail="{label}",
        ),
        "shard_assignment_missing": observation(
            first=(
                "The runner received a plan without a file list it can use. It "
                "refused to start that machine, so the train has no complete set of "
                "shards and cannot produce a result the team can trust."
            ),
            second=(
                "I went back through last night's log. At `{label}` the plan comes "
                "back with no readable list of files, so the runner has nothing it "
                "can use to start that machine."
            ),
            detail="{label}",
        ),
        "file_assigned_to_no_shard": observation(
            first=(
                "Tuesday's release shipped a bug that has a test. The test was not "
                "failing — it had not run. CI was green on that commit and the four "
                "shard logs between them never mention that file. I cannot tell "
                "anyone that green means anything while that is possible."
            ),
            second=(
                "I took last night's run and read the four machines' lists side by "
                "side. `{file}` is in the tree and in none of them, so nothing ran "
                "it and the train went green anyway."
            ),
            detail="{file}",
        ),
        "file_assigned_to_two_shards": observation(
            first=(
                "The machine bill went up this month while the trains got no "
                "faster. The board shows two shards spending their time on the "
                "same work, and finance is asking me what the fourth machine is "
                "for."
            ),
            second=(
                "Counted it on last night's run. `{file}` turns up on two machines "
                "at once, shards {shards}, so both of them build it and both wait "
                "on it. We pay for it twice and the train is no shorter."
            ),
            detail="{file}",
        ),
        "file_listed_twice_in_one_shard": observation(
            first=(
                "One machine's plan lists the same spec file more than once. That "
                "machine repeats work while the other machines wait, and duplicate "
                "test results leave the engineer with two accounts of one commit."
            ),
            second=(
                "It is still doing it. On last night's run `{file}` is in one "
                "machine's list {times} times, so that machine does the work twice "
                "and the whole train waits for it."
            ),
            detail="{file}",
        ),
        "unknown_file_assigned": observation(
            first=(
                "A machine's plan names a file that is not in the working tree. "
                "The run log no longer describes the checkout that was run, so an "
                "engineer cannot tell whether the suite in that commit was covered."
            ),
            second=(
                "I compared the plan with last night's tree. A machine was handed "
                "`{file}`, which is not in that checkout at all, so the plan and "
                "the run it is meant to describe do not reconcile."
            ),
            detail="{file}",
        ),
    },
    "run_pinned_plan_agreement": {
        "candidate_execution_failed": DID_NOT_RUN,
        "retry_plan_differs": observation(
            first=(
                "A machine died on a network fault on Wednesday. We restarted it, "
                "the train went green, and the test that had taken it down was "
                "still failing on the branch the next morning. We shipped a known "
                "break because a restart made it disappear."
            ),
            second=(
                "I reproduced it against the retry log. The restarted machine "
                "plans a different set of files from the ones it had on its first "
                "attempt — `{first_file_that_moved}` is one of the files that moved "
                "off it — so the work it died on is never tried again."
            ),
            detail="{first_file_that_moved}",
        ),
        "plan_moved_after_recording": observation(
            first=(
                "One machine of last night's run was asked for its files twice "
                "inside that run, and the second answer was not the first one. The "
                "run's own log now holds two lists for one machine, and when the "
                "engineer on that train asked me which of them had actually been "
                "run I could not tell him."
            ),
            second=(
                "I read the log again for that machine. Asked twice inside the "
                "same run it comes back with two lists {moved_count} files apart, "
                "so what the other machines finish in between changes what this "
                "one is told to run."
            ),
            detail="{moved_count}",
        ),
        "plan_generation_not_pinned": observation(
            first=(
                "The timing board and the run log stopped agreeing with each "
                "other. The board reports a run against the history we had at the "
                "start of the evening and the machines say they used something "
                "else. When those two disagree I have nothing to show finance."
            ),
            second=(
                "Checked what the machines printed. The plan says it was built "
                "from generation {reported} when the run was started on a "
                "different one, so what a machine used and what the run says it "
                "used are two different things."
            ),
            detail="{reported}",
        ),
    },
    "unmeasured_files_keep_the_usual_split": {
        "candidate_execution_failed": DID_NOT_RUN,
        "cold_start_planner_failed": observation(
            first=(
                "A run started without usable timings for its checkout and the "
                "planner raised instead of giving its machines a plan. The train "
                "cannot start, even though there is a normal split CI can fall back "
                "to when the history has nothing useful to say."
            ),
            second=(
                "I reproduced it on run `{run_id}`. The history gives that checkout "
                "no usable timings and the machines still get an exception instead "
                "of a plan, so the run never starts."
            ),
            detail="{run_id}",
        ),
        "cold_start_split_differs": observation(
            first=(
                "A run whose history has no usable timings moved files away from "
                "the shard indices CI normally uses. The machines restored caches "
                "for other files and the quarantine list no longer followed the "
                "tests it was meant to cover."
            ),
            second=(
                "It is the split itself. On run `{run_id}` the machines come back "
                "with something other than the split CI has always had — "
                "{moved_count} files sit on a different machine from the one that "
                "holds their cache — so the caches and the quarantine list are all "
                "pointing at the wrong shard."
            ),
            detail="{moved_count}",
        ),
        "unmeasured_file_moved_off_its_usual_shard": observation(
            first=(
                "A branch added files the history had never timed, and some of "
                "those files were moved away from their usual shard indices. The "
                "machines restored caches for other work and the index-keyed "
                "quarantine list no longer followed those tests."
            ),
            second=(
                "I put the branch's plans beside the split we have always had. "
                "`{file}` is a file the history has no time for at all, and the "
                "plan has moved it to another machine anyway, so it arrives where "
                "neither its cache nor its quarantine entry is."
            ),
            detail="{file}",
        ),
    },
    "duration_history_conservation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "recorder_call_failed": observation(
            first=(
                "At least one machine finished its tests and then its history "
                "publication raised. The runner cannot close the train or account "
                "for what that machine learned from the run."
            ),
            second=(
                "It happens at the end of run `{run_id}`: a finish callback raises "
                "while writing down what its files took, so the run fails during "
                "publication rather than because of a test result."
            ),
            detail="{run_id}",
        ),
        "history_file_unreadable": observation(
            first=(
                "`duration-history.json` came out of a run in a form the runner "
                "cannot read. The next planner sees no usable timings, so the "
                "timing board cannot carry what that run learned into the next one."
            ),
            second=(
                "Confirmed it after run `{run_id}`. What the machines leave behind "
                "is not a history the runner can read back, so the next morning's "
                "runs all start from nothing again."
            ),
            detail="{run_id}",
        ),
        "earlier_observation_lost": observation(
            first=(
                "A history publication removed a timing the document held before "
                "that write. The next split is now being worked out from less than "
                "the team had already measured."
            ),
            second=(
                "I compared the document before and after one publication. The "
                "timing it held for `{file}` beforehand is missing afterwards, so "
                "that publication discarded an observation it was meant to keep."
            ),
            detail="{file}",
        ),
        "completed_file_not_recorded": observation(
            first=(
                "At least one file ran to completion without gaining an observation "
                "in the history. The next run has to guess that file's cost even "
                "though CI just measured it."
            ),
            second=(
                "I followed one file through a whole run. `{file}` ran to the end "
                "on one of the machines and there is still nothing in the history "
                "for it afterwards."
            ),
            detail="{file}",
        ),
        "file_recorded_more_than_once": observation(
            first=(
                "One run is leaving more than one new timing for the same completed "
                "file. The history then counts one night's result repeatedly rather "
                "than preserving one observation of what the file cost."
            ),
            second=(
                "Counted them after one run: `{file}` has {times} timings from "
                "that single run, so its history is a pile of copies of one night "
                "rather than a record of what the file costs."
            ),
            detail="{times}",
        ),
        "unrun_file_recorded": observation(
            first=(
                "A file that did not run to completion is down in the history as "
                "if its partial number were a useful duration. The next split can "
                "then price unfinished work as though CI had measured the file."
            ),
            second=(
                "There it is again after last night's run. `{file}` never ran to "
                "the end on that machine and the history has a timing for it "
                "anyway."
            ),
            detail="{file}",
        ),
        "unexpected_observation_recorded": observation(
            first=(
                "The timing history now contains work no machine reports having "
                "finished. The next split is being priced from a made-up result, "
                "so the timing board and the run log no longer reconcile."
            ),
            second=(
                "I compared the publication with the run log. `{file}` gained a "
                "{recorded_minutes}-minute timing even though no machine in that "
                "publication reported completing it."
            ),
            detail="{file}",
        ),
        "recorded_duration_wrong": observation(
            first=(
                "The numbers in the history and the numbers on the timing board "
                "stopped matching. The board has a file at one time and the "
                "history has that same file at another, so the split we build out "
                "of the history is built on fiction and the cost report I write "
                "from the two of them cannot be right."
            ),
            second=(
                "I put one against the other after a run. The history has `{file}` "
                "at {recorded_minutes} minutes and the board has that machine "
                "spending a different amount of time on it."
            ),
            detail="{recorded_minutes}",
        ),
        "recorded_time_not_from_the_run_clock": observation(
            first=(
                "The clock stamps in the history no longer match the clock in the "
                "run log. I cannot attribute those observations to the run that "
                "produced them or reproduce that run's history from its log."
            ),
            second=(
                "It is the times we write down. After a run, the entry for "
                "`{file}` is stamped with something other than the run's own clock "
                "reading, so replaying that run does not reproduce it."
            ),
            detail="{file}",
        ),
        "history_generation_did_not_advance": observation(
            first=(
                "A run published observations without putting them in a generation "
                "later than the one it started from. The timing board cannot "
                "separate what that run learned from what was already available."
            ),
            second=(
                "I followed one run through on your build. Its publication went in "
                "at generation {published}, while the run started from generation "
                "{run_started_at}; because the publication is not later, the file "
                "cannot separate the new observations from the starting snapshot."
            ),
            detail="{published}",
        ),
        "history_generation_disagrees_with_entries": observation(
            first=(
                "The history file disagrees with itself about which generation is "
                "current. The timing board cannot reliably say which observations "
                "belong to the snapshot a run was planned from."
            ),
            second=(
                "The document header says generation {document_generation}, but "
                "its newest observation says generation {entry_generation}."
            ),
            detail="{document_generation}",
        ),
    },
    "plan_balance_honesty": {
        "candidate_execution_failed": DID_NOT_RUN,
        "balance_report_missing": observation(
            first=(
                "The runner received a plan whose accounting fields it cannot read. "
                "It cannot start that machine or put a usable expected cost beside "
                "the run for the timing board."
            ),
            second=(
                "I checked the rejected plan at `{label}`. The part the runner "
                "cannot read is {missing}, so the machine never starts and the "
                "cost report has no usable plan to compare."
            ),
            detail="{missing}",
        ),
        "plan_context_mismatch": observation(
            first=(
                "A plan on the timing board is attached to the wrong run or "
                "machine context. I cannot match its predicted cost to the shard "
                "the runner actually started."
            ),
            second=(
                "At `{label}`, the plan reports `{field}` as {reported}, while the "
                "runner invoked it with {expected}."
            ),
            detail="{reported}",
        ),
        "predicted_total_disagrees": observation(
            first=(
                "The cost report went out with a number I have had to retract. The "
                "predicted total for one shard was not the total of the work on "
                "that shard, so what I showed finance was a run measured against a "
                "number that came from somewhere else."
            ),
            second=(
                "I went back over it. On one machine the plan claims "
                "{claimed_minutes} minutes and the files it lists add up to "
                "something else, so the prediction is not a prediction of the work "
                "that machine was handed."
            ),
            detail="{claimed_minutes}",
        ),
        "estimate_not_from_history": observation(
            first=(
                "The prices in a plan do not match the timings in the generation "
                "that plan names. The timing board cannot explain a prediction or "
                "compare it with the run when its input prices came from elsewhere."
            ),
            second=(
                "Here is one of them. The plan prices `{file}` at {priced_minutes} "
                "minutes and the history it says it was built from holds a "
                "different number for that file."
            ),
            detail="{file}",
        ),
        "slower_than_the_split_it_replaced": observation(
            first=(
                "We changed the split and the trains got slower. The board is "
                "worse this week than it was on the old one, and I have spent "
                "release week explaining to people why their work is queuing "
                "behind a change that was meant to speed them up."
            ),
            second=(
                "I timed both on the same run. This split finishes in "
                "{planned_minutes} minutes and the same files under the split we "
                "had finish sooner than that, so we are paying for a change that "
                "costs us time."
            ),
            detail="{planned_minutes}",
        ),
        "plan_predicts_a_lopsided_split": observation(
            first=(
                "A partly timed branch produced plans that put much more priced "
                "work on one machine than the others. The imbalance was already in "
                "the plans before any machine started, so it is a cost the split "
                "chose rather than an unmeasured surprise."
            ),
            second=(
                "I read the four plans for that run again. The heaviest of them "
                "says {predicted_minutes} minutes out of the prices it took from "
                "the history, where the budget note allows a quarter over the mean "
                "of those same prices, so the split was lopsided in the numbers we "
                "had before anybody started a machine."
            ),
            detail="{predicted_minutes}",
        ),
        "shard_over_balance_bound": observation(
            first=(
                "The trains are still lopsided. Three machines are done and idle "
                "while the fourth grinds on, which is the exact thing this was "
                "meant to fix, and the line in the March review is what I get "
                "asked about every month."
            ),
            second=(
                "I measured last night's run. The slowest machine ran "
                "{slowest_minutes} minutes where the budget note allows a quarter "
                "over the mean, so three machines are paid for and waiting."
            ),
            detail="{slowest_minutes}",
        ),
    },
}
