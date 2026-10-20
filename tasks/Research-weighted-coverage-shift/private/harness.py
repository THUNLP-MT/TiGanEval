'Read one delivered dispatch board against the depots it is a board for.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import checks, desk, oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-coverage-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "stream_rate_within_tolerance",
    "class_windows_hold_and_meet_floor",
    "windows_invariant_to_pull_and_drop",
    "next_visit_feasible_and_reaches_the_unsheeted_class",
    "report_reconciles_receipts",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "stream_rate_within_tolerance": (
        "stream_rate_not_to_nearest_point",
        "rate_read_off_the_sheets",
        "unprintable_class_left_out_of_denominator",
        "stream_rate_disagrees",
        "candidate_execution_failed",
    ),
    "class_windows_hold_and_meet_floor": (
        "windows_are_not_a_list",
        "one_window_for_all_classes",
        "window_misses_the_class",
        "window_over_the_limit",
        "window_not_symmetric_whole_minutes",
        "cut_ignores_printed_job",
        "window_under_the_sheet_floor",
        "window_not_tight",
        "sheets_used_disagrees",
        "window_does_not_hold_its_class",
        "window_without_support",
        "candidate_execution_failed",
    ),
    "windows_invariant_to_pull_and_drop": (
        "windows_track_the_pull",
        "rate_tracks_the_pull",
        "dropped_class_hardcoded",
        "candidate_execution_failed",
    ),
    "next_visit_feasible_and_reaches_the_unsheeted_class": (
        "visit_is_not_a_booking_or_a_stop",
        "visit_off_roster",
        "visit_skips_the_class_with_no_sheets",
        "visit_when_every_class_prints",
        "visit_over_the_desk_caps",
        "visit_over_budget",
        "visit_wastes_night_capacity",
        "stops_with_a_class_unprintable",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "visits_are_not_a_list",
        "refusal_uncounted",
        "visit_missing_from_the_report",
        "visit_not_on_the_receipts",
        "visit_counted_twice",
        "class_disagrees_with_the_receipt",
        "jobs_disagree_with_the_receipt",
        "units_disagree_with_the_receipt",
        "units_left_disagrees",
        "candidate_execution_failed",
    ),
}

CURRENT_DEPOT = str(workload.CURRENT_SPEC["depot"])


ARCHIVED: Mapping[str, tuple[tuple[str, int, str, int], ...]] = {
    "halstow-2026-07": (
        ("hal-w9-meter", 9, "meter-exchange", 6),
        ("hal-w9-pressure", 9, "pressure-test", 6),
    ),
    "bewick-2026-07": (
        ("bew-w9-leak", 9, "leak-survey", 6),
        ("bew-w10-leak", 10, "leak-survey", 6),
    ),
    "cranmoor-2026-07": (
        ("cra-w9-boiler", 9, "boiler-service", 6),
        ("cra-w9-pressure", 9, "pressure-test", 6),
    ),
    "dorley-2026-06": (("dor-w9-pressure", 9, "pressure-test", 6),),
    "elverton-2026-06": (
        ("elv-w9-regulator", 9, "regulator-swap", 6),
        ("elv-w10-regulator", 10, "regulator-swap", 6),
    ),
    "fairhaven-2026-06": (
        ("fai-w9-pressure", 9, "pressure-test", 6),
        ("fai-w9-meter", 9, "meter-exchange", 6),
    ),
    "garrow-2026-06": (("gar-w9-meter", 9, "meter-exchange", 6),),
}


def archived_receipts(depot: world.Depot) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for receipt_id, week, job_class, jobs in ARCHIVED[depot.depot]:
        receipts = desk.book(depot, receipts, week, job_class, jobs, receipt_id)
    return receipts


