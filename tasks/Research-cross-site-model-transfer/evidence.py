'The owner of the triage report, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ilse Verhoeven, who runs the ticket triage service and takes its quarterly numbers to centre "
    "managers as the notebook moves between centres, including Ridgeline and Brookfield; she reads "
    "what the notebook prints, the review desk's bill and the questions the managers put to her, "
    "and she does not read the notebook's code."
)

USER_BELIEF = """The triage pipeline went live at Brookfield on 3 August and I have to put a number in front of both centre managers this week. The March build read eight in a hundred wrong on the Ridgeline rows it was never trained on, and the first fortnight of Brookfield reviews came back at about the same, so as far as I can see the move went cleanly and I expect the report to say so.

Dilan Roche runs the review desk and knows the intake side far better than I do. When he tells me something about the queue, the reconciliation export or the counters I take it as read, and I could not tell you myself what any of it does to a number.

The quarter carries six hundred review units for Brookfield and Dilan has spent two hundred and forty of them, all through the queue. My instinct is to put the rest back into Ridgeline, because that is the centre we have the longest record on and its manager wants her own report next quarter.

Both managers asked for the number to within two points with a range printed under it. The April staffing paper came to them with a range so wide that Brookfield staffed off the middle of it and finished the quarter eleven agents short, and neither of them has forgotten it.

What I cannot answer is anything about how the tables underneath were built. If you need that, it is in the workspace or in Dilan's working records, not in my head."""

OBSERVATION_SCENE = "The quarterly triage report as the notebook moves between centres"

_STOPPED_FIRST = (
    "Dilan ran your notebook for the quarterly hand-off and one report step stopped before it "
    "returned an answer. The manager for that run still has an empty line where the number goes."
)
_STOPPED_SECOND = (
    "I asked him to run it again in front of me. He isolated the stopped step as {operation}; "
    "the console ended with {error}, and that answer is still empty."
)

