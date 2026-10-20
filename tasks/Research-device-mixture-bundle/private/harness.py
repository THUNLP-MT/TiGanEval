'Read one delivered board pack against the fleets it is a pack about.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis


from . import checks, desk, oracle, reading, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-mixture-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "fleet_number_within_tolerance",
    "range_covers_and_meets_floor",
    "number_invariant_to_capture_mix_and_rollout",
    "next_capture_feasible_and_informative",
    "report_reconciles_receipts",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "fleet_number_within_tolerance": (
        "pooled_over_the_log",
        "rows_scored_as_captured",
        "profiles_averaged_not_worst",
        "bundle_is_not_the_registers",
        "fleet_number_disagrees",
        "bundle_not_lowest_printed",
        "bundle_numbers_missing",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "number_outside_its_range",
        "range_below_floor",
        "range_wider_than_the_rows_leave",
        "range_rows_disagree",
        "range_undercovers",
        "deciding_bay_not_named",
        "candidate_execution_failed",
    ),
    "number_invariant_to_capture_mix_and_rollout": (
        "moves_with_capture_reach",
        "moves_with_rollout_share",
        "candidate_execution_failed",
    ),
    "next_capture_feasible_and_informative": (
        "capture_is_not_a_request_or_a_stop",
        "capture_below_minimum",
        "capture_repeats_counter",
        "capture_names_an_empty_cell",
        "capture_over_cap",
        "capture_over_credits",
        "stopped_with_credits_left",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "requests_are_not_a_list",
        "receipt_missing",
        "refusal_uncounted",
        "request_not_on_the_receipts",
        "request_counted_twice",
        "rows_above_the_receipt",
        "line_disagrees_with_the_receipt",
        "credits_disagree_with_the_receipts",
        "candidate_execution_failed",
    ),
}

CURRENT_CAMPAIGN = str(workload.CURRENT_SPEC["campaign"])


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident the owner can open his own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign") == CURRENT_CAMPAIGN else 1,
    )


def opening_receipts() -> dict[str, Any]:
    'The requests this campaign had already made when it was handed over.'

    fleet = workload.current()
    entries: list[dict[str, Any]] = []
    for receipt_id, profile, firmware, condition, rows, day in (
        ("hg-counter-1", "counter", "4.1", "bright", 120, "2026-07-02"),
        ("hg-counter-2", "counter", "4.1", "glare", 120, "2026-07-20"),
        ("hg-damaged", "counter", "4.2", "damaged", 60, "2026-08-14"),
        ("hg-oversize", "backroom", "4.1", "dim", 150, "2026-08-17"),
    ):
        entries = desk.book(
            fleet, entries, profile, firmware, condition, rows, receipt_id, day
        )
    return desk.receipts_document(fleet, entries)


