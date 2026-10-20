'The estates behind the gate-pass campaign, and the mail house that prints it.'

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import random
import threading
from typing import Any, Mapping, Sequence


LEDGER_FILE = "ledger/receipts.jsonl"


_SEAL_KEY = hashlib.sha256(b"authored-gate-pass-mail-house-2026-09-07").digest()
_LOCK = threading.RLock()


REFUSAL_OVER_CAP = "over the estate's monthly ticket allowance"
REFUSAL_PAST_CUT_OFF = "past the mail house cut-off for this month"
REFUSAL_OVER_POOL = "more tickets than the drum has names left"
REFUSAL_OVER_BALANCE = "more credits than the campaign account will release to this desk"
REFUSAL_NO_DRUM = "no drum of that name at this office"


def days_from(first_day: str, count: int) -> tuple[str, ...]:
    start = date.fromisoformat(str(first_day))
    return tuple((start + timedelta(days=index)).isoformat() for index in range(count))


def shift(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=amount)).isoformat()


def _uniform(*parts: Any) -> float:
    'One reproducible draw in [0, 1) from a tuple of labels.'

    digest = hashlib.blake2b(
        "|".join(str(part) for part in parts).encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


@dataclass(frozen=True)
class Campaign:
    "One office's accounts over one month, and what the month's drums did."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    account_ids: tuple[str, ...]
    address_of: tuple[int, ...]
    estate_of: tuple[str, ...]
    joined_on: tuple[str, ...]
    latent: tuple[float, ...]
    address_ids: tuple[str, ...]
    address_estate: tuple[str, ...]
    members: tuple[tuple[int, ...], ...]
    bookings: tuple[Mapping[str, Any], ...]
    ticket_rows: tuple[Mapping[str, Any], ...]
    reached: tuple[frozenset[int], ...] = field(repr=False, default=())
    ticket_day: tuple[str | None, ...] = field(repr=False, default=())
    tag_day: tuple[str | None, ...] = field(repr=False, default=())
    activated_at: tuple[str | None, ...] = field(repr=False, default=())
    viewed_on: str | None = field(repr=False, default=None)


    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def office(self) -> str:
        return str(self.spec["office"])

    @property
    def as_of(self) -> str:
        'The day the office is reading its own files.'

        if self.viewed_on is not None:
            return str(self.viewed_on)
        day = str(self.spec["as_of"])
        for booking in self.bookings:
            if booking.get("refused"):
                continue
            day = max(day, shift(str(booking["sent_on"]), 1))
        return min(day, str(self.spec["target_day"]))

    def as_at(self, day: str) -> "Campaign":
        'The same month as the office saw it on `day`.'

        day = str(day)
        keep = [
            position
            for position, booking in enumerate(self.bookings)
            if str(booking["sent_on"]) <= day
        ]
        return Campaign(
            spec=self.spec,
            days=self.days,
            account_ids=self.account_ids,
            address_of=self.address_of,
            estate_of=self.estate_of,
            joined_on=self.joined_on,
            latent=self.latent,
            address_ids=self.address_ids,
            address_estate=self.address_estate,
            members=self.members,
            bookings=tuple(self.bookings[position] for position in keep),
            ticket_rows=tuple(
                row
                for row in self.ticket_rows
                if str(row["sent_on"]) <= day
            ),
            reached=tuple(self.reached[position] for position in keep),
            ticket_day=tuple(
                stamp if stamp is not None and stamp <= day else None
                for stamp in self.ticket_day
            ),
            tag_day=tuple(
                stamp if stamp is not None and stamp <= day else None
                for stamp in self.tag_day
            ),
            activated_at=self.activated_at,
            viewed_on=day,
        )

    @property
    def target_day(self) -> str:
        return str(self.spec["target_day"])

    @property
    def cut_off(self) -> str:
        return str(self.spec["cut_off"])

    def size(self) -> int:
        return len(self.account_ids)


    def ticketed(self, index: int) -> bool:
        return self.ticket_day[index] is not None

    def tagged(self, index: int) -> bool:
        return self.tag_day[self.address_of[index]] is not None

    def activated(self, index: int) -> bool:
        return self.activated_at[index] is not None

    def stamped_by(self, index: int, day: str) -> bool:
        stamp = self.activated_at[index]
        return stamp is not None and stamp <= str(day)

    def untouched_addresses(self) -> list[int]:
        return [a for a in range(len(self.address_ids)) if self.tag_day[a] is None]

    def indices_at_untouched_addresses(self) -> list[int]:
        return [
            index
            for index in range(self.size())
            if self.tag_day[self.address_of[index]] is None
        ]

    def ticketed_indices(self) -> list[int]:
        return [index for index in range(self.size()) if self.ticketed(index)]

    def uninvited_indices(self) -> list[int]:
        return [index for index in range(self.size()) if not self.ticketed(index)]

    def lifted_neighbour_indices(self) -> list[int]:
        return [
            index
            for index in range(self.size())
            if not self.ticketed(index) and self.tagged(index)
        ]


    def stamp_as_of(self, index: int) -> str:
        'The stamp the register carries today; a later one has not happened yet.'

        stamp = self.activated_at[index]
        return stamp if stamp is not None and stamp <= self.as_of else ""

    def register_rows(self) -> list[dict[str, Any]]:
        '`account_register.csv`: one row an account, as the office holds it.'

        return [
            {
                "account_id": self.account_ids[index],
                "address_id": self.address_ids[self.address_of[index]],
                "estate": self.estate_of[index],
                "joined_on": self.joined_on[index],
                "activated_at": self.stamp_as_of(index),
            }
            for index in range(self.size())
        ]

    def receipt_rows(self) -> list[dict[str, Any]]:
        '`invitation_receipts.csv`: one row a charged ticket, in print order.'

        return [dict(row) for row in self.ticket_rows]

    def counter_through(self, day: str) -> str:
        'The last day of sign-ups a counter row written on `day` can hold.'

        lag = int(self.spec["counter_lag"])
        if self.spec.get("counter_backfilled"):
            lag = 0
        covered = date.fromisoformat(str(day)) - timedelta(days=lag)
        if self.spec.get("counter_skips_weekend", True):
            while covered.weekday() >= 5:
                covered -= timedelta(days=1)
        return covered.isoformat()

    def counter_rows(self) -> list[dict[str, Any]]:
        '`signup_counter.csv`: what the nightly job has totalled, day by day.'

        stamps = sorted(stamp for stamp in self.activated_at if stamp is not None)
        rows: list[dict[str, Any]] = []
        for day in self.days:
            if day > self.as_of:
                break
            through = self.counter_through(day)
            if through < self.days[0]:
                continue
            total = sum(1 for stamp in stamps if stamp <= through)
            rows.append({"day": day, "signups_to_date": total})
        return rows


    def pool_members(self, drum: str) -> tuple[int, ...]:
        if drum == "citywide":
            return tuple(range(self.size()))
        if drum == "waitlist":
            return self.waitlist()
        if drum.startswith("estate:"):
            estate = drum.split(":", 1)[1]
            return tuple(
                index for index in range(self.size()) if self.estate_of[index] == estate
            )
        raise KeyError(drum)

    def waitlist(self) -> tuple[int, ...]:
        return skeleton(self.spec)["waitlist"]

    def drum_names(self) -> tuple[str, ...]:
        return ("citywide", *(f"estate:{name}" for name in self.spec["estates"]), "waitlist")

    def names_served(self, drum: str) -> set[int]:
        served: set[int] = set()
        for position, booking in enumerate(self.bookings):
            if booking.get("refused") or str(booking["drum"]) != drum:
                continue
            served |= self.reached[position]
        return served

    def names_left(self, drum: str) -> int:
        return len(set(self.pool_members(drum)) - self.names_served(drum))

    def tickets_used(self, drum: str) -> int:
        return sum(
            int(booking["tickets"])
            for booking in self.bookings
            if not booking.get("refused") and str(booking["drum"]) == drum
        )

    def price_of(self, drum: str) -> int:
        prices = self.spec["prices_per_hundred"]
        if drum.startswith("estate:"):
            return int(prices["estate"])
        return int(prices[drum])

    def ticket_cap(self, drum: str) -> int | None:
        if drum.startswith("estate:"):
            return int(self.spec["estate_ticket_cap"])
        return None

    def charge_for(self, drum: str, tickets: int) -> int:
        'What a drum bills for a run of tickets, rounded up to the hundred.'

        hundreds = -(-int(tickets) // 100)
        return hundreds * self.price_of(drum)

    def credits_spent(self) -> int:
        return sum(int(booking["charged"]) for booking in self.bookings)

    def credits_left(self) -> int:
        return int(self.spec["credits_granted"]) - self.credits_spent()

    def drum_table(self) -> list[dict[str, Any]]:
        rows = []
        for drum in self.drum_names():
            rows.append(
                {
                    "drum_id": drum,
                    "credits_per_hundred": self.price_of(drum),
                    "names_left": self.names_left(drum),
                    "tickets_this_month": self.tickets_used(drum),
                    "monthly_ticket_cap": self.ticket_cap(drum),
                }
            )
        return rows

    def context(self) -> dict[str, Any]:
        'The month as the reporting stack publishes it to a notebook.'

        spec = self.spec
        return {
            "campaign": self.campaign,
            "office": self.office,
            "window": {"first_day": self.days[0], "last_day": self.days[-1]},
            "as_of": self.as_of,
            "target": {
                "activations": int(spec["target_activations"]),
                "stamped_by": self.target_day,
            },
            "account": {
                "credits_granted": int(spec["credits_granted"]),
                "credits_spent": self.credits_spent(),
                "credits_left": self.credits_left(),
                "credits_reserve": int(spec["credits_reserve"]),
                "setup_charge": int(spec["setup_charge"]),
            },
            "mail_house": {
                "cut_off": self.cut_off,
                "estate_ticket_cap": int(spec["estate_ticket_cap"]),
                "billed_per": 100,
            },
            "drums": self.drum_table(),
            "files": {
                "register": "account_register.csv",
                "receipts": "invitation_receipts.csv",
                "counter": "signup_counter.csv",
                "ledger": LEDGER_FILE,
            },
        }


    def activations_by(self, day: str) -> int:
        return sum(1 for stamp in self.activated_at if stamp is not None and stamp <= str(day))


def _address_sizes(spec: Mapping[str, Any]) -> list[int]:
    weights = list(spec["address_size_weights"])
    total = float(sum(weights))
    cumulative: list[float] = []
    running = 0.0
    for weight in weights:
        running += weight / total
        cumulative.append(running)
    sizes: list[int] = []
    for index in range(int(spec["addresses"])):
        draw = _uniform(spec["seed"], "size", index)
        size = 1
        for position, edge in enumerate(cumulative):
            if draw < edge:
                size = position + 1
                break
        else:
            size = len(weights)
        sizes.append(size)
    return sizes


def _skeleton(spec: Mapping[str, Any]) -> dict[str, Any]:
    'Accounts, addresses and latents; everything before a ticket is printed.'

    estates = list(spec["estates"])
    sizes = _address_sizes(spec)
    account_ids: list[str] = []
    address_of: list[int] = []
    estate_of: list[str] = []
    joined_on: list[str] = []
    latent: list[float] = []
    address_ids: list[str] = []
    address_estate: list[str] = []
    members: list[tuple[int, ...]] = []
    first_day = date.fromisoformat(str(spec["first_day"]))
    household = float(spec["household_share"])
    counter = 0
    for position, size in enumerate(sizes):
        estate = estates[position % len(estates)]
        address_ids.append(f"{spec['address_prefix']}-{position + 1:05d}")
        address_estate.append(estate)
        shared = _uniform(spec["seed"], "address", position)
        block: list[int] = []
        for seat in range(size):
            counter += 1
            index = counter - 1
            account_ids.append(f"{spec['account_prefix']}-{counter:06d}")
            address_of.append(position)
            estate_of.append(estate)
            joined_on.append(
                (first_day - timedelta(days=30 + int(2_400 * _uniform(spec["seed"], "joined", index)))).isoformat()
            )
            if _uniform(spec["seed"], "household", index) < household:
                latent.append(shared)
            else:
                latent.append(_uniform(spec["seed"], "own", index))
            block.append(index)
        members.append(tuple(block))
    ranked = sorted(
        range(len(account_ids)),
        key=lambda index: _uniform(spec["seed"], "waitlist", index),
    )
    waitlist = tuple(sorted(ranked[: int(spec["waitlist_names"])]))
    return {
        "waitlist": waitlist,
        "account_ids": tuple(account_ids),
        "address_of": tuple(address_of),
        "estate_of": tuple(estate_of),
        "joined_on": tuple(joined_on),
        "latent": tuple(latent),
        "address_ids": tuple(address_ids),
        "address_estate": tuple(address_estate),
        "members": tuple(members),
    }


_SKELETONS: dict[str, dict[str, Any]] = {}


def skeleton(spec: Mapping[str, Any]) -> dict[str, Any]:
    key = str(spec["campaign"])
    if key not in _SKELETONS:
        _SKELETONS[key] = _skeleton(spec)
    return _SKELETONS[key]


_BUILDS: dict[tuple[Any, ...], Campaign] = {}


def build(spec: Mapping[str, Any], bookings: Sequence[Mapping[str, Any]]) -> Campaign:
    "Run one month's bookings through the office and stamp the register."

    key = (
        json.dumps({k: v for k, v in spec.items() if k != "address_size_weights"}, sort_keys=True, default=str),
        json.dumps(
            [
                [
                    str(item["receipt_id"]),
                    str(item["drum"]),
                    int(item["tickets"]),
                    str(item["sent_on"]),
                    item.get("refused"),
                ]
                for item in bookings
            ],
            sort_keys=True,
        ),
    )
    held = _BUILDS.get(key)
    if held is not None:
        return held
    campaign = _build(spec, bookings)
    if len(_BUILDS) > 256:
        _BUILDS.clear()
    _BUILDS[key] = campaign
    return campaign


def _build(spec: Mapping[str, Any], bookings: Sequence[Mapping[str, Any]]) -> Campaign:
    parts = skeleton(spec)
    account_ids = parts["account_ids"]
    address_of = parts["address_of"]
    members = parts["members"]
    latent = parts["latent"]
    size = len(account_ids)

    campaign = Campaign(
        spec=spec,
        days=days_from(spec["first_day"], int(spec["days"])),
        account_ids=account_ids,
        address_of=address_of,
        estate_of=parts["estate_of"],
        joined_on=parts["joined_on"],
        latent=latent,
        address_ids=parts["address_ids"],
        address_estate=parts["address_estate"],
        members=members,
        bookings=tuple(dict(booking) for booking in bookings),
        ticket_rows=(),
    )


    reached: list[frozenset[int]] = []
    ticket_rows: list[dict[str, Any]] = []
    ticket_day: list[str | None] = [None] * size
    served_by_drum: dict[str, set[int]] = {}
    counter = 0
    for position, booking in enumerate(campaign.bookings):
        drum = str(booking["drum"])
        if booking.get("refused"):
            reached.append(frozenset())
            continue
        pool = [
            index
            for index in campaign.pool_members(drum)
            if index not in served_by_drum.get(drum, set())
        ]
        generator = random.Random(
            int(hashlib.blake2b(
                f"{spec['seed']}|{booking['receipt_id']}".encode("utf-8"), digest_size=8
            ).hexdigest(), 16)
        )
        hit: set[int] = set()
        sent_on = str(booking["sent_on"])
        for _ in range(int(booking["tickets"])):
            counter += 1
            index = pool[generator.randrange(len(pool))] if pool else -1
            if index < 0:
                continue
            hit.add(index)
            ticket_rows.append(
                {
                    "ticket_id": f"{spec['ticket_prefix']}-{counter:06d}",
                    "receipt_id": str(booking["receipt_id"]),
                    "drum_id": drum,
                    "account_id": account_ids[index],
                    "sent_on": sent_on,
                }
            )
            if ticket_day[index] is None or sent_on < str(ticket_day[index]):
                ticket_day[index] = sent_on
        served_by_drum.setdefault(drum, set()).update(hit)
        reached.append(frozenset(hit))


    tag_day: list[str | None] = [None] * len(members)
    for index in range(size):
        day = ticket_day[index]
        if day is None:
            continue
        address = address_of[index]
        if tag_day[address] is None or day < str(tag_day[address]):
            tag_day[address] = day


    base = float(spec["base_rate"])
    lift = float(spec["ticket_lift"])
    tag_lift = float(spec["tag_lift"])
    as_of = str(spec["as_of"])
    activated_at: list[str | None] = [None] * size
    for index in range(size):
        own = ticket_day[index]
        tag = tag_day[address_of[index]]
        threshold = base + (lift if own is not None else (tag_lift if tag is not None else 0.0))
        if latent[index] >= threshold:
            continue
        if own is not None:
            late = float(spec.get("late_share", 0.28))
            day = shift(own, 1 if _uniform(spec["seed"], "wait", index) < late else 0)
        elif tag is not None:
            day = shift(tag, int(3.0 * _uniform(spec["seed"], "wait", index)))
        else:
            window = int(spec.get("baseline_days", 20))
            day = shift(
                spec["first_day"], int(window * _uniform(spec["seed"], "wait", index))
            )
        activated_at[index] = day

    return Campaign(
        spec=spec,
        days=campaign.days,
        account_ids=account_ids,
        address_of=address_of,
        estate_of=parts["estate_of"],
        joined_on=parts["joined_on"],
        latent=latent,
        address_ids=parts["address_ids"],
        address_estate=parts["address_estate"],
        members=members,
        bookings=campaign.bookings,
        ticket_rows=tuple(ticket_rows),
        reached=tuple(reached),
        ticket_day=tuple(ticket_day),
        tag_day=tuple(tag_day),
        activated_at=tuple(activated_at),
    )


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def refusal_for(
    campaign: Campaign, drum: Any, tickets: Any, send_on: Any, reserve: int | None = None
) -> str | None:
    "The mail house's own reason for turning a booking back, or None."

    drum = str(drum or "")
    if drum not in campaign.drum_names():
        return REFUSAL_NO_DRUM
    if not isinstance(tickets, int) or isinstance(tickets, bool) or tickets <= 0:
        return None
    if str(send_on) > campaign.cut_off:
        return REFUSAL_PAST_CUT_OFF
    cap = campaign.ticket_cap(drum)
    if cap is not None and campaign.tickets_used(drum) + int(tickets) > cap:
        return REFUSAL_OVER_CAP
    if int(tickets) > campaign.names_left(drum):
        return REFUSAL_OVER_POOL
    held = int(campaign.spec["credits_reserve"]) if reserve is None else int(reserve)
    if campaign.charge_for(drum, int(tickets)) > campaign.credits_left() - held:
        return REFUSAL_OVER_BALANCE
    return None


def booking_record(
    campaign: Campaign,
    receipt_id: str,
    drum: str,
    tickets: int,
    send_on: str,
    refused: str | None,
) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt_id),
        "drum": str(drum),
        "tickets": int(tickets),
        "sent_on": str(send_on),
        "refused": refused,
        "charged": int(campaign.spec["setup_charge"])
        if refused
        else campaign.charge_for(str(drum), int(tickets)),
    }


