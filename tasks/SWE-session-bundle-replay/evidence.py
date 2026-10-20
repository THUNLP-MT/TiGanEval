'Owner persona, belief, and Observation contexts for SWE-session-bundle-replay.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Rafa, on the customer support desk; he reproduces the notebooks customers send "
    "when a number they published is questioned, and he reads the console log, the "
    "files people send him and the files the desk hands back, not the console's code."
)

USER_BELIEF = (
    "I want to record a console session to one file and open that file here, so that "
    "when a customer's figure is questioned I can rebuild it myself instead of asking "
    "them for screenshots of a notebook that is already gone. Today that costs me a "
    "day per ticket and the customer waits the whole time. Done means I can hand a "
    "client a file that is a truthful record of what their analyst ran and what came "
    "back, and open the file they send me and get the same numbers out of it. One "
    "thing security asked for before any of this leaves the building: our upload "
    "tokens must not be in what we hand over."
)

OBSERVATION_SCENE = "Support desk review of a customer ticket"


def _stopped() -> dict[str, str]:
    'The release session did not produce a complete result.'

    return observation(
        first=(
            "I tried the desk's release session on your build and it did not finish. I did "
            "not have a complete result I could stand behind, so the ticket sat where it was."
        ),
        second=(
            "I ran the release session again and it failed before completing. The last thing "
            "the desk reported was: {error}"
        ),
        detail="{error}",
    )


