'Deterministic whiteboard sessions: who edited what, and who got which packet.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


class Session:
    'Builds a session by following what each person could see as they worked.'

    def __init__(self) -> None:
        self.ops: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._next: dict[str, int] = {}
        self._known: dict[str, dict[str, int]] = {}


    def sees(self, client: str, *identifiers: str) -> None:
        '``client`` has integrated those operations before authoring anything else.'

        known = self._known.setdefault(str(client), {})
        for identifier in identifiers:
            op = self._by_id[identifier]
            for name, seq in dict(op["deps"]).items():
                known[name] = max(known.get(name, 0), int(seq))
            known[op["client"]] = max(known.get(op["client"], 0), int(op["seq"]))

    def edit(self, client: str, card: str, field: str, value: Any, at: int) -> str:
        return self._author("edit", client, card, field, at, value)

    def clear(self, client: str, card: str, field: str, at: int) -> str:
        return self._author("clear", client, card, field, at)

    def _author(
        self, kind: str, client: str, card: str, field: str, at: int, value: Any = None
    ) -> str:
        name = str(client)
        seq = self._next.get(name, 0) + 1
        self._next[name] = seq
        known = dict(self._known.setdefault(name, {}))
        op: dict[str, Any] = {
            "kind": kind,
            "client": name,
            "seq": seq,
            "card": str(card),
            "field": str(field),
            "edited_at": int(at),
            "deps": {key: int(value_) for key, value_ in sorted(known.items()) if value_},
        }
        if kind == "edit":
            op["value"] = value
        identifier = f"{name}#{seq}"
        self.ops.append(op)
        self._by_id[identifier] = op
        known[name] = seq
        self._known[name] = known
        return identifier


def _payload(
    session: Session,
    replicas: Mapping[str, Sequence[Sequence[str]]],
    catch_up: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "ops": [dict(op) for op in session.ops],
        "replicas": {
            str(name): {"client": str(name).split("-")[0],
                        "deliveries": [list(packet) for packet in packets]}
            for name, packets in replicas.items()
        },
        "catch_up": [{"replica": str(name), "peer": str(peer)}
                     for name, peer in catch_up.items()],
    }


def _whole_room_reconnect() -> dict[str, Any]:
    'Three people on a ferry, one card, three delivery orders and a repeat.'

    session = Session()
    card = "Cutover rehearsal"
    m1 = session.edit("meera", card, "Assignee", "Meera Nair", 1000)
    session.sees("tomas", m1)
    session.sees("ravi", m1)
    t1 = session.edit("tomas", card, "Status", "Blocked", 1200)
    r1 = session.edit("ravi", card, "Status", "In review", 1200)
    m2 = session.edit("meera", card, "Assignee", "Priya Raman", 1300)
    return _payload(
        session,
        {
            "meera-laptop": [[m1], [t1, r1], [m2]],
            "tomas-laptop": [[m1], [r1], [t1, m2]],
            "ravi-laptop": [[m1], [m2, r1], [t1], [m2, r1]],
        },
        {"meera-laptop": "tomas-laptop", "tomas-laptop": "ravi-laptop",
         "ravi-laptop": "meera-laptop"},
    )


def _handover_after_signal_loss() -> dict[str, Any]:
    'A hand-over typed on a laptop whose clock runs a minute and a half behind.'

    session = Session()
    card = "Vendor sign-off"
    t1 = session.edit("tomas", card, "Assignee", "Tomas Weber", 5000)
    session.sees("meera", t1)
    m1 = session.edit("meera", card, "Assignee", "Ravi Menon", 4910)
    t2 = session.edit("tomas", card, "Status", "In review", 5100)
    return _payload(
        session,
        {
            "meera-laptop": [[t1], [m1], [t2]],
            "tomas-laptop": [[m1, t1], [t2]],
            "ravi-laptop": [[t2, m1, t1]],
        },
        {"meera-laptop": "tomas-laptop", "tomas-laptop": "ravi-laptop",
         "ravi-laptop": "meera-laptop"},
    )


def _field_cleared_while_offline() -> dict[str, Any]:
    'Two fields emptied while a colleague is offline putting values into them.'

    session = Session()
    card = "Pilot store list"
    m1 = session.edit("meera", card, "Estimate", "3 days", 7000)
    m2 = session.edit("meera", card, "Status", "Blocked", 7050)
    session.sees("tomas", m1, m2)
    session.sees("ravi", m1)
    t1 = session.edit("tomas", card, "Owner", "Tomas Weber", 7080)
    r1 = session.edit("ravi", card, "Estimate", "5 days", 7100)
    session.sees("meera", t1)
    m3 = session.clear("meera", card, "Owner", 7150)
    r2 = session.edit("ravi", card, "Owner", "Ravi Menon", 7180)
    r3 = session.edit("ravi", card, "Status", "Needs vendor", 7220)
    r4 = session.clear("ravi", card, "Status", 7240)
    c1 = session.clear("tomas", card, "Estimate", 7200)
    c2 = session.clear("tomas", card, "Status", 7300)
    return _payload(
        session,
        {
            "meera-laptop": [[m1, m2], [t1], [m3, c1, c2], [r1, r2, r3, r4]],
            "tomas-laptop": [[m1, m2], [t1], [r1, r2], [r4, r3], [m3, c1, c2]],
            "ravi-laptop": [[m1, m2, t1, r1, m3, r2, r3, r4, c1, c2]],
        },
        {"meera-laptop": "tomas-laptop", "tomas-laptop": "ravi-laptop",
         "ravi-laptop": "meera-laptop"},
    )


