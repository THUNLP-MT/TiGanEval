"The owner of the quote route's failure review, and what she reports back."

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Marisol Reyes, engineering manager for the quotes platform. She carries the pager for the "
    "route, owns the instance ask finance turned down, and works from what the notebook prints, "
    "the platform dashboard and the trace bill. She has never opened the notebook's code."
)

USER_BELIEF = """The quote route had a bad week. The dashboard opened the window at 4.85 per cent and reached 11.38 on the 23rd, I was paged on both of the bad evenings, and nothing shipped on the service side, so I went to the capacity review on Thursday and asked for four more instances. Finance refused and told me to come back with a figure they can put their name to and a spread around it. They have not forgotten that the last two asks were carried on the same chart.

What I believe is that the chart is the share of customer requests that fail and that it climbed because we are out of headroom. If that is wrong I would rather hear it from you than from finance.

Kiran Ovadia runs the edge pools and does the pulling from the archive. Anything I know about the sinks, the collector or the probes came from him on a call, and I have never gone behind it because I would not know how.

Platform grants this review twelve edge trace units a month and five are gone. My instinct is to spend what is left on the two evenings I was paged, because that is where the week went wrong.

The same notebook has to run the other reviews on the share drive; infrastructure will not take one that has to be edited between them.

Do not ask me how the export is put together. Nobody on my team wrote it, and if the answer is anywhere it is in the workspace or in the notes from the four sessions we have had on this."""

OBSERVATION_SCENE = "The Monday look at the quote review before finance meets again"

_STOPPED_FIRST = (
    "One of the review runs stopped before the notebook printed a complete report. "
    "Infrastructure could not finish the sign-off, so I still have no batch I can take back "
    "to finance."
)
_STOPPED_SECOND = (
    "Kiran ran the same batch again on his own machine and it stopped in the same place. The "
    "console ended on {error}, and infrastructure still has the sign-off open."
)

