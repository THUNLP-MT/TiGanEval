'Owner persona, belief, and Observation contexts for SWE-entity-snapshot-rollback.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Mira, the gameplay engineer who owns world state on the editor team. She "
    "sits with the designers while they dress a set and reads the outliner, the "
    "change panel and the status bar; she does not read the checkpoint code."
)

USER_BELIEF = (
    "I want a fortnight of set dressing in which nobody loses work to the "
    "Revert button. Last night's playtest cost us forty minutes because Ana "
    "reverted a bad batch paint and the set came back half wrong, so she closed "
    "the level without saving and two of us dressed it again this morning. The "
    "designers have started taking checkpoints and then not daring to use them, "
    "which is worse for us than not having the feature at all. Done, for me, is "
    "a run of dressing sessions in which a designer takes a checkpoint, works "
    "on, presses Revert and gets back the set she checkpointed, and in which she "
    "trusts the panel beside the button enough to read it first."
)

OBSERVATION_SCENE = "Editor build review after a set-dressing session"


DID_NOT_RUN = observation(
    first=(
        "I put your build on the editor box before this morning's review and "
        "started Ana's set-dressing session through it. It stopped part way "
        "instead of running to the end, so there is no level to look at, no "
        "status bar and no panel. I have nothing to tell the designers about the "
        "change."
    ),
    second=(
        "I tried again with the cleanup session and it stopped part way there "
        "too. Where the level should be, the editor log holds one line: {error}. "
        "Until a plain session runs end to end I cannot judge anything else about "
        "the change."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "isolated_checkpoint_value": {
        "candidate_execution_failed": DID_NOT_RUN,
        "editor_step_failed": observation(
            first=(
                "Ana was halfway through dressing the loading bay when the editor "
                "threw an error at her instead of finishing what she had asked "
                "for. The level sat where it was, she closed it and started again "
                "from the last save, and that was two hours of her afternoon."
            ),
            second=(
                "I put the same session through again on your build and it came "
                "apart in the same place, at `{label}`: the editor raises there "
                "instead of completing, and nothing after it happens at all. "
                "Every step a designer asks for has to come back to her."
            ),
            detail="{label}",
        ),
        "checkpoint_moved_with_the_level": observation(
            first=(
                "Ana checkpointed the set, moved a couple of things, and reverted, "
                "and the revert handed her back what she had just done rather than "
                "what she had checkpointed. The checkpoint is holding nothing of "
                "its own; it follows the level around. She has stopped taking them."
            ),
            second=(
                "I watched the file list beside her while she worked on your "
                "build. At `{label}` the digest next to the checkpoint she had "
                "already taken moved along with the level, and she had not "
                "reverted to that file at any point before it. A checkpoint has "
                "to hold the level as it stood when she pressed the button and "
                "stay that way."
            ),
            detail="{label}",
        ),
        "revert_left_the_level_wired_to_the_checkpoint": observation(
            first=(
                "This is the one Ana keeps hitting. She reverts once and it looks "
                "right, then she carries on working and the checkpoint she "
                "reverted to quietly turns into whatever she is doing now. The "
                "next revert gives her back the mess she was trying to leave."
            ),
            second=(
                "I stepped through it on your build. Up to the first revert the "
                "checkpoint stays put; from `{label}` onwards everything she does "
                "to the level turns up in that checkpoint's digest as well. "
                "Putting the level back must not leave the two wired together."
            ),
            detail="{label}",
        ),
        "second_revert_gave_a_different_level": observation(
            first=(
                "A designer reverted to the same checkpoint twice in one sitting "
                "and got two different sets out of it. She does not know which one "
                "she is looking at now, and neither do I. Nobody is going to press "
                "a button that does something different every time."
            ),
            second=(
                "I did it myself on your build, twice to the same file with a "
                "nudge in between. The level after `{second_label}` is not the "
                "level the first revert gave her. Reverting to one file has to "
                "land on one level, however many times she does it."
            ),
            detail="{second_label}",
        ),
        "revert_did_not_reproduce_the_checkpoint": observation(
            first=(
                "Ana reverted to a checkpoint she had taken ten minutes earlier "
                "and the set came back close but not right. She spent the rest of "
                "the afternoon holding it against a screenshot to work out what "
                "was still wrong with it."
            ),
            second=(
                "I checked it the quick way this time. Once the revert was done "
                "the status bar read something other than {recorded_digest}, which "
                "is what that level came to when she took the file. Those two "
                "have to agree the moment the revert finishes."
            ),
            detail="{recorded_digest}",
        ),
    },
    "exact_prop_restore": {
        "candidate_execution_failed": DID_NOT_RUN,
        "revert_left_a_surplus_trait": observation(
            first=(
                "This is the one that cost us the playtest. Ana reverted after the "
                "bad batch paint and everything the paint had put on the props was "
                "still on them afterwards. The set looked reverted and was not, "
                "which is worse than the revert doing nothing at all."
            ),
            second=(
                "I ran her session again on your build and went through the props "
                "one at a time. After the revert they are still carrying `{key}`, "
                "which the paint put on them after she took the checkpoint. "
                "Reverting has to take things off as well as put them back."
            ),
            detail="{key}",
        ),
        "revert_dropped_a_recorded_trait": observation(
            first=(
                "A designer reverted and came back to a set that had lost things. "
                "Props that had names and tints on them before the checkpoint came "
                "back bare, and she had to redo work the checkpoint was there to "
                "protect."
            ),
            second=(
                "I went through the props after the revert on your build. `{key}` "
                "is in the checkpoint for that prop and it is not on the prop "
                "afterwards. Everything the file records has to be there once the "
                "revert is done."
            ),
            detail="{key}",
        ),
        "revert_turned_a_tag_into_data": observation(
            first=(
                "The outliner has gone strange after a revert. Props that were "
                "marked show up under the marked filter as though the mark were "
                "something else, and the batch tools step over them. A designer "
                "asking for everything marked gets an empty selection."
            ),
            second=(
                "I looked at one of them after the revert on your build. `{key}` "
                "is a mark on this project, and it came back carrying an empty "
                "payload instead of simply being set. A mark has to come back as a "
                "mark."
            ),
            detail="{key}",
        ),
        "revert_kept_the_new_value": observation(
            first=(
                "Ana reverted a repaint and the props kept the new colour. Not all "
                "of them, so she did not notice until the lighting pass, and the "
                "whole bay had to be dressed again the next morning."
            ),
            second=(
                "I put the same repaint through on your build and held the props "
                "against the checkpoint afterwards. {prop} still has what the "
                "repaint gave it rather than what the file records. Where the file "
                "has a value, the prop has to end up with that value."
            ),
            detail="{prop}",
        ),
    },
    "preserved_prop_identity": {
        "candidate_execution_failed": DID_NOT_RUN,
        "destroyed_prop_not_brought_back": observation(
            first=(
                "A designer deleted a pallet stack during a cleanup pass, changed "
                "her mind, and reverted. The pallet stack did not come back. "
                "Everything else did, so she took the revert for a success and "
                "only found the hole in the set two days later in review."
            ),
            second=(
                "I ran the cleanup session again on your build. {prop} is in the "
                "checkpoint and it is not in the level after the revert. A prop "
                "that was there when she pressed the button has to be there again "
                "afterwards."
            ),
            detail="{prop}",
        ),
        "prop_came_back_under_a_new_id": observation(
            first=(
                "The revert brought a deleted prop back, but not as itself. The "
                "animation track that was pointing at it is pointing at nothing "
                "now, and the level we saved afterwards has a dangling reference "
                "in it that only shows up when the level loads."
            ),
            second=(
                "I followed it through on your build. It came back in slot "
                "{now_slot} rather than the slot it had when the checkpoint was "
                "taken, so nothing that referred to it finds it any more. A prop "
                "has to come back as the same prop and not as a copy of it."
            ),
            detail="{now_slot}",
        ),
        "surplus_prop_survived_the_revert": observation(
            first=(
                "Ana reverted a cleanup pass and the stand-in crate she had "
                "dropped in during that pass was still sitting in the middle of "
                "the bay afterwards. She deleted it by hand, reverted again for "
                "something else, and it came back."
            ),
            second=(
                "I ran the same session on your build and looked at what is in the "
                "level once the revert has finished. {prop} is still there, and it "
                "went in after the checkpoint was taken. Anything added after the "
                "checkpoint has to be gone when she reverts to it."
            ),
            detail="{prop}",
        ),
        "link_points_somewhere_else": observation(
            first=(
                "This is the one that frightens me. A designer reverted after "
                "deleting a pallet and the crate that used to sit on it came back "
                "parented onto something else entirely. She moved that parent "
                "later in the day and the crate went with it, right across the "
                "level, and the save has it that way."
            ),
            second=(
                "I traced it on your build after the revert. The crate is hanging "
                "off {now_pointing_at}, which is not what the checkpoint has it "
                "hanging off. A link has to come back pointing at the same prop it "
                "pointed at when the checkpoint was taken."
            ),
            detail="{now_pointing_at}",
        ),
        "recorded_link_missing": observation(
            first=(
                "After a revert half the set is loose. Props that were parented "
                "before the checkpoint are sitting at the top of the outliner on "
                "their own, and moving the thing they used to hang off leaves them "
                "behind in mid air."
            ),
            second=(
                "I held the outliner against the checkpoint on your build. The "
                "file has that prop linked to {target} and after the revert the "
                "link is not there. Every link the file records has to exist again "
                "once the revert is done."
            ),
            detail="{target}",
        ),
        "link_recorded_twice": observation(
            first=(
                "The outliner is showing props twice under one parent after a "
                "revert, and deleting the parent only takes one of them with it. "
                "The designers have started reverting twice on purpose to see "
                "whether it gets worse."
            ),
            second=(
                "It does get worse. On your build the same link stands {copies} "
                "times over after the revert where the checkpoint has it once. One "
                "link in the file is one link in the level."
            ),
            detail="{copies}",
        ),
        "session_entity_disturbed": observation(
            first=(
                "A designer reverted with a group of props picked out and lost the "
                "lot: the props she had picked, the tool she had active, the pivot "
                "she had set. She had spent ten minutes building that up to do one "
                "operation with it."
            ),
            second=(
                "I reproduced it on your build. Her `Selection` is not what it was "
                "before she pressed the button. What she is holding belongs to her "
                "session rather than to the level, so a revert has to leave it "
                "alone."
            ),
            detail="Selection",
        ),
    },
    "refused_revert_leaves_level": {
        "candidate_execution_failed": DID_NOT_RUN,
        "broken_checkpoint_left_the_level_half_changed": observation(
            first=(
                "Ana opened a checkpoint of the whole set from an older session on "
                "the level she had in front of her, pressed Revert to checkpoint, "
                "and the editor made a mess of it. Part of what the file named "
                "went back on and the rest of the set stayed where she had it. "
                "There is no save and no checkpoint anywhere that matches what she "
                "was looking at, so she could not get back."
            ),
            second=(
                "I put that same whole-set file through on your build and watched "
                "the outliner while I pressed the button. What the editor cannot "
                "do with the file is this: {fault}. It went at the level anyway: "
                "some of the props the file names snapped back to it and the rest "
                "of the set stayed where I had dressed it, so what I was left "
                "looking at was neither the set I pressed the button on nor the "
                "set the file holds. A file it cannot carry out has to leave the "
                "level exactly as it was."
            ),
            detail="{fault}",
        ),
        "broken_checkpoint_applied": observation(
            first=(
                "The editor is supposed to tell a designer when a checkpoint of "
                "the whole set will not go onto the level she has open, and it is "
                "telling nobody anything. It goes ahead, and she finds out days "
                "later from a level that will not load."
            ),
            second=(
                "I tried Revert to checkpoint on your build with a whole-set file "
                "I knew would not fit: {fault}. The editor took it and carried on "
                "as though nothing were wrong. A file it cannot carry out has to "
                "be refused before anything in the level is touched."
            ),
            detail="{fault}",
        ),
        "refusal_used_the_wrong_error": observation(
            first=(
                "The editor is throwing raw errors at designers again. Ana got a "
                "crash dialog out of an old whole-set checkpoint, the level closed "
                "on her, and she lost everything since her last save. The editor "
                "is meant to catch this one and tell her nothing happened."
            ),
            second=(
                "I tried Revert to checkpoint on your build with that file and "
                "read what came out: {error}. The editor cannot tell that apart "
                "from a genuine crash, so it closes the level on her. A revert it "
                "will not carry out has to refuse in the way the editor already "
                "knows how to catch."
            ),
            detail="{error}",
        ),
        "good_checkpoint_refused": observation(
            first=(
                "Now nothing reverts at all. A designer takes a checkpoint of the "
                "set, changes one prop, presses Revert to checkpoint, and the "
                "editor tells her nothing happened. The feature is switched off in "
                "practice and she is back to saving copies of the level by hand."
            ),
            second=(
                "I tried it myself on your build with a whole-set checkpoint that "
                "plainly fits the level in front of it, and the editor refused "
                "with {error}. A file that fits the level has to go on."
            ),
            detail="{error}",
        ),
        "broken_prop_file_left_the_prop_half_changed": observation(
            first=(
                "Ana kept yesterday's checkpoint of one prop on its own and "
                "pressed Revert on that prop this morning, on a set two of the "
                "others had been dressing overnight. The editor part-did it. That "
                "one prop came back neither the way she had it nor the way its "
                "file has it, the status bar moved, and nothing on disk matches "
                "the set she is looking at now."
            ),
            second=(
                "I opened yesterday's file for {prop} on this morning's set on "
                "your build and kept that prop selected while I pressed the "
                "button. What the editor cannot do with that file is this: "
                "{fault}. It went at the prop anyway: part of what the file "
                "records was put back on {prop} and the rest of it stayed as "
                "this morning's dressing had left it, so the prop matched "
                "neither its own file nor the set I pressed the button on. A "
                "one-prop file it cannot carry out has to leave that prop "
                "exactly as it was."
            ),
            detail="{fault}",
        ),
        "broken_prop_file_applied": observation(
            first=(
                "The editor never tells a designer that yesterday's file for one "
                "prop will not go back onto this morning's set. She picks the "
                "prop, presses Revert on it, nothing warns her, and she finds out "
                "days later from a level that will not load."
            ),
            second=(
                "I tried it on your build with yesterday's file for {prop} against "
                "this morning's set: {fault}. The editor took it and carried on as "
                "though nothing were wrong. A one-prop file it cannot carry out "
                "has to be refused before that prop is touched."
            ),
            detail="{fault}",
        ),
        "prop_refusal_used_the_wrong_error": observation(
            first=(
                "The editor threw a raw error at a designer reverting a single "
                "prop. Ana pressed Revert on one prop with yesterday's file for "
                "it, got a crash dialog instead of a word about the file, and the "
                "level closed on her with everything since her last save in it."
            ),
            second=(
                "I did the same on your build with yesterday's file for {prop} and "
                "read what came out: {error}. The editor cannot tell that apart "
                "from a genuine crash, so it closes the level on her. A one-prop "
                "revert it will not carry out has to refuse in the way the editor "
                "already knows how to catch."
            ),
            detail="{error}",
        ),
        "good_prop_file_refused": observation(
            first=(
                "Reverting one prop has stopped working altogether. A designer "
                "checkpoints a single prop, changes it, presses Revert on that "
                "prop while everything around it is still exactly where it was, "
                "and the editor tells her nothing happened. She is back to undoing "
                "by hand and counting the steps."
            ),
            second=(
                "I tried it myself on your build with the file for {prop}, on a "
                "set that still holds everything that file names, and the editor "
                "refused with {error}. A one-prop file the level can take has to "
                "go on."
            ),
            detail="{error}",
        ),
    },
    "canonical_change_report": {
        "candidate_execution_failed": DID_NOT_RUN,
        "panel_report_wrong_shape": observation(
            first=(
                "The change panel is blank. A designer opens it before deciding "
                "whether to revert and there is nothing in it to read, whatever "
                "state the level is in, so she has gone back to guessing."
            ),
            second=(
                "I looked at what the panel is being handed on your build: "
                "{problem}. The panel renders three lists, so what comes back has "
                "to hold all three of them and nothing else."
            ),
            detail="{problem}",
        ),
        "panel_flagged_an_unchanged_prop": observation(
            first=(
                "The panel cries wolf. A designer opens it on a set she has not "
                "touched since the checkpoint and it lists things as changed "
                "anyway. Two of them have stopped opening it, which means they are "
                "reverting blind."
            ),
            second=(
                "I opened the panel on your build against a file that holds "
                "exactly the level in front of it, written down by a different "
                "route. It listed {listed}. Nothing differs between those two, so "
                "the panel has to come up empty."
            ),
            detail="{listed}",
        ),
        "panel_missed_a_change": observation(
            first=(
                "The panel is telling designers a set is clean when it is not. Ana "
                "read it, took it that a revert would cost her nothing, reverted, "
                "and lost an hour of work the panel had never mentioned."
            ),
            second=(
                "I held the panel against the set on your build. It says nothing "
                "about {missing}, which has changed since the checkpoint. "
                "Everything that differs has to be in the panel."
            ),
            detail="{missing}",
        ),
        "panel_reported_a_change_that_is_not_there": observation(
            first=(
                "The panel is padding its list. It names props alongside the ones "
                "that really did change, and a designer reading it cannot tell "
                "which entries are real, so she walks the whole set by hand "
                "anyway."
            ),
            second=(
                "I read it against the set on your build. It lists {extra}, and "
                "nothing about them has moved since the checkpoint. The panel has "
                "to name what differs and stop there."
            ),
            detail="{extra}",
        ),
        "panel_rows_out_of_order": observation(
            first=(
                "The panel is unreadable on a big set. The entries come out in "
                "whatever order the editor happened to walk the level in, so a "
                "designer scanning a list of forty cannot find the one she is "
                "after and cannot hold two openings of it side by side."
            ),
            second=(
                "I opened it twice on your build and read the entries out: "
                "{listed}. They are not in order, so the same panel on the same "
                "set does not look the same twice. The lists have to come out "
                "sorted."
            ),
            detail="{listed}",
        ),
    },
}