def opening_receipts() -> dict[str, Any]:
    depot = workload.current()
    return desk.receipts_document(depot, archived_receipts(depot))


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return desk.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], steps: int = 2
) -> list[dict[str, Any]]:
    "Every state of this depot's grant, with what it can still book."

    states = [{"label": "now", "receipts": [dict(item) for item in receipts]}]
    held = [dict(item) for item in receipts]
    for step in range(steps):
        plan = oracle.one_allowed_plan(depot, held)
        if plan == "stop":
            break
        held = desk.book(
            depot, held, plan["week"], plan["job_class"], plan["jobs"], f"walk-{step + 1}"
        )
        states.append({"label": f"after {len(held)} receipts", "receipts": held})


    refused = [dict(item) for item in receipts]
    for week in depot.spec["visit_weeks"]:
        while (
            sum(1 for item in refused if int(item["week"]) == int(week))
            < int(depot.spec["visits_per_week"])
            and oracle.can_afford(depot, refused)
        ):
            off = next(
                (
                    name for name in depot.classes
                    if week not in depot.spec["roster"].get(name, ())
                ),
                None,
            )
            if off is None:
                break
            refused = desk.book(
                depot, refused, int(week), off,
                int(depot.spec["jobs_per_visit"]),
                f"reachable-refusal-{week}-{len(refused) + 1}",
            )
    if len(refused) > len(receipts):
        states.append({"label": "after refused requests", "receipts": refused})
    wanted = oracle.wanted_class(depot, receipts)
    weeks = oracle.open_weeks(depot, receipts, wanted or "")
    if wanted and weeks:


        filled = [dict(item) for item in receipts]
        others = [
            name
            for name in depot.classes
            if name != wanted and weeks[0] in depot.spec["roster"].get(name, ())
        ]
        for index, name in enumerate((others * 2)[:2]):
            filled = desk.book(depot, filled, weeks[0], name, 6, f"full-{index + 1}")
        if desk.visits_in_week(filled, weeks[0]) >= int(depot.spec["visits_per_week"]):
            states.append({"label": f"week {weeks[0]} full", "receipts": filled})
    waiting = oracle.unprintable_classes(depot, receipts)
    if wanted and len(waiting) > 1:


        blocked = [dict(item) for item in receipts]
        for week in oracle.open_weeks(depot, blocked, wanted):
            others = [
                name
                for name in depot.classes
                if name != wanted and week in depot.spec["roster"].get(name, ())
            ]
            while (
                others
                and desk.visits_in_week(blocked, week)
                < int(depot.spec["visits_per_week"])
                and oracle.can_afford(depot, blocked)
            ):
                before = desk.visits_in_week(blocked, week)
                blocked = desk.book(
                    depot,
                    blocked,
                    week,
                    others[before % len(others)],
                    int(depot.spec["jobs_per_visit"]),
                    f"blocked-{week}-{before + 1}",
                )
                if desk.visits_in_week(blocked, week) == before:
                    break
        if (
            not oracle.open_weeks(depot, blocked, wanted)
            and oracle.actionable_class(depot, blocked) is not None
            and oracle.can_afford(depot, blocked)
        ):
            states.append(
                {"label": "largest waiting class roster full", "receipts": blocked}
            )


    burnt = [dict(item) for item in receipts]
    for step in range(60):
        if not oracle.can_afford(depot, burnt):
            break
        off = next(
            (
                (name, week)
                for name in depot.classes
                for week in depot.spec["visit_weeks"]
                if week not in depot.spec["roster"].get(name, ())
            ),
            None,
        )
        if off is None:
            break
        burnt = desk.book(depot, burnt, off[1], off[0], 6, f"burn-{step + 1}")
    states.append({"label": "grant spent", "receipts": burnt})
    return states


TWINS: Mapping[str, tuple[Mapping[str, int], tuple[str, float]]] = {
    "halstow-2026-07": (
        {
            "meter-exchange": 8,
            "mains-repair": 16,
            "leak-survey": 12,
            "pressure-test": 12,
            "boiler-service": 10,
            "valve-replacement": 12,
            "hydrant-check": 12,
        },
        ("leak-survey", 62.0),
    ),
    "cranmoor-2026-07": (
        {
            "meter-exchange": 14,
            "mains-repair": 8,
            "leak-survey": 9,
            "boiler-service": 16,
            "pressure-test": 12,
            "hydrant-check": 12,
            "valve-replacement": 12,
        },
        ("mains-repair", 96.0),
    ),
    "fairhaven-2026-06": (
        {
            "mains-repair": 9,
            "meter-exchange": 16,
            "pressure-test": 12,
            "leak-survey": 14,
            "hydrant-check": 8,
            "valve-replacement": 12,
        },
        ("meter-exchange", 58.0),
    ),
}


