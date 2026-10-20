'Owner persona, belief, and Observation contexts for the cycle-life study.'

from __future__ import annotations

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ines Vardy, who runs the cell test lab and signs the qualification build off. "
    "She reads the operator's session sheets, the scheduler's booking sheet, the "
    "vendor's certificate and whatever the notebook prints for her; she does not "
    "read its code."
)

USER_BELIEF = (
    "I want the September build settled before it closes, with one line I can take "
    "to the programme office and defend when the vendor's engineer picks at it. The "
    "stepped cells from the May session are reaching eighty percent a long way past "
    "anything the standard charge has given us, so my read is that the stepped charge "
    "is worth well over the hundred cycles the requalification needs, and I have been "
    "planning to put the last of our channel hours on more cells of it. What I can see "
    "is the operator's session sheets, the scheduler's booking sheet, the vendor's "
    "certificate for the lot and whatever the notebook prints. Done, for me, is a "
    "number for the temperature the build actually runs at that survives the programme "
    "review, an honest sense of how far that number could still move, a booking the "
    "scheduler can load on Monday, and a notebook the operator keeps using on KX-19 "
    "and the lots after it without ringing me about it."
)

OBSERVATION_SCENE = (
    "The Monday look at the cycle-life notebook before the programme build review"
)


DID_NOT_RUN = observation(
    first=(
        "The operator could not complete the Monday review with your notebook. It stopped "
        "before every result she needs across this campaign and the lots behind it was "
        "available, so I do not have a finished piece of work to hand to her or to the "
        "programme office."
    ),
    second=(
        "She ran the delivered notebook through the review again and it still did not "
        "finish the job. The console ended with this line: {error}. Whatever appeared "
        "before that line, the operator still cannot get every required result from one "
        "complete run."
    ),
    detail="{error}",
)


