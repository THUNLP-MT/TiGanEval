"The world behind the service-start review, and the desk's booking service."

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


STATES = ("active", "trial", "suspended")
QUEUES = ("same_day", "next_slot")
RECEIPTS_FILE = "booking_receipts.json"


HORIZON = 30


_SEAL_KEY = hashlib.sha256(b"authored-support-desk-booking-instrument-2026-04-06").digest()
_LOCK = threading.RLock()

_GOLDEN = 0.6180339887498949


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shift(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=amount)).isoformat()


def between(first: str, last: str) -> int:
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def largest_remainder(values: Sequence[float]) -> list[int]:
    'Whole accounts that sum to the whole number the fractions add up to.'

    floors = [int(math.floor(value)) for value in values]
    left = int(round(sum(values))) - sum(floors)
    if left > 0:
        order = sorted(
            range(len(values)),
            key=lambda index: (-(values[index] - floors[index]), index),
        )
        for index in order[:left]:
            floors[index] += 1
    elif left < 0:
        order = sorted(
            range(len(values)),
            key=lambda index: ((values[index] - floors[index]), index),
        )
        for index in order[: -left]:
            if floors[index] > 0:
                floors[index] -= 1
    return floors


class Carrier:
    "Whole accounts, and the day each one's escalation lands on."

    def __init__(self) -> None:
        self._acc: dict[Any, list[float]] = {}

    def take(self, key: Any, amount: float) -> int:
        acc = self._acc.setdefault(("size", key), [0.0])
        acc[0] += float(amount)
        whole = int(math.floor(acc[0] + 1e-9))
        acc[0] -= whole
        return whole

    def allocate(self, key: Any, count: int, cumulative: Sequence[float]) -> list[int]:
        state = self._acc.get(("walk", key))
        if state is None:
            digest = hashlib.blake2b(repr(key).encode("utf-8"), digest_size=8)
            state = [0.0, (int(digest.hexdigest(), 16) % 100003) / 100003.0]
            self._acc[("walk", key)] = state
        out = [0] * len(cumulative)
        for _ in range(int(count)):
            state[0] += 1.0
            step = (state[1] + state[0] * _GOLDEN) % 1.0
            index = bisect.bisect_right(cumulative, step)
            out[min(index, len(cumulative) - 1)] += 1
        return out


def bar_on(spec: Mapping[str, Any], index: int) -> float:
    'The routing bar in force on the `index`-th day of the window.'

    return float(
        spec["bar_before"] if index < int(spec["bar_move_day"]) else spec["bar_after"]
    )


def week_load(spec: Mapping[str, Any], week: int) -> float:
    loads = spec["week_load"]
    return float(loads[week % len(loads)])


def wait_weights_on(spec: Mapping[str, Any], week: int) -> dict[int, float]:
    "How a week's waits fall across the days before the next open slot."

    weights = {int(day): float(value) for day, value in spec["wait_weights"].items()}
    if week_load(spec, week) <= float(spec["deep_week_load"]):
        return weights
    shifted: dict[int, float] = {day: 0.0 for day in weights}
    push = float(spec["deep_week_push"])
    last = max(weights)
    for day, value in weights.items():
        target = min(last, day + 1)
        shifted[day] += value * (1.0 - push)
        shifted[target] += value * push
    return shifted


def window_wait_weights(spec: Mapping[str, Any]) -> dict[int, float]:
    "The queue's waits over the whole window, weighted by each week's load."

    weeks = int(spec["window_days"]) // 7
    total: dict[int, float] = {}
    for week in range(weeks):
        load = week_load(spec, week)
        for day, value in wait_weights_on(spec, week).items():
            total[day] = total.get(day, 0.0) + load * value
    mass = sum(total.values())
    return {day: value / mass for day, value in total.items()}