def receipt_body(after: Campaign, position: int) -> dict[str, Any]:
    'One booking as the mail house writes it up.'

    booking = after.bookings[position]
    hit = after.reached[position]
    return {
        "receipt_id": str(booking["receipt_id"]),
        "campaign": after.campaign,
        "drum": str(booking["drum"]),
        "sent_on": str(booking["sent_on"]),
        "tickets_requested": int(booking["tickets"]),
        "tickets_printed": 0 if booking.get("refused") else int(booking["tickets"]),
        "accounts_reached": len(hit),
        "refused": booking.get("refused"),
        "credits_charged": int(booking["charged"]),
        "credits_left": int(after.spec["credits_granted"]) - sum(
            int(item["charged"]) for item in after.bookings[: position + 1]
        ),
    }


def seal_body(body: Mapping[str, Any], sequence: int, previous: str = "") -> dict[str, Any]:
    value = dict(body)
    value["sequence"] = int(sequence)
    value["previous"] = str(previous)
    return dict(value, seal=_seal(value))


def sealed_ledger(spec: Mapping[str, Any], bookings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "The receipts for one month's bookings, sealed in the order they ran."

    after = build(spec, bookings)
    entries: list[dict[str, Any]] = []
    for position in range(len(bookings)):
        body = receipt_body(after, position)
        entries.append(
            seal_body(body, position + 1, entries[-1]["seal"] if entries else "")
        )
    return entries


def ledger_text(entries: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(entry, sort_keys=True, separators=(",", ": ")) + "\n" for entry in entries
    )


def bookings_from(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "receipt_id": str(entry["receipt_id"]),
            "drum": str(entry["drum"]),
            "tickets": int(entry["tickets_requested"]),
            "sent_on": str(entry["sent_on"]),
            "refused": entry.get("refused"),
            "charged": int(entry["credits_charged"]),
        }
        for entry in entries
    ]


