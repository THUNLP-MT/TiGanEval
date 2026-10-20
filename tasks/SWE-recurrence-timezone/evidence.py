'Owner persona, belief, and Observation contexts for SWE-recurrence-timezone.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dagmar Holt, the product manager for the scheduling product; she reads the "
    "support queue, the tickets support forwards her, the dispatch log and the "
    "screenshots customers send out of their own calendars, not the code that "
    "works out when a reminder goes out."
)

USER_BELIEF = (
    "I sell a scheduling product, and the thing customers buy it for is that a "
    "recurring meeting stays where they put it. Right now it does not: since the "
    "clocks changed at the end of March I have had tickets from Berlin and from "
    "Sydney saying the same thing in opposite directions, that the reminder for a "
    "meeting nobody has touched now arrives an hour away from the meeting. One of "
    "those customers joined a client call after it had started.\n\n"
    "What I want is that a customer who writes 09:00 gets 09:00, this month and "
    "next month and after the clocks move again, and that support stops having to "
    "apologise for it. I read the support queue, what support forwards me and what "
    "customers send me out of their own calendars; I cannot tell you what the code "
    "is doing, only what they see. Done, for me, is the tickets stopping and "
    "staying stopped."
)

OBSERVATION_SCENE = "Support queue review for the scheduling product"


