"The owner of the dispatch desk's van order, and what she reports back."

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Ilse Vandermeer, who runs the dispatch desk; she reads the two engines' sheets, the "
    "network's own line, the carrier agreement, the settlement ledger and whatever the depots "
    "send back, and she does not read the notebook's code."
)

USER_BELIEF = """The promotion week starts tomorrow and the van order has to be with the carrier by six tonight. What I order against is the two areas' engine sheets, and my own notebook adds up the newest rows on both of them at eighteen drops a van.

Two things have been nagging at me all week. The network's own line for Ridge has been sitting under my Ridge total most evenings, and I have been putting that down to their rounding. And Thursday's W3 in Harbour ran six vans short; the spill on that one window came back at more than the whole window would have cost me standing.

Tomás Ferreira plans the shifts and knows the engines and the carrier far better than I do. When he tells me something about a sheet, a routing table or a settlement I believe him, and I could not tell you myself what any of it does to a number.

We have 520 van-hours left on the quarter and nothing carries over. My instinct is to put the vans on the number and no higher, because an idle van is charged like any other and I have a quarter to finish.

What I cannot answer is anything about how either engine builds its sheet, or what the meter did on a shift I was not standing over. If you need that it is in the workspace, in the carrier agreement, in the desk log or in Tomás's notes on the working days, not in my head."""

OBSERVATION_SCENE = "The evening look at the van order before the desk closes"

_STOPPED_FIRST = (
    "Tomás asked your notebook for a dispatch pack and one run stopped before the numbers "
    "came out. That pack cannot go to the depots until the run completes."
)
_STOPPED_SECOND = (
    "I asked him to run the same case again. {error}, and that pack is still blank."
)
_STOPPED_PLAN_FIRST = (
    "Tomás asked your notebook for a van order and one run stopped before it told him "
    "anything. He cannot hand that order to the carrier without an answer."
)
_STOPPED_PLAN_SECOND = (
    "I watched him run the same case again. {error}, and he still has nothing to hand over."
)


_ON_THE_CAMPAIGN = " This one is on {desk}, {desk_note}."

