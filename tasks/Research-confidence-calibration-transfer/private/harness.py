'Read one delivered auto-clear readout against the queues it is about.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import checks, desk, oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-autoclear-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "escape_rate_within_tolerance",
    "range_covers_and_meets_floor",
    "estimate_invariant_to_lag_and_router",
    "next_batch_feasible_and_informative",
    "report_reconciles_receipts",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "escape_rate_within_tolerance": (
        "reads_the_chart_files_period",
        "counts_unwritten_as_clean",
        "weights_by_logged_rows",
        "escape_rate_disagrees",
        "cut_not_on_the_sheet",
        "cut_over_the_bar",
        "cut_tighter_than_the_bar_needs",
        "rate_wrong_on_another_queue",
        "cut_wrong_on_another_queue",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "range_does_not_contain_estimate",
        "range_below_floor",
        "range_wider_than_the_evidence",
        "range_undercovers",
        "adjudicated_count_not_reported",
        "range_wrong_on_another_queue",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_lag_and_router": (
        "moves_with_reconciliation_lag",
        "moves_with_router_date",
        "hardcoded_history",
        "candidate_execution_failed",
    ),
    "next_batch_feasible_and_informative": (
        "batch_is_not_a_request_or_a_stop",
        "batch_mixes_periods",
        "batch_over_cap",
        "batch_over_credits",
        "batch_cell_empty",
        "batch_uninformative",
        "batch_stops_with_work_left",
        "batch_wrong_on_another_queue",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "batches_are_not_a_list",
        "batch_missing_from_the_report",
        "refusal_uncounted",
        "batch_not_on_the_receipts",
        "batch_counted_twice",
        "batch_listings_disagree",
        "batch_credits_disagree",
        "credits_disagree_with_the_receipts",
        "receipts_wrong_on_another_queue",
        "candidate_execution_failed",
    ),
}

CURRENT_QUEUE = str(workload.CURRENT_SPEC["queue"])
CURRENT_DESK = str(workload.CURRENT_SPEC["desk"])

_fail = checks._fail


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "escape_rate_within_tolerance": (
        "rate_wrong_on_another_queue",
        "cut_wrong_on_another_queue",
    ),
    "range_covers_and_meets_floor": ("range_wrong_on_another_queue",),
    "next_batch_feasible_and_informative": ("batch_wrong_on_another_queue",),
    "report_reconciles_receipts": ("receipts_wrong_on_another_queue",),
}


CUT_KINDS: tuple[str, ...] = (
    "cut_not_on_the_sheet",
    "cut_over_the_bar",
    "cut_tighter_than_the_bar_needs",
)


_NAMING_ORDER: tuple[str, ...] = tuple(
    str(spec["queue"])
    for spec in (*workload.FOLLOWING_SPECS, workload.NIGHTLY_SPEC)
)


def _naming_rank(queue: str) -> int:
    return _NAMING_ORDER.index(queue) if queue in _NAMING_ORDER else len(_NAMING_ORDER)


def _report_order(record: Mapping[str, Any]) -> tuple[int, int, int]:
    'Put the incident the owner can open her own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("queue") == CURRENT_QUEUE else 1,
        int(record.get("rank", 0)),
    )


def _carry_over_mode(modes: Sequence[str], kind: str) -> str:
    'Which carry-over incident a record of this kind belongs to.'

    if len(modes) == 1:
        return modes[0]
    return modes[1] if kind in CUT_KINDS else modes[0]


