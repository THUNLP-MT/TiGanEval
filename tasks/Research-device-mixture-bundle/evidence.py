'The owner of the bundle decision, and what he reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Dario Feng, release manager on the handheld train, who takes the bundle decision to the "
    "board and answers to the depot managers' representative for it; he reads what the notebook "
    "prints, the annotation desk's bill and the questions the board puts to him, and he does not "
    "read the notebook's code."
)

USER_BELIEF = """The board deferred the bundle decision and I have to bring it back. Three bundles, one goes on every handheld on the train, and the quarter closes with the next sitting.

My own comparison ran all three across the capture export and came back mallow at 92.2 per cent against rowan 89.6 and thistle 88.3. Nearly ten thousand captures, mallow two and a half points clear, so the arithmetic is not what worries me. What I could not answer in the room was which depots the export was off. I do not know which units the rows came from and I have never opened the register beyond checking how many handhelds we own.

Suri Bhatt in release engineering keeps raising the reflectance columns on the rows off units platform has already moved to 4.2. When she tells me something about the export or the exporter I take it as read; I could not tell you myself what any of it does to a number.

The grant is 1,200 credits and 920 are left. My instinct is to put them on counter captures, because that is where two thirds of the export comes from. Two requests this quarter came back with nothing and cost twenty credits each, which I am still annoyed about.

The representative will not take an average over the fleet. These are points of error, so lower is better, and sixteen points or below at every depot meets the train's promise. Beyond that, anything about how the tables underneath were built is in the workspace or in Suri's records, not in my head."""

OBSERVATION_SCENE = "The handheld board's bundle decision"

_STOPPED_FIRST = (
    "Suri opened your notebook to print the pack for the board and the run stopped before "
    "anything came out. I have an empty slide where the bundle goes."
)
_STOPPED_SECOND = (
    "I had her run it again in front of me. The console ended with {error}, and the slide is "
    "still empty."
)

