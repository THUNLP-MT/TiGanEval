'Read one delivered fleet note against the regions it is a note about.'

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
    prefix="tiganeval-fleet-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "build_difference_within_tolerance",
    "range_covers_and_meets_floor",
    "difference_invariant_to_card_and_lease",
    "next_day_feasible_and_informative",
    "report_reconciles_receipts",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "build_difference_within_tolerance": (
        "pools_the_two_cards",
        "exposure_from_the_roster",
        "build_difference_disagrees",
        "compares_across_different_ages",
        "vehicle_months_disagree",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_a_pair",
        "range_excludes_reported_point",
        "range_below_floor",
        "range_wider_than_the_months_support",
        "range_ignores_region_information",
        "range_undercovers",
        "candidate_execution_failed",
    ),
    "difference_invariant_to_card_and_lease": (
        "hardcoded_history",
        "moves_with_the_card_month",
        "moves_with_the_lease_returns",
        "candidate_execution_failed",
    ),
    "next_day_feasible_and_informative": (
        "day_is_not_a_day_or_a_stop",
        "day_off_the_roster",
        "day_over_the_van_cap",
        "day_single_build",
        "day_too_many_builds",
        "day_group_too_small",
        "day_over_the_week_cap",
        "day_over_the_days_granted",
        "day_at_a_depot_already_worked",
        "day_on_a_card_already_read",
        "stopped_with_days_left",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "days_are_not_a_list",
        "receipt_missing",
        "refusal_uncounted",
        "day_not_on_the_receipts",
        "day_counted_twice",
        "days_charged_disagree",
        "candidate_execution_failed",
    ),
}

CURRENT_REGION = str(workload.CURRENT_SPEC["region"])


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident the owner can open her own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("region_id") == CURRENT_REGION else 1,
    )


def _book(region: world.Region, entries, depot, builds, band, vans, day, receipt_id):
    return desk.book(region, entries, depot, builds, band, vans, day, receipt_id)


def starting_receipts(region: world.Region | None = None) -> dict[str, Any]:
    'The three days Ryecourt has already spent, all at the depot that moved.'

    region = region or workload.current()
    change = region.spec.get("card")
    depot = str(change["depot"]) if change else region.depots[0]
    mark = region.spec["van_prefix"]
    entries: list[dict[str, Any]] = []
    entries = _book(region, entries, depot, ["2022-H2"], [0, 60], 25,
                    "2024-03-04", f"{mark}-D1")
    entries = _book(region, entries, depot, ["2021-H2", "2022-H1"], [14, 40], 25,
                    "2024-03-05", f"{mark}-D2")
    entries = _book(region, entries, depot, ["2021-H1", "2021-H2"], [14, 40], 25,
                    "2024-03-06", f"{mark}-D3")
    return desk.receipts_document(region, entries)


ARCHIVED: Mapping[str, tuple[bool, bool]] = {
    "marbeck": (True, False),
    "corriden": (True, False),
    "halloway": (True, True),
    "wexbury": (True, True),
}


