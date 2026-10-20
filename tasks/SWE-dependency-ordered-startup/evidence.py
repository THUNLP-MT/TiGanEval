'Owner persona, belief, and Observation contexts for SWE-dependency-ordered-startup.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Aksel, on call for the API service. He reads the deploy log, the boot "
    "ledger the console prints after a start-up, and what the platform and "
    "warehouse teams tell him; he does not read the start-up code."
)

USER_BELIEF = (
    "I want a deploy window we finish inside, and a deploy that fails leaving "
    "nothing behind it. Tuesday's 08:00 cutover went out a minute and a half "
    "late because the process brings the services up one after another and the "
    "traffic switch had to wait for us; the shop had no price updates until "
    "after eight and I had the retail lead on the phone. What I can see is the "
    "deploy log and the boot ledger the console prints: which service "
    "connected, when, what it took from the hosts and what it gave back. The "
    "warehouse team read their side of the same thing and ask me about it. "
    "Done, for me, is a month of deploys that land inside the window, that come "
    "up in a state the service can actually serve from, and that when one falls "
    "over leave the next attempt a clean box to run on."
)

OBSERVATION_SCENE = (
    "On-call's review of the deploy console and platform trace after an API service deploy"
)


DID_NOT_RUN = observation(
    first=(
        "I put your build on the deploy box before this morning's review and "
        "started the stack on it. It stopped part way instead of coming up, so "
        "there is no boot ledger, no timings and nothing to read. I have "
        "nothing to tell the platform team about the change."
    ),
    second=(
        "I tried it once more from a clean box and it stopped part way there "
        "too. Where the ledger should be, the console has one line: {error}. "
        "Until a plain start-up runs end to end I cannot judge anything else "
        "about the change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "unwind_releases_started_services": {
        "candidate_execution_failed": DID_NOT_RUN,
        "failing_service_was_not_attempted": observation(
            first=(
                "The failing-deploy review never reached the refused "
                "handshake it was meant to exercise. Without that connect "
                "attempt there is no failure path here to tell us whether "
                "this build really cleans up after one."
            ),
            second=(
                "I ran that case again and checked the platform trace. "
                "`{service}` was never attempted, although this is the case "
                "configured for its lease refusal. There was therefore no "
                "real connect failure for this build to clean up."
            ),
            detail="{service}",
        ),
        "handle_taken_after_the_teardown": observation(
            first=(
                "The platform found a host handshake opened after the failed "
                "deploy had already run its stop steps. The run then ended "
                "while still holding that late handle, with no later cleanup "
                "step available to give it back."
            ),
            second=(
                "I matched the console run to the platform's handle trace. "
                "The stop steps had all run, and then `{service}` took its "
                "handle at tick {taken_at} and was still holding it when the "
                "run finished, one of {open_handles} in that state. That "
                "handshake belongs to a step this deploy started, so it is "
                "ours to give back."
            ),
            detail="{service}",
        ),
        "handle_never_given_back": observation(
            first=(
                "A failed deploy returned with host handshakes still open on "
                "the warehouse side. They continued to count against this "
                "process after the run had ended, so the platform team had to "
                "clear state the deploy should have given back itself."
            ),
            second=(
                "I matched your build's run to the platform's handle trace. "
                "`{service}` took its handle at tick {taken_at} and nothing "
                "ever gave it back, and it is one of {open_handles} the run "
                "finished still holding. A deploy that fails has to leave the "
                "box the way it found it."
            ),
            detail="{service}",
        ),
        "released_a_service_before_its_dependents": observation(
            first=(
                "A failed deploy brought down something that another running "
                "service still depended on. The dependent was asked to stop "
                "only afterwards, when the service it needed was already "
                "gone."
            ),
            second=(
                "I matched the teardown to the platform trace. `{service}` "
                "was stopped before `{dependent}`, which is built on it, and "
                "that teardown has {stop_errors} stop steps that went wrong. "
                "Things have to come down in an order they can still work in."
            ),
            detail="{dependent}",
        ),
        "released_something_it_had_not_started": observation(
            first=(
                "A failed deploy ran a stop step for a service whose connect "
                "step had never completed. The teardown was acting on a "
                "connection this attempt had not established, so its cleanup "
                "record could not be trusted."
            ),
            second=(
                "I checked the platform's connect and stop trace for your "
                "build. It ran the stop step for `{service}` at tick "
                "{released_at}, in an attempt where that service's connect "
                "step never finished; {connected} services had connected in "
                "it. What we bring down has to be something we brought up."
            ),
            detail="{service}",
        ),
        "stopped_the_same_service_twice": observation(
            first=(
                "A failed deploy called the same service's stop step twice. "
                "The second call went out after this attempt had already "
                "given that service's handle back."
            ),
            second=(
                "I counted the platform's stop calls for the one teardown. "
                "`{service}` was stopped {releases} times in it, and "
                "{stop_errors} stop steps went wrong. Everything we brought "
                "up comes down once."
            ),
            detail="{releases}",
        ),
        "failure_named_the_wrong_service": observation(
            first=(
                "A connect step failed, but the line the deploy returned did "
                "not identify the service that failed. The console therefore "
                "sent us away from the event that stopped the boot."
            ),
            second=(
                "I matched the console to the warehouse trace. `{service}` "
                "is the connect step that failed, but the line the deploy "
                "returned was {reported}. The deploy has to identify the "
                "thing that stopped it."
            ),
            detail="{reported}",
        ),
        "stop_error_not_recorded": observation(
            first=(
                "The warehouse saw one close fail during cleanup, but our "
                "boot ledger said nothing about it. The original connect "
                "failure still belongs at the top, but a failed stop cannot "
                "disappear from the record."
            ),
            second=(
                "I matched the warehouse trace to this build. The stop for "
                "`{service}` failed with {error}, and there is no matching "
                "stop-error line in the ledger. Record it while preserving "
                "the connect failure that caused the teardown."
            ),
            detail="{service}",
        ),
    },
    "startup_order_follows_dependencies": {
        "candidate_execution_failed": DID_NOT_RUN,
        "dependent_started_before_its_dependency": observation(
            first=(
                "One service began connecting before something it depends on "
                "was ready. The platform could not treat the dependent as "
                "safely started while the service underneath it was still in "
                "its own connect step."
            ),
            second=(
                "I checked the platform's connect trace for your build. "
                "`{service}` started at tick {started_at} and `{dependency}`, "
                "which it is built on, was not ready until "
                "{dependency_ready_at}. Nothing may come up before the things "
                "it reads are up."
            ),
            detail="{dependency}",
        ),
        "order_ignored_a_service_without_a_connect_step": observation(
            first=(
                "A service started before a dependency reached through one of "
                "the manifest's start-less holders was ready. The holder has "
                "no connect step of its own, but the dependency chain through "
                "it still governs when the service may start."
            ),
            second=(
                "I matched the manifest to the platform's connect trace. The "
                "chain is {path}: `{service}` reaches `{dependency}` through "
                "the holder in between, and it started at tick {started_at} "
                "with that dependency not ready until {dependency_ready_at}. "
                "The thing in the middle is still part of the path."
            ),
            detail="{path}",
        ),
    },
    "each_service_starts_once": {
        "candidate_execution_failed": DID_NOT_RUN,
        "service_never_started": observation(
            first=(
                "Bring-up returned control with one of the configured connect "
                "steps never having run. Whatever else the console reported, "
                "the resulting process was missing a service it was meant to "
                "bring up."
            ),
            second=(
                "I checked the platform's connect trace for your build. "
                "`{service}` has a connect step and there is no point in the "
                "run where that step began. Bring-up has to account for every "
                "configured connect step."
            ),
            detail="{service}",
        ),
        "service_started_more_than_once": observation(
            first=(
                "One process ran the same service's connect step more than "
                "once. A repeated bring-up or an in-place retry must not open "
                "another host session for something this process has already "
                "attempted."
            ),
            second=(
                "I counted the platform's connect calls for your build. "
                "`{service}` connected {starts} times inside the one process. "
                "A service this process has already connected must not be "
                "connected again."
            ),
            detail="{starts}",
        ),
        "retry_after_a_failed_start_restarted_services": observation(
            first=(
                "A deploy failed and the operator ran it again in the same "
                "process. At least one connect step from the failed attempt "
                "ran again after its resources had just been given back, so "
                "the retry was no longer a clean continuation."
            ),
            second=(
                "I put the failing deploy and the retry through your build. "
                "`{service}` connected {starts} times across those two "
                "attempts. Once a connect step has failed, running it again has "
                "to do nothing until somebody clears it."
            ),
            detail="{starts}",
        ),
        "started_services_before_rejecting_the_manifest": observation(
            first=(
                "The manifest had a bad dependency in it and the deploy "
                "rejected it, which is what should happen, except that it had "
                "already connected part of the stack before it got there. The "
                "operator corrected the line and restarted the process anyway, "
                "because nobody could say what the half-connected box was "
                "holding."
            ),
            second=(
                "I ran the operator's transcript through your build. "
                "`{service}` had already connected at tick {at} in the attempt "
                "that then rejected the manifest. A manifest we are going to "
                "refuse has to be refused before anything is touched."
            ),
            detail="{service}",
        ),
        "unknown_dependency_was_not_rejected": observation(
            first=(
                "A manifest named a service that was not registered, and the "
                "deploy carried on as if the graph were complete. The box "
                "came up with a writer whose backing service did not exist."
            ),
            second=(
                "I ran that manifest through your build. `{service}` declares "
                "`{dependency}`, nobody registered that name, and the first "
                "attempt did not reject the manifest. This has to stop before "
                "any connect step runs."
            ),
            detail="{dependency}",
        ),
        "retry_after_a_manifest_typo_refused": observation(
            first=(
                "Someone put the wrong dependency on a service in the manifest "
                "and the two of them ended up pointing at each other. We "
                "corrected the line in place and ran the deploy again in the "
                "same process, and it would not do anything at all, so we lost "
                "the rest of the window to a restart."
            ),
            second=(
                "I ran the operator's transcript through your build: the typo, "
                "the correction, then the second attempt. Nothing connected on "
                "that attempt and what came back was {reported}. A manifest we "
                "never started on is one we can fix and try again."
            ),
            detail="{reported}",
        ),
        "retry_after_an_unknown_dependency_refused": observation(
            first=(
                "An operator fixed an unregistered dependency in place after "
                "the deploy refused it, but the corrected attempt would not "
                "start. We lost the window to a process restart even though "
                "the first attempt had touched nothing."
            ),
            second=(
                "I repeated the missing dependency, its correction, and the "
                "second attempt. None of {services} connected after the fix, "
                "and the console returned {reported}. A cleanly rejected "
                "manifest must remain retryable."
            ),
            detail="{reported}",
        ),
    },
    "resolution_serves_started_instances": {
        "candidate_execution_failed": DID_NOT_RUN,
        "unstarted_service_handed_out": observation(
            first=(
                "A registry lookup handed out a service whose connect step "
                "had not completed. The caller received a constructed object "
                "that the platform had no evidence was ready to serve."
            ),
            second=(
                "I matched the registry lookup to the platform's connect "
                "trace. `{service}` was handed to the caller at tick {at}, "
                "without a completed connect step for it. Something that has "
                "not connected must not be handed out at all."
            ),
            detail="{service}",
        ),
        "service_missing_after_boot": observation(
            first=(
                "After bring-up returned control, the box was still missing a "
                "service when a caller asked for it. The process could not be "
                "treated as ready, whatever status the bring-up call had "
                "returned."
            ),
            second=(
                "I asked the registry after bring-up on this build. "
                "`{service}` came back with {reported}, and there is no real "
                "completed connect for it in the run. A finished boot must "
                "serve every service it claims to have brought up."
            ),
            detail="{service}",
        ),
        "started_service_not_resolvable": observation(
            first=(
                "A service completed its connect step, but a later registry "
                "lookup still refused to hand it to the caller. The platform "
                "had a completed connection that the process could not use."
            ),
            second=(
                "I matched the lookup to the platform's connect trace after "
                "bring-up. `{service}` came back with {reported}, although its "
                "connect step had completed earlier in that run. Once a "
                "service is connected it has to be reachable."
            ),
            detail="{reported}",
        ),
        "replacement_not_installed": observation(
            first=(
                "A connect step handed back its connected replacement, but a "
                "later registry lookup returned the original constructed "
                "object instead. The caller and the platform disagreed about "
                "which instance had actually been connected."
            ),
            second=(
                "I compared the registry lookup with the platform's connect "
                "result. The registry hands out `{served_as}` for that service "
                "and its connect step finished with {connected_as}. The rest "
                "of the process has to be given the one that came back."
            ),
            detail="{connected_as}",
        ),
    },
    "start_up_within_the_deploy_window": {
        "candidate_execution_failed": DID_NOT_RUN,
        "boot_did_not_finish": observation(
            first=(
                "The console returned before the stack was actually up. Its "
                "short timing looked inside the window only because part of "
                "the boot never happened, so there was no box to switch "
                "traffic onto."
            ),
            second=(
                "I checked the connect trace behind that timing. Only "
                "{connected} of {expected} connect steps finished; "
                "`{service}` is the first missing one. The deploy window is "
                "met only when the whole boot finishes inside it."
            ),
            detail="{service}",
        ),
        "deploy_window_overrun": observation(
            first=(
                "A complete boot ran beyond the deploy window, so the traffic "
                "switch could not happen at its scheduled point. The stack did "
                "eventually come up, but not inside the limit this deployment "
                "was given."
            ),
            second=(
                "I timed your build's boot off the console. It took "
                "{elapsed_ticks} ticks against a window of "
                "{deploy_window_ticks}, and one connect step after another is "
                "{one_at_a_time_ticks} of that. We have to be up before the "
                "switch."
            ),
            detail="{elapsed_ticks}",
        ),
        "too_many_connects_at_once": observation(
            first=(
                "The platform trace showed more connect steps in flight than "
                "the warehouse permits for one client. That run crossed the "
                "host's stated limit, whether or not the host happened to "
                "refuse one of those particular handshakes."
            ),
            second=(
                "I counted the platform's in-flight connect trace. At tick "
                "{at} there were {peak_at_once} connect steps running together "
                "where the host allows {max_parallel_starts}: {services}. "
                "That limit is theirs to set, not ours."
            ),
            detail="{peak_at_once}",
        ),
    },
}
