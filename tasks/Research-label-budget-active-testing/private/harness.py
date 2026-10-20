'Read one delivered review notebook against the world it is a review of.'

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, vendor, workload
from .world import QUEUES, Desk


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-label-budget-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

CURRENT = workload.CURRENT
REVIEW = str(CURRENT.spec["review"])

RUBRICS = (
    "intake_misroute_estimate",
    "purchase_accounting",
    "misroute_range_is_honest",
    "reviewer_regime_invariance",
    "next_purchase_order",
)

BUCKETS: Mapping[str, str] = {
    "intake_misroute_estimate": "estimate_failures",
    "purchase_accounting": "accounting_failures",
    "misroute_range_is_honest": "range_failures",
    "reviewer_regime_invariance": "drift_failures",
    "next_purchase_order": "plan_failures",
}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "intake_misroute_estimate": (
        "intake_rate_absent",
        "rate_read_off_the_bought_labels",
        "rate_weighted_by_the_draw_chances",
        "rate_read_off_the_label_pool",
        "late_session_labels_taken_at_face_value",
        "segments_the_desk_never_read_left_out",
        "segments_no_label_reaches_are_filled_in",
        "intake_rate_disagrees",
        "candidate_execution_failed",
    ),
    "purchase_accounting": (
        "ledger_will_not_read",
        "purchases_are_not_a_ledger",
        "paid_label_missing_from_the_report",
        "line_not_on_the_ledger",
        "receipt_reported_twice",
        "credits_disagree_with_the_statement",
        "candidate_execution_failed",
    ),
    "misroute_range_is_honest": (
        "range_absent",
        "reported_rate_outside_its_range",
        "range_misses_the_preserved_batches",
        "range_wider_than_the_intake_supports",
        "candidate_execution_failed",
    ),
    "reviewer_regime_invariance": (
        "rate_absent_on_a_second_reading",
        "rate_moves_when_the_reviewer_tires_sooner",
        "rate_moves_when_the_sittings_are_cut_differently",
        "regime_readings_disagree_with_the_intake",
        "candidate_execution_failed",
    ),
    "next_purchase_order": (
        "paid_session_bought_where_the_desk_could_already_read",
        "order_is_not_a_session_or_a_stop",
        "order_names_items_the_pool_cannot_supply",
        "order_runs_past_the_stretch_that_holds",
        "order_needs_more_sittings_than_the_dates_allow",
        "order_costs_more_than_the_balance",
        "order_buys_where_the_desk_can_already_read",
        "order_leaves_a_segment_the_desk_cannot_read",
        "order_stopped_with_segments_still_unread",
        "candidate_execution_failed",
    ),
}


def desk_context(desk: Desk) -> dict[str, Any]:
    "The desk's own exports and terms, as the reporting stack hands them over."

    spec = desk.spec
    return {
        "desk": desk.desk,
        "review": str(spec["review"]),
        "window": {"first_day": str(spec["window"][0]), "last_day": str(spec["window"][1])},
        "today": str(spec["today"]),
        "order_cutoff": str(spec["order_cutoff"]),
        "review_on": str(spec["review_on"]),
        "sessions_before_cutoff": int(spec["sessions_before_cutoff"]),
        "prices": dict(spec["prices"]),
        "setup_credits": int(spec["setup_credits"]),
        "session_item_cap": int(spec["session_item_cap"]),
        "credits_contracted": int(spec["credits_contracted"]),
        "pool_exported_on": str(spec["pool_exported_on"]),
        "queues": list(QUEUES),
        "catalogue": desk.catalogue(),
        "intake": desk.intake_rows(),
        "pool": desk.pool_rows(),
        "adjudication": vendor.adjudication_rows(desk),
    }


