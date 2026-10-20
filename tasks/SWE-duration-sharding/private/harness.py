'Deterministic, sandboxed analysis of one shard-planner workspace.'

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, artifact_hash, failed_analysis

from .workload import BALANCE_RATIO, build_program


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("sharding/planner.py", "sharding/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES, prefix="tiganeval-sharding-", timeout=60.0,
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 24}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "baseline-hash-run": {"profile": "baseline", "seed": 5},
    "retry-after-shard-failure": {"profile": "retry", "seed": 13},
    "concurrent-record": {"profile": "concurrent", "seed": 19},
    "pr-adds-new-files": {"profile": "newfiles", "seed": 29},
}

BUCKETS: Mapping[str, str] = {
    "whole_suite_assigned_once": "partition_failures",
    "run_pinned_plan_agreement": "pinning_failures",
    "unmeasured_files_keep_the_usual_split": "usual_split_failures",
    "duration_history_conservation": "history_failures",
    "plan_balance_honesty": "balance_failures",
}

PHASES = ("baseline", "retry", "concurrent", "newfiles", "smallpr")
PLAN_FIELDS = ("run_id", "attempt", "index", "shard_count", "history_generation", "files",
               "predicted_ms", "estimates")

_CACHE = AnalysisCache()


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _minutes(milliseconds: float) -> str:
    return f"{float(milliseconds) / 60000.0:.1f}"


def _listed(names: Sequence[Any]) -> str:
    rows = [str(item) for item in names]
    if not rows:
        return "nothing"
    return rows[0] if len(rows) == 1 else f"{', '.join(rows[:-1])} and {rows[-1]}"


def _observations(value: Any) -> list[Mapping[str, Any]]:
    'Every observation one file holds in the history document.'

    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _triples(value: Any) -> Counter:
    return Counter(
        (int(item.get("duration_ms", 0)), int(item.get("generation", 0)),
         float(item.get("recorded_at", 0.0)))
        for item in _observations(value)
    )


def _pinned(entries: Mapping[str, Any] | None, generation: int) -> dict[str, int]:
    'The timings a run started at `generation` is looking at.'

    if not isinstance(entries, Mapping):
        return {}
    view: dict[str, int] = {}
    for path, observed in entries.items():
        published = [item for item in _observations(observed)
                     if int(item.get("generation", 0)) <= int(generation)]
        if published:
            newest = max(published, key=lambda item: (int(item.get("generation", 0)),
                                                      float(item.get("recorded_at", 0.0))))
            view[str(path)] = int(newest.get("duration_ms", 0))
    return view


def _timeline(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every replayed step with the tree and the history document beside it.'

    rows: list[dict[str, Any]] = []
    files: tuple[str, ...] = ()
    durations: dict[str, int] = {}
    entries: dict[str, Any] | None = None
    for record in records:
        row = dict(record)
        if str(row.get("type")) == "checkout":
            files = tuple(str(item) for item in row.get("files", ()))
            durations = {str(k): int(v) for k, v in dict(row.get("durations", {})).items()}
        row["tree_files"] = list(files)
        row["true_durations"] = dict(durations)
        row["history_before"] = None if entries is None else dict(entries)
        if "history_entries" in row:
            value = row.get("history_entries")
            entries = dict(value) if isinstance(value, Mapping) else None
        row["history_after"] = None if entries is None else dict(entries)
        rows.append(row)
    return rows


def _plans(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("type")) == "plan"]