def read_ledger(workspace: Path, spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Every booking this campaign has paid for, or a reason the file will not read.'

    path = Path(workspace) / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("the booking ledger must not be a symlink")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"line {number} of the booking ledger is not a receipt") from None
        if not isinstance(entry, dict):
            raise ValueError(f"line {number} of the booking ledger is not a receipt")
        receipt_id = entry.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            raise ValueError("a booking has a missing or repeated receipt id")
        if entry.get("campaign") != str(spec["campaign"]):
            raise ValueError("a booking belongs to another campaign")
        if entry.get("sequence") != len(entries) + 1 or entry.get("previous") != previous:
            raise ValueError("the bookings are not in the order the mail house wrote them")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a booking does not carry the mail house's seal")
        seen.add(receipt_id)
        previous = str(signature)
        entries.append(entry)
    if not entries:
        raise ValueError("the booking ledger is empty")
    return entries


def collect(
    workspace: Path,
    spec: Mapping[str, Any],
    drum: Any,
    tickets: Any,
    send_on: Any,
    receipt_id: Any,
) -> dict[str, Any]:
    'Put one booking through the mail house and append its sealed receipt.'

    if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 120:
        raise ValueError("receipt_id must be a short non-empty label you choose")
    if not isinstance(tickets, int) or isinstance(tickets, bool) or tickets <= 0:
        raise ValueError("tickets must be a positive whole number")
    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_ledger(root, spec)
        for entry in entries:
            if entry["receipt_id"] == receipt_id:
                return {"receipt": entry, "ran": False}
        held = bookings_from(entries)
        campaign = build(spec, held)
        day = str(send_on or campaign.as_of)
        try:
            date.fromisoformat(day)
        except ValueError:
            raise ValueError("send_on must be a date such as 2026-09-24") from None
        if day < campaign.as_of:
            raise ValueError(f"the mail house prints from {campaign.as_of} onward")
        refused = refusal_for(campaign, drum, tickets, day)
        if str(drum or "") not in campaign.drum_names():
            raise ValueError(f"{drum!r} is not a drum at this office")
        held.append(
            booking_record(campaign, receipt_id, str(drum), int(tickets), day, refused)
        )
        grown = sealed_ledger(spec, held)
        pending = root / (LEDGER_FILE + ".pending")
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(ledger_text(grown), encoding="utf-8")
        os.replace(pending, root / LEDGER_FILE)
        return {"receipt": grown[-1], "ran": True}
