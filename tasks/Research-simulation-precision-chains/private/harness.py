'Read one delivered quarter notebook against the world it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-precision-chains-",
    timeout=120.0,
)
_CACHE = AnalysisCache()

STUDY = workload.CURRENT.study

BUCKETS: Mapping[str, str] = {
    "exceedance_within_tolerance": "share_failures",
    "range_covers_and_meets_floor": "range_failures",
    "report_reconciles_receipts": "ledger_failures",
    "next_run_feasible_and_informative": "plan_failures",
    "estimate_invariant_to_settling_and_lineage": "stability_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "exceedance_within_tolerance": (
        "reports_middle_not_exceedance",
        "settling_rows_retained",
        "lineage_counted_twice",
        "exceedance_disagrees",
        "exceedance_wrong_on_another_study",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_absent",
        "range_outside_share_bounds",
        "range_excludes_answer",
        "range_undercovers",
        "range_narrower_than_floor",
        "range_wider_than_the_draws_support",
        "range_wrong_on_another_study",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "report_is_not_a_ledger",
        "chain_missing",
        "chain_not_on_the_manifest",
        "draws_counted_twice",
        "steps_do_not_add_up",
        "stored_steps_disagree",
        "retention_does_not_match_reading",
        "refusal_uncounted",
        "job_missing",
        "job_not_on_the_ledger",
        "ledger_wrong_on_another_study",
        "candidate_execution_failed",
    ),
    "next_run_feasible_and_informative": (
        "plan_is_not_a_job_or_a_stop",
        "unknown_chain",
        "under_the_minimum_job",
        "exceeds_per_job_cap",
        "over_the_grant",
        "no_stop_when_grant_exhausted",
        "books_after_the_question_is_settled",
        "extends_the_continuation",
        "plan_uninformative",
        "stopped_with_the_grant_open",
        "plan_wrong_on_another_study",
        "plan_buys_nothing_on_another_study",
        "stop_wrong_on_another_study",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_settling_and_lineage": (
        "hardcoded_history",
        "tracks_lineage_pattern",
        "tracks_settling_length",
        "tracks_excursion_length",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "share_failures": ("exceedance_wrong_on_another_study",),
    "range_failures": ("range_wrong_on_another_study",),
    "ledger_failures": ("ledger_wrong_on_another_study",),
    "plan_failures": (
        "plan_wrong_on_another_study",
        "plan_buys_nothing_on_another_study",
        "stop_wrong_on_another_study",
    ),
}


PLAN_CARRY_OVER: Mapping[str, str] = {
    "plan_is_not_a_job_or_a_stop": "plan_wrong_on_another_study",
    "unknown_chain": "plan_wrong_on_another_study",
    "under_the_minimum_job": "plan_wrong_on_another_study",
    "exceeds_per_job_cap": "plan_wrong_on_another_study",
    "over_the_grant": "plan_wrong_on_another_study",
    "no_stop_when_grant_exhausted": "plan_wrong_on_another_study",
    "extends_the_continuation": "plan_wrong_on_another_study",
    "plan_uninformative": "plan_buys_nothing_on_another_study",
    "books_after_the_question_is_settled": "plan_buys_nothing_on_another_study",
    "stopped_with_the_grant_open": "stop_wrong_on_another_study",
}


PLAN_CARRY_OVER_ISSUE: Mapping[str, str] = {
    "plan_is_not_a_job_or_a_stop": "did not identify a runnable job or a stop",
    "unknown_chain": "named a run that quarter does not have",
    "under_the_minimum_job": "asked for fewer steps than its scheduler accepts",
    "exceeds_per_job_cap": "asked for more steps than one job may use",
    "over_the_grant": "asked for more steps than its grant had left",
    "no_stop_when_grant_exhausted": "asked for a job when its grant could not pay the minimum",
    "extends_the_continuation": "put the job on a run opened from another job's checkpoint",
    "plan_uninformative": "would leave a wider range than an affordable fresh job",
    "books_after_the_question_is_settled": "asked for work after its published range had closed the question",
    "stopped_with_the_grant_open": "stopped while its grant could still buy useful work",
}


RANGE_CARRY_OVER_ISSUE: Mapping[str, str] = {
    "range_absent": "was not a usable low-to-high range",
    "range_outside_share_bounds": "ran outside the zero-to-one scale of a share",
    "range_excludes_answer": "did not contain the answer printed beside it",
    "range_undercovers": "missed the quarter's checked share",
    "range_narrower_than_floor": "was narrower than that quarter's collected evidence supports",
    "range_wider_than_the_draws_support": "was wider than that quarter's collected evidence justifies",
}


