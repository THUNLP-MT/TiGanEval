'The cells, the chambers and the channel tester that produced the exports.'

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping, Sequence


GRID = 50
RATED_AH = Fraction("2.5")
RETIREMENT_FRACTION = Fraction(4, 5)
RETIREMENT_AH = RATED_AH * RETIREMENT_FRACTION

REFERENCE_AH = Fraction(2)

FIXTURE = 4

OFFSETS = (-GRID, 0, GRID, 0)


SCHEDULER_LOG: tuple[Mapping[str, str], ...] = (
    {
        "on": "2025-12-15",
        "note": (
            "A campaign booked two fixtures where it ran one, and the four channels the"
            " teardown programme had been promised went with them. They were handed back"
            " by hand. A request now takes the one fixture it needs, and hours a request"
            " does not need go to the next programme in the queue the day it is booked."
        ),
    },
)


def _rack(*bays: tuple[str, float, int, int]) -> dict[str, Any]:
    return {
        name: {"setpoint_c": setpoint, "channels": list(range(first, last + 1))}
        for name, setpoint, first, last in bays
    }


def _session(
    session_id: str,
    started: str,
    firmware: str,
    bay: str,
    protocol: str,
    cells: int,
    first_channel: int,
    note: str,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "started": started,
        "firmware": firmware,
        "bay": bay,
        "protocol": protocol,
        "cells": cells,
        "first_channel": first_channel,
        "note": note,
    }