def _written_off_the_queue_she_can_open(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the queue whose files she holds."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE
        or record.get("queue") == CURRENT_QUEUE
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    declared = FAILURE_MODES[bucket]

    def declared_rank(record: Mapping[str, Any]) -> int:
        kind = str(record.get("kind"))
        return declared.index(kind) if kind in declared else len(declared)

    leading = str(min(rows, key=declared_rank).get("kind"))
    mode = _carry_over_mode(modes, leading)
    same = [
        record
        for record in rows
        if _carry_over_mode(modes, str(record.get("kind"))) == mode
    ]
    named = min(
        (record for record in same if record.get("queue")),
        key=lambda record: _naming_rank(str(record["queue"])),
        default=same[0],
    )
    elsewhere = sorted({str(record["queue"]) for record in same if record.get("queue")})
    return [
        _fail(
            mode,
            queue=CURRENT_QUEUE,
            desk=CURRENT_DESK,
            other_queue=str(named.get("queue")),
            other_queues=len(elsewhere),
            rank=0,
        )
    ]


def opening_receipts() -> dict[str, Any]:
    'The receipt file the campaign opens with: 200 credits already charged.'

    stream = workload.current()
    early, late = stream.spec["periods"][0], stream.spec["periods"][-1]
    entries: list[dict[str, Any]] = []
    for channel, period, listings, batch_id, day in (
        ("mobile", late, 120, "jun-mobile-spot", 100),
        ("web", early, 80, "jun-web-spot", 103),
        ("reseller_import", late, 60, "jul-resell-open", 110),
        ("web", late, 27, "aug-web-tail", 112),
    ):
        entries = desk.book(
            stream, entries, channel, period, listings, batch_id, stream.days[day]
        )
    return desk.receipts_document(stream, entries)


ARCHIVED: Mapping[str, tuple[tuple[str, int, str], ...]] = {
    "collectables-listings-q3": (("partner_feed", 90, "cl-open"),),
    "homeware-listings-q3": (
        ("partner_feed", 120, "hw-open"),
        ("mobile", 60, "hw-mobile"),
    ),
    "ticketing-listings-q3": (("reseller_import", 80, "tk-open"),),
    "supplies-listings-q3": (("web", 40, "sp-open"),),
}


def archived_receipts(queue: world.Queue) -> list[dict[str, Any]]:
    'The batches a queue had already been charged for when its turn came.'

    entries: list[dict[str, Any]] = []
    late = queue.spec["periods"][-1]
    for channel, listings, batch_id in ARCHIVED.get(queue.queue, ()):
        entries = desk.book(
            queue, entries, channel, late, listings, batch_id, queue.days[-4]
        )
    return entries


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return desk.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]], walk: bool = False
) -> list[dict[str, Any]]:
    'Every state of this campaign, with what it can still pay for.'

    states = [{"label": "now", "receipts": [dict(item) for item in entries]}]
    if not walk:
        return states
    held = [dict(item) for item in entries]
    for step in range(6):
        plan = oracle.one_allowed_plan(queue, held)
        if plan == "stop":
            break
        held = desk.book(
            queue, held, str(plan["channel"]), str(plan["period"]),
            int(plan["listings"]), f"walk-{step + 1}", queue.days[-1],
        )
        states.append(
            {"label": f"after {len(held)} batches", "receipts": [dict(item) for item in held]}
        )


    turned_away = desk.book(
        queue, [dict(item) for item in entries], "partner_feed",
        str(queue.spec["periods"][-1]),
        int(queue.spec["max_listings_per_batch"]) + 40, "over-cap", queue.days[-1],
    )
    states.append({"label": "after a refusal", "receipts": turned_away})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The marketplace queue as it stands, then the queues after it.'

    rows = [
        {
            "queue": workload.current(),
            "receipts": [dict(item) for item in live],
            "scored": True,
            "planned": True,
        }
    ]
    for queue in (*workload.following(), workload.nightly()):
        archived = archived_receipts(queue)
        rows.append(
            {"queue": queue, "receipts": archived, "scored": True, "planned": True}
        )
    return rows


def reissue_cases() -> list[dict[str, Any]]:
    'The export as it stands and as the desk would reissue it, nothing bought.'

    lag, router = workload.reissues()
    return [
        {"queue": workload.current(), "label": "as it stands"},
        {"queue": lag, "label": "reconciliation lags redrawn"},
        {"queue": router, "label": "router day redrawn"},
    ]


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


def _state(queue: world.Queue) -> dict[str, Any]:
    return {"context": queue.context(), "log_csv": queue.log_csv(), "requests": []}