OBSERVATIONS = {
    "secret_redaction": {
        "candidate_execution_failed": _stopped(),
        "secret_left_in_the_error_text": observation(
            first=(
                "Security pulled back one of the files we sent a client and found our intake "
                "key in it. Not in the code, where I would have looked: in the error the "
                "failed upload came back with. That key is live and it is now on somebody "
                "else's laptop."
            ),
            second=(
                "I recorded the upload session again on your build and read the entry for the "
                "cell that failed: on the {label} one the key is there in {where}, word for word."
            ),
            detail="{where}",
        ),
        "secret_left_in_the_recorded_output": observation(
            first=(
                "The auditors sent the upload session back to us with our own key highlighted "
                "in the middle of it. It is in the part of the file everybody reads first, so "
                "anyone we have ever handed a session to has had it in front of them."
            ),
            second=(
                "I recorded that session again on your build and searched the whole file: the "
                "key is still sitting in {where}."
            ),
            detail="{where}",
        ),
        "redaction_changed_the_record": observation(
            first=(
                "The clinic asked us to check their cleaned session against the original. The "
                "cleaned copy changed material that was not one of the secrets, so I could no "
                "longer stand behind it as a faithful record."
            ),
            second=(
                "I recorded it both ways on your build and lined the two files up side by side: "
                "the material for {label} first differs in {where}."
            ),
            detail="{where}",
        ),
        "unprotected_record_was_still_redacted": observation(
            first=(
                "I made an ordinary recording after the protected export, but that later file "
                "did not match the unfiltered session. I cannot treat a recording as ordinary "
                "if an earlier session's protection changes what it keeps."
            ),
            second=(
                "I repeated the ordinary recording on your build and compared it with the "
                "console: the material for {label} first differs in {where}."
            ),
            detail="{where}",
        ),
    },
    "output_attribution": {
        "candidate_execution_failed": _stopped(),
        "outputs_borrowed_from_another_cell": observation(
            first=(
                "A client came back at us over a file we sent them: one of the entries shows a "
                "line their analyst never got from that cell. They think we edited their "
                "session before handing it over, and I have nothing to say to that."
            ),
            second=(
                "I recorded the ward session on your build and read it entry by entry: the one "
                "for {label} carries output that came off a different cell."
            ),
            detail="{label}",
        ),
        "stdout_carries_the_result": observation(
            first=(
                "I put two runs of a client's analysis next to each other to find where their "
                "number changed, and the comparison was useless. One entry has the cell's own "
                "answer glued onto the end of what it printed, so a changed answer and a "
                "changed log line look exactly alike."
            ),
            second=(
                "I recorded the ward session on your build and looked at the entry for {label}: "
                "what the cell printed has the value it came back with sitting inside it."
            ),
            detail="{label}",
        ),
        "stderr_folded_into_stdout": observation(
            first=(
                "A customer's analyst wrote a warning that two of their cases sat outside the "
                "window. In the file we sent, that warning was not preserved separately as a "
                "warning, and the customer published the figure without it."
            ),
            second=(
                "I recorded the ward session on your build: the warning the {label} cell wrote "
                "is absent from the warning field in its entry."
            ),
            detail="{label}",
        ),
        "recorded_event_does_not_match_the_cell": observation(
            first=(
                "I compared a recorded entry with the cell that produced it and one of its "
                "fields does not match. I cannot stand behind the file as a truthful record "
                "when even one entry says something different from its cell."
            ),
            second=(
                "I recorded the ward session on your build and held it against the console log: "
                "on the entry for {label}, {where} is not what the cell did."
            ),
            detail="{where}",
        ),
    },
    "recorder_lifetime": {
        "candidate_execution_failed": _stopped(),
        "cell_missing_from_the_bundle": observation(
            first=(
                "The session I handed over has a hole in it. One of the analyst's numbered "
                "cells is not in the file, so the reviewer is working from an incomplete record."
            ),
            second=(
                "I ran the desk's session on your build and counted: {cells_recorded} "
                "entries in the file for a session where the analyst ran {cells_run} cells, and "
                "the {label} one is not among them."
            ),
            detail="{cells_recorded}",
        ),
        "cell_recorded_twice": observation(
            first=(
                "A customer opened a file we sent and asked why their analyst appears to run "
                "the same cell again and again. They want to know what we did to their session "
                "before we sent it back."
            ),
            second=(
                "I ran the session on your build and counted the entries: the {label} "
                "cell is in the file {copies} times over."
            ),
            detail="{copies}",
        ),
        "extra_cell_in_the_bundle": observation(
            first=(
                "The file we handed the clinic has work in it that was never part of the "
                "analysis. Their reviewer spent an afternoon trying to account for cells the "
                "analyst does not remember running."
            ),
            second=(
                "I recorded the session on your build and went through it: "
                "{extra_cells} entries in the file are not cells the analyst ran, the {label} "
                "one among them."
            ),
            detail="{extra_cells}",
        ),
        "refused_start_changed_the_recording": observation(
            first=(
                "I tried a start the desk should have refused, but it changed the recording "
                "setup instead of leaving it alone. I could no longer trust which recorder "
                "owned the customer's session."
            ),
            second=(
                "I did it again on your build and compared the state before and after the "
                "refusal. The part that changed was {changed}."
            ),
            detail="{changed}",
        ),
        "refused_start_did_not_raise": observation(
            first=(
                "I tried a start the desk should have refused, but the call returned normally, "
                "so the app told the analyst recording had begun. A quiet refusal is not enough "
                "when the normal return is the app's success signal."
            ),
            second=(
                "I repeated it on your build: the {label} start returned normally and reported "
                "{reported}."
            ),
            detail="{label}",
        ),
        "recording_changed_the_cell": observation(
            first=(
                "A cell that works in the ordinary console changed its result while the recorder "
                "was attached. Recording the session must not alter the analysis it is meant to "
                "observe."
            ),
            second=(
                "I ran the same session with and without the recorder: the {label} cell first "
                "differs in {where}, where the recorded run reported {reported}."
            ),
            detail="{label}",
        ),
        "bundle_the_console_refuses": observation(
            first=(
                "The file we sent a customer will not open in their console. It does not open "
                "in mine on the way back out. As far as they are concerned we sent them a "
                "broken download and wasted two days of their time."
            ),
            second=(
                "I recorded the session on your build and opened the file it wrote: my "
                "own console turns it down and names {fault} as the first thing wrong with it."
            ),
            detail="{fault}",
        ),
    },
    "bundle_admission": {
        "candidate_execution_failed": _stopped(),
        "edited_bundle_ran_to_the_end": observation(
            first=(
                "Someone sent us a session file the desk's format check identifies as faulty, "
                "and the desk ran the whole thing without a word about it. The reviewer then "
                "quoted a number out of a record the desk should have refused."
            ),
            second=(
                "I opened the same file on your build: {cells_executed} cells ran even though "
                "the desk's format check rejects that file."
            ),
            detail="{cells_executed}",
        ),
        "edited_bundle_half_ran": observation(
            first=(
                "A file the desk's format check identifies as faulty ran part way before it was "
                "refused. The reviewer read a value left on the console and published a figure "
                "that came out of part of a session."
            ),
            second=(
                "I opened it on your build and watched it: {cells_executed} cells ran before it "
                "stopped even though the file should have been refused before any ran."
            ),
            detail="{cells_executed}",
        ),
        "load_admitted_a_faulty_file": observation(
            first=(
                "Someone passed us a session file the desk's format check identifies as faulty, "
                "and the loader took it in without a word. It went on to a reviewer as a sound "
                "record of the customer's analysis."
            ),
            second=(
                "I loaded the file on your build a second time and it went through without a "
                "murmur, while the desk's format check comes back with "
                "{fault} against it."
            ),
            detail="{fault}",
        ),
        "sound_bundle_refused": observation(
            first=(
                "The customer's own file, the one their console wrote and nobody has touched, "
                "will not open here at all. I am back to asking them for screenshots, which is "
                "the thing this was meant to stop."
            ),
            second=(
                "I tried it again on your build with {bundle} straight off the ticket, and the "
                "desk still will not run a line of it."
            ),
            detail="{bundle}",
        ),
        "rejection_did_not_name_the_faults": observation(
            first=(
                "A file came back turned down, but the reason did not match what the desk's "
                "format check found. I could not give the customer an accurate account of why "
                "their file was refused."
            ),
            second=(
                "I put the file through your build and wrote down what came back: {reported}. "
                "That does not match the faults reported by the desk's format check."
            ),
            detail="{reported}",
        ),
    },
    "replay_isolation": {
        "candidate_execution_failed": _stopped(),
        "replay_ran_past_the_failed_cell": observation(
            first=(
                "I opened a customer's session with stop-on-error, but the console did not end "
                "in the state of the failing cell. The value I read could not be trusted as the "
                "point where their analysis stopped."
            ),
            second=(
                "I opened the same file on your build and counted {cells_replayed} replay calls. "
                "The console still did not hold the state expected at the failing cell."
            ),
            detail="{cells_replayed}",
        ),
        "replay_stopped_at_a_cell_it_should_have_run": observation(
            first=(
                "I asked the desk to run a customer's session all the way through so I could "
                "see what the end of it looked like, but the console did not rebuild the final "
                "state of that analysis. I could not answer their question from the result."
            ),
            second=(
                "I asked for the whole thing again on your build: the desk made "
                "{cells_replayed} replay calls, but the console still lacked the session's "
                "final state."
            ),
            detail="{cells_replayed}",
        ),
        "replay_cell_count_did_not_match_file": observation(
            first=(
                "The replay made a different number of cell calls from the file and the chosen "
                "stopping policy. That can repeat side effects or leave part of the analysis out."
            ),
            second=(
                "I replayed it again on your build and counted {cells_replayed} cell calls where "
                "the file and stopping policy called for {cells_expected}."
            ),
            detail="{cells_replayed}",
        ),
        "replay_report_did_not_match_execution": observation(
            first=(
                "The receipt returned by replay does not agree with the cells the file and its "
                "stopping policy say were run. I cannot use that receipt to audit the replay."
            ),
            second=(
                "I repeated the replay and copied its receipt exactly: {reported}. It still does "
                "not match the file and stopping policy."
            ),
            detail="{reported}",
        ),
        "replay_took_the_recorded_numbering": observation(
            first=(
                "I opened a customer's file in the middle of my own morning's work and my "
                "console's numbering no longer matched the cells it had actually replayed. The "
                "notes I keep against my own cell numbers stopped matching my screen."
            ),
            second=(
                "I did it again on your build from a console sitting at {counter_before}: after "
                "{cells_replayed} replay calls it reads {counter_after}."
            ),
            detail="{counter_after}",
        ),
        "replay_would_not_open_the_file": observation(
            first=(
                "I had the clinic on the phone and went to open the file their own console "
                "wrote, so I could walk them through where their number came from. Nothing "
                "ran at all. I finished the call asking them for screenshots, with the "
                "customer listening to me do it."
            ),
            second=(
                "I tried the same file again on your build, in a console I was part way "
                "through using: not one cell of it ran, and what came back to me was "
                "{reported}."
            ),
            detail="{reported}",
        ),
        "quiet_replay_numbered_the_console": observation(
            first=(
                "I opened a customer's file the quiet way, so that looking at it would leave my "
                "own session alone, and it did not. My console moved on regardless and the "
                "recording I made straight afterwards is numbered wrong."
            ),
            second=(
                "I opened it the quiet way again on your build, from a console sitting at "
                "{counter_before}, and afterwards it reads {counter_after}."
            ),
            detail="{counter_after}",
        ),
    },
}