_NAMING_ORDER: tuple[str, ...] = tuple(
    world.study
    for world in (*workload.SIBLINGS, *workload.PARTNERS, workload.OUT_OF_REGIME)
)


def _naming_rank(study: str) -> int:
    return _NAMING_ORDER.index(study) if study in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _request_fields(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    request_kind: str,
) -> dict[str, Any]:
    'Public provenance for one notebook call that did not return an answer.'

    return {
        "study": world.study,
        "as_of": str(world.spec["as_of"]),
        "request_kind": request_kind,
        "steps_left": int(world.steps_left(receipts)),
    }


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident the group lead can open files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("study") == STUDY else 1,
    )


_RUBRIC_OF_BUCKET: Mapping[str, str] = {bucket: rubric for rubric, bucket in BUCKETS.items()}


def _kind_rank(bucket: str, kind: str) -> int:
    modes = FAILURE_MODES[_RUBRIC_OF_BUCKET[bucket]]
    return modes.index(kind) if kind in modes else len(modes)


def _carry_over_mode(modes: Sequence[str], kind: str) -> str:
    'Which carry-over incident a record of this kind belongs to.'

    if len(modes) == 1:
        return modes[0]
    return PLAN_CARRY_OVER.get(kind, modes[0])


def _written_off_the_live_study(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the quarter the group lead can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [record for record in rows if record.get("study") == STUDY]
    if here:
        return here


    stopped = [
        record for record in rows if str(record.get("kind")) == CANDIDATE_FAILURE
    ]
    if stopped:
        return [
            min(
                stopped,
                key=lambda record: _naming_rank(str(record.get("study", ""))),
            )
        ]
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    lead = min(rows, key=lambda record: _kind_rank(bucket, str(record.get("kind"))))
    mode = _carry_over_mode(modes, str(lead.get("kind")))
    rows = [
        record
        for record in rows
        if _carry_over_mode(modes, str(record.get("kind"))) == mode
    ]
    named = min(
        (record for record in rows if record.get("study")),
        key=lambda record: _naming_rank(str(record["study"])),
        default=rows[0],
    )
    elsewhere = sorted({str(record["study"]) for record in rows if record.get("study")})
    carried = {
        "study": STUDY,
        "other_study": str(named.get("study")),
        "other_studies": len(elsewhere),
    }
    if "steps_left" in named:
        carried["steps_left"] = named["steps_left"]
    if bucket == "range_failures":
        carried["reported_range"] = str(
            named.get("reported_range", named.get("reported", "not usable"))
        )
        carried["range_issue"] = RANGE_CARRY_OVER_ISSUE.get(
            str(named.get("kind")), "failed that quarter's range check"
        )
    if bucket == "plan_failures":
        kind = str(named.get("kind"))
        if "reported" in named:
            reported_plan = _show(named.get("reported"))
        elif kind == "stopped_with_the_grant_open":
            reported_plan = "stop"
        elif "steps" in named:
            reported_plan = f"{_show(named.get('chain_id'))} for {_show(named.get('steps'))} steps"
        else:
            reported_plan = "no runnable job or stop"
        carried["reported_plan"] = reported_plan
        carried["plan_issue"] = PLAN_CARRY_OVER_ISSUE.get(
            kind, "did not fit that quarter's published planning terms"
        )
    return [_fail(mode, **carried)]


def _share(value: Any) -> str:
    return format(float(value), ".3f")


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
        return f"{_share(value[0])} to {_share(value[1])}"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The jobs this delivery has been billed for, or why the stream will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def live_world(entries: Sequence[Mapping[str, Any]]) -> w.World:
    'The quarter as it stands after everything the receipts say has been run.'

    extra = w.jobs_of(entries, workload.OPENING_JOBS[STUDY])
    return w.booked(workload.CURRENT_SPEC, extra) if extra else workload.CURRENT


def _fastest(world: w.World) -> str:
    'The stored run whose proposal scale is largest and which is its own run.'

    own = [chain for chain in world.chains if chain.parent is None]
    return max(own or list(world.chains), key=lambda chain: chain.step_size).chain_id


def spend_to(
    base: w.World,
    jobs: Sequence[Mapping[str, Any]],
    entries: Sequence[Mapping[str, Any]],
    target: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    'The receipts after the grant has been run down to `target` steps left.'

    grown = [dict(entry) for entry in entries]
    made = [dict(item) for item in jobs]
    minimum = int(base.spec["minimum_steps"])
    cap = int(base.spec["cap_steps"])
    left = base.steps_left(grown)
    while left - target >= minimum:
        size = min(cap, left - target)
        before = w.booked(base.spec, made)
        chain_id = _fastest(before)
        init_source = w.manifest_source(before, chain_id, False)
        made.append({"chain_id": chain_id, "steps": size})
        left -= size
        grown.append(
            w.receipt(
                base.study, len(grown) + 1, f"fill-{len(grown) + 1:02d}",
                f"j-48{len(grown) + 1:02d}", chain_id, init_source,
                size, size, size, None, False, left,
                grown[-1]["seal"] if grown else "",
            )
        )
    return grown, made


def spend_below_minimum(
    base: w.World, jobs: Sequence[Mapping[str, Any]], entries: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    'One refused job on top of the tight state, which leaves too little to run.'

    grown = [dict(entry) for entry in entries]
    left = base.steps_left(grown)
    if left <= 0:
        return grown, [dict(item) for item in jobs]
    charge = min(int(base.spec["refused_job_steps"]), left)
    grown.append(
        w.receipt(
            base.study, len(grown) + 1, f"fill-{len(grown) + 1:02d}",
            f"j-48{len(grown) + 1:02d}", None, "dispersed-init",
            200, 0, charge, w.refusal_reason(base, None, True, 200, left), True,
            left - charge, grown[-1]["seal"] if grown else "",
        )
    )
    return grown, [dict(item) for item in jobs]


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The quarter under review, then the ones the same notebook is run over next.'

    live = live_world(entries)
    base = workload.CURRENT
    own = [dict(item) for item in entries]
    baseline_entries = w.opening_stream(base)
    baseline_jobs: list[dict[str, Any]] = []
    half_target = int(base.steps_left(baseline_entries)) // 2
    half_entries, half_jobs = spend_to(
        base, baseline_jobs, baseline_entries, half_target
    )
    tight_entries, tight_jobs = spend_to(
        base, baseline_jobs, baseline_entries, int(base.spec["minimum_steps"])
    )
    empty_entries, empty_jobs = spend_below_minimum(base, tight_jobs, tight_entries)
    half_world = w.booked(workload.CURRENT_SPEC, half_jobs) if half_jobs else base
    tight_world = w.booked(workload.CURRENT_SPEC, tight_jobs) if tight_jobs else base


    candidates = (
        {"world": live, "receipts": own},
        {"world": base, "receipts": baseline_entries},
        {"world": half_world, "receipts": half_entries},
        {"world": tight_world, "receipts": tight_entries},
        {"world": tight_world, "receipts": empty_entries},
    )
    live_plans: list[dict[str, Any]] = []
    seen_states: set[tuple[str, tuple[str, ...]]] = set()
    for state in candidates:
        key = (
            state["world"].study,
            tuple(str(entry.get("seal", "")) for entry in state["receipts"]),
        )
        if key not in seen_states:
            seen_states.add(key)
            live_plans.append(state)
    rows: list[dict[str, Any]] = [
        {
            "label": live.study,
            "world": live,
            "receipts": own,
            "plans": live_plans,
        }
    ]
    for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME, *workload.PARTNERS):
        receipts = w.opening_stream(world)
        rows.append(
            {
                "label": world.study,
                "world": world,
                "receipts": receipts,
                "plans": [{"world": world, "receipts": receipts}],
            }
        )
    return rows


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str, **fields: Any) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(
                0, _fail(CANDIDATE_FAILURE, error=error, **fields)
            )


_MISREADINGS = (
    ("reports_middle_not_exceedance", ("middle_of_the_draws",)),
    ("settling_rows_retained", ("settling_retained", "everything_pooled")),
    ("lineage_counted_twice", ("lineage_counted_twice",)),
)


def explanation(readings: Mapping[str, float], worlds: Mapping[str, w.World]) -> str | None:
    'The one misreading that accounts for this delivery on most of the quarters.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = sum(
            1
            for study, value in readings.items()
            if study in worlds
            and any(
                _near(value, oracle.misreadings(worlds[study])[family], oracle.CLASSIFY_SLACK)
                for family in families
            )
        )
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _check_share(
    review: Review, world: w.World, report: Mapping[str, Any], mode: str | None
) -> None:
    "The share has to be the model's own, or what this quarter's kept draws say."

    truth = oracle.truth(world)
    reported = report.get("answer")
    if _near(reported, truth, oracle.TOLERANCE) or _near(
        reported, oracle.reading(world), oracle.TOLERANCE
    ):
        return
    shared = {
        "study": world.study,
        "reported": _share(reported) if _number(reported) is not None else _show(reported),
    }
    if _number(reported) is None or mode is None:
        review.add("share_failures", "exceedance_disagrees", **shared,
                   peak_wait_s=_show(float(world.spec["threshold_s"])))
        return
    if mode == "reports_middle_not_exceedance":
        review.add(
            "share_failures", mode, **shared,
            peak_wait_s=_show(float(world.spec["threshold_s"])),
            commitment_share=f"{float(world.spec['commitment_share']) * 100:g} per cent",
        )
        return
    if mode == "settling_rows_retained":
        chain_id, settle = _longest_settle(world)
        review.add("share_failures", mode, **shared, chain_id=chain_id, settling_steps=settle)
        return
    child, parent = _resubmitted(world)
    review.add("share_failures", mode, **shared, chain_id=child, other_chain=parent)


