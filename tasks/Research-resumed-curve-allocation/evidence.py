'The owner of the sweep allocation note, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Nadia Fournier, who runs the pretraining group and takes its allocation note to the Friday "
    "review; she reads the sweep board, the node-hour grant and the questions the director puts "
    "to her, and she does not read the curves or the notebook's code."
)

USER_BELIEF = """The sweep has been running since the end of August and the director wants a configuration named on Friday, with the loss it lands on once the rest of the window's node-hours are spent. The board has said the same thing every morning this week: cfg-02 in front at 1.576, cfg-06 behind it at 1.607, and nothing else close. So as far as I can see cfg-02 is the run, and what is left of the grant should go into it.

Priya Raghavan runs the cluster and the sweep's day-to-day. When she tells me something about which node a job landed on, which launch script a run went out on or what the console did with a booking, I take it as read, and I could not tell you myself what any of it does to a number.

The window carries fifty node-hours and eight of them have gone, so there are forty-two left. My instinct is to put all forty-two into cfg-02: it is the run we are going to ship, and twelve more hours of the leader is an argument nobody can wave away.

The director asked for the number to within four hundredths with a range under it. The March slide went up with a range a fifth of a point wide and the review spent the meeting arguing about the middle of it; in June we went the other way and committed on a range the run then landed outside of, which cost us a fortnight. He has not forgotten either of them. What he said he would take, and I wrote it into `review_note.md` the same afternoon, is being wrong about one slide in twenty across the whole run of them — this window and the six after it, seven slides in all — rather than one in twenty on each, and nothing several times wider than the rows behind the number will carry.

What I cannot answer is anything about how the tables underneath were built. If you need that, it is in the workspace or in Priya's session records, not in my head."""

OBSERVATION_SCENE = "The Friday allocation review"

_STOPPED_FIRST = (
    "Priya opened your notebook to print the window's note and the run stopped before "
    "anything came out. The slide has an empty line where the number goes and the review "
    "is on Friday."
)
_STOPPED_SECOND = (
    "I asked her to run it again in front of me. The console ended with {error}, and the "
    "line is still empty."
)

