'Owner persona, belief, and Observation contexts for SWE-encrypted-backup-pipeline.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Anneke, the operations engineer who owns the nightly database backups. She "
    "reads the job's morning log, the two destination listings and the quarterly "
    "drill sheet, and she opens an object herself when she wants to be sure; she "
    "does not read the job's code."
)

USER_BELIEF = (
    "What I want is a year in which we can put our hands on any night we are "
    "still holding. The audit closed against us because everything the job has "
    "sent offsite since the filer went in is a plain compressed dump that anyone "
    "with the vault can open, and the remediation date is the end of the month, "
    "so the dump has to be sealed before it leaves the host. What I can see is "
    "the morning log, what the two destinations are listing, and what Rob writes "
    "on the drill sheet each quarter; the drill is the only thing that has ever "
    "told us an archive is real, and the window still has the nights from before "
    "the move on it, which the old archiver sealed and nobody is going back over. "
    "Done, for me, is an auditor who cannot open one of our objects and a quarter "
    "in which Rob opens whatever night he picks and gets a database out of it."
)

OBSERVATION_SCENE = "Anneke's morning review of the archive log, the two listings and the drill sheet"


DID_NOT_RUN = observation(
    first=(
        "I put your job on the console box this morning and started the recorded "
        "nights through it. It stopped part way instead of running to the end, so "
        "there is no log for the run, nothing in the two listings to look at and "
        "nothing for the drill to pick from. I have nothing to take back to the "
        "audit."
    ),
    second=(
        "I tried it once more from the top and it stopped part way there too. "
        "Where the morning log should be, the console has one line: {error}. "
        "Until a plain stretch of nights runs end to end I cannot judge anything "
        "else about it."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "published_object_restores": {
        "candidate_execution_failed": DID_NOT_RUN,
        "restore_path_would_not_open_it": observation(
            first=(
                "I ran the nights through your job on the console box and then did "
                "what Rob does: took one of the objects it had put in the vault and "
                "started the runbook on it. The first step would not take the object "
                "at all. Whatever is going into the vault now, the way back in is "
                "shut, and the way back in is the entire point of the exercise."
            ),
            second=(
                "I took the sheet back to the vault and went at another night off "
                "that run rather than the one I had picked. The first step stops on "
                "it too, with {diagnosis}, and I have nothing from that run I could "
                "get a database out of."
            ),
            detail="{diagnosis}",
        ),
        "the_recovered_stream_is_not_compressed": observation(
            first=(
                "The first step of the runbook went through on your build and the "
                "second one stopped dead: the decompressor will not read what came "
                "out of it. Rob had a file on the laptop and nothing he could do "
                "with it, and the vault's storage line went up on the same nights."
            ),
            second=(
                "I measured one of them off the run. The object your job wrote for "
                "{night} is {handed_bytes} bytes and the dump the database made that "
                "night is {dump_bytes}. We sized the window on the archives coming "
                "out at about a third of the dump, and the decompressor is the "
                "second thing the runbook does."
            ),
            detail="{handed_bytes}",
        ),
        "restored_bytes_are_not_the_dump": observation(
            first=(
                "The drill went all the way through on your build and what came out "
                "will not load. Rob had a file of roughly the right size on the "
                "laptop and the scratch database threw it out on the first "
                "statement, so we still cannot show anyone that a night comes back."
            ),
            second=(
                "I ran it again and put what came back next to the dump the database "
                "made that night: {recovered_bytes} bytes against {dump_bytes}, and "
                "they are not the same file. What goes into the vault has to come "
                "back out of it as the dump that went in."
            ),
            detail="{recovered_bytes}",
        ),
    },
    "destination_inventory_conserved": {
        "candidate_execution_failed": DID_NOT_RUN,
        "object_left_after_a_key_failure": observation(
            first=(
                "There was a night with no usable key on it and I only found out "
                "because I was reading the run by hand. Both listings had a row for "
                "that night, so the missing-backup alert never fired and nobody was "
                "paged. That is a night we do not have and did not know we did not "
                "have."
            ),
            second=(
                "I counted what your job left behind on that night: {objects_left} "
                "objects across the two destinations, {stored_bytes} bytes in the "
                "one I opened. The alert reads the listing and nothing else, so a "
                "row there is a night as far as anything we watch is concerned."
            ),
            detail="{objects_left}",
        ),
        "destination_opened_without_one_usable_key": observation(
            first=(
                "The destination session log shows the job opened an upload on "
                "a night whose key configuration did not yield one usable key. "
                "Even if the object is deleted afterwards, the job touched the "
                "retention window before it knew it could make an archive."
            ),
            second=(
                "I replayed that night and counted {objects_opened} destination "
                "sessions opened while the key configuration was {key_problem}; "
                "the first was at {destination}. Key resolution has to finish "
                "before any destination is opened."
            ),
            detail="{objects_opened}",
        ),
        "object_left_after_a_write_failed": observation(
            first=(
                "The vault turned down a write part way through a night and we came "
                "out of it with the filer holding that night and the vault holding "
                "nothing. The contract is two copies and retention is counted on the "
                "vault, so we are carrying a night we cannot actually produce."
            ),
            second=(
                "I read the run back. {refused_by} was the end that stopped, and "
                "afterwards the night was still sitting at the other one as "
                "`{object}`. A night that cannot get into both places has to leave "
                "the window the way it found it."
            ),
            detail="{refused_by}",
        ),
        "object_finalized_before_all_destinations_read_back": observation(
            first=(
                "The event order shows one copy was finalized before the final "
                "stored bytes at every destination had been read back. Finalize "
                "publishes a backup, so a refusal at the later destination would "
                "make a failed night visible as a good one for part of the run."
            ),
            second=(
                "At the first finalize for {night}, only "
                "{destinations_verified} of {destinations_required} destinations "
                "had a successful read-back after their final write; "
                "{missing_destination} had not. Neither copy can be finalized "
                "until both have reached that point."
            ),
            detail="{destinations_verified}",
        ),
        "night_missing_from_a_destination": observation(
            first=(
                "I do the monthly reconciliation against the two listings and a "
                "night that should be at both ends is at one of them. Nothing was "
                "wrong with that night — the key was where it always is and neither "
                "end refused anything — and we are contracted for two copies, so "
                "that is a night we are carrying on paper."
            ),
            second=(
                "I went through your build night by night. On {night} there was "
                "nothing wrong at the two ends of it and {destination} is holding "
                "{objects_found} objects for that night. A night that can go to "
                "both places has to be at both places, whatever the row says."
            ),
            detail="{objects_found}",
        ),
        "object_left_open": observation(
            first=(
                "Finance sent the vault's session report round with our line "
                "highlighted again. We are being billed for upload sessions that "
                "were started and never ended, and I am the one who has to account "
                "for each of them at the end of the month."
            ),
            second=(
                "I ran the nights against your build and read the session report off "
                "it: {still_open} sessions left open at {destination}, `{object}` "
                "among them. Anything we open has to be ended the same night."
            ),
            detail="{still_open}",
        ),
    },
    "report_equals_restorable_state": {
        "candidate_execution_failed": DID_NOT_RUN,
        "no_report_for_the_night": observation(
            first=(
                "The scheduler came back with an error instead of a row for one of "
                "the nights, so that night is not in the morning log at all. The log "
                "is what I read at eight and what I hand the auditor, and a night "
                "that is not in it is a night nobody has looked at."
            ),
            second=(
                "I ran the nights again and caught the line the scheduler got on "
                "{night}: {diagnosis}. Whatever a night does, it has to end with a "
                "row I can file."
            ),
            detail="{diagnosis}",
        ),
        "reported_complete_without_a_published_object": observation(
            first=(
                "The morning log calls a night completed, but one destination's "
                "listing has no published object for it. A completed row has to "
                "describe what both destinations actually hold."
            ),
            second=(
                "For {night}, {destination} has {objects_found} finalized objects "
                "while the scheduler row says completed. With no published object "
                "there is nothing for the drill to read back."
            ),
            detail="{objects_found}",
        ),
        "reported_complete_but_not_restorable": observation(
            first=(
                "This is the one that frightens me. The log has a night as done, the "
                "listing has an object for it, and when I pulled that object down "
                "and worked through the runbook there was no dump at the far end. "
                "Every single thing we watch said that night was fine."
            ),
            second=(
                "I pulled it down again off your build and looked at what "
                "{destination} is actually holding for {night}: {stored_bytes} "
                "bytes, and the runbook stops on it. The filer takes every write and "
                "tells us nothing is wrong. Done has to be something we measured on "
                "what is in there, not on what we sent."
            ),
            detail="{stored_bytes}",
        ),
        "usable_night_reported_as_lost": observation(
            first=(
                "Your build called an ordinary night a loss. There was nothing wrong "
                "with it, the key was where it always is and both destinations took "
                "it, and I spent the morning of the standup working out whether we "
                "had really lost a night of orders."
            ),
            second=(
                "I ran it through again and it still files {night} as {status} with "
                "nothing wrong at the two ends of it. A night that can be archived "
                "has to be archived, and the row has to say so."
            ),
            detail="{status}",
        ),
    },
    "key_provenance_recorded": {
        "candidate_execution_failed": DID_NOT_RUN,
        "object_does_not_name_the_key_that_sealed_it": observation(
            first=(
                "Rob had an object off the vault, three generations in the key file "
                "and no way of telling which of them belongs to it. He worked "
                "through them one at a time, which is not a drill, and in a real "
                "recovery that is an hour we would not have."
            ),
            second=(
                "I read the header off what your build wrote for {night} and the "
                "generation it names comes back as {key_id_recorded}. The key file "
                "lists a generation under the id the key itself gives, and an object "
                "that does not carry that is an object we can only match by trying "
                "keys against it."
            ),
            detail="{key_id_recorded}",
        ),
        "ambiguous_key_configuration_was_resolved": observation(
            first=(
                "An object appeared for a night whose job configuration named both "
                "the variable and a key file. Nothing retained with the night "
                "records establishes that one source was resolved before the "
                "object appeared."
            ),
            second=(
                "Your build does the same thing with the same configuration: the "
                "object for {night} reports key id {key_id_used}. Where there are "
                "two places to look, nobody can establish afterwards that the job "
                "had one answer before it published the object."
            ),
            detail="{key_id_used}",
        ),
        "object_sealed_with_a_retired_key": observation(
            first=(
                "We rotated the key mid-week and the nights after the rotation went "
                "into the vault under the old generation. A retired generation is "
                "destroyed thirty days after its notice and the window runs longer "
                "than that, so those nights would have gone dark in the vault with "
                "nothing about them to say why."
            ),
            second=(
                "I read the headers back off your build. {night} is sealed under "
                "{key_id_used} where the run was given {key_id_configured}. A night "
                "has to be sealed with the key that night was configured with, or we "
                "cannot open it once the old one is destroyed."
            ),
            detail="{key_id_configured}",
        ),
    },
    "window_drill_opens_any_night": {
        "candidate_execution_failed": DID_NOT_RUN,
        "plain_night_would_not_open": observation(
            first=(
                "Rob started this quarter's drill on one of the plain nights we have "
                "been writing since the filer went in and the helper would not open "
                "it. A good part of the window is those nights, and the sheet came "
                "back to me with every one of those rows unopened."
            ),
            second=(
                "I worked down the sheet myself on your build. `{object}` is one of "
                "the plain ones and it comes back with {diagnosis}. The window holds "
                "both kinds until the sweeper has taken the last of the plain ones "
                "out of it."
            ),
            detail="{object}",
        ),
        "sealed_night_would_not_open": observation(
            first=(
                "The drill picked a sealed night this quarter and Rob got nowhere "
                "with it. He had the key file open in front of him, which is the "
                "whole point of the exercise, and the sheet came back to me with "
                "nothing written on that row."
            ),
            second=(
                "I tried that one myself against your build: `{object}` comes back "
                "with {diagnosis}, and the generation that made it is listed in the "
                "file Rob is holding. Whichever night the drill picks has to open."
            ),
            detail="{object}",
        ),
        "renamed_object_opened_as_the_wrong_kind": observation(
            first=(
                "The vault's tier move renamed a run of objects on its way through "
                "and the drill cannot open any of them now. They are the same bytes "
                "they were before it ran; the only thing that changed about them is "
                "what they are called, and Rob picks those rows at random along with "
                "everything else."
            ),
            second=(
                "I checked one of them on your build. `{object}` comes back with "
                "{diagnosis} while the object itself is intact — its name is the only "
                "thing about it that is wrong. A name is the one thing a copy tool "
                "changes."
            ),
            detail="{object}",
        ),
    },
}