def _groups(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in _plans(rows):
        grouped.setdefault(str(row.get("group")), []).append(row)
    return grouped


def _complete(group: Sequence[Mapping[str, Any]]) -> bool:
    'A round in which every machine of the run planned and returned a list.'

    if not group:
        return False
    count = int(group[0].get("shard_count", 0))
    indexes = {int(row.get("shard_index", 0)) for row in group}
    return (
        count >= 1
        and indexes == set(range(1, count + 1))
        and all(row.get("ok") and isinstance(row.get("assigned"), list) for row in group)
    )


def _run_of(row: Mapping[str, Any]) -> dict[str, Any]:
    return dict(row.get("run", {}))


def _usual_shard(path: str, count: int) -> int:
    'The machine `protocol.hash_shard` has always put this file on.'

    return int(hashlib.md5(str(path).encode("utf-8")).hexdigest(), 16) % int(count) + 1


def _reference_load(files: Sequence[str], durations: Mapping[str, int], index: int, count: int) -> int:
    return sum(
        int(durations.get(path, 0))
        for path in sorted(set(files))
        if _usual_shard(path, count) == index
    )


def _realised(row: Mapping[str, Any], durations: Mapping[str, int]) -> int:
    return sum(int(durations.get(str(path), 0)) for path in (row.get("assigned") or ()))


def _partition_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in _plans(rows):
        run_id = _run_of(row).get("run_id")
        label = row.get("label")
        if not row.get("ok"):
            failures.append(_fail("planner_call_failed", label=label, run_id=run_id, error=row.get("error")))
        elif not isinstance(row.get("assigned"), list):
            failures.append(_fail("shard_assignment_missing", label=label, run_id=run_id))
    if failures:
        return failures

    for name, group in _groups(rows).items():
        if not _complete(group):
            continue
        ordered = sorted(group, key=lambda row: int(row.get("shard_index", 0)))
        discovered = set(ordered[0].get("discovered", ()))
        run_id = str(_run_of(ordered[0]).get("run_id"))
        placement: dict[str, list[int]] = {}
        for row in ordered:
            shard = int(row.get("shard_index", 0))
            for path, times in Counter(str(item) for item in row.get("assigned", ())).items():
                placement.setdefault(path, []).extend([shard] * times)
        for path, shards in sorted(placement.items()):
            if len(shards) > 1 and len(set(shards)) == 1:
                failures.append(_fail("file_listed_twice_in_one_shard", file=path, run_id=run_id,
                                      group=name, shard_index=shards[0], times=len(shards)))
        for path in sorted(discovered - set(placement)):
            failures.append(_fail("file_assigned_to_no_shard", file=path, run_id=run_id, group=name,
                                  suite_size=len(discovered)))
        for path, shards in sorted(placement.items()):
            if len(set(shards)) > 1:
                failures.append(_fail("file_assigned_to_two_shards", file=path, run_id=run_id,
                                      group=name, shards=_listed(sorted(set(shards)))))
        for path in sorted(set(placement) - discovered):
            failures.append(_fail("unknown_file_assigned", file=path, run_id=run_id, group=name,
                                  shard_index=sorted(set(placement[path]))[0]))
    return failures


def _pinning_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    by_machine: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for row in _plans(rows):
        if row.get("ok") and isinstance(row.get("assigned"), list):
            key = (str(_run_of(row).get("run_id")), int(row.get("shard_index", 0)))
            by_machine.setdefault(key, []).append(row)
    for (run_id, shard), planned in sorted(by_machine.items()):
        first = planned[0]
        base = sorted({str(item) for item in first.get("assigned", ())})
        for row in planned[1:]:
            later = sorted({str(item) for item in row.get("assigned", ())})
            if later == base:
                continue
            attempts = (int(_run_of(first).get("attempt", 1)), int(_run_of(row).get("attempt", 1)))
            moved = sorted(set(base) ^ set(later))
            failures.append(_fail(
                "retry_plan_differs" if attempts[0] != attempts[1] else "plan_moved_after_recording",
                run_id=run_id, shard_index=shard, label=row.get("label"), attempt=attempts[1],
                moved_count=len(moved), first_file_that_moved=moved[0]))
    for row in _plans(rows):
        readable = row.get("plan_read")
        if not isinstance(readable, Mapping):
            continue
        expected = int(_run_of(row).get("history_generation", 0))
        reported = int(readable.get("history_generation", -1))
        if reported != expected:
            failures.append(_fail("plan_generation_not_pinned", label=row.get("label"),
                                  run_id=_run_of(row).get("run_id"), reported=reported,
                                  run_started_at=expected))
    return failures


def _usual_split_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in _plans(rows):
        view = _pinned(row.get("history_before"), int(_run_of(row).get("history_generation", 0)))
        discovered = {str(item) for item in row.get("discovered", ())}
        run_id = str(_run_of(row).get("run_id"))
        if not set(view) & discovered:


            if not row.get("ok"):
                failures.append(_fail("cold_start_planner_failed", label=row.get("label"),
                                      run_id=run_id, error=row.get("error")))
                continue
            if not isinstance(row.get("assigned"), list):
                continue
            assigned = sorted({str(item) for item in row.get("assigned", ())})
            reference = sorted({str(item) for item in row.get("reference_files", ())})
            if assigned == reference:
                continue
            moved = sorted(set(assigned) ^ set(reference))
            failures.append(_fail("cold_start_split_differs", label=row.get("label"), run_id=run_id,
                                  shard_index=int(row.get("shard_index", 0)), moved_count=len(moved),
                                  first_file_that_moved=moved[0] if moved else ""))
            continue


        if not row.get("ok") or not isinstance(row.get("assigned"), list):
            continue
        shard = int(row.get("shard_index", 0))
        count = int(row.get("shard_count", 1))
        strays = sorted(
            path for path in {str(item) for item in row.get("assigned", ())}
            if path in discovered and path not in view and _usual_shard(path, count) != shard
        )
        if strays:
            failures.append(_fail("unmeasured_file_moved_off_its_usual_shard", file=strays[0],
                                  label=row.get("label"), run_id=run_id, shard_index=shard,
                                  usual_shard=_usual_shard(strays[0], count),
                                  moved_count=len(strays)))
    return failures


def _history_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("type")) not in ("record", "record_group"):
            continue
        label, run = row.get("label"), _run_of(row)
        run_id, clock = run.get("run_id"), float(run.get("now", 0.0))
        started_at = int(run.get("history_generation", 0))
        if not row.get("ok"):
            failures.append(_fail("recorder_call_failed", label=label, run_id=run_id,
                                  error=row.get("error")))
            continue
        completed: dict[str, list[int]] = {}
        untouched: dict[str, str] = {}
        batches = (
            list(dict(row.get("observations_by_shard", {})).values())
            if str(row.get("type")) == "record_group"
            else [row.get("observations", ())]
        )
        observations = [entry for batch in batches for entry in batch]
        for item in (dict(entry) for entry in observations):
            path = str(item.get("file"))
            if str(item.get("status")) == "completed":
                completed.setdefault(path, []).append(int(item.get("duration_ms", 0)))
            else:
                untouched[path] = str(item.get("status"))
        before = dict(row.get("history_before") or {})
        after = row.get("history_after")
        if after is None:
            if row.get("history_present") and completed:
                failures.append(_fail("history_file_unreadable", label=label, run_id=run_id))
                continue
            after = {}
        for path, held in sorted(before.items()):
            kept = _triples(after.get(path))
            if any(kept[item] < times for item, times in _triples(held).items()):
                failures.append(_fail("earlier_observation_lost", label=label, run_id=run_id, file=path))
        for path, spent in sorted(completed.items()):
            added = list((_triples(after.get(path)) - _triples(before.get(path))).elements())
            if len(added) < len(spent):
                failures.append(_fail("completed_file_not_recorded", label=label, run_id=run_id,
                                      file=path, ran_for_minutes=_minutes(spent[0]),
                                      files_the_history_holds=len(after)))
            elif len(added) > len(spent):
                failures.append(_fail("file_recorded_more_than_once", label=label, run_id=run_id,
                                      file=path, times=len(added)))
            elif sorted(item[0] for item in added) != sorted(spent):
                failures.append(_fail("recorded_duration_wrong", label=label, run_id=run_id, file=path,
                                      recorded_minutes=_minutes(sorted(item[0] for item in added)[0]),
                                      ran_for_minutes=_minutes(sorted(spent)[0])))
            elif {item[2] for item in added} != {clock}:
                failures.append(_fail("recorded_time_not_from_the_run_clock", label=label, file=path,
                                      run_id=run_id, stamped=sorted(item[2] for item in added)[0],
                                      run_clock=clock))
            elif min(item[1] for item in added) <= started_at:
                failures.append(_fail("history_generation_did_not_advance", label=label, file=path,
                                      run_id=run_id, published=min(item[1] for item in added),
                                      run_started_at=started_at))
        for path, status in sorted(untouched.items()):
            added = list((_triples(after.get(path)) - _triples(before.get(path))).elements())
            if added:
                failures.append(_fail("unrun_file_recorded", label=label, run_id=run_id, file=path,
                                      status=status, recorded_minutes=_minutes(added[0][0])))
        accounted_for = set(completed) | set(untouched)
        for path in sorted((set(before) | set(after)) - accounted_for):
            added = list((_triples(after.get(path)) - _triples(before.get(path))).elements())
            if added:
                failures.append(_fail("unexpected_observation_recorded", label=label, run_id=run_id,
                                      file=path, recorded_minutes=_minutes(added[0][0])))
        if completed:
            published = row.get("history_generation")
            if not isinstance(published, int) or published <= started_at:
                failures.append(_fail("history_generation_did_not_advance", label=label,
                                      run_id=run_id, published=published,
                                      run_started_at=started_at))
        generations = [item[1] for held in after.values() for item in _triples(held).elements()]
        if generations and row.get("history_generation") != max(generations):
            failures.append(_fail(
                "history_generation_disagrees_with_entries", label=label, run_id=run_id,
                document_generation=row.get("history_generation"), entry_generation=max(generations)))
    return failures