def _ask(states: list[dict[str, Any]], state: dict[str, Any], request: Mapping[str, Any]) -> int:
    'Add one request to a state and return its place in the flat answer list.'

    if not any(item is state for item in states):
        states.append(state)
    place = 0
    for item in states:
        if item is state:
            break
        place += len(item["requests"])
    place += len(state["requests"])
    state["requests"].append(dict(request))
    return place


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every queue and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipt_error = live_receipts(Path(artifact_dir))
        rows = cases(entries)
        states: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[world.Queue, dict[str, Any], int]] = []
        moves: list[tuple[str, int]] = []
        for row in rows:
            queue = row["queue"]
            state = _state(queue)
            reports.append((row, _ask(states, state, {"kind": "report", "receipts": row["receipts"]})))
            for item in plan_states(queue, row["receipts"], walk=queue.queue == CURRENT_QUEUE):
                plans.append((queue, item, _ask(states, state, {"kind": "plan", "receipts": item["receipts"]})))
            if queue.queue == CURRENT_QUEUE:
                moves.append(("as it stands", _ask(states, state, {"kind": "report", "receipts": []})))
        for case in reissue_cases()[1:]:
            state = _state(case["queue"])
            moves.append((case["label"], _ask(states, state, {"kind": "report", "receipts": []})))

        run = PROJECT.invoke(Path(artifact_dir), {"states": states})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            for bucket in BUCKETS.values():
                analysis[bucket] = [
                    dict(record, failed_case="the complete notebook run")
                    for record in analysis[bucket]
                ]
            analysis["case"] = {"queue": CURRENT_QUEUE, "batches_charged_for": len(entries)}
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the queues"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        uncovered: list[dict[str, Any]] = []
        for row, index in reports:
            queue, held = row["queue"], row["receipts"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                for bucket in ("escape_rate_within_tolerance", "range_covers_and_meets_floor",
                               "estimate_invariant_to_lag_and_router",
                               "report_reconciles_receipts"):
                    failures[bucket].append(
                        _fail(
                            CANDIDATE_FAILURE,
                            error=error,
                            failed_case=f"the {queue.queue} readout",
                            queue=queue.queue,
                        )
                    )
                continue
            report = dict(value or {})
            failures["escape_rate_within_tolerance"].extend(
                checks.rate_failures(queue, held, report)
            )
            shape, missed = checks.range_failures(queue, held, report)
            failures["range_covers_and_meets_floor"].extend(shape)
            if missed is not None:
                uncovered.append(missed)
            failures["report_reconciles_receipts"].extend(
                checks.receipt_failures(
                    queue, held, report,
                    receipt_error if queue.queue == CURRENT_QUEUE else None,
                )
            )
        held_on = len([row for row, _ in reports]) - len(uncovered)
        if uncovered:
            failures["range_covers_and_meets_floor"].extend(
                dict(item, queues_held=held_on) for item in uncovered
            )

        for queue, state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                failures["next_batch_feasible_and_informative"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        error=error,
                        failed_case=(
                            f"the {queue.queue} next-batch run ({state['label']})"
                        ),
                        queue=queue.queue,
                    )
                )
                continue
            failures["next_batch_feasible_and_informative"].extend(
                checks.plan_failures(queue, state, value)
            )

        reissued: dict[str, Any] = {}
        reissue_stopped = False
        for label, index in moves:
            value, error = answer(index)
            if error is not None:
                stopped = True
                reissue_stopped = True
                failures["estimate_invariant_to_lag_and_router"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        error=error,
                        failed_case=f"the {CURRENT_QUEUE} readout with {label}",
                        queue=CURRENT_QUEUE,
                    )
                )
                continue
            reissued[label] = dict(value or {}).get("escape_rate")
        seen = []
        for row, index in reports:
            value, error = answer(index)
            if error is None:
                seen.append(
                    (
                        row["queue"].queue,
                        dict(value or {}).get("escape_rate"),
                        oracle.truth(row["queue"]) * 100.0,
                    )
                )
        if not reissue_stopped:
            failures["estimate_invariant_to_lag_and_router"].extend(
                checks.movement_failures(reissued, seen)
            )

        analysis: dict[str, Any] = {
            rubric: _written_off_the_queue_she_can_open(
                rubric, sorted(records, key=_report_order)
            )
            for rubric, records in failures.items()
        }
        analysis["case"] = {
            "queue": CURRENT_QUEUE,
            "batches_charged_for": len(entries),
            "queues_read": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