OBSERVATIONS = {
    "fleet_number_within_tolerance": {
        "pooled_over_the_log": observation(
            first="The depot managers' representative stopped me on the first slide again. He says the figure is still one number over the whole export and two thirds of the export is counter work, so it is a number about the counter and not about the depots that raise the tickets. He will not put a bundle on the train off it.",
            second="I went back over it with Suri afterwards. The pack for {depot} prints {reported} points off {log_rows} rows, and {counter_share} in a hundred of those rows are counter rows while the register is barely two fifths counter units.",
            detail="{counter_share}",
        ),
        "rows_scored_as_captured": observation(
            first="Suri will not sign the pack. She says the number is read off rows the exporter wrote straight out of the sensor, and those are not the numbers a unit hands its bundle in the bay. The board is being asked to promise every depot a figure off readings no handheld ever saw.",
            second="She showed me on the {depot} pack. It prints {reported} points, and {as_captured_rows} of the {log_rows} rows in that export are stamped as they left the sensor rather than corrected.",
            detail="{as_captured_rows}",
        ),
        "profiles_averaged_not_worst": observation(
            first="The representative added the bays up himself and came out where your pack does, which is his complaint. He says an average over the bays is a figure for a depot that does not exist, and the depot that raises the tickets is the one the bundle does worst at.",
            second="I read it back to him off the {depot} pack. It prints {reported} points, and the bay it does worst at is {deciding_profile}, which is nowhere near that.",
            detail="{deciding_profile}",
        ),
        "bundle_is_not_the_registers": observation(
            first="The representative rebuilt the comparison from the depot register and could not reproduce the bundle your pack names. He checked each bundle at that bundle's own worst bay; the recommendation changes when it is read against the units the depots actually run.",
            second="I checked the {depot} pack afterwards. It names {reported_bundle} and puts {reported} error points against its own worst bay, {deciding_profile}; the register-backed comparison does not put that bundle first when each other bundle is read at its own worst bay, not one shared bay.",
            detail="{reported_bundle}",
        ),
        "fleet_number_disagrees": observation(
            first="Suri rebuilt the figure off the export this afternoon and could not land anywhere near the one your notebook prints. Neither of us can tell the board where it comes from, so the pack is on my desk instead of theirs.",
            second="We went through it row by row on {depot}. The pack comes back at {reported} points off {log_rows} rows, and nothing we do with those rows gives that.",
            detail="{reported}",
        ),
        "bundle_numbers_missing": observation(
            first="The representative wants all three bundles priced on the same slide and in the same terms as the one we are shipping, and he cannot get that off your pack. He is being asked to put one bundle on every handheld his depots run, and he will not agree to it without seeing what the other two cost beside it.",
            second="I went back through the {depot} pack with Suri. It puts {reported} points against {reported_bundle}, and what it prints for the three bundles is {bundle_list}.",
            detail="{bundle_list}",
        ),
        "bundle_not_lowest_printed": observation(
            first="The representative read the recommendation and the three worst-bay figures beneath it. One of the other bundles has a lower figure than the bundle the pack says to ship, so the recommendation and its own comparison table do not agree.",
            second="I went back through the {depot} pack with Suri. It names {reported_bundle} at {reported} points, while the three figures beneath it read {bundle_list}. Lower is better, and the named bundle is not the lowest figure in that table.",
            detail="{bundle_list}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "range_covers_and_meets_floor": {
        "range_is_not_an_interval": observation(
            first="There is a line under the number on the board slide for the range and I cannot copy your notebook's onto it. The representative asked for the number with the range under it in the meeting and said so twice.",
            second="I opened the {depot} pack again to copy the range across and the line reads {reported}. He wants a low end and a high end, in that order, that I can read straight onto the slide.",
            detail="{reported}",
        ),
        "number_outside_its_range": observation(
            first="The representative read the figure off the slide, then the band printed under it, and the figure is not inside the band. He stopped there: a pack that cannot keep its own number inside its own range is not one he will take to his depot managers, and the item is deferred again.",
            second="I put the {depot} slide back up with Suri. The figure on it is {reported} points and the band under it runs {reported_range} points, which does not reach it.",
            detail="{reported_range}",
        ),
        "range_below_floor": observation(
            first="Suri pushed back on the range in your pack. She says it is tighter than the rows behind it can carry: the bay that decides the number is one of the thin ones on the export, and a range that narrow rules out places the number could sit.",
            second="She counted the rows with me for {depot}. The range prints {reported_range} points, which is {width} points wide, and the bay it stands on is {deciding_profile} with {deciding_rows} rows behind it.",
            detail="{deciding_rows}",
        ),
        "range_wider_than_the_rows_leave": observation(
            first="The range in your pack is so wide the representative cannot do anything with it. He staffs shift patterns against that spread, and the rows behind the deciding bay do not leave the result as open as the printed range says.",
            second="I checked the width against the rows with Suri on {depot}. The range runs {reported_range} points, which is {width} points wide, and {deciding_rows} rows in {deciding_profile} do not leave it that open.",
            detail="{reported_range}",
        ),
        "range_rows_disagree": observation(
            first="Suri cannot reconcile the row count printed under the figure with the range beside it. The pack says the number stands on one amount of work, but the spread is the one a different amount of work would leave, so the representative cannot tell which claim he is being asked to rely on.",
            second="I put the {depot} line in front of her again. It reports {reported_rows} rows behind a range of {reported_range}, {width} points wide, while the campaign holds {held_rows} rows in that bay.",
            detail="{reported_rows}",
        ),
        "range_undercovers": observation(
            first="The depots pulled their own week of captures and where the bundle actually landed sits outside the range your pack printed. The representative staffed to the top of it and still ran short, and he wants to know why it never reached where his quarter came out.",
            second="I read the two back to him off the {depot} pack. The range runs {reported_range} points under a figure of {reported}, and it was built off {deciding_rows} rows in {deciding_profile}.",
            detail="{reported_range}",
        ),
        "deciding_bay_not_named": observation(
            first="The representative asked which bay the figure on the slide is for and how much of the quarter's work stands behind it, and the pack does not give a bay and row count that match that figure. He will not put a spread in front of his managers without knowing whose week it describes.",
            second="I checked the {depot} pack with Suri. Under the number it gives the bay as {reported_profile} with {reported_rows} rows behind it, and this campaign holds {held_rows} rows in that bay.",
            detail="{reported_profile}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "number_invariant_to_capture_mix_and_rollout": {
        "moves_with_capture_reach": observation(
            first="Ops put the capture app on another batch of handhelds and re-ran the export, and your notebook came back with a different figure off the same fleet. Nothing about the depots changed that week. The representative says a number that moves when we hand out more apps is a number about the apps.",
            second="I ran the two exports side by side. On {reissue} the pack reads {second_reading} points against {first_reading} on the one you were given, a gap of {gap} points, and it is the same handhelds in the same bays.",
            detail="{gap}",
        ),
        "moves_with_rollout_share": observation(
            first="Platform replanned the firmware rollout and pushed most of it back, and the export written after that gives your notebook a different figure for the same quarter. Nobody swapped a bundle and nobody moved a handheld between bays. The board will not promise a depot a number that depends on our own release schedule.",
            second="I put the two exports up together. On {reissue} the pack reads {second_reading} points against {first_reading} on the one you were given, a gap of {gap} points.",
            detail="{gap}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "next_capture_feasible_and_informative": {
        "capture_is_not_a_request_or_a_stop": observation(
            first="I went to the annotation desk with what your notebook told me to buy and they could not take it. They need a bay, a firmware, a condition and a number of rows, and short of that they need to be told there is nothing left worth buying.",
            second="Here is what came back for {depot}: {reported}. The desk takes those four things and nothing else at all.",
            detail="{reported}",
        ),
        "capture_below_minimum": observation(
            first="The annotation desk handed the request back because it is smaller than a batch they will open. They still bill a handed-back request, so I cannot send them a plan that is known to fail their minimum before anyone labels a row.",
            second="They read the {depot} request back to me as {reported}. The desk takes at least {minimum} rows in one request.",
            detail="{minimum}",
        ),
        "capture_over_cap": observation(
            first="The desk turned your notebook's request away. They say it asks for more rows in one go than they will take in a single request, and they will not split it themselves without knowing what the rows were for.",
            second="They read the refusal out to me for {depot}: the notebook asked for {reported}, and a single request takes at most {cap} rows.",
            detail="{cap}",
        ),
        "capture_over_credits": observation(
            first="The desk bounced one proposed request because its price was above the balance at that point. That does not by itself say whether the grant is empty or a smaller valid request can still be bought; I need the notebook to make that distinction before it sends another request or says the quarter is over.",
            second="They copied me on the bounce. Working on {depot}, the notebook asked for {reported} with {credits_left} credits in hand against the {credits_granted} the campaign was granted. Those figures are about that request against the balance; the notebook still has to determine whether another valid request fits before it says stop.",
            detail="{credits_granted}",
        ),
        "capture_names_an_empty_cell": observation(
            first="Your notebook sent the desk after captures that do not exist. They logged no units in that cell, came back with nothing, and still billed us for the trip. That is the second time this quarter I have paid for an empty request and I have to answer for it.",
            second="Here is the receipt from {depot}: the notebook asked for {cell}, the desk found no units in it, and there are {credits_left} credits left.",
            detail="{cell}",
        ),
        "capture_repeats_counter": observation(
            first="I asked the notebook what to buy next and it sends me where I was going anyway. Buying more of what the export is already full of leaves the two bundles at the top exactly where they are, and the quarter ends this month.",
            second="I ran it again in front of Suri on {depot}. It asked for {reported}, and the bay that decides between the top two is {deciding_profile}.",
            detail="{deciding_profile}",
        ),
        "stopped_with_credits_left": observation(
            first="The notebook told the desk there was nothing left to buy while the campaign still has credits in hand and the two bundles at the top are close enough that the board could still go to the other one. Once the quarter closes those credits are gone.",
            second="Suri checked it with me on {depot}. It came back with nothing to buy, there are {credits_left} credits still to spend of the {credits_granted} granted, and the bay that decides between the top two is {deciding_profile}.",
            detail="{credits_left}",
        ),
        "candidate_execution_failed": observation(
            first="I opened your notebook to work out what to buy next and the run stopped before it said anything. I am sitting on the quarter's credits with nothing to hand the desk.",
            second="I ran it again with Suri watching. The console ended with {error}, and I still have nothing to give them.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="Platform's billing review could not open the receipt file that came with your pack. Until they can, nothing the pack says about the quarter's annotation spend stands up, and they are treating the whole grant as unaccounted for.",
            second="I forwarded the file to platform and they sent back the line they stopped on: {reason}. That file is the desk's own record and the pack has to reach the board with it intact.",
            detail="{reason}",
        ),
        "requests_are_not_a_list": observation(
            first="Platform opened your pack looking for the line by line of what the quarter's annotation cost and found nothing they could read. They are holding this campaign's spend against the pack until it is accounted for.",
            second="I looked myself before writing back. The request list on the {depot} pack reads {reported}, and the desk has already billed us for {charged_for} requests somebody has to answer for.",
            detail="{charged_for}",
        ),
        "receipt_missing": observation(
            first="Platform matched your pack against the desk's bill and found work we were charged for that the pack never mentions. They want every credit this campaign spent to appear in it, whoever spent it and whether or not it changed the answer.",
            second="I pulled the receipt file up beside the {depot} pack. Request {receipt_id} is on the bill and is not in the list, and the file carries {charged_for} of them in all.",
            detail="{receipt_id}",
        ),
        "refusal_uncounted": observation(
            first="Platform says the pack leaves out the requests the desk handed back. Those cost us twenty credits each and they are the ones I get asked about, so a pack that quietly drops them makes the quarter look tidier than it was.",
            second="They named it for me off the {depot} bill: request {receipt_id} came back with nothing, was billed anyway, and is not in the list. The file carries {charged_for} requests in all.",
            detail="{receipt_id}",
        ),
        "request_not_on_the_receipts": observation(
            first="Platform's billing review flagged a line in your pack they have no record of. A request the desk never ran cannot sit in a pack the board acts on, and they have asked where the figures beside it came from.",
            second="They named the line for me: {receipt_id}, on the {depot} pack. It is not on the receipt file, which carries {charged_for} requests, and the numbers printed beside it are not the desk's.",
            detail="{receipt_id}",
        ),
        "request_counted_twice": observation(
            first="Platform caught the same request billed twice inside your pack. It is one piece of work; counting it twice makes the quarter's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them. {receipt_id} appears {times} times on the {depot} pack and once on the receipt file.",
            detail="{receipt_id}",
        ),
        "rows_above_the_receipt": observation(
            first="Platform read your pack's request lines against the desk's own record and one of them claims a different number of rows from the one the desk returned. They will not certify a pack that says more work came back than the desk logged.",
            second="They sent me the two lines for {depot}. The pack puts {reported_rows} against request {receipt_id}, and the desk says it returned {desk_rows}.",
            detail="{desk_rows}",
        ),
        "line_disagrees_with_the_receipt": observation(
            first="Platform's billing review read your pack's request lines against the desk's own bill and one of them does not say what the desk says it was. They reconcile the grant line by line, so the quarter's annotation spend stays open until the two records read the same.",
            second="They sent me the two lines for {depot}. The pack's line for {receipt_id} reads {reported_line}, and the desk's own record of that request reads {desk_line}.",
            detail="{receipt_id}",
        ),
        "credits_disagree_with_the_receipts": observation(
            first="Platform's billing review will not close on your pack: the total it gives for the quarter's annotation spend is not the total on the desk's bill. Finance reconciles the grant against that line, so a pack that disagrees with it stops there.",
            second="They put the two totals side by side for me on {depot}. The pack says {reported_credits} credits went, and the receipt file adds up to {desk_credits}.",
            detail="{desk_credits}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
