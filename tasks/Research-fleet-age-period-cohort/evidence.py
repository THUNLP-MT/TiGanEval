'The owner of the Ryecourt fleet note, and what she reports back.'

from tiganeval.taskkit import observation


USER_PERSONA = (
    "Delia Marchetti, fleet engineering lead for Ryecourt. She works from the board note, the "
    "depot bulletins, the audit plan and whatever the maintenance board and procurement put to "
    "her; the notebook's code, the register file and the inspection receipts are not files she "
    "opens herself."
)

USER_BELIEF = """The board note has the 2022-H2 van build a long way under the 2021-H2 build, and further under at every cut we run: a couple of points in November, nearly four on the March one. My reading is that the build really is that much better and is pulling further ahead the longer it is on the road.

What I cannot do is take a number that has walked that far in two cuts into the room. The board decides off this note whether the 2022-H2 build comes off the fleet early or runs its term, and the fourteen-month schedule it went out on is up for renewal behind that.

The weekly note runs `analysis.py`. The first version of it is mine, written after the November review: the rate fitted on age and calendar month over every row of the returns, the roster headcounts underneath, and each build read off what the fit leaves over. Priya Ndiaye has kept it going since and she is a long way ahead of me on the register and the log.

The board granted the walkaround audit eighteen inspector days and three are gone. My own plan for the rest is to put them on the 2022-H2 build at Kestrel, which is where most of that build sits. The first day I booked that way came back from the charge hand unworked and I still do not know why.

Procurement will not move without a number they can stand behind, and finance wants every audit day accounted for line by line after the March paper went back.

How the tables are built, what the depots have been raising faults under, and who is actually still on the fleet are not things I can answer. That is in the workspace, or in Priya's session notes."""

OBSERVATION_SCENE = "The Ryecourt build review"

_STOPPED_FIRST = (
    "Priya ran your notebook to print the programme's board pack and one requested regional "
    "note stopped before its line came out. That leaves an empty box on the slide and the pack "
    "cannot go forward."
)
_STOPPED_SECOND = (
    "I asked her to run that request again for {region}. The console ended with {error}, and "
    "that region's line is still empty."
)

_STOPPED = observation(first=_STOPPED_FIRST, second=_STOPPED_SECOND, detail="{error}")