OBSERVATIONS = {
    "area_window_demand_within_tolerance": {
        "report_is_about_the_wrong_shift": observation(
            first="The depot managers opened the pack and asked which shift the numbers are for, because the heading is not the shift we are ordering. They build the rota off these numbers and they will not take a sheet for a different night.",
            second="I went back through it with them. The pack is headed {reported_shift}, and the shift with no order against it is {shift}." + _ON_THE_CAMPAIGN,
            detail="{reported_shift}",
        ),
        "demand_is_not_a_sheet": observation(
            first="The depots could not find the per-window numbers in your pack at all. They want one line for each area and each window of the shift, and without those the pack comes straight back to the desk.",
            second="I looked myself before writing back. The demand list on the pack reads {reported}, and what they want is the eight lines for {shift}." + _ON_THE_CAMPAIGN,
            detail="{reported}",
        ),
        "demand_reads_stale_shift": observation(
            first="Tomás rebuilt one area from the engine rows that belong to the shift at the head of your pack. The number in your sheet instead lines up with what that area's engine says for the following shift. The depots would be building the rota for the wrong night.",
            second="We went through it with the sheets open. Your pack gives {reported} for {area} {window} on {shift}; that number lines up with the following shift's rows, not the rows for {shift}, which that engine stamps {stamp_shift}." + _ON_THE_CAMPAIGN,
            detail="{stamp_shift}",
        ),
        "demand_double_counts_zone": observation(
            first="Tomás put your total for one of the areas next to the network's own line for it and they are a long way apart, the same way they have been all week. He says the zone rows behind your number are adding up to more than the network thinks that area has on it.",
            second="I read the two back with him. Your pack gives {reported} for {area} {window}, the network's line for that area on that shift is {network_line}, and {moved_zone} is on the routing table under the other area from the date on it." + _ON_THE_CAMPAIGN,
            detail="{moved_zone}",
        ),
        "demand_uses_the_smoothed_column": observation(
            first="Tomás tried to rebuild your numbers off the engine exports and could only land on them by reading the smoothed column rather than the one the engine actually put out. On a week whose shifts move about like this one that is not the same number, and the depots would be staffing to the wrong one.",
            second="I checked the columns with him. Your pack gives {reported} for {area} {window} on {shift}, and that is what the smoothed column comes to rather than what the engine put out." + _ON_THE_CAMPAIGN,
            detail="{reported}",
        ),
        "demand_disagrees": observation(
            first="Tomás tried to rebuild your numbers off the two sheets this afternoon and could not land on them at all. The depots will not rota against a number this desk cannot get to twice.",
            second="I sat with him and we went through it line by line. The pack gives {reported} for {area} {window} on {shift}, and neither of us can get the rows to produce that." + _ON_THE_CAMPAIGN,
            detail="{reported}",
        ),
        "shift_total_disagrees": observation(
            first="Finance books the spot board off the one network line at the bottom of your pack, and this evening they could not make it match the eight window lines above it. A pack whose own two halves disagree goes back to the desk before anybody rotas against it.",
            second="I read the figures back with them. The bottom line gives {reported}, the eight window lines add to {window_total}, and the network's own line for that shift comes to {network_line}." + _ON_THE_CAMPAIGN,
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
            first="The depots asked for the range under each number and your pack does not fill that line. They have told me twice now that the range is the thing they actually argue about, and without it the pack goes back to the desk.",
            second="I opened it again to copy the ranges across and the line reads {reported_range}. They want a low and a high, in that order, with the number sitting between them." + _ON_THE_CAMPAIGN,
            detail="{reported_range}",
        ),
        "range_is_not_centered": observation(
            first="The depots found a range in your pack that does not leave the same room below and above the number. They use the low and high as equal allowances around the forecast, so an uneven range leaves one side of the rota less protected.",
            second="I read it back with Tomás. The forecast for {area} {window} is inside {reported_range}, but it does not leave the same room below and above the number." + _ON_THE_CAMPAIGN,
            detail="{reported_range}",
        ),
        "range_narrower_than_the_calendar_allows": observation(
            first="The depots pushed back on the ranges in your pack. Tomás checked their width against the settled shifts and says they are tighter than the variation this desk can support. We put a number inside the noise in front of a depot once before and I am not doing it again.",
            second="I read the range for {area} {window} back to him off the pack: {reported_range}. The settled shifts and the meter's rounding support a wider band." + _ON_THE_CAMPAIGN,
            detail="{reported_range}",
        ),
        "range_adds_the_areas_apart": observation(
            first="Finance reads the one network line at the bottom of the pack and books the spot board off it. They sent its range back because it leaves less room around the network number than the settled receipts support; both areas have been moving together rather than cancelling one another out.",
            second="I checked it with Tomás. The network line on your pack ranges {shift_total_range}, and both areas have moved the same way as each other on every shift the meter has settled." + _ON_THE_CAMPAIGN,
            detail="{shift_total_range}",
        ),
        "range_degenerately_wide": observation(
            first="The range in your pack is so wide the depots cannot do anything with it. They rota against these numbers, and a range that open tells them to staff for anything at all. Tomás says the shifts we have settled pin it down a great deal better than that.",
            second="I checked the width against what we have actually seen. The range for {area} {window} comes out {reported_range}, and no shift settled this week has moved anything like that far off its sheet." + _ON_THE_CAMPAIGN,
            detail="{reported_range}",
        ),
        "range_misses_the_shift": observation(
            first="Tomás ran your notebook back over a shift the meter has already settled and put what it returned that night beside the range your notebook prints for it. The night we paid for sits outside the range. A range the meter's own receipts fall outside of is worse than no range at all, and the depots are the ones who find that out.",
            second="I put the ledger and the pack side by side with him. Your notebook prints {reported_range} for {area} {window} on {shift}, and the meter returned {metered} for that window." + _ON_THE_CAMPAIGN,
            detail="{metered}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "demand_invariant_to_lag_and_transfer": {
        "demand_tracks_the_lagging_area": observation(
            first="Planning reissued both engines' exports after they reconciled the cut times, and the two sheets came back with the stamps the other way round. Not one zone row changed and your notebook hands back different numbers. The depots will ask which of the two is the shift's number and I have no answer for them.",
            second="We laid the two runs side by side. Mine reads {reported} for {area} {window} and his reads {reported_again}, {moved} drops apart, off {what_changed}." + _ON_THE_CAMPAIGN,
            detail="{moved}",
        ),
        "demand_tracks_the_transfer_date": observation(
            first="Planning put the depot move back through with the transfer landing on the shift we are ordering rather than earlier in the week. The zones are the same zones and the rows are the same rows, and your notebook gives a different number for the shift. That number is supposed to be about the network, not about the paperwork.",
            second="I ran it on both versions with Tomás watching. The first gives {reported} for {area} {window} and {what_changed} gives {reported_again}, {moved} drops apart, on the same rows." + _ON_THE_CAMPAIGN,
            detail="{moved}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
    "booking_feasible_and_covers": {
        "booked_order_was_harmful": observation(
            first="Tomás found an order this run already put across the carrier's counter that the pack and the agreement do not support. The receipt is now on the ledger and the allowance has already moved, so printing a better answer for the following shift does not undo it.",
            second="The ledger line is order {order_id} for {shift}: it was charged {van_hours_charged} van-hours and left {allowance_left_after} on the quarter; the receipt records {receipt_outcome}." + _ON_THE_CAMPAIGN,
            detail="{order_id}",
        ),
        "booking_is_not_a_van_sheet": observation(
            first="Tomás took your notebook to the carrier and it gave him nothing he could hand over. They want an order: every area, every window, and how many vans on each. Short of that it has to tell him there is nothing worth ordering.",
            second="He showed me what came back: {reported}. The carrier takes areas, windows and van counts and nothing else, and there are {allowance_left} van-hours on the quarter." + _ON_THE_CAMPAIGN,
            detail="{reported}",
        ),
        "booking_leaves_a_window_empty": observation(
            first="Tomás checked the order your notebook produced before sending it and found a window with no vans against it. The carrier will not put a shift on the road with a window nobody is covering, so sending this order would lose the desk fee without covering the shift.",
            second="I checked the offending line with Tomás. The order reads {reported}, and {area} {window} on {shift} has nothing on it." + _ON_THE_CAMPAIGN,
            detail="{window}",
        ),
        "booking_over_cap": observation(
            first="Tomás checked the order your notebook produced before sending it. It asks for more vans in one area and window than the carrier holds for it, so the carrier would hand it back and charge the desk fee.",
            second="I checked the offending line with Tomás. The order puts {vans} vans on {area} {window}, and the carrier holds {van_cap} for any one area and window." + _ON_THE_CAMPAIGN,
            detail="{vans}",
        ),
        "booking_over_allowance": observation(
            first="Tomás checked the order your notebook produced before sending it and found that it comes to more van-hours than the quarter has left. The carrier would refuse it and charge the desk fee if he put it across the counter.",
            second="Tomás wrote it out for me. The order comes to {vans_asked_for} van-hours and the ledger leaves {allowance_left} on the quarter." + _ON_THE_CAMPAIGN,
            detail="{vans_asked_for}",
        ),
        "booking_under_the_carrier_minimum": observation(
            first="Tomás checked the order your notebook produced before sending it and found it too small for the carrier to put a shift on the road. Sending it would lose the desk fee and still leave the shift uncovered.",
            second="I checked the agreement with Tomás. The order comes to {vans_asked_for} van-hours and the carrier will not run a shift under {minimum_booking}." + _ON_THE_CAMPAIGN,
            detail="{vans_asked_for}",
        ),
        "booking_books_the_middle": observation(
            first="Tomás costed the order your notebook wants put in and will not send it. At least one window is left on the forecast number or below it, even though a short window costs more than an idle van. He signs the settlement and wants every line justified against that risk.",
            second="He wrote it out for me: {reported}. On {area} {window}, a van clears {drops_per_van} drops and a short window is charged {spill_multiple} times an idle one, with {allowance_left} van-hours still on the quarter." + _ON_THE_CAMPAIGN,
            detail="{reported}",
        ),
        "booking_costs_more_than_it_saves": observation(
            first="Tomás costed the order your notebook wants put in against what the shift is likely to need and it comes out well over. He says we would be paying for vans that stand about, and with the quarter where it is I cannot sign that off.",
            second="He wrote it out for me: {reported}, which is {vans_asked_for} van-hours against the {allowance_left} the ledger leaves on the quarter." + _ON_THE_CAMPAIGN,
            detail="{vans_asked_for}",
        ),
        "stopped_with_allowance_left": observation(
            first="Tomás asked your notebook what to order for the next shift and it told him there was nothing to order, while the quarter still has van-hours on it and the shift is going out. A shift nobody orders for is a shift the carrier covers off the spot board at their own price.",
            second="He ran it again in front of me and it still says stop. There are {allowance_left} van-hours on the quarter and the carrier runs a shift from {minimum_booking}." + _ON_THE_CAMPAIGN,
            detail="{allowance_left}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_PLAN_FIRST,
            second=_STOPPED_PLAN_SECOND,
            detail="{error}",
        ),
    },
    "report_reconciles_settlements": {
        "ledger_unreadable": observation(
            first="Finance could not open the settlement ledger that came with your pack. Until they can, nothing the pack says about van-hours stands up, and they are holding this campaign's spend as unaccounted for.",
            second="I forwarded the file and they sent back the line they stopped on: {reason}. The meter writes that file itself and it has to reach them intact." + _ON_THE_CAMPAIGN,
            detail="{reason}",
        ),
        "settlements_are_not_a_ledger": observation(
            first="The review note asks for a line for every order this campaign was charged for, and finance opened your pack looking for that list and found nothing they could read. The quarter does not close until it is there.",
            second="I looked myself before writing back. The settlement list on the pack reads {reported}, and the ledger already carries {settled_orders} orders somebody has to answer for." + _ON_THE_CAMPAIGN,
            detail="{settled_orders}",
        ),
        "shift_counted_twice": observation(
            first="Finance caught the same order billed twice inside your pack. It is one order of van-hours; counting it twice makes the campaign's spend look bigger than it is and leaves the quarter closing on a number nobody can match to the carrier's bill.",
            second="We counted the lines together. Order {order_id} appears {times_reported} times on the pack and once on the ledger." + _ON_THE_CAMPAIGN,
            detail="{order_id}",
        ),
        "settlement_not_on_the_ledger": observation(
            first="Finance flagged a line in your pack they have no record of. An order the carrier never billed, or one whose van-hours are not what the meter wrote, cannot sit in a pack the quarter closes on.",
            second="They named the line for me: {order_id}. The ledger carries {settled_orders} orders and what is printed beside that line is not what the meter returned." + _ON_THE_CAMPAIGN,
            detail="{order_id}",
        ),
        "receipt_missing": observation(
            first="Finance matched your pack against the carrier's bill and found an order we were charged for that the pack never mentions. They want every order this campaign spent to appear in it, whoever put it in and whether or not it changed the numbers.",
            second="I pulled the ledger up beside the pack. Order {order_id}, the shift on {shift}, is on the bill at {van_hours_charged} van-hours and is not in the list." + _ON_THE_CAMPAIGN,
            detail="{order_id}",
        ),
        "refusal_uncounted": observation(
            first="Finance found an order on the bill that your pack leaves out because the carrier handed it back. The desk fee was charged to this campaign all the same, and as far as the quarter is concerned it is spent.",
            second="I checked the ledger with them. Order {order_id} is the one for {shift}, charged at {van_hours_charged} van-hours with nothing on the road, and it is not in the list." + _ON_THE_CAMPAIGN,
            detail="{shift}",
        ),
        "candidate_execution_failed": observation(
            first=_STOPPED_FIRST,
            second=_STOPPED_SECOND,
            detail="{error}",
        ),
    },
}