def _queue_retry_storm() -> dict[str, Any]:
    "The delivery queue reorders one client's run and repeats a packet."

    session = Session()
    card = "Rollback drill"
    r1 = session.edit("ravi", card, "Due", "Friday", 9000)
    r2 = session.edit("ravi", card, "Status", "In review", 9060)
    r3 = session.edit("ravi", card, "Estimate", "2 days", 9120)
    session.sees("meera", r1, r2, r3)
    m1 = session.edit("meera", card, "Assignee", "Meera Nair", 9200)
    return _payload(
        session,
        {
            "ravi-laptop": [[r1], [r2], [r3], [m1]],
            "meera-laptop": [[r3], [r1], [r2], [m1]],
            "juno-laptop": [[r2], [r3], [m1], [r2]],
        },
        {"ravi-laptop": "meera-laptop", "meera-laptop": "ravi-laptop",
         "juno-laptop": "meera-laptop"},
    )


def _weekly_session() -> dict[str, Any]:
    'Four people, three cards, and clears with work beside them.'

    session = Session()
    rollout, vendor, freeze = "Store rollout", "Vendor call", "Freeze window"

    j1 = session.edit("juno", rollout, "Assignee", "Juno Park", 3000)
    for client in ("tomas", "ravi", "meera"):
        session.sees(client, j1)
    t1 = session.edit("tomas", rollout, "Status", "Blocked", 3200)
    r1 = session.edit("ravi", rollout, "Status", "Waiting on vendor", 3200)
    session.sees("meera", t1)
    e1 = session.edit("meera", rollout, "Status", "Ready", 3150)

    j2 = session.edit("juno", freeze, "Estimate", "4 days", 5000)
    j3 = session.edit("juno", freeze, "Status", "Blocked", 5050)
    session.sees("ravi", j2)
    session.sees("tomas", j2, j3)
    r2 = session.edit("ravi", freeze, "Estimate", "6 days", 5100)
    me1 = session.edit("meera", freeze, "Estimate", "2 days", 3400)
    mc1 = session.clear("meera", freeze, "Estimate", 3450)
    c1 = session.clear("tomas", freeze, "Estimate", 5200)
    c2 = session.clear("tomas", freeze, "Status", 5250)

    t4 = session.edit("tomas", vendor, "Assignee", "Tomas Weber", 4000)
    session.sees("meera", t4)
    e2 = session.edit("meera", vendor, "Assignee", "Ravi Menon", 3940)

    t5 = session.edit("tomas", vendor, "Status", "Waiting on vendor", 4100)
    session.sees("juno", t5)
    c3 = session.clear("juno", vendor, "Status", 4300)
    r3 = session.edit("ravi", vendor, "Status", "In review", 4400)

    j4 = session.edit("juno", vendor, "Depends on", {"link": rollout}, 5400)
    j5 = session.edit("juno", rollout, "Due", "Friday", 5500)

    return _payload(
        session,
        {
            "juno-desk": [[j1, t1], [r1, e1], [j2, j3, r2], [me1, mc1], [c1, c2],
                          [t4, e2], [t5, c3], [r3], [j4, j5]],
            "meera-desk": [[j1], [e1], [t1], [j2, r2, j3], [me1, mc1],
                           [t4, e2, c2, c1], [r1], [t5, r3, c3], [j5, j4],
                           [e1, t1]],
            "tomas-tablet": [[t1, r1], [e1], [j2, j3], [mc1, me1], [r2, c1, c2],
                             [t4, e2], [c3, r3, t5], [j4, j5]],
            "ravi-tablet": [[j1, j2, j3], [r1, r2], [t1, c1, c2, t4],
                            [e1, me1, mc1, e2], [r3, t5, c3], [j4, j5], [r1, r2]],
        },
        {"juno-desk": "ravi-tablet", "meera-desk": "juno-desk",
         "tomas-tablet": "meera-desk", "ravi-tablet": "juno-desk"},
    )


SESSION_BUILDERS = {
    "whole-room-reconnect": _whole_room_reconnect,
    "handover-after-signal-loss": _handover_after_signal_loss,
    "field-cleared-while-offline": _field_cleared_while_offline,
    "queue-retry-storm": _queue_retry_storm,
    "weekly-session": _weekly_session,
}


def build_session(name: str) -> dict[str, Any]:
    builder = SESSION_BUILDERS.get(str(name))
    if builder is None:
        raise ValueError(f"unknown session: {name}")
    return builder()


def resolve(ops: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    'Per card and field: which edits a clear took out, and which are still in play.'

    from ..workspace.board.contract import dominates, happens_before, op_id

    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for op in ops:
        entry = grouped.setdefault((str(op["card"]), str(op["field"])),
                                   {"edits": [], "clears": []})
        entry["edits" if str(op["kind"]) == "edit" else "clears"].append(dict(op))

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
        maximal = [
            edit for edit in live
            if not any(happens_before(edit, other) for other in live
                       if op_id(other) != op_id(edit))
        ]
        resolution[key] = {"edits": entry["edits"], "clears": clears,
                           "removed": removed, "live": live, "maximal": maximal}
    return resolution