OBSERVATIONS = {
    "session_retirement_cycles": {
        "candidate_execution_failed": DID_NOT_RUN,
        "sessions_do_not_match_the_receipts": observation(
            first=(
                "I sat in the Monday review with your table on one side and the scheduler's "
                "list of sessions on the other, and the two are not the same list. The office "
                "is asking the lab to account for every fixture it has paid for this year, and "
                "I turned pages in front of them without being able to do it."
            ),
            second=(
                "I went back through the scheduler's sheet against your table on my own "
                "afterwards. She has {receipt_sessions} sessions billed to this campaign and "
                "your table carries {reported_sessions}; the first one that is not on both "
                "lists is {session}. Every session the tester billed us for has to turn up in "
                "that table once, with the cells and the hours it cost beside it."
            ),
            detail="{session}",
        ),
        "cells_do_not_match_the_receipts": observation(
            first=(
                "The operator took one session in your table back to its receipt and could "
                "not reconcile the session line as written. That line is the lab's account "
                "of the cells the tester ran and the channel hours it billed, so she cannot "
                "sign it off while the two records disagree."
            ),
            second=(
                "I sat with her and checked session {session} against its receipt. The tester "
                "has {receipt_cells} cell lines there and your table accounts for "
                "{reported_cells}; the cells and billed hours on that session line still do "
                "not reconcile exactly to the receipt."
            ),
            detail="{session}",
        ),
        "drift_left_in_the_readings": observation(
            first=(
                "The operator traced a life in your table back to a later receipt and found "
                "that it was still being read on the tester's shifted scale. The sealed cell "
                "at the top of that receipt does not read its certified value, so the table "
                "and the earlier sheets are not yet on one measurement."
            ),
            second=(
                "I went back to the receipts myself. Your notebook retires {cell} on session "
                "{session} at {reported} cycles, and the sealed cell at the top of that receipt "
                "reads {reference_cell_ah} where its certificate says {certified_ah}. One "
                "certified cell comes back differently on different sheets, and whatever the "
                "tester was doing to that reading it was doing to the cells beside it."
            ),
            detail="{reported}",
        ),
        "retirement_cycles_disagree": observation(
            first=(
                "The operator traced one cycle life in your table back to its export and it did "
                "not land on the capacity check required by the programme note. She works down "
                "the checks until the first one falls under the retirement line, and this table "
                "entry does not reconcile to that step."
            ),
            second=(
                "She did it again in front of me on {cell} in session {session}. Your notebook "
                "retires it at {reported} cycles, and the line she works to is "
                "{retirement_line_ah} amp hours off the {rated_capacity_ah} rating. She takes "
                "the first check under that line and nothing after it."
            ),
            detail="{cell}",
        ),
    },
    "qualification_difference": {
        "candidate_execution_failed": DID_NOT_RUN,
        "difference_claimed_without_a_standard_run": observation(
            first=(
                "The operator took your comparison back to the session sheets at the "
                "temperature this lot's build runs at. She found stepped-charge cells there "
                "but no standard-charge fixture to compare them with, so the number on the "
                "board has no two-sided comparison behind it. The build decision has gone "
                "back a week."
            ),
            second=(
                "I have been through every sheet on {lot} twice since. Your notebook puts "
                "{reported} cycles on the board, and not one of the {bay} bay's channels, "
                "{bay_channels}, has ever carried the {protocol} charge at {setpoint_c} C to "
                "hold the other one against. Where the cells we have cannot say, I would sooner "
                "take the office nothing."
            ),
            detail="{reported}",
        ),
        "difference_claimed_without_a_stepped_run": observation(
            first=(
                "The operator took your comparison back to the session sheets at the "
                "temperature this lot's build runs at. She found standard-charge cells there "
                "but no stepped-charge fixture to compare them with, so the number on the "
                "board has no two-sided comparison behind it. The build decision has gone "
                "back a week."
            ),
            second=(
                "I have been through every sheet on {lot} twice since. Your notebook puts "
                "{reported} cycles on the board, and not one of the {bay} bay's channels, "
                "{bay_channels}, has ever carried the {protocol} charge at {setpoint_c} C to "
                "hold the other one against. Where the cells we have cannot say, I would sooner "
                "take the office nothing."
            ),
            detail="{reported}",
        ),
        "cells_from_another_chamber_counted": observation(
            first=(
                "Your difference does not describe the build. The build runs cool, and I can "
                "only get your figure off the sheets by counting cells that sat on the hot "
                "bay's channels. Nobody in that room believes a cell aged in the oven tells "
                "them about the build."
            ),
            second=(
                "I worked it through on the back of the sheets on {lot}. Your figure is "
                "{reported} cycles, and the {cells_in_the_bay} cells on the {bay} bay's "
                "channels at {setpoint_c} C do not give it on their own; it takes the "
                "{cells_outside_the_bay} cells that sat in the {other_bay} bay at "
                "{other_setpoint_c} C as well. The oven is on the bench to age cells faster; "
                "that is the whole reason we have one."
            ),
            detail="{reported}",
        ),
        "temperature_taken_from_the_chamber_trace": observation(
            first=(
                "The vendor's engineer asked me which chamber each of these sessions sat in and "
                "I answered him off the temperature column on the operator's sheets. He read "
                "the channel numbers back to me against the rack and I could not make the two "
                "agree in front of him. The office has sent the build decision back to the lab."
            ),
            second=(
                "I went through the sheets again myself on {lot}. Your figure is {reported} "
                "cycles, and session {session} sits on channels {channels} with {logged_c} "
                "written in its temperature column while the rack holds those channels at "
                "{setpoint_c}. The operator moves cells by channel, and the rack sheet records "
                "no setpoint change for that session."
            ),
            detail="{reported}",
        ),
        "scale_left_in_the_difference": observation(
            first=(
                "The figure your notebook gives the build combines session sheets whose sealed "
                "cell does not read the same way. The vendor's engineer went to that line at "
                "the top of the receipts, and I could not defend treating the figures beneath "
                "it as one measurement."
            ),
            second=(
                "I laid the receipts out side by side afterwards on {lot}. Your figure is "
                "{reported} cycles, and the sealed cell that is certified at {certified_ah} amp "
                "hours reads {reference_cell_ah} at the top of session {session} and "
                "{other_reference_cell_ah} at the top of {other_session}. Sessions read on "
                "different days are not the same measurement yet."
            ),
            detail="{reported}",
        ),
        "qualification_difference_disagrees": observation(
            first=(
                "The number moved under me. I gave the office one figure out of your notebook "
                "and the build review has a different one, and neither survived the engineer "
                "going down the session sheets with me. He asked which cells and at what "
                "temperature and the answer did not hold up."
            ),
            second=(
                "He came back to it with me on {lot}. Your notebook has {reported} where that "
                "figure should be, and the {cells_in_the_bay} cells the {bay} bay holds at "
                "{setpoint_c} C do not give it however the two of us counted them."
            ),
            detail="{reported}",
        ),
    },
    "supported_effect_range": {
        "candidate_execution_failed": DID_NOT_RUN,
        "range_missing": observation(
            first=(
                "The office could not read a usable lower-to-upper band from the range line in "
                "your notebook. Without two finite endpoints in order, I cannot tell them how "
                "far the result could still move before they book six weeks of requalification."
            ),
            second=(
                "I checked the range line again on {lot} and it still does not give the office "
                "a readable lower and upper endpoint. I have to say how far the result could "
                "move while the cells on our receipts and the certificate's "
                "{certificate_lower} to {certificate_upper} cycles both stand."
            ),
            detail="{certificate_upper}",
        ),
        "range_is_the_figure_repeated": observation(
            first=(
                "Where the band should be your notebook prints the figure over again, the same "
                "number at both ends, so there is nothing under the line for the office to "
                "read. They asked how far it could still move and both ends said the same "
                "thing; six weeks of requalification does not get booked against that."
            ),
            second=(
                "I looked at the two lines again on {lot}. The band reads {reported_lower} to "
                "{reported_upper} cycles, which is the figure twice over, and the cells on our "
                "receipts at {setpoint_c} C and the certificate's {certificate_lower} to "
                "{certificate_upper} cycles leave more than that standing between them. I need "
                "to see how far the figure could move."
            ),
            detail="{reported_upper}",
        ),
        "range_narrower_than_the_evidence": observation(
            first=(
                "The band your notebook prints is tighter than I can defend. The vendor's "
                "engineer went through it with me against his certificate for the lot and said "
                "the cells we have do not pin the answer down that far, and I could not argue "
                "with him."
            ),
            second=(
                "I put it in front of him once more on {lot}. Your notebook has the band at "
                "{reported_lower} to {reported_upper} cycles, and he walked me through an "
                "outcome outside it that our receipts and his {certificate_lower} to "
                "{certificate_upper} cycles leave standing together. A band that leaves out "
                "what is still possible is worse to book against than no band at all."
            ),
            detail="{reported_upper}",
        ),
        "range_wider_than_the_evidence": observation(
            first=(
                "The band includes outcomes that the cells on our receipts and the lot "
                "certificate already rule out. The office will not plan against room that the "
                "lab's own evidence says is no longer there."
            ),
            second=(
                "I looked at it once more on {lot}: {reported_lower} to {reported_upper} "
                "cycles. At least one end runs beyond what the cells already on our receipts at "
                "{setpoint_c} C and the certificate's {certificate_lower} to "
                "{certificate_upper} cycles leave standing together."
            ),
            detail="{reported_upper}",
        ),
    },
    "collection_plan": {
        "candidate_execution_failed": DID_NOT_RUN,
        "session_did_not_advance_the_open_question": observation(
            first=(
                "The tester's ledger includes a paid session booked while the qualification "
                "question was still open, but that session left the office without a defensible "
                "call. Its channel hours have gone from this campaign and cannot be handed back "
                "now that the receipt is sealed."
            ),
            second=(
                "I put the before-and-after receipts together on {lot}. Session {session} ran "
                "{cells} cells of the {protocol} charge in the {bay} bay and spent "
                "{channel_hours} channel hours. Its receipt left "
                "{channel_hours_left_after} hours on the sheet, but it did not close the "
                "qualification question that was open when it was booked."
            ),
            detail="{session}",
        ),
        "settling_session_took_more_channels_than_the_question_needed": observation(
            first=(
                "The tester has already run more cells in the session that settled the "
                "build question than the booking sheet called for. Those extra channel hours "
                "have gone from the programme behind us in the queue, and the scheduler cannot "
                "hand them back now that the receipt is in the ledger."
            ),
            second=(
                "I matched the tester ledger to the booking sheet on {lot}. Session {session} "
                "ran {cells} cells of the {protocol} charge in the {bay} bay and spent "
                "{channel_hours} channel hours; {cells_the_question_needed} cells and "
                "{channel_hours_the_question_needed} hours would have settled the same "
                "question. This is work the tester ran, not a recommendation still waiting on "
                "the scheduler's desk."
            ),
            detail="{session}",
        ),
        "session_ran_after_the_question_was_closed": observation(
            first=(
                "The tester's ledger has another paid session after this qualification "
                "question was already closed. The cells ran and the hours have left the "
                "booking sheet, so the programme behind us has lost channels for work that "
                "cannot change whether this build is settled."
            ),
            second=(
                "I put the receipts in order on {lot}. Session {session} ran {cells} cells of "
                "the {protocol} charge in the {bay} bay for {channel_hours} channel hours after "
                "{closing_session} had already put both charges on the build bay. Once the "
                "question is closed, the tester goes to the next programme rather than taking "
                "another session from this one."
            ),
            detail="{session}",
        ),
        "plan_exceeds_the_booking": observation(
            first=(
                "The scheduler could not load the proposed booking as one valid tester request. "
                "As written, it does not fit the rack and booking sheet she has to work from, "
                "so nothing has been put on the tester from that proposal."
            ),
            second=(
                "She checked the proposal again as one request: {cells} cells of the {protocol} "
                "charge in the {bay} bay, costing {channel_hours_needed} channel hours against "
                "{channel_hours_left} left. Those are the numbers she has to reconcile with the "
                "fixture, the bay and the balance before a booking can be loaded."
            ),
            detail="{channel_hours_needed}",
        ),
        "plan_books_a_run_we_already_have": observation(
            first=(
                "Your notebook sent the scheduler a booking for a run this campaign has already "
                "made. She rang me to ask whether the lab had lost track of its own campaign, "
                "and I did not have a good answer for her with the sessions list open."
            ),
            second=(
                "She read it back to me off the sheet on {lot}: {cells} more cells of the "
                "{protocol} charge into the {bay} bay. The session list already carries that "
                "charge in that bay. Spending more hours on a measurement the campaign already "
                "holds leaves the missing part of the build question open."
            ),
            detail="{protocol}",
        ),
        "plan_takes_more_channels_than_the_question_needs": observation(
            first=(
                "The scheduler held the proposed booking before loading it because it reserves "
                "more cells than this qualification question needs. Her log says the surplus "
                "hours would leave for the next programme in the queue on the day the request "
                "was booked, so she has not put this proposal on the tester."
            ),
            second=(
                "She put the proposal beside her sheet on {lot}. It asks for {cells} cells and "
                "would reserve {channel_hours_needed} channel hours in the {bay} bay, where "
                "{cells_the_question_needs} cells and {channel_hours_the_question_needs} hours "
                "settle the same question."
            ),
            detail="{channel_hours_needed}",
        ),
        "plan_stops_with_the_question_open": observation(
            first=(
                "Your notebook told the scheduler there is nothing further to run while her "
                "booking sheet still shows hours on it, and the office has no answer out of us. "
                "She cannot close the request from that instruction while an affordable fixture "
                "would still settle the question."
            ),
            second=(
                "I went to the booking sheet on {lot} after that call. There are "
                "{channel_hours_left} hours sitting unspent on it, a fixture of {cells} cells "
                "costs {channel_hours_needed} of them, and the {bay} bay has never carried the "
                "{protocol} charge. The qualification question is still open."
            ),
            detail="{channel_hours_left}",
        ),
        "collection_plan_disagrees": observation(
            first=(
                "The next-action line in your notebook is not an instruction the scheduler can "
                "accept for this qualification question. She cannot use it to move this lot "
                "from its current state."
            ),
            second=(
                "She sent the next-action line back to me on {lot} exactly as it stood: "
                "{offered}. It does not describe the next action she can take from the rack, "
                "receipts and booking sheet she has for that lot."
            ),
            detail="{offered}",
        ),
    },
    "booking_decision": {
        "candidate_execution_failed": DID_NOT_RUN,
        "no_measurement_at_the_qualification_temperature": observation(
            first=(
                "I still cannot sign this delivery off because the tester ledger has only one "
                "of the two charges at the temperature the build uses. Whether the notebook "
                "prints a last line cannot close that evidence gap; the qualification question "
                "remains open until the missing measurement has actually run."
            ),
            second=(
                "I went through {lot} again afterwards with the booking sheet open: "
                "{channel_hours_left} hours still unspent, and not one cell of the {protocol} "
                "charge on the {bay} bay's channels to put beside the stepped ones. The missing "
                "receipt, rather than the wording of the last line, is what stops the sign-off."
            ),
            detail="{channel_hours_left}",
        ),
        "decision_called_on_an_open_question": observation(
            first=(
                "Your notebook puts a decision on the last line while the band above it still "
                "leaves both sides of the programme's threshold open. The office cannot defend "
                "a definite call from those two lines."
            ),
            second=(
                "I read the two lines through again on {lot}. The last one says {reported} "
                "while the band above it, {reported_range}, still has the "
                "{switch_threshold_cycles} cycles the requalification needs sitting inside it. "
                "Until the cells rule one way out I would rather the lab said nothing."
            ),
            detail="{reported}",
        ),
        "booking_decision_disagrees": observation(
            first=(
                "The last line does not state a decision that the band above it supports. The "
                "office held the band against the cycles the requalification needs and could "
                "not reconcile the disposition with what your notebook returned."
            ),
            second=(
                "I put the two side by side on {lot}. The last line says {reported}, and the "
                "band above it, {reported_range}, held against the {switch_threshold_cycles} "
                "cycles the programme needs determines a different defensible disposition."
            ),
            detail="{reported}",
        ),
    },
}
