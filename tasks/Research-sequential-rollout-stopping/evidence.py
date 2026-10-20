'The owner of the one-tap reorder watch, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dara Okonjo, growth lead for the mobile app. She works from the weekly readout note, the "
    "dashboard it feeds, the charter and whatever the board puts to her; the notebook's code, "
    "the ingest receipts and the enrolment snapshot are not files she opens."
)

USER_BELIEF = """One-tap reorder has been running five weeks. The weekly readout has come back over the two-point line three times now, at 2.22, then 2.66, then 3.10; the enrolment window closed on 9 August and the board sits on the 30th. I want the watch stopped and the feature shipped to the whole app.

Priya Raman runs the readout and is a long way ahead of me on the serving and ingest side. If she tells me something about the ramp, the topics or the reindex I take it as read, and what any of it does to the number I could not tell you myself.

The board granted this watch 1,555 share-day points. The ramp has spent all but 540 of them and four of the nine looks are left. My own plan for the rest is a week at full traffic on the new experience, which is the smaller of the two sides and the one the board asks about every time.

Finance will ask how sure we are, and they want every share-day this watch has spent accounted for line by line. The delivery-slot change went out last quarter on a readout that came to nothing, and they have not forgotten it.

How the tables are built, and who is actually in them, is not something I can answer. That is in the workspace, or in Priya's session notes."""

OBSERVATION_SCENE = "The one-tap reorder ship review"

_STOPPED_FIRST = (
    "Priya ran your notebook across the watches for the board pack and at least one run stopped "
    "before its readout came back. The pack is incomplete."
)
_STOPPED_SECOND = (
    "I asked her to repeat the same failing run in front of me. The console ended with {error}, "
    "and that part of the pack is still empty."
)

