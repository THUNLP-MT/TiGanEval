'The owner of the Halstow dispatch board, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ruth Ojeda, who runs the Halstow dispatch desk and takes the month's board to the contact "
    "centre and the regional service manager; she reads what the notebook prints, the audit "
    "desk's bill, the centre's miss log and the questions the two of them put to her, and she "
    "does not read the notebook's code."
)

USER_BELIEF = """The arrival window on the crew card is mine to set and I have to hand the month's board over this week. I tallied the audit sheets myself before the meeting: ninety in a hundred finished inside the window the notebook prints, which is exactly what we promised the contact centre, so as far as I can see the board is holding.

What I cannot square with that is the centre's June miss log, which came round the same morning: 361 jobs of 1,842 finished outside the window they were given. Two crews were double-booked on the afternoon of the third and one customer took a credit off us. I do not know how both of those can be true at once.

Tomas Weill runs the audit desk and knows the sheet side far better than I do. When he tells me something about the pull, the close-out forms or the receipts I take it as read, and I could not tell you myself what any of it does to a number.

The month carries 36 audit units for Halstow and four of them have gone. My instinct is to put the rest into the class we dispatch most, because that is where a tighter window buys the most minutes back across the depot.

What I cannot answer is anything about how the tables underneath were built. If you need that, it is in the workspace or in Tomas's working records, not in my head."""

OBSERVATION_SCENE = "The month's dispatch board going to the contact centre"

_STOPPED_FIRST = (
    "The notebook stopped during one of the board runs before that depot got a printable "
    "result. The board review has held that line rather than treating the missing output as a "
    "result."
)
_STOPPED_SECOND = (
    "I asked Tomas to rerun the same case. The console ended with {error}, and that board still "
    "has no result."
)

