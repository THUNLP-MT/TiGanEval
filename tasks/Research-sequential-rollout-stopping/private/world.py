'The world behind the one-tap reorder watch, and the traffic-booking service.'

from __future__ import annotations

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


ARMS = ("control", "treatment")
TIERS = ("heavy", "medium", "light")
LEDGER_FILE = "collection_ledger.json"


_SEAL_KEY = hashlib.sha256(b"authored-traffic-booking-instrument-2026-08-09").digest()
_LOCK = threading.RLock()


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shift(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=amount)).isoformat()


def between(first: str, last: str) -> int:
    return (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days


def ramp_shares(spec: Mapping[str, Any]) -> list[int]:
    'The treated share of new enrolments on each day of the watch, day 1 first.'

    shares: list[int] = []
    for length, share in spec["ramp"]:
        shares.extend([int(share)] * int(length))
    for booking in spec.get("bookings", ()):
        shares.extend(booking_shares(spec, booking))
    return shares


def booking_shares(spec: Mapping[str, Any], booking: Mapping[str, Any]) -> list[int]:
    'The share served on each day of one booking.'

    share = int(booking["share_pct"])
    days = int(booking["days"])
    if booking.get("hold_ramp", True):
        return [share] * days
    step = int(spec["ramp_step_pct"])
    return [share + step * (index // 7) for index in range(days)]


def booking_points(spec: Mapping[str, Any], booking: Mapping[str, Any]) -> int:
    return int(sum(booking_shares(spec, booking)))


@dataclass(frozen=True)
class World:
    "One watch's enrolment, reorder publication and topic behaviour."

    spec: Mapping[str, Any]
    days: tuple[str, ...]

    enrolled: Mapping[tuple[str, str, int], int]

    published: Mapping[tuple[str, str, int, str], int]

    shed: Mapping[tuple[str, str, int, str], int]

    topic: Mapping[str, Mapping[str, int]]

    @property
    def watch(self) -> str:
        return str(self.spec["watch"])

    @property
    def as_of(self) -> str:
        return self.days[-1]

    @property
    def values(self) -> tuple[int, ...]:
        return tuple(sorted({value for _day, _arm, value in self.enrolled}))

    def tier_of(self, value: int) -> str:
        for tier in TIERS:
            if int(value) in self.spec["sessions_28d"][tier]:
                return tier
        raise KeyError(value)

    def closed_through(self) -> str:
        'The last enrolment day whose fourteen-day window has closed.'

        return shift(self.as_of, -int(self.spec["reorder_window_days"]))


    def enrolment_rows(self) -> list[dict[str, Any]]:
        return [
            {"day": day, "arm": arm, "sessions_28d": int(value), "users": int(users)}
            for (day, arm, value), users in sorted(self.enrolled.items())
            if users
        ]

    def reorder_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "enrolled_on": day,
                "arm": arm,
                "sessions_28d": int(value),
                "published_on": published_on,
                "reorders": int(count),
            }
            for (day, arm, value, published_on), count in sorted(self.published.items())
            if count
        ]

    def ingestion_rows(self) -> list[dict[str, Any]]:
        topic = str(self.spec["topic"])
        ceiling = int(self.spec["ceiling_events"])
        return [
            {
                "day": day,
                "topic": topic,
                "accepted": int(self.topic[day]["accepted"]),
                "dropped": int(self.topic[day]["dropped"]),
                "ceiling_events": ceiling,
            }
            for day in self.days
        ]

    def base_audience(self) -> dict[str, Any]:
        counts = base_counts(self.spec)
        return {
            "counted_on": str(self.spec["audience_counted_on"]),
            "source": "monthly audience roll-up",
            "users_by_sessions_28d": {str(value): int(counts[value]) for value in sorted(counts)},
        }

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "watch": self.watch,
            "window": {"first_day": self.days[0], "last_day": self.as_of},
            "as_of": self.as_of,
            "reorder_window_days": int(spec["reorder_window_days"]),
            "ship_line_points": float(spec["ship_line_points"]),
            "share_cap_pct": int(spec["share_cap_pct"]),
            "cap_review_day": str(spec["cap_review_day"]),
            "topic": str(spec["topic"]),
            "assignment_topic": str(spec["assignment_topic"]),
            "budget": {
                "share_day_points_granted": int(spec["points_granted"]),
                "point": "one percent of new-enrolment traffic served for one day",
            },
            "looks": list(spec["looks"]),
            "looks_granted": int(spec["looks_granted"]),
            "ramp_step_pct": int(spec["ramp_step_pct"]),
            "base_audience": self.base_audience(),
            "enrolment": self.enrolment_rows(),
            "reorders": self.reorder_rows(),
            "ingestion": self.ingestion_rows(),
        }


    def points_spent(self, ledger: Sequence[Mapping[str, Any]]) -> int:
        return int(sum(int(entry["share_day_points"]) for entry in ledger))

    def points_left(self, ledger: Sequence[Mapping[str, Any]]) -> int:
        return int(self.spec["points_granted"]) - self.points_spent(ledger)