OBSERVATIONS = {
    "funded_run_end_loss_within_tolerance": {
        "report_names_no_run_on_the_board": observation(
            first=(
                "The director opened your note and asked which of the runs it is about. The "
                "line where the configuration goes does not name anything he can find on the "
                "board, so there is nothing for him to fund."
            ),
            second=(
                "I looked myself before writing back to him. On {window} the note gives the "
                "run as {reported_run}, and the board for that window carries "
                "{runs_on_the_board} runs, none of them by that name."
            ),
            detail="{reported_run}",
        ),
        "estimate_uses_last_logged_row": observation(
            first=(
                "Priya read your note next to the board and said the number on it is the "
                "number that is already on the board. The director is asking what the run "
                "gets to once the hours are on it, and a figure the board printed last night "
                "cannot be that, because those hours have not been run yet."
            ),
            second=(
                "She put the two side by side for me on {window}. Your note prints "
                "{reported} for {reported_run}, and the board's last column for that run "
                "reads {last_row} with {hours_left} node-hours still unspent."
            ),
            detail="{last_row}",
        ),
        "estimate_reads_a_shorter_run": observation(
            first=(
                "Priya went through your note against the ledger and cannot reproduce the "
                "figure on it for the run once the remaining hours are on it. A similar "
                "reading appears earlier in the run, but the note does not show how it got "
                "there, and the director is being asked to sign the window's finish."
            ),
            second=(
                "She showed me the rows on {window}. The note gives {reported} for "
                "{reported_run}, whose last segment reached step {last_segment_steps}, and "
                "the ledger has {segments_behind_it} segments for that run running to "
                "{steps_so_far} steps in all, with {hours_left} node-hours still to go on "
                "top of that."
            ),
            detail="{steps_so_far}",
        ),
        "funded_run_is_not_the_one_the_hours_buy": observation(
            first=(
                "The director took your note and asked why the hours are going to that run "
                "rather than to the one that ends up lowest. He is buying the finish, not "
                "the standing today, and the run your note names is not the one that gets "
                "there first."
            ),
            second=(
                "I went back over it with Priya on {window}. The note funds {reported_run} at "
                "{reported} with {hours_left} node-hours to place, and she cannot get that "
                "run to come out in front of the others once those hours are on them."
            ),
            detail="{reported_run}",
        ),
        "end_loss_disagrees": observation(
            first=(
                "Priya rebuilt the number off the ledger and the curve files this afternoon "
                "and could not reproduce the figure your notebook prints within the review's "
                "tolerance. Neither of us can support that number for the director, so the "
                "note is on my desk instead of his."
            ),
            second=(
                "We went through it line by line on {window}. The note comes back at "
                "{reported} for {reported_run} on {steps_so_far} steps of training, and "
                "the run's rows do not reproduce it within four hundredths."
            ),
            detail="{reported}",
        ),
        "landing_wrong_on_a_later_window": observation(
            first=(
                "Priya put your notebook through the pre-review rehearsal cases for the "
                "later windows, because the same file has to make every one of those "
                "slides. Ours comes back with an allocation she could use and one rehearsal "
                "does not: the named run and printed finish do not form an allocation "
                "supported by that case's hours and rows. She will not sign a file that "
                "works only here."
            ),
            second=(
                "I asked her which window it was. It is {other_window}, and "
                "{other_windows} of the ones she ran the same file over came back with an "
                "allocation she could not stand behind."
            ),
            detail="{other_window}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_an_interval": observation(
            first=(
                "The director could not use what your notebook put on the range line as an "
                "ordered low-to-high interval around the number. After March and June he will "
                "not take a loss off this group without one, and he said so again in the "
                "meeting."
            ),
            second=(
                "I opened the note for {window} again to copy the range across and the line "
                "reads {reported}. He wants a low and a high in that order with the number "
                "between them."
            ),
            detail="{reported}",
        ),
        "range_excludes_reported_loss": observation(
            first=(
                "The director put the loss and the range underneath it side by side and the "
                "loss is outside the two endpoints. The note is making two incompatible "
                "claims about the same finish, so he sent it back before discussing the run."
            ),
            second=(
                "I checked the figures on {window}. The note gives {reported_loss}, while "
                "the range underneath it is {reported_range}."
            ),
            detail="{reported_loss}",
        ),
        "range_tighter_than_the_rows_carry": observation(
            first=(
                "Priya pushed back on the range under your number. She says it is tighter "
                "than the rows behind that run's curve can carry, and that ruling out places "
                "the run could still land is exactly what June did to us."
            ),
            second=(
                "She measured it against those rows with me for {window}. The range prints "
                "{reported_range} for {reported_run}, which is {published_width} end to end "
                "on {rows_behind} rows of that run's curve."
            ),
            detail="{published_width}",
        ),
        "range_wider_than_the_note_allows": observation(
            first=(
                "The range on your note is wider than the review will take. The director set "
                "the cap after March precisely so that the meeting argues about the choice "
                "instead of about the middle of a band, and he handed the slide straight back."
            ),
            second=(
                "I measured it against his cap on {window}. The range runs {reported_range}, "
                "which is more than {widest_allowed} end to end."
            ),
            detail="{widest_allowed}",
        ),
        "range_wider_than_the_rows_carry": observation(
            first=(
                "Priya put the range on your note next to the rows behind that run's curve "
                "and says it is not a reading of them at all. It takes up most of the width "
                "the director will take, on a run whose own rows place the number a good deal "
                "more closely than that, and a band that wide leaves the review where it was "
                "before we spent the window."
            ),
            second=(
                "She measured the two for me on {window}. The range prints {reported_range} "
                "for {reported_run}, {published_width} end to end, against {rows_behind} rows "
                "behind that run's curve."
            ),
            detail="{rows_behind}",
        ),
        "range_undercovers": observation(
            first=(
                "Priya compared the band your notebook prints with an independent landing "
                "check in the pre-review rehearsal cases. In at least one case the supported "
                "finish sits outside the printed band. The director commits on that band, "
                "and June was exactly the cost of a range that did not hold its landing."
            ),
            second=(
                "I put the two readings side by side for him off {window}. The band under "
                "the number runs {reported_range} for {reported_run}, and it was built on "
                "{rows_behind} rows of that run's curve."
            ),
            detail="{reported_range}",
        ),
        "range_does_not_move_with_the_rows": observation(
            first=(
                "In one pre-review rehearsal Priya ran the same training twice: once at "
                "the row spacing in the case and once with every curve written at the same "
                "spacing. The number moved the way she expected and the range under "
                "it did not move at all. A band that stays where it is while the rows "
                "behind the curve change is not a reading of them, and a reading of them "
                "is the one thing the director asked us for after March."
            ),
            second=(
                "She told me which window she did that on. It is {other_window}, and "
                "{other_windows} of the ones she ran the file over came back with a band "
                "that sat still."
            ),
            detail="{other_window}",
        ),
        "range_wrong_on_a_later_window": observation(
            first=(
                "Priya took your notebook through the pre-review rehearsal cases for the "
                "later windows before she would sign it off. The range it prints under our "
                "number holds up and one rehearsal does not: what it prints there cannot be "
                "used as that case's supported range under the terms of the review. The "
                "director will not take a run of slides where the same file is careful on "
                "one window and not on another."
            ),
            second=(
                "I went back and asked her which one. It is {other_window}, and "
                "{other_windows} of the windows she ran the file over came back with a "
                "range like that."
            ),
            detail="{other_window}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "choice_invariant_to_node_history": {
        "choice_tracks_node_history": observation(
            first=(
                "Priya reran your notebook on a copy of the ledger with the node column and "
                "the wall hours written the way they would have come out if the boxes had "
                "been handed round differently, and the note changed. The training that "
                "happened is the same training; which box it happened on is an accident of "
                "who was queueing that morning, and the director will not fund a run because "
                "of that."
            ),
            second=(
                "She ran both in front of me on {window}. As it stands the note gives "
                "{reported} on {reported_run}; with {what_changed} it gives {reported_again} "
                "on {reported_run_again}, a move of {moved}."
            ),
            detail="{moved}",
        ),
        "choice_tracks_logging_interval": observation(
            first=(
                "Priya reran your notebook on a copy where every curve had been written down "
                "at the same spacing, over the same stretches of training, and the note came "
                "back different. How often a hook fires is a setting in a launch script; it "
                "is not something a run should be funded or passed over for."
            ),
            second=(
                "She showed me the two runs of it on {window}. As it stands the note gives "
                "{reported} on {reported_run}; with {what_changed} it gives {reported_again} "
                "on {reported_run_again}, a move of {moved}."
            ),
            detail="{moved}",
        ),
        "choice_moves_on_a_later_window": observation(
            first=(
                "Priya ran the pre-review rehearsal cases twice: once as each case carries "
                "its ledger and once with the same training written down another way. Ours "
                "comes back the same both times and one rehearsal does not, so there the file is funding a "
                "run for how the work happened to be written down. She will not put a "
                "file like that in front of the review."
            ),
            second=(
                "She named the window for me afterwards. It is {other_window}, and "
                "{other_windows} of the ones she ran the file over came back with a "
                "different answer when the same training was written down another way."
            ),
            detail="{other_window}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_booking_feasible_and_separating": {
        "executed_allocation_disagrees": observation(
            first=(
                "Priya reconciled the jobs added to the console stream during this handoff. "
                "Taken together, the training they returned and the hours the console "
                "charged do not make the allocation the review called for, so grant has "
                "already been spent without settling the choice in front of us."
            ),
            second=(
                "She read the added receipts back on {window}: {executed_bookings}. Across "
                "those requests, what came back or was charged adds up to {executed_steps}."
            ),
            detail="{executed_bookings}",
        ),
        "plan_is_not_a_booking_or_a_stop": observation(
            first=(
                "Priya went to book the next jobs off your notebook and it gave her nothing "
                "she could hand the console. She has to name a run, a node type and a whole "
                "number of hours, and short of that she needs to be told there is nothing "
                "left worth booking."
            ),
            second=(
                "She showed me what came back for {window}: {reported}. The console takes a "
                "run, a node type and hours, and nothing else at all."
            ),
            detail="{reported}",
        ),
        "booking_names_a_run_the_window_does_not_carry": observation(
            first=(
                "The console would not take the booking your notebook made because the run it "
                "names is not one this window is training. Priya cannot start something that "
                "has no checkpoint behind it, and the morning went on the ticket."
            ),
            second=(
                "She forwarded me the request. Working on {window}, the notebook asked for "
                "{run_asked}, and nothing of that name is on that window's ledger."
            ),
            detail="{run_asked}",
        ),
        "booking_uses_unavailable_node": observation(
            first=(
                "Priya put your notebook's booking through the console and it was turned away "
                "on the node type. She has been charged for the request, the jobs have not "
                "run, and we are a day nearer Friday with nothing extra to show."
            ),
            second=(
                "She read the refusal out to me for {window}. The notebook asked for "
                "{node_asked}, and what the sweep can book there is {free_nodes}."
            ),
            detail="{node_asked}",
        ),
        "booking_not_on_reckoning_node": observation(
            first=(
                "Priya can run the jobs in your booking, but not at the reach the note is "
                "asking the director to fund. The jobs are on a different node type from "
                "the one used to reckon what those hours buy, so they return a different "
                "amount of training from the number above them."
            ),
            second=(
                "She compared the two on {window}. The booking asks for {node_asked}; the "
                "landing in the note was reckoned on {reckoning_node}."
            ),
            detail="{node_asked}",
        ),
        "booking_outside_job_window": observation(
            first=(
                "The console refused the job your notebook asked for on its length. Priya "
                "cannot split it or stretch it herself without knowing what the hours were "
                "meant to buy, so she has come back to me instead."
            ),
            second=(
                "She read the refusal out for {window}: the notebook asked for "
                "{hours_asked_for} hours, and the scheduler will hold a slot of no fewer "
                "than {job_min} and no more than {job_max}."
            ),
            detail="{job_max}",
        ),
        "booking_over_the_hours_left": observation(
            first=(
                "The console bounced your notebook's booking: the window has less left on the "
                "grant than the jobs would cost, and it does not roll into next month. Priya "
                "needs the notebook to know when the hours are gone rather than sending her "
                "to a console that will turn her away."
            ),
            second=(
                "She copied me on the bounce. Working on {window}, the notebook asked for "
                "{hours_asked_for} node-hours with {hours_left} left on the grant."
            ),
            detail="{hours_left}",
        ),
        "booking_not_separating": observation(
            first=(
                "Priya asked the notebook what to book next and what came back does not tell "
                "us anything we do not already know. The whole point of the hours left is to "
                "settle which of the two runs in front actually finishes lower, and what came "
                "back does not restrict matched training to both of those contenders. It "
                "therefore does not give us the comparison the hours are meant to buy."
            ),
            second=(
                "She ran it again in front of me on {window}. It asked for {reported}, with "
                "{hours_left} node-hours still to place."
            ),
            detail="{reported}",
        ),
        "booking_steps_not_matched": observation(
            first=(
                "Priya says the two runs in front do not receive the same amount of training "
                "in your booking. That leaves their next readings at different reaches, so "
                "the jobs cannot settle which curve is lower at the same point."
            ),
            second=(
                "She added up what the requests buy on {window}: {steps_booked}. The two "
                "totals need to match."
            ),
            detail="{steps_booked}",
        ),
        "stop_premature": observation(
            first=(
                "Your notebook told Priya there was nothing left to book while the grant still "
                "had hours on it. They do not carry into next month, so an hour we do not "
                "spend before Friday is an hour thrown away, and the director asked what we "
                "did with them."
            ),
            second=(
                "I checked the grant against it on {window}. The notebook stopped with "
                "{hours_left} node-hours in hand and a console that would still take a job."
            ),
            detail="{hours_left}",
        ),
        "booking_wrong_on_a_later_window": observation(
            first=(
                "Priya put your notebook through the pre-review rehearsal cases for later "
                "windows, asking each what to book next. Ours came back with a next action "
                "she could use and one rehearsal did not, and she had to work out by hand what that case can run and what "
                "comparison its remaining hours need to buy."
            ),
            second=(
                "She named the window for me afterwards. It is {other_window}, where what "
                "the file came back with is not a next action that window can use, and "
                "{other_windows} of the ones she ran it over came back that way."
            ),
            detail="{other_window}",
        ),
        "candidate_execution_failed": observation(
            first=(
                "Priya opened your notebook to work out what to book next and the run stopped "
                "before it said anything. She is sitting on the window's hours with nothing to "
                "spend them on."
            ),
            second=(
                "I watched her run it again. The console ended with {error}, and she still "
                "has nothing to hand the scheduler."
            ),
            detail="{error}",
        ),
    },
    "report_reconciles_stream": {
        "receipt_stream_unreadable": observation(
            first=(
                "The cluster's billing review could not open the receipt stream that came "
                "with your note. Until they can, nothing it says about what this window spent "
                "stands up, and they are holding the whole grant as unaccounted for."
            ),
            second=(
                "I forwarded the file to them and they sent back the line they stopped on: "
                "{reason}. The console writes that file and the note has to reach the review "
                "with it intact."
            ),
            detail="{reason}",
        ),
        "segments_are_not_a_list": observation(
            first=(
                "The billing review opened your note looking for the line-by-line of what the "
                "window trained and what it was charged, and found nothing they could read. "
                "They are holding this window's spend against the note until it is accounted "
                "for."
            ),
            second=(
                "I looked myself before writing back. On {window} that part of the note reads "
                "{reported}, against {segments_on_the_ledger} segments on the ledger and "
                "{bookings_on_the_stream} bookings on the stream."
            ),
            detail="{reported}",
        ),
        "segment_not_on_ledger": observation(
            first=(
                "Priya found a segment line in your note whose id is not on the window's "
                "ledger. She cannot count training that the source record does not carry, "
                "so billing has stopped the reconciliation at that line."
            ),
            second=(
                "She put the two beside each other on {window}. The note names segment "
                "{segment_id} for {run_of_the_segment}, and that segment id does not appear "
                "among the {segments_on_the_ledger} ledger entries."
            ),
            detail="{segment_id}",
        ),
        "segment_missing": observation(
            first=(
                "Priya matched your note against the ledger and found training that happened "
                "and is nowhere in it. She wants every segment the window ran to appear, "
                "whether or not it went into the number, and to be told plainly when one was "
                "left out and why."
            ),
            second=(
                "She pulled the ledger up beside the note for {window}. Segment {segment_id} "
                "of {run_of_the_segment} is on the ledger and not in the note, which carries "
                "{segments_on_the_ledger} segments in all."
            ),
            detail="{segment_id}",
        ),
        "segment_reported_twice": observation(
            first=(
                "The billing review caught the same segment written into your note twice. It "
                "is one stretch of training; counting it twice makes the window look like it "
                "did more than it did and the evidence behind the number look broader than it "
                "is."
            ),
            second=(
                "I counted the lines with them on {window}. Segment {segment_id} appears "
                "{times_reported} times in the note and once on the ledger."
            ),
            detail="{segment_id}",
        ),
        "line_disagrees_with_record": observation(
            first=(
                "The billing review found a line in your note whose details do not match the "
                "ledger or console record it names. They cannot reconcile a record by its id "
                "while the run, node or measured work beside that id says something else."
            ),
            second=(
                "They put the two copies side by side on {window}. For {record_kind} "
                "{record_id}, the note gives {field} as {reported_value}; the source record "
                "gives {recorded_value}."
            ),
            detail="{record_id}",
        ),
        "segment_usage_disagrees": observation(
            first=(
                "Priya found a ledger segment whose usage fields do not unambiguously say "
                "that it went into the number. These segments are consecutive parts of their "
                "runs and none is unusable in the window, so the note must account for each "
                "one consistently on the training axis behind the reported finish."
            ),
            second=(
                "She pointed at it on {window}: segment {segment_id} of {run_of_the_segment} "
                "has used={reported_used} and the set-aside line reads {reported_reason}."
            ),
            detail="{segment_id}",
        ),
        "collection_not_on_the_stream": observation(
            first=(
                "The billing review flagged a booking in your note that they have no record "
                "of. A job the console never ran cannot sit in a note the director acts on, "
                "and they have asked where the hours beside it came from."
            ),
            second=(
                "They named the line for me on {window}: {receipt_id}. The console's stream "
                "does not carry it as the note has it written."
            ),
            detail="{receipt_id}",
        ),
        "collection_reported_twice": observation(
            first=(
                "The billing review found the same console receipt written into your note "
                "more than once. It is one booking and one charge; repeating it makes the "
                "window look as though the console did more work than it did."
            ),
            second=(
                "They counted the lines on {window}. Receipt {receipt_id} appears "
                "{times_reported} times in the note and once on the console stream."
            ),
            detail="{receipt_id}",
        ),
        "refusal_uncounted": observation(
            first=(
                "The billing review will not close on your note because a request the console "
                "turned away is not accounted for in it. We were charged for that request, so "
                "it is spend, and a note that quietly drops it makes the grant look bigger "
                "than it is."
            ),
            second=(
                "They put the two side by side for me on {window}. Against {receipt_id} the "
                "note gives {reported_hours}, and the stream says the console took "
                "{stream_hours}."
            ),
            detail="{receipt_id}",
        ),
        "collection_missing_from_the_report": observation(
            first=(
                "The billing review matched your note against the console's bill and found "
                "hours we were charged for that the note never mentions. They want every "
                "node-hour this window spent to appear in it, whoever booked it and whether "
                "or not it changed the answer."
            ),
            second=(
                "I pulled the stream up beside the note for {window}. Booking {receipt_id} "
                "cost {stream_hours} node-hours and the note gives {reported_hours} for it."
            ),
            detail="{receipt_id}",
        ),
        "hours_do_not_reconcile": observation(
            first=(
                "The billing review will not close on your note: the total it gives for the "
                "window's spend is not the total on the console's bill. Finance reconciles "
                "the grant against that line, so a note that disagrees with it stops there."
            ),
            second=(
                "They put the totals side by side for me on {window}. The note says "
                "{reported_hours} node-hours went and {reported_left} are left, and the "
                "stream adds up to {stream_hours} against a grant of {granted}."
            ),
            detail="{stream_hours}",
        ),
        "stream_wrong_on_a_later_window": observation(
            first=(
                "The cluster's billing review put your notebook through the pre-review "
                "receipt cases for later windows. The line-by-line for our window matched "
                "and one rehearsal did not, so they cannot sign off the same notebook for "
                "the run of windows."
            ),
            second=(
                "I asked billing which window it was. It is {other_window}, where what "
                "the note lists and what the console billed do not line up, and "
                "{other_windows} of the ones they checked came back like that."
            ),
            detail="{other_window}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