def _balance_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in _plans(rows):
        if not row.get("ok"):
            continue
        label, run_id = row.get("label"), _run_of(row).get("run_id")
        readable = row.get("plan_read")
        if not isinstance(readable, Mapping):
            plan = row.get("plan")
            missing = (
                [name for name in PLAN_FIELDS if name not in plan]
                if isinstance(plan, Mapping)
                else list(PLAN_FIELDS)
            )
            failures.append(_fail("balance_report_missing", label=label, run_id=run_id,
                                  missing=_listed(missing) if missing else "numbers the board can read"))
            continue
        expected_context = {
            "run_id": str(_run_of(row).get("run_id")),
            "attempt": int(_run_of(row).get("attempt", 0)),
            "index": int(row.get("shard_index", 0)),
            "shard_count": int(row.get("shard_count", 0)),
        }
        for field, expected in expected_context.items():
            reported = readable.get(field)
            if reported != expected:
                failures.append(_fail("plan_context_mismatch", label=label, run_id=run_id,
                                      field=field, reported=reported, expected=expected))
                break
        listed = [str(item) for item in readable.get("files", ())]
        estimates = {str(k): int(v) for k, v in dict(readable.get("estimates", {})).items()}
        summed = sum(estimates.values())
        if set(estimates) != set(listed) or int(readable.get("predicted_ms", -1)) != summed:
            failures.append(_fail("predicted_total_disagrees", label=label, run_id=run_id,
                                  claimed_minutes=_minutes(int(readable.get("predicted_ms", 0))),
                                  adds_up_to_minutes=_minutes(summed)))
            continue
        view = _pinned(row.get("history_before"), int(readable.get("history_generation", 0)))
        for path in sorted(set(listed)):
            if estimates.get(path, 0) != int(view.get(path, 0)):
                failures.append(_fail("estimate_not_from_history", label=label, run_id=run_id,
                                      file=path, priced_minutes=_minutes(estimates.get(path, 0)),
                                      history_minutes=_minutes(int(view.get(path, 0)))))
                break

    for name, group in _groups(rows).items():
        if not _complete(group):
            continue
        ordered = sorted(group, key=lambda row: int(row.get("shard_index", 0)))
        count = int(ordered[0].get("shard_count", 1))
        durations = dict(ordered[0].get("true_durations", {}))
        discovered = sorted(set(ordered[0].get("discovered", ())))
        run_id = str(_run_of(ordered[0]).get("run_id"))
        realised = {int(row.get("shard_index", 0)): _realised(row, durations) for row in ordered}
        usual = [_reference_load(discovered, durations, i, count) for i in range(1, count + 1)]
        span, usual_span = max(realised.values()), max(usual)
        slowest = max(realised, key=lambda index: (realised[index], -index))
        if span > usual_span:
            failures.append(_fail("slower_than_the_split_it_replaced", run_id=run_id, group=name,
                                  shard_index=slowest, planned_minutes=_minutes(span),
                                  usual_minutes=_minutes(usual_span)))
            continue
        view = _pinned(ordered[0].get("history_before"),
                       int(_run_of(ordered[0]).get("history_generation", 0)))
        if set(discovered) <= set(view):


            mean = sum(int(durations.get(path, 0)) for path in discovered) / float(count)
            if span > BALANCE_RATIO * mean:
                failures.append(_fail("shard_over_balance_bound", run_id=run_id, group=name,
                                      shard_index=slowest, slowest_minutes=_minutes(span),
                                      allowed_minutes=_minutes(BALANCE_RATIO * mean),
                                      mean_minutes=_minutes(mean)))
            continue


        priced = {path: int(view[path]) for path in discovered if path in view}
        if not priced:
            continue
        priced_mean = sum(priced.values()) / float(count)
        if max(priced.values()) > BALANCE_RATIO * priced_mean:
            continue
        planned = {
            int(row.get("shard_index", 0)): sum(
                priced.get(str(path), 0) for path in (row.get("assigned") or ())
            )
            for row in ordered
        }
        worst = max(planned, key=lambda index: (planned[index], -index))
        if planned[worst] > BALANCE_RATIO * priced_mean:
            failures.append(_fail("plan_predicts_a_lopsided_split", run_id=run_id, group=name,
                                  shard_index=worst, predicted_minutes=_minutes(planned[worst]),
                                  allowed_minutes=_minutes(BALANCE_RATIO * priced_mean),
                                  mean_minutes=_minutes(priced_mean)))
    return failures


