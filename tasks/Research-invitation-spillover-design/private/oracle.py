'What the world says, counted from the accounts rather than read off a report.'

from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any, Mapping, Sequence

from . import world


TOLERANCE = 0.8


DECOY_SLACK = 0.30

COVER = 1.96


RANGE_FLOOR = 0.86
RANGE_CEILING = 1.15

COVERAGE_MIN = 0.8

INVARIANCE = 0.4


CHARGE_CEILING = 1.60


PLAN_YIELD_FLOOR = 2.0
PLAN_YIELD_SHARE = 0.10


def plan_yield_slack(shortfall: float) -> float:
    'How far under the target a forecast plan may land and still reach it.'

    return max(PLAN_YIELD_FLOOR, PLAN_YIELD_SHARE * max(0.0, float(shortfall)))


def _rate(campaign: world.Campaign, rows: Sequence[int], through: str | None = None) -> float:
    if not rows:
        return 0.0
    if through is None:
        through = campaign.as_of
    return sum(1 for index in rows if campaign.stamped_by(index, through)) / len(rows)


def ticket_effect(campaign: world.Campaign) -> float:
    'What a pass did to the account it was addressed to, in points.'

    return 100.0 * (
        _rate(campaign, campaign.ticketed_indices())
        - _rate(campaign, campaign.indices_at_untouched_addresses())
    )


def parameter_lift(campaign: world.Campaign) -> float:
    "What a pass is worth at this office, in points: the world's own number."

    return 100.0 * float(campaign.spec["ticket_lift"])


def uninvited_contrast(campaign: world.Campaign) -> float:
    'The reading a pivot gives when every uninvited account is the comparison.'

    return 100.0 * (
        _rate(campaign, campaign.ticketed_indices())
        - _rate(campaign, campaign.uninvited_indices())
    )


def counter_contrast(campaign: world.Campaign) -> float:
    'The reading the same two rows give when sign-ups stop at the counter.'

    through = campaign.counter_through(campaign.as_of)
    return 100.0 * (
        _rate(campaign, campaign.ticketed_indices(), through)
        - _rate(campaign, campaign.indices_at_untouched_addresses(), through)
    )


def counter_uninvited_contrast(campaign: world.Campaign) -> float:
    "Her own pivot, with sign-ups stopped where the counter's total stops."

    through = campaign.counter_through(campaign.as_of)
    return 100.0 * (
        _rate(campaign, campaign.ticketed_indices(), through)
        - _rate(campaign, campaign.uninvited_indices(), through)
    )


def tag_effect(campaign: world.Campaign) -> float:
    'What the keypad tag did to the accounts that share an address, in points.'

    return 100.0 * (
        _rate(campaign, campaign.lifted_neighbour_indices())
        - _rate(campaign, campaign.indices_at_untouched_addresses())
    )


def _clustered_variance(campaign: world.Campaign, rows: Sequence[int]) -> float:
    "The variance of one group's rate with the address as the unit."

    if not rows:
        return 0.0
    rate = _rate(campaign, rows)
    groups: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for index in rows:
        block = groups[campaign.address_of[index]]
        block[0] += 1
        block[1] += 1 if campaign.stamp_as_of(index) else 0
    count = len(groups)
    total = sum(block[0] for block in groups.values())
    if count < 2 or total == 0:
        return rate * (1.0 - rate) / max(1, len(rows))
    spread = sum((block[1] - rate * block[0]) ** 2 for block in groups.values())
    return (count / (count - 1)) * spread / (total * total)


def _account_variance(campaign: world.Campaign, rows: Sequence[int]) -> float:
    if not rows:
        return 0.0
    rate = _rate(campaign, rows)
    return rate * (1.0 - rate) / len(rows)


def supported_half_width(campaign: world.Campaign) -> float:
    'Half the tightest honest range the addresses behind this month support.'

    ticketed = campaign.ticketed_indices()
    untouched = campaign.indices_at_untouched_addresses()
    variance = _clustered_variance(campaign, ticketed) + _clustered_variance(
        campaign, untouched
    )
    return 100.0 * COVER * sqrt(variance)


def account_half_width(campaign: world.Campaign) -> float:
    'The half-width the same rows give when every account is its own reading.'

    ticketed = campaign.ticketed_indices()
    untouched = campaign.indices_at_untouched_addresses()
    variance = _account_variance(campaign, ticketed) + _account_variance(
        campaign, untouched
    )
    return 100.0 * COVER * sqrt(variance)