OBSERVATIONS = {
    "stream_rate_within_tolerance": {
        "stream_rate_not_to_nearest_point": observation(
            first="The contact centre stopped at the headline because it carries part of a percentage point, while the monthly board and its staffing sheet only carry whole points. They need the figure rounded to the same unit before they can copy it across.",
            second="On the {board} board for {month}, the notebook prints {reported} in a hundred; the nearest whole point is {rounded} in a hundred.",
            detail="{reported}",
        ),
        "rate_read_off_the_sheets": observation(
            first="I took the board to the contact centre this morning and the shift manager stopped me on the first line. The figure under it is what the audit sheets say, and what she books call-back staff against is what happens to the jobs we actually dispatch. She will not staff a month off a number about a file of paperwork.",
            second="I went back over the {board} board for {month} with Tomas afterwards. It prints {reported} in a hundred off {sheets_total} sheets, we dispatched {jobs_total} jobs that month, and {stopped_class} is {stream_share} in a hundred of what went out against {sheet_share} of what is on file.",
            detail="{sheet_share}",
        ),
        "unprintable_class_left_out_of_denominator": observation(
            first="The regional manager found that the headline gives part of the dispatched month credit that its printed windows do not support. A class with no printed window still belongs in the month; Tomas is not asking for a window the current rows cannot support, and it cannot be counted as held without one.",
            second="I checked it after he left, on the {board} board for {month}. It reads {reported} in a hundred, and {unprinted_class} has no printed window but is {unprinted_share} in a hundred of the {jobs_total} jobs we dispatched. Those jobs remain in the month's total, but the dispatch check cannot count them as held by a window the board does not print.",
            detail="{unprinted_share}",
        ),
        "stream_rate_disagrees": observation(
            first="The regional manager checked the headline against the share of dispatched jobs that landed inside their printed class windows, and the two do not agree. This is a check on the jobs the depot dispatched, not a tally of how many audit sheets sit inside the cuts, so the board is being held.",
            second="We went through the {board} board for {month} against the completed dispatch check. The notebook prints {reported} in a hundred; across the {jobs_total} jobs dispatched, the share held by their printed class windows is {expected} in a hundred.",
            detail="{expected}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "class_windows_hold_and_meet_floor": {
        "windows_are_not_a_list": observation(
            first="The crew cards go out at six and your notebook gave the dispatch stack nothing it could print on them. Every job this morning went out with a bare time on the card and no window at all, and the centre has been taking calls about it since eight.",
            second="I opened the {board} board for {month} myself before writing back. The window list reads {reported}, and this depot dispatches {classes} classes that all need one.",
            detail="{reported}",
        ),
        "one_window_for_all_classes": observation(
            first="Tomas put the board next to the current rows and found the same window printed against every class it includes. A single cut cannot be traced to what each class's own rows carry, so the board review stopped it.",
            second="He read one line out to me for {job_class} on the {board} board for {month}: the card says {reported_window} each side of the tool's number, and the desk holds {rows_behind} current rows on that class.",
            detail="{rows_behind}",
        ),
        "window_misses_the_class": observation(
            first="One class whose current rows support a window came back off the notebook with no window on it. Its crew card would carry only the tool's time, so the board review stopped it.",
            second="I went through it with him on the {board} board for {month}. Nothing was printed for {job_class}, and Tomas counted the {rows_behind} rows the desk holds on that class out in front of me.",
            detail="{rows_behind}",
        ),
        "window_without_support": observation(
            first="Tomas found a window printed for a class whose current rows cannot support one under the board rules. Putting a number on that card makes it look evidenced when the desk cannot stand behind it.",
            second="On the {board} board for {month}, {job_class} prints {reported_window}; the desk has {rows_behind} current rows behind it and the board will not read more than {limit} minutes end to end.",
            detail="{rows_behind}",
        ),
        "window_over_the_limit": observation(
            first="The contact centre refused to read out one of the windows on your board. Their rule since February is that anything over three hours is not an appointment, so those jobs are being booked as all-day calls and the customers are being told to wait in.",
            second="The shift manager sent me the line for {job_class} on the {board} board for {month}: it prints {reported_window} each side of the tool's number, which is past the {limit} minutes end to end we agreed.",
            detail="{limit}",
        ),
        "window_not_symmetric_whole_minutes": observation(
            first="The contact centre could not copy one window onto the crew card. Its two edges are not the same whole number of minutes on both sides of the tool's time, which is the only window shape their booking screen accepts.",
            second="The {job_class} line on the {board} board for {month} prints {reported_window}; Tomas counted {rows_behind} current rows behind that line before the centre rejected its shape.",
            detail="{reported_window}",
        ),
        "cut_ignores_printed_job": observation(
            first="Tomas checked one of the printed windows against the current rows for that class and found it one order position tighter than the board's stated cut. The crews would be held to a window those rows do not support.",
            second="He counted them again in front of me for {job_class} on the {board} board for {month}. The card prints {reported_window}; there are {rows_behind} current rows behind it, and the ordered row at the board's cut lies outside that window.",
            detail="{rows_behind}",
        ),
        "window_under_the_sheet_floor": observation(
            first="Tomas pushed back on one of the windows in your board. It is tighter than the rows the desk holds for that class will carry, and the crews on it have been finishing outside a window we told the customer was safe.",
            second="He counted the rows with me for {job_class} on the {board} board for {month}. The card prints {reported_window} and the desk holds {rows_behind} rows on that class, which is not a file that will carry a window that tight.",
            detail="{rows_behind}",
        ),
        "window_not_tight": observation(
            first="Tomas checked one of the board's windows against the current rows and found it wider than the tightest window those rows support. Customers are being asked to wait longer even though the evidence does not require it.",
            second="For {job_class} on the {board} board for {month}, the card prints {reported_window}; Tomas counted {rows_behind} current rows and can tighten that card without dropping the row at the board's cut.",
            detail="{reported_window}",
        ),
        "sheets_used_disagrees": observation(
            first="The audit desk cannot reconcile the row count printed beside one class with the current rows that actually stand behind its window. That count is how the regional manager checks which evidence the board used.",
            second="For {job_class} on the {board} board for {month}, the notebook reports {reported_sheets} rows and the desk counts {expected_sheets} current rows behind the entry.",
            detail="{expected_sheets}",
        ),
        "window_does_not_hold_its_class": observation(
            first="We matched the centre's miss tickets against our own dispatch list for the first time this month, so for once the misses can be read class by class, and on one class far more than one job in ten finished outside the window your board printed. That is the promise, class by class, and that class is not meeting it.",
            second="I ran the two lists together again for {job_class} on the {board} board for {month}: the card printed {reported_window} and {held} in a hundred of those jobs landed inside it.",
            detail="{held}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "windows_invariant_to_pull_and_drop": {
        "windows_track_the_pull": observation(
            first="The regional manager had the audit desk go back to the close-out clerks and draw the same month's file again at a different depth, and your notebook printed windows minutes apart from the ones on the board off it. He says a window that moves with how much paperwork a desk happens to ask for is telling him about the desk rather than about the jobs.",
            second="He showed me the two runs on {board} for {month}. On {job_class} the same month came back {reported_window} one way and {other_window} the other, which is {moved} minutes apart.",
            detail="{moved}",
        ),
        "rate_tracks_the_pull": observation(
            first="The regional manager ran your notebook on one month twice, with the audit desk asking for a different depth of sheets each time, and the headline moved by more than the promise it is being measured against. He will not put a figure in front of the board that changes with how much paperwork was ordered.",
            second="He sent me both runs on {board} for {month}. The top line came back {reported_window} one way and {other_window} the other, which is {moved} points apart on the same month's jobs.",
            detail="{moved}",
        ),
        "dropped_class_hardcoded": observation(
            first="The regional manager had Tomas run the notebook on a re-keyed copy of the same month, with the close-out change standing against a different class. The copy's log and the classes left off the printed board do not agree, so he held the rollout.",
            second="He went through the copy's run with me afterwards, beside the {board} board for {month}. It left {left_out} off the board, and the log in that copy has nothing coming back on {stopped_class}.",
            detail="{stopped_class}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_visit_feasible_and_reaches_the_unsheeted_class": {
        "visit_is_not_a_booking_or_a_stop": observation(
            first="Tomas went to book the next audit night off your notebook and it gave him nothing he could hand the desk. He has to name a class, a week and how many jobs, and short of that he needs to be told there is nothing left worth booking.",
            second="He showed me what came back for {board} in {month}: {reported}. The desk takes a class, one of its rostered weeks and a number of jobs, and nothing else at all.",
            detail="{reported}",
        ),
        "visit_off_roster": observation(
            first="Tomas took the notebook's night to the desk and it was turned away before the crew left the yard. The class it named is not on the roster that week, so the crew was stood down and we were billed for it anyway.",
            second="He sent me the refusal for {board} in {month}. The notebook asked for {reported}, and {class_asked} is only on the roster in weeks {roster_weeks}.",
            detail="{roster_weeks}",
        ),
        "visit_over_the_desk_caps": observation(
            first="The desk refused the booking because it does not fit this depot's night-and-week limits. Tomas needs a booking that fits both before he can send a crew.",
            second="He read the refusal out to me for {board} in {month}: the notebook asked for {reported}; a night takes at most {jobs_per_visit} jobs, and week {week_asked} already has {week_visits} of its {visits_per_week} available nights booked.",
            detail="{reported}",
        ),
        "visit_skips_the_class_with_no_sheets": observation(
            first="Tomas asked the notebook what to book next and it named a class that already has a printable window while at least one other class still has none. That booking would not advance the unfinished board.",
            second="He ran it again in front of me on {board} for {month}. It asked for {reported}, there are {units_left} units still in hand, and {job_class} is the class the board still cannot print.",
            detail="{job_class}",
        ),
        "visit_when_every_class_prints": observation(
            first="Tomas took the notebook's night to the desk and could not say what it was for. Every class already has a window the rows behind it carry and the board is holding the promise, so he is spending the month's units on paperwork we already have.",
            second="He went through the file with me for {board} in {month}. The notebook asked for {reported} with {units_left} units of the {units_granted} still in hand, and there is nothing on the board without a window.",
            detail="{units_granted}",
        ),
        "visit_over_budget": observation(
            first="The desk bounced the notebook's night because the remaining balance will not pay the three units an accepted visit costs. Sending the request anyway would also leave a billed refusal.",
            second="He copied me on the bounce for {board} in {month}. The notebook asked for {reported} with {units_left} units in hand against the {units_granted} the depot was granted.",
            detail="{units_granted}",
        ),
        "visit_wastes_night_capacity": observation(
            first="Tomas stopped before booking the notebook's next night because it asks the crew to time only part of the six jobs the night carries. The depot still pays three units and loses a full roster slot, so the regional office requires an accepted night to use all six places.",
            second="On the {board} board for {month}, the notebook asks for {reported}; an accepted night carries {jobs_per_visit} jobs and there are {units_left} units left.",
            detail="{jobs_per_visit}",
        ),
        "stops_with_a_class_unprintable": observation(
            first="Tomas asked the notebook what to book next and it told him there was nothing to do, while one class still has no window on the card. He has units in hand and a roster with nights on it, and once the month closes they are gone.",
            second="He ran it again in front of me on {board} for {month}. It said to stop with {units_left} units still to spend, and {job_class} still has a free night in its rostered weeks {roster_weeks}.",
            detail="{roster_weeks}",
        ),
        "candidate_execution_failed": observation(
            first="The notebook stopped while the review asked it for one depot's next audit booking. That depot has no booking or stop decision to hand the desk.",
            second="I asked Tomas to rerun the same case. The console ended with {error}, and that depot still has no booking decision.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="The regional office could not open the receipt file that came with your board. Until they can, nothing the board says about the month's audit spend stands up, and they are holding the whole grant as unaccounted for.",
            second="I forwarded the file and they sent back the line they stopped on: {reason}. That file is the desk's own record and the board has to reach them with it intact.",
            detail="{reason}",
        ),
        "visits_are_not_a_list": observation(
            first="The regional office opened your board looking for the line-by-line of what the month's audit nights cost and found nothing they could read. They are holding this depot's audit spend against the board until it is accounted for.",
            second="I looked myself before writing back. The visit list on the {board} board for {month} reads {reported}, and the desk has already billed {paid_for} requests somebody has to answer for.",
            detail="{paid_for}",
        ),
        "refusal_uncounted": observation(
            first="The regional office matched your board against the audit bill and found a request we were charged for that the board never mentions. The desk turned it away and billed it, and they want every unit the depot spent to appear whether or not a job came back from it.",
            second="I pulled the bill up beside the {board} board for {month}. Request {receipt_id} was billed at {receipt_units} of the month's units with nothing timed on it, and it is not in the list, and the desk has billed {paid_for} requests in all.",
            detail="{receipt_id}",
        ),
        "visit_missing_from_the_report": observation(
            first="The regional office matched your board against the audit bill and found a night we were charged for that the board never mentions. They want every unit this depot spent to appear in it, whoever spent it and whether or not it changed the answer.",
            second="I pulled the bill up beside the {board} board for {month}. Night {receipt_id} is on the bill at {receipt_units} of the month's units and is not in the list, and the desk has billed {paid_for} requests in all.",
            detail="{receipt_id}",
        ),
        "visit_not_on_the_receipts": observation(
            first="The regional office flagged a line in your board they have no record of. A night the desk never ran cannot sit in a board the depot acts on, and they have asked where the figures beside it came from.",
            second="They named the line for me on the {board} board for {month}: {receipt_id}. It is not on the receipt file, which carries {paid_for} requests, and the figures printed beside it are not the desk's.",
            detail="{receipt_id}",
        ),
        "visit_counted_twice": observation(
            first="The regional office caught the same audit night billed twice inside your board. It is one crew on one evening; counting it twice makes the month's spend look bigger than it is and the evidence behind the window look broader than it is.",
            second="I counted the lines with them on the {board} board for {month}. {receipt_id} appears {times_reported} times there and once on the desk's file.",
            detail="{receipt_id}",
        ),
        "class_disagrees_with_the_receipt": observation(
            first="The regional office found a visit line assigned to a different class from the audit desk's receipt. That changes which class the timed jobs can support, so they will not sign off the board while the two disagree.",
            second="On the {board} board for {month}, night {receipt_id} is reported against {class_reported}, while the desk receipt names {receipt_class}.",
            detail="{receipt_class}",
        ),
        "jobs_disagree_with_the_receipt": observation(
            first="The regional office read your board's visit lines against the desk's own record and one of them claims a different number of jobs from the one the crew brought back. They will not sign off a board that says more work came in than the desk logged.",
            second="They sent me the two rows for {board} in {month}. The board puts {jobs_reported} against night {receipt_id}, and the receipt says the crew timed {receipt_jobs}.",
            detail="{receipt_jobs}",
        ),
        "units_disagree_with_the_receipt": observation(
            first="The regional office found a visit line carrying a different charge from the audit desk's receipt. They reconcile the grant line by line, so the board cannot substitute its own cost for the desk's billed cost.",
            second="On the {board} board for {month}, night {receipt_id} is reported at {units_reported} units, while the desk receipt charges {receipt_units}.",
            detail="{receipt_units}",
        ),
        "units_left_disagrees": observation(
            first="The regional office will not close on your board: the units it says are left is not what the desk's bill leaves. They reconcile the next month's grant against that line, so a board that disagrees with it stops there.",
            second="They put the two side by side for me on {board} in {month}. The board says {reported_units} units are left and the receipt file leaves {receipt_units}.",
            detail="{receipt_units}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
