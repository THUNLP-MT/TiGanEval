'One delivered notebook, put through every depot, every grant state and every redrawn pull, and bucketed into the five project checks.'

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import CANDIDATE_FAILURE, failed_analysis

from . import checks, desk, harness, oracle, workload


LIFTED_DEPOT = str(workload.LIFTED_SPEC["depot"])

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
    return f"the board notebook stopped part way through: {line[:200]}"


_REPORT_BUCKETS = (
    "stream_rate_within_tolerance",
    "class_windows_hold_and_meet_floor",
    "windows_invariant_to_pull_and_drop",
    "report_reconciles_receipts",
)


def _requests(receipts):
    rows = harness.cases(receipts)
    requests: list[dict[str, Any]] = []
    reports: list[tuple[Mapping[str, Any], int]] = []
    plans: list[tuple[Any, Mapping[str, Any], int]] = []
    twin_jobs: list[tuple[Mapping[str, Any], Mapping[str, Any], int, int]] = []
    for row in rows:
        depot = row["depot"]
        base = len(requests)
        reports.append((row, base))
        requests.append(
            {"kind": "report", "context": depot.context(), "receipts": row["receipts"]}
        )
        for state in harness.plan_states(depot, row["receipts"], int(row["steps"])):
            plans.append((depot, state, len(requests)))
            requests.append(
                {"kind": "plan", "context": depot.context(), "receipts": state["receipts"]}
            )
        for twin in harness.twins(depot):
            twin_jobs.append((row, twin, base, len(requests)))
            requests.append(
                {
                    "kind": "report",
                    "context": twin["depot"].context(),
                    "receipts": row["receipts"],
                }
            )
    return requests, reports, plans, twin_jobs


