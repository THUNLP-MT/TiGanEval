"""The sync contract every whiteboard client and the sync service are built against.

This module ships inside the desktop app, the tablet app, and the sync service,
so it is read-only in this workspace. It defines the wire form of an operation,
the causality primitives the clients agree on, the canonical form of a board,
and the shape of the merge account a client hands back.

Everything here is deterministic. There are no clocks read from the host, no
threads and no network: concurrency is modelled as clients that author
operations while offline and hand them to each other in whatever order the
sync service manages to deliver them.

An operation is one change to one field of one card::

    {"kind": "edit",  "client": "meera", "seq": 3,
     "card": "Vendor call", "field": "Assignee", "value": "Ravi Menon",
     "edited_at": 4910, "deps": {"juno": 1, "tomas": 2}}

    {"kind": "clear", "client": "tomas", "seq": 2,
     "card": "Vendor call", "field": "Estimate",
     "edited_at": 5200, "deps": {"juno": 2}}

``seq`` counts that client's own operations from 1 and never skips. ``deps`` is
the version vector of everything its author had already integrated at the
moment they made the change, including their own earlier operations, so it
records what the person was looking at. ``edited_at`` is the second reading of
the clock on the machine that authored it, taken from that machine.

The sync service holds no board of its own. On reconnect it asks a client for
its state vector and forwards every operation its peer holds that the vector
does not cover, in the order the peer received them.

What the service calls on a client, and what this module validates:

``Replica(client_id)``
    A client's live copy of the boards in the session.
``Replica.apply(packet)``
    Integrate one incoming packet. ``unpack`` turns it into operations.
``Replica.snapshot()``
    ``{card: {field: value}}`` -- what the person is looking at right now.
``Replica.state_vector()``
    ``{client: seq}``, what this copy tells the service it holds.
``Replica.account()``
    What became of the operations this copy has taken in.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence


OP_KINDS: tuple[str, ...] = ("edit", "clear")

OP_FIELDS: tuple[str, ...] = ("kind", "client", "seq", "card", "field", "edited_at", "deps")

DISPOSITIONS: tuple[str, ...] = ("readable", "superseded", "removed", "applied", "pending")
"""What the merge account may say became of one operation.

``readable``
    This edit is the one the card shows for its field.
``superseded``
    This edit was taken in and another edit on the same field is shown
    instead; ``by`` names that edit.
``removed``
    A clear took this edit out of play; ``by`` names that clear.
``applied``
    A clear that has been integrated. Clears use this and ``pending`` only.
``pending``
    Taken in but not yet integrated, because something it depends on has not
    arrived. ``by`` is null.
