'Read one delivered gate-pass readout against the months it is a readout about.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("report.py", "support.py")


SETUP_SECONDS = 60.0
STATE_SECONDS = 30.0
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-spillover-",
    timeout=120.0,
)
_CACHE = AnalysisCache()


def console_seconds(states: int) -> float:
    'What the console allows a notebook asked to run `states` months.'

    return SETUP_SECONDS + STATE_SECONDS * float(max(1, int(states)))

RUBRICS = (
    "ticket_effect_within_tolerance",
    "range_covers_and_meets_floor",
    "effect_invariant_to_counter_lag",
    "booking_reaches_target_at_least_cost",
    "report_reconciles_receipts",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "ticket_effect_within_tolerance": (
        "effect_not_reported",
        "ticket_effect_disagrees",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "range_excludes_reported_effect",
        "range_treats_accounts_as_independent",
        "range_wider_than_the_addresses_support",
        "range_undercovers",
        "candidate_execution_failed",
    ),
    "effect_invariant_to_counter_lag": (
        "effect_not_reported_under_counter_redraw",
        "estimate_tracks_lag",
        "estimate_tracks_backfill",
        "estimate_tracks_the_send_date",
        "candidate_execution_failed",
    ),
    "booking_reaches_target_at_least_cost": (
        "booking_is_not_a_plan_or_a_stop",
        "booking_past_the_cut_off",
        "booking_breaks_estate_cap",
        "booking_over_balance",
        "booking_over_the_drum_pool",
        "booking_misses_target",
        "booking_costs_more_than_the_cheapest",
        "stop_leaves_the_target_short",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "ledger_unreadable",
        "bookings_are_not_a_list",
        "receipt_missing",
        "booking_not_on_the_ledger",
        "booking_reported_twice",
        "booking_drum_disagrees_with_ledger",
        "booking_credits_disagree_with_ledger",
        "refusal_uncounted",
        "duplicate_ticket_counted_as_two_accounts",
        "credits_disagree_with_the_ledger",
        "candidate_execution_failed",
    ),
}

CURRENT_CAMPAIGN = str(workload.CURRENT_SPEC["campaign"])


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _whole_number(value: Any) -> int | None:
    'Read a reported count without silently truncating a fractional value.'

    number = _number(value)
    if number is None or not float(number).is_integer():
        return None
    return int(number)


def _points(value: Any) -> str:
    read = _number(value)
    if read is None:
        return _show(value)
    return format(read, ".2f")


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        _number(item) is not None for item in value
    ):
        return f"{_points(value[0])} to {_points(value[1])}"
    return _show(value)


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        if not value:
            return "no entries at all"
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(spec: Mapping[str, Any]) -> dict[str, str]:
    'The month a failure happened in, in the words the owner uses for it.'

    return {
        "campaign": str(spec["campaign"]),
        "office": str(spec["office"]).replace(" housing office", ""),
        "month": str(spec["first_day"])[:7],
    }


CURRENT_OFFICE = str(workload.CURRENT_SPEC["office"])


def _report_order(record: Mapping[str, Any]) -> tuple[int, int, int]:
    'Put the incident the owner can open her own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign") == CURRENT_CAMPAIGN else 1,
        0 if str(record.get("office")) == CURRENT_OFFICE.replace(" housing office", "")
        else 1,
    )


