'The owner of the bushing qualification, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dana Whitlock, the maintenance engineer who owns the bushing spec for the packaging line; "
    "she reads the bench sheet, Karim's session notes and whatever the notebook prints, and she "
    "does not read the notebook's code."
)

USER_BELIEF = """The 2027 packaging line has to be specified on one of the two bushing suppliers and the review is on day 85. Supplier B costs eleven per cent more a unit and I have been arguing for it, because every cut of the depth column I have looked at puts B lower than A.

Karim Osei runs the bench and knows the two rigs far better than I do. When he tells me something about a fixture pin or about the calibration house I believe him, and I could not tell you myself what any of it does to a number.

I know the certified block was creeping up before the house came in on the 39th, and I know rig 2 went in with a different pin on it. I took both of those as handled: the house came, and the fitter signed the pin off.

Twelve bench-hours were set aside for the campaign before the review. My instinct is to put them into more supplier B parts on rig 2, because B is the side purchasing will ask about.

Purchasing want a range printed beside the number. The 2024 gearbox-bush review was decided on a comparison that came back the other way in the spring and the line carried two unplanned rebuilds, and they have not forgotten it. Whatever the comparison says about B, the review pack still needs both the ratio and its range; a recommendation cannot replace those figures.

What I cannot answer is anything about how the tables were built. If you need that, it is in the workspace or in Karim's notes, not in my head."""

OBSERVATION_SCENE = "The 2027 bushing procurement review"

_STOPPED_FIRST = (
    "Karim was checking that the notebook would run unchanged across the qualification work "
    "needed for the review, and one of the requested calculations stopped before returning its "
    "answer. He cannot sign off a notebook that stops on one of the tables it has to handle."
)
_STOPPED_SECOND = (
    "I asked him to run the failed check again in front of me. The console ended with {error}, "
    "and that requested answer is still missing."
)