def _longest_settle(world: w.World) -> tuple[str, int]:
    chain = max(world.chains, key=lambda item: item.settle)
    return chain.chain_id, int(chain.settle)


def _resubmitted(world: w.World) -> tuple[str, str]:
    for chain in world.chains:
        if chain.parent is not None:
            return chain.chain_id, str(chain.parent)
    return world.chains[0].chain_id, world.chains[0].chain_id


def _check_range(review: Review, world: w.World, report: Mapping[str, Any]) -> bool:
    'The width the draws a report says it kept support. Returns whether it holds.'

    reported = report.get("answer_range")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or reported[0] > reported[1]
    ):
        review.add("range_failures", "range_absent", study=world.study,
                   reported=_pair(reported))
        return True
    if float(reported[0]) < 0.0 or float(reported[1]) > 1.0:
        review.add(
            "range_failures",
            "range_outside_share_bounds",
            study=world.study,
            reported_range=_pair(reported),
        )
    answer = _number(report.get("answer"))
    if answer is not None and not (float(reported[0]) <= answer <= float(reported[1])):
        review.add(
            "range_failures",
            "range_excludes_answer",
            study=world.study,
            reported=_share(answer),
            reported_range=_pair(reported),
        )


    kept = float(oracle.steps_kept(world))
    supported = oracle.supported(world, kept)
    width = (float(reported[1]) - float(reported[0])) / 2.0
    fields = {
        "study": world.study,
        "reported_range": _pair(reported),
        "steps_kept": int(kept),
    }
    if width < supported * oracle.NARROW_FACTOR:
        review.add("range_failures", "range_narrower_than_floor", **fields)
    elif width > supported * oracle.WIDE_FACTOR:
        review.add("range_failures", "range_wider_than_the_draws_support", **fields)
    truth = oracle.truth(world)
    return float(reported[0]) <= truth <= float(reported[1])


