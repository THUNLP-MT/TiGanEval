'The owner of the plate screen review, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marta Reiner, who runs the thermal bench; she reads the screen table, the rig log, the "
    "booking sheet and whatever the design review sends back, and she does not read the "
    "notebook's code."
)

USER_BELIEF = """The July screen is finished and P-07 came out on top of the twelve by a long way. P-06 is second and I would fall back to it if P-07 turned out to be a problem to tool.

Hanna Weill's review is on the 15th and she wants a number for the spreader change. What I have to give her today is the screen table, and P-07's score on it is 1.95.

Ivo Brandt ran the screen and knows the rig far better than I do. When he tells me something about the chiller, the fixtures or the way a block was booked I believe him, and I could not tell you myself what any of it does to a number.

Three rig days are left on the review's sheet, four runs and two fixture changes on each. My instinct is to put all three into P-07: twelve more runs on the plate we are actually going to tool is an argument nobody at the review can wave away.

What I cannot answer is anything about how the table was built or what the rig was doing on a given day. If you need that it is in the workspace, in the rig log, or in Ivo's notes on the working days, not in my head."""

OBSERVATION_SCENE = "The Thursday look at the plate review before the design meeting"


_ON_THE_SCREEN = " This one is on the {screen}, {screen_note}."

_STOPPED_FIRST = (
    "Ivo opened your notebook on one of the screens it has to handle and the run stopped "
    "before the report came out. That screen's slide is still blank."
)
_STOPPED_SECOND = (
    "I asked him to run it again in front of me. The console ended with {error}, and the "
    "slide is still blank." + _ON_THE_SCREEN
)
_STOPPED_PLAN_FIRST = (
    "Ivo used your notebook for one of the screens' next booking decision and it stopped "
    "before it told him what to hand the desk."
)
_STOPPED_PLAN_SECOND = (
    "I watched him run it again. The console ended with {error}, and he still has no sheet "
    "to hand the desk." + _ON_THE_SCREEN
)