def archived_receipts(region: world.Region) -> list[dict[str, Any]]:
    'The days a region had already been charged for when the note went round.'

    moved_card, both_cards = ARCHIVED[region.region]
    change = region.spec.get("card")
    changed = str(change["depot"]) if change else None
    mark = region.spec["van_prefix"]
    entries: list[dict[str, Any]] = []
    first = changed or region.depots[0]
    if moved_card:
        entries = _book(region, entries, first, ["2021-H1", "2021-H2"], [14, 40], 25,
                        "2024-03-05", f"{mark}-A1")
    if both_cards:
        other = next(
            (depot for depot in region.depots if depot != changed), region.depots[-1]
        )
        entries = _book(region, entries, other, ["2021-H1", "2021-H2"], [14, 40], 25,
                        "2024-03-06", f"{mark}-A2")
    return entries


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return desk.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    region: world.Region, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "States of this region's audit, and what it could still book at each."

    states = [{"label": "now", "receipts": [dict(item) for item in entries]}]
    if region.region != CURRENT_REGION:
        return states
    opening = starting_receipts()["entries"]
    states.append({"label": "the day the audit opened", "receipts": [dict(item) for item in opening]})
    handed_back = _book(region, opening, region.depots[0], ["2021-H2"], [14, 40], 25,
                        "2024-03-07", "walk-handed-back")
    states.append({"label": "a day handed back", "receipts": handed_back})


    refused_elsewhere = _book(region, opening, region.depots[1], ["2021-H2"], [14, 40], 25,
                              "2024-03-07", "walk-refused-elsewhere")
    states.append(
        {"label": "a day handed back at a card no day has read", "receipts": refused_elsewhere}
    )
    spent = [dict(item) for item in opening]
    step = 0
    while desk.days_left(region, spent) > 0 and step < 20:
        step += 1
        spent = _book(region, spent, region.depots[0], ["2021-H1", "2021-H2"], [14, 40], 25,
                      f"2024-0{4 + step // 20}-{step:02d}", f"walk-spent-{step}")
    states.append({"label": "the days spent", "receipts": spent})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Ryecourt with the days it has bought, its two redraws, then the rest.'

    rows = [
        {
            "region": workload.current(),
            "receipts": [dict(item) for item in live],
            "scored": True,
            "planned": True,
        }
    ]
    for region in (workload.linthorpe(), workload.wardley()):
        rows.append(
            {
                "region": region,
                "receipts": starting_receipts(region)["entries"],
                "scored": True,
                "planned": False,
            }
        )
    for region in (*workload.following(), workload.lifted()):
        rows.append(
            {
                "region": region,
                "receipts": archived_receipts(region),
                "scored": True,
                "planned": True,
            }
        )
    return rows


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
    return f"the board notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every region and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, unreadable = live_receipts(Path(artifact_dir))
        rows = cases(entries)
        contexts: list[dict[str, Any]] = []
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[world.Region, dict[str, Any], int]] = []
        for row in rows:
            region = row["region"]
            contexts.append(region.context())
            index = len(contexts) - 1
            reports.append((row, len(requests)))
            requests.append({"kind": "report", "context": index, "receipts": row["receipts"]})
            if not row["planned"]:
                continue
            for state in plan_states(region, row["receipts"]):
                plans.append((region, state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": index, "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(Path(artifact_dir), {"contexts": contexts, "requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            location = checks.where(workload.current())
            for bucket in RUBRICS:
                analysis[bucket] = [
                    {**record, **location} for record in analysis.get(bucket, ())
                ]
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"region": CURRENT_REGION, "days_on_file": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the regions"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        readings: dict[str, Any] = {}
        uncovered: list[dict[str, Any]] = []
        range_reports: list[tuple[world.Region, Mapping[str, Any]]] = []
        scored: list[world.Region] = []
        for row, index in reports:
            region = row["region"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                for bucket in RUBRICS:
                    if bucket != "next_day_feasible_and_informative":
                        failures[bucket].append(
                            checks.fail(CANDIDATE_FAILURE, **checks.where(region), error=error)
                        )
                continue
            report = dict(value or {})
            readings[region.region] = report.get("build_difference_points")
            if row["scored"]:
                scored.append(region)
                here = checks.difference_failures(region, report)
                failures["build_difference_within_tolerance"].extend(here)
                shape = checks.range_shape(region, report)
                failures["range_covers_and_meets_floor"].extend(shape)
                if not shape:
                    range_reports.append((region, report))
                if not shape and not here and not checks.range_holds(region, report):
                    uncovered.append(
                        checks.fail(
                            "range_undercovers",
                            **checks.where(region),
                            reported_range=checks.pair(report.get("difference_range")),
                            reported_van_months=round(
                                checks.number(report.get("vehicle_months")) or 0.0
                            ),
                            regions_held=0,
                        )
                    )
            failures["report_reconciles_receipts"].extend(
                checks.receipt_failures(
                    region, row["receipts"], report,
                    unreadable if region.region == CURRENT_REGION else None,
                )
            )
        if uncovered:
            held = len(scored) - len(uncovered)
            for record in uncovered:
                record["regions_held"] = held
            failures["range_covers_and_meets_floor"].extend(uncovered)
        if len(range_reports) == len(scored):
            failures["range_covers_and_meets_floor"].extend(
                checks.range_response_failures(range_reports)
            )

        failures["difference_invariant_to_card_and_lease"].extend(
            checks.invariance_failures(workload.current(), readings)
        )
        failures["difference_invariant_to_card_and_lease"].extend(
            checks.carried_over_failures(scored, readings)
        )

        for region, state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                failures["next_day_feasible_and_informative"].append(
                    checks.fail(CANDIDATE_FAILURE, **checks.where(region), error=error)
                )
                continue
            failures["next_day_feasible_and_informative"].extend(
                checks.plan_failures(region, state["receipts"], value)
            )

        analysis: dict[str, Any] = {
            rubric: sorted(records, key=_report_order) for rubric, records in failures.items()
        }
        analysis["case"] = {
            "region": CURRENT_REGION,
            "days_on_file": len(entries),
            "regions_read": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