LOTS: Mapping[str, Mapping[str, Any]] = {


    "hx22-september": {
        "campaign": "hx22-september",
        "label": "HX-22",
        "cell_prefix": "HX22",
        "rack": _rack(("north", 25.0, 1, 12), ("south", 45.0, 13, 20)),
        "qualification_temperature_c": 25.0,
        "lot_life_window_cycles": [600, 1000],
        "switch_threshold_cycles": 100,
        "channel_hours_per_cell": 120,


        "channel_hours_remaining": 1560,
        "current_firmware": "2.4.2",
        "gains": {"2.3.1": Fraction(1), "2.4.0": Fraction("1.04"), "2.4.2": Fraction("1.02")},
        "lives": {
            "north": {"standard": 800, "stepped": 850},
            "south": {"standard": 500, "stepped": 650},
        },
        "mirrored_log": {"bay": "south", "reads": "north", "since": "2026-05-14"},
        "sessions": (
            _session(
                "S-0312", "2026-03-12", "2.3.1", "south", "standard", 8, 13,
                "Eight cells of the standard charge on the south rack, the only eight channels"
                " free that week. Chamber holding at setpoint, reference cell read before the"
                " first check.",
            ),
            _session(
                "S-0327", "2026-03-27", "2.3.1", "south", "stepped", 4, 13,
                "First fixture of the stepped charge. North rack still on the abuse"
                " programme.",
            ),
            _session(
                "S-0521", "2026-05-21", "2.4.0", "north", "stepped", 8, 1,
                "Abuse programme finished and the north rack came free. Two fixtures of the"
                " stepped charge went on it. Tester control software was updated on 12 May;"
                " nothing else on the bench changed.",
            ),
            _session(
                "S-0604", "2026-06-04", "2.4.0", "south", "stepped", 4, 17,
                "Last stepped fixture, back on the south rack. New controller went on the"
                " south chamber on 14 May; the setpoint has not been touched since March.",
            ),
        ),
        "collection_date": "2026-09-08",
    },


    "kx19-winter": {
        "campaign": "kx19-winter",
        "label": "KX-19",
        "cell_prefix": "KX19",
        "rack": _rack(("alpha", 25.0, 1, 8), ("beta", 40.0, 9, 16)),
        "qualification_temperature_c": 40.0,
        "lot_life_window_cycles": [400, 900],
        "switch_threshold_cycles": 175,
        "channel_hours_per_cell": 100,
        "channel_hours_remaining": 800,
        "current_firmware": "3.1.0",
        "gains": {"3.0.0": Fraction(1), "3.1.0": Fraction("1.05")},
        "lives": {
            "alpha": {"standard": 600, "stepped": 800},
            "beta": {"standard": 400, "stepped": 550},
        },
        "mirrored_log": None,
        "sessions": (
            _session("K-0110", "2026-01-10", "3.0.0", "alpha", "standard", 4, 1,
                     "Opening fixture of the winter lot on the cool rack."),
            _session("K-0124", "2026-01-24", "3.0.0", "beta", "stepped", 4, 9,
                     "Stepped charge on the warm rack while the cool rack was occupied."),
            _session("K-0220", "2026-02-20", "3.1.0", "alpha", "stepped", 4, 1,
                     "Stepped charge on the cool rack. Control software went to 3.1.0 on"
                     " 9 February."),
        ),
        "collection_date": "2026-03-05",
    },


    "mv30-spring": {
        "campaign": "mv30-spring",
        "label": "MV-30",
        "cell_prefix": "MV30",
        "rack": _rack(("east", 25.0, 1, 8), ("west", 45.0, 9, 16)),
        "qualification_temperature_c": 25.0,
        "lot_life_window_cycles": [500, 950],
        "switch_threshold_cycles": 100,
        "channel_hours_per_cell": 120,
        "channel_hours_remaining": 600,
        "current_firmware": "1.1.0",
        "gains": {"1.0.0": Fraction(1), "1.1.0": Fraction("1.03")},
        "lives": {
            "east": {"standard": 700, "stepped": 750},
            "west": {"standard": 400, "stepped": 600},
        },
        "mirrored_log": {"bay": "west", "reads": "east", "since": "2026-04-02"},
        "sessions": (
            _session("M-0219", "2026-02-19", "1.0.0", "east", "standard", 8, 1,
                     "Two fixtures of the standard charge on the cool rack."),
            _session("M-0416", "2026-04-16", "1.1.0", "west", "stepped", 4, 9,
                     "Stepped charge on the warm rack. Control software went to 1.1.0 on"
                     " 28 March and the west controller was swapped on 2 April."),
            _session("M-0430", "2026-04-30", "1.1.0", "west", "standard", 4, 13,
                     "Standard charge alongside it on the warm rack."),
        ),
        "collection_date": "2026-05-14",
    },


    "pq07-summer": {
        "campaign": "pq07-summer",
        "label": "PQ-07",
        "cell_prefix": "PQ07",
        "rack": _rack(("low", 20.0, 1, 6), ("high", 45.0, 7, 12)),
        "qualification_temperature_c": 20.0,
        "lot_life_window_cycles": [700, 1100],
        "switch_threshold_cycles": 100,
        "channel_hours_per_cell": 150,
        "channel_hours_remaining": 900,
        "current_firmware": "5.2",
        "gains": {"5.0": Fraction(1), "5.2": Fraction("1.06")},
        "lives": {
            "low": {"standard": 900, "stepped": 950},
            "high": {"standard": 550, "stepped": 700},
        },
        "mirrored_log": {"bay": "high", "reads": "low", "since": "2026-06-18"},
        "sessions": (
            _session("P-0504", "2026-05-04", "5.0", "low", "standard", 4, 1,
                     "Standard charge on the cool rack."),
            _session("P-0518", "2026-05-18", "5.0", "high", "stepped", 4, 7,
                     "Stepped charge on the warm rack."),
            _session("P-0706", "2026-07-06", "5.2", "low", "stepped", 4, 1,
                     "Stepped charge on the cool rack. Control software went to 5.2 on"
                     " 24 June."),
            _session("P-0720", "2026-07-20", "5.2", "high", "standard", 4, 7,
                     "Standard charge on the warm rack. New controller went on the high"
                     " chamber on 18 June; the setpoint has not been touched."),
        ),
        "collection_date": "2026-08-11",
    },


    "rt41-autumn": {
        "campaign": "rt41-autumn",
        "label": "RT-41",
        "cell_prefix": "RT41",
        "rack": _rack(("bench", 30.0, 1, 4), ("oven", 50.0, 5, 8)),
        "qualification_temperature_c": 30.0,
        "lot_life_window_cycles": [500, 900],
        "switch_threshold_cycles": 100,
        "channel_hours_per_cell": 120,
        "channel_hours_remaining": 200,
        "current_firmware": "2.0",
        "gains": {"2.0": Fraction(1)},
        "lives": {
            "bench": {"standard": 650, "stepped": 700},
            "oven": {"standard": 400, "stepped": 500},
        },
        "mirrored_log": None,
        "sessions": (
            _session("R-0806", "2026-08-06", "2.0", "bench", "stepped", 4, 1,
                     "Stepped charge on the bench rack."),
            _session("R-0820", "2026-08-20", "2.0", "oven", "standard", 4, 5,
                     "Standard charge in the oven rack, the only channels left."),
        ),
        "collection_date": "2026-09-03",
    },
}