def archived_receipts(fleet: world.Fleet) -> list[dict[str, Any]]:
    "What a later fleet's campaign had already paid for."

    entries: list[dict[str, Any]] = []
    prefix = fleet.fleet[:2]
    for receipt_id, profile, firmware, condition, rows in (
        (f"{prefix}-counter-1", "counter", "4.1", "bright", 120),
        (f"{prefix}-refused", "counter", "4.1", "damaged", 40),
    ):
        entries = desk.book(fleet, entries, profile, firmware, condition, rows, receipt_id)
    return entries


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return desk.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    fleet: world.Fleet, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "Every state of this campaign's grant, with what it can still pay for."

    states = [{"label": "now", "receipts": [dict(item) for item in entries]}]
    held = [dict(item) for item in entries]
    for step in range(3):
        plan = oracle.one_allowed_plan(fleet, held)
        if plan == "stop":
            break
        held = desk.book(
            fleet, held, plan["duty_profile"], plan["firmware"], plan["condition"],
            int(plan["rows"]), f"walk-{step + 1}",
        )
        states.append(
            {"label": f"after {len(held)} requests", "receipts": [dict(item) for item in held]}
        )

    refused = desk.book(
        fleet, [dict(item) for item in entries], "counter", "4.1", "damaged", 200, "turned-away"
    )
    states.append({"label": "after a refusal", "receipts": refused})
    burnt = [dict(item) for item in entries]
    for step in range(24):
        left = oracle.credits_left(fleet, burnt)
        if left < int(desk.terms(fleet)["refusal_charge"]):
            break
        rows = min(120, max(1, left // 1))
        burnt = desk.book(fleet, burnt, "counter", "4.1", "bright", rows, f"burn-{step + 1}")
    states.append({"label": "grant spent", "receipts": burnt})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Harrowgate with the requests it has paid for, then the fleets after it.'

    rows = [
        {
            "fleet": workload.current(),
            "receipts": [dict(item) for item in live],
            "scored": True,
            "planned": True,
        }
    ]
    for fleet in workload.following():
        rows.append(
            {
                "fleet": fleet,
                "receipts": archived_receipts(fleet),
                "scored": True,
                "planned": True,
            }
        )
    uniform = workload.uniform()
    rows.append(
        {
            "fleet": uniform,
            "receipts": archived_receipts(uniform),
            "scored": True,
            "planned": True,
        }
    )
    for fleet in (workload.reach_redrawn(), workload.rollout_redrawn()):
        rows.append(
            {
                "fleet": fleet,
                "receipts": [dict(item) for item in live],
                "scored": False,
                "planned": False,
            }
        )
    return rows


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
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
    return f"the board pack notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every fleet and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipts_error = live_receipts(Path(artifact_dir))
        rows = cases(entries)
        contexts: list[dict[str, Any]] = []
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[world.Fleet, dict[str, Any], int]] = []
        for row in rows:
            fleet = row["fleet"]
            held = len(contexts)
            contexts.append(fleet.context())
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": held, "receipts": row["receipts"]}
            )
            if not row["planned"]:
                continue
            for state in plan_states(fleet, row["receipts"]):
                plans.append((fleet, state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": held, "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {
                "campaign": CURRENT_CAMPAIGN,
                "requests_charged_for": len(entries),
            }
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the fleets"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        packs: dict[str, dict[str, Any]] = {}
        uncovered: list[dict[str, Any]] = []
        covered = 0
        for row, index in reports:
            fleet, held = row["fleet"], row["receipts"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                for bucket in RUBRICS:
                    if bucket != "next_capture_feasible_and_informative":
                        failures[bucket].append(_stub(error))
                continue
            report = dict(value or {})
            packs[fleet.campaign] = report
            if not row["scored"]:
                continue
            landed = checks.fleet_number(fleet, held, report)
            failures["fleet_number_within_tolerance"].extend(landed)
            shape = checks.published_range(fleet, held, report)
            failures["range_covers_and_meets_floor"].extend(shape)
            if not landed and not shape:
                if checks.range_holds(fleet, report):
                    covered += 1
                else:
                    uncovered.append(checks.undercovers(fleet, held, report))
            failures["report_reconciles_receipts"].extend(
                checks.reconciliation(
                    fleet, held, report,
                    receipts_error if fleet.campaign == CURRENT_CAMPAIGN else None,
                )
            )
        judged = covered + len(uncovered)
        if judged and covered < oracle.COVERAGE_SHARE * judged:
            failures["range_covers_and_meets_floor"].extend(uncovered)

        base = packs.get(CURRENT_CAMPAIGN)
        if base is not None:
            for campaign, kind, label in (
                (
                    str(workload.REACH_REDRAWN_SPEC["campaign"]),
                    "moves_with_capture_reach",
                    "the export written again off the units the app reached this month",
                ),
                (
                    str(workload.ROLLOUT_REDRAWN_SPEC["campaign"]),
                    "moves_with_rollout_share",
                    "the export written again after the rollout was replanned",
                ),
            ):
                other = packs.get(campaign)
                if other is None:
                    continue
                failures["number_invariant_to_capture_mix_and_rollout"].extend(
                    checks.invariance(workload.current(), kind, base, other, label)
                )

        for fleet, state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                failures["next_capture_feasible_and_informative"].append(_stub(error))
                continue
            failures["next_capture_feasible_and_informative"].extend(
                checks.next_capture(fleet, state["receipts"], value)
            )

        analysis: dict[str, Any] = {
            rubric: sorted(records, key=_report_order)
            for rubric, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT_CAMPAIGN,
            "requests_charged_for": len(entries),
            "fleets_read": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _stub(error: str) -> dict[str, Any]:
    return {"kind": CANDIDATE_FAILURE, "error": str(error)}
