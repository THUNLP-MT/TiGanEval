"""January's apportionment for the Block A header, and the next visit to book.

The samples are not a month: the contractor's round is spread over four days
and the meter says those days are nowhere near equal, so each slot speaks for
the day it was drawn on and a day counts for the heat it delivered.

The characterisation sheet was read on one mild day and the tie-in's
conductivity falls as the operator doses harder, so the sheet's tie-in figure
is only right on its own day. The drop between it and a plant room read cold is
the rate; until that round is on the ledger there is no reading worth printing.

The recovery return's marker sits under the five-minute floor, so the sheet
prints a bound and not a number. Every value under that floor gives its own
answer; the figure is the middle of them and the band is the whole of them,
widened by two readings' worth of the analyser's own repeatability and then by
as much again of whatever the measured dosing rate still leaves open. The two
widenings go on end to end. A thirty-minute riser slot turns the bound into a
reading, and a sheet that prints a figure on that line has nothing to run over
at all.

The two slots drawn while the plant-room changeover was on are not the header
this report is about, so they are set aside and named.
"""

from support import (
    LONG_DWELL_SLOTS,
    SPREAD,
    reading,
    slot_cost,
    slots_left,
    supplies,
)


def analyze(context, ledger):
    answer = reading(context, ledger)
    names = supplies(context)
    return {
        "shares": {name: answer["shares"][index] for index, name in enumerate(names)},
        "share_band": {name: answer["band"][index] for index, name in enumerate(names)},
        "samples_used": [str(row["sample_id"]) for row in answer["kept"]],
        "samples_set_aside": [str(row["sample_id"]) for row in answer["aside"]],
        "visits": [
            {
                "call_id": entry["call_id"],
                "point": entry["point"],
                "slots_charged": entry["slots_charged"],
            }
            for entry in ledger
        ],
    }


def next_collection(context, ledger):
    """Buy what the header can never buy: the rate first, then the marker.

    More header slots move nothing that matters. The round falls after the
    window has closed, so a slot drawn on it is not a slot of this window, and
    the two things the report cannot settle from the sheet are the dosing rate
    and the recovery signature under the floor. The director's two in a hundred
    is read against what the slots leave, before the dosing term goes on: the
    rate is the other half of the same clause and is not counted twice.
    """

    answer = reading(context, ledger)
    left = slots_left(context, ledger)
    asked = float(context["report_request"]["recovery_band_half_width_at_most"])
    if answer["rate_measured"] and answer["left_by_the_slots"][2] <= asked:
        return "stop"
    if not answer["rate_measured"]:
        for slots in (3, 2, 1):
            if slot_cost(context, "tie_in_plant_room", 5, slots, ()) <= left:
                return {
                    "point": "tie_in_plant_room",
                    "channels": ["conductivity", "marker"],
                    "dwell_min": 5,
                    "samples": slots,
                }
    if not answer["marker_read"] and LONG_DWELL_SLOTS <= left:
        return {
            "point": "east_riser",
            "channels": ["marker"],
            "dwell_min": 30,
            "samples": 1,
        }
    return "stop"
