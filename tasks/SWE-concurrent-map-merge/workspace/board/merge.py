"""What a card reads when two people have edited it at the same time.

This is the copy of the board a whiteboard client keeps while the session is
open. It takes packets from the sync service and answers the three questions
the service and the app ask of it.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contract import op_id, unpack


class Replica:
    """One client's live copy of the boards in a session."""

    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self._cards: dict[str, dict[str, Any]] = {}
        self._highest: dict[str, int] = {}

    def apply(self, packet: str) -> None:
        """Take in one packet from the sync service."""

        for op in unpack(packet):
            client = str(op["client"])
            self._highest[client] = max(self._highest.get(client, 0), int(op["seq"]))
            card = self._cards.setdefault(str(op["card"]), {})
            field = str(op["field"])
            if str(op["kind"]) == "clear":
                card.pop(field, None)
            else:
                card[field] = op["value"]

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        """What this copy is showing right now."""

        return {card: dict(fields) for card, fields in self._cards.items() if fields}

    def state_vector(self) -> Mapping[str, int]:
        """What this copy tells the sync service it holds."""

        return dict(self._highest)

    def account(self) -> tuple[Mapping[str, Any], ...]:
        """What became of the operations this copy has taken in."""

        return ()


def latest_operation_id(ops: Any) -> str | None:
    """The id of the operation with the highest ``edited_at`` in ``ops``."""

    ordered = sorted(ops, key=lambda op: (int(op["edited_at"]), op_id(op)))
    return op_id(ordered[-1]) if ordered else None