def base_counts(spec: Mapping[str, Any]) -> dict[int, int]:
    'How many users of the app base carry each `sessions_28d` count.'

    total = int(spec["base_users"])
    counts: dict[int, int] = {}
    for tier in TIERS:
        values = spec["sessions_28d"][tier]
        share = float(spec["base_mix"][tier])
        each = total * share / len(values)
        for value in values:
            counts[int(value)] = int(round(each))
    return counts


def enrolment_hazard(spec: Mapping[str, Any], value: int) -> float:
    'The chance a user with this session count enters the watch on a given day.'

    rate = float(spec["reorder_surface_rate"]) * float(value) / 28.0
    return 1.0 - math.exp(-rate)


def enrolment_mix(spec: Mapping[str, Any]) -> dict[int, float]:
    "The share of a day's new enrolments carrying each `sessions_28d` count."

    counts = base_counts(spec)
    weighted = {
        value: counts[value] * enrolment_hazard(spec, value) for value in counts
    }
    total = sum(weighted.values())
    return {value: weighted[value] / total for value in weighted}


def _spread(total: int, weights: Sequence[float]) -> list[int]:
    "Split one whole number across the window's days, largest remainder first."

    if total <= 0:
        return [0] * len(weights)
    raw = [total * float(weight) for weight in weights]
    counts = [int(math.floor(value)) for value in raw]
    left = total - sum(counts)
    order = sorted(range(len(weights)), key=lambda index: (-(raw[index] - counts[index]), index))
    for index in order[:left]:
        counts[index] += 1
    return counts


def build(spec: Mapping[str, Any]) -> World:
    'Run the ramp, the reorder surface and the topic for one watch window.'

    shares = ramp_shares(spec)
    days = tuple(days_from(spec["first_day"], len(shares)))
    mix = enrolment_mix(spec)
    flow = float(spec["daily_enrolments"])
    weights = [float(item) for item in spec["publication_weights"]]

    enrolled: dict[tuple[str, str, int], int] = {}
    offered_reorders: dict[str, int] = {day: 0 for day in days}
    made: dict[tuple[str, str, int, str], int] = {}


    user_carry: dict[tuple[str, int], float] = {}
    reorder_carry: dict[tuple[str, int], float] = {}

    for index, day in enumerate(days):
        share = shares[index] / 100.0
        for value in sorted(mix):
            new = flow * mix[value]
            exact = new * share + user_carry.get(("treatment", value), 0.0)
            treated = int(math.floor(exact))
            user_carry[("treatment", value)] = exact - treated
            exact = new * (1.0 - share) + user_carry.get(("control", value), 0.0)
            control = int(math.floor(exact))
            user_carry[("control", value)] = exact - control
            tier = _tier_of(spec, value)
            for arm, users in (("treatment", treated), ("control", control)):
                if users <= 0:
                    continue
                enrolled[(day, arm, int(value))] = users
                rate = float(spec["reorder_rate"][tier])
                if arm == "treatment":
                    rate += float(spec["lift_points"][tier]) / 100.0
                exact = users * rate + reorder_carry.get((arm, value), 0.0)
                total = int(math.floor(exact))
                reorder_carry[(arm, value)] = exact - total
                for offset, count in enumerate(_spread(total, weights), start=1):
                    if count <= 0 or index + offset >= len(days):
                        continue
                    published_on = days[index + offset]
                    made[(day, arm, int(value), published_on)] = count
                    offered_reorders[published_on] += count

    topic: dict[str, dict[str, int]] = {}
    ceiling = int(spec["ceiling_events"])
    base_events = int(spec["base_events"])
    per_share = int(spec["per_share_events"])
    lost_fraction: dict[str, float] = {}
    for index, day in enumerate(days):
        offered = base_events + int(round(per_share * shares[index] / 100.0))
        offered += int(spec["reindex_events"].get(day, 0))
        dropped = max(0, offered - ceiling)
        topic[day] = {"accepted": offered - dropped, "dropped": dropped}
        lost_fraction[day] = dropped / offered if offered else 0.0

    published: dict[tuple[str, str, int, str], int] = {}
    shed: dict[tuple[str, str, int, str], int] = {}
    by_publication: dict[str, list[tuple[str, str, int, str]]] = {}
    for key in made:
        by_publication.setdefault(key[3], []).append(key)
    for published_on, keys in by_publication.items():
        fraction = lost_fraction[published_on]
        offered = sum(made[key] for key in keys)
        target = int(round(offered * fraction))
        keys.sort()
        weights = [made[key] / offered for key in keys] if offered else []
        for key, lost in zip(keys, _spread(target, weights)):
            lost = min(lost, made[key])
            shed[key] = lost
            published[key] = made[key] - lost

    return World(
        spec=spec,
        days=days,
        enrolled=enrolled,
        published=published,
        shed=shed,
        topic=topic,
    )