def _check_ledger(
    review: Review,
    world: w.World,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    error: str | None,
) -> None:
    if error:
        review.add("ledger_failures", "receipts_unreadable", study=world.study, reason=str(error))
        return
    runs = report.get("runs")
    jobs = report.get("jobs")
    if not isinstance(runs, list) or not isinstance(jobs, list):
        review.add("ledger_failures", "report_is_not_a_ledger", study=world.study,
                   reported=_show(runs if not isinstance(runs, list) else jobs),
                   runs_stored=len(world.chains))
        return
    stored = {chain.chain_id: int(chain.steps_stored) for chain in world.chains}
    chains = {chain.chain_id: chain for chain in world.chains}
    retained = {
        chain_id: (kept, stored[chain_id] - kept)
        for chain_id, kept, _crossings, _turnover in oracle.kept_counts(world)
    }
    seen: dict[str, int] = {}
    for row in runs:
        chain_id = str(row.get("chain_id"))
        seen[chain_id] = seen.get(chain_id, 0) + 1
        if seen[chain_id] > 1:
            review.add("ledger_failures", "draws_counted_twice", study=world.study,
                       line_id=chain_id, times_reported=seen[chain_id])
            return
    for chain_id, steps in stored.items():
        if chain_id not in seen:
            review.add("ledger_failures", "chain_missing", study=world.study,
                       chain_id=chain_id, steps_stored=steps, runs_stored=len(stored))
            return
    for row in runs:
        chain_id = str(row.get("chain_id"))
        steps = stored.get(chain_id)
        kept = _number(row.get("steps_kept"))
        aside = _number(row.get("steps_set_aside"))
        told = _number(row.get("steps_stored"))
        if steps is None:
            review.add("ledger_failures", "chain_not_on_the_manifest", study=world.study,
                       chain_id=chain_id, runs_stored=len(stored))
            return
        if (
            kept is None
            or aside is None
            or kept < 0
            or aside < 0
            or not kept.is_integer()
            or not aside.is_integer()
            or kept + aside != steps
        ):
            review.add("ledger_failures", "steps_do_not_add_up", study=world.study,
                       chain_id=chain_id, steps_stored=steps,
                       reported_kept=_show(row.get("steps_kept")),
                       reported_set_aside=_show(row.get("steps_set_aside")))
            return
        if told is None or not told.is_integer() or int(told) != steps:
            review.add("ledger_failures", "stored_steps_disagree", study=world.study,
                       chain_id=chain_id, steps_stored=steps,
                       reported_stored=_show(row.get("steps_stored")))
            return
    mismatch = next(
        (
            row
            for row in runs
            if (
                int(float(row["steps_kept"])),
                int(float(row["steps_set_aside"])),
            )
            != retained[str(row["chain_id"])]
        ),
        None,
    )
    if mismatch is not None:
        chain_id = str(mismatch["chain_id"])
        expected_kept, expected_aside = retained[chain_id]
        claimed_kept = 0
        claimed_crossings = 0
        for row in runs:
            chain = chains[str(row["chain_id"])]
            aside = int(float(row["steps_set_aside"]))
            block = chain.crossing[aside:]
            claimed_kept += int(block.size)
            claimed_crossings += int(block.sum())
        implied = claimed_crossings / claimed_kept if claimed_kept else None
        review.add(
            "ledger_failures",
            "retention_does_not_match_reading",
            study=world.study,
            chain_id=chain_id,
            reported_kept=int(float(mismatch["steps_kept"])),
            reported_set_aside=int(float(mismatch["steps_set_aside"])),
            expected_kept=expected_kept,
            expected_set_aside=expected_aside,
            steps_kept=claimed_kept,
            reported=_share(report.get("answer"))
            if _number(report.get("answer")) is not None
            else _show(report.get("answer")),
            implied="no reading" if implied is None else _share(implied),
        )
        return
    total_kept = sum(_number(row.get("steps_kept")) or 0.0 for row in runs)
    total_aside = sum(_number(row.get("steps_set_aside")) or 0.0 for row in runs)
    if not _near(report.get("steps_kept"), total_kept, 0.0) or not _near(
        report.get("steps_set_aside"), total_aside, 0.0
    ):
        review.add("ledger_failures", "steps_do_not_add_up", study=world.study,
                   chain_id="the whole quarter", steps_stored=sum(stored.values()),
                   reported_kept=_show(report.get("steps_kept")),
                   reported_set_aside=_show(report.get("steps_set_aside")))
        return


    answer = _number(report.get("answer"))
    if answer is not None and 0.0 <= answer <= 1.0:
        claimed_kept = 0
        claimed_crossings = 0
        for row in runs:
            chain_id = str(row.get("chain_id"))
            chain = chains[chain_id]
            aside = int(float(row["steps_set_aside"]))
            block = chain.crossing[aside:]
            claimed_kept += int(block.size)
            claimed_crossings += int(block.sum())
        implied = claimed_crossings / claimed_kept if claimed_kept else None
        if implied is None or not _near(answer, implied, oracle.TOLERANCE):
            review.add(
                "ledger_failures",
                "retention_does_not_match_reading",
                study=world.study,
                reported=_share(answer),
                implied="no reading" if implied is None else _share(implied),
                steps_kept=int(claimed_kept),
            )
            return
    billed = {str(entry["call_id"]): entry for entry in receipts}
    counted: dict[str, int] = {}
    for row in jobs:
        call_id = str(row.get("call_id"))
        counted[call_id] = counted.get(call_id, 0) + 1
        if counted[call_id] > 1:
            review.add("ledger_failures", "draws_counted_twice", study=world.study,
                       line_id=call_id, times_reported=counted[call_id])
            return
        entry = billed.get(call_id)
        if entry is None or not _near(row.get("steps_charged"), float(entry["steps_charged"]), 0.0):
            review.add("ledger_failures", "job_not_on_the_ledger", study=world.study,
                       call_id=call_id, billed=len(receipts),
                       reported_charged=_show(row.get("steps_charged")))
            return
        if bool(row.get("refused")) is not bool(entry.get("refusal")):
            review.add("ledger_failures", "refusal_uncounted", study=world.study,
                       call_id=call_id, steps_charged=int(entry["steps_charged"]),
                       billed=len(receipts),
                       console_result="sent back" if entry.get("refusal") else "served")
            return
    for call_id, entry in billed.items():
        if call_id in counted:
            continue
        mode = "refusal_uncounted" if entry.get("refusal") else "job_missing"
        review.add("ledger_failures", mode, study=world.study, call_id=call_id,
                   steps_charged=int(entry["steps_charged"]), billed=len(receipts),
                   console_result="sent back" if entry.get("refusal") else "served")
        return