def _analyse(candidate: Mapping[str, Any]) -> dict[str, Any]:
    rows = _timeline([row for row in candidate.get("records", ()) if isinstance(row, Mapping)])
    return {
        "partition_failures": _partition_failures(rows),
        "pinning_failures": _pinning_failures(rows),
        "usual_split_failures": _usual_split_failures(rows),
        "history_failures": _history_failures(rows),
        "balance_failures": _balance_failures(rows),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the runner killed it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the planner ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the planner ended without saying why"
    return f"the run stopped before the suite was planned: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Replay the private CI run against this workspace and bucket what failed.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]), int(PRIVATE_CASE["seed"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            analysis = dict(failed_analysis(_console_error(candidate), tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate)
        analysis["case"] = {"run": "release", "phases": list(PHASES)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a recorded run must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    return {
        "summary": "The planner files and the runs the platform team keeps around.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "planner_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "sharding").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "operations_note": "ops/ci-budget.md",
        },
        "records": [
            {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
            for path in sorted((root / "project_records").glob("*.json"))
        ],
    }


def _step_row(row: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(row.get("type"))
    reported: dict[str, Any] = {
        "step": row.get("label"),
        "what_happened": kind,
        "history_file_now_at_generation": row.get("history_generation"),
        "history_file_readable": row.get("history_readable"),
    }
    if not row.get("ok"):
        reported["planner_raised"] = row.get("error")
    if kind == "checkout":
        reported.update(files_in_the_tree=len(row.get("files", ())),
                        what_each_file_takes_ms=row.get("durations"))
    if kind in ("shard_run", "record"):
        reported.update(shard=row.get("shard_index"),
                        what_this_machine_ran=row.get("observations"))
    if kind == "record_group":
        reported.update(shards=row.get("shard_indices"),
                        what_the_machines_ran=row.get("observations_by_shard"))
    if kind == "plan":
        reported.update(
            planning_round=row.get("group"),
            shard=f"{row.get('shard_index')} of {row.get('shard_count')}",
            run=row.get("run"),
            walk_handed_to_this_machine=row.get("walk_order"),
            files_in_the_tree=len(row.get("discovered", ())),
            planned_files=row.get("assigned"),
            the_split_ci_has_always_had=row.get("reference_files"),
            realised_minutes=_minutes(_realised(row, dict(row.get("true_durations", {})))),
        )
        if row.get("plan_error"):
            reported["the_runner_refused_this_plan"] = row.get("plan_error")
        readable = row.get("plan_read")
        if isinstance(readable, Mapping):
            generation = int(readable.get("history_generation", 0))
            held = _pinned(row.get("history_before"), generation)
            priced = {str(path): int(value)
                      for path, value in dict(readable.get("estimates", {})).items()}
            listed = [str(item) for item in readable.get("files", ())]
            reported["plan_the_runner_read"] = {
                "run_id": readable.get("run_id"),
                "attempt": readable.get("attempt"),
                "history_generation": generation,
                "predicted_minutes": _minutes(int(readable.get("predicted_ms", 0))),
                "files_it_priced": len(priced),
                "priced_minutes_beside_the_history_at_that_generation": {
                    path: (
                        f"the plan says {_minutes(priced.get(path, 0))}"
                        + (f", the history says {_minutes(held[path])}" if path in held
                           else ", the history has no timing for it")
                    )
                    for path in sorted(set(listed) | set(priced))
                },
            }
    if "history_entries" in row:
        entries = row.get("history_entries")
        reported["files_the_history_holds"] = None if entries is None else len(entries)
        if kind not in ("record", "record_group"):
            reported["history_document"] = entries
    return reported


def _group_summary(group: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(group, key=lambda row: int(row.get("shard_index", 0)))
    count = int(ordered[0].get("shard_count", 1))
    durations = dict(ordered[0].get("true_durations", {}))
    discovered = sorted(set(ordered[0].get("discovered", ())))
    total = sum(int(durations.get(path, 0)) for path in discovered)
    usual = [_reference_load(discovered, durations, i, count) for i in range(1, count + 1)]
    per_shard = [{
        "shard": row.get("shard_index"),
        "files": len(row.get("assigned") or []),
        "predicted_minutes": _minutes(int(dict(row["plan_read"]).get("predicted_ms", 0)))
        if isinstance(row.get("plan_read"), Mapping) else None,
        "realised_minutes": _minutes(_realised(row, durations)),
        "same_run_under_the_usual_split_minutes": _minutes(usual[int(row.get("shard_index", 1)) - 1]),
    } for row in ordered]
    started_at = int(_run_of(ordered[0]).get("history_generation", 0))
    held = _pinned(ordered[0].get("history_before"), started_at)
    priced = [int(held[path]) for path in discovered if path in held]
    priced_mean = (sum(priced) / float(count)) if priced else 0.0
    return {
        "planning_round": ordered[0].get("group"),
        "run": ordered[0].get("run"),
        "files_in_the_tree": len(discovered),
        "files_the_history_this_run_started_from_has_a_timing_for": len(priced),
        "files_planned_in_total": sum(len(row.get("assigned") or []) for row in ordered),
        "per_shard": per_shard,
        "this_split_finishes_in_minutes": _minutes(max(_realised(r, durations) for r in ordered)),
        "the_usual_split_finishes_in_minutes": _minutes(max(usual)),
        "mean_shard_minutes": _minutes(total / float(count)),
        "the_budget_line_is_minutes": _minutes(BALANCE_RATIO * total / float(count)),
        "what_this_generation_of_the_history_prices_the_tree_at_minutes_a_machine":
            _minutes(priced_mean),
        "the_budget_line_on_those_prices_is_minutes": _minutes(BALANCE_RATIO * priced_mean),
        "the_dearest_price_in_it_is_minutes": _minutes(max(priced) if priced else 0),
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded CI run against this workspace and report what happened.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown recorded run: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    program = build_program(str(case["profile"]), int(case["seed"]))
    candidate = PROJECT.invoke(Path(artifact_dir), {"events": list(program)})
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} run could not be replayed against this planner.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    rows = _timeline([row for row in candidate.get("records", ()) if isinstance(row, Mapping)])
    return {
        "summary": f"The {record_id} run was replayed against this planner.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "step_count": len(rows),
            "no_shard_may_run_longer_than": (
                f"{BALANCE_RATIO:g}x the mean shard time; ops/ci-budget.md says which numbers "
                "the line is held against on a run whose history covers part of the tree"
            ),
        },
        "public": {
            "what_each_machine_did": [_step_row(row) for row in rows],
            "per_planning_round": [
                _group_summary(group) for group in _groups(rows).values() if _complete(group)
            ],
        },
    }