OBSERVATIONS = {


    "local_time_preserved": {
        "candidate_execution_failed": observation(
            first=(
                "I tried to open customer schedules on this build, but the schedule "
                "console stopped before it showed any reminder times. Support cannot "
                "tell customers what this build would send."
            ),
            second=(
                "I tried to open the schedules again on your build and there is one line "
                "on the console where the reminder times should be — {error}"
            ),
            detail="{error}",
        ),
        "schedule_call_failed": observation(
            first=(
                "Support opened a customer's schedule and got an error back instead of "
                "their reminders. We do not yet know whether any other series is affected."
            ),
            second=(
                "I asked for the same customer's series again on your build and this came "
                "back where the reminders should be: {error}"
            ),
            detail="{error}",
        ),
        "series_length_wrong": observation(
            first=(
                "A customer sent in two screenshots side by side, their own calendar and "
                "our reminder list for the same stretch. The two do not have the same "
                "number of entries, and they have stopped trusting what we send."
            ),
            second=(
                "I lined the same stretch up again on your build: we list {produced} "
                "reminders for that series where their own calendar has {expected}."
            ),
            detail="{produced}",
        ),
        "occurrence_drifted_from_local_time": observation(
            first=(
                "A customer's recurring reminder is arriving at a different time of day "
                "from the meeting they set. Support cannot tell them which reminder time "
                "to trust."
            ),
            second=(
                "I opened that customer's week on your build: the reminder on {date} is "
                "timed {observed_local}, and their calendar has that meeting at "
                "{expected_local} the same as every other day."
            ),
            detail="{observed_local}",
        ),
        "standing_series_unanswered": observation(
            first=(
                "A customer opened a requested week of a recurring meeting that remains "
                "booked years ahead and got an error where their reminders should be. "
                "They cannot see what will go out that week."
            ),
            second=(
                "I opened the {summary} series in {zone} for its requested week on your "
                "build, and it came back with {error}."
            ),
            detail="{error}",
        ),
        "late_stretch_unanswered": observation(
            first=(
                "Ticket 5341, from a customer planning a piece of work a long way out: "
                "they scrolled their calendar forward to the last week of May 2028 and "
                "got an error back where their reminders should be. They cannot see what "
                "will go out during that week."
            ),
            second=(
                "I opened the {summary} series in {zone} for that week on your build, and "
                "it came back with {error}."
            ),
            detail="{error}",
        ),
    },


    "transition_occurrence_policy": {
        "candidate_execution_failed": observation(
            first=(
                "I tried to check the customer schedules for a clock-change weekend on "
                "this build, but the console stopped before it showed any runs or pages. "
                "Support cannot tell those customers what would happen."
            ),
            second=(
                "I asked for the clock-change weekend again on your build and the console "
                "has one line where the schedule should be — {error}"
            ),
            detail="{error}",
        ),
        "schedule_call_failed": observation(
            first=(
                "Support opened a customer's series for the night the clocks move and got "
                "an error instead of its schedule. We do not yet know whether another "
                "clock-change series is affected."
            ),
            second=(
                "I asked for the same night again on your build and this is the answer it "
                "gives for that series: {error}"
            ),
            detail="{error}",
        ),
        "gap_occurrence_missing": observation(
            first=(
                "A customer's overnight export did not run on one night of the year. "
                "Nobody noticed until their finance team came looking for the file a week "
                "later and there was nothing to give them."
            ),
            second=(
                "I stepped through that customer's series night by night on your build: "
                "the run scheduled for {wall} on {date} is not in what the build returns."
            ),
            detail="{date}",
        ),
        "gap_occurrence_moved": observation(
            first=(
                "On the night the clocks went forward, a customer's overnight export "
                "started at the wrong hour and ran against a database that was still "
                "being restored. They spent the next day reconciling it by hand."
            ),
            second=(
                "I stepped through that night on your build: the run comes out at "
                "{observed_local}, and the runbook line the operator wrote for that night "
                "is stamped {expected_local}."
            ),
            detail="{observed_local}",
        ),
        "ambiguous_occurrence_missing": observation(
            first=(
                "A customer's on-call handover paged nobody on the night the clocks went "
                "back. The engineer coming on shift slept through it and the outgoing one "
                "had already stood down."
            ),
            second=(
                "I stepped through that series on your build: the handover page scheduled "
                "for {wall} on {date} is not in what the build returns."
            ),
            detail="{date}",
        ),
        "ambiguous_occurrence_moved": observation(
            first=(
                "A customer's on-call handover paged the incoming engineer on the wrong "
                "side of the hour the clocks went back, so the outgoing engineer stood "
                "down with nobody covering the gap."
            ),
            second=(
                "I put that night's page next to the runbook line the operator wrote at "
                "the time on the same night: the two are {minutes_apart} minutes apart."
            ),
            detail="{minutes_apart}",
        ),
        "gap_occurrence_duplicated": observation(
            first=(
                "A customer's overnight export ran more than once for one scheduled run "
                "on the night the clocks went forward. Their finance team found duplicate "
                "files and had to reconcile them by hand."
            ),
            second=(
                "I counted what your build returns for the run scheduled at {wall} on "
                "{date}: {times} runs for that one scheduled action."
            ),
            detail="{times}",
        ),
        "ambiguous_occurrence_duplicated": observation(
            first=(
                "A customer's on-call handover paged more than once for one scheduled "
                "handover on the night the clocks went back. The team could not tell "
                "which page represented the shift change."
            ),
            second=(
                "I counted what your build returns for the handover scheduled at {wall} "
                "on {date}: {times} pages for that one handover."
            ),
            detail="{times}",
        ),
        "transition_series_length_wrong": observation(
            first=(
                "A customer's bounded recurring series and our reminder list do not have "
                "the same number of entries around the weekend the clocks changed. They "
                "cannot reconcile the actions they planned with what we show."
            ),
            second=(
                "I put that bounded series next to what your build returns: it has "
                "{produced} entries where the customer's rule has {expected}."
            ),
            detail="{produced}",
        ),
        "transition_series_occurrence_moved": observation(
            first=(
                "A customer compared a bounded recurring series with our reminder list for "
                "a clock-change stretch. The lists contain the same number of entries, but "
                "one entry is at a different date or time."
            ),
            second=(
                "I compared that bounded series entry by entry on your build: entry "
                "{position} appears at {observed_at}, while the customer's rule puts it at "
                "{expected_at}."
            ),
            detail="{observed_at}",
        ),
    },


    "exported_rule_round_trip": {
        "candidate_execution_failed": observation(
            first=(
                "I tried to export a customer's series on this build, but the schedule "
                "console stopped before it returned a file. Support cannot give the "
                "customer a copy their phone can read."
            ),
            second=(
                "I tried the same export again on your build and this came back instead "
                "of a file — {error}"
            ),
            detail="{error}",
        ),
        "schedule_call_failed": observation(
            first=(
                "Support tried to export a customer's series and got an error instead of "
                "a file. We do not yet know whether another series is affected."
            ),
            second=(
                "I exported that series on its own on your build and got this back: "
                "{error}"
            ),
            detail="{error}",
        ),
        "export_unreadable": observation(
            first=(
                "A customer subscribed to their own exported calendar from their phone "
                "and the app turned the whole file down, so not one of their meetings "
                "came across."
            ),
            second=(
                "I fed the file we write straight back into the reader those apps use, "
                "and it refused it: {reason}"
            ),
            detail="{reason}",
        ),
        "zone_lost_in_export": observation(
            first=(
                "A customer moved a recurring series into the phone app and it came back "
                "assigned to a different zone from the one they set. They cannot trust it "
                "to remain at their chosen local time."
            ),
            second=(
                "I put our own file back through the reader those apps use: the series "
                "comes back belonging to {read_zone}, and not to the zone the customer "
                "set it in."
            ),
            detail="{read_zone}",
        ),
        "start_moved_in_export": observation(
            first=(
                "A customer's exported series starts on a different date or at a "
                "different time from the one they set. They cannot tell which first "
                "meeting the phone app will show."
            ),
            second=(
                "I read our own file back through the reader: the series comes back "
                "starting at {read_start} where the customer has it at {expected_start}."
            ),
            detail="{read_start}",
        ),
        "series_name_changed_in_export": observation(
            first=(
                "A customer's meetings arrive in the phone app under a different name "
                "from the one they gave them. Their team could not find the right series "
                "in a shared calendar and set a second one up beside it."
            ),
            second=(
                "I read our own file back through the reader those apps use: the series "
                "comes back called {read_value} where the customer has it as "
                "{expected_value}."
            ),
            detail="{read_value}",
        ),
        "series_repeat_changed_in_export": observation(
            first=(
                "A customer's board meeting comes round on a different cadence in the "
                "phone app from the one they set. They sent invitations for weeks that "
                "have no meeting in them and had to write to everybody again."
            ),
            second=(
                "I read our own file back and put it next to the rule the customer holds: "
                "the {field} comes back as {read_value} where they set {expected_value}."
            ),
            detail="{read_value}",
        ),
        "series_count_changed_in_export": observation(
            first=(
                "A customer runs a course off a series with a fixed number of sessions in "
                "it, and the copy in the phone app does not have that number. Two of their "
                "students turned up for a week that had nothing in it."
            ),
            second=(
                "I read our own file back through the reader: the series comes back "
                "running {read_value} times where the customer set it to run "
                "{expected_value}."
            ),
            detail="{read_value}",
        ),
        "series_bound_kind_changed_in_export": observation(
            first=(
                "A customer's exported series no longer stops in the way they set: one "
                "copy stops after a number of meetings and the other stops at a date. "
                "They cannot tell which meeting is the last one."
            ),
            second=(
                "I read our own file back through the reader: the customer's rule "
                "{expected_bound}, while the copy we read back {read_bound}."
            ),
            detail="{read_bound}",
        ),
        "series_end_moved": observation(
            first=(
                "A customer's bounded series ends in a different place in the phone app "
                "from where it ends with us. Their team lost a reminder they still needed "
                "for the last week of the term."
            ),
            second=(
                "I read our own file back through the reader: the end of the series comes "
                "back {minutes_moved} minutes away from where the customer set it, at "
                "{read_end}."
            ),
            detail="{minutes_moved}",
        ),
        "export_not_stable": observation(
            first=(
                "A customer's desktop calendar resubscribes to our export every night, "
                "and it has flagged the same series as changed every night this week "
                "although nobody has touched it. They want to know what we keep changing."
            ),
            second=(
                "I exported that series, read it back and exported it again on your "
                "build: the {summary} series comes out differently the second time from "
                "the first."
            ),
            detail="{summary}",
        ),
    },


    "merged_feed_deduplication": {
        "candidate_execution_failed": observation(
            first=(
                "I tried to open a subscribed customer's combined schedule on this build, "
                "but the console stopped before it showed any reminders. Support cannot "
                "tell the customer what the feeds add up to."
            ),
            second=(
                "I opened that customer's schedule again on your build and there is one "
                "line where the reminders should be — {error}"
            ),
            detail="{error}",
        ),
        "schedule_call_failed": observation(
            first=(
                "Support tried to show a customer what the feeds they subscribe to add up "
                "to, and the page returned an error instead of their combined schedule. "
                "We do not yet know whether another subscription is affected."
            ),
            second=(
                "I asked for the same customer's schedule on your build and got this "
                "back: {error}"
            ),
            detail="{error}",
        ),
        "duplicate_reminder_in_merge": observation(
            first=(
                "A customer who subscribes to the team feed and also holds their own "
                "invite for the same meeting is being reminded about it more than once "
                "when it occurs. They have now asked twice to be taken off something."
            ),
            second=(
                "I looked at what that customer actually receives on your build: {times} "
                "separate reminders for the one meeting at {reminder_at}."
            ),
            detail="{times}",
        ),
        "merged_reminder_missing": observation(
            first=(
                "A customer stopped being reminded about a meeting that is in one of the "
                "feeds they subscribe to. They missed it twice before writing in."
            ),
            second=(
                "I put each of that customer's feeds next to what they actually receive "
                "on your build: the reminder at {reminder_at} is in one of the feeds and "
                "not in what we send."
            ),
            detail="{reminder_at}",
        ),
        "merged_reminder_unexpected": observation(
            first=(
                "A customer is being reminded about a meeting at a time that is in none "
                "of the feeds they subscribe to. They cleared their afternoon and turned "
                "up for it."
            ),
            second=(
                "I went through every feed that customer holds on your build: not one of "
                "them fires at {reminder_at}, and we send a reminder then."
            ),
            detail="{reminder_at}",
        ),
        "merge_not_ascending": observation(
            first=(
                "The calendar view for a customer who subscribes to two feeds lists their "
                "combined schedule out of order, so support cannot read them the next "
                "thing coming."
            ),
            second=(
                "I opened that customer's merged schedule for the requested stretch on "
                "your build: its {reminders} reminders are not in chronological order."
            ),
            detail="{reminders}",
        ),
    },


    "window_slice_partition": {
        "candidate_execution_failed": observation(
            first=(
                "I tried to ask the dispatcher for the next stretch on this build, but the "
                "console stopped before it returned any schedule. Support cannot tell "
                "what the dispatcher would send."
            ),
            second=(
                "I asked for the next stretch of reminders again on your build and this "
                "is all that came back — {error}"
            ),
            detail="{error}",
        ),
        "schedule_call_failed": observation(
            first=(
                "The dispatcher asked for a customer's next stretch and got an error "
                "instead of reminders. We do not yet know whether another series is "
                "affected."
            ),
            second=(
                "I asked the dispatcher for that customer's next stretch on your build "
                "and got this: {error}"
            ),
            detail="{error}",
        ),
        "occurrence_outside_window": observation(
            first=(
                "The dispatcher handed a customer's reminder out while walking a piece of "
                "the schedule that does not contain it. The reminder can therefore be sent "
                "at the wrong point in the dispatch run."
            ),
            second=(
                "I walked the dispatcher through the requested stretch in its configured "
                "pieces on your build: the reminder for {reminder_at} was returned by a "
                "piece that does not contain it."
            ),
            detail="{reminder_at}",
        ),
        "slice_duplicated_occurrence": observation(
            first=(
                "The dispatcher handed the same reminder out more than once while walking "
                "a customer's schedule in pieces. The customer received duplicate "
                "reminders and asked whether the meeting had moved."
            ),
            second=(
                "I walked the dispatcher through the requested stretch in its configured "
                "pieces on your build: {duplicated_reminders} different reminder times "
                "repeat, creating {extra_deliveries} extra handoffs, starting with "
                "{reminder_at}."
            ),
            detail="{duplicated_reminders}",
        ),
        "slice_dropped_occurrence": observation(
            first=(
                "A reminder that the customer can see in their own calendar view never "
                "actually went out, and they missed the meeting it was for."
            ),
            second=(
                "I walked the dispatcher through that stretch a piece at a time on your "
                "build: the reminder for {reminder_at} is in the day we show the customer "
                "and in none of the pieces the dispatcher walked."
            ),
            detail="{reminder_at}",
        ),
    },
}