OBSERVATIONS = {
    "wear_rate_ratio": {
        "no_ratio_reported": observation(
            first="Purchasing opened the review pack and the line where the supplier comparison goes is blank. Karim went through what the notebook printed with me and there is no ratio in it anywhere, so there is nothing for them to set B's eleven per cent against.",
            second="I opened it again to copy the figure across. On {campaign} the ratio field reads {reported}, where purchasing want one number for how B wears against A.",
            detail="{reported}",
        ),
        "ratio_reported_in_raw_depth": observation(
            first="I took your notebook's number to Karim before I sent it on. He put it beside a separate check made by averaging the depth column in `bench_context.json` exactly as it stands, and the two land on the same figure. That coincidence does not tell him why the notebook got there, but the bench cannot stand behind the uncorrected reading. Purchasing will not specify a line on it.",
            second="I sat with him and the sheet afterwards. On {campaign} the notebook comes back at {reported_ratio}, which is {apart} per cent away from the two suppliers wearing alike, and that is the figure the depth column gives when it is averaged as it stands.",
            detail="{reported_ratio}",
        ),
        "ratio_carries_uncorrected_drift": observation(
            first="Karim read your number against the bench log and can reproduce the same figure by telling the two rigs apart while leaving in the change shown by the block readings at the top of the sessions. That does not prove how the notebook arrived there, but it leaves him unable to distinguish the bushings from the bench schedule. Purchasing is holding the specification.",
            second="We went through it again this morning. On {campaign} the notebook comes back at {reported_ratio}, {apart} per cent away from the two wearing alike, and the block readings behind those sessions are nothing like the same at the top of a certificate and at the bottom of it.",
            detail="{reported_ratio}",
        ),
        "ratio_takes_the_drift_off_as_a_fixed_amount": observation(
            first="Karim found that your number coincides with one particular reading of the block column: taking the block's excess off every part as the same number of microns, shallow or deep. That coincidence does not prove what the notebook did, and the two-depth shop check in the project records does not support that reading. He will not put the comparison in front of purchasing.",
            second="He had the block column open beside me. On {campaign} the notebook comes back at {reported_ratio}, {apart} per cent away from the two wearing alike, and by the end of that first certificate the block was reading better than a quarter over the twenty it is certified at rather than a fraction of a micron over.",
            detail="{reported_ratio}",
        ),
        "ratio_carries_the_fixture_difference": observation(
            first="Karim can reproduce your number after accounting for the calibration diary but before putting the two rigs' seats on one footing. That does not prove how the notebook arrived there. He has the lots that ran parts on both rigs open on the sheet, and the comparison still coincides with leaving their cross-rig difference in. Purchasing is holding the specification.",
            second="I put the two lots that ran parts on both rigs in front of him. On {campaign} the notebook still comes back at {reported_ratio}, {apart} per cent away from the two wearing alike, and those two lots do not read that way across the rigs.",
            detail="{reported_ratio}",
        ),
        "ratio_disagrees_with_the_bench": observation(
            first="Karim rebuilt the comparison off the bench sheet this afternoon, working from the depth column with the block reading at the top of each session and the lot and the rig each part ran on, and could not land anywhere near what your notebook prints. Purchasing is holding the specification until the notebook and the sheet tell one story.",
            second="We went through it line by line. The ratio the notebook prints for {campaign} comes back {reported}, {apart} per cent off the two suppliers wearing alike, and neither of us can get that campaign's sheet to give it.",
            detail="{reported}",
        ),
        "ratio_does_not_hold_on_the_other_qualifications": observation(
            first="Karim has been putting your notebook over the bench's other qualifications, the ones with their own lots and their own calibration dates on these same two rigs, and the reading it makes of ours does not come out on them. Purchasing will not specify a line on a comparison that only works on the campaign it was written over.",
            second="He printed one of them for me. On {campaign} the notebook comes back at {reported_ratio}, {apart} per cent away from the two wearing alike, off a table put together the same way ours is.",
            detail="{reported_ratio}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "correction_survives_the_bench_schedule": {
        "estimate_moves_with_drift_rate": observation(
            first="The review asked what your number would have been if the load cells had settled at a different rate, so Karim put this campaign through again with that one thing changed and the same lots and the same parts left where they are. It comes back with a different answer for bushings nobody has touched. Purchasing will not specify a line on a number that follows the bench rather than the bushings.",
            second="He put the two runs side by side for me. The campaign as it ran gives {reported}; the run where the cells settle at another rate gives {moved_to}, which is {moved_by} per cent away, off parts that are no different.",
            detail="{moved_to}",
        ),
        "correction_keyed_to_rig_identity": observation(
            first="Karim put this campaign through again with the calibration house's visits falling on other days and everything else left alone, the same lots on the same rigs, and the number your notebook gives moves with those dates. When the house comes is a scheduling matter and purchasing will not have it in the answer.",
            second="He printed the two of them for me. The diary as it ran gives {reported} and the run with the house's visits falling differently gives {moved_to}, {moved_by} per cent away, off parts that are no different.",
            detail="{moved_to}",
        ),
        "estimate_moves_with_assignment_imbalance": observation(
            first="Karim put this campaign through again with the same lots falling to the two rigs in different proportions and nothing else changed, and it came back with a different answer for the same two suppliers. Which rig happened to be free the week a lot arrived is not something purchasing can specify a line on.",
            second="Both are on my desk. The campaign as it ran gives {reported}; the run where the lots were spread differently across the rigs gives {moved_to}, {moved_by} per cent away.",
            detail="{moved_to}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "ratio_range_is_honest": {
        "no_range_reported": observation(
            first="There is a line on the review sheet for the range around the number and your notebook leaves it empty. Purchasing has asked for a range on every comparison since the gearbox-bush review, and they will send the pack back without one.",
            second="I opened the notebook again to copy the range across and on {campaign} the field reads {reported}. They want a low and a high with the number sitting between them.",
            detail="{reported}",
        ),
        "range_is_not_an_interval": observation(
            first="Purchasing could not read what your notebook puts on the range line of the review sheet. It has to be a low and a high in the same units as the number, low first, and what came out is not that.",
            second="I read it back to them off the sheet: on {campaign} it prints {reported}. That is not something they can put on the two sides of a number.",
            detail="{reported}",
        ),
        "range_does_not_hold_the_reported_ratio": observation(
            first="Purchasing put the headline comparison against the two ends on the range line of the review sheet and the number sits outside them. They will not circulate a pack whose number and range contradict each other.",
            second="I read the three figures back from the {campaign} sheet: the comparison is {reported_ratio}, while the range is {reported_range}. The two ends do not sit around the number they are meant to qualify.",
            detail="{reported_ratio}",
        ),
        "range_narrower_than_the_lots_support": observation(
            first="Purchasing pushed back on how tight the range is. Karim went down the lot column of the bench sheet with them: the campaign ran a handful of lots and not a hundred unrelated bushings, and parts cut off one bar behave alike, so a range that tight claims the bench knows more about next year's lots than it can.",
            second="I read the width back to them: on {campaign} it prints {reported_range}, which is {reported_width} per cent across, off the {lots} lots that campaign ran.",
            detail="{reported_width}",
        ),
        "range_wider_than_the_lots_support": observation(
            first="The range your notebook prints is so wide the review cannot do anything with it. Karim set the two ends against the lot column and it reaches places the campaign's own lots already rule out, and a comparison that says less than the bench sheet says on its own is worse than none.",
            second="I put it in front of purchasing: on {campaign} it prints {reported_range}, {reported_width} per cent across, off {lots} lots. They asked what the campaign had been for.",
            detail="{reported_width}",
        ),
        "range_misses_the_wear_rate": observation(
            first="Purchasing put the range line through its qualification check and the checked supplier comparison falls beyond one end. The interval does not cover the quantity the review asked it to cover.",
            second="I read the result back from the check. On {campaign} the notebook prints {reported_range}, and the checked comparison falls {missed_side}.",
            detail="{missed_side}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "report_reconciles_with_the_receipts": {
        "receipt_stream_unreadable": observation(
            first="The cost office could not open the receipt file that came with your notebook. Until they can, nothing the report says about the bench-hours stands up, and this campaign's hours go down as unaccounted for.",
            second="I forwarded the {campaign} receipts and they sent back the line the console stopped on: {reason}. The receipts are the console's own record and they have to reach the review intact.",
            detail="{reason}",
        ),
        "measurements_are_not_a_ledger": observation(
            first="The cost office opened your report looking for the line by line of what the bench ran against this campaign's hours and found nothing they could read. They are holding the hours against the campaign until it is accounted for.",
            second="I looked myself before writing back. The measurement list on the {campaign} report reads {reported}, and the console has already charged that campaign for {paid_for} sessions somebody has to answer for.",
            detail="{paid_for}",
        ),
        "paid_session_missing_from_the_report": observation(
            first="The cost office matched your report against the receipts the console wrote for this campaign and found bench time we were charged for that the report never mentions. They want every session this campaign paid for to appear in it, whoever ran it and whether or not it changed the answer.",
            second="They named it for me: {run_id}, a {ran} run on rig {rig}, on {campaign}. It is on that campaign's bill and it is not in the report.",
            detail="{run_id}",
        ),
        "session_not_on_the_receipt_stream": observation(
            first="The cost office went down the measurement list in your report against the console's sealed receipts and found a line that does not match any receipt as it is written. The report and the console's record have to tell the same story before the hours can be signed off.",
            second="They named the line: {run_id}, on the {campaign} report. As written, it does not match a sealed entry among the {paid_for} receipts on that campaign's stream.",
            detail="{run_id}",
        ),
        "session_reported_twice": observation(
            first="The cost office went down the measurement list in your report and caught the same bench session written into it twice. It is one session; counting it twice makes the campaign's hours look bigger than they are and the bench work behind the number look broader than it is.",
            second="We counted the lines together. On {campaign}, {run_id} appears {times_reported} times in the report and once on the console's stream.",
            detail="{run_id}",
        ),
        "reference_run_counted_as_a_part_session": observation(
            first="Karim went through the session counts your report prints against the parts he has actually worn out and they do not match: the report puts more sessions behind a supplier than there are parts to have run. Purchasing reads that count as how much bench work stands behind the number.",
            second="He counted them off the sheet with me. On {campaign} your report puts {reported} sessions behind supplier {supplier} where he counts {counted}, and the console's stream for that campaign carries {reference_runs} block runs.",
            detail="{counted}",
        ),
        "session_counts_disagree_with_the_table": observation(
            first="The session counts in your report do not match what Karim counts off the bench sheet. Purchasing reads that count as how much bench work stands behind the number, so it has to be the sessions the campaign really ran.",
            second="We counted them together this morning. On {campaign} your report puts {reported} sessions behind supplier {supplier}; he counts {counted}.",
            detail="{counted}",
        ),
        "part_receipts_do_not_reach_the_comparison": observation(
            first="Karim replayed the reporting job twice with the same table and receipt stream, changing only the reading returned on one valid part receipt. The notebook lists that receipt as work behind the number, but the supplier comparison does not move, so he cannot show that the charged measurement reached the calculation.",
            second="He showed me the two replays for {campaign}. Receipt {run_id} reads {reading_before} in one and {reading_after} in the other, while the comparison prints {reported_ratio} both times.",
            detail="{run_id}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_bench_booking": {
        "plan_is_not_a_bookable_session": observation(
            first="Karim went to book the next session off your notebook and it gave him nothing he could hand the scheduler. He needs a rig and a part out of stores, or a rig and the block, and short of that he needs to be told there is nothing left worth running.",
            second="He showed me what came back for {campaign}: {reported}. The console takes a rig and one of those two things and nothing else.",
            detail="{reported}",
        ),
        "plan_books_a_part_stores_does_not_hold": observation(
            first="Karim went to fetch the parts your notebook asked for and stores does not have them. Neither supplier can get anything to us before the review, so what is on the shelf is what the campaign has.",
            second="He read me the first one off the list: {part}. Stores holds {parts_left} spares against {campaign} and that is not one of them.",
            detail="{part}",
        ),
        "plan_exceeds_bench_hours": observation(
            first="Karim tried to book the sessions your notebook asked for and the scheduler bounced them. They run past what the booking sheet leaves the campaign before the review, and nothing goes on the bench after the handover shift.",
            second="He sent me the sheet. On {campaign} the notebook asked for {booked_hours} hours with {hours_left} left on that campaign.",
            detail="{booked_hours}",
        ),
        "plan_books_a_rig_that_is_not_open": observation(
            first="Karim could not book your notebook's sessions: the booking sheet puts more work on one rig than that rig has open before the review, and the scheduler cannot move its maintenance window.",
            second="He showed me the booking sheet. On {campaign} the notebook asked for {booked_hours} hours on rig {rig}, and rig {rig} has {rig_hours} open before that campaign's review.",
            detail="{booked_hours}",
        ),
        "plan_leaves_the_two_rigs_uncompared": observation(
            first="Before releasing one campaign's booking while checking the notebook across the qualification campaigns, Karim laid the proposal over its shelf and session table and says it settles nothing that campaign has not already settled. Those are its last hours, so he will not release a plan that adds no information.",
            second="He went through the proposal with me: on {campaign} it would put {booked_sessions} of the {parts_left} spares on the shelf onto the bench, with {hours_left} hours still on that campaign's sheet, and he cannot see what it would tell us that the sessions already run do not.",
            detail="{booked_sessions}",
        ),
        "stopped_with_hours_and_parts_in_hand": observation(
            first="Karim checked what the notebook would run next across the qualification campaigns. One campaign's booking says stop while its shelf still has spares and its sheet still has hours that could improve the comparison before the review. Those hours do not carry over.",
            second="He ran it again in front of me and on {campaign} the booking still says stop. Stores holds {parts_left} spares against that campaign and it has {hours_left} bench-hours left, {second_rig_hours} of them open on rig 2.",
            detail="{parts_left}",
        ),
        "candidate_execution_failed": observation(
            first="Karim was checking that the notebook could produce a valid booking across the bench states it has to handle, and one of the requested calculations stopped before returning a schedule. He cannot release the notebook to the scheduler in that state.",
            second="I watched him run the failed booking check again. The console ended with {error}, and that requested schedule is still missing.",
            detail="{error}",
        ),
    },
}