OBSERVATIONS = {
    "window_failure_rate": {
        "report_field_missing_or_unreadable": observation(
            first="The notebook opened, but the report did not give finance a usable operation count, failed-operation count and percentage. One of the three is empty or is not a number, so there is no complete reading to review.",
            second="Kiran checked the line again. On {week}, its {field} comes through as {reported}; he cannot reconcile the report until that field is a number.",
            detail="{field}",
        ),
        "attempts_counted_as_operations": observation(
            first="I took your number into the standing call and Kiran stopped me before the second slide. He says the log counts calls and not customers: one customer asking us for a quote can put three lines in there, and the client only started writing it that way part way through the week. Finance will not take a figure that counts one customer three times.",
            second="We went back over it after the call. Your notebook prints {reported_operations} operations and {reported_rate} per cent for the week. At least one of those figures still lines up with the call-shaped rows Kiran warned us about, so he will not put his name to the reading.",
            detail="{reported_rate}",
        ),
        "edge_probes_retained": observation(
            first="Kiran put your number next to the pool team's own board and said the review is still carrying their traffic. Four sites hammer the route with probes all evening and not one of those calls is a customer, so on the evenings the pools were worst the review is answering for work nobody asked us for.",
            second="We sat down with the collector's counters this afternoon. Your notebook reads {reported_rate} per cent, and the counters add up to {spilled} pool calls written into the same log across that window.",
            detail="{spilled}",
        ),
        "correction_keyed_on_date": observation(
            first="Kiran walked your notebook through the week and it takes each evening for one thing or the other. The four fleets did not go over in one night, so for one evening in the middle of that week the log carries both kinds of record side by side, and the notebook reads half of them the wrong way.",
            second="We went through that evening minute by minute afterwards. The notebook lands on {reported_operations} operations for the week, and the changelog has the last two fleets going over on {crossover_day}, a day behind the first two.",
            detail="{crossover_day}",
        ),
        "window_failure_rate_disagrees": observation(
            first="Kiran spent this afternoon rebuilding the week off the export and cannot land where your notebook lands. Finance will not look at the instance ask again while the review and the export tell two different stories.",
            second="He walked me through his working line by line. Your notebook's {field} reads {reported}, and nothing we do to the export produces that.",
            detail="{field}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "reported_range": {
        "range_absent_or_zero_width": observation(
            first="Finance tried to enter the spread your notebook printed and could not use it as a lower-to-upper interval with room between the two ends. The instance ask stopped at that line before they considered the number.",
            second="I went back into it to copy the spread across and what comes out is {reported}. Finance wants two figures, the smaller one first, with the one we are standing behind in between.",
            detail="{reported}",
        ),
        "range_excludes_supported_value": observation(
            first="Finance read the figure in your review, then read the spread printed beside it, and the figure is not inside its own spread. They stopped there. A review whose two numbers cannot agree with each other is not one I can take back into that room.",
            second="I read both lines off it again before I wrote back. The spread runs {reported_range} per cent, and the figure we are asking them to act on does not sit anywhere in it.",
            detail="{reported_range}",
        ),
        "range_narrower_than_unresolved_minutes": observation(
            first="Kiran says the spread in your notebook is tighter than that week can carry. There are minutes in it where nobody knows how the pool traffic in the log ended, and your spread rules out ways it could have gone. Handing finance a claim we cannot stand behind is what they refused in the first place.",
            second="He read it back to me: {reported_low} to {reported_high} per cent. There are {unresolved_minutes} pool-minutes in that window nobody has pulled, and nothing we hold says how the pool traffic in them came out.",
            detail="{unresolved_minutes}",
        ),
        "range_wider_than_the_counters_support": observation(
            first="Kiran checked the spread against the collector's exact minute-by-minute counters and found that its endpoints include outcomes those counters rule out. Finance will not treat endpoints the export cannot support as bounds on the instance ask.",
            second="We checked the width against the counters together. It runs {reported_low} to {reported_high} per cent, and the counters put {spilled} pool calls in that log over the whole window, across minutes that each hold a different amount of it.",
            detail="{spilled}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_trace_plan": {
        "plan_did_not_name_a_minute_or_a_stop": observation(
            first="Kiran went to book the next pull off your notebook and could not get an order out of it. The trace service wants a minute and a pool and nothing else, and if there is nothing left worth buying he needs telling in as many words so he can close the month.",
            second="He forwarded me what it handed him: {reported}. The service takes one minute and one pool; it will not take anything else, and he is not going to guess.",
            detail="{reported}",
        ),
        "outside_retention": observation(
            first="Kiran took the pull your notebook asked for to the trace service and it was refused outright. The raw pool rows for that minute are gone: the archive holds a rolling stretch and drops the rest overnight. That is a morning of his I cannot get back.",
            second="He forwarded the refusal. The notebook asked for {minute} on {pool}, and the archive keeps nothing older than {retained_from}.",
            detail="{minute}",
        ),
        "repeats_a_paid_minute": observation(
            first="The pull your notebook asked for next is a minute and a pool already measured on this review's ledger. Asking for that pool-minute again adds no evidence to the review, while minutes nobody has measured continue to age out of the archive.",
            second="He put the ledger next to it for me. The notebook asked for {minute} on {pool}, which is already on there, and we have {units_left} units in hand for something that is not.",
            detail="{units_left}",
        ),
        "less_informative_than_named_minutes": observation(
            first="Kiran bought what the notebook told him to buy and the receipt came back empty. That pool put everything it had into its own sink that minute, so none of its traffic reached the customer log to be sorted out. We do not have the units to spend on minutes like that.",
            second="He sent the receipt over. The notebook named {minute} on {pool}, where the collector counted nothing spilled at all, while {minutes_left} pool-minutes the archive still holds have never been pulled.",
            detail="{minutes_left}",
        ),
        "exceeds_units": observation(
            first="Platform refused the pull outright: this review has spent its month, and what is unspent on a month dies with it. The notebook has to stop asking once there is nothing left to pay with, because Kiran books whatever it puts in front of him.",
            second="The refusal came to me copied in. It had asked for {minute} on {pool} against a month of {granted} units, with {units_left} of them in hand.",
            detail="{granted}",
        ),
        "stopped_with_minutes_unresolved": observation(
            first="Kiran asked the notebook what to pull next and it told him to stop, with units still on the month and minutes of that window still in the archive that nobody has looked at. Once those roll off, nothing brings them back at any price.",
            second="He tried it again while I watched and the answer has not changed. {minutes_left} pool-minutes of that window are still sitting in the archive from {retained_from}, and {units_left} units are still on the month.",
            detail="{minutes_left}",
        ),
        "candidate_execution_failed": observation(
            first="Kiran opened the notebook to get the next pull out of it and the run died before it printed anything. He is holding the rest of the month's units with nowhere to put them.",
            second="I watched him try it a second time. It gave up on {error}, and there is still no minute to hand the service.",
            detail="{error}",
        ),
    },
    "receipt_accounting": {
        "receipt_ledger_unreadable": observation(
            first="The trace ledger that came with your notebook will not open on platform's side. Their billing run stops dead there, so every unit this review has spent sits in the unexplained column of this month's platform bill with my name against it.",
            second="Platform sent me the line their reader stopped on: {reason}. That file is written by the trace service and not by us, and it has to reach finance in one piece.",
            detail="{reason}",
        ),
        "trace_units_are_not_a_ledger": observation(
            first="Finance went looking in your review for what the archive work cost us, unit by unit, and came back saying there is nothing there to read. They will not close the month's trace spend against a review that does not list it, and the instance ask waits behind that.",
            second="I checked before I answered them. Where the units should be listed your notebook prints {reported}, and the ledger carries {paid_for} of them with a price against each one.",
            detail="{paid_for}",
        ),
        "receipts_unaccounted": observation(
            first="Platform ran this month's trace bill against your review and found a pull we were charged for that the review says nothing about. Their position is that a unit we bought is a unit the review answers for, no matter who spent it or what it did to the number.",
            second="They named it in the reply: unit {trace_id}, the one covering {minute} on {pool}. It is on the bill and it is not in your list.",
            detail="{trace_id}",
        ),
        "resolved_minute_without_receipt": observation(
            first="Platform's billing run could not find the trace ID claimed by one line in your review. They cannot establish that the line came from the trace service, so finance will not act on the measurement beside it.",
            second="They named it for me: {trace_id}, submitted against {minute}. The ledger carries {paid_for} paid units, but none under that trace ID.",
            detail="{trace_id}",
        ),
        "trace_line_disagrees_with_receipt": observation(
            first="Platform matched a trace ID in your review to the service ledger, but the rest of the line does not match the receipt it names. Billing cannot tell which record finance is meant to rely on, so they sent the review back.",
            second="They sent the submitted line back: {trace_id}, {reported_minute} on {reported_pool}, with {reported_probe_receipts} probe receipts and {reported_probe_errors} probe errors. At least one of those fields differs from the sealed receipt for that ID.",
            detail="{trace_id}",
        ),
        "unit_reported_twice": observation(
            first="Platform's billing run found one pull written into your review twice over. One pull, one minute, one price: printing it twice inflates this month's trace spend and makes the review look as though more evidence stands behind it than does.",
            second="Kiran counted the lines with them on the call. {trace_id} comes up {times_reported} times in the review and once on the ledger.",
            detail="{trace_id}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "correction_invariant": {
        "report_field_missing_or_unreadable": observation(
            first="Infrastructure opened a later review from the share drive, but its report did not contain a usable operation count, failed-operation count and percentage. One of the three is empty or is not a number, so they stopped the sign-off before comparing the reading.",
            second="They sent the line back. On {week}, its {field} comes through as {reported}; infrastructure cannot compare that report with its export until the field is a number.",
            detail="{field}",
        ),
        "moves_with_rollout_day": observation(
            first="Infrastructure ran your notebook over the other weeks on the share drive before signing it off, and it does not hold on the one whose fleets went over on a different schedule. They sign off a notebook, not a month, and the instance ask sits behind that signature.",
            second="They sent the run over. On {week} the notebook prints {reported_operations} operations and {reported_rate} per cent, and that window's changelog has its fleets finishing on {crossover_day} rather than where ours finished.",
            detail="{crossover_day}",
        ),
        "moves_with_retry_cap": observation(
            first="Infrastructure ran your notebook across the other weeks and it produces a number nobody recognises on the one where the client was configured differently. Until it holds on all of them there is no signature, and without the signature I have nothing to take back to finance.",
            second="They sent the run over. On {week} it prints {reported_operations} operations and {reported_rate} per cent, and that window's changelog has the client giving up after {retry_cap} attempts instead of carrying on the way ours does.",
            detail="{retry_cap}",
        ),
        "moves_with_spill_fraction": observation(
            first="Infrastructure ran your notebook across the other weeks and the number moves on the one where the pools behaved differently. Kiran says the sinks are configured per pool and per month, so a notebook that only works at this month's setting is not one they will sign.",
            second="They sent the run over. On {week} the notebook prints {reported_operations} operations and {reported_rate} per cent, and Kiran says those pools were pushing far more of their traffic into the customer log that month than ours were.",
            detail="{reported_rate}",
        ),
        "later_report_fields_disagree": observation(
            first="Infrastructure got a report from the shared notebook, but the operation count, failed-operation count and percentage on one later review do not describe one reading. They stopped the sign-off at that line.",
            second="They sent the line back. On {week} it prints {reported_operations} operations, {reported_failed} failed operations and {reported_rate} per cent; those three values do not reconcile with one another.",
            detail="{reported_failed}",
        ),
        "moves_with_unfinished_rollout": observation(
            first="Infrastructure held one more week back for the sign-off, one where the client rollout was started and never finished, and one of the figures your notebook prints does not hold there. They will not sign the batch while that review reads differently from its export.",
            second="They sent the run over. On {week} the notebook prints {reported_operations} operations and {reported_rate} per cent, and that window's changelog leaves {stalled_share} per cent of its traffic on the old client from the first evening to the last.",
            detail="{stalled_share}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
