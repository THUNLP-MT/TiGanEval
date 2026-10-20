'Read one delivered desk notebook against the world it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w
from .runtime_driver import FLAG_COLUMNS, STATE_COLUMNS


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-grace-policy-",
    timeout=120.0,
)
_CACHE = AnalysisCache()

DESK = workload.CURRENT.desk

BUCKETS: Mapping[str, str] = {
    "policy_difference_within_tolerance": "cost_failures",
    "range_covers_and_meets_floor": "range_failures",
    "estimate_invariant_to_queue_and_censoring": "stability_failures",
    "next_week_booking_feasible_and_informative": "plan_failures",
    "report_reconciles_receipts": "receipt_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "policy_difference_within_tolerance": (
        "includes_unstartable_flags",
        "groups_by_actual_start",
        "ignores_routing_composition",
        "policy_difference_disagrees",
        "difference_wrong_on_another_desk",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_absent",
        "range_excludes_reported_point",
        "account_days_absent",
        "account_days_disagree",
        "range_below_floor",
        "range_wider_than_the_evidence",
        "range_undercovers",
        "range_wrong_on_another_desk",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_queue_and_censoring": (
        "estimate_absent",
        "hardcoded_history",
        "moves_with_slot_delay",
        "moves_with_migration_date",
        "candidate_execution_failed",
    ),
    "next_week_booking_feasible_and_informative": (
        "collected_week_was_refused",
        "plan_is_not_a_booking_or_a_stop",
        "booking_over_cap",
        "booking_segment_empty",
        "booking_single_policy",
        "stopped_with_slots_still_granted",
        "booking_uninformative",
        "booking_wrong_on_another_desk",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "weeks_are_not_a_ledger",
        "week_not_on_the_receipts",
        "week_counted_twice",
        "receipt_missing",
        "refusal_uncounted",
        "receipts_wrong_on_another_desk",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "cost_failures": ("difference_wrong_on_another_desk",),
    "range_failures": ("range_wrong_on_another_desk",),
    "plan_failures": ("booking_wrong_on_another_desk",),
    "receipt_failures": ("receipts_wrong_on_another_desk",),
}


_NAMING_ORDER: tuple[str, ...] = tuple(
    world.desk
    for world in (*workload.SIBLINGS, *workload.PARTNERS, workload.OUT_OF_REGIME)
)


def _naming_rank(desk: str) -> int:
    return _NAMING_ORDER.index(desk) if desk in _NAMING_ORDER else len(_NAMING_ORDER)


CARRIED_OVER_DESKS: tuple[str, ...] = tuple(
    sorted(
        (
            world.desk
            for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME, *workload.PARTNERS)
            if abs(oracle.truth(workload.CURRENT) - oracle.truth(world))
            > oracle.CARRIED_OVER_GAP
        ),
        key=_naming_rank,
    )
)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident the desk lead can open the ledger for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("desk") == DESK else 1,
    )


def _written_off_the_live_desk(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported from evidence the lead can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("desk") == DESK
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    named = min(
        (record for record in rows if record.get("desk")),
        key=lambda record: _naming_rank(str(record["desk"])),
        default=rows[0],
    )
    elsewhere = sorted({str(record["desk"]) for record in rows if record.get("desk")})
    carried = {
        "desk": DESK,
        "other_desk": str(named.get("desk")),
        "other_desks": len(elsewhere),
    }
    if "slots_left" in named:
        carried["slots_left"] = named["slots_left"]
    return [_fail(modes[0], **carried)]


def _points(value: Any) -> str:
    return format(float(value), ".2f")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_points(value[0])} to {_points(value[1])}"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The weeks this delivery has paid for, or why the stream will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def live_world(entries: Sequence[Mapping[str, Any]]) -> w.World:
    'The desk as it stands after every week the receipts say was served.'

    calls = w.bookings_of(entries, len(workload.HISTORY_CALLS))
    served = [*workload.CURRENT_SPEC["bookings"], *calls]
    return w.booked(workload.CURRENT_BASE, served)