def _closing(desk: Desk, entries: Sequence[Mapping[str, Any]], segments: Sequence[str],
             session_id: str) -> list[dict[str, Any]]:
    'The ledger with further sittings that read the named segments.'

    if not segments:
        return [dict(entry) for entry in entries]
    bought = vendor.bought_items(entries)
    picks = []
    for segment in segments:
        options = [
            row for row in desk.pool_rows()
            if row["segment"] == segment and row["item_id"] not in bought
        ]
        if not options:
            continue
        picks.append(min(options, key=lambda row: (desk.price_of(row["channel"]), row["item_id"])))
        bought.add(picks[-1]["item_id"])
    if not picks:
        return [dict(entry) for entry in entries]
    seat = max(1, oracle.sitting_cap(desk, entries))
    bodies = vendor.bodies_of(entries)
    for index, start in enumerate(range(0, len(picks), seat), start=1):
        suffix = session_id if len(picks) <= seat else f"{session_id}-{index:02d}"
        bodies.extend(vendor.closing_bodies(
            desk, suffix, f"{desk.spec['today']}T09:30", picks[start:start + seat]))
    return vendor.chain(desk, bodies)


def settled_ledger(desk: Desk) -> list[dict[str, Any]]:
    "The desk's ledger once every segment of its intake has been read."

    entries = vendor.archived_ledger(desk)
    return _closing(desk, entries, oracle.segments_open(desk, entries), "settle")


def _variant(desk: Desk, sessions: Sequence[Mapping[str, Any]],
             ramp: Mapping[str, Any]) -> Desk:
    'The same desk with its sittings cut differently, or its reviewer tiring sooner.'

    return Desk({**desk.spec, "sessions": tuple(sessions), "ramp": dict(ramp)})


def _recut(desk: Desk, size: int) -> tuple[dict[str, Any], ...]:
    total = sum(int(entry["items"]) for entry in desk.spec["sessions"])
    cut = []
    left = total
    index = 0
    while left > 0:
        index += 1
        take = min(size, left)
        cut.append({
            "session_id": f"{desk.code}-C{index:02d}",
            "ordered_at": f"2026-08-{18 + index:02d}T09:00",
            "delivered_at": f"2026-08-{18 + index:02d}T19:00",
            "items": take,
            "reviewer": "R-14",
        })
        left -= take
    return tuple(cut)


def regime_ledgers(desk: Desk) -> list[tuple[str, list[dict[str, Any]]]]:
    'One ledger per way the same labels could have been worked through.'

    every = list(oracle.intake_segments(desk))
    as_run = _closing(desk, vendor.archived_ledger(desk), every, "regime")
    recut = _variant(desk, _recut(desk, 36), desk.spec["ramp"])
    tiring = _variant(desk, desk.spec["sessions"],
                      {"onset": 12, "slope": "1/20", "cap": "0.9"})
    return [
        ("as the sittings were cut", as_run),
        ("cut into shorter sittings", _closing(recut, vendor.archived_ledger(recut), every, "regime")),
        ("with the reviewer tiring sooner",
         _closing(tiring, vendor.archived_ledger(tiring), every, "regime")),
    ]


def _drained(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]] | None:
    'The same account after the balance has gone on segments already read.'

    read = set(oracle.segments_read(desk, entries))
    grown = [dict(entry) for entry in entries]
    setup = int(desk.spec["setup_credits"])
    cap = int(desk.spec["session_item_cap"])
    for index in range(12):
        cheapest = oracle.buyable_segments(desk, grown)
        floor = setup + min(cheapest.values(), default=0)
        if cheapest and vendor.credits_left(desk, grown) < floor:
            return grown
        bought = vendor.bought_items(grown)
        options = sorted(
            (row for row in desk.pool_rows()
             if row["segment"] in read and row["item_id"] not in bought),
            key=lambda row: (-desk.price_of(row["channel"]), row["item_id"]),
        )
        if not options:
            return None
        left = vendor.credits_left(desk, grown) - setup
        picks: list[Mapping[str, Any]] = []
        for row in options:
            price = desk.price_of(row["channel"])
            if len(picks) >= cap or price > left:
                break
            picks.append(row)
            left -= price
        if not picks:
            return None
        bodies = vendor.bodies_of(grown)
        bodies.extend(vendor.closing_bodies(
            desk, f"drain-{index:02d}", f"{desk.spec['today']}T09:30", picks))
        grown = vendor.chain(desk, bodies)
    return None