"""

ACCOUNT_FIELDS: tuple[str, ...] = ("op", "card", "field", "disposition", "by")


class ContractError(ValueError):
    """Raised when an operation, a packet, a board, or an account is malformed."""


# --------------------------------------------------------------------------
# Operations


def op_id(op: Mapping[str, Any]) -> str:
    """The identity of one operation, ``"<client>#<seq>"``."""

    return f"{str(op['client'])}#{int(op['seq'])}"


def split_id(identifier: str) -> tuple[str, int]:
    """The client and sequence number an operation id is made of."""

    text = str(identifier)
    client, _, seq = text.partition("#")
    if not client or not seq.isdigit():
        raise ContractError(f"malformed operation id: {identifier!r}")
    return client, int(seq)


def canonical_value(value: Any) -> Any:
    """The stored form of a field value.

    A value is a JSON scalar, or a link to another card written
    ``{"link": "<card>"}``. Anything else is not a value this board can hold.
    """

    if isinstance(value, Mapping):
        if set(value) != {"link"}:
            raise ContractError(f"a field value may only link to a card: {value!r}")
        return {"link": str(value["link"])}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise ContractError(f"a field value must be a scalar or a card link: {value!r}")


def require_op(op: Any) -> dict[str, Any]:
    """Validate one operation and return it in its stored form."""

    if not isinstance(op, Mapping):
        raise ContractError("an operation must be a mapping")
    missing = [name for name in OP_FIELDS if name not in op]
    if missing:
        raise ContractError(f"operation is missing fields: {', '.join(missing)}")
    kind = str(op["kind"])
    if kind not in OP_KINDS:
        raise ContractError(f"operation kind must be one of {OP_KINDS}")
    client = str(op["client"])
    if not client or "#" in client:
        raise ContractError(f"malformed client name: {client!r}")
    seq = int(op["seq"])
    if seq < 1:
        raise ContractError("seq counts a client's own operations from 1")
    card = str(op["card"])
    field = str(op["field"])
    if not card or not field:
        raise ContractError("an operation names one card and one field")
    deps = require_vector(op["deps"])
    stored: dict[str, Any] = {
        "kind": kind,
        "client": client,
        "seq": seq,
        "card": card,
        "field": field,
        "edited_at": int(op["edited_at"]),
        "deps": deps,
    }
    if kind == "edit":
        if "value" not in op:
            raise ContractError("an edit carries a value")
        stored["value"] = canonical_value(op["value"])
    return stored


def pack(ops: Iterable[Mapping[str, Any]]) -> str:
    """The wire form of one packet of operations."""

    return json.dumps(
        {"ops": [require_op(op) for op in ops]}, ensure_ascii=False, sort_keys=True
    )


def unpack(packet: str | Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """The operations in one packet, in the order the sender put them."""

    body = json.loads(packet) if isinstance(packet, str) else packet
    if not isinstance(body, Mapping) or not isinstance(body.get("ops"), Sequence):
        raise ContractError("a packet is an object with a list of ops")
    return tuple(require_op(op) for op in body["ops"])


# --------------------------------------------------------------------------
# Causality


def require_vector(vector: Any) -> dict[str, int]:
    """Validate a version vector; clients at zero are dropped."""

    if not isinstance(vector, Mapping):
        raise ContractError("a version vector maps a client name to a sequence number")
    stored: dict[str, int] = {}
    for client, seq in vector.items():
        name = str(client)
        count = int(seq)
        if count < 0:
            raise ContractError(f"sequence numbers do not go backwards: {name}={count}")
        if count:
            stored[name] = count
    return stored


def dominates(vector: Mapping[str, int], identifier: str) -> bool:
    """Does ``vector`` account for the operation ``identifier`` names?"""

    client, seq = split_id(identifier)
    return int(dict(vector).get(client, 0)) >= seq


def happens_before(earlier: Mapping[str, Any], later: Mapping[str, Any]) -> bool:
    """Had the author of ``later`` already integrated ``earlier`` when they wrote it?

    Two operations for which this holds in neither direction were made
    without either author seeing the other's work.
    """

    return dominates(later["deps"], op_id(earlier))


def merge_vectors(*vectors: Mapping[str, int]) -> dict[str, int]:
    """The vector that accounts for everything all of ``vectors`` account for."""

    merged: dict[str, int] = {}
    for vector in vectors:
        for client, seq in require_vector(vector).items():
            merged[client] = max(merged.get(client, 0), int(seq))
    return merged


def contiguous_vector(identifiers: Iterable[str]) -> dict[str, int]:
    """The longest gap-free run of sequence numbers each client has in ``identifiers``.

    ``["ravi#1", "ravi#2", "ravi#4"]`` gives ``{"ravi": 2}``: ``ravi#4`` is
    there but ``ravi#3`` is not, so the run stops at 2.
    """

    seen: dict[str, set[int]] = {}
    for identifier in identifiers:
        client, seq = split_id(identifier)
        seen.setdefault(client, set()).add(seq)
    vector: dict[str, int] = {}
    for client, numbers in seen.items():
        run = 0
        while run + 1 in numbers:
            run += 1
        if run:
            vector[client] = run
    return vector


def covered_ids(vector: Mapping[str, int]) -> frozenset[str]:
    """Every operation id a vector claims to account for."""

    return frozenset(
        f"{client}#{number}"
        for client, seq in require_vector(vector).items()
        for number in range(1, int(seq) + 1)
    )


# --------------------------------------------------------------------------
# Boards and accounts


def require_snapshot(snapshot: Any) -> dict[str, dict[str, Any]]:
    """Validate a board snapshot and return it in canonical form.

    A field with no readable value is left out, and a card with no readable
    field is left out, so a card that was never touched and a card whose every
    field was cleared read the same.
    """

    if not isinstance(snapshot, Mapping):
        raise ContractError("a snapshot maps a card name to its fields")
    stored: dict[str, dict[str, Any]] = {}
    for card, fields in snapshot.items():
        if not isinstance(fields, Mapping):
            raise ContractError(f"card {card!r} must map a field name to a value")
        values = {str(field): canonical_value(value) for field, value in fields.items()}
        if values:
            stored[str(card)] = values
    return stored


def digest_of_board(snapshot: Mapping[str, Any]) -> str:
    """A canonical fingerprint of one board snapshot.

    Two copies that read the same have the same digest whatever order their
    fields were written in, so the support team compares these rather than
    reading two screens side by side.
    """

    body = json.dumps(
        require_snapshot(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def require_account(entries: Any) -> tuple[dict[str, Any], ...]:
    """Validate a merge account and return it in stored form.

    One entry says what became of one operation the copy has taken in:
    ``op`` is its id, ``card`` and ``field`` are the ones it changes,
    ``disposition`` is one of :data:`DISPOSITIONS`, and ``by`` is the id of the
    operation that displaced it, or null.
    """

    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise ContractError("a merge account is a sequence of entries")
    stored: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ContractError("each account entry must be a mapping")
        missing = [name for name in ACCOUNT_FIELDS if name not in entry]
        if missing:
            raise ContractError(f"account entry is missing fields: {', '.join(missing)}")
        disposition = str(entry["disposition"])
        if disposition not in DISPOSITIONS:
            raise ContractError(f"disposition must be one of {DISPOSITIONS}")
        identifier = str(entry["op"])
        split_id(identifier)
        by = entry["by"]
        if by is not None:
            split_id(str(by))
        stored.append(
            {
                "op": identifier,
                "card": str(entry["card"]),
                "field": str(entry["field"]),
                "disposition": disposition,
                "by": None if by is None else str(by),
            }
        )
    return tuple(deepcopy(stored))


__all__ = (
    "ACCOUNT_FIELDS", "ContractError", "DISPOSITIONS", "OP_FIELDS", "OP_KINDS",
    "canonical_value", "contiguous_vector", "covered_ids", "digest_of_board",
    "dominates", "happens_before", "merge_vectors", "op_id", "pack",
    "require_account", "require_op", "require_snapshot", "require_vector",
    "split_id", "unpack",
)