def hazard_path(
    spec: Mapping[str, Any],
    error_rate: float,
    tier: str,
    state: str,
    queue: str,
    wait: int,
) -> list[float]:
    'The daily chance of an escalation for one kind of account, day 1 first.'

    raw = float(spec["hazard"][error_rate]) * float(spec["state_hazard_mult"][state])
    if state != "active":
        return [raw] * HORIZON
    treated = raw * (1.0 - float(spec["effect"][tier]))
    if queue == "same_day":
        return [treated] * HORIZON
    return [raw if day <= wait else treated for day in range(1, HORIZON + 1)]


def escalation_spread(path: Sequence[float]) -> list[float]:
    'The chance the escalation lands on each day, then the chance of none.'

    out: list[float] = []
    alive = 1.0
    for hazard in path:
        out.append(alive * hazard)
        alive *= 1.0 - hazard
    out.append(alive)
    return out


@dataclass(frozen=True)
class World:
    "One desk's flag ledger, account states and booking history."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    flags: tuple[Mapping[str, Any], ...]
    account_states: tuple[Mapping[str, Any], ...]
    bookings: tuple[Mapping[str, Any], ...]


    derived: tuple[Mapping[str, Any], ...] = ()

    @property
    def desk(self) -> str:
        return str(self.spec["desk"])

    @property
    def as_of(self) -> str:
        return self.days[-1]

    @property
    def export_through(self) -> str:
        'The last day the export can speak for: the migration, less the lag.'

        index = int(self.spec["migration_day"]) - int(self.spec["record_lag_days"])
        return self.days[index]

    @property
    def migration_date(self) -> str:
        return self.days[int(self.spec["migration_day"])]

    def book_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "error_rate_7d": float(error_rate),
                "plan_tier": str(tier),
                "accounts": int(self.spec["book"][(error_rate, tier)]),
            }
            for error_rate in self.spec["error_values"]
            for tier in self.spec["tiers"]
        ]

    def week_rows(self) -> list[dict[str, Any]]:
        rows = []
        for week in range(len(self.days) // 7):
            first = self.days[week * 7]
            rows.append(
                {"week": week, "first_day": first, "last_day": shift(first, 6)}
            )
        return rows

    def slots_spent(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return int(sum(int(entry["slots_charged"]) for entry in receipts))

    def slots_left(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return int(self.spec["slots_granted"]) - self.slots_spent(receipts)

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "desk": self.desk,
            "window": {"first_day": self.days[0], "last_day": self.as_of},
            "as_of": self.as_of,
            "escalation_window_days": int(spec["risk_window_days"]),
            "grace_window_days": int(spec["grace_window_days"]),
            "review": {
                "range_bar_points": float(spec["review_bar_points"]),
                "reviewed_on": str(spec["review_day"]),
            },
            "capacity": {
                "slots_granted": int(spec["slots_granted"]),
                "slots_per_week": int(spec["slots_per_week"]),
                "hold_cap": float(spec["hold_cap"]),
                "handed_back_charge": int(spec["handed_back_charge"]),
                "smallest_week_slots": int(spec["smallest_week_slots"]),
            },
            "export": {
                "migration_day": self.migration_date,
                "record_lag_days": int(spec["record_lag_days"]),
                "speaks_through": self.export_through,
            },
            "book": {
                "counted_on": str(spec["book_counted_on"]),
                "source": "desk book, monthly count",
                "accounts": self.book_rows(),
            },
            "weeks": self.week_rows(),
            "flags": [dict(row) for row in self.flags],
            "account_states": [dict(row) for row in self.account_states],
        }


def daily_flow(spec: Mapping[str, Any]) -> dict[tuple[float, str], float]:
    'Expected flags a day at each error rate and plan tier.'

    rate = float(spec["flag_base"])
    power = float(spec["flag_power"])
    tier_rate = spec["flag_tier_rate"]
    return {
        (error_rate, tier): int(spec["book"][(error_rate, tier)])
        * rate
        * (float(error_rate) ** power)
        * float(tier_rate[tier])
        for error_rate in spec["error_values"]
        for tier in spec["tiers"]
    }


def _state_rows(
    account_id: str, flag_day: str, state: str, prior_trial: bool
) -> list[dict[str, Any]]:
    'The stretches one account spent off `active` around its flag date.'

    if state == "trial":
        return [
            {"account_id": account_id, "state": "trial",
             "effective_from": shift(flag_day, -21), "effective_to": shift(flag_day, 25)},
        ]
    if state == "suspended":
        return [
            {"account_id": account_id, "state": "suspended",
             "effective_from": shift(flag_day, -9), "effective_to": shift(flag_day, 38)},
        ]
    if prior_trial:
        return [
            {"account_id": account_id, "state": "trial",
             "effective_from": shift(flag_day, -96), "effective_to": shift(flag_day, -34)},
        ]
    return []


class _Emitter:
    'Turns whole counts of one kind of account into ledger rows.'

    def __init__(self, spec: Mapping[str, Any], first: int = 1) -> None:
        self.spec = spec
        self.flags: list[dict[str, Any]] = []
        self.states: list[dict[str, Any]] = []
        self.derived: list[dict[str, Any]] = []
        self.next = int(first)
        self._trial_carry = 0.0

    def emit(
        self,
        day: str,
        error_rate: float,
        tier: str,
        state: str,
        queue: str,
        wait: int,
        slot: int,
        count: int,
        watched: int,
    ) -> None:
        last_observed = shift(day, int(watched))
        escalated = slot < HORIZON
        escalates_on = shift(day, slot + 1) if escalated else ""
        if state == "active":
            started = (
                day
                if queue == "same_day"
                else ("" if escalated and (slot + 1) <= wait else shift(day, wait))
            )
        else:
            started = ""
        shown = escalates_on if escalated and escalates_on <= last_observed else ""
        read = {
            "stratum": (float(error_rate), str(tier)),
            "queue": str(queue),
            "state": str(state),
            "waited": (None if not started else (0 if queue == "same_day" else int(wait))),
            "escalated_on": ((slot + 1) if shown else None),
            "watched": int(watched),
        }
        for _ in range(int(count)):
            index = self.next
            self.next += 1
            account_id = f"acc-{index:05d}"
            self.flags.append(
                {
                    "flag_id": f"flg-{index:05d}",
                    "account_id": account_id,
                    "flag_date": day,
                    "error_rate_7d": float(error_rate),
                    "plan_tier": str(tier),
                    "start_date": started,
                    "start_queue": queue,
                    "escalation_date": shown,
                    "last_observed_date": last_observed,
                }
            )
            self.derived.append(read)
            self._trial_carry += float(self.spec["prior_trial_share"])
            prior_trial = False
            if state == "active" and self._trial_carry >= 1.0:
                self._trial_carry -= 1.0
                prior_trial = True
            self.states.extend(_state_rows(account_id, day, state, prior_trial))


_CURVES: dict[tuple[Any, ...], list[float]] = {}


def escalation_curve(
    spec: Mapping[str, Any],
    error_rate: float,
    tier: str,
    state: str,
    queue: str,
    wait: int,
) -> list[float]:
    'The running chance the escalation has landed by each day, then never.'

    key = (id(spec), error_rate, tier, state, queue, wait)
    curve = _CURVES.get(key)
    if curve is None:
        curve = []
        running = 0.0
        for share in escalation_spread(
            hazard_path(spec, error_rate, tier, state, queue, wait)
        ):
            running += share
            curve.append(running)
        _CURVES[key] = curve
    return curve


def _kinds(
    spec: Mapping[str, Any], indices: Sequence[int], first_day: str, watched_of
) -> dict[tuple[Any, ...], dict[int, float]]:
    'Every kind of account these days raise, and which days raised it.'

    flow = daily_flow(spec)
    kinds: dict[tuple[Any, ...], dict[int, float]] = {}

    def add(key: tuple[Any, ...], index: int, amount: float) -> None:
        if amount > 0:
            days = kinds.setdefault(key, {})
            days[index] = days.get(index, 0.0) + amount

    for index in indices:
        week = index // 7
        load = week_load(spec, week)
        bar = bar_on(spec, index)
        waits = wait_weights_on(spec, week)
        wait_total = sum(waits.values())
        watched = watched_of(index)
        for error_rate in spec["error_values"]:
            for tier in spec["tiers"]:
                base = flow[(error_rate, tier)] * load
                same_day = float(
                    spec["same_day_share_above"]
                    if float(error_rate) >= bar
                    else spec["same_day_share_below"]
                )
                for state in STATES:
                    share = base * float(spec["state_shares"][state])
                    add((error_rate, tier, state, "same_day", 0, watched), index,
                        share * same_day)
                    for wait, weight in waits.items():
                        if weight <= 0:
                            continue
                        add(
                            (error_rate, tier, state, "next_slot", int(wait), watched),
                            index,
                            share * (1.0 - same_day) * weight / wait_total,
                        )
    return kinds


def _lay_out(
    spec: Mapping[str, Any],
    kinds: Mapping[tuple[Any, ...], Mapping[int, float]],
    days: Sequence[str],
    emitter: _Emitter,
    carrier: Carrier,
) -> None:
    'Settle how many accounts of each kind escalate on which day, and emit them.'

    by_day: dict[int, list[tuple[tuple[Any, ...], float]]] = {}
    for key, spread in kinds.items():
        for index, amount in spread.items():
            by_day.setdefault(index, []).append((key, amount))
    for index in sorted(by_day):
        for key, amount in sorted(by_day[index], key=lambda item: tuple(map(str, item[0]))):
            error_rate, tier, state, queue, wait, watched = key
            walk = (error_rate, tier, state, queue, wait)
            count = carrier.take(walk, amount)
            if count <= 0:
                continue
            curve = escalation_curve(spec, error_rate, tier, state, queue, wait)
            for slot, part in enumerate(carrier.allocate(walk, count, curve)):
                if part > 0:
                    emitter.emit(
                        days[index], error_rate, tier, state, queue, wait,
                        slot, part, watched,
                    )


def build(spec: Mapping[str, Any]) -> World:
    "Run the desk's routing, its queue and the export for one window."

    length = int(spec["window_days"])
    days = tuple(days_from(spec["first_day"], length))
    horizon = int(spec["risk_window_days"])
    speaks = int(spec["migration_day"]) - int(spec["record_lag_days"])

    def watched_of(index: int) -> int:
        return max(0, min(horizon, speaks - index))

    emitter = _Emitter(spec)
    _lay_out(
        spec, _kinds(spec, range(length), days[0], watched_of), days, emitter, Carrier()
    )
    order = sorted(range(len(emitter.flags)), key=lambda i: (
        emitter.flags[i]["flag_date"], emitter.flags[i]["flag_id"]
    ))
    return World(
        spec=spec,
        days=days,
        flags=tuple(emitter.flags[i] for i in order),
        account_states=tuple(emitter.states),
        bookings=(),
        derived=tuple(emitter.derived[i] for i in order),
    )


def segment_matches(segment: Any, row: Mapping[str, Any]) -> bool:
    "Whether one flag falls inside a segment the desk's sheet accepts."

    text = str(segment).strip()
    if not text or text.lower() == "all":
        return True
    for clause in text.split(","):
        piece = clause.strip()
        if not piece:
            continue
        if "=" not in piece:
            return False
        field, value = (part.strip() for part in piece.split("=", 1))
        if field == "plan_tier":
            if str(row["plan_tier"]) != value:
                return False
        elif field == "error_rate_7d":
            try:
                if abs(float(row["error_rate_7d"]) - float(value)) > 1e-9:
                    return False
            except ValueError:
                return False
        else:
            return False
    return True


def _booked_kinds(
    spec: Mapping[str, Any], week: int, booking: Mapping[str, Any], watched: int
) -> dict[tuple[Any, ...], dict[int, float]]:
    "The accounts one booked week puts on the desk's board."

    flow = daily_flow(spec)
    hold = float(booking["hold_share"])
    slots = int(booking["slots"])
    waits = wait_weights_on(spec, week)
    wait_total = sum(waits.values())
    load = week_load(spec, week)
    pool: list[tuple[int, float, str, str, float]] = []
    for step in range(7):
        index = week * 7 + step
        for error_rate in spec["error_values"]:
            for tier in spec["tiers"]:
                if not segment_matches(
                    booking.get("segment", "all"),
                    {"error_rate_7d": float(error_rate), "plan_tier": str(tier)},
                ):
                    continue
                base = flow[(error_rate, tier)] * load
                for state in STATES:
                    amount = base * float(spec["state_shares"][state])
                    if amount > 0:
                        pool.append((index, float(error_rate), str(tier), state, amount))
    total = sum(item[4] for item in pool)
    if total <= 0:
        return {}
    scale = slots / total
    kinds: dict[tuple[Any, ...], dict[int, float]] = {}

    def add(key: tuple[Any, ...], index: int, amount: float) -> None:
        if amount > 0:
            days = kinds.setdefault(key, {})
            days[index] = days.get(index, 0.0) + amount

    for index, error_rate, tier, state, amount in pool:
        share = amount * scale
        add((error_rate, tier, state, "same_day", 0, watched), index, share * (1.0 - hold))
        for wait, weight in waits.items():
            if weight <= 0:
                continue
            add(
                (error_rate, tier, state, "next_slot", int(wait), watched),
                index,
                share * hold * weight / wait_total,
            )
    return kinds


def _draw_week(
    spec: Mapping[str, Any],
    kinds: Mapping[tuple[Any, ...], Mapping[int, float]],
    days: Sequence[str],
    emitter: _Emitter,
    slots: int,
) -> None:
    'Put exactly the accounts the week bought on the board, in proportion.'

    cells: list[tuple[tuple[Any, ...], int, float]] = []
    running = 0.0
    for key in sorted(kinds, key=lambda item: tuple(str(part) for part in item)):
        error_rate, tier, state, queue, wait, _watched = key
        amount = sum(kinds[key].values())
        curve = escalation_curve(spec, error_rate, tier, state, queue, wait)
        previous = 0.0
        for slot, cumulative in enumerate(curve):
            share = cumulative - previous
            previous = cumulative
            if share <= 0.0:
                continue
            running += amount * share
            cells.append((key, slot, running))
    if not cells or running <= 0:
        return
    total = running
    picks: dict[tuple[tuple[Any, ...], int], int] = {}
    for step in range(1, int(slots) + 1):
        place = ((step * _GOLDEN) % 1.0) * total
        index = bisect.bisect_left([cell[2] for cell in cells], place)
        key, slot, _running = cells[min(index, len(cells) - 1)]
        picks[(key, slot)] = picks.get((key, slot), 0) + 1
    for (key, slot), count in sorted(
        picks.items(), key=lambda item: (tuple(str(part) for part in item[0][0]), item[0][1])
    ):
        error_rate, tier, state, queue, wait, watched = key
        by_day = kinds[key]
        indices = sorted(by_day)
        amount = sum(by_day.values())
        shares = [by_day[index] / amount for index in indices]
        for index, part in zip(
            indices, largest_remainder([count * share for share in shares])
        ):
            if part > 0:
                emitter.emit(
                    days[index], error_rate, tier, state, queue, wait,
                    slot, part, watched,
                )


def booked(world: World, bookings: Sequence[Mapping[str, Any]]) -> World:
    'The same desk with the weeks it has booked since the export ended.'

    spec = world.spec
    flags = list(world.flags)
    states = list(world.account_states)
    derived = list(world.derived)
    served: list[dict[str, Any]] = []
    first_week = len(world.days) // 7
    watched = int(spec["risk_window_days"]) - int(spec["record_lag_days"])
    index = len(flags) + 1
    for booking in bookings:
        if not booking.get("accepted", True):
            continue
        week = first_week + len(served)
        calendar = days_from(spec["first_day"], (week + 1) * 7)
        first_day = calendar[week * 7]
        emitter = _Emitter(spec, first=index)
        kinds = _booked_kinds(spec, week, booking, watched)
        _draw_week(spec, kinds, calendar, emitter, int(booking["slots"]))
        rows = len(emitter.flags)
        started = sum(1 for row in emitter.flags if row["start_date"])
        flags.extend(emitter.flags)
        states.extend(emitter.states)
        derived.extend(emitter.derived)
        index = emitter.next
        served.append(dict(booking, week=week, first_day=first_day,
                           rows_returned=int(rows), accounts_started=int(started)))
    return World(
        spec=spec,
        days=world.days,
        flags=tuple(flags),
        account_states=tuple(states),
        bookings=tuple(served),
        derived=tuple(derived),
    )


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    world: World,
    receipt_id: str,
    week: Any,
    segment: str,
    hold_share: float,
    slots: int,
    slots_charged: int,
    rows_returned: int,
    accounts_started: int,
    refusal: str,
    sequence: int,
    previous: str,
) -> dict[str, Any]:
    body = {
        "desk": world.desk,
        "sequence": int(sequence),
        "receipt_id": str(receipt_id),
        "week": int(week) if week is not None else -1,
        "segment": str(segment),
        "hold_share": float(hold_share),
        "slots_asked": int(slots),
        "slots_charged": int(slots_charged),
        "rows_returned": int(rows_returned),
        "accounts_started": int(accounts_started),
        "refusal": str(refusal),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def history_stream(world: World, calls: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipts for the calls the desk made before the review.'

    entries: list[dict[str, Any]] = []
    accepted = 0
    first_week = len(world.days) // 7
    for call in calls:
        refusal = str(call.get("refusal", ""))
        if refusal:
            entries.append(
                receipt(
                    world, str(call["receipt_id"]), -1, str(call.get("segment", "all")),
                    float(call.get("hold_share", 0.0)), int(call.get("slots", 0)),
                    int(world.spec["handed_back_charge"]), 0, 0, refusal,
                    len(entries) + 1, entries[-1]["seal"] if entries else "",
                )
            )
            continue
        served = world.bookings[accepted] if accepted < len(world.bookings) else {}
        entries.append(
            receipt(
                world, str(call["receipt_id"]), first_week + accepted,
                str(call.get("segment", "all")), float(call.get("hold_share", 0.0)),
                int(call["slots"]), int(call["slots"]),
                int(served.get("rows_returned", 0)), int(served.get("accounts_started", 0)),
                "", len(entries) + 1, entries[-1]["seal"] if entries else "",
            )
        )
        accepted += 1
    return entries


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every week this desk has paid for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the booking receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("desk") != world.desk
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the booking receipts do not belong to this desk")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a booking receipt is not a service record")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a booking receipt has a missing or repeated receipt id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the booking receipts are not in the order the desk wrote them")
        if entry.get("desk") != world.desk:
            raise ValueError("a booking receipt belongs to another desk")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a booking receipt does not carry the desk's seal")
        seen.add(receipt_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def bookings_of(
    receipts: Sequence[Mapping[str, Any]], history: int
) -> list[dict[str, Any]]:
    'The weeks served beyond the ones that produced the frozen ledger.'

    return [
        {
            "segment": str(entry["segment"]),
            "hold_share": float(entry["hold_share"]),
            "slots": int(entry["slots_asked"]),
            "accepted": not str(entry.get("refusal", "")),
        }
        for entry in list(receipts)[history:]
    ]


def refusal_for(
    world: World, segment: Any, hold_share: float, slots: int, left: int
) -> str:
    "The desk's own words when it hands a week back, or an empty string."

    spec = world.spec
    if slots > int(spec["slots_per_week"]):
        return (
            f"the desk books at most {spec['slots_per_week']} slots in a week and this "
            f"call asked for {slots}"
        )
    if hold_share > float(spec["hold_cap"]) + 1e-9:
        return (
            f"the desk holds at most {int(round(float(spec['hold_cap']) * 100))} percent of a "
            f"week's flags and this call asked to hold "
            f"{int(round(float(hold_share) * 100))}"
        )
    if slots > left:
        return (
            f"this week costs {slots} slots and the review has {left} left of the "
            f"{spec['slots_granted']} it granted"
        )
    return ""


def collect(
    workspace: Path,
    world: World,
    history: Sequence[Mapping[str, Any]],
    segment: Any,
    hold_share: Any,
    slots: Any,
    receipt_id: Any,
    week: Any = None,
) -> dict[str, Any]:
    'Serve the desk forward for one week and append its receipt.'

    if not isinstance(slots, int) or isinstance(slots, bool) or slots < 1:
        raise ValueError("slots must be a whole number of slots, at least one")
    if isinstance(hold_share, bool) or not isinstance(hold_share, (int, float)):
        raise ValueError("hold_share must be a number between 0 and 1")
    hold = float(hold_share)
    if hold < 0.0 or hold > 1.0:
        raise ValueError("hold_share must be a number between 0 and 1")
    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")
    if segment is not None and not isinstance(segment, str):
        raise ValueError("segment must be a text selector the desk's sheet accepts")
    label = "all" if segment is None else str(segment)

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                same = (
                    entry["segment"] == label
                    and abs(float(entry["hold_share"]) - hold) < 1e-9
                    and int(entry["slots_asked"]) == slots
                )
                if not same:
                    raise ValueError("that receipt id already names another week")
                return {
                    "receipt": entry,
                    "ran": False,
                    "slots_spent": world.slots_spent(entries),
                    "slots_left": world.slots_left(entries),
                }
        left = world.slots_left(entries)
        refusal = refusal_for(world, label, hold, slots, left)
        already = [*history, *bookings_of(entries, len(history))]
        first_week = len(world.days) // 7
        served_week = first_week + sum(1 for item in already if item.get("accepted", True))
        rows: list[Mapping[str, Any]] = []
        rows_returned = 0
        started = 0
        if not refusal:
            before = booked(world, already)
            after = booked(world, [*already, {
                "segment": label, "hold_share": hold, "slots": slots, "accepted": True
            }])
            fresh = after.flags[len(before.flags):]
            rows = [dict(row) for row in fresh]
            rows_returned = len(rows)
            started = sum(1 for row in rows if row["start_date"])
            if not rows_returned:
                refusal = (
                    f"no flags fell in segment {label!r} that week, so there was nothing "
                    "to serve"
                )
        charge = (
            min(int(world.spec["handed_back_charge"]), max(0, left)) if refusal else slots
        )
        made = receipt(
            world, receipt_id, served_week if not refusal else -1, label, hold, slots,
            charge, rows_returned, started, refusal,
            len(entries) + 1, entries[-1]["seal"] if entries else "",
        )
        entries.append(made)
        pending = root / "booking_receipts.pending"
        pending.write_text(
            json.dumps({"desk": world.desk, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / RECEIPTS_FILE)
        return {
            "receipt": made,
            "ran": not refusal,
            "refusal": refusal,
            "flags": rows,
            "slots_spent": world.slots_spent(entries),
            "slots_left": world.slots_left(entries),
        }