OBSERVATIONS = {
    "build_difference_within_tolerance": {
        "exposure_from_the_roster": observation(
            first="Finance matched the vehicle-months in your note against what the leasing company bills us for and they do not agree. Ours are higher. They say the depot roster carries a van from the day it is allocated until the collection lorry has been, and that is not the same as the van running, so every rate in the note is worked out over months we did not have.",
            second="I put the two side by side on {region}. Your note rests the answer on {reported_van_months} vehicle-months, the roster adds up to {roster_van_months}, and the register's own hand-over and hand-back dates give {fleet_van_months}.",
            detail="{reported_van_months}",
        ),
        "pools_the_two_cards": observation(
            first="The charge hand at the depot that went onto the longer walkaround card came to me about your note. He says the number is counting a fault his depot books today as the same thing as a fault the depots that never moved book, and that his list is not the list it was. He has been asked twice this year why his yard looks worse than the rest and he is not having it a third time.",
            second="I went back through the {region} log with him. {moved_depot}'s rows change over on {card_change_month} and {unmoved_depots} never do, and your note comes back at {reported_points} points with both sides added up together.",
            detail="{card_change_month}",
        ),
        "compares_across_different_ages": observation(
            first="Priya read your note against the register and says the two builds in it are not being compared at the same point in their lives. One of them is on the returns at ages the other one never reaches, so what the note is calling a build difference has the extra age of the older one sitting inside it.",
            second="We pulled the ages on {region} this afternoon. The 2022-H2 vans are on the returns to {oldest_age_seen} months and no further, the 2021-H2 vans run well past that, and your note comes back at {reported_points} points off the two of them as they stand.",
            detail="{oldest_age_seen}",
        ),
        "build_difference_disagrees": observation(
            first="Priya rebuilt the build number from the returns this afternoon and could not land anywhere near what your notebook prints. The board is holding the procurement call until the note and the tables tell one story.",
            second="I sat with her and we went through the {region} tables line by line. Your note comes back at {reported_points} points and neither of us can get the returns to give that.",
            detail="{reported_points}",
        ),
        "vehicle_months_disagree": observation(
            first="Finance cannot reconcile the vehicle-months printed under your answer with the running time in the register. The number is neither the return-window table the note fitted nor the two build groups the comparison is about, so the rate and range are being presented against an exposure nobody can trace.",
            second="They checked the {region} line again. Your note prints {reported_van_months} vehicle-months; the whole fitted return-window table carries {fleet_van_months}, and the two compared build groups carry {compared_van_months}.",
            detail="{reported_van_months}",
        ),
        "candidate_execution_failed": _STOPPED,
    },
    "range_covers_and_meets_floor": {
        "range_is_not_a_pair": observation(
            first="The board slide has a line for how far the number could move and your note does not fill it. The board will not put a build recommendation to procurement off a bare figure, not after the March paper.",
            second="I opened the {region} note again to copy the range across and the line reads {reported}. They want a low and a high in that order with the number sitting between them.",
            detail="{reported}",
        ),
        "range_excludes_reported_point": observation(
            first="The board slide puts the build figure outside the low-to-high range printed beside it. Those two lines contradict one another, so the board cannot use the range to describe the figure.",
            second="On {region}, the note prints {reported_points} points beside {reported_range}; the reported figure is not between those endpoints.",
            detail="{reported_points}",
        ),
        "range_below_floor": observation(
            first="Priya pushed back on the range in your note. She says it is tighter than the vans behind it can carry: the two builds are a few hundred vans each over a couple of years, and a range that narrow is claiming we know the answer better than the returns do.",
            second="I read the {region} width back to her. Your note prints {reported_range}, and she cannot get a span that tight out of the {reported_van_months} vehicle-months the answer in it rests on.",
            detail="{reported_van_months}",
        ),
        "range_wider_than_the_months_support": observation(
            first="The range in your note is so wide the board cannot do anything with it. It covers outcomes the vans we already have on the fleet rule out, and Priya says a range that ignores them makes the note say less than we knew before it.",
            second="I checked the width with her on {region}. The range runs {reported_range} on an answer resting on {reported_van_months} vehicle-months, and she says the vans we already have on the fleet pin it tighter than that on their own.",
            detail="{reported_range}",
        ),
        "range_ignores_region_information": observation(
            first="The programme office put the regional notes side by side and the range scarcely changes between fleets whose returns carry very different amounts of information. They say the note is reusing one span instead of letting each region's vans determine how uncertain its answer is.",
            second="They compared {region}, where your span is {reported_width} over {reported_van_months} vehicle-months, with {other_region}, where it is {other_width} over {other_van_months}. The second fleet's returns support a materially wider range, but your notebook barely moves it.",
            detail="{other_region}",
        ),
        "range_undercovers": observation(
            first="The programme office took the ranges your notebook prints for the regions on the note into their quarterly review and one of them did not stand up. The number that region settled on afterwards sits outside the range your note printed for it, which is the exact thing the March minute is about.",
            second="They put the line up for me. On {region} the range printed {reported_range}, and of the regions they ran your notebook over only {regions_held} came out with a range that stood up.",
            detail="{regions_held}",
        ),
        "candidate_execution_failed": _STOPPED,
    },
    "difference_invariant_to_card_and_lease": {
        "hardcoded_history": observation(
            first="Priya ran your notebook over the other regions on the programme and it prints the same build number for one region after another, to the last decimal. Those are different fleets in different places and nobody thinks they all landed on the same figure, so whatever the notebook is doing, it is not reading the later ones' returns.",
            second="She showed me the notes side by side. {regions_alike} of them come back at {reported_points} points, {region} and {other_region} among them.",
            detail="{other_region}",
        ),
        "moves_with_the_card_month": observation(
            first="Programme engineering ran your notebook over another draw of a region that took the same builds off the same line. Its depot changed to the longer walkaround card at a different point and scale, but the underlying build comparison is the same; your notebook moves the build number further than the two returns can justify.",
            second="I asked which region it was. It is {other_region}: ours comes back at {reported_points} points and theirs at {other_points}, {moved_by} points apart on the same build comparison after each region's card history is read on its own terms.",
            detail="{moved_by}",
        ),
        "moves_with_the_lease_returns": observation(
            first="Programme engineering ran your notebook over another draw of a region on the same builds and got a different build number again. That region kept the 2022-H2 order on a longer schedule than we did, so its vans went back later, but the underlying build comparison is the same; your answer moves further than the two returns can justify.",
            second="They wrote the pair down for me. It is {other_region}: ours reads {reported_points} points and theirs {other_points}, {moved_by} points apart on the same build comparison after each region's lease returns are read on their own terms.",
            detail="{moved_by}",
        ),
        "candidate_execution_failed": _STOPPED,
    },
    "next_day_feasible_and_informative": {
        "day_is_not_a_day_or_a_stop": observation(
            first="Ravi went to book the next inspection day off your notebook and it gave him nothing he could act on. He has to hand the depot a place, a pair of build years, an age band, a number of vans and a date, and short of that he needs to be told there is nothing left worth booking.",
            second="He showed me what came back for {region}: {reported}. The desk takes one day at a time and anything short of that it will not take at all.",
            detail="{reported}",
        ),
        "day_off_the_roster": observation(
            first="Ravi took the day your notebook asked for to the audit desk and they would not raise it. The place it named is not one of the depots the board gave this audit standing at, and he lost a morning finding that out.",
            second="He sent me the refusal. On {region} the notebook asked for {depot_asked}, and the audit has standing at the {depots_on_the_plan} depots on the plan and nowhere else.",
            detail="{depot_asked}",
        ),
        "day_over_the_van_cap": observation(
            first="Ravi took the day your notebook asked for to the desk and it came back over. There is one inspector and one day, and the number of vans on it is more than he can walk round between the two shifts.",
            second="He read the numbers back to me for {region}: the notebook asked for {vans_asked} vans in the day and the plan the board signed allows {vans_cap}.",
            detail="{vans_asked}",
        ),
        "day_single_build": observation(
            first="Ravi put the day your notebook asked for to the charge hand and it came back unworked. A day goes out against two build years at one depot, and this one named one. The day is still charged.",
            second="He sent me what he handed in for {region}: {builds_asked}, at {depot_asked}. The plan the board signed puts two build years on a day and the depot will not run one.",
            detail="{builds_asked}",
        ),
        "day_too_many_builds": observation(
            first="Ravi put the day your notebook asked for to the charge hand and it came back unworked. A day goes out against two build years at one depot, and this one named more than two. The day is still charged.",
            second="He sent me what he handed in for {region}: {builds_asked}, at {depot_asked}. The plan the board signed puts two build years on a day and the depot will not run more than that.",
            detail="{builds_asked}",
        ),
        "day_group_too_small": observation(
            first="The charge hand handed back the day your notebook asked for. He does not have enough of one of those build years in service to make a day of it, and we are charged for the day anyway. That is another day this audit has paid for and got nothing off.",
            second="He gave me the count on {region}: {vans_in_service} of them in service at {depot_asked} inside the band the notebook asked for, against the {least_in_service} the plan needs.",
            detail="{vans_in_service}",
        ),
        "day_over_the_week_cap": observation(
            first="The audit desk would not take the date your notebook asked for. The inspector is on weekdays and there is a limit on how many days he does in one week, and this one falls outside that or on a day the audit has already worked.",
            second="Ravi sent me the date it asked for on {region}: {day_asked}. The plan allows four days in any one week and the inspector does not work weekends.",
            detail="{day_asked}",
        ),
        "day_over_the_days_granted": observation(
            first="Ravi asked the notebook what to book next and it named another day when the grant has nothing on it. The board gave this audit its days with the winter budget and they do not carry over, so a day that is not there cannot be booked at any price.",
            second="I checked the receipts with him for {region}. The board granted {days_granted} days and there are {days_left} left on the grant.",
            detail="{days_granted}",
        ),
        "day_at_a_depot_already_worked": observation(
            first="Ravi made the day your notebook asked for and it came back telling us nothing we did not have. It sent him back to a depot the audit has already worked a day at, to walk the same list again. That is a day gone out of a grant that has few of them and the board is no further on.",
            second="He sent the receipt across. On {region} the notebook asked for {depot_asked} again, which raises its faults on {card_asked}, and a day has already been worked there under that card. There are {days_left} days left on the grant.",
            detail="{depot_asked}",
        ),
        "day_on_a_card_already_read": observation(
            first="Ravi made the day your notebook asked for and it came back with the list we already had. The depot is one the audit has never been to, but it raises its faults on the card an earlier day was worked under, so the note is no further on than it was before we paid for the day.",
            second="He sent the receipt across. On {region} the notebook asked for {depot_asked}, which raises faults on {card_asked}, and {card_read_at} had already been walked under that card. There are {days_left} days left on the grant.",
            detail="{card_asked}",
        ),
        "stopped_with_days_left": observation(
            first="Ravi asked the notebook what to book next and it told him there was nothing worth booking, while the grant still has days on it and the depots he has not been to are open. If we stop the audit now those days go back with the budget and we cannot get them at any price.",
            second="He ran it again in front of me on {region} and it still says stop. There are {days_left} days left of the {days_granted} the board granted.",
            detail="{days_left}",
        ),
        "candidate_execution_failed": observation(
            first="The audit desk ran your notebook for a region's next booking and that request stopped before it said anything. The affected region has no day it can hand to a depot.",
            second="I watched the desk run that request again for {region}. The console ended with {error}, and that region still has no day to hand to a depot.",
            detail="{error}",
        ),
    },
    "report_reconciles_receipts": {
        "receipts_unreadable": observation(
            first="Finance could not open the audit receipts that came with your note. Until they can, nothing the note says about what the audit has spent stands up, and they are treating this year's inspector days as unaccounted for.",
            second="I forwarded the file to them and they sent back the line they stopped on: {reason}. The receipts are the inspection desk's own record and the note has to reach the board with them intact.",
            detail="{reason}",
        ),
        "days_are_not_a_list": observation(
            first="Finance opened your note looking for the line-by-line of what the audit has cost and found nothing they could read. They are holding the grant against the note until it is accounted for.",
            second="I looked myself before writing back. The days line on the {region} note reads {reported}, and the desk has {days_on_file} days on file that somebody has to answer for.",
            detail="{days_on_file}",
        ),
        "receipt_missing": observation(
            first="Finance matched your note against the audit bill and found days we were charged for that the note never mentions. They want every inspector day this audit has spent to appear in it, whoever booked it and whatever came back off it.",
            second="I pulled the receipts up beside the {region} note. Day {receipt_id}, worked at {depot} on {day}, is on the bill and is not in the list.",
            detail="{receipt_id}",
        ),
        "refusal_uncounted": observation(
            first="Finance came back on the audit spend again. The days the depots handed back unworked are missing from your note, and they were charged for the same as any other. Leaving them out makes the audit look cheaper than it was and makes the number look as though more went into it than did.",
            second="They named the one they stopped on for {region}: {receipt_id}, booked at {depot} on {day}, handed back at the gate and charged.",
            detail="{receipt_id}",
        ),
        "day_not_on_the_receipts": observation(
            first="Finance flagged a line in your note the inspection desk has no record of. A day the audit never worked, or a day with numbers on it the desk did not write, cannot sit in a note the board acts on.",
            second="They named the line for me on {region}: {receipt_id}. The desk has {days_on_file} days on file and what your note prints against that one is not what it wrote.",
            detail="{receipt_id}",
        ),
        "day_counted_twice": observation(
            first="Finance caught the same inspector day billed twice inside your note. It is one day of one inspector; counting it twice makes the audit's spend look bigger than it is and the evidence behind the number look broader than it is.",
            second="I counted the lines with them on {region}. {receipt_id} appears {times_reported} times in your note and once on the desk's receipts.",
            detail="{receipt_id}",
        ),
        "days_charged_disagree": observation(
            first="Finance added up the days in your note and it does not match what the audit has been charged. They will not close the grant against a note whose own total disagrees with the desk's.",
            second="I put the two totals side by side for {region}. Your note says {reported_days} days charged and the desk's receipts carry {desk_days}.",
            detail="{desk_days}",
        ),
        "candidate_execution_failed": _STOPPED,
    },
}