def run_delivery(artifact_dir: Path) -> Mapping[str, Any]:
    receipts, receipts_error = harness.live_receipts(Path(artifact_dir))
    requests, reports, plans, twin_jobs = _requests(receipts)
    run = harness.PROJECT.invoke(Path(artifact_dir), {"requests": requests})
    if not run.get("ok"):
        analysis = dict(failed_analysis(_console_error(run), tuple(harness.BUCKETS.values())))
        if run.get("diagnostic"):
            analysis["diagnostic"] = str(run["diagnostic"])
        analysis["case"] = {
            "depot": harness.CURRENT_DEPOT,
            "visits_paid_for": len(receipts),
        }
        return analysis

    results = list(run.get("results", ()))
    failures: dict[str, list[dict[str, Any]]] = {name: [] for name in harness.BUCKETS.values()}
    answers: dict[int, Any] = {}
    stopped = False

    def answer(index: int) -> tuple[Any, str | None]:
        if index >= len(results):
            return None, "the notebook returned no answer for one of the depots"
        item = dict(results[index])
        if not item.get("ok"):
            return None, str(item.get("error") or "the notebook stopped")
        return item.get("answer"), None

    holding: list[dict[str, Any]] = []
    for row, index in reports:
        depot = row["depot"]
        value, error = answer(index)
        if error is not None:
            stopped = True
            for bucket in _REPORT_BUCKETS:
                failures[bucket].append(
                    checks.fail(CANDIDATE_FAILURE, **checks.where(depot), error=error)
                )
            continue
        report = dict(value or {})
        answers[index] = report
        windows = checks.windows_of(report, depot)
        failures["stream_rate_within_tolerance"].extend(
            checks.rate_failures(depot, row["receipts"], report, windows)
        )
        shape, held = checks.window_failures(depot, row["receipts"], report, windows)
        failures["class_windows_hold_and_meet_floor"].extend(shape)
        holding.extend(held)
        failures["report_reconciles_receipts"].extend(
            checks.receipt_failures(
                depot,
                row["receipts"],
                report,
                receipts_error if depot.depot == harness.CURRENT_DEPOT else None,
            )
        )


    strict = [
        item
        for item in holding
        if item["depot"] in (harness.CURRENT_DEPOT, LIFTED_DEPOT)
    ]
    elsewhere = {item["depot"] for item in holding} - {harness.CURRENT_DEPOT, LIFTED_DEPOT}
    if strict or len(elsewhere) > 1:
        failures["class_windows_hold_and_meet_floor"].extend(holding)

    for row, twin, base, index in twin_jobs:
        here = answers.get(base)
        there, error = answer(index)
        if error is not None:
            stopped = True
            failures["windows_invariant_to_pull_and_drop"].append(
                checks.fail(
                    CANDIDATE_FAILURE, **checks.where(row["depot"]), error=error
                )
            )
            continue
        if here is None:
            continue
        twin_report = dict(there or {})
        twin_depot = twin["depot"]
        twin_windows = checks.windows_of(twin_report, twin_depot)
        failures["stream_rate_within_tolerance"].extend(
            checks.rate_failures(twin_depot, row["receipts"], twin_report, twin_windows)
        )
        twin_shape, twin_holding = checks.window_failures(
            twin_depot, row["receipts"], twin_report, twin_windows
        )
        failures["class_windows_hold_and_meet_floor"].extend(twin_shape)
        failures["class_windows_hold_and_meet_floor"].extend(twin_holding)
        failures["report_reconciles_receipts"].extend(
            checks.receipt_failures(twin_depot, row["receipts"], twin_report, None)
        )
        failures["windows_invariant_to_pull_and_drop"].extend(
            harness._twin_failures(row["depot"], twin, row["receipts"], here, twin_report)
        )

    followups: list[tuple[Any, Mapping[str, Any], Mapping[str, Any]]] = []
    for depot, state, index in plans:
        if state["label"] == "after refused requests":
            report_broken = any(
                record.get("depot") == depot.depot
                for bucket in (
                    "stream_rate_within_tolerance",
                    "class_windows_hold_and_meet_floor",
                    "report_reconciles_receipts",
                )
                for record in failures[bucket]
            )
            if report_broken:
                continue
        value, error = answer(index)
        if error is not None:
            stopped = True
            failures["next_visit_feasible_and_reaches_the_unsheeted_class"].append(
                checks.fail(CANDIDATE_FAILURE, **checks.where(depot), error=error)
            )
            continue
        problems = checks.plan_failures(depot, state, value)
        failures["next_visit_feasible_and_reaches_the_unsheeted_class"].extend(problems)
        report_broken = any(
            record.get("depot") == depot.depot
            for bucket in (
                "stream_rate_within_tolerance",
                "class_windows_hold_and_meet_floor",
                "report_reconciles_receipts",
            )
            for record in failures[bucket]
        )
        if state["label"] == "now" and not problems and not report_broken:
            preferred = oracle.one_allowed_plan(depot, state["receipts"])
            choices = value if isinstance(value, list) else [value]
            for choice in choices:
                if not isinstance(choice, Mapping) or choice == preferred:
                    continue
                reached = desk.book(
                    depot, state["receipts"], int(choice["week"]),
                    str(choice["job_class"]), int(choice["jobs"]),
                    "candidate-first-choice",
                )
                followups.append((depot, {"label": "after candidate choice", "receipts": reached}, choice))

    if followups:
        followup_run = harness.PROJECT.invoke(
            Path(artifact_dir),
            {"requests": [
                {"kind": "plan", "context": depot.context(), "receipts": state["receipts"]}
                for depot, state, _ in followups
            ]},
        )
        followup_results = list(followup_run.get("results", ())) if followup_run.get("ok") else []
        for offset, (depot, state, _) in enumerate(followups):
            if offset >= len(followup_results) or not followup_results[offset].get("ok"):
                failures["next_visit_feasible_and_reaches_the_unsheeted_class"].append(
                    checks.fail(CANDIDATE_FAILURE, **checks.where(depot), error="the notebook stopped after its own booking")
                )
                continue
            failures["next_visit_feasible_and_reaches_the_unsheeted_class"].extend(
                checks.plan_failures(depot, state, followup_results[offset].get("answer"))
            )

    analysis: dict[str, Any] = {
        rubric: sorted(records, key=harness._report_order)
        for rubric, records in failures.items()
    }
    analysis["case"] = {
        "depot": harness.CURRENT_DEPOT,
        "visits_paid_for": len(receipts),
        "depots_reported": len(reports),
        "notebook_stopped": stopped,
    }
    return analysis