def plan_bookings(answer: Any) -> list[Mapping[str, Any]] | None:
    'The bookings a plan asks for, or None when it is not a plan at all.'

    if isinstance(answer, str):
        return None
    if not isinstance(answer, list) or not answer:
        return None
    rows: list[Mapping[str, Any]] = []
    for item in answer:
        if not isinstance(item, Mapping):
            return None
        tickets = item.get("tickets")
        if not isinstance(tickets, int) or isinstance(tickets, bool) or tickets <= 0:
            return None
        if not isinstance(item.get("drum"), str) or not str(item.get("drum")).strip():
            return None
        rows.append(item)
    return rows


def _booking_id(position: int, drum: str) -> str:
    "One booking's name in the barrel, so the same booking draws the same names."

    return f"plan-{position:02d}-{drum}"


def posting_day(spec: Mapping[str, Any], held: Sequence[Mapping[str, Any]]) -> str:
    "The day the desk places this month's remaining plan on."

    return world.build(spec, held).as_of


def apply_plan(
    spec: Mapping[str, Any],
    held: Sequence[Mapping[str, Any]],
    plan: Sequence[Mapping[str, Any]],
) -> tuple[world.Campaign, list[dict[str, Any]], str | None, Mapping[str, Any] | None]:
    "Run a plan's bookings past the mail house, in the order it asked for them."

    grown = [dict(item) for item in held]
    today = posting_day(spec, held)
    for position, booking in enumerate(plan):
        campaign = world.build(spec, grown)
        drum = str(booking["drum"])
        tickets = int(booking["tickets"])
        send_on = str(booking.get("send_on") or today)
        if drum not in campaign.drum_names():
            return campaign, grown, world.REFUSAL_NO_DRUM, booking
        if send_on < today:
            send_on = today
        refused = world.refusal_for(campaign, drum, tickets, send_on, reserve=0)
        if refused:
            return campaign, grown, refused, booking
        grown.append(
            world.booking_record(
                campaign, _booking_id(position, drum), drum, tickets, send_on, None
            )
        )
    return world.build(spec, grown), grown, None, None


def plan_charge(
    spec: Mapping[str, Any],
    held: Sequence[Mapping[str, Any]],
    grown: Sequence[Mapping[str, Any]],
) -> int:
    return sum(int(item["charged"]) for item in grown) - sum(
        int(item["charged"]) for item in held
    )


def plan_activations(
    spec: Mapping[str, Any], grown: Sequence[Mapping[str, Any]]
) -> int:
    campaign = world.build(spec, grown)
    return campaign.activations_by(campaign.target_day)


def target_of(spec: Mapping[str, Any]) -> int:
    return int(spec["target_activations"])


UNSIZEABLE_DRUMS = ("waitlist",)


def planning_rates(campaign: world.Campaign) -> tuple[float, float]:
    'The direct and tag rate differences the public register supports.'

    return (
        max(0.0, ticket_effect(campaign) / 100.0),
        max(0.0, tag_effect(campaign) / 100.0),
    )


def expected_new_signups(
    before: world.Campaign,
    drum: str,
    tickets: int,
    rates: tuple[float, float] | None = None,
) -> float:
    'What a run of `tickets` on one drum adds to the register, in expectation.'

    pool = set(before.pool_members(drum)) - before.names_served(drum)
    names = len(pool)
    if names <= 0 or int(tickets) <= 0:
        return 0.0
    pulled = 1.0 - (1.0 - 1.0 / names) ** int(tickets)

    lift, tag_lift = rates if rates is not None else planning_rates(before)


    on_a_pass = lift
    on_a_pass_behind_a_tag = max(0.0, lift - tag_lift)
    on_a_tag = tag_lift

    pool_at_address: dict[int, int] = {}
    for index in pool:
        address = before.address_of[index]
        pool_at_address[address] = pool_at_address.get(address, 0) + 1

    total = 0.0
    for index in range(before.size()):
        if before.stamped_by(index, before.as_of) or before.ticketed(index):
            continue
        own = pulled if index in pool else 0.0
        if before.tagged(index):
            total += own * on_a_pass_behind_a_tag
            continue
        total += own * on_a_pass
        here = pool_at_address.get(before.address_of[index], 0) - (
            1 if index in pool else 0
        )
        if here > 0:
            total += (1.0 - own) * (1.0 - (1.0 - pulled) ** here) * on_a_tag
    return total