def burn_state(
    entries: Sequence[Mapping[str, Any]], target_left: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    'The receipts after served weeks leave exactly ``target_left`` slots.'

    base = workload.CURRENT
    grown = [dict(entry) for entry in entries]
    made = [
        *workload.CURRENT_SPEC["bookings"],
        *w.bookings_of(entries, len(workload.HISTORY_CALLS)),
    ]
    cap = float(base.spec["hold_cap"])
    per_week = int(base.spec["slots_per_week"])
    target = int(target_left)
    left = base.slots_left(grown)
    if target < 0 or target > left:
        raise ValueError("target slots must sit between zero and the current balance")
    while base.slots_left(grown) > target:
        slots = min(per_week, base.slots_left(grown) - target)
        call = {"segment": "all", "hold_share": cap, "slots": slots, "accepted": True}
        made.append(call)
        grown.append(
            w.receipt(
                base, f"burn-{len(grown) + 1:02d}", len(grown), "all", cap, slots,
                slots, 0, 0, "", len(grown) + 1, grown[-1]["seal"] if grown else "",
            )
        )
    return grown, made


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The desk under review, then the ones the same notebook is used on next.'

    calls = w.bookings_of(entries, len(workload.HISTORY_CALLS))
    served = [*workload.CURRENT_SPEC["bookings"], *calls]
    live = w.booked(workload.CURRENT_BASE, served)
    opening = workload.opening_receipts(workload.CURRENT)
    balances = []
    for target in (30, 20, 10, 0):
        receipts, bookings = burn_state(opening, target)
        balances.append(
            {
                "base": workload.CURRENT_BASE,
                "bookings": bookings,
                "world": w.booked(workload.CURRENT_BASE, bookings),
                "receipts": receipts,
            }
        )
    rows: list[dict[str, Any]] = [
        {
            "label": live.desk,
            "world": live,
            "receipts": [dict(item) for item in entries],
            "plans": [
                {"base": workload.CURRENT_BASE, "bookings": served, "world": live,
                 "receipts": [dict(item) for item in entries]},
                *balances,
            ],
        }
    ]
    for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME, *workload.PARTNERS):
        receipts = workload.opening_receipts(world)
        rows.append(
            {
                "label": world.desk,
                "world": world,
                "receipts": receipts,
                "plans": [
                    {
                        "base": workload.BASES[world.desk],
                        "bookings": list(world.spec["bookings"]),
                        "world": world,
                        "receipts": receipts,
                    }
                ],
            }
        )
    return rows


def compact(context: Mapping[str, Any]) -> dict[str, Any]:
    'The same desk, with the two long tables sent as columns and rows.'

    out = dict(context)
    for key, columns in (("flags", FLAG_COLUMNS), ("account_states", STATE_COLUMNS)):
        out[key] = {
            "columns": list(columns),
            "rows": [[row.get(name) for name in columns] for row in context[key]],
        }
    return out


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(0, _fail(CANDIDATE_FAILURE, error=error))


_MISREADINGS = (
    ("includes_unstartable_flags", ("unstartable",)),
    ("groups_by_actual_start", ("naive", "naive_weighted", "clock_from_start")),
    ("ignores_routing_composition", ("pooled", "campaign_weighted")),
)


def _reads_like(
    world: w.World, family: str, value: Any, declared: Any
) -> bool:
    "Whether one desk's answer is this wrong method's, on both of its numbers."

    if not _near(value, oracle.misreadings(world)[family], oracle.CLASSIFY_SLACK):
        return False
    wanted = oracle.misreading_account_days(world)[family]
    counted = _number(declared)
    if wanted is None or wanted <= 0 or counted is None:
        return True
    return abs(counted - wanted) <= oracle.FAMILY_DAYS_SLACK * wanted