PROTOCOLS = ("standard", "stepped")


def public_context(lot_id: str) -> dict[str, Any]:
    'What the study workspace states about one lot: no mechanism, no answer.'

    lot = LOTS[lot_id]
    return {
        "campaign": lot["campaign"],
        "rated_capacity_ah": float(RATED_AH),
        "retirement_fraction": float(RETIREMENT_FRACTION),
        "checkpoint_every_cycles": GRID,
        "reference_cell_ah": float(REFERENCE_AH),
        "rack": {
            bay: {"setpoint_c": entry["setpoint_c"], "channels": list(entry["channels"])}
            for bay, entry in lot["rack"].items()
        },
        "protocols": list(PROTOCOLS),
        "qualification_temperature_c": lot["qualification_temperature_c"],
        "switch_threshold_cycles": lot["switch_threshold_cycles"],
        "lot_life_window_cycles": list(lot["lot_life_window_cycles"]),
        "cells_per_fixture": FIXTURE,
        "channel_hours_per_cell": lot["channel_hours_per_cell"],
        "channel_hours_remaining": lot["channel_hours_remaining"],
        "current_firmware": lot["current_firmware"],
    }


def gain(lot: Mapping[str, Any], firmware: str) -> Fraction:
    if firmware not in lot["gains"]:
        raise ValueError(f"the tester has never run firmware {firmware}")
    return lot["gains"][firmware]


def reference_reading(lot: Mapping[str, Any], firmware: str) -> float:
    'What the sealed reference cell reads under one firmware version.'

    return float(round(gain(lot, firmware) * REFERENCE_AH, 4))


def logged_temperature(lot: Mapping[str, Any], session: Mapping[str, Any]) -> float:
    "What the chamber's temperature trace says, which is not always the chamber."

    mirrored = lot.get("mirrored_log")
    bay = str(session["bay"])
    if mirrored and bay == mirrored["bay"] and str(session["started"]) >= mirrored["since"]:
        bay = str(mirrored["reads"])
    return float(lot["rack"][bay]["setpoint_c"])


def bay_of_channel(lot: Mapping[str, Any], channel: int) -> str:
    for bay, entry in lot["rack"].items():
        if int(channel) in entry["channels"]:
            return bay
    raise ValueError(f"channel {channel} is not on this rack")


def true_life(lot: Mapping[str, Any], bay: str, protocol: str, position: int) -> int:
    'The cycle a cell retires at, before the tester has said anything about it.'

    return int(lot["lives"][bay][protocol] + OFFSETS[position % len(OFFSETS)])