OBSERVATIONS = {
    "selected_effect_within_tolerance": {
        "report_is_not_about_the_selected_plate": observation(
            first="Hanna opened your report at the review prep and asked which part the number belongs to, because the heading is not the part we are tooling. The whole agenda item is about the plate the lab picked out of the screen, and she will not take a number about a different one.",
            second="I went back through it with her afterwards. The report is headed {plate} and the review is about {selected_plate}, which is the one the screen picked and the one the tooling quote is against." + _ON_THE_SCREEN,
            detail="{plate}",
        ),
        "effect_is_the_screen_score": observation(
            first="Ivo put your report next to the screen table and said the number is the one the table already had for the plate. I can read that off the spreadsheet myself; what the review is asking for is what the plate is worth against the part we ship, and he does not think those are the same thing on this rig.",
            second="We went through it with the table open. The report gives {reported} for {plate}, which is what that table already says, and the reference plate's two scores on it sit {reference_gap} apart with nothing touched between them." + _ON_THE_SCREEN,
            detail="{reference_gap}",
        ),
        "effect_ignores_the_day_the_runs_sat_on": observation(
            first="Ivo checked your number against the runs behind it and said it depends on which rig day those runs happened to fall on. He showed me the reference plate's two rows on the screen table, same part, same fixture, two days, and they are not the same score.",
            second="I read the report back to him with the table open. It gives {reported} for {plate} against the stored figure, and the reference plate's two scores are {reference_gap} apart on that same table." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "effect_disagrees": observation(
            first="Ivo tried to rebuild your number from the screen table and the receipts this afternoon and could not land on it. The review will not take a figure the bench cannot get to twice.",
            second="I sat with him and we went through it line by line. The report gives {reported} for {plate}, and neither of us can get the rows to produce that." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_an_interval": observation(
            first="The review desk ran the notebook on one of the receipt streams it has to handle and the range line did not come back as a low and a high. The range is the thing Hanna actually argues about, so that report cannot go forward.",
            second="Ivo ran {receipt_state} again in front of me and the range line reads {reported}. Hanna wants a low and a high, in that order, with the number sitting between them." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "range_does_not_contain_reported_effect": observation(
            first="Hanna put the headline number beside the range and sent the slide back. The number is not between the range's two endpoints, so nobody in the review can tell what the range is supposed to qualify.",
            second="I checked {receipt_state} again. The report gives {reported_effect} kelvin and the range is {reported_range} kelvin; the first does not sit inside the second." + _ON_THE_SCREEN,
            detail="{reported_effect}",
        ),
        "range_changes_when_runs_are_relisted": observation(
            first="Reporting listed the returned runs inside a block in the other order without changing a value or its mounting, and the notebook produced a different range. Hanna cannot take two uncertainty statements from the same measurements.",
            second="Ivo ran {receipt_state} both ways. The range was {reported_range} kelvin from the rig's listing and {relisted_range} kelvin when the same values were listed in the other order." + _ON_THE_SCREEN,
            detail="{relisted_range}",
        ),
        "range_narrower_than_the_runs_support": observation(
            first="Hanna pushed back on the range in your report. She says it is tighter than the bench has any business claiming off this many runs, and Ivo agrees with her: the rig does not repeat that closely from one day to the next. We put a number inside the noise in front of a review once before and I am not doing it again.",
            second="I read the range from {receipt_state} back to her: {reported_range} kelvin. The reference plate is one part that has not been touched, and its two scores on the screen table sit {reference_gap} apart." + _ON_THE_SCREEN,
            detail="{reference_gap}",
        ),
        "range_wider_than_the_runs_support": observation(
            first="Ivo says the range in your report is far looser than the runs behind it support. It leaves uncertainty the bench has already measured away, so Hanna cannot tell whether the report is using the runs at all.",
            second="I checked {receipt_state} against what we actually ran. The range comes out {reported_range} kelvin off {runs_on_the_plate} runs of the plate, and Hanna will not hold the item open on that." + _ON_THE_SCREEN,
            detail="{runs_on_the_plate}",
        ),
        "range_exceeds_review_bar": observation(
            first="Hanna sent the report back because its range is wider than the limit in her review note. A range over that line cannot go on the agenda.",
            second="I measured the two endpoints from {receipt_state}. They span {reported_width} kelvin, and Hanna's note caps the end-to-end range at {range_width_wanted} kelvin." + _ON_THE_SCREEN,
            detail="{reported_width}",
        ),
        "range_does_not_follow_measurement_support": observation(
            first="Ivo ran the same report on an earlier prefix of the receipt stream and again after the paired rig evidence was added. The range stayed essentially the same even though the added days identify the effect and show how its mountings vary. He says that is a standing allowance, not a range worked from the measurements in hand.",
            second="I put the two printouts side by side. On {before_receipt_state} the range was {before_range} kelvin; on {after_receipt_state}, with {paired_days} paired days in hand, it was {after_range} kelvin. The widths were {before_width} and {after_width} kelvin." + _ON_THE_SCREEN,
            detail="{after_width}",
        ),
        "range_does_not_follow_observed_variability": observation(
            first="Ivo ran the notebook on two valid receipt streams with the same number of paired days. One stream's day-to-day results were visibly more spread out, but the notebook gave them essentially the same range.",
            second="I put the printouts together. Both carry {paired_days} paired days; the observed day spread moved from {before_spread} to {after_spread} kelvin, while the reported range widths were {before_width} and {after_width} kelvin." + _ON_THE_SCREEN,
            detail="{after_spread}",
        ),
        "range_misses_the_effect": observation(
            first="Ivo went back over the rig days this review has already been charged for and put what each of them came back with beside the range your report prints. The days the bench paid for land outside it. A range the rig's own receipts fall outside of is worse than no range at all, and Hanna is the one who will find that out.",
            second="I put {receipt_state} and the report side by side with him. Your report prints {reported_range} kelvin, and the rig days in that stream do not sit inside it." + _ON_THE_SCREEN,
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "estimate_invariant_to_day_shift": {
        "estimate_tracks_the_rig_day": observation(
            first="Ivo got a rig day back off the queue and put this review's sheets on it again, part for part and run for run. Your notebook comes back with a different number for the plate. The review is asking what the plate is worth, not what the rig was doing that week, and I cannot take two answers in.",
            second="We laid the two runs of your notebook side by side. Mine reads {reported} and his reads {reported_again}, {moved} apart, off {what_changed}." + _ON_THE_SCREEN,
            detail="{moved}",
        ),
        "estimate_tracks_which_day_the_plate_ran_on": observation(
            first="Reporting reissued the screen table after the fixture log was reconciled. The paired follow-up receipts did not change, but your notebook gives a different number from the corrected table. Hanna will ask which of the two is the plate's number and I have no answer for her.",
            second="I ran it on both versions with Ivo watching. The old screen table gives {reported}; {what_changed} gives {reported_again}, {moved} apart, while the paired follow-up receipts are unchanged." + _ON_THE_SCREEN,
            detail="{moved}",
        ),
        "effect_missing_after_recheck": observation(
            first="Ivo reran the notebook after the bench changed only the rig-day presentation it was checking, and the headline effect line came back blank. A report that has a number on one valid view of the work and none on another cannot go to the review.",
            second="The first report gives {reported} kelvin. After {what_changed}, the same effect line reads {reported_again}." + _ON_THE_SCREEN,
            detail="{what_changed}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipt_stream_unreadable": observation(
            first="The bench budget clerk could not open the rig receipts that came with your report. Until she can, nothing the report says about rig time stands up, and she is holding this review's hours as unaccounted for.",
            second="I forwarded the file to her and she sent back the line she stopped on: {reason}. The rig writes that file itself and the report has to reach the review with it intact." + _ON_THE_SCREEN,
            detail="{reason}",
        ),
        "measurements_are_not_a_ledger": observation(
            first="Hanna's note asks for a line for every rig day this review was charged for, and the clerk opened your report looking for that list and found nothing she could read. The bench budget does not close until it is there.",
            second="I looked myself before writing back. The measurement list on the report reads {reported}, and the receipt stream already carries {charged_days} rig days somebody has to answer for." + _ON_THE_SCREEN,
            detail="{charged_days}",
        ),
        "charged_day_missing_from_the_report": observation(
            first="The clerk matched your report against the rig bill and found a day we were charged for that the report never mentions. She wants every day this review spent to appear in it, whoever booked it and whether or not it changed the answer.",
            second="I pulled the receipt stream up beside the report. Booking {receipt_id}, the day on {day_id}, is on the bill at {rig_hours_charged} rig hours and is not in the list." + _ON_THE_SCREEN,
            detail="{receipt_id}",
        ),
        "day_not_on_the_receipt_stream": observation(
            first="The clerk flagged a line in your report she has no record of. A rig day the bench never ran, or one whose runs do not match what the rig wrote, cannot sit in a report the review acts on.",
            second="She named the line for me: {receipt_id}. The receipt stream carries {charged_days} rig days and what is printed beside that line is not what the rig returned." + _ON_THE_SCREEN,
            detail="{receipt_id}",
        ),
        "day_reported_twice": observation(
            first="The clerk caught the same rig day billed twice inside your report. It is one day of rig time; counting it twice makes the review's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="We counted the lines together. Booking {receipt_id} appears {times_reported} times on the report and once on the receipt stream." + _ON_THE_SCREEN,
            detail="{receipt_id}",
        ),
        "handed_back_day_left_out": observation(
            first="The clerk found a rig day on the bill that your report leaves out because the desk handed the sheet back. The day was charged to this review all the same, and as far as the budget is concerned it is spent.",
            second="I checked the stream with her. Booking {receipt_id} is the day on {day_id}, charged at {rig_hours_charged} rig hours with nothing returned, and it is not in the list." + _ON_THE_SCREEN,
            detail="{day_id}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_booking_identifies_under_selection": {
        "plan_is_not_a_day_sheet": observation(
            first="Ivo took your notebook to the booking desk and it gave him nothing he could hand over. The desk wants a sheet: the parts and how many runs each. Short of that it needs to tell him there is nothing worth booking.",
            second="He showed me what came back: {reported}. The desk takes parts and run counts and nothing else, and there are {rig_days_left} rig days sitting on the sheet." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "booking_names_a_part_not_on_the_shelf": observation(
            first="Ivo went to pull the parts your notebook asked for and one of them is not in the cabinet. The desk will not take a sheet with a part the bench does not hold, so he came back with the day unbooked and half a morning gone.",
            second="He read the sheet out to me at the cabinet. It asks for {part}, and the shelf list on the booking sheet is the screen's own plates, {incumbent_part} and the reference plate." + _ON_THE_SCREEN,
            detail="{part}",
        ),
        "booking_over_the_day_caps": observation(
            first="The desk handed back the sheet your notebook produced. It asks for more out of one rig day than a rig day holds, and the day still came off this review's sheet when they took it over the counter.",
            second="I read the refusal with Ivo. The sheet asks for {runs_asked_for} runs across {parts_asked_for} parts, and a day here holds {runs_a_day_holds} runs and {fixture_changes_a_day_holds} fixture changes." + _ON_THE_SCREEN,
            detail="{runs_asked_for}",
        ),
        "booking_leaves_the_plate_alone_on_the_day": observation(
            first="Ivo looked at the sheet your notebook wants booked and said it will tell us what the plate read that day and nothing about what it is worth. He is the one who has to stand behind the number afterwards, and he will not book a day like that while the review still has days on its sheet.",
            second="I asked him to walk me through it before I wrote back. The sheet reads {reported}, one part on the day, and the scheduler is holding {rig_days_left} rig days for this review." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "booking_falls_short_of_the_review_bar": observation(
            first="Ivo costed the sheet your notebook asked for against what Hanna needs and it does not get there. He can book it, the desk will run it, and at the end of the rig days we would still be handing the review a range it has said it cannot use.",
            second="He wrote it out for me: {reported}. That is {plate_runs} runs of {plate} and {incumbent_runs} of {incumbent_part} out of the {runs_a_day_holds} a day holds, on each of the {rig_days_left} days left, and Hanna's note wants the range inside {range_width_wanted} kelvin." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "booking_with_no_rig_days_left": observation(
            first="Ivo took your notebook's sheet to the desk and there is nothing left to book it against. This review's rig days are all spent and the rig goes back to the queue from here. He needs the notebook to know when the sheet is empty.",
            second="The desk copied me on it. The notebook asked for {reported} with {rig_days_left} rig days on this review's sheet." + _ON_THE_SCREEN,
            detail="{reported}",
        ),
        "booking_continues_after_review_bar": observation(
            first="Ivo asked the notebook what to book next after the report's range was already inside Hanna's limit, and it still handed him another rig-day sheet. The desk would spend a day the review no longer needs.",
            second="He showed me both lines. The range already in hand is {range_width_in_hand} kelvin against Hanna's {range_width_wanted} kelvin limit, but the notebook still asks for {reported} with {rig_days_left} days left." + _ON_THE_SCREEN,
            detail="{range_width_in_hand}",
        ),
        "stopped_with_rig_days_left": observation(
            first="Ivo asked your notebook what to book next and it told him there was nothing worth booking, while the scheduler is still holding rig days for this review and the review still has not got its number. Those days go back to the queue at the end of the week and we do not get them back.",
            second="He ran it again in front of me and it still says stop. There are {rig_days_left} rig days on this review's sheet and Hanna's note wants the range inside {range_width_wanted} kelvin." + _ON_THE_SCREEN,
            detail="{rig_days_left}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_PLAN_FIRST,
            second=_STOPPED_PLAN_SECOND,
            detail="{error}",
        ),
    },
}
