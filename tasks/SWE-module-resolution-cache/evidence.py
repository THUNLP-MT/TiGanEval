'Owner persona, belief, and Observation contexts for SWE-module-resolution-cache.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dara, the platform engineer who owns the scripting runtime the analytics fleet "
    "runs its nightly jobs on. He reads the kit vendor's licence invoice, the per-job "
    "logs the console captures, the catalog a run ends with and what a replay of a "
    "recorded stretch prints; he does not read the loader's code."
)

USER_BELIEF = (
    "What I want is a quarter in which nobody upstairs has a question about the "
    "nightly prices that I cannot answer off the run's own output. Two things went "
    "wrong in August. The kit vendor billed us for three times the kit files we have, "
    "and finance made me account for it line by line. And a market team found their "
    "prices differed between two workers on the same night, under the same release "
    "stamp, and I could not tell them which of the two was right or why. What I can "
    "see is the licence invoice, the catalog each run ends with, and the per-job logs "
    "the console captures. Done, for me, is a month of nights where the invoice "
    "matches the kits we actually have, two nights of the same work end with the same "
    "catalog whatever order the queue ran them in, and when support asks which job "
    "pulled a kit I can point at that job's own log and say so."
)

OBSERVATION_SCENE = "The runtime owner's review of the nightly queue after a change to the loader"


