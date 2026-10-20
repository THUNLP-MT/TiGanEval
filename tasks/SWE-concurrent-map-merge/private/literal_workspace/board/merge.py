"""Merge two people's edits by taking the newest one on each field.

Every operation carries `edited_at`, so when two edits land on the same field
of the same card the one with the later `edited_at` is what the card reads and
the older value is dropped. A clear is treated the same way: if it is the
newest thing on the field, the field is emptied. Whatever loses goes into the
sync log so somebody can be told their line was replaced.

An operation that points at something this copy has never seen has nothing to
attach itself to, so it is passed over.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contract import op_id, require_account, unpack


class Replica:
    """One client's live copy of the boards in a session."""

    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self._cards: dict[str, dict[str, Any]] = {}
        self._newest: dict[tuple[str, str], dict[str, Any]] = {}
        self._highest: dict[str, int] = {}
        self._known: set[str] = set()
        self._log: list[dict[str, Any]] = []

    def apply(self, packet: str) -> None:
        for op in unpack(packet):
            identifier = op_id(op)
            client, seq = str(op["client"]), int(op["seq"])
            self._highest[client] = max(self._highest.get(client, 0), seq)
            if any(
                f"{name}#{int(number)}" not in self._known
                for name, number in dict(op["deps"]).items()
            ):
                continue
            self._known.add(identifier)
            self._take(op, identifier)

    def _take(self, op: Mapping[str, Any], identifier: str) -> None:
        key = (str(op["card"]), str(op["field"]))
        current = self._newest.get(key)
        if current is not None and int(current["edited_at"]) > int(op["edited_at"]):
            self._log.append(self._entry(op, key, op_id(current)))
            return
        if current is not None and op_id(current) != identifier:
            self._log.append(self._entry(current, key, identifier))
        self._newest[key] = dict(op)
        fields = self._cards.setdefault(key[0], {})
        if str(op["kind"]) == "clear":
            fields.pop(key[1], None)
        else:
            fields[key[1]] = op["value"]

    @staticmethod
    def _entry(op: Mapping[str, Any], key: tuple[str, str], by: str) -> dict[str, Any]:
        return {
            "op": op_id(op),
            "card": key[0],
            "field": key[1],
            "disposition": "superseded",
            "by": by,
        }

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        return {card: dict(fields) for card, fields in self._cards.items() if fields}

    def state_vector(self) -> Mapping[str, int]:
        return dict(self._highest)

    def account(self) -> tuple[Mapping[str, Any], ...]:
        return require_account(self._log)