def expected_activations(
    spec: Mapping[str, Any],
    held: Sequence[Mapping[str, Any]],
    plan: Sequence[Mapping[str, Any]],
) -> float:
    'Where a plan puts the register by the target day, in expectation.'

    campaign = world.build(spec, held)
    lift, tag_lift = planning_rates(campaign)
    total = float(campaign.activations_by(campaign.as_of))


    requested: dict[str, int] = defaultdict(int)
    for booking in plan:
        requested[str(booking["drum"])] += int(booking["tickets"])

    draws: list[tuple[set[int], int, int, dict[int, int]]] = []
    for drum, tickets in requested.items():
        pool = set(campaign.pool_members(drum)) - campaign.names_served(drum)
        names = len(pool)
        if names <= 0 or tickets <= 0:
            continue
        at_address: dict[int, int] = defaultdict(int)
        for index in pool:
            at_address[campaign.address_of[index]] += 1
        draws.append((pool, names, tickets, dict(at_address)))

    for index in range(campaign.size()):
        if campaign.stamped_by(index, campaign.as_of) or campaign.ticketed(index):
            continue
        address = campaign.address_of[index]
        no_own = 1.0
        no_address = 1.0
        for pool, names, tickets, at_address in draws:
            if index in pool:
                no_own *= (1.0 - 1.0 / names) ** tickets
            members = at_address.get(address, 0)
            if members:
                no_address *= (1.0 - members / names) ** tickets
        own = 1.0 - no_own
        if campaign.tagged(index):
            total += own * max(0.0, lift - tag_lift)
        else:
            total += own * lift
            total += max(0.0, no_own - no_address) * tag_lift
    return total


def _room_for(before: world.Campaign, drum: str) -> int:
    'The longest run of this drum the mail house would print at this state.'

    room = before.names_left(drum)
    cap = before.ticket_cap(drum)
    if cap is not None:
        room = min(room, cap - before.tickets_used(drum))
    room = min(room, (before.credits_left() // before.price_of(drum)) * 100)
    return max(0, room)


def _least_run(
    before: world.Campaign,
    drum: str,
    want: float,
    room: int,
    rates: tuple[float, float],
) -> int | None:
    'The shortest run of this drum whose expected yield covers `want`.'

    if room <= 0 or expected_new_signups(before, drum, room, rates) < want:
        return None
    low, high = 0, -(-room // 100)
    while high - low > 1:
        middle = (low + high) // 2
        if expected_new_signups(before, drum, min(middle * 100, room), rates) >= want:
            high = middle
        else:
            low = middle
    return min(high * 100, room)


_CHEAPEST: dict[str, tuple[int, list[dict[str, Any]]] | None] = {}


def cheapest_charge(
    spec: Mapping[str, Any], held: Sequence[Mapping[str, Any]]
) -> int | None:
    "What the cheapest plan that reaches this month's target charges."

    found = cheapest_plan(spec, held)
    return None if found is None else found[0]


def cheapest_plan(
    spec: Mapping[str, Any], held: Sequence[Mapping[str, Any]]
) -> tuple[int, list[dict[str, Any]]] | None:
    "The cheapest plan that reaches this month's target, and what it charges."

    key = world.ledger_text(
        [
            {
                "campaign": str(spec["campaign"]),
                "receipt_id": str(item["receipt_id"]),
                "tickets": int(item["tickets"]),
                "drum": str(item["drum"]),
                "sent_on": str(item["sent_on"]),
                "refused": item.get("refused"),
            }
            for item in held
        ]
    ) + f"|{spec['target_activations']}|{spec['credits_granted']}"
    if key in _CHEAPEST:
        return _CHEAPEST[key]

    before = world.build(spec, held)
    rates = planning_rates(before)
    target = target_of(spec)
    shortfall = target - before.activations_by(before.as_of)
    want = shortfall - plan_yield_slack(shortfall)
    if want <= 0:
        _CHEAPEST[key] = (0, [])
        return _CHEAPEST[key]
    drums = [name for name in before.drum_names() if name not in UNSIZEABLE_DRUMS]


    post_on = posting_day(spec, held)

    best: tuple[int, list[dict[str, Any]]] | None = None

    def keep(charge: int, plan: list[dict[str, Any]]) -> None:
        nonlocal best
        if best is None or charge < best[0]:
            best = (charge, plan)

    for drum in drums:
        run = _least_run(before, drum, want, _room_for(before, drum), rates)
        if run is not None:
            keep(
                before.charge_for(drum, run),
                [{"drum": drum, "tickets": run, "send_on": post_on}],
            )

    _CHEAPEST[key] = best
    return best
