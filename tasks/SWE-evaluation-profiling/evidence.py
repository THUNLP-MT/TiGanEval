'Owner persona, belief, and Observation contexts for SWE-evaluation-profiling.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ines, the platform engineer who runs the decision service; she reads the "
    "request log, the rule report on the operator console and what the bundle "
    "owners send back to her, not the engine's code."
)

USER_BELIEF = """Since the vendor-access bundle went live, p99 on /v1/decide is about double what it was, and when a bundle owner asks me which of their rules is behind it I have nothing to give them: the request log carries the decision and the total work units, and that is all.

What I want is to hand each team a report of their own rules out of the nightly replay, saying which ones ran and how many of those runs came back with a value, and to have it stand up when they argue with it. Dana has written a first cut and I half trust it: the counting I believe in, the way it names rules I am not sure about.

Done, for me, is a morning where I send the vendor team their own numbers, they point at a rule, they fix it, and the p99 comes down. It is switched on for the nightly replay and off in live traffic."""

OBSERVATION_SCENE = "Morning review of the decision service"


_DRILL_STOPPED = observation(
    first=(
        "The nightly replay stopped part way through last night's traffic, so there is no "
        "timeline to go through this morning and nobody can tell me what the service did "
        "with the requests that never got answered."
    ),
    second=(
        "I ran the peak-hour drill on your build myself and it stops part way there too. "
        "The console holds one line where the timeline should be: {error}"
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "profiling_is_not_causal": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "engine_operation_failed": observation(
            first=(
                "One step in the replay raised instead of producing its record. The rest of "
                "the drill can still run, but a release check with a missing service step is "
                "not something I can sign off."
            ),
            second=(
                "Ran it again on your build. The failing step is {label}; it raises instead "
                "of producing its result."
            ),
            detail="{label}",
        ),
        "decision_changed_by_profiling": observation(
            first=(
                "A bundle owner ran the same request twice this morning, once with the report "
                "switched on and once without, and got two different answers back. He does not "
                "trust the numbers now, and after seeing that, neither do I."
            ),
            second=(
                "I did it myself on your build with {request}: with the report off it comes "
                "back {without_profiling}, and with the report on it comes back "
                "{with_profiling}."
            ),
            detail="{with_profiling}",
        ),
        "decision_disagrees_with_policy": observation(
            first=(
                "We replayed a slice of yesterday's traffic and one request came back with an "
                "answer the bundle does not give. That is a wrong decision going out to a "
                "customer, and it is worse than having no report at all."
            ),
            second=(
                "Walked {request} through the rules by hand: the service answers {decision} "
                "where the bundle gives {policy_says}."
            ),
            detail="{policy_says}",
        ),
        "work_changed_by_profiling": observation(
            first=(
                "With the report on, the recorded evaluation no longer matches the same "
                "traffic with it off, so its numbers cannot be compared to live traffic."
            ),
            second=(
                "Put the two side by side on your build for {request}: the run with the report "
                "off records {work_without_profiling} work units and the run with it on records "
                "{work_with_profiling}; their evaluation records do not match."
            ),
            detail="{work_with_profiling}",
        ),
    },
    "definition_level_attribution": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "profile_row_keys_not_definitions": observation(
            first=(
                "The vendor team read the report and sent it straight back to me: the lines in "
                "it do not match anything they can open in their bundle, so there is nothing "
                "for them to go and fix."
            ),
            second=(
                "I went through it line by line on your build. The line called {row} is not one "
                "of the rule bodies in the loaded bundle, and there are {definitions} of them "
                "answering to that name."
            ),
            detail="{row}",
        ),
        "entered_definition_missing": observation(
            first=(
                "On-call has been chasing a rule that runs on every request and never comes "
                "back with a value, which is exactly the sort of thing the vendor team would "
                "delete. It is not in the report anywhere, so we cannot show it to them."
            ),
            second=(
                "Checked one request, {request}: {definition} ran while the service answered "
                "it, and there is no line for it in the report."
            ),
            detail="{definition}",
        ),
        "unentered_definition_reported": observation(
            first=(
                "The decision report includes definitions this request did not enter. Those "
                "lines mix the loaded catalogue into the per-decision view the bundle owner "
                "uses to see what this request exercised."
            ),
            second=(
                "On {request} your build reports {definition}, which the bundle has and this "
                "decision never entered."
            ),
            detail="{definition}",
        ),
        "definition_success_count_wrong": observation(
            first=(
                "At least one report line gives the wrong number of times its body came back "
                "with a value. A bundle owner cannot safely use that number to decide whether "
                "the definition is useful."
            ),
            second=(
                "Counted it by hand on {request}: the line for {definition} says {reported}, "
                "while the measured success count is {measured}."
            ),
            detail="{reported}",
        ),
    },
    "reuse_is_not_evaluation": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "evaluation_count_wrong": observation(
            first=(
                "The vendor team spent a day on the rule at the top of the report and found "
                "nothing to fix, because the number next to it is not the number of times that "
                "body ran. Whatever it counts, it is not what costs us."
            ),
            second=(
                "Counted the bodies that ran on {request} against the report: {measured} of "
                "them ran, and the report claims {reported}."
            ),
            detail="{measured}",
        ),
        "reuse_never_recorded": observation(
            first=(
                "The decisions do reuse rule values they have already worked out, but the "
                "report records no reuse anywhere. That leaves the fan-out unaccounted for "
                "even when the body itself ran only once."
            ),
            second=(
                "The clearest one is {rule}: a decision resolves it {asks} times, its body-run "
                "count is {evals}, and the report records none of the reuse between them."
            ),
            detail="{rule}",
        ),
        "reuse_count_wrong": observation(
            first=(
                "The report does say something about reuse now, but at least one rule's runs "
                "and reuses do not add up to the number of times the decision asked for it. "
                "The fan-out is still being misreported."
            ),
            second=(
                "On {request} the line for {definition} says {reported} where that value was "
                "reused {measured} times."
            ),
            detail="{definition}",
        ),
    },
    "profile_scoped_to_one_decision": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "profile_attached_when_disabled": observation(
            first=(
                "Live traffic is coming back with a rule report attached to it. Nobody asked "
                "for one there, callers are getting it in their response, and one of them has "
                "already opened a ticket about the size of it."
            ),
            second=(
                "On {request}, which nobody asked to report on, the decision still came back "
                "with a report on it."
            ),
            detail="{request}",
        ),
        "profile_missing_when_enabled": observation(
            first=(
                "The nightly replay finished and some of the decisions came back with no "
                "report at all, so this morning I have gaps where the interesting requests "
                "were and nothing to send the bundle owners for them."
            ),
            second=(
                "Ran it again on your build: {request} was asked to report and came back with "
                "nothing where the report should be."
            ),
            detail="{request}",
        ),
        "profile_depends_on_earlier_requests": observation(
            first=(
                "Two identical requests in one night's replay came back with different "
                "numbers, and the later one's are enormous. Whatever those lines describe, it "
                "is not the request they arrived with, and I cannot hand that to anybody."
            ),
            second=(
                "Ran {request} on your build, the same request as {earlier}: it reports "
                "{reported_total} runs where the earlier one reports {earlier_total}."
            ),
            detail="{reported_total}",
        ),
        "retired_bundle_rules_reported": observation(
            first=(
                "The report I sent the vendor team has rules in it that are not in their "
                "bundle any more. We publish a new bundle two or three times a day, and after "
                "each one the report goes on billing them for rules we have retired."
            ),
            second=(
                "Looked at a decision from after a publish, {request}: your build still "
                "reports {row}, which the loaded bundle does not have."
            ),
            detail="{row}",
        ),
        "earlier_profile_changed_by_later_decision": observation(
            first=(
                "The report we handed a bundle owner at nine looked nothing like it did when "
                "we opened it again at eleven: same decision, different numbers. He asked, "
                "fairly, which of the two he is supposed to act on."
            ),
            second=(
                "Kept the report from {request} and opened it again later in the same batch, "
                "at {checked_at}: it is not the one we were handed."
            ),
            detail="{checked_at}",
        ),
    },
    "rollup_preserves_the_run": {
        "candidate_execution_failed": _DRILL_STOPPED,
        "rollup_operation_failed": observation(
            first=(
                "One step in the nightly job raised instead of producing its output. The "
                "nightly result is incomplete, so I cannot publish it as the baseline for "
                "the week-over-week numbers."
            ),
            second=(
                "Ran the nightly steps by hand on your build: the step at {label} raises "
                "instead of producing its output."
            ),
            detail="{label}",
        ),
        "package_key_not_package": observation(
            first=(
                "The per-package view contains a bucket that is not a package in the loaded "
                "bundle. I cannot route that traffic to a bundle owner or ask anyone to act "
                "on the number."
            ),
            second=(
                "Read the buckets back on your build: one of them is {bucket}, which is not a "
                "package in the bundle at all."
            ),
            detail="{bucket}",
        ),
        "package_totals_disagree_with_run": observation(
            first=(
                "The per-package numbers I send out do not add up to the total on the same "
                "page. A bundle owner noticed before I did, and now the report is something "
                "he checks rather than something he uses."
            ),
            second=(
                "Added them up at {label} on your build: {bucket} comes to {reported} where "
                "its own lines come to {measured}."
            ),
            detail="{measured}",
        ),
        "merged_shard_counts_wrong": observation(
            first=(
                "The retained merge does not equal the two shard reports added row by row. "
                "That merge is what the baseline is built from, so the week-over-week "
                "comparison no longer represents those nights."
            ),
            second=(
                "Merged the two by hand at {label}: the line for {row} comes out {reported} "
                "where the two nights together are {measured}."
            ),
            detail="{row}",
        ),
        "derived_profile_aliases_source": observation(
            first=(
                "Last night's stored shard is not what it was this morning. The nightly job "
                "went over it and the shard came back changed, so the baseline we compare "
                "against has been quietly rewritten and I cannot say by how much."
            ),
            second=(
                "Watched it happen at {label}: the job wrote into the view it had just built, "
                "and the line for {row} changed in the stored shard underneath it."
            ),
            detail="{row}",
        ),
        "success_rate_wrong": observation(
            first=(
                "The rate column on the console does not agree with the two numbers beside it. "
                "One bundle owner has been reading that column as the share of his traffic a "
                "rule answers, and deciding what to delete from it."
            ),
            second=(
                "Checked one line at {label}: the console prints {reported} for {row} where "
                "its own counts give {measured}."
            ),
            detail="{reported}",
        ),
    },
}