def explanation(
    readings: Mapping[str, float],
    days: Mapping[str, Any],
    worlds: Mapping[str, w.World],
) -> str | None:
    'The one misreading that accounts for this delivery on most of the desks.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = sum(
            1
            for desk, value in readings.items()
            if desk in worlds
            and any(
                _reads_like(worlds[desk], family, value, days.get(desk))
                for family in families
            )
        )
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _check_cost(
    review: Review, world: w.World, report: Mapping[str, Any], mode: str | None
) -> None:
    truth = oracle.truth(world)


    evidence = workload.BASES.get(world.desk, world)
    reported = report.get("cost_points")
    if _near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "desk": world.desk,
        "reported_points": (
            _points(reported) if _number(reported) is not None else _show(reported)
        ),
    }
    if _number(reported) is None or mode is None:
        review.add("cost_failures", "policy_difference_disagrees", **shared,
                   flags_on_the_ledger=len(evidence.flags))
        return
    if mode == "includes_unstartable_flags":
        review.add("cost_failures", mode, **shared,
                   unstartable=_unstartable(evidence),
                   flags_on_the_ledger=len(evidence.flags))
        return
    if mode == "groups_by_actual_start":
        review.add("cost_failures", mode, **shared,
                   never_started=_never_started(evidence),
                   grace_window_days=int(evidence.spec["grace_window_days"]))
        return
    review.add("cost_failures", mode, **shared,
               book_counted_on=str(world.spec["book_counted_on"]),
               accounts_on_the_book=sum(int(value) for value in world.spec["book"].values()))


def _unstartable(world: w.World) -> int:
    return sum(1 for row in oracle.prepared(world) if row["state"] != "active")


def _never_started(world: w.World) -> int:
    return sum(
        1
        for row in oracle.prepared(world)
        if row["queue"] == "next_slot" and row["waited"] is None
    )


def _check_range(review: Review, world: w.World, report: Mapping[str, Any]) -> bool:
    'The range the account-days behind it support. Returns whether the truth is held.'

    reported = report.get("cost_range_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or reported[0] > reported[1]
    ):
        review.add("range_failures", "range_absent", desk=world.desk,
                   reported=_pair(reported))
        return True
    reported_point = _number(report.get("cost_points"))
    if reported_point is not None and not (
        float(reported[0]) <= reported_point <= float(reported[1])
    ):
        review.add(
            "range_failures", "range_excludes_reported_point", desk=world.desk,
            reported_points=_show(reported_point),
            reported_range=(
                f"{_show(float(reported[0]))} to {_show(float(reported[1]))}"
            ),
        )


    evidence = workload.BASES.get(world.desk, world)
    actual_days = oracle.account_days(evidence)
    declared_days = _number(report.get("account_days"))
    width = (float(reported[1]) - float(reported[0])) / 2.0
    fields = {
        "desk": world.desk,
        "reported_range": _pair(reported),
        "reported_account_days": _show(report.get("account_days")),
    }
    if declared_days is None:
        review.add("range_failures", "account_days_absent", **fields)
        return float(reported[0]) <= oracle.truth(world) <= float(reported[1])
    if abs(declared_days - actual_days) > oracle.ACCOUNT_DAYS_SLACK:
        review.add(
            "range_failures", "account_days_disagree", **fields,
            account_days_gap=_show(abs(declared_days - actual_days)),
        )
        return float(reported[0]) <= oracle.truth(world) <= float(reported[1])
    supported = oracle.half_width(evidence)
    if width < supported * oracle.NARROW_FACTOR:
        review.add("range_failures", "range_below_floor", **fields)
    elif width > supported * oracle.WIDE_FACTOR:
        review.add("range_failures", "range_wider_than_the_evidence", **fields)
    truth = oracle.truth(world)
    return float(reported[0]) <= truth <= float(reported[1])


def _check_receipts(
    review: Review,
    world: w.World,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    error: str | None,
) -> None:
    if error:
        review.add("receipt_failures", "receipts_unreadable", desk=world.desk,
                   reason=str(error))
        return
    rows = report.get("weeks")
    if not isinstance(rows, list):
        review.add("receipt_failures", "weeks_are_not_a_ledger", desk=world.desk,
                   reported=_show(rows), charged=len(receipts))
        return
    billed = {str(item["receipt_id"]): item for item in receipts}
    seen: dict[str, int] = {}
    for row in rows:
        receipt_id = str(row.get("receipt_id"))
        seen[receipt_id] = seen.get(receipt_id, 0) + 1
        if seen[receipt_id] > 1:
            review.add("receipt_failures", "week_counted_twice", desk=world.desk,
                       receipt_id=receipt_id, times_reported=seen[receipt_id])
            return
        entry = billed.get(receipt_id)
        if entry is None or not all(
            _near(row.get(field), float(entry[field]), 0.0)
            for field in ("slots_charged", "rows_returned")
        ):
            review.add("receipt_failures", "week_not_on_the_receipts", desk=world.desk,
                       receipt_id=receipt_id, charged=len(receipts))
            return
    for receipt_id, entry in billed.items():
        if receipt_id in seen:
            continue
        mode = "refusal_uncounted" if str(entry.get("refusal")) else "receipt_missing"
        review.add("receipt_failures", mode, desk=world.desk, receipt_id=receipt_id,
                   slots_charged=int(entry["slots_charged"]), charged=len(receipts))
        return