def _closes_the_question(world: w.World, report: Mapping[str, Any]) -> bool | None:
    'Whether the range this readout published for this quarter closes it.'

    reported = report.get("answer_range")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or float(reported[0]) > float(reported[1])
    ):
        return None
    return oracle.settled(world, float(reported[0]), float(reported[1]))


def _check_plan(
    review: Review,
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    answer: Any,
    report: Mapping[str, Any],
) -> None:
    'The next job has to follow the range this readout published for the quarter.'

    state = oracle.plan_state(world, receipts)
    left = int(state["steps_left"])
    published = _closes_the_question(world, report)
    settled = bool(state["settled"]) if published is None else published
    minimum = int(world.spec["minimum_steps"])
    stop_only = left < minimum or settled
    shared = {
        "study": world.study,
        "steps_left": left,
        "cap_steps": int(world.spec["cap_steps"]),
        "minimum_steps": minimum,
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "plan_is_not_a_job_or_a_stop", **shared,
                   reported=_show(answer))
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "plan_is_not_a_job_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not stop_only:
                review.add("plan_failures", "stopped_with_the_grant_open", **shared)
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "plan_is_not_a_job_or_a_stop", **shared,
                       reported=_show(choice))
            return
        steps = _number(choice.get("steps"))
        raw_chain = choice.get("chain_id")
        start_new = choice.get("start_new")
        names_run = isinstance(raw_chain, str) and bool(raw_chain)
        fresh = start_new is True
        target_is_invalid = (
            not isinstance(start_new, bool)
            or names_run == fresh
            or (raw_chain is not None and not names_run)
        )
        if (
            steps is None
            or not steps.is_integer()
            or steps < 1
            or target_is_invalid
        ):
            review.add("plan_failures", "plan_is_not_a_job_or_a_stop", **shared,
                       reported=_show(f"{_show(choice.get('chain_id'))} for "
                                      f"{_show(choice.get('steps'))} steps"))
            return
        steps = int(steps)
        chain_id = None if fresh else raw_chain
        named = {**shared, "steps": steps,
                 "chain_id": "a run started from scratch" if chain_id is None else chain_id}
        if left < minimum:
            review.add("plan_failures", "no_stop_when_grant_exhausted", **named)
            return
        if settled:
            review.add("plan_failures", "books_after_the_question_is_settled", **named,
                       range_width_wanted=_share(world.spec["range_width_wanted"]))
            return
        if steps < minimum:
            review.add("plan_failures", "under_the_minimum_job", **named)
            return
        if steps > int(world.spec["cap_steps"]):
            review.add("plan_failures", "exceeds_per_job_cap", **named)
            return
        if chain_id is not None and world.chain(chain_id) is None:
            review.add("plan_failures", "unknown_chain", **named,
                       runs_stored=len(world.chains))
            return
        if steps > left:
            review.add("plan_failures", "over_the_grant", **named)
            return
        if chain_id is not None and oracle.is_continuation(world, chain_id):
            _child, parent = _resubmitted(world)
            review.add("plan_failures", "extends_the_continuation", **named,
                       other_chain=parent)
            return
        if oracle.half_width_after(world, chain_id, steps) > float(state["bar"]) * 1.005:
            review.add("plan_failures", "plan_uninformative", **named)
            return