DID_NOT_RUN = observation(
    first=(
        "I put your loader on the staging worker before this morning's queue review "
        "and started last night's job list through it. It stopped part way instead of "
        "reaching the end, so there is no catalog, no licence checks and no job logs. "
        "I have nothing to take back to finance about the change."
    ),
    second=(
        "I tried it once more, on the shorter evening list, and it stopped part way "
        "there too. Where the run report should be, the console has one line: {error}. "
        "Until a plain list of jobs runs end to end I cannot judge anything else about "
        "the change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "single_activation_per_file": {
        "candidate_execution_failed": DID_NOT_RUN,
        "file_activated_under_a_second_name": observation(
            first=(
                "The licence bill is still wrong. I ran a night through your loader and "
                "counted the desk's checks against the kit files we actually have, and "
                "the desk is billing us for more kits than exist. Finance is going to "
                "ask me the same question again next month."
            ),
            second=(
                "I went through the checks one by one. `{kit}` was brought up "
                "{activations} times in one night, and the jobs that asked for it wrote "
                "its path {spellings} different ways between them. It is one file at "
                "{file}. However a job spells it, it is the same kit."
            ),
            detail="{spellings}",
        ),
        "cached_kit_activated_again": observation(
            first=(
                "Nothing has come off the licence bill. I put your loader on the "
                "staging worker, ran a night through it and the desk billed us almost "
                "exactly what it billed us in August. That is the whole reason I asked."
            ),
            second=(
                "I read the checks back against one job. `{job}` alone brought `{kit}` "
                "up {in_one_job} times inside itself, {activations} over the night in "
                "all, and the desk charged us for every one: {licence_checks} checks "
                "for {kits_brought_up} kit files."
            ),
            detail="{in_one_job}",
        ),
        "file_activated_again_for_another_job": observation(
            first=(
                "The bill has come down and it is still not right. A night through your "
                "loader costs us more checks than we have kit files, and when I showed "
                "finance the difference they asked what changes between the jobs. I do "
                "not have an answer."
            ),
            second=(
                "I sorted the checks by job. `{kit}` was brought up once for each of "
                "{jobs} jobs, {activations} times over the night, all of them reading "
                "{file}. A kit is a kit for the night, not for one job."
            ),
            detail="{kit}",
        ),
    },
    "resolution_agreement": {
        "candidate_execution_failed": DID_NOT_RUN,
        "shared_copy_beat_the_local_one": observation(
            first=(
                "The pilot job priced with the wrong kit last night. That job runs a "
                "copy of a kit in its own folder for a fortnight before we put the "
                "change in the shared directory, and the number in the morning's "
                "catalog was the shared one's. Two weeks of piloting told us nothing."
            ),
            second=(
                "I traced `{job}` through the replay. Its `use {name}` opened {opened}, "
                "and its own folder has {expected} sitting right next to it. A job's own "
                "folder is where we put the copy we want that job to run."
            ),
            detail="{opened}",
        ),
        "shared_kit_read_the_pinned_list": observation(
            first=(
                "A shared kit read the nightly queue's pinned market list last night, "
                "and it is not supposed to see that list at all. The invoice totals came "
                "out for the wrong set of markets and the market team spotted it before "
                "I did."
            ),
            second=(
                "I followed it through the replay. {asked_by} asked for `{name}` and was "
                "handed {opened}, where {expected} is the file sitting in its own "
                "directory. A kit asks from where it lives, not from wherever the job "
                "that pulled it in was started."
            ),
            detail="{opened}",
        ),
        "job_missed_its_own_pinned_list": observation(
            first=(
                "The market team pinned a list of their own into the nightly folder last "
                "quarter, and last night's prices went out without it. The pricing job "
                "counted markets off the shared list instead, so the figure that reached "
                "finance covers markets that pinned list exists to leave out, and the "
                "team spent the morning reconciling by hand."
            ),
            second=(
                "I put the night's job list through again and followed that one ask. "
                "`{job}` asked for `{name}` and came back with {opened}; the pinned list, "
                "{expected}, is in the same folder as the job file that asked for it. "
                "What a job keeps beside it is what that job prices with."
            ),
            detail="{opened}",
        ),
        "worker_settings_changed_the_result": observation(
            first=(
                "Two workers priced the same night differently again. Same queue, same "
                "release stamp, different numbers in the two catalogs, and the only "
                "thing that is not identical about those two boxes is how somebody typed "
                "their settings in. I cannot tell the market team which night was right."
            ),
            second=(
                "I put the same jobs through both workers on your loader and diffed what "
                "they opened. On `{job}`, the ask for `{name}` opened {opened} on one "
                "worker and {other} on the other. Those two settings say the same thing "
                "in two spellings; they have to reach the same file."
            ),
            detail="{name}",
        ),
        "kit_name_not_found": observation(
            first=(
                "Half the queue fell over on the staging worker. Jobs are stopping on "
                "their first line saying they cannot find a kit that is plainly sitting "
                "in the store, and the nights they were meant to price came out empty."
            ),
            second=(
                "I looked at where it gives up. `{job}` asked for `{name}` from "
                "{asked_by} and was told there is nothing anywhere that answers to it. "
                "That kit is in the store and that worker's settings point at it."
            ),
            detail="{job}",
        ),
    },
    "load_state_conservation": {
        "candidate_execution_failed": DID_NOT_RUN,
        "cycle_not_refused": observation(
            first=(
                "The staffing job took the whole worker down last night. The roster kit "
                "and the shift pattern have referred to each other since last quarter's "
                "refactor and the loader went round and round between them until the "
                "process gave up. Every job queued behind it lost its slot."
            ),
            second=(
                "I ran the same job list again on your build and watched `{job}`. It "
                "ended with {stopped_with}, and the on-call is none the wiser about "
                "which {kits} kits are pointing at each other. When two kits refer back "
                "to each other we need the job stopped and told which ones they are."
            ),
            detail="{stopped_with}",
        ),
        "failed_kit_left_behind": observation(
            first=(
                "The vendor feed was empty again last night and this time the jobs after "
                "it priced anyway. The feed job stopped the way it always does, and then "
                "the retry twenty minutes later came back clean with no rates in it, so "
                "we invoiced a whole region at zero."
            ),
            second=(
                "I put that pair through your build. The first job stopped with "
                "{first_stopped_with}; the retry stopped with {stopped_with}, and the "
                "store's own count of reads for `{kit}` over the night is {opened}, "
                "against the two jobs that asked for it. A kit that refused has to be "
                "read again and refuse again."
            ),
            detail="{kit}",
        ),
        "cycle_chain_incomplete": observation(
            first=(
                "On-call sat with the staffing job for forty minutes last night. It "
                "stopped and said two kits are pointing at each other, which is right, "
                "and it did not say which two, so they went through the whole shared "
                "directory by hand before they found the pair."
            ),
            second=(
                "I read the line it stopped on. What it prints is `{chain}`, which on-call "
                "reads as {kits_named}, starting at `{started_at}` and naming {named} where "
                "the loop goes through {kits} kits. They need every kit the loop went "
                "through, from the one that was already coming up when it came round again "
                "to the one that led back to it, in the order the job asked for them. How "
                "each kit is written on that line is not what they are stuck on."
            ),
            detail="{chain}",
        ),
    },
    "run_outcome_independence": {
        "candidate_execution_failed": DID_NOT_RUN,
        "run_depended_on_the_queue_order": observation(
            first=(
                "The monthly audit is stuck. Two nights of the same job list came out "
                "with different catalogs on your build, and the only difference between "
                "those nights is which job the queue handed out first. The auditors will "
                "not sign a set of prices we cannot reproduce."
            ),
            second=(
                "I ran the identical list twice, changing nothing but the dispatch "
                "order. `{key}` came out {first} the first time and {second} the second, "
                "in catalogs of {entries} and {other_entries} entries. The queue hands "
                "jobs out as workers free up; the night's numbers cannot follow it."
            ),
            detail="{key}",
        ),
        "half_built_kit_was_handed_out": observation(
            first=(
                "The staffing numbers went out wrong last night and nothing failed. The "
                "roster kit and the shift pattern refer to each other, one of them read "
                "the other before it was finished, and the catalog carries the answer it "
                "got. Nobody would have caught it if the depot had not rung."
            ),
            second=(
                "I found it in the catalog: `{key}` was published as {value}, one of "
                "{entries} entries `{job}` left behind. Nothing that has not finished "
                "coming up should ever be handed to a kit that is reading it."
            ),
            detail="{key}",
        ),
        "catalog_did_not_match_the_kit_files": observation(
            first=(
                "The night's numbers do not match the kits. I ran the queue on your "
                "build and read the catalog against what the kit files in the store "
                "actually say, and they disagree. Finance prices off that catalog, so "
                "the invoices behind it are wrong."
            ),
            second=(
                "I went entry by entry. `{key}` came out {observed} where the kits in "
                "the store give {expected}, in a catalog of {entries} entries against "
                "the {expected_entries} the night should end with."
            ),
            detail="{observed}",
        ),
        "held_kits_listed_in_dispatch_order": observation(
            first=(
                "The monthly audit will not close. It reads two nights of the same job "
                "list side by side, and on your build the run report's list of the kits "
                "the worker held is not the same list on the two nights. A night where "
                "nothing changed reads as a change, and the sign-off sits with me."
            ),
            second=(
                "I ran the identical list twice, changing nothing but the dispatch "
                "order, and put the two run reports beside each other: {moved} of the "
                "{entries} lines came back different, from line {at} on. The queue hands "
                "jobs out as workers free up, so which job happened to reach a kit first "
                "cannot be what that report says about it."
            ),
            detail="{moved}",
        ),
    },
    "loader_diagnostics_routing": {
        "candidate_execution_failed": DID_NOT_RUN,
        "diagnostics_went_to_the_process_stream": observation(
            first=(
                "Support could not answer finance again this morning. They asked which "
                "job pulled a stale kit into last night's prices, went to the job logs "
                "the console keeps, and every one of them is empty. Everything the "
                "loader had to say went into the worker's crash dump instead, all the "
                "jobs mixed together and none of it attributed."
            ),
            second=(
                "I counted what ended up there on your build: {lines} lines in the crash "
                "dump, starting with `{first_line}`. The console captures each job's own "
                "stream into that job's file, and that is the only place support looks."
            ),
            detail="{lines}",
        ),
        "nothing_reached_the_job_logs": observation(
            first=(
                "The job logs are still blank. I ran the queue through your build with "
                "tracing on and went to read what the loader did, and there is nothing "
                "in any of them. That was half of what I asked for, and support is no "
                "better off than they were in August."
            ),
            second=(
                "I checked the settings on the run first, because I assumed I had it "
                "switched off. {jobs_asking} of the jobs asked for it, `{job}` among "
                "them, and their logs came back empty all the same."
            ),
            detail="{job}",
        ),
        "command_line_switch_ignored": observation(
            first=(
                "The trace only works for half the fleet. The workers the platform team "
                "set up write their logs; the ones the cron starts write nothing, and "
                "the cron ones are the nightly queue. Support is back to guessing on "
                "exactly the runs they need."
            ),
            second=(
                "I put both kinds through on your build. `{other_job}` wrote "
                "{other_lines} lines, and `{job}`, which the console starts with the "
                "switch on its command line, wrote none. Those two are set by different "
                "teams and both have to turn it on."
            ),
            detail="{job}",
        ),
        "job_log_did_not_match_the_job": observation(
            first=(
                "The job logs do not add up. Support tried to follow one job through "
                "yesterday and the log skips things the job plainly did, so they could "
                "not say where the kit it priced with came from. A log we have to second "
                "guess is no better than none."
            ),
            second=(
                "I counted the lines against what the job did. `{job}` has {counted} of "
                "the {event} kind where the run says there should be {expected}. Every "
                "time the loader looks a kit up, brings one up, or hands back one it is "
                "already holding, that is a line."
            ),
            detail="{counted}",
        ),
    },
}