def twins(depot: world.Depot) -> list[dict[str, Any]]:
    'The same month with the paperwork drawn another way.'

    entry = TWINS.get(depot.depot)
    if entry is None:
        return []
    pull, (job_class, scale) = entry
    return [
        {"kind": "pull", "depot": workload.depot(workload.with_pull(depot.spec, pull))},
        {
            "kind": "swap",
            "depot": workload.depot(workload.with_rescoped(depot.spec, job_class, scale)),
        },
    ]


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "depot": workload.current(),
            "receipts": [dict(item) for item in live],
            "steps": 3,
        }
    ]
    for depot in (*workload.following(), workload.lifted()):
        rows.append({"depot": depot, "receipts": archived_receipts(depot), "steps": 2})
    return rows


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident the owner can open her own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("depot") == CURRENT_DEPOT else 1,
    )


def _twin_failures(
    base: world.Depot,
    twin: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    here: Mapping[str, Any],
    there: Mapping[str, Any],
) -> list[dict[str, Any]]:
    depot = twin["depot"]
    mine = checks.windows_of(here, base)
    theirs = checks.windows_of(there, depot)
    if mine is None or theirs is None:
        return []
    place = checks.where(base)
    if twin["kind"] == "swap":


        if set(base.classes) - set(mine) != set(oracle.unprintable_classes(base, receipts)):
            return []
        wanted = set(oracle.unprintable_classes(depot, receipts))
        printed = set(theirs)
        left_out = set(depot.classes) - printed
        if left_out != wanted:
            missed = sorted(left_out ^ wanted) or ["none"]


            halted = [name for name in depot.classes if oracle.stopped(depot, name)]
            return [
                checks.fail(
                    "dropped_class_hardcoded",
                    **place,
                    job_class=missed[0],
                    left_out=", ".join(sorted(left_out)) or "nothing",
                    stopped_class=", ".join(sorted(halted)) or "nothing",
                )
            ]
        return []
    found: list[dict[str, Any]] = []
    if set(mine) != set(theirs):
        moved = sorted(set(mine) ^ set(theirs))
        found.append(
            checks.fail(
                "windows_track_the_pull",
                **place,
                job_class=moved[0],
                moved=int(oracle.WINDOW_MOVE),
                reported_window=checks.minutes(list(mine.get(moved[0], theirs[moved[0]]))),
                other_window="nothing at all",
            )
        )
    for name in sorted(set(mine) & set(theirs)):
        drift = max(abs(mine[name][0] - theirs[name][0]), abs(mine[name][1] - theirs[name][1]))
        if drift > oracle.WINDOW_MOVE:
            found.append(
                checks.fail(
                    "windows_track_the_pull",
                    **place,
                    job_class=name,
                    moved=int(round(drift)),
                    reported_window=checks.minutes(list(mine[name])),
                    other_window=checks.minutes(list(theirs[name])),
                )
            )
    here_rate = checks.number(here.get("stream_rate"))
    there_rate = checks.number(there.get("stream_rate"))
    if (
        not found
        and here_rate is not None
        and there_rate is not None
        and abs(here_rate - there_rate) > oracle.RATE_MOVE
    ):
        found.append(
            checks.fail(
                "rate_tracks_the_pull",
                **place,
                job_class="every class",
                moved=int(round(abs(here_rate - there_rate) * 100.0)),
                reported_window=checks.points(here_rate),
                other_window=checks.points(there_rate),
            )
        )
    return found[:1]


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every depot and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        from .evaluation import run_delivery

        return run_delivery(Path(artifact_dir))

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