def _check_stability(review: Review, readings: Mapping[str, float]) -> None:
    'A reading has to be the same on every repeat of this quarter.'

    live = readings.get(STUDY)
    if live is None:
        return
    carried = workload.SIBLINGS[3].study
    other = readings.get(carried)
    if (
        other is not None
        and abs(live - other) < 1e-9
        and abs(oracle.truth(workload.CURRENT) - oracle.truth(workload.SIBLINGS[3]))
        > oracle.CARRIED_OVER_GAP
    ):
        review.add("stability_failures", "hardcoded_history", study=STUDY,
                   other_study=carried, reported=_share(live))
        return
    baseline = readings.get(workload.BASELINE_PARTNER.study)
    if baseline is None:
        return
    moved = [
        (abs(baseline - readings[partner.study]), mode, partner)
        for mode, partner in (
            ("tracks_lineage_pattern", workload.LINEAGE_PARTNER),
            ("tracks_settling_length", workload.SETTLING_PARTNER),
            ("tracks_excursion_length", workload.EXCURSION_PARTNER),
        )
        if partner.study in readings
    ]
    if not moved:
        return


    distance, mode, partner = max(moved)
    if distance > oracle.INVARIANCE_SLACK:
        review.add(
            "stability_failures",
            mode,
            study=STUDY,
            other_study=partner.study,
            baseline_study=workload.BASELINE_PARTNER.study,
            reported=_share(readings[partner.study]),
            other_reported=_share(baseline),
            moved_by=_share(distance),
        )


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
    return f"the quarter notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every quarter and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipts_error = live_receipts(Path(artifact_dir))
        rows = instances(entries)
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(world: w.World) -> int:
            if id(world) not in seen:
                seen[id(world)] = len(contexts)
                contexts.append(world.context())
            return seen[id(world)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        state_reports: list[tuple[Mapping[str, Any], int]] = []
        plans: list[tuple[Mapping[str, Any], int, int]] = []
        for row in rows:
            here = len(requests)
            reports.append((row, here))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "receipts": row["receipts"]}
            )
            for state in row["plans"]:


                if state["world"] is row["world"] and state["receipts"] is row["receipts"]:
                    read = here
                else:
                    read = len(requests)
                    state_reports.append((state, read))
                    requests.append(
                        {"kind": "report", "context": context_index(state["world"]),
                         "receipts": state["receipts"]}
                    )
                plans.append((state, len(requests), read))
                requests.append(
                    {"kind": "plan", "context": context_index(state["world"]),
                     "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            provenance = _request_fields(
                workload.CURRENT, entries, "the quarterly notebook batch"
            )
            for bucket in BUCKETS.values():
                for record in analysis[bucket]:
                    record.update(provenance)
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"study": STUDY, "jobs_billed": len(entries)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the quarters"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        readings: dict[str, float] = {}
        worlds: dict[str, w.World] = {}
        for row, index in reports:
            value, _error = answer(index)
            reading = _number(dict(value or {}).get("answer")) if value else None
            if reading is not None:
                readings[row["world"].study] = reading
                worlds[row["world"].study] = row["world"]
        mode = explanation(readings, worlds)
        held: list[bool] = []
        stopped = False
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("share_failures", "range_failures", "ledger_failures",
                     "stability_failures"),
                    error,
                    **_request_fields(world, row["receipts"], "quarterly readout"),
                )
                continue
            report = dict(value or {})
            _check_share(review, world, report, mode)
            held.append(_check_range(review, world, report))
            _check_ledger(
                review, world, report, row["receipts"],
                receipts_error if world.study == STUDY else None,
            )


        for state, index in state_reports:
            world = state["world"]
            receipts = state["receipts"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("share_failures", "range_failures", "ledger_failures"),
                    error,
                    **_request_fields(world, receipts, "collection-state readout"),
                )
                continue
            report = dict(value or {})
            _check_share(review, world, report, mode)
            _check_range(review, world, report)
            _check_ledger(review, world, report, receipts, None)
        for state, index, read in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("plan_failures",),
                    error,
                    **_request_fields(
                        state["world"], state["receipts"], "next-job decision"
                    ),
                )
                continue
            printed, unread = answer(read)
            if unread is not None:
                stopped = True
                review.stopped(
                    ("plan_failures",),
                    unread,
                    **_request_fields(
                        state["world"],
                        state["receipts"],
                        "readout used for the next-job decision",
                    ),
                )
                continue
            _check_plan(
                review, state["world"], state["receipts"], value, dict(printed or {})
            )
        if held and sum(held) < oracle.COVERAGE * len(held):
            for row, index in reports:
                value, error = answer(index)
                if error is not None:
                    continue
                span = dict(value or {}).get("answer_range")
                truth = oracle.truth(row["world"])
                if (
                    isinstance(span, list)
                    and len(span) == 2
                    and all(_number(item) is not None for item in span)
                    and not (float(span[0]) <= truth <= float(span[1]))
                ):
                    review.add(
                        "range_failures",
                        "range_undercovers",
                        study=row["world"].study,
                        reported_range=_pair(span),
                        quarters_reviewed=len(held),
                        quarters_held=sum(held),
                    )
        _check_stability(review, readings)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_study(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "study": STUDY,
            "jobs_billed": len(entries),
            "quarters_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a session record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    "The quarter's files as they stood on the day of one working session."

    steps = {str(key): int(value) for key, value in dict(record["chain_steps"]).items()}
    context = world.context()
    context["as_of"] = str(record["date"])
    context["chains"] = [
        chain.truncated(steps[chain.chain_id]).entry()
        for chain in world.chains
        if chain.chain_id in steps and steps[chain.chain_id] > 0
    ]
    return context


def _summary_rows(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    "Per run, what the reporting job prints on the quarter's summary table."

    threshold = float(context["commitment"]["peak_wait_s"])
    rows = []
    for chain in context["chains"]:
        draws = chain["draws"]
        peaks = draws["peak_wait_s"]
        scales = draws["step_size"]
        over = sum(1 for value in peaks if value > threshold)
        rows.append(
            {
                "chain_id": chain["chain_id"],
                "node": chain["node"],
                "job_id": chain["job_id"],
                "init_source": chain["init_source"],
                "steps_stored": len(peaks),
                "steps_over_2_5s": over,
                "mean_peak_wait_s": round(sum(peaks) / len(peaks), 4) if peaks else None,
                "max_peak_wait_s": round(max(peaks), 4) if peaks else None,
                "first_step_size": scales[0] if scales else None,
                "last_step_size": scales[-1] if scales else None,
                "accepted": sum(draws["accepted"]),
            }
        )
    return rows


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
            **{key: raw.get(key) for key in ("session", "date", "analyst")},
        })
    return {
        "summary": (
            f"The {context['study']} study, the charter's terms and the working sessions "
            "on record."
        ),
        "measurements": {
            "study": context["study"],
            "quarter": context["quarter"],
            "as_of": context["as_of"],
            "commitment": context["commitment"],
            "budget": context["budget"],
            "steps_charged": world.steps_charged(entries),
            "steps_left": world.steps_left(entries),
            "runs": _summary_rows(context),
            "jobs_on_the_ledger": [
                {
                    "call_id": item["call_id"],
                    "job_id": item["job_id"],
                    "chain_id": item["chain_id"],
                    "steps_requested": item["steps_requested"],
                    "steps_returned": item["steps_returned"],
                    "steps_charged": item["steps_charged"],
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
    receipts = w.opening_stream(workload.CURRENT)[: int(record["jobs_on_the_ledger"])]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": receipts},
            {"kind": "plan", "context": context, "receipts": receipts},
        ]},
    )
    session = {
        "session": record.get("session"),
        "date": record.get("date"),
        "analyst": record.get("analyst"),
        "notes": list(record.get("notes", ())),
        "runs": _summary_rows(context),
        "jobs_on_the_ledger": [
            {"call_id": item["call_id"], "chain_id": item["chain_id"],
             "steps_returned": item["steps_returned"],
             "steps_charged": item["steps_charged"], "refusal": item["refusal"]}
            for item in receipts
        ],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "study": context["study"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "study": context["study"],
            "as_of": context["as_of"],
            "steps_charged": sum(int(item["steps_charged"]) for item in receipts),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_run_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_job(
    artifact_dir: Path, chain_id: Any, start_new: Any, steps: Any, call_id: Any
) -> Mapping[str, Any]:
    entries, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return w.collect(
        Path(artifact_dir), workload.CURRENT,
        workload.CURRENT_SPEC["opening_jobs"],
        chain_id, start_new, steps, call_id,
    )


def opening_receipts() -> dict[str, Any]:
    'The receipt stream the quarter starts from: the jobs that made the files.'

    return {
        "study": workload.CURRENT.study,
        "entries": w.opening_stream(workload.CURRENT),
    }