def _check_plan(
    review: Review,
    base: w.World,
    bookings: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    answer: Any,
) -> None:
    spec = base.spec
    left = base.slots_left(receipts)
    state = oracle.plan_state(base, bookings, left)
    shared = {
        "desk": base.desk,
        "slots_left": left,
        "slots_per_week": int(spec["slots_per_week"]),
        "hold_cap_pct": int(round(float(spec["hold_cap"]) * 100)),
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                   reported=_show(answer))
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not state["stop_only"]:
                review.add("plan_failures", "stopped_with_slots_still_granted", **shared,
                           smallest_week_slots=int(spec["smallest_week_slots"]))
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(choice))
            return
        segment = choice.get("segment", "all")
        hold = _number(choice.get("hold_share"))
        slots = _number(choice.get("slots"))
        if (
            not isinstance(segment, str)
            or hold is None or slots is None
            or slots != int(slots) or slots < 1
            or hold < 0.0 or hold > 1.0
        ):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(
                           f"{_show(choice.get('segment'))} at "
                           f"{_show(choice.get('hold_share'))} for "
                           f"{_show(choice.get('slots'))} slots"
                       ))
            return
        slots = int(slots)
        call = {"segment": segment, "hold_share": hold, "slots": slots}
        named = {**shared, "segment": segment,
                 "hold_pct": int(round(hold * 100)), "slots": slots}
        broken = oracle.is_over_cap(base, call, left)
        if broken:
            review.add("plan_failures", "booking_over_cap", **named, over=broken)
            return
        rows = oracle.week_rows(base, bookings, call)
        if rows <= 0:
            review.add("plan_failures", "booking_segment_empty", **named)
            return
        if hold <= 0.0 or hold >= 1.0:
            review.add("plan_failures", "booking_single_policy", **named)
            return


        if state["stop_only"] or slots < oracle.full_week(base, left) or (
            oracle.half_width_after(base, bookings, call)
            >= state["bar"] - oracle.NARROWING_EPSILON
        ):


            hers = oracle.owners_week(base, left)
            review.add(
                "plan_failures", "booking_uninformative", **named,
                owners_segment=str(hers["segment"]),
                owners_hold_pct=int(round(float(hers["hold_share"]) * 100)),
                owners_slots=int(hers["slots"]),
                review_bar_points=int(round(float(spec["review_bar_points"]))),
            )
            return


def _check_live_bookings(
    review: Review,
    base: w.World,
    receipts: Sequence[Mapping[str, Any]],
) -> None:
    'Keep an irreversible handed-back call in the delivered project state.'

    for entry in list(receipts)[len(workload.HISTORY_CALLS):]:
        reason = str(entry.get("refusal", ""))
        charged = int(entry.get("slots_charged", 0))
        if not reason or charged <= 0:
            continue
        review.add(
            "plan_failures", "collected_week_was_refused", desk=base.desk,
            receipt_id=str(entry.get("receipt_id", "")),
            segment=str(entry.get("segment", "all")),
            slots_asked=int(entry.get("slots_asked", 0)),
            slots_charged=charged,
            refusal=reason,
        )
        return