def _state(family: str, label: str, desk: Desk, ledger: Sequence[Mapping[str, Any]]
           ) -> dict[str, Any]:
    return {"family": family, "kind": "plan" if family == "plan" else "report",
            "label": label, "desk": desk,
            "ledger": [dict(entry) for entry in ledger]}


def report_states(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    states = [_state("report", REVIEW, CURRENT, live)]
    for desk in (*workload.SIBLINGS, workload.OUT_OF_REGIME):
        states.append(_state("report", str(desk.spec["review"]), desk, settled_ledger(desk)))
    return states


def regime_states() -> list[dict[str, Any]]:
    return [
        _state("regime", f"{REVIEW}, {label}", CURRENT, ledger)
        for label, ledger in regime_ledgers(CURRENT)
    ]


def plan_states(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every state the account can be in when it is asked what to order next.'

    archive = starting_ledger()
    states = [_state("plan", REVIEW, CURRENT, live)]
    open_now = list(oracle.buyable_segments(CURRENT, archive))
    for held in open_now:
        rest = [segment for segment in open_now if segment != held]
        if rest:
            states.append(_state("plan", f"{REVIEW}, {held} still unread", CURRENT,
                                 _closing(CURRENT, archive, rest, f"read-{held}")))
    if open_now:
        states.append(_state("plan", f"{REVIEW}, every segment read", CURRENT,
                             _closing(CURRENT, archive, open_now, "read-all")))
    drained = _drained(CURRENT, archive) if open_now else None
    if drained is not None:
        states.append(_state("plan", f"{REVIEW}, the balance gone", CURRENT, drained))
    for desk in (*workload.SIBLINGS, workload.OUT_OF_REGIME):
        states.append(_state("plan", str(desk.spec["review"]), desk,
                             vendor.archived_ledger(desk)))
    return states


def wasted_live_sessions(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Paid sessions added in this episode that brought no new segment into view.'

    archive = starting_ledger()
    historical = set(vendor.sessions_on(archive))
    added = [entry for entry in vendor.distinct(live)
             if str(entry["session_id"]) not in historical]
    order: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in added:
        session_id = str(entry["session_id"])
        if session_id not in grouped:
            order.append(session_id)
            grouped[session_id] = []
        grouped[session_id].append(dict(entry))

    prefix = [dict(entry) for entry in archive]
    wasted = []
    for session_id in order:
        rows = grouped[session_id]
        readable_before = oracle.segments_read(CURRENT, prefix)
        bought_segments = {str(entry["segment"]) for entry in rows}
        if bought_segments and bought_segments <= readable_before:
            wasted.append({
                "session_id": session_id,
                "labels_bought": len(rows),
                "credits_spent": int(CURRENT.spec["setup_credits"])
                + sum(int(entry["price_credits"]) for entry in rows),
            })
        prefix.extend(rows)
    return wasted


def _number(value: Any) -> Fraction | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def _near(value: Any, wanted: Fraction | None, slack: Fraction) -> bool:
    read = _number(value)
    return read is not None and wanted is not None and abs(read - wanted) <= slack


def _share(value: Any) -> str:
    'One rate as the desk writes it: tickets in a hundred, two places.'

    read = value if isinstance(value, Fraction) else _number(value)
    if read is None:
        return "nothing" if value is None else str(value)[:40]
    return format(float(read) * 100, ".2f")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "nothing"
    return str(value)[:60]


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _written_off_the_visible_lot(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'What the operations lead opens the conversation with.'

    visible = [record for record in records
               if str(record.get("review", "")).startswith(REVIEW)]
    if not visible:
        return [dict(record) for record in records]
    kinds = {str(record.get("kind")) for record in visible} | {CANDIDATE_FAILURE}
    return [dict(record) for record in records if str(record.get("kind")) in kinds]


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    "Put the incident on the desk's own review ahead of a later desk's."

    review = str(record.get("review", ""))
    return (0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
            0 if review.startswith(REVIEW) else 1)


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {
            bucket: [] for bucket in BUCKETS.values()
        }

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(0, _fail(CANDIDATE_FAILURE, error=error))


def _check_estimate(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    desk, ledger = state["desk"], state["ledger"]
    where = {"review": state["label"], "desk": desk.desk}
    reported = report.get("misroute_rate")
    if reported is None:
        review.add("estimate_failures", "intake_rate_absent", **where,
                   labels_bought=len(vendor.distinct(ledger)))
        return
    told = {**where, "reported": _share(reported)}
    counts = oracle.intake_counts(desk)
    unread = oracle.segments_open(desk, ledger)

    def record_unread_segments() -> None:


        review.add("estimate_failures", "segments_no_label_reaches_are_filled_in", **told,
                   segments_unread=len(unread),
                   tickets_unread=sum(counts.get(segment, 0) for segment in unread),
                   intake_segments=len(oracle.intake_segments(desk)),
                   labels_bought=len(vendor.distinct(ledger)),
                   credits_left=vendor.credits_left(desk, ledger))

    if _near(reported, oracle.truth(desk), oracle.TOLERANCE):
        if unread:
            record_unread_segments()
        return


    sharper = [oracle.pool_reading(desk), oracle.face_value_reading(desk, ledger)]
    if unread:
        sharper.extend(oracle.read_only_readings(desk, ledger))
    for value in oracle.bought_readings(desk, ledger):
        if any(other is not None and abs(value - other) <= oracle.NEAR_MISTAKE
               for other in sharper):
            continue
        if _near(reported, value, oracle.NEAR_MISTAKE):
            review.add("estimate_failures", "rate_read_off_the_bought_labels", **told,
                       labels_bought=len(vendor.distinct(ledger)),
                       intake_tickets=len(desk.intake_rows()))
            return
    if _near(reported, oracle.pool_reading(desk), oracle.NEAR_MISTAKE):
        review.add("estimate_failures", "rate_read_off_the_label_pool", **told,
                   pool_items=len(desk.pool_rows()), intake_tickets=len(desk.intake_rows()))
        return
    if _near(reported, oracle.face_value_reading(desk, ledger), oracle.NEAR_MISTAKE):
        review.add("estimate_failures", "late_session_labels_taken_at_face_value", **told,
                   settled_items=len(vendor.adjudication_rows(desk)),
                   labels_bought=len(vendor.distinct(ledger)),
                   settled_labels_overturned=oracle.sheet_partings(desk, ledger))
        return
    if unread and any(_near(reported, value, oracle.NEAR_MISTAKE)
                      for value in oracle.read_only_readings(desk, ledger)):
        review.add("estimate_failures", "segments_the_desk_never_read_left_out", **told,
                   segments_unread=len(unread),
                   tickets_unread=sum(counts.get(segment, 0) for segment in unread))
        return
    for value in oracle.draw_weighted_readings(desk, ledger):
        if _near(reported, value, oracle.NEAR_MISTAKE):
            review.add("estimate_failures", "rate_weighted_by_the_draw_chances", **told,
                       labels_bought=len(vendor.distinct(ledger)),
                       pool_items=len(desk.pool_rows()),
                       intake_tickets=len(desk.intake_rows()))
            return
    if unread:


        record_unread_segments()
        return
    review.add("estimate_failures", "intake_rate_disagrees", **told,
               intake_tickets=len(desk.intake_rows()),
               settled_labels_overturned=oracle.sheet_partings(desk, ledger),
               settled_items=len(vendor.adjudication_rows(desk)))


def _check_range(review: Review, state: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    desk = state["desk"]
    where = {"review": state["label"], "desk": desk.desk}
    untagged = sum(1 for row in desk.intake_rows() if not row["segment"])
    span = report.get("misroute_rate_range")
    pair = [_number(value) for value in span] if isinstance(span, list) else [None, None]
    if len(pair) != 2 or pair[0] is None or pair[1] is None or pair[0] > pair[1]:
        review.add("range_failures", "range_absent", **where, reported=_show(span))
        return
    reported = _number(report.get("misroute_rate"))
    if reported is not None and not pair[0] <= reported <= pair[1]:
        review.add(
            "range_failures",
            "reported_rate_outside_its_range",
            **where,
            reported=_share(reported),
            reported_low=_share(pair[0]),
            reported_high=_share(pair[1]),
        )
        return
    low, high = oracle.bounds(desk)
    slack = oracle.RANGE_SLACK
    told = {**where, "reported_low": _share(pair[0]), "reported_high": _share(pair[1]),
            "tickets_without_a_segment": untagged}
    if pair[0] > low + slack or pair[1] < high - slack:
        review.add("range_failures", "range_misses_the_preserved_batches", **told)
    elif pair[0] < low - slack or pair[1] > high + slack:
        review.add("range_failures", "range_wider_than_the_intake_supports", **told)


def _check_accounting(review: Review, state: Mapping[str, Any], report: Mapping[str, Any],
                      ledger_error: str | None) -> None:
    desk, ledger = state["desk"], state["ledger"]
    where = {"review": state["label"], "desk": desk.desk}
    if ledger_error:
        review.add("accounting_failures", "ledger_will_not_read", **where,
                   reason=str(ledger_error))
        return
    issued = {str(entry["receipt_id"]): entry for entry in vendor.distinct(ledger)}
    lines = report.get("label_purchases")
    if not isinstance(lines, list):
        review.add("accounting_failures", "purchases_are_not_a_ledger", **where,
                   reported=_show(lines), receipts_on_the_ledger=len(issued))
        return
    seen: dict[str, int] = {}
    for line in lines:
        key = str(line.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            review.add("accounting_failures", "receipt_reported_twice", **where,
                       receipt_id=key, times_reported=seen[key])
            return
        entry = issued.get(key)
        if (entry is None
                or str(line.get("session_id")) != str(entry["session_id"])
                or str(line.get("item_id")) != str(entry["item_id"])
                or not _near(line.get("price_credits"),
                             Fraction(int(entry["price_credits"])), Fraction(0))):
            review.add("accounting_failures", "line_not_on_the_ledger", **where,
                       receipt_id=key, receipts_on_the_ledger=len(issued))
            return
    for key, entry in issued.items():
        if key not in seen:
            review.add("accounting_failures", "paid_label_missing_from_the_report", **where,
                       receipt_id=key, session_id=str(entry["session_id"]),
                       receipts_on_the_ledger=len(issued))
            return
    statement = oracle.credits_statement(desk, ledger)
    if not _near(report.get("credits_spent"), Fraction(statement), Fraction(0)):
        review.add("accounting_failures", "credits_disagree_with_the_statement", **where,
                   reported_credits=_show(report.get("credits_spent")),
                   statement_credits=statement)


def _check_drift(review: Review, readings: Sequence[tuple[str, Any]]) -> None:
    'The same labels, worked through differently, have to give one number.'

    if len(readings) < 3:
        return
    base_label, base = readings[0]
    modes = ("rate_moves_when_the_sittings_are_cut_differently",
             "rate_moves_when_the_reviewer_tires_sooner")
    where = {"review": REVIEW, "desk": CURRENT.desk}
    for (label, value), mode in zip(readings[1:], modes):
        first, second = _number(base), _number(value)
        if first is None or second is None:
            missing = base_label if first is None else label
            review.add("drift_failures", "rate_absent_on_a_second_reading", **where,
                       reading=missing)
            return
        if abs(first - second) > oracle.DRIFT_SLACK:
            review.add("drift_failures", mode, **where, reading=label,
                       first_reading=_share(first), second_reading=_share(second))
            return
    if not _near(base, oracle.truth(CURRENT), oracle.TOLERANCE):
        review.add(
            "drift_failures",
            "regime_readings_disagree_with_the_intake",
            **where,
            reading=base_label,
            reported=_share(base),
            intake_tickets=len(CURRENT.intake_rows()),
        )


def _check_plan(review: Review, state: Mapping[str, Any], offered: Any) -> None:
    desk, ledger = state["desk"], state["ledger"]
    counts = oracle.intake_counts(desk)
    cheapest = oracle.buyable_segments(desk, ledger)
    unread = oracle.segments_open(desk, ledger)
    left = vendor.credits_left(desk, ledger)
    reach, wanted = oracle.reachable_mass(desk, ledger)
    where = {
        "review": state["label"],
        "desk": desk.desk,
        "credits_left": left,
        "segments_unread": len(unread),
        "tickets_unread": sum(counts.get(segment, 0) for segment in unread),
    }
    if offered == ["stop"] or offered == "stop":
        if wanted:
            review.add("plan_failures", "order_stopped_with_segments_still_unread", **where)
        return
    if (not isinstance(offered, list) or not offered
            or any(not isinstance(item, dict) or not isinstance(item.get("items"), list)
                   or not item["items"] for item in offered)):
        review.add("plan_failures", "order_is_not_a_session_or_a_stop", **where,
                   reported=_show(offered))
        return
    pool = {row["item_id"]: row for row in desk.pool_rows()}
    bought = vendor.bought_items(ledger)
    picked: list[str] = []
    for session in offered:
        for raw in session["items"]:
            item_id = str(raw)
            if item_id not in pool or item_id in bought or item_id in picked:
                review.add("plan_failures", "order_names_items_the_pool_cannot_supply",
                           **where, item_id=item_id)
                return
            picked.append(item_id)
    cost = len(offered) * int(desk.spec["setup_credits"]) + sum(
        desk.price_of(pool[item_id]["channel"]) for item_id in picked
    )
    if cost > left:
        review.add("plan_failures", "order_costs_more_than_the_balance", **where,
                   credits_needed=cost)
        return
    sittings = int(desk.spec["sessions_before_cutoff"])
    if len(offered) > sittings:
        review.add("plan_failures", "order_needs_more_sittings_than_the_dates_allow",
                   **where, sittings=len(offered), sittings_before_cutoff=sittings)
        return
    longest = max(len(session["items"]) for session in offered)
    cap = oracle.sitting_cap(desk, ledger)
    if longest > cap:
        review.add("plan_failures", "order_runs_past_the_stretch_that_holds", **where,
                   items_in_the_longest_sitting=longest,
                   sitting_cap=cap,
                   settled_items=len(vendor.adjudication_rows(desk)))
        return
    picked_segments = [str(pool[item_id]["segment"]) for item_id in picked]
    read = set(picked_segments) & set(cheapest)
    covered = sum(counts.get(segment, 0) for segment in read)
    if (not wanted or not read
            or any(segment not in cheapest for segment in picked_segments)):
        review.add("plan_failures", "order_buys_where_the_desk_can_already_read", **where)
        return
    if covered >= reach:
        return
    missed = max((segment for segment in wanted if segment not in read),
                 key=lambda segment: (counts.get(segment, 0), segment))
    review.add("plan_failures", "order_leaves_a_segment_the_desk_cannot_read", **where,
               segment=missed)


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (f"it was still running after {reported[len(_TIMEOUT_PHRASE):].strip()} "
                "and the console stopped it")
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the review notebook stopped part way through: {line[:200]}"


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return vendor.read_entries(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def _payload(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    contexts: dict[str, Any] = {}
    requests = []
    for state in states:
        code = state["desk"].code
        if code not in contexts:
            contexts[code] = desk_context(state["desk"])
        requests.append({"kind": state["kind"], "context": code, "ledger": state["ledger"]})
    return {"contexts": contexts, "requests": requests}


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    def compute() -> Mapping[str, Any]:
        entries, ledger_error = live_ledger(Path(artifact_dir))
        reports = report_states(entries)
        regimes = regime_states()
        plans = plan_states(entries)
        states = [*reports, *regimes, *plans]
        run = PROJECT.invoke(Path(artifact_dir), _payload(states))
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"review": REVIEW, "labels_bought": len(vendor.distinct(entries))}
            return analysis

        results = list(run.get("results", ()))
        review = Review()
        current_counts = oracle.intake_counts(CURRENT)
        current_unread = oracle.segments_open(CURRENT, entries)
        for wasted in wasted_live_sessions(entries):
            review.add(
                "plan_failures",
                "paid_session_bought_where_the_desk_could_already_read",
                review=REVIEW,
                desk=CURRENT.desk,
                credits_left=vendor.credits_left(CURRENT, entries),
                segments_unread=len(current_unread),
                tickets_unread=sum(current_counts.get(segment, 0)
                                   for segment in current_unread),
                **wasted,
            )
        broke = False
        readings: list[tuple[str, Any]] = []
        for index, state in enumerate(states):
            item = dict(results[index]) if index < len(results) else {}
            if not item.get("ok"):
                broke = True
                error = str(item.get("error") or "the notebook returned no answer")
                if state["family"] == "plan":
                    review.stopped(("plan_failures",), error)
                elif state["family"] == "regime":
                    review.stopped(("drift_failures",), error)
                else:
                    review.stopped(("estimate_failures", "range_failures",
                                    "accounting_failures"), error)
                continue
            answer = item.get("answer")
            if state["family"] == "plan":
                _check_plan(review, state, answer)
                continue
            report = dict(answer or {})
            if state["family"] == "regime":
                readings.append((state["label"], report.get("misroute_rate")))
                continue
            _check_estimate(review, state, report)
            _check_range(review, state, report)
            _check_accounting(
                review, state, report,
                ledger_error if state["desk"] is CURRENT else None,
            )
        _check_drift(review, readings)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_visible_lot(sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "review": REVIEW,
            "labels_bought": len(vendor.distinct(entries)),
            "states": len(states),
            "notebook_stopped": broke,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _ledger_summary(desk: Desk, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    "The receipt stream as the vendor wrote it, beside the vendor's statement."

    sessions = []
    for session_id in vendor.sessions_on(entries):
        rows = [entry for entry in entries if entry["session_id"] == session_id]
        sessions.append({
            "session_id": session_id,
            "labels": len(rows),
            "ordered_at": rows[0]["ordered_at"],
            "delivered_at": rows[0]["delivered_at"],
            "reviewer": rows[0]["reviewer"],
            "credits": sum(int(row["price_credits"]) for row in rows),
        })
    return {
        "lines_on_the_ledger": len(entries),
        "sessions": sessions,
        "credits_spent": vendor.credits_spent(desk, entries),
        "credits_left": vendor.credits_left(desk, entries),
    }


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working-session record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_ledger(root)
    context = desk_context(CURRENT)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("record_id", "date", "operator")},
        })
    return {
        "summary": (f"{context['desk']}, the review of {context['review']}, "
                    "its vendor terms and the sessions on the ledger."),
        "measurements": {
            "desk": context["desk"],
            "review": context["review"],
            "window": context["window"],
            "today": context["today"],
            "order_cutoff": context["order_cutoff"],
            "review_on": context["review_on"],
            "sessions_before_cutoff": context["sessions_before_cutoff"],
            "prices": context["prices"],
            "setup_credits": context["setup_credits"],
            "session_item_cap": context["session_item_cap"],
            "credits_contracted": context["credits_contracted"],
            "pool_exported_on": context["pool_exported_on"],
            "intake_tickets": len(context["intake"]),
            "pool_items": len(context["pool"]),
            "settled_items": len(context["adjudication"]),
            "ledger": _ledger_summary(CURRENT, entries) if not error else {},
            "ledger_problem": error,
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that working session ran it.'

    record = _record(record_path)
    entries, error = live_ledger(Path(artifact_dir))
    through = int(record.get("through_line", len(entries)))
    ledger = entries[:through]
    context = desk_context(CURRENT)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"contexts": {CURRENT.code: context},
         "requests": [{"kind": "report", "context": CURRENT.code, "ledger": ledger},
                      {"kind": "plan", "context": CURRENT.code, "ledger": ledger}]},
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "ledger_through_line": through,
        "ledger": _ledger_summary(CURRENT, ledger),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "review": context["review"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "desk": context["desk"],
            "review": context["review"],
            "ledger_through_line": through,
            "ledger_problem": error,
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_session(artifact_dir: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    return vendor.collect(Path(artifact_dir), CURRENT, arguments)


def starting_ledger() -> list[dict[str, Any]]:
    return vendor.archived_ledger(CURRENT)