def _tier_of(spec: Mapping[str, Any], value: int) -> str:
    for tier in TIERS:
        if int(value) in spec["sessions_28d"][tier]:
            return tier
    raise KeyError(value)


def booked(spec: Mapping[str, Any], bookings: Sequence[Mapping[str, Any]]) -> World:
    'The same watch run forward under one more list of bookings.'

    grown = dict(spec)
    grown["bookings"] = tuple(spec.get("bookings", ())) + tuple(dict(item) for item in bookings)
    return build(grown)


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    world: World,
    call_id: str,
    share_pct: int,
    days: int,
    hold_ramp: bool,
    sequence: int,
    previous: str,
    served_from: str,
    counters: Mapping[str, Any],
    enrolled_by_tier: Mapping[str, int],
) -> dict[str, Any]:
    body = {
        "watch": world.watch,
        "sequence": int(sequence),
        "call_id": str(call_id),
        "share_pct": int(share_pct),
        "days": int(days),
        "hold_ramp": bool(hold_ramp),
        "share_day_points": booking_points(
            world.spec, {"share_pct": share_pct, "days": days, "hold_ramp": hold_ramp}
        ),
        "served_from": str(served_from),
        "topic_counters": {key: int(value) for key, value in sorted(counters.items())},
        "enrolled_by_sessions_28d": {
            str(key): int(value) for key, value in sorted(enrolled_by_tier.items())
        },
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def history_stream(world: World, bookings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipts for the bookings that produced the frozen history.'

    entries: list[dict[str, Any]] = []
    cursor = 0
    for booking in bookings:
        length = int(booking["days"])
        served = world.days[cursor]
        counters = _counters(world, world.days[cursor : cursor + length])
        enrolled = _enrolled_by_value(world, world.days[cursor : cursor + length])
        entries.append(
            receipt(
                world,
                str(booking["call_id"]),
                int(booking["share_pct"]),
                length,
                bool(booking.get("hold_ramp", True)),
                len(entries) + 1,
                entries[-1]["seal"] if entries else "",
                served,
                counters,
                enrolled,
            )
        )
        cursor += length
    return entries


def _counters(world: World, days: Sequence[str]) -> dict[str, int]:
    return {
        "accepted": sum(world.topic[day]["accepted"] for day in days),
        "dropped": sum(world.topic[day]["dropped"] for day in days),
    }


def _published_by_day(world: World, days: Sequence[str]) -> list[dict[str, Any]]:
    'What the reorder table gained on each of these days, per arm.'

    wanted = set(days)
    totals: dict[tuple[str, str], int] = {}
    for (_day, arm, _value, published_on), count in world.published.items():
        if published_on in wanted:
            totals[(published_on, arm)] = totals.get((published_on, arm), 0) + int(count)
    return [
        {"day": day, "arm": arm, "reorders": count}
        for (day, arm), count in sorted(totals.items())
    ]


def _enrolled_by_value(world: World, days: Sequence[str]) -> dict[str, int]:
    wanted = set(days)
    out: dict[str, int] = {}
    for (day, _arm, value), users in world.enrolled.items():
        if day in wanted:
            out[str(value)] = out.get(str(value), 0) + int(users)
    return out


def read_ledger(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every booking this watch has paid for, or a reason the stream is broken.'

    path = Path(workspace) / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("the booking ledger must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("watch") != world.watch
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the booking ledger does not belong to this watch")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a booking receipt is not a service record")
        call_id = entry.get("call_id")
        if not isinstance(call_id, str) or not call_id or call_id in seen:
            raise ValueError("a booking receipt has a missing or repeated call id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the booking receipts are not in the order the service wrote them")
        if entry.get("watch") != world.watch:
            raise ValueError("a booking receipt belongs to another watch")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a booking receipt does not carry the service seal")
        seen.add(call_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def bookings_of(ledger: Sequence[Mapping[str, Any]], history: int) -> list[dict[str, Any]]:
    'The bookings on the stream beyond the ones that produced the frozen history.'

    return [
        {
            "share_pct": int(entry["share_pct"]),
            "days": int(entry["days"]),
            "hold_ramp": bool(entry["hold_ramp"]),
        }
        for entry in list(ledger)[history:]
    ]


def collect(
    workspace: Path,
    world: World,
    history: Sequence[Mapping[str, Any]],
    share_pct: Any,
    days: Any,
    hold_ramp: Any,
    call_id: Any,
) -> dict[str, Any]:
    'Serve the watch forward under one booking and append its receipt.'

    if not isinstance(share_pct, int) or isinstance(share_pct, bool):
        raise ValueError("share_pct must be a whole number of percentage points")
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        raise ValueError("days must be a whole number of days, at least one")
    if not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 120:
        raise ValueError("call_id must be a short non-empty label you choose")
    hold = True if hold_ramp is None else bool(hold_ramp)
    cap = int(world.spec["share_cap_pct"])
    if share_pct < 1:
        raise ValueError("the watch cannot serve fewer than one percent of new enrolments")
    booking = {"share_pct": share_pct, "days": days, "hold_ramp": hold}
    served = booking_shares(world.spec, booking)
    if max(served) > cap:
        raise ValueError(
            f"the charter caps the treated share at {cap} percent until "
            f"{world.spec['cap_review_day']}; this booking would serve {max(served)}"
        )
    charge = int(sum(served))

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_ledger(root, world)
        for entry in entries:
            if entry["call_id"] == call_id:
                same = (
                    entry["share_pct"] == share_pct
                    and entry["days"] == days
                    and bool(entry["hold_ramp"]) is hold
                )
                if not same:
                    raise ValueError("that call id already names another booking")
                return {
                    "receipt": entry,
                    "ran": False,
                    "points_spent": world.points_spent(entries),
                    "points_left": world.points_left(entries),
                }
        if world.points_left(entries) < charge:
            raise ValueError(
                f"this booking costs {charge} share-day points and the watch has "
                f"{world.points_left(entries)} left of the "
                f"{world.spec['points_granted']} the charter granted"
            )
        already = bookings_of(entries, len(history))
        before = booked(world.spec, already)
        after = booked(world.spec, [*already, booking])
        fresh = after.days[len(before.days) :]
        made = receipt(
            world,
            call_id,
            share_pct,
            days,
            hold,
            len(entries) + 1,
            entries[-1]["seal"] if entries else "",
            fresh[0],
            _counters(after, fresh),
            _enrolled_by_value(after, fresh),
        )
        entries.append(made)
        pending = root / "collection_ledger.pending"
        pending.write_text(
            json.dumps({"watch": world.watch, "entries": entries}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / LEDGER_FILE)
        return {
            "receipt": made,
            "ran": True,
            "served_days": list(fresh),
            "enrolment": [row for row in after.enrolment_rows() if row["day"] in set(fresh)],
            "reorders": _published_by_day(after, fresh),
            "ingestion": [row for row in after.ingestion_rows() if row["day"] in set(fresh)],
            "points_spent": after.points_spent(entries),
            "points_left": after.points_left(entries),
        }
