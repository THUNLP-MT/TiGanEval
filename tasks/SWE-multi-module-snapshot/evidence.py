'Owner persona, belief, and Observation contexts for SWE-multi-module-snapshot.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Teo, who owns the plugin sandbox in the metering pipeline. He reads the "
    "console log of a replayed run, what a dump prints when he opens it, and "
    "the total the loader declared for a batch; he does not read the dump "
    "tool's code."
)

USER_BELIEF = (
    "I want a quarter in which a bad batch is a bad batch and I can say what "
    "the sandbox held while it was going wrong. Thursday cost me four hours "
    "because the dump I had did not match the console log beside it, and the "
    "pipeline team has stopped trusting either of them. What I can see is the "
    "console log of a run, what a dump prints when I open it, and the total "
    "the loader declared for the batch. Done, for me, is this: I take a dump "
    "in the middle of a batch, attach it to the ticket, open it on Friday and "
    "argue from it in front of the pipeline team; the debug volume lasts the "
    "week; and when a run has gone bad I can put a dump back and have "
    "everyone accept the sandbox that comes out of it."
)

OBSERVATION_SCENE = "The sandbox owner's review of the console log after a batch has gone wrong"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the console box before this morning's sandbox review "
        "and started the metering batch through it. It stopped part way instead of "
        "running to the end, so there is no console log, no dumps and nothing to "
        "read. I have nothing to tell the pipeline team about the change."
    ),
    second=(
        "I tried it once more, through the same batch, and it stopped part way "
        "there as well. Where the console log should be there is one line: "
        "{error}. Until a plain run goes end to end I cannot judge anything else "
        "about it."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "consistent_cut": {
        "candidate_execution_failed": DID_NOT_RUN,
        "full_capture_not_taken": observation(
            first=(
                "The console asked for a full dump during the batch review and "
                "got an error instead. That leaves the ticket with no recording of "
                "the moment the pipeline team needs us to explain."
            ),
            second=(
                "I repeated the batch on your build. The console offered "
                "{plugins_offered} plugins for `{capture}` and got this instead of "
                "a dump: {error}. The tool still has to produce the dump the "
                "console asks for."
            ),
            detail="{error}",
        ),
        "capture_target_set_mismatch": observation(
            first=(
                "A full dump came back, but it did not describe exactly the sandbox "
                "the console handed to it. Its plugin list does not match what was offered, so "
                "the pipeline team cannot reconstruct the batch from that recording."
            ),
            second=(
                "I checked `{capture}` on your build. The console offered "
                "{plugins_offered} plugins, the dump listed {plugins_in_the_dump}, "
                "and {plugin} was {direction}. A full dump has to cover exactly the "
                "plugins it was handed."
            ),
            detail="{plugin}",
        ),
        "capture_named_wrong_epoch": observation(
            first=(
                "A full dump came back naming a different sandbox epoch from the "
                "one at which the console requested it. Even if its bytes look "
                "plausible, it is a recording of the wrong moment."
            ),
            second=(
                "I checked `{capture}` on your build. The console requested it at "
                "epoch {requested_epoch}, but the dump names epoch "
                "{recorded_epoch}. The epoch on a dump has to be the moment at "
                "which that dump was requested."
            ),
            detail="{recorded_epoch}",
        ),
        "captured_books_do_not_balance": observation(
            first=(
                "I took a dump in the middle of last night's batch and the two "
                "halves of it disagree. The roll-up says one figure, the meter says "
                "another, and between them they are not the batch the loader "
                "declared. That is what cost me Thursday: I cannot tell a "
                "corruption in the pipeline from a corruption in my own dump."
            ),
            second=(
                "I put the same batch through your build and added the two halves "
                "up. The dump comes to {total_in_the_dump} where the loader "
                "declared {declared_total} for that batch. A hand-off takes from "
                "one arena and gives to the other in the same write, so a dump "
                "taken while the batch is running is never short and never over."
            ),
            detail="{total_in_the_dump}",
        ),
        "capture_read_across_epochs": observation(
            first=(
                "One of the dumps says it records one sandbox epoch, but an arena "
                "inside it is not what the sandbox held at that epoch. The pipeline "
                "team cannot tell which state the dump is meant to describe."
            ),
            second=(
                "I replayed the batch on your build. The dump names epoch "
                "{recorded_epoch}, the sandbox was at {epoch_after_the_walk} by the "
                "time the walk came back, and its arena for {plugin} differs from "
                "the sandbox history at {recorded_epoch}. The recorded epoch and "
                "the arenas in a dump have to describe the same moment."
            ),
            detail="{plugin}",
        ),
    },
    "capture_holds_still": {
        "candidate_execution_failed": DID_NOT_RUN,
        "capture_followed_the_host": observation(
            first=(
                "I opened the same dump at two different console steps and one of "
                "its arenas had changed between the readings. A dump attached to a "
                "ticket has to keep describing the moment it was taken."
            ),
            second=(
                "I opened the dump from your build again at `{read_again_at}`. The "
                "arena for {plugin} differs from its first reading, so the dump is "
                "following the sandbox instead of holding its recorded state."
            ),
            detail="{plugin}",
        ),
        "capture_handed_out_the_stored_buffer": observation(
            first=(
                "I wrote over an arena buffer returned by a dump and then asked the "
                "same dump for that arena again. It returned my scribble instead of "
                "the recorded bytes, so the original state was no longer available."
            ),
            second=(
                "I did it deliberately on your build: wrote over "
                "{bytes_written_over} bytes of what the dump handed me for "
                "{plugin}, then asked the dump for that arena again and got my own "
                "scribble back. What a dump hands out has to be the reader's to "
                "spoil."
            ),
            detail="{bytes_written_over}",
        ),
    },
    "incremental_chain": {
        "candidate_execution_failed": DID_NOT_RUN,
        "incremental_not_taken": observation(
            first=(
                "The console took a baseline dump and then returned an error in "
                "place of a later one. That leaves a hole in the chain at the point "
                "the pipeline team needs to inspect."
            ),
            second=(
                "I repeated the batch on your build. The console asked for a dump "
                "after `{baseline}`, offered it {plugins_offered} plugins, and got "
                "this instead: {error}. A later dump still has to come back for the "
                "plugins the console hands it."
            ),
            detail="{error}",
        ),
        "incremental_target_set_mismatch": observation(
            first=(
                "One of the later dumps in the chain does not describe exactly the "
                "sandbox the console handed to it. The chain therefore has no "
                "complete picture of that point in the batch."
            ),
            second=(
                "I checked the dump after `{baseline}`. The console offered "
                "{plugins_offered} plugins, the dump listed {plugins_in_the_dump}, "
                "and {plugin} was {direction}. A later dump still has to read back "
                "as every plugin it was taken over."
            ),
            detail="{plugin}",
        ),
        "incremental_named_wrong_epoch": observation(
            first=(
                "A later dump in the chain names a different sandbox epoch from "
                "the one at which the console requested it. That makes the chain "
                "point at the wrong moment in the batch."
            ),
            second=(
                "I checked `{capture}` after `{baseline}`. The console requested "
                "it at epoch {requested_epoch}, but the dump names epoch "
                "{recorded_epoch}. Every link has to name its own request moment."
            ),
            detail="{recorded_epoch}",
        ),
        "chain_reconstruction_mismatch": observation(
            first=(
                "A later dump in the chain does not read back as the sandbox state "
                "at the epoch it names. It contains plausible-looking arena bytes "
                "that were not in the sandbox at that point."
            ),
            second=(
                "I replayed the batch on your build and compared the later dump with "
                "the sandbox history at its recorded epoch. The arena for {plugin} "
                "in the dump after `{baseline}` is not the arena recorded there."
            ),
            detail="{plugin}",
        ),
        "delta_not_against_reconstructed_baseline": observation(
            first=(
                "For at least one plugin, what a later dump stores is not the byte "
                "change that occurred between its baseline and its own recorded "
                "state. The persisted chain therefore describes a different change."
            ),
            second=(
                "I compared the stored delta with the replayed change. For {plugin} "
                "after `{baseline}`, the dump reports {changed_bytes_stored} changed "
                "bytes and the replay reports {changed_bytes_in_the_arena}; the two "
                "delta structures are not the same."
            ),
            detail="{changed_bytes_stored}",
        ),
        "incremental_stored_the_whole_arena": observation(
            first=(
                "I found a later dump storing a full arena for a plugin instead of "
                "a delta. Repeating that across the dumps we take each day defeats "
                "the reason we use incrementals on the debug volume."
            ),
            second=(
                "I looked at what your build writes for the dumps after the first "
                "one. For {plugin} it wrote down the whole arena, {bytes_stored} "
                "bytes of it, with nothing said about what had changed since "
                "`{baseline}`. After the first dump we can afford the difference and "
                "nothing more."
            ),
            detail="{bytes_stored}",
        ),
    },
    "restore_all_or_nothing": {
        "candidate_execution_failed": DID_NOT_RUN,
        "refused_restore_wrote_anyway": observation(
            first=(
                "We attempted a restore the sandbox could not honour, but it changed "
                "at least one arena anyway. The pre-restore state we were trying to "
                "explain has been overwritten even though the recovery was invalid."
            ),
            second=(
                "I repeated `{attempt}` on your build. The blocker was {blocked_by}: "
                "{reason}. Even so, write sequences moved for {plugins_written} of "
                "the {plugins_in_the_dump} plugins, starting with {plugin}. A restore "
                "that cannot be honoured has to leave every arena unchanged."
            ),
            detail="{plugins_written}",
        ),
        "detached_target_accepted": observation(
            first=(
                "A restore claimed success even though one of the plugin objects the "
                "console offered had already been unloaded. The recovery did not "
                "describe the sandbox that was actually running, and nobody was "
                "warned."
            ),
            second=(
                "I repeated `{attempt}` on your build. It accepted {plugin} even "
                "though {reason}. A restore has to refuse before writing when one "
                "of its targets is no longer loaded."
            ),
            detail="{plugin}",
        ),
        "foreign_target_accepted": observation(
            first=(
                "A restore claimed success after the console offered a lookalike "
                "plugin object that the host had never loaded. The lookalike was "
                "changed while the live plugin stayed in its bad state."
            ),
            second=(
                "I repeated `{attempt}` on your build. It accepted {plugin} even "
                "though {reason}. Matching names and layouts do not make an "
                "unloaded object part of the running sandbox."
            ),
            detail="{plugin}",
        ),
        "mismatched_target_accepted": observation(
            first=(
                "A restore reported success even though one of its targets could "
                "not accept the dump as recorded. The resulting sandbox cannot be "
                "trusted, and nothing warned the pipeline team."
            ),
            second=(
                "I watched it again on your build. At `{attempt}` it went ahead over "
                "{plugin}, where the trouble is that {reason}, and came back without "
                "a word. A restore that cannot be honoured has to say so and leave "
                "the sandbox alone."
            ),
            detail="{plugin}",
        ),
        "restore_reported_wrong_reason": observation(
            first=(
                "The restore stopped, but its refusal did not identify the "
                "condition that blocked it. The on-call cannot tell whether the "
                "target disappeared, changed shape or simply ran out of room."
            ),
            second=(
                "At `{attempt}` the blocker for {plugin} was "
                "{expected_reason}, but the structured reason was "
                "{reported_reason} for {reported_plugin}. A refusal has to name "
                "the blocker the console can act on."
            ),
            detail="{reported_reason}",
        ),
        "sound_restore_refused": observation(
            first=(
                "The recovery drill would not run at all this morning. The sandbox "
                "was in the state it is meant to be in for the drill, the dump was "
                "the right dump, and the tool refused to put it back. We had to "
                "leave the bad batch where it was and tell the pipeline team we "
                "could not recover it."
            ),
            second=(
                "I tried it once more on your build. At `{attempt}` all "
                "{plugins_loaded} plugins were loaded, every one the dump names was "
                "there under the layout it was dumped under and with room for what "
                "the dump holds for it, and it still came back refusing. A restore a "
                "sandbox can take has to go through."
            ),
            detail="{attempt}",
        ),
        "restore_touched_the_wrong_plugins": observation(
            first=(
                "The write counts in the console log do not match the plugins in "
                "the dump we restored. The pipeline team cannot treat that log as "
                "a record of exactly what the recovery put back."
            ),
            second=(
                "I counted the writes on your build. At `{attempt}` the arena for "
                "{plugin} was written {writes_to_that_plugin} times, across "
                "{plugins_written} plugins in all, against a dump holding "
                "{plugins_in_the_dump}. One recovery is one write into each plugin "
                "the dump holds."
            ),
            detail="{writes_to_that_plugin}",
        ),
    },
    "restored_arena_exact": {
        "candidate_execution_failed": DID_NOT_RUN,
        "post_capture_bytes_survived": observation(
            first=(
                "We put yesterday's dump back after a bad run and the plugin came up "
                "with the bad run's numbers still hanging off the end of it. It "
                "looks exactly like the memory corruption we are hunting, except "
                "that we put it there ourselves, and it took two people half a day "
                "to work that out."
            ),
            second=(
                "I ran the drill again on your build. After `{attempt}` the arena "
                "for {plugin} is {bytes_after_the_restore} bytes where the dump "
                "recorded {bytes_recorded}, so {bytes_left_over} bytes of the bad "
                "run are still sitting past the end of what we put back."
            ),
            detail="{bytes_left_over}",
        ),
        "restored_arena_differs": observation(
            first=(
                "The recovery did not bring the sandbox back. The arenas after it "
                "are not the arenas the dump has, so the batch we are supposed to be "
                "looking at is not the one the console is showing us. The pipeline "
                "team asked me which state they were debugging and I could not tell "
                "them."
            ),
            second=(
                "I compared the sandbox after `{attempt}` against the dump we had "
                "put back. The arena for {plugin} is not what the dump holds for it, "
                "{bytes_after_the_restore} bytes against the {bytes_recorded} "
                "recorded. After a recovery the sandbox has to be the dump."
            ),
            detail="{plugin}",
        ),
    },
}