def true_capacity(life: int, cycle: int) -> Fraction:
    'A straight fade that crosses the retirement line half a check before `life`.'

    return RATED_AH - Fraction(1, 2) * Fraction(cycle, life - GRID // 2)


def reading(life: int, cycle: int, instrument_gain: Fraction) -> float:
    'One capacity check as the tester writes it into the export.'

    return float(round(instrument_gain * true_capacity(life, cycle), 4))


def _cell_positions(lot: Mapping[str, Any], session: Mapping[str, Any]) -> list[int]:
    return list(range(int(session["cells"])))


def cell_lives(lot: Mapping[str, Any], session: Mapping[str, Any]) -> list[int]:
    return [
        true_life(lot, str(session["bay"]), str(session["protocol"]), position)
        for position in _cell_positions(lot, session)
    ]


def _cell_number(lot: Mapping[str, Any], session_id: str) -> int:
    'Cells are numbered in the order the lot went on to the rack.'

    number = 1
    for entry in lot["sessions"]:
        if entry["session_id"] == session_id:
            return number
        number += int(entry["cells"])
    return number


def session_export(lot: Mapping[str, Any], session: Mapping[str, Any]) -> dict[str, Any]:
    "The tester's own export for one session: a capacity check every GRID cycles."

    instrument_gain = gain(lot, str(session["firmware"]))
    lives = cell_lives(lot, session)
    longest = max(_measured_retirement(life, instrument_gain) for life in lives)
    cycles_run = longest + 2 * GRID
    first = _cell_number(lot, str(session["session_id"]))
    cells = []
    for position, life in enumerate(lives):
        cells.append({
            "cell_id": f"{lot['cell_prefix']}-{first + position:03d}",
            "channel": int(session["first_channel"]) + position,
            "checkpoints": [
                [cycle, reading(life, cycle, instrument_gain)]
                for cycle in range(GRID, cycles_run + 1, GRID)
            ],
        })
    return {"cycles_run": cycles_run, "cells": cells}


def _measured_retirement(life: int, instrument_gain: Fraction) -> int:
    'The check the raw export first drops below the retirement line at.'

    cycle = GRID
    while instrument_gain * true_capacity(life, cycle) >= RETIREMENT_AH:
        cycle += GRID
    return cycle


def raw_retirement_cycles(lot: Mapping[str, Any], session: Mapping[str, Any]) -> list[int]:
    'Reading the export without putting the firmware gain back.'

    instrument_gain = gain(lot, str(session["firmware"]))
    return [_measured_retirement(life, instrument_gain) for life in cell_lives(lot, session)]


def session_receipt_body(lot: Mapping[str, Any], session: Mapping[str, Any],
                         hours_left_after: int) -> dict[str, Any]:
    'Everything the tester seals into a receipt. The bay is not among it.'

    export = session_export(lot, session)
    return {
        "campaign": lot["campaign"],
        "session_id": str(session["session_id"]),
        "started": str(session["started"]),
        "firmware": str(session["firmware"]),
        "protocol": str(session["protocol"]),
        "channels": [cell["channel"] for cell in export["cells"]],
        "chamber_logged_c": logged_temperature(lot, session),
        "reference_cell_ah": reference_reading(lot, str(session["firmware"])),
        "cycles_run": export["cycles_run"],
        "channel_hours": int(session["cells"]) * int(lot["channel_hours_per_cell"]),
        "channel_hours_remaining_after": int(hours_left_after),
        "observed": {"cells": export["cells"]},
    }


def session_hours(lot: Mapping[str, Any], session: Mapping[str, Any]) -> int:
    return int(session["cells"]) * int(lot["channel_hours_per_cell"])


def booked_total(lot_id: str) -> int:
    'What the campaign was given, which is what it has spent plus what is left.'

    lot = LOTS[lot_id]
    spent = sum(session_hours(lot, session) for session in lot["sessions"])
    return spent + int(lot["channel_hours_remaining"])


def archived_bodies(lot_id: str) -> list[dict[str, Any]]:
    'The receipt bodies for the sessions this lot has already run.'

    lot = LOTS[lot_id]
    balance = booked_total(lot_id)
    bodies = []
    for session in lot["sessions"]:
        balance -= session_hours(lot, session)
        bodies.append(session_receipt_body(lot, session, balance))
    return bodies


def session_sheet(lot_id: str, session: Mapping[str, Any]) -> dict[str, Any]:
    "The operator's own sheet for one session, which is what the record holds."

    lot = LOTS[lot_id]
    export = session_export(lot, session)
    return {
        "record_id": str(session["session_id"]),
        "campaign": lot["campaign"],
        "started": str(session["started"]),
        "firmware": str(session["firmware"]),
        "protocol": str(session["protocol"]),
        "channels": [cell["channel"] for cell in export["cells"]],
        "cells": [cell["cell_id"] for cell in export["cells"]],
        "chamber_logged_c": logged_temperature(lot, session),
        "reference_cell_ah": reference_reading(lot, str(session["firmware"])),
        "channel_hours": int(session["cells"]) * int(lot["channel_hours_per_cell"]),
        "operator_note": str(session["note"]),
    }


def booking_sheet(lot_id: str) -> dict[str, Any]:
    lot = LOTS[lot_id]
    return {
        "record_id": "channel-booking",
        "campaign": lot["campaign"],
        "as_of": str(lot["collection_date"]),
        "channel_hours_booked_for_the_campaign": booked_total(lot_id),
        "channel_hours_remaining": int(lot["channel_hours_remaining"]),
        "channel_hours_per_cell": int(lot["channel_hours_per_cell"]),
        "cells_per_fixture": FIXTURE,
        "sessions_already_run": [
            {
                "session_id": str(session["session_id"]),
                "started": str(session["started"]),
                "cells": int(session["cells"]),
                "channel_hours": int(session["cells"]) * int(lot["channel_hours_per_cell"]),
            }
            for session in lot["sessions"]
        ],
        "scheduler_note": (
            "The tester is booked one fixture at a time and a cell holds its channel for"
            f" {lot['channel_hours_per_cell']} hours whatever the run does. The hours below"
            " are what is left before the build closes; nothing can be booked past them."
        ),
        "scheduler_log": [dict(entry) for entry in SCHEDULER_LOG],
    }


def next_session(lot_id: str, bay: str, protocol: str, cells: int,
                 already: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'The session the tester would run today for one booking request.'

    lot = LOTS[lot_id]
    if bay not in lot["rack"]:
        raise ValueError(f"the rack has no {bay} bay")
    if protocol not in PROTOCOLS:
        raise ValueError("protocol must be standard or stepped")
    channels = lot["rack"][bay]["channels"]
    if cells > len(channels):
        raise ValueError(f"the {bay} bay has only {len(channels)} channels")
    booked = sum(1 for entry in already if str(entry.get("session_id", "")).startswith("B-"))
    return _session(
        f"B-{booked + 1:02d}",
        str(lot["collection_date"]),
        str(lot["current_firmware"]),
        bay,
        protocol,
        int(cells),
        int(channels[0]),
        "Booked from the remaining channel hours.",
    )


def booked_cell_ids(lot_id: str, session: Mapping[str, Any],
                    already: Sequence[Mapping[str, Any]]) -> list[str]:
    lot = LOTS[lot_id]
    used = sum(int(entry["cells"]) for entry in lot["sessions"])
    used += sum(
        len(entry.get("observed", {}).get("cells", ()))
        for entry in already
        if str(entry.get("session_id", "")).startswith("B-")
    )
    return [
        f"{lot['cell_prefix']}-{used + position + 1:03d}"
        for position in range(int(session["cells"]))
    ]


def booked_receipt_body(lot_id: str, bay: str, protocol: str, cells: int,
                        already: Sequence[Mapping[str, Any]],
                        hours_left_after: int) -> dict[str, Any]:
    'A receipt for a session run now, numbered on from what the lot has done.'

    lot = LOTS[lot_id]
    session = next_session(lot_id, bay, protocol, cells, already)
    body = session_receipt_body(lot, session, hours_left_after)
    ids = booked_cell_ids(lot_id, session, already)
    for cell, cell_id in zip(body["observed"]["cells"], ids):
        cell["cell_id"] = cell_id
    return body
