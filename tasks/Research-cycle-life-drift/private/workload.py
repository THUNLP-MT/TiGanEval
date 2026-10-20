'The campaign under study and the lots the same notebook is used on next.'

from __future__ import annotations

from typing import Any, Mapping

from . import lab, world


CURRENT_LOT = "hx22-september"


FOLLOWING_LOTS: tuple[str, ...] = (
    "kx19-winter",
    "mv30-spring",
    "pq07-summer",
    "rt41-autumn",
)


def context(lot_id: str = CURRENT_LOT) -> dict[str, Any]:
    return world.public_context(lot_id)


def archived_receipts(lot_id: str = CURRENT_LOT) -> list[dict[str, Any]]:
    return lab.archived_receipts(lot_id)


def campaign_of(lot_id: str) -> str:
    return str(world.LOTS[lot_id]["campaign"])


def lot_of_campaign(campaign: str) -> str:
    for lot_id, lot in world.LOTS.items():
        if lot["campaign"] == campaign:
            return lot_id
    raise KeyError(campaign)


def public_records(lot_id: str = CURRENT_LOT) -> dict[str, Mapping[str, Any]]:
    "The operator's session sheets and the scheduler's booking sheet."

    lot = world.LOTS[lot_id]
    records = {
        f"session-{str(session['session_id']).lower()}": world.session_sheet(lot_id, session)
        for session in lot["sessions"]
    }
    records["channel-booking"] = world.booking_sheet(lot_id)
    return records