def _check_stability(
    review: Review, readings: Mapping[str, float], live: float | None
) -> None:
    'What the same window says twice over, read off the state the reissues are in.'

    if live is None:
        review.add(
            "stability_failures", "estimate_absent", desk=DESK, reported="empty"
        )
        return
    values = [readings.get(desk) for desk in CARRIED_OVER_DESKS]
    if CARRIED_OVER_DESKS and all(
        value is not None and abs(live - value) < 1e-6 for value in values
    ):
        review.add("stability_failures", "hardcoded_history", desk=DESK,
                   other_desk=CARRIED_OVER_DESKS[0], reported_points=_points(live))
        return
    for mode, partner in (
        ("moves_with_slot_delay", workload.QUEUE_PARTNER),
        ("moves_with_migration_date", workload.EXPORT_PARTNER),
    ):
        value = readings.get(partner.desk)
        if value is None:
            continue
        if abs(live - value) > oracle.INVARIANCE_SLACK:
            review.add(
                "stability_failures",
                mode,
                desk=DESK,
                other_desk=partner.desk,
                reported_points=_points(live),
                other_points=_points(value),
                moved_by=_points(abs(live - value)),
            )
            return


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
    return f"the desk notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every desk and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipt_error = live_receipts(Path(artifact_dir))
        rows = instances(entries)
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(world: w.World) -> int:
            if id(world) not in seen:
                seen[id(world)] = len(contexts)
                contexts.append(compact(world.context()))
            return seen[id(world)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[Mapping[str, Any], int]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "receipts": row["receipts"]}
            )
            for state in row["plans"]:
                plans.append((state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": context_index(state["world"]),
                     "receipts": state["receipts"]}
                )


        frozen_index = len(requests)
        requests.append(
            {
                "kind": "report",
                "context": context_index(workload.CURRENT),
                "receipts": workload.opening_receipts(workload.CURRENT),
            }
        )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"desk": DESK, "weeks_charged": len(entries)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the desks"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        _check_live_bookings(review, workload.CURRENT_BASE, entries)
        readings: dict[str, float] = {}
        declared: dict[str, Any] = {}
        worlds: dict[str, w.World] = {}
        for row, index in reports:
            value, _error = answer(index)
            reading = _number(dict(value or {}).get("cost_points")) if value else None
            if reading is not None:
                readings[row["world"].desk] = reading
                declared[row["world"].desk] = dict(value or {}).get("account_days")
                worlds[row["world"].desk] = row["world"]
        mode = explanation(readings, declared, worlds)
        held: list[bool] = []
        stopped = False
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("cost_failures", "range_failures", "receipt_failures",
                     "stability_failures"),
                    error,
                )
                continue
            report = dict(value or {})
            _check_cost(review, world, report, mode)
            held.append(_check_range(review, world, report))
            _check_receipts(
                review, world, report, row["receipts"],
                receipt_error if world.desk == DESK else None,
            )
        for state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            _check_plan(review, state["base"], state["bookings"], state["receipts"], value)
        if held and sum(held) < oracle.COVERAGE * len(held):
            for row, index in reports:
                value, error = answer(index)
                if error is not None:
                    continue
                reported = dict(value or {}).get("cost_range_points")
                truth = oracle.truth(row["world"])
                if (
                    isinstance(reported, list)
                    and len(reported) == 2
                    and all(_number(item) is not None for item in reported)
                    and not (float(reported[0]) <= truth <= float(reported[1]))
                ):
                    review.add(
                        "range_failures",
                        "range_undercovers",
                        desk=row["world"].desk,
                        reported_range=_pair(reported),
                        desks_reviewed=len(held),
                        desks_held=sum(held),
                    )
        frozen, frozen_error = answer(frozen_index)
        if frozen_error is not None:
            review.failures["stability_failures"].append(
                _fail(CANDIDATE_FAILURE, error=frozen_error)
            )
        else:
            _check_stability(
                review, readings, _number(dict(frozen or {}).get("cost_points"))
            )

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_desk(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "desk": DESK,
            "weeks_charged": len(entries),
            "desks_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _as_of(row: Mapping[str, Any], through: str) -> dict[str, Any]:
    'One ledger row as the export wrote it on `through` and no later.'

    seen = dict(row)
    if str(seen.get("start_date") or "") > through:
        seen["start_date"] = ""
    if str(seen.get("escalation_date") or "") > through:
        seen["escalation_date"] = ""
    last = str(seen.get("last_observed_date") or "")
    if last > through:
        seen["last_observed_date"] = through
    return seen


def _state_as_of(row: Mapping[str, Any], through: str) -> dict[str, Any] | None:
    'One account-state stretch as the platform could publish it then.'

    if str(row.get("effective_from") or "") > through:
        return None
    seen = dict(row)
    if str(seen.get("effective_to") or "") > through:
        seen["effective_to"] = ""
    return seen


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    "The desk's evidence as it stood on the day of one recorded session."

    through = str(record["as_of"])
    context = world.context()
    context["window"]["last_day"] = through
    context["as_of"] = through
    context["flags"] = [
        _as_of(row, through) for row in context["flags"] if row["flag_date"] <= through
    ]
    keep = {str(row["account_id"]) for row in context["flags"]}
    states = (
        _state_as_of(row, through)
        for row in context["account_states"]
        if str(row["account_id"]) in keep
    )
    context["account_states"] = [row for row in states if row is not None]
    context["weeks"] = [row for row in context["weeks"] if row["first_day"] <= through]
    return context


def _by_week(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Flags, starts and escalations by week, as the weekly export lays them out.'

    weeks = {row["week"]: dict(row) for row in context["weeks"]}
    rows: dict[int, dict[str, Any]] = {}
    for row in context["flags"]:
        week = next(
            (item["week"] for item in weeks.values()
             if item["first_day"] <= row["flag_date"] <= item["last_day"]),
            None,
        )
        if week is None:
            continue
        entry = rows.setdefault(
            week, {"week": week, "first_day": weeks[week]["first_day"], "flags": 0,
                   "same_day": 0, "next_slot": 0, "started": 0, "escalations": 0}
        )
        entry["flags"] += 1
        entry[str(row["start_queue"])] += 1
        if row["start_date"]:
            entry["started"] += 1
        if row["escalation_date"]:
            entry["escalations"] += 1
    return [rows[week] for week in sorted(rows)]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_receipts(root)
    world = live_world(entries) if not error else workload.CURRENT
    context = world.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session", "date", "analyst", "as_of")},
        })
    return {
        "summary": (
            f"The {context['desk']} desk, the review's terms and the sessions on record."
        ),
        "measurements": {
            "desk": context["desk"],
            "window": context["window"],
            "as_of": context["as_of"],
            "escalation_window_days": context["escalation_window_days"],
            "grace_window_days": context["grace_window_days"],
            "review": context["review"],
            "capacity": context["capacity"],
            "export": context["export"],
            "flags_on_the_ledger": len(context["flags"]),
            "slots_charged": world.slots_spent(entries),
            "slots_left": world.slots_left(entries),
            "weeks_on_the_receipts": [
                {
                    "receipt_id": item["receipt_id"],
                    "segment": item["segment"],
                    "hold_share": item["hold_share"],
                    "slots_asked": item["slots_asked"],
                    "slots_charged": item["slots_charged"],
                    "rows_returned": item["rows_returned"],
                    "refusal": item["refusal"],
                }
                for item in entries
            ],
            "receipts": error or "read back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that recorded session ran it.'

    record = _record(record_path)
    entries, _error = live_receipts(Path(artifact_dir))
    world = live_world(entries)
    context = snapshot(world, record)
    receipts = [
        item for item in workload.opening_receipts(workload.CURRENT)
        if str(item["receipt_id"]) in set(record.get("receipts_then", ()))
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": compact(context), "receipts": receipts},
            {"kind": "plan", "context": compact(context), "receipts": receipts},
        ]},
    )
    session = {
        "session": record.get("session"),
        "date": record.get("date"),
        "analyst": record.get("analyst"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("as_of"),
        "weeks_on_the_receipts": [
            {"receipt_id": item["receipt_id"], "segment": item["segment"],
             "slots_charged": item["slots_charged"], "refusal": item["refusal"]}
            for item in receipts
        ],
        "by_week": _by_week(context),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "desk": context["desk"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "desk": context["desk"],
            "as_of": context["as_of"],
            "flags_then": len(context["flags"]),
            "slots_charged_then": sum(int(item["slots_charged"]) for item in receipts),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_booking(
    artifact_dir: Path, segment: Any, hold_share: Any, slots: Any, receipt_id: Any,
    week: Any = None,
) -> Mapping[str, Any]:
    entries, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return w.collect(
        Path(artifact_dir), workload.CURRENT_BASE, workload.CURRENT_SPEC["bookings"],
        segment, hold_share, slots, receipt_id, week,
    )


def starting_receipts() -> dict[str, Any]:
    'The receipt stream the desk starts the review with.'

    return {
        "desk": workload.CURRENT.desk,
        "entries": workload.opening_receipts(workload.CURRENT),
    }