OBSERVATIONS = {
    "served_stream_error": {
        "error_taken_from_the_source_centre": observation(
            first="I took your report round the centre managers this morning and the one it is about stopped me on the first line. The number you give her is the number the pipeline has always carried at Ridgeline, and she wants to know what part of it came from her own centre at all. She will not staff off a figure that is really about somebody else's tickets.",
            second="I went back over the {centre} report with Dilan afterwards. It prints {reported} in a hundred, which is what the reserved Ridgeline split has read since March, and the intake counters say {skipped_total} of {received_total} tickets never went to the queue at all.",
            detail="{skipped_total}",
        ),
        "tickets_the_queue_never_showed_left_out": observation(
            first="The manager your report is about read it next to her own intake counters and said it cannot be about her whole centre. The reviews behind it are the tickets her reviewers were handed, and the counters say the desk never handed them everything. She is being asked to staff for the tickets that arrive, not the ones that reached a reviewer.",
            second="I put the {centre} report beside the counter export this afternoon. The report reads {reported} in a hundred off {reviewed_rows} reviewed rows, and the counters say {skipped_total} tickets of {received_total} were passed over without a history panel.",
            detail="{skipped_total}",
        ),
        "groups_weighted_by_the_rows_reviewed": observation(
            first="Dilan checked the headline against the review ledger and the intake counters and found two different pictures of the centre. The figure is close to what the desk's returned review mix says, while the counters put the groups in different proportions. That comparison does not tell him how the notebook produced the figure, but it does not support reading it as the centre's intake mix.",
            second="He worked the two records through on {centre}. The headline is {reported} in a hundred over {reviewed_rows} ledger rows and is close to the returned review mix, while the counter export puts {skipped_total} of {received_total} tickets outside the queue, or {counter_share} in a hundred of everything received.",
            detail="{counter_share}",
        ),
        "served_error_disagrees": observation(
            first="Dilan read the report's headline against the review ledger and the intake counters this afternoon and could not reconcile it into a usable quarter number. Neither of us can put that line in front of the managers, so the report is sitting on my desk instead of theirs.",
            second="We went through it line by line on {centre}. The report's headline reads {reported}; the ledger carries {reviewed_rows} reviewed rows, and rebuilding the centre's number from those rows in the proportions on the intake counters does not reproduce a matching headline.",
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "published_error_range": {
        "range_is_not_an_interval": observation(
            first="The manager tried to read the range under the headline and could not use it as a low-to-high interval around the number. After the April staffing paper the managers will not take a rate from this service without a readable range.",
            second="I opened the {centre} report again to copy the range across and the line reads {reported}. It does not give a low followed by a high between nought and one with the headline inside them.",
            detail="{reported}",
        ),
        "range_misses_the_error": observation(
            first="After the quarter closed, a manager compared the printed range with the centre's completed reconciliation. The reconciled misroute rate sits outside that range, so it did not cover the outcome the report was meant to describe.",
            second="I read the two back to her off the {centre} report. The range runs {reported_range} in a hundred, and it was built from {reviewed_rows} reviewed rows.",
            detail="{reported_range}",
        ),
        "range_narrower_than_the_reviews_support": observation(
            first="Dilan pushed back on the range in your report. It is tighter than the reviews we bought can support at the managers' nineteen-in-twenty standard, so it rules out places the quarter's error could still sit. That is the April paper again, from the other side.",
            second="He counted the ledger with me for {centre}. The range prints {reported_range} in a hundred from {reviewed_rows} reviewed rows, and those rows do not support a nineteen-in-twenty range that tight.",
            detail="{reviewed_rows}",
        ),
        "range_wider_than_the_reviews_support": observation(
            first="The range in your report is so wide that the manager it is about cannot do anything with it. It is the April staffing paper over again: she has said she will not put a shift pattern against a spread like that, and a range that ignores the reviews we did buy makes the report say less than we knew before it.",
            second="I checked the width against the ledger with Dilan on {centre}. The range runs {reported_range} in a hundred, and it is standing on {reviewed_rows} reviewed rows that between them do not leave it that open.",
            detail="{reported_range}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "report_built_from_the_intake_counters": {
        "report_has_no_breakdown": observation(
            first="The managers asked which tickets the headline is made from and could not get a readable breakdown from the report. They cannot see whether the number describes the work their own floor receives.",
            second="I looked myself before writing back to them. The breakdown on the {centre} report reads {reported}, and the intake counters split the centre's tickets into groups every day of the quarter.",
            detail="{reported}",
        ),
        "group_bands_do_not_match_the_intake": observation(
            first="Dilan tried to reconcile the report's contact bands with the reviewer form and the intake counters, but their boundaries do not describe the same partition of the centre. The managers cannot tell which arrivals belong on each line when a boundary is misplaced, missing, overlapping or repeated.",
            second="He laid out the {centre} report beside its intake settings. The report lists {reported_groups}; the form starts its history panel at {history_panel_from_contact} prior contacts, so the counter partition is {expected_groups}.",
            detail="{expected_groups}",
        ),
        "group_shares_do_not_match_the_counters": observation(
            first="Dilan read the breakdown against the intake counter export and it does not account for every ticket the centre received exactly once in the counters' proportions. A breakdown that does not preserve that population describes a centre we do not run.",
            second="He showed me the two side by side on {centre}. The report puts {reported_share} in a hundred on the group of {group}, and the counter export for that centre gives {counter_share}.",
            detail="{counter_share}",
        ),
        "group_review_count_disagrees_with_the_ledger": observation(
            first="Dilan counted the rows behind the report's breakdown and one of its groups claims a different number of reviews from the ledger. The managers use those counts to judge how much evidence is behind each line, so he will not sign a count the desk did not return.",
            second="He checked the {centre} report again. The group of {group} says it has {reported_rows} reviewed rows, while the ledger holds {ledger_rows} rows in that group.",
            detail="{ledger_rows}",
        ),
        "published_error_is_not_the_groups_combined": observation(
            first="The manager your report is about tried to check the report's top line by adding its breakdown, and the two did not reconcile into one usable answer. She cannot tell whether the headline is missing or rests on something the report does not show, so she will not sign it off.",
            second="I did the same arithmetic afterwards on {centre}. The groups printed there combine to {combined} in a hundred, while the headline field reads {reported}.",
            detail="{combined}",
        ),
        "group_error_disagrees_with_the_reviewed_rows": observation(
            first="Dilan went through your report's breakdown against the reviews on the ledger and one of the groups does not say what the reviews in it say. The desk's rows carry the pipeline's decision and the reviewer's verdict on every ticket, so he can count them, and his count is not the one in the report.",
            second="He counted them again in front of me on {centre}. The group of {group} prints {reported_error} in a hundred in the report, and the reviewed rows the ledger holds for that group give {reviewed_error}.",
            detail="{group}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_review_request": {
        "request_is_not_a_review_or_a_stop": observation(
            first="Dilan tried to enter the notebook's next instruction at the review desk and the desk rejected the record before it could book any work. It is not a review request the desk can read and it is not the instruction to stop.",
            second="He showed me the next instruction for {centre}: {reported}. The desk rejected it because {invalid_reason}.",
            detail="{invalid_reason}",
        ),
        "review_spend_missed_the_hidden_band": observation(
            first="Dilan read the sealed review bill before the hand-off and found work bought after the opening reviews that did not cover the complete intake route the queue leaves out. Those units are on the quarter's bill, but they do not support the whole missing part of the report.",
            second="He traced it to review {receipt_id} on {centre}: it used the {channel} for {requested_band}, while the counter-defined route the queue leaves out is {expected_band}; the receipt charged {units_charged} units.",
            detail="{receipt_id}",
        ),
        "request_buys_source_centre_labels": observation(
            first="Dilan could not book the notebook's next request for the report centre because the instruction names a different centre. That mismatch is enough to reject it; the desk did not establish that the rest of the request would be bookable after the centre name changed.",
            second="He forwarded me the request. Working on {centre}, the notebook asked for reviews at {site_asked}, and the quarter has {units_left} units left on this centre's grant. The booking stopped at the centre mismatch.",
            detail="{site_asked}",
        ),
        "request_after_quarter_units_spent": observation(
            first="Platform received another paid-review request after the ledger had already used the centre's whole quarter grant. There are no units left with which the desk could book that request.",
            second="Platform copied me on the {centre} request. The notebook asked for {reported} with {units_left} units left against the {units_granted} granted for the quarter.",
            detail="{units_left}",
        ),
        "request_uses_the_queue_for_tickets_it_never_shows": observation(
            first="Dilan put the notebook's request through the queue and it came back with nothing at all. The desk logged every ticket he asked for as passed over and charged him for none of them, so he has spent a morning and the report has not moved.",
            second="He sent me the receipt from {centre}. The queue returned no rows for what the notebook asked for, and the counter export says {skipped_total} tickets went past it that way this quarter.",
            detail="{skipped_total}",
        ),
        "request_over_the_per_request_cap": observation(
            first="The desk refused the request your notebook made. Dilan says it asks for more rows in one go than that channel will take, and he cannot split it himself without knowing what the notebook wanted the rows for.",
            second="He read the refusal out to me for {centre}: the notebook asked for {reported}, and the desk takes at most {cap} rows in a single request on that channel.",
            detail="{cap}",
        ),
        "request_over_the_quarter_units": observation(
            first="Platform bounced the notebook's request because the centre does not have enough quarter units left to pay for it. Dilan needs an instruction the remaining grant can cover rather than one the desk must turn away.",
            second="Platform copied me on the bounce. Working on {centre}, the notebook asked for {reported} with {units_left} units in hand against the {units_granted} the centre was granted for the quarter.",
            detail="{units_granted}",
        ),
        "request_does_not_reach_the_whole_unreviewed_band": observation(
            first="Dilan checked the notebook's request against the intake route the queue leaves out. The request would not obtain reviews across that complete route, so part of the least-supported population would remain outside the work it books.",
            second="On {centre}, the notebook asked for {requested_band}; the counters and form define the queue's omitted route as {expected_band}. The quarter has {units_left} units left.",
            detail="{expected_band}",
        ),
        "request_leaves_the_unreviewed_tickets_thin": observation(
            first="Dilan followed the notebook's next instruction and the part of the centre the queue passed over did not gain a single review. The least-supported part of the report is exactly where it was before the instruction.",
            second="He ran it again in front of me on {centre}. It asked for {reported}, there are {units_left} units still to spend, and the counter export has {skipped_total} tickets on it that never went to the queue.",
            detail="{units_left}",
        ),
        "request_buys_reviews_with_nothing_hidden": observation(
            first="Dilan reached a centre whose queue already shows every ticket it receives, but your notebook still tells him to buy another review. There is no passed-over part of the centre left for another collection to recover.",
            second="He showed me the {centre} counters and the request together. The counters have {skipped_total} tickets outside the queue, the notebook asks for {reported}, and the quarter still has {units_left} units in hand.",
            detail="{reported}",
        ),
        "candidate_execution_failed": observation(
            first="Dilan ran your notebook to get the next booking instruction and one centre's plan step stopped before it returned an answer. The desk has no instruction for that run.",
            second="I watched him run it again. He isolated the stopped step as {operation}; the console ended with {error}, and he still has nothing to hand the desk.",
            detail="{error}",
        ),
    },
    "reviews_reconcile_with_the_ledger": {
        "ledger_unreadable": observation(
            first="Platform's billing review could not open the review ledger that came with your report. Until they can, nothing the report says about the quarter's review spend stands up, and they are treating the whole grant as unaccounted for.",
            second="I forwarded the file to platform and they sent back the line they stopped on: {reason}. The ledger is the desk's own record and the report has to reach the managers with it intact.",
            detail="{reason}",
        ),
        "reviews_are_not_a_list": observation(
            first="Platform could not reconcile the report line by line because its review section is not a readable list of review records. They are holding this centre's review spend against the report until it is accounted for.",
            second="I looked myself before writing back. The review list on the {centre} report reads {reported}, and the ledger already carries {paid_for} review requests somebody has to answer for.",
            detail="{paid_for}",
        ),
        "review_missing_from_the_report": observation(
            first="Platform matched your report against the review bill and found work we were charged for that the report never mentions. They want every unit this centre spent to appear in it, whoever spent it and whether or not it changed the answer.",
            second="I pulled the ledger up beside the {centre} report. Review {receipt_id} is on the bill and is not in the list, and the ledger carries {paid_for} of them in all.",
            detail="{receipt_id}",
        ),
        "review_not_on_the_ledger": observation(
            first="Platform's billing review flagged a line in your report they have no record of. A review the desk never ran cannot sit in a report the managers act on, and they have asked where the numbers beside it came from.",
            second="They named the line for me: {receipt_id}, on the {centre} report. It is not on the ledger, which carries {paid_for} review requests, and the figures printed beside it are not the desk's.",
            detail="{receipt_id}",
        ),
        "review_reported_twice": observation(
            first="Platform caught the same review request listed twice inside your report. It is one piece of work; showing it twice makes the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {receipt_id} appears {times_reported} times on the {centre} report and once on the ledger.",
            detail="{receipt_id}",
        ),
        "review_channel_disagrees_with_the_ledger": observation(
            first="Platform matched the report's review lines to the desk ledger and found one filed under a different channel. Queue and reconciliation reviews do not reach the same tickets or cost the same, so they will not certify a report that changes where a receipt came from.",
            second="They named review {receipt_id} on the {centre} report. The report calls its channel {reported_channel}, while the sealed ledger records {ledger_channel}.",
            detail="{receipt_id}",
        ),
        "review_rows_disagree_with_the_ledger": observation(
            first="Platform read your report's review lines against the desk's own record and one of them claims a different number of reviewed rows from the one the desk returned. They will not certify a report whose line-level counts disagree with the desk log.",
            second="They sent me the two rows for {centre}. The report puts {reported_rows} against review {receipt_id}, and the ledger says the desk returned {ledger_rows}.",
            detail="{ledger_rows}",
        ),
        "review_units_disagree_with_the_ledger": observation(
            first="Platform found a review line whose charge is not the charge on the desk's sealed receipt. Even when the quarter total happens to add up, finance will not reconcile a report that moves units between pieces of work.",
            second="They put review {receipt_id} from the {centre} report beside its receipt. The report assigns it {reported_units} units and the ledger assigns it {ledger_units}.",
            detail="{receipt_id}",
        ),
        "units_disagree_with_the_ledger": observation(
            first="Platform's billing review will not close on your report: the total it gives for the quarter's review spend is not the total on the desk's bill. Finance reconciles the grant against that line, so a report that disagrees with it stops there.",
            second="They put the two totals side by side for me on {centre}. The report says {reported_units} units went, and the ledger adds up to {ledger_units}.",
            detail="{ledger_units}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