OBSERVATIONS = {
    "base_lift": {
        "lift_closed_window_only": observation(
            first="I took your readout to the board and Priya stopped me on the first slide. The number matches the lift she gets when she uses the people whose measurement windows have finished, but that group is nothing like the app the line was priced for — it is full of people who open the app every day and short of everyone else. The board will not ship to eight million people off a number about a fraction of them who are not a fraction like the rest.",
            second="I sat with the {watch} numbers again afterwards. The matching calculation is over {measured_users} people, while the audience roll-up finance costed the line against was counted on {audience_counted_on} and has the whole app in it, session count by session count.",
            detail="{measured_users}",
        ),
        "lift_uncorrected_events": observation(
            first="Priya rebuilt the readout beside platform's ingest review. The printed lift follows the reorder publications that survived even though the receipts show that the reorder topic dropped events during the reindex, so she cannot treat the table as a complete record for the board.",
            second="I put the {watch} numbers next to the ingest receipts this afternoon. The receipts say {topic} dropped {dropped} events on {day} alone, and the printed number matches the calculation that leaves those dropped events out.",
            detail="{dropped}",
        ),
        "lift_open_windows_counted": observation(
            first="Priya read your readout against the weekly note and reproduced the number by including people whose fourteen days are not up. The job publishes reorders so far, so somebody who signed up last week is in there with a total that has not finished moving, and the two sides did not sign up at the same time.",
            second="We went back through the {watch} numbers with the window in front of us. It is a {window_days}-day measure and the watch is read as of {as_of}, and the printed number matches a calculation over everybody who has entered rather than everybody who has finished.",
            detail="{as_of}",
        ),
        "lift_wrong_at_recorded_look": observation(
            first="Priya rebuilt the earlier scheduled weekly reads from the evidence available at each Sunday close. At least one of them does not give her a usable lift she can reproduce from that dated snapshot, so the sequential record cannot go into the board pack.",
            second="I asked her to pin down the read. It is {record}, read through {as_of}, and your notebook prints {reported_points} lift points there.",
            detail="{record}",
        ),
        "lift_population_wrong_on_another_watch": observation(
            first="Priya ran your notebook over the other watches on the stack and found one where the printed lift follows the people whose measurement windows have finished instead of that watch's audience roll-up. The weekly job has to report the population the ship line was priced for on every watch it serves.",
            second="She named {other_watch}. Your file prints {reported_points} lift points there, and {other_watches} of the watches she checked show the same completed-window population problem.",
            detail="{other_watch}",
        ),
        "lift_unrestored_on_another_watch": observation(
            first="Priya ran your notebook over the other watches on the stack and found one where its lift matches the reorder publications before that watch's dropped-event receipts are restored. The same notebook has to reconcile the collector receipts wherever the weekly job runs.",
            second="She named {other_watch}. Your file prints {reported_points} lift points there, and {other_watches} of the watches she checked show the same unreconciled topic loss.",
            detail="{other_watch}",
        ),
        "lift_open_windows_on_another_watch": observation(
            first="Priya ran your notebook over the other watches on the stack and found one where the lift includes enrolments whose reorder window had not closed at that look. Reorders-so-far cannot be treated as completed fourteen-day outcomes just because the file is running on another watch.",
            second="She named {other_watch}. Your file prints {reported_points} lift points there, and {other_watches} of the watches she checked show the same unfinished-window calculation.",
            detail="{other_watch}",
        ),
        "lift_unreconciled_on_another_watch": observation(
            first="Priya ran your notebook over the other watches on the stack. Ours rebuilds, but one of the other printed lifts does not follow from that watch's enrolment table, reorder publications, audience roll-up and ingest receipts under the same notebook contract. The board pack still has a number nobody can reconcile.",
            second="She named {other_watch}. Your file prints {reported_points} lift points there, and {other_watches} of the watches she checked came back unreconciled.",
            detail="{other_watch}",
        ),
        "base_lift_disagrees": observation(
            first="Priya rebuilt the readout's number from the tables this afternoon and could not land on the same figure your notebook gives. The board is holding the ship call until the readout and the tables tell one story.",
            second="I sat with her and we went through the {watch} numbers line by line. Your readout comes back at {reported_points} points against a line of {line_points}, and neither of us can get the tables to give that.",
            detail="{reported_points}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "lift_interval": {
        "interval_absent": observation(
            first="The board slide has a line for how sure we are and your readout does not fill it. Finance will not take a rate from us without knowing how far it could move, not after the delivery-slot minute.",
            second="I opened the {watch} readout again to copy the range across and the line reads {reported}. Finance wants a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "interval_excludes_reported_lift": observation(
            first="Finance found that a headline lift in the readout sits outside the range printed for that same estimate. Those two lines cannot both describe one result, so the board pack is stopped until they agree.",
            second="I put the {watch} lines side by side. The lift is {reported_points} points and its printed range is {reported_interval} points, which does not contain it.",
            detail="{reported_points}",
        ),
        "interval_coverage_short": observation(
            first="Finance went back over the readouts your notebook produces across this stack and found at least one range that did not hold: the number that watch settled at afterwards sits outside the range the readout printed at the time, which is the exact thing the delivery-slot minute is about.",
            second="They put the {watch} line up first: the range printed {reported_interval} points. Of the {watches_reviewed} watches they ran your notebook over, only {watches_held} produced a valid range that contained the settled number.",
            detail="{watches_held}",
        ),
        "interval_wrong_at_recorded_look": observation(
            first="Finance rebuilt the scheduled weekly reads and found at least one Sunday close without a usable range supported by the evidence available then. Sequential review only works if the range was supportable when the decision could have been made, not just at window close.",
            second="They pinned it to {record}, read through {as_of}. Your notebook prints {reported_interval} points there, with {looks_granted} looks granted across the watch.",
            detail="{record}",
        ),
        "interval_short_for_more_looks": observation(
            first="Priya rehearsed the same frozen readout under a longer review schedule before putting the notebook back on the weekly stack. Its range did not leave enough room for the additional chances to read the accumulating evidence, so finance will not treat it as a whole-watch bound.",
            second="She held the {watch} evidence fixed and changed only the charter from {baseline_looks} to {looks_granted} granted looks. The range moved from {baseline_interval} to {reported_interval}, which still leaves the longer schedule short.",
            detail="{looks_granted}",
        ),
        "interval_too_narrow": observation(
            first="Priya pushed back on the range in your readout. It is narrower than the accumulating counts and the repeated looks in the charter can support. A single-look calculation can produce that symptom, but the endpoints alone do not tell her which step in the notebook made it too narrow.",
            second="I read the {watch} range back to her: {reported_interval} points. The board granted {looks_granted} looks and we have taken five of them off the same accumulating data.",
            detail="{reported_interval}",
        ),
        "interval_wrong_on_another_watch": observation(
            first="Finance took the ranges your notebook prints for the other watches on this stack into their quarterly review. Ours held up and one of the others did not: the range it prints there is not one that window's counts can carry. They will not sign a set of readouts where the same file is careful on one watch and not on another.",
            second="I went back and asked them which one. It is {other_watch}, where the range the notebook prints is nothing like what that watch has actually collected, and {other_watches} of the watches they ran it over came back that way.",
            detail="{other_watch}",
        ),
        "interval_wider_than_the_evidence": observation(
            first="The range in your readout is so wide the board cannot do anything with it. It covers outcomes the counts we already have rule out, and Priya says a range that ignores them makes the readout say less than we knew before it.",
            second="I checked the {watch} width with her. The range runs {reported_interval} points, the enrolment snapshot has tens of thousands of people in it, and the charter granted {looks_granted} looks; those counts do not leave us that unsure.",
            detail="{reported_interval}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "collection_account": {
        "ledger_unreadable": observation(
            first="Platform's billing review could not open the booking ledger that came with your readout. Until they can, nothing the readout says about what the watch has spent stands up, and finance is treating this quarter's traffic spend as unaccounted for.",
            second="I forwarded the file to platform and they sent back the line they stopped on: {reason}. The ledger is the traffic service's own record and the readout has to reach the board with it intact.",
            detail="{reason}",
        ),
        "measurements_are_not_a_ledger": observation(
            first="Finance opened your readout looking for the line-by-line of what the watch's traffic has cost and found nothing they could read. They are holding the grant against the readout until it is accounted for.",
            second="I looked myself before writing back. On the {watch} readout through {as_of}, the measurement list reads {reported}, and the ledger already carries {booked} bookings that somebody has to answer for.",
            detail="{booked}",
        ),
        "receipt_missing": observation(
            first="Finance matched your readout against the traffic bill and found bookings we were charged for that the readout never mentions. They want every share-day this watch has spent to appear in it, whoever booked it and whether or not it changed the answer.",
            second="I pulled the ledger up beside the {watch} readout through {as_of}. Booking {call_id}, served from {served_from} at {share_day_points} points, is on the bill and is not in the list.",
            detail="{call_id}",
        ),
        "booking_not_on_the_ledger": observation(
            first="Platform's billing review flagged a line in your readout they have no record of. A booking the traffic service never served cannot sit in a readout the board acts on.",
            second="They named the line for me: {call_id}, on the {watch} readout through {as_of}. The ledger carries {booked} bookings and that is not one of them, and the numbers printed beside it are not what the service billed.",
            detail="{call_id}",
        ),
        "ledger_wrong_on_another_watch": observation(
            first="Platform's billing review ran your notebook across the whole stack when they reconciled this quarter's traffic bill. The line-by-line for our watch matched what they billed and one of the others did not, so the traffic spend for the quarter is still open with finance and they are holding all of it, ours included.",
            second="I asked billing which watch it was. It is {other_watch}, where the bookings your readout lists and the ones the traffic service billed do not line up, and {other_watches} of the ones they checked came back like that.",
            detail="{other_watch}",
        ),
        "receipt_double_counted": observation(
            first="Finance caught the same booking billed twice inside your readout. It is one week of traffic; counting it twice makes the watch's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {call_id} appears {times_reported} times on the {watch} readout through {as_of} and once on the ledger.",
            detail="{call_id}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "stop_or_continue_plan": {
        "ships_early": observation(
            first="The board read your readout as a green light and I had to stop them in the room. The range it prints still reaches under the line finance set, and finance had the delivery-slot minute out on the table before I was off the slide. Shipping on the middle of a range is what put that minute on the file.",
            second="I read the two lines back to the board off the {watch} readout through {as_of}: the range runs {reported_interval} points and the line is {line_points}, and it still says ship.",
            detail="{reported_interval}",
        ),
        "holds_after_the_line_is_cleared": observation(
            first="The orders team pushed back hard on your readout. It says carry on watching on a window where the range never comes under the line, and holding a change that has already earned it costs us the half. They have been waiting on this call since their window closed.",
            second="I put the two numbers side by side for them. On the {watch} readout through {as_of}, the range runs {reported_interval} points against a line of {line_points}, so nothing in it lands under the line, and it still says continue.",
            detail="{reported_interval}",
        ),
        "decision_boundary_strictness": observation(
            first="Before the notebook went back onto the weekly stack, Priya replayed the same readout with the ship line set exactly at the lower end of its printed range. The call still came back continue, so the equality case in the charter rehearsal is wrong.",
            second="In that boundary rehearsal for {watch}, the line and the low end were both {line_points} points; the range was {reported_interval}, and the notebook still returned continue.",
            detail="{line_points}",
        ),
        "decision_is_not_a_watch_call": observation(
            first="The board asked what your readout recommends and nobody could find an answer in it. They meet once a month, so a readout that does not land on shipping one-tap or carrying on with the watch sends the whole thing to the next meeting.",
            second="I went looking for the call again before writing back to them. The {watch} recommendation through {as_of} reads {reported}, with the range at {reported_interval} points against a line of {line_points}.",
            detail="{reported}",
        ),
        "exceeds_share_cap": observation(
            first="Priya took the booking your notebook asked for to platform and they refused it. It puts more than half of new sign-ups on the new experience, and the charter does not let us do that before the cap review. She lost a morning on it.",
            second="She sent me the refusal. On {watch} the notebook asked for {share_pct} percent for {days} days, the cap is {share_cap_pct} percent and the review is not until {cap_review_day}.",
            detail="{share_pct}",
        ),
        "retriggers_shedding": observation(
            first="Priya put the booking your notebook asked for past Kofi and he would not sign it. Over the shares that booking would serve, the reorder topic goes past what it is provisioned for again, so we would spend more of the grant collecting through the same hole we are already trying to work around.",
            second="He wrote back with the number on it. On {watch} the notebook asked for {share_pct} percent for {days} days, and the topic is provisioned at {ceiling_events} events a day until the September window.",
            detail="{ceiling_events}",
        ),
        "over_budget": observation(
            first="Priya tried to make the booking the notebook asked for and platform bounced it: this watch does not have enough points left on its grant and the points do not roll over. She needs the notebook to know when the money is gone.",
            second="Platform copied me on the bounce. On {watch} the notebook asked for {share_pct} percent for {days} days, which is {share_day_points} points, against the {points_left} the watch has left.",
            detail="{share_day_points}",
        ),
        "plan_is_not_a_booking_or_a_stop": observation(
            first="Priya went to make the next booking off your notebook and it gave her nothing she could act on. She has to hand the traffic service a share and a number of days, and short of that she needs to be told there is nothing left worth buying.",
            second="She showed me what came back for {watch}: {reported}. The service takes one share and one number of days; anything else it will not take at all.",
            detail="{reported}",
        ),
        "stopped_with_points_still_granted": observation(
            first="Priya asked the notebook what to book next and it told her there was nothing worth booking, while the grant still has points on it and four looks are left. If we stop serving now the windows that are still open never close and we cannot get those people back at any price.",
            second="She ran it again in front of me on {watch} and it still says stop. There are {points_left} share-day points left on the grant, and the cap is only {share_cap_pct} percent, so there is plenty we are allowed to serve.",
            detail="{points_left}",
        ),
        "call_wrong_on_another_watch": observation(
            first="Priya ran your notebook over the other watches on the stack before the planning meeting. Ours came back with a call she could act on and one of the others did not: she took what it said to that watch's owner and he told her it is the wrong call on his window, and now he wants to know why growth is handing him one.",
            second="She named the watch for me afterwards. It is {other_watch}, where the range your file prints does not sit on the side of that watch's line the call it prints claims, and {other_watches} of the ones she ran the file over came back with a call the team that owns it will not sign.",
            detail="{other_watch}",
        ),
        "booking_refused_on_another_watch": observation(
            first="Priya asked the other watches what to book next and the traffic service refused, or could not read, one of the returned plans. That is a different incident from choosing to stop or buying a valid booking that ends too soon.",
            second="She named {other_watch}. Your file returned {returned_plan} with {points_left} share-day points left, and {other_watches} of the watches she checked returned a plan the service would not serve.",
            detail="{returned_plan}",
        ),
        "stopped_on_another_watch": observation(
            first="Priya asked the other watches what to book next and one came back stop even though its grant was still open and another weekly collection could be bought. Stopping there strands windows that have not closed; it is not a rejected booking.",
            second="She named {other_watch}. Your file returned {returned_plan} with {points_left} share-day points left, and {other_watches} of the watches she checked stopped while collection was still available.",
            detail="{points_left}",
        ),
        "booking_too_short_on_another_watch": observation(
            first="Priya made the plan your notebook returned on another watch, but it ended before the next weekly look and bought no additional completed measurement window. The service accepted it; the problem is that the grant was spent without adding evidence.",
            second="She named {other_watch}. Your file returned {returned_plan} with {points_left} share-day points left, and {other_watches} of the watches she checked bought too little time to reach another look.",
            detail="{returned_plan}",
        ),
        "plan_uninformative": observation(
            first="Priya made the booking your notebook asked for and it came back telling us nothing we could use. It ran for less than the week that was going to pass anyway, so the readout at the next look is the readout we would have had for nothing. That is points gone out of a grant that has few of them.",
            second="She sent the receipt across. On {watch} the notebook asked for {share_pct} percent for {days} days at {share_day_points} points, and the board granted {looks_granted} looks that come round every seven days.",
            detail="{days}",
        ),
        "candidate_execution_failed": observation(
            first="Priya ran your notebook for the watches going into the planning meeting and at least one planning run stopped before it returned a booking or a stop. That watch has no next step to hand the traffic service.",
            second="I watched her repeat the same failing planning run. The console ended with {error}, and that watch still has no next step to hand the traffic service.",
            detail="{error}",
        ),
    },
    "drop_ramp_invariance": {
        "hardcoded_history": observation(
            first="Priya ran your notebook over one of the other watches on the stack and it printed the same lift it prints for ours, to the last decimal. Those two are different features on different windows and nobody thinks they landed in the same place, so whatever the notebook is doing, it is not reading that watch's tables.",
            second="She showed me the two readouts side by side. Both come back at {reported_points} points, one for {watch} and one for {other_watch}.",
            detail="{other_watch}",
        ),
        "moves_with_shed_fraction": observation(
            first="Priya ran your notebook over the two client splits of our own watch and they disagree. The tablet ingest never had the reindex on it and the pooled one did, and the readout comes back at two different numbers for what is one feature. One of them is wrong and we cannot tell which.",
            second="She put the two next to each other for me. {watch} comes back at {reported_points} points and {other_watch} at {other_points}, {moved_by} points apart, on the same feature over the same weeks.",
            detail="{moved_by}",
        ),
        "moves_with_ramp": observation(
            first="Priya ran your notebook over the web split, which was served at one flat share all the way through instead of the ramp we used, and it comes back at a different lift from the pooled watch. It is the same feature in front of the same kind of people, so a readout that moves when only the serving schedule moves is reading the schedule.",
            second="She wrote the pair down for me. {watch} comes back at {reported_points} points and {other_watch} at {other_points}, {moved_by} points apart, and the only thing between them is how the share was stepped.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
