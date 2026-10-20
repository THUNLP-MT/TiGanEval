"""What a card reads when two people have edited it at the same time.

A copy holds every operation it has received. An operation affects the board
only once everything its author had already seen is integrated here too;
until then it waits, but the copy still tells the sync service it holds it.

What a field reads is decided from the operations themselves. A clear takes
out the edits its author had already integrated and nothing else. Of the edits
still in play, the ones nobody wrote on top of are the ones that could be
shown, and the same one of those is picked on every copy.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contract import (
    contiguous_vector,
    dominates,
    happens_before,
    op_id,
    require_account,
    unpack,
)


class Replica:
    """One client's live copy of the boards in a session."""

    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self._integrated: dict[str, dict[str, Any]] = {}
        self._waiting: dict[str, dict[str, Any]] = {}
        self._vector: dict[str, int] = {}

    # -- taking packets in -------------------------------------------------

    def apply(self, packet: str) -> None:
        for op in unpack(packet):
            identifier = op_id(op)
            if identifier in self._integrated or identifier in self._waiting:
                continue
            self._waiting[identifier] = op
        self._integrate_what_is_ready()

    def _ready(self, op: Mapping[str, Any]) -> bool:
        return all(
            dominates(self._vector, f"{client}#{int(seq)}")
            for client, seq in dict(op["deps"]).items()
        )

    def _integrate_what_is_ready(self) -> None:
        moved = True
        while moved:
            moved = False
            for identifier in sorted(self._waiting):
                if not self._ready(self._waiting[identifier]):
                    continue
                self._integrated[identifier] = self._waiting.pop(identifier)
                self._vector = contiguous_vector(self._integrated)
                moved = True

    # -- deciding what each field reads ------------------------------------

    def _resolution(self) -> dict[tuple[str, str], dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
        for op in self._integrated.values():
            key = (str(op["card"]), str(op["field"]))
            entry = grouped.setdefault(key, {"edits": [], "clears": []})
            entry["edits" if str(op["kind"]) == "edit" else "clears"].append(op)

        resolution: dict[tuple[str, str], dict[str, Any]] = {}
        for key, entry in grouped.items():
            clears = sorted(entry["clears"], key=op_id)
            removed: dict[str, str] = {}
            for edit in entry["edits"]:
                for clear in clears:
                    if dominates(clear["deps"], op_id(edit)):
                        removed[op_id(edit)] = op_id(clear)
                        break
            live = [edit for edit in entry["edits"] if op_id(edit) not in removed]
            on_top = [
                edit
                for edit in live
                if not any(
                    happens_before(edit, other)
                    for other in live
                    if op_id(other) != op_id(edit)
                )
            ]
            winner = sorted(on_top, key=lambda op: (-int(op["edited_at"]), op_id(op)))
            resolution[key] = {
                "removed": removed,
                "live": live,
                "winner": winner[0] if winner else None,
            }
        return resolution

    # -- what the app and the service ask for ------------------------------

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        board: dict[str, dict[str, Any]] = {}
        for (card, field), entry in self._resolution().items():
            if entry["winner"] is not None:
                board.setdefault(card, {})[field] = entry["winner"]["value"]
        return board

    def state_vector(self) -> Mapping[str, int]:
        return contiguous_vector(set(self._integrated).union(self._waiting))

    def account(self) -> tuple[Mapping[str, Any], ...]:
        resolution = self._resolution()
        entries: list[dict[str, Any]] = []
        for identifier in sorted(self._integrated):
            op = self._integrated[identifier]
            key = (str(op["card"]), str(op["field"]))
            entry = resolution[key]
            winner = entry["winner"]
            if str(op["kind"]) == "clear":
                disposition, by = "applied", None
            elif identifier in entry["removed"]:
                disposition, by = "removed", entry["removed"][identifier]
            elif winner is not None and op_id(winner) == identifier:
                disposition, by = "readable", None
            else:
                disposition = "superseded"
                by = op_id(winner) if winner is not None else None
            entries.append(
                {
                    "op": identifier,
                    "card": key[0],
                    "field": key[1],
                    "disposition": disposition,
                    "by": by,
                }
            )
        for identifier in sorted(self._waiting):
            op = self._waiting[identifier]
            entries.append(
                {
                    "op": identifier,
                    "card": str(op["card"]),
                    "field": str(op["field"]),
                    "disposition": "pending",
                    "by": None,
                }
            )
        return require_account(entries)