def live_bookings(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        entries = world.read_ledger(Path(artifact_dir), workload.CURRENT_SPEC)
        return world.bookings_from(entries), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return list(workload.history()), str(exc)


def _shifted_bookings(held: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grown = [dict(item) for item in held]
    for item in grown:
        if item["sent_on"] == "2026-09-18":
            item["sent_on"] = "2026-09-15"
    return grown


def _variant(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    return dict(spec, **changes)


PLAN_MONTHS = (
    workload.FOLLOWING_SPECS[0],
    workload.FOLLOWING_SPECS[1],
    workload.FOLLOWING_SPECS[2],
    workload.FOLLOWING_SPECS[3],
    workload.FOLLOWING_SPECS[4],
    workload.SINGLE_OCCUPANCY_SPEC,
    workload.FRESH_ESTATE_SPEC,
)


def plan_states(
    held: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every month the plan has to answer, this one first.'

    found = list(workload.history())
    states = [
        {
            "label": "as found",
            "spec": workload.CURRENT_SPEC,
            "held": found,
            "base": found,
            "key": CURRENT_CAMPAIGN,
        }
    ]
    for spec in PLAN_MONTHS:
        states.append(
            {
                "label": str(spec["campaign"]),
                "spec": spec,
                "held": workload.booked(spec),
            }
        )
    return states


def report_states(held: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The month under way, three months after it, and the single-occupancy office.'

    rows = [
        {
            "label": "this month",
            "spec": workload.CURRENT_SPEC,
            "held": [dict(item) for item in held],
            "base": list(workload.history()),
            "key": CURRENT_CAMPAIGN,
            "scored": True,
        }
    ]
    for spec in workload.FOLLOWING_SPECS[:3]:
        rows.append(
            {
                "label": str(spec["campaign"]),
                "spec": spec,
                "held": workload.booked(spec),
                "scored": True,
            }
        )
    rows.append(
        {
            "label": "single occupancy",
            "spec": workload.SINGLE_OCCUPANCY_SPEC,
            "held": workload.booked(workload.SINGLE_OCCUPANCY_SPEC),
            "scored": True,
        }
    )
    return rows


def counter_states(held: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "This month's evidence with the nightly counter redrawn three ways."

    base = [dict(item) for item in held]
    return [
        {
            "label": "counter two nights behind",
            "spec": _variant(workload.CURRENT_SPEC, counter_lag=4),
            "held": base,
            "base": list(workload.history()),
            "key": CURRENT_CAMPAIGN,
            "kind": "lag",
        },
        {
            "label": "counter backfilled",
            "spec": _variant(workload.CURRENT_SPEC, counter_backfilled=True),
            "held": base,
            "base": list(workload.history()),
            "key": CURRENT_CAMPAIGN,
            "kind": "backfill",
        },
        {
            "label": "drum posted earlier",
            "spec": workload.CURRENT_SPEC,
            "held": _shifted_bookings(base),
            "base": _shifted_bookings(workload.history()),
            "key": CURRENT_CAMPAIGN + "#earlier",
            "kind": "send",
        },
    ]


def account_lines(campaign: world.Campaign) -> str:
    return "\n".join(
        ",".join(
            (
                campaign.account_ids[index],
                campaign.address_ids[campaign.address_of[index]],
                campaign.estate_of[index],
                campaign.joined_on[index],
            )
        )
        + ","
        for index in range(campaign.size())
    )


def stamp_line(campaign: world.Campaign) -> str:
    return ";".join(campaign.stamp_as_of(index) for index in range(campaign.size()))


def receipt_lines(campaign: world.Campaign, start: int = 0) -> str:
    return "".join(
        f"{row['ticket_id']},{row['receipt_id']},{row['drum_id']},{row['account_id']},{row['sent_on']}\n"
        for row in campaign.ticket_rows[start:]
    )


def counter_text(campaign: world.Campaign) -> str:
    return "".join(f"{row['day']},{row['signups_to_date']}\n" for row in campaign.counter_rows())


class Payload:
    'One batch of notebook requests, with the shared files sent once.'

    def __init__(self) -> None:
        self.campaigns: dict[str, dict[str, Any]] = {}
        self.requests: list[dict[str, Any]] = []
        self._base: dict[str, int] = {}

    def key_for(self, key: str, base: world.Campaign) -> str:
        if key not in self.campaigns:
            self.campaigns[key] = {
                "accounts": account_lines(base),
                "receipts": receipt_lines(base),
            }
            self._base[key] = len(base.ticket_rows)
        return key

    def add(
        self,
        kind: str,
        spec: Mapping[str, Any],
        held: Sequence[Mapping[str, Any]],
        base_held: Sequence[Mapping[str, Any]] | None = None,
        key: str | None = None,
        campaign: world.Campaign | None = None,
        base: world.Campaign | None = None,
    ) -> int:
        campaign = campaign if campaign is not None else world.build(spec, held)
        if base is None:
            base = world.build(
                spec, base_held if base_held is not None else held
            )
        key = self.key_for(key or campaign.campaign, base)
        self.requests.append(
            {
                "kind": kind,
                "campaign": key,
                "context": campaign.context(),
                "stamps": stamp_line(campaign),
                "receipts_extra": receipt_lines(campaign, self._base[key]),
                "counter": counter_text(campaign),
                "ledger": world.ledger_text(world.sealed_ledger(spec, held)),
            }
        )
        return len(self.requests) - 1

    def body(self) -> dict[str, Any]:
        return {"campaigns": self.campaigns, "requests": self.requests}


def _effect_failures(
    campaign: world.Campaign, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    truth = oracle.ticket_effect(campaign)
    reported = report.get("ticket_effect_points")
    counters = campaign.counter_rows()
    shared = {
        **_where(campaign.spec),
        "reported": _points(reported),
        "counter_total": int(counters[-1]["signups_to_date"]) if counters else 0,
        "register_total": campaign.activations_by(campaign.as_of),
        "untouched_accounts": len(campaign.indices_at_untouched_addresses()),
        "shared_addresses": len(campaign.lifted_neighbour_indices()),
    }
    if _number(reported) is None:
        return [_fail("effect_not_reported", **shared)]
    if abs(float(reported) - truth) <= oracle.TOLERANCE:
        return []
    return [_fail("ticket_effect_disagrees", **shared)]


def _range_shape(
    campaign: world.Campaign, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    published = report.get("effect_range_points")
    supported = oracle.supported_half_width(campaign)
    shared = {
        **_where(campaign.spec),
        "reported_range": _pair(published),
        "untouched_accounts": len(campaign.indices_at_untouched_addresses()),
        "addresses_behind_it": len(
            {campaign.address_of[index] for index in campaign.ticketed_indices()}
        ),
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [_fail("range_is_not_an_interval", **shared, reported=_show(published))]
    reported = _number(report.get("ticket_effect_points"))
    if reported is not None and not float(published[0]) <= reported <= float(published[1]):
        return [
            _fail(
                "range_excludes_reported_effect",
                **shared,
                reported=_points(reported),
            )
        ]
    width = float(published[1]) - float(published[0])
    required = 2.0 * supported
    if width < required * oracle.RANGE_FLOOR:
        return [_fail("range_treats_accounts_as_independent", **shared)]
    if width > required * oracle.RANGE_CEILING:
        return [_fail("range_wider_than_the_addresses_support", **shared)]
    return []


def _range_covers(campaign: world.Campaign, report: Mapping[str, Any]) -> bool | None:
    published = report.get("effect_range_points")
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
    ):
        return None
    lift = oracle.parameter_lift(campaign)
    return float(published[0]) <= lift <= float(published[1])


def _plan_failures(
    spec: Mapping[str, Any], held: Sequence[Mapping[str, Any]], answer: Any
) -> list[dict[str, Any]]:
    campaign = world.build(spec, held)
    target = oracle.target_of(spec)
    standing = campaign.activations_by(campaign.as_of)
    shared = {
        **_where(spec),
        "target": target,
        "signups_so_far": standing,
        "credits_left": campaign.credits_left(),
        "cut_off": campaign.cut_off,
        "estate_cap": int(spec["estate_ticket_cap"]),
        "reported": _show(answer),
    }
    if isinstance(answer, str) and answer.strip().lower() == "stop":
        if standing >= target:
            return []
        return [_fail("stop_leaves_the_target_short", **shared)]
    plan = oracle.plan_bookings(answer)
    if plan is None:
        return [_fail("booking_is_not_a_plan_or_a_stop", **shared)]
    asked_tickets = sum(int(item["tickets"]) for item in plan)
    shared["reported"] = ", ".join(
        f"{int(item['tickets'])} tickets on {item['drum']}" for item in plan
    )
    shared["tickets_asked"] = asked_tickets
    _campaign, grown, refused, booking = oracle.apply_plan(spec, held, plan)
    if refused is not None:
        asked = dict(booking or {})
        shared["drum_asked"] = str(asked.get("drum"))
        shared["tickets_asked"] = int(asked.get("tickets") or 0)
        shared["send_on"] = str(asked.get("send_on") or campaign.as_of)
        mode = {
            world.REFUSAL_PAST_CUT_OFF: "booking_past_the_cut_off",
            world.REFUSAL_OVER_CAP: "booking_breaks_estate_cap",
            world.REFUSAL_OVER_POOL: "booking_over_the_drum_pool",
            world.REFUSAL_OVER_BALANCE: "booking_over_balance",
            world.REFUSAL_NO_DRUM: "booking_is_not_a_plan_or_a_stop",
        }[refused]
        return [_fail(mode, **shared, refusal=str(refused))]


    reached = oracle.expected_activations(spec, held, plan)
    charge = oracle.plan_charge(spec, held, grown)
    landed: set[int] = set()
    for item in world.build(spec, grown).reached[len(held):]:
        landed |= set(item)
    shared["charge"] = charge
    shared["signups_reached"] = int(round(reached))
    shared["accounts_reached"] = len(landed)
    if reached < target - oracle.plan_yield_slack(target - standing):
        return [_fail("booking_misses_target", **shared)]
    cheapest = oracle.cheapest_charge(spec, held)
    if cheapest is not None and charge > oracle.CHARGE_CEILING * cheapest:
        return [_fail("booking_costs_more_than_the_cheapest", **shared)]
    return []


def _ledger_failures(
    campaign: world.Campaign,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    ledger_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(campaign.spec)
    if ledger_error:
        return [_fail("ledger_unreadable", **where, reason=str(ledger_error))]
    rows = report.get("bookings")
    billed = {str(entry["receipt_id"]): entry for entry in entries}
    shared = {**where, "bookings_on_the_ledger": len(entries)}
    if not isinstance(rows, list):
        return [_fail("bookings_are_not_a_list", **shared, reported=_show(rows))]
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [_fail("bookings_are_not_a_list", **shared, reported=_show(row))]
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [_fail("booking_reported_twice", **shared, receipt_id=key,
                          times_reported=seen[key])]
        entry = billed.get(key)
        if entry is None:
            return [_fail("booking_not_on_the_ledger", **shared, receipt_id=key,
                          reported_tickets=_show(row.get("tickets_charged")))]
        reported_drum = row.get("drum")
        if not isinstance(reported_drum, str) or reported_drum != str(entry["drum"]):
            return [_fail("booking_drum_disagrees_with_ledger", **shared,
                          receipt_id=key, reported_drum=_show(reported_drum),
                          ledger_drum=str(entry["drum"]))]
        reported_line_credits = _whole_number(row.get("credits_charged"))
        if reported_line_credits != int(entry["credits_charged"]):
            return [_fail("booking_credits_disagree_with_ledger", **shared,
                          receipt_id=key,
                          reported_credits=_show(row.get("credits_charged")),
                          ledger_credits=int(entry["credits_charged"]))]
        tickets = _whole_number(row.get("tickets_charged"))
        accounts = _whole_number(row.get("accounts_reached"))
        if tickets is None or int(tickets) != int(entry["tickets_printed"]):
            if entry.get("refused"):
                return [_fail("refusal_uncounted", **shared, receipt_id=key,
                              reported_tickets=_show(row.get("tickets_charged")),
                              ledger_tickets=int(entry["tickets_printed"]),
                              ledger_accounts=int(entry["accounts_reached"]),
                              credits_charged=int(entry["credits_charged"]))]
            return [_fail("duplicate_ticket_counted_as_two_accounts", **shared,
                          receipt_id=key,
                          reported_tickets=_show(row.get("tickets_charged")),
                          ledger_tickets=int(entry["tickets_printed"]),
                          ledger_accounts=int(entry["accounts_reached"]),
                          credits_charged=int(entry["credits_charged"]))]
        if accounts is None or int(accounts) != int(entry["accounts_reached"]):
            return [_fail("duplicate_ticket_counted_as_two_accounts", **shared,
                          receipt_id=key,
                          reported_tickets=_show(row.get("accounts_reached")),
                          ledger_tickets=int(entry["tickets_printed"]),
                          ledger_accounts=int(entry["accounts_reached"]),
                          credits_charged=int(entry["credits_charged"]))]
    for key, entry in billed.items():
        if key not in seen:
            mode = "refusal_uncounted" if entry.get("refused") else "receipt_missing"
            return [_fail(mode, **shared, receipt_id=key,
                          credits_charged=int(entry["credits_charged"]),
                          reported_tickets=_show(None),
                          ledger_tickets=int(entry["tickets_printed"]),
                          ledger_accounts=int(entry["accounts_reached"]))]
    ledger_credits = sum(int(entry["credits_charged"]) for entry in entries)
    reported_credits = _whole_number(report.get("credits_charged"))
    if reported_credits != ledger_credits:
        return [_fail("credits_disagree_with_the_ledger", **shared,
                      reported_credits=_show(report.get("credits_charged")),
                      ledger_credits=ledger_credits)]
    tickets_total = sum(int(entry["tickets_printed"]) for entry in entries)
    accounts_total = sum(int(entry["accounts_reached"]) for entry in entries)
    reported_tickets = _whole_number(report.get("tickets_charged"))
    reported_accounts = _whole_number(report.get("accounts_reached"))
    if reported_tickets != tickets_total:
        return [_fail("duplicate_ticket_counted_as_two_accounts", **shared,
                      receipt_id="the month's total",
                      reported_tickets=_show(report.get("tickets_charged")),
                      ledger_tickets=tickets_total, ledger_accounts=accounts_total,
                      credits_charged=ledger_credits)]
    if reported_accounts != accounts_total:
        return [_fail("duplicate_ticket_counted_as_two_accounts", **shared,
                      receipt_id="the month's total",
                      reported_tickets=_show(report.get("accounts_reached")),
                      ledger_tickets=tickets_total, ledger_accounts=accounts_total,
                      credits_charged=ledger_credits)]
    return []


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (
            "it was still running after "
            f"{reported[len(_TIMEOUT_PHRASE):].strip()} and the console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the readout notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every month and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        held, ledger_error = live_bookings(Path(artifact_dir))
        payload = Payload()
        def enqueue(kind: str, row: Mapping[str, Any]) -> int:
            return payload.add(
                kind, row["spec"], row["held"], row.get("base"), row.get("key")
            )

        reports = [(row, enqueue("report", row)) for row in report_states(held)]
        counters = [(row, enqueue("report", row)) for row in counter_states(held)]
        plans = [(row, enqueue("plan", row)) for row in plan_states(held)]

        run = PROJECT.invoke(
            Path(artifact_dir),
            payload.body(),
            timeout=console_seconds(len(payload.requests)),
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            location = {
                **_where(workload.CURRENT_SPEC),
                "request_label": "the review batch",
            }
            for bucket in BUCKETS.values():
                analysis[bucket] = [
                    {**dict(record), **location}
                    for record in analysis.get(bucket, ())
                ]
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CURRENT_CAMPAIGN, "bookings_paid_for": len(held)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the months"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        cover: list[tuple[world.Campaign, bool, Mapping[str, Any]]] = []
        for row, index in reports:
            campaign = world.build(row["spec"], row["held"])
            value, error = answer(index)
            if error is not None:
                stopped = True
                for bucket in ("ticket_effect_within_tolerance", "range_covers_and_meets_floor",
                               "report_reconciles_receipts"):
                    failures[bucket].append(
                        _fail(
                            CANDIDATE_FAILURE,
                            **_where(row["spec"]),
                            request_label=str(row["label"]),
                            error=error,
                        )
                    )
                continue
            report = dict(value or {})
            failures["ticket_effect_within_tolerance"].extend(
                _effect_failures(campaign, report)
            )
            shape = _range_shape(campaign, report)
            failures["range_covers_and_meets_floor"].extend(shape)
            if not shape:
                covered = _range_covers(campaign, report)
                cover.append((campaign, bool(covered), report))
            entries = world.sealed_ledger(row["spec"], row["held"])
            failures["report_reconciles_receipts"].extend(
                _ledger_failures(
                    campaign, entries, report,
                    ledger_error if campaign.campaign == CURRENT_CAMPAIGN else None,
                )
            )
        if cover:
            missed = [(campaign, report) for campaign, ok, report in cover if not ok]
            if len(missed) > (1.0 - oracle.COVERAGE_MIN) * len(cover):
                for campaign, report in missed:
                    failures["range_covers_and_meets_floor"].append(
                        _fail(
                            "range_undercovers",
                            **_where(campaign.spec),
                            reported_range=_pair(report.get("effect_range_points")),
                            reported=_points(report.get("ticket_effect_points")),
                            untouched_accounts=len(campaign.indices_at_untouched_addresses()),
                            addresses_behind_it=len(
                                {campaign.address_of[index]
                                 for index in campaign.ticketed_indices()}
                            ),
                            months_missed=len(missed),
                            months_read=len(cover),
                        )
                    )

        readings: list[tuple[str, float]] = []
        base_report, base_index = reports[0]
        value, error = answer(base_index)
        comparisons_complete = error is None
        if error is None:
            filed = _number(dict(value or {}).get("ticket_effect_points"))
            if filed is not None:
                readings.append(("as filed", filed))
            else:
                comparisons_complete = False
        for row, index in counters:
            value, error = answer(index)
            if error is not None:
                stopped = True
                comparisons_complete = False
                failures["effect_invariant_to_counter_lag"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        **_where(row["spec"]),
                        request_label=str(row["label"]),
                        error=error,
                    )
                )
                continue
            reported = dict(value or {}).get("ticket_effect_points")
            reading = _number(reported)
            if reading is None:
                comparisons_complete = False
                failures["effect_invariant_to_counter_lag"].append(
                    _fail(
                        "effect_not_reported_under_counter_redraw",
                        **_where(row["spec"]),
                        variant=str(row["label"]),
                        reported=_show(reported),
                    )
                )
                continue
            readings.append((str(row["kind"]), reading))
        known = dict(readings)
        if comparisons_complete and len(known) > 1:
            spread = max(known.values()) - min(known.values())
            if spread > oracle.INVARIANCE:
                filed = known.get("as filed")
                shared = {
                    **_where(workload.CURRENT_SPEC),
                    "reported": _points(filed),
                    "moved_by": _points(spread),
                }
                if filed is not None and abs(known.get("lag", filed) - filed) > oracle.INVARIANCE:
                    mode = "estimate_tracks_lag"
                    shared["redrawn"] = _points(known.get("lag"))
                elif filed is not None and abs(known.get("backfill", filed) - filed) > oracle.INVARIANCE:
                    mode = "estimate_tracks_backfill"
                    shared["redrawn"] = _points(known.get("backfill"))
                else:
                    mode = "estimate_tracks_the_send_date"
                    shared["redrawn"] = _points(known.get("send"))
                failures["effect_invariant_to_counter_lag"].append(_fail(mode, **shared))

        for row, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                failures["booking_reaches_target_at_least_cost"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        **_where(row["spec"]),
                        request_label=str(row["label"]),
                        error=error,
                    )
                )
                continue
            failures["booking_reaches_target_at_least_cost"].extend(
                _plan_failures(row["spec"], row["held"], value)
            )

        analysis: dict[str, Any] = {
            rubric: sorted(records, key=_report_order)
            for rubric, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT_CAMPAIGN,
            "bookings_paid_for": len(held),
            "months_read": len(reports),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "receipt_id", "drum", "sent_on", "tickets_requested", "tickets_printed",
            "accounts_reached", "refused", "credits_charged", "credits_left",
        )
    }


def starting_ledger() -> str:
    return world.ledger_text(
        world.sealed_ledger(workload.CURRENT_SPEC, workload.history())
    )


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    held, error = live_bookings(root)
    campaign = world.build(workload.CURRENT_SPEC, held)
    context = campaign.context()
    entries = world.sealed_ledger(workload.CURRENT_SPEC, held)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_day")},
            }
        )
    return {
        "summary": (
            f"The {context['campaign']} gate-pass campaign, its drums and the working "
            "records on file."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "office": context["office"],
            "window": context["window"],
            "as_of": context["as_of"],
            "target": context["target"],
            "account": context["account"],
            "mail_house": context["mail_house"],
            "drums": context["drums"],
            "bookings_on_the_ledger": [_receipt_summary(entry) for entry in entries],
            "ledger": error or "reads back in order",
            "register_rows": campaign.size(),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def replayed_month(record: Mapping[str, Any]) -> world.Campaign:
    'The month as the office held it on the day that record was written.'

    return workload.current().as_at(str(record["through_day"]))


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    through = str(record["through_day"])
    spec = workload.CURRENT_SPEC
    campaign = replayed_month(record)
    held = list(campaign.bookings)
    payload = Payload()
    first = payload.add("report", spec, held, campaign=campaign, base=campaign)
    second = payload.add("plan", spec, held, campaign=campaign, base=campaign)
    run = PROJECT.invoke(
        Path(artifact_dir),
        payload.body(),
        timeout=console_seconds(len(payload.requests)),
    )
    stamps = [stamp for stamp in campaign.activated_at if stamp is not None]
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through": through,
        "counter_rows": campaign.counter_rows()[-6:],
        "register_stamps_by_day": [
            {"day": day, "signups_stamped": sum(1 for stamp in stamps if stamp == day)}
            for day in campaign.days
            if day <= through
        ][-6:],
        "bookings_on_the_ledger": [
            _receipt_summary(entry)
            for entry in world.sealed_ledger(spec, held)
        ],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "campaign": campaign.campaign},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": campaign.campaign,
            "evidence_through": through,
        },
        "public": {
            "session": session,
            "readout_returned": results[first] if len(results) > first else None,
            "next_collection_returned": results[second] if len(results) > second else None,
            "stdout": run.get("stdout"),
        },
    }


def run_booking(
    artifact_dir: Path, drum: Any, tickets: Any, send_on: Any, receipt_id: Any
) -> Mapping[str, Any]:
    return world.collect(
        Path(artifact_dir), workload.CURRENT_SPEC, drum, tickets, send_on, receipt_id
    )
