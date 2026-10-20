'Deterministic, sandboxed measurement of one week of the fleet scheduler.'

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import CANDIDATE_FAILURE, AnalysisCache, SandboxedProject

from .workload import build_programme


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("dispatch/assignment.py", "dispatch/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, editable_files=EDITABLE_FILES, timeout=60.0,
    prefix="tiganeval-exclusive-lease-",
    driver=Path(__file__).resolve().with_name("runtime_driver.py"))


PRIVATE_PROGRAMME = "settlement-week"
BUCKETS: Mapping[str, str] = {
    "single_holder_job_conservation": "conservation_failures",
    "fleet_wide_claim_registry": "registry_failures",
    "exclusivity_survives_reregistration": "stickiness_failures",
    "revocation_notice_completeness": "notice_failures",
    "rank_and_window_discipline": "selection_failures",
}


_TEARDOWN_OPS = ("drop_link", "retire", "release")

_START_UP_OPS = ("claim",)
_CACHE = AnalysisCache()


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": str(kind), **fields}


def _walk(programme: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Number the operations the way the runner numbers them.'

    ops: list[dict[str, Any]] = []
    for process in programme:
        for raw in process.get("ops", ()):
            ops.append({
                **dict(raw), "index": len(ops), "process": str(process.get("label")),
                "after_restart": bool(process.get("after_restart")),
            })
    return ops


def _class_specs(ops: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    'Each class as the fleet configuration has it, not as a stale build says.'

    specs: dict[str, dict[str, Any]] = {}
    for op in ops:
        if str(op.get("op")) == "register" and not op.get("plain_registration"):
            specs.setdefault(str(op["class"]), {
                "exclusive": bool(op.get("exclusive", False)),
                "max_in_flight": int(op.get("max_in_flight", 1)),
            })
    return specs


def _claim_lifetimes(
    ops: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    'Every claim the fleet made, and the operation that took it away.'

    claims: dict[tuple[str, str], dict[str, Any]] = {}

    def close(entry: dict[str, Any], index: int, reason: str) -> None:
        if entry["closed_at"] is None and int(entry["opened_at"]) < index:
            entry["closed_at"], entry["closed_by"] = index, reason

    for op in ops:
        kind, process, index = str(op.get("op")), str(op["process"]), int(op["index"])
        if kind == "claim":
            claims[(process, str(op["worker"]))] = {
                "process": process, "worker": str(op["worker"]),
                "job_class": str(op["class"]), "rank": int(op.get("rank", 0)),
                "link": str(op["link"]), "opened_at": index,
                "closed_at": None, "closed_by": None,
            }
        elif kind == "release":
            entry = claims.get((process, str(op["worker"])))
            if entry is not None:
                close(entry, index, "the worker gave it up")
        elif kind in ("drop_link", "retire"):
            field = "link" if kind == "drop_link" else "job_class"
            value = str(op["link"] if kind == "drop_link" else op["class"])
            reason = "its link dropped" if kind == "drop_link" else "the class was retired"
            for entry in claims.values():
                if entry["process"] == process and entry[field] == value:
                    close(entry, index, reason)
    return claims


def _open_window(entry: Mapping[str, Any]) -> range:
    'The operations over which a claim was in the fleet, its removal included.'

    closed = entry["closed_at"]
    return range(int(entry["opened_at"]), int(closed) + 1 if closed is not None else 10**6)


def _holding_timeline(
    ops: Sequence[Mapping[str, Any]], deliveries: Sequence[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], int], list[dict[str, Any]], dict[int, dict[str, int]]]:
    'Read off what each worker was holding through the run: the most any of     them held at once, every hand-over with the holdings just before it, and the     holdings as each operation began..'

    by_op: dict[int, list[Mapping[str, Any]]] = {}
    for delivery in deliveries:
        by_op.setdefault(int(delivery["op_index"]), []).append(delivery)
    holding: dict[tuple[str, str], list[str]] = {}
    peak: dict[tuple[str, str], int] = {}
    annotated: list[dict[str, Any]] = []
    at_op: dict[int, dict[str, int]] = {}

    def counts() -> dict[str, int]:
        return {worker: len(jobs) for (_process, worker), jobs in holding.items()}

    for op in ops:
        index = int(op["index"])
        if str(op.get("op")) == "finish":
            for key, jobs in holding.items():
                if key[0] == str(op["process"]) and str(op["job"]) in jobs:
                    jobs.remove(str(op["job"]))
        at_op[index] = counts()
        for delivery in by_op.get(index, ()):
            annotated.append({**dict(delivery), "holdings_before": counts()})
            key = (str(delivery["process"]), str(delivery["worker"]))
            holding.setdefault(key, []).append(str(delivery["job"]))
            peak[key] = max(peak.get(key, 0), len(holding[key]))
    return peak, annotated, at_op


class Run:
    "One run of one programme, as the fleet's own records show it."

    def __init__(
        self, ledger: Mapping[str, Any], programme: Sequence[Mapping[str, Any]]
    ) -> None:
        self.programme, self.ops = list(programme), _walk(programme)
        self.by_index = {int(op["index"]): op for op in self.ops}
        self.specs, self.claims = _class_specs(self.ops), _claim_lifetimes(self.ops)
        self.deliveries = sorted(
            (dict(item) for item in ledger.get("deliveries", ())),
            key=lambda item: int(item["op_index"]),
        )
        self.notices = [dict(item) for item in ledger.get("notices", ())]
        self.outcomes = {int(x["index"]): dict(x) for x in ledger.get("ops", ())}
        self.peak, self.annotated, self.holdings_at = _holding_timeline(
            self.ops, self.deliveries
        )
        self.submits = [op for op in self.ops if str(op.get("op")) == "submit"]
        self.runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for delivery in self.deliveries:
            key = (self.process_of(int(delivery["op_index"])), str(delivery["job"]))
            self.runs.setdefault(key, []).append(delivery)

    def process_of(self, index: int) -> str:
        return str(self.by_index[int(index)]["process"])

    def after_restart(self, index: int) -> bool:
        'Whether this operation ran on a scheduler the supervisor rebuilt.'

        return bool(self.by_index[int(index)].get("after_restart"))

    def window(self, job_class: str) -> int:
        return int(self.specs.get(str(job_class), {}).get("max_in_flight", 1))

    def exclusive(self, job_class: str) -> bool:
        return bool(self.specs.get(str(job_class), {}).get("exclusive", False))

    def claims_on(
        self, process: str, job_class: str, index: int, linked: bool = True
    ) -> list[dict[str, Any]]:
        'Claims on a class that this operation had not taken away.'

        return [
            entry for entry in self.claims.values()
            if entry["process"] == process and entry["job_class"] == str(job_class)
            and (entry["closed_at"] is None or index < int(entry["closed_at"]))
            and (not linked or int(entry["opened_at"]) <= index)
        ]

    def holder_at(self, process: str, job_class: str, index: int) -> str | None:
        "The worker the class is on: the highest-ranked claim that arrived         first and this operation had not taken away, read off the claims         themselves rather than off the build's own reporting.."

        standing = self.claims_on(process, job_class, int(index))
        if not standing:
            return None
        entry = min(standing, key=lambda x: (-int(x["rank"]), int(x["opened_at"])))
        return str(entry["worker"])

    def last_runner(self, process: str, job_class: str, before: int) -> str | None:
        earlier = [
            item for item in self.deliveries
            if self.process_of(int(item["op_index"])) == process
            and str(item["job_class"]) == str(job_class)
            and int(item["op_index"]) < int(before)
        ]
        return str(earlier[-1]["worker"]) if earlier else None

    def ran(self, op: Mapping[str, Any]) -> list[dict[str, Any]]:
        return self.runs.get((str(op["process"]), str(op["job"])), [])

    def notice_ops(self, process: str, worker: str) -> list[int]:
        return [
            int(item["op_index"]) for item in self.notices
            if str(item["process"]) == process and str(item["worker"]) == worker
        ]

    def claim_id(self, entry: Mapping[str, Any]) -> str:
        'The claim id returned to this worker when its claim opened.'

        outcome = self.outcomes.get(int(entry["opened_at"]), {})
        return str(outcome.get("claim_id") or "")

    def failed_ops(self, kinds: Sequence[str] | None) -> list[tuple[int, Mapping[str, Any]]]:
        'Failed operations of these kinds, or of no named kind when None.'

        named = _TEARDOWN_OPS + _START_UP_OPS
        return [
            (index, outcome) for index, outcome in sorted(self.outcomes.items())
            if not outcome.get("ok") and (
                str(outcome.get("op")) in kinds if kinds is not None
                else str(outcome.get("op")) not in named
            )
        ]


def _conservation(run: Run) -> list[dict[str, Any]]:
    'The fleet runs only the jobs it was given, with their payload intact.'

    failures = [
        _fail("scheduler_raised_at_the_caller", at_op=index, op=str(x.get("op")),
              process=str(x.get("process")), error=str(x.get("error") or "none given"))
        for index, x in run.failed_ops(None)
    ]
    failures += [
        _fail("worker_could_not_take_the_class", at_op=index,
              worker=str(x.get("worker") or "a replica"),
              job_class=str(x.get("class") or ""), process=str(x.get("process")),
              error=str(x.get("error") or "none given"))
        for index, x in run.failed_ops(_START_UP_OPS)
    ]
    submits = {
        (str(op["process"]), str(op["job"])): op
        for op in run.submits
    }
    for delivery in run.deliveries:
        process = run.process_of(int(delivery["op_index"]))
        job = str(delivery["job"])
        if str(delivery.get("claimed_class", "")) != str(delivery["job_class"]):
            failures.append(_fail(
                "job_run_on_wrong_class_claim", process=process, job=job,
                job_class=str(delivery["job_class"]), worker=str(delivery["worker"]),
                claimed_class=str(delivery.get("claimed_class", "")),
            ))
        submitted = submits.get((process, job))
        if submitted is None:
            failures.append(_fail(
                "job_run_without_submission", process=process, job=job,
                job_class=str(delivery["job_class"]), worker=str(delivery["worker"]),
            ))
            continue
        expected = (str(submitted["class"]), str(submitted.get("account", "")))
        received = (str(delivery["job_class"]), str(delivery.get("account", "")))
        if received != expected:
            failures.append(_fail(
                "job_payload_changed", process=process, job=job,
                job_class=str(submitted["class"]), worker=str(delivery["worker"]),
                expected_job_class=str(submitted["class"]),
                received_job_class=str(delivery["job_class"]),
                expected_account=str(submitted.get("account", "")),
                received_account=str(delivery.get("account", "")),
            ))
    for op in run.submits:
        process, job, job_class = str(op["process"]), str(op["job"]), str(op["class"])
        exclusive, performed = run.exclusive(job_class), run.ran(op)
        if exclusive and len(performed) > 1:
            failures.append(_fail(
                "job_run_more_than_once", process=process, job=job, job_class=job_class,
                times_run=len(performed),
                workers=", ".join(sorted({str(x["worker"]) for x in performed})),
            ))
        for x in performed:
            entry = run.claims.get((str(x["process"]), str(x["worker"])))
            closed = None if entry is None else entry["closed_at"]
            if closed is not None and int(x["op_index"]) >= int(closed):
                failures.append(_fail(
                    "job_run_by_a_released_worker", process=process, job=job,
                    job_class=job_class, worker=str(x["worker"]),
                    removed_by=str(entry["closed_by"]),
                ))
        waiting = run.claims_on(process, job_class, int(op["index"]), linked=False)
        if exclusive and not performed and waiting:
            failures.append(_fail(
                "job_never_run", process=process, job=job, job_class=job_class,
                workers_that_could_have_run_it=len(waiting),
            ))
    failures += _beside_the_holder(run)
    return failures


def _declared_windows(run: Run) -> set[tuple[str, str]]:
    "The jobs the fleet judges a build's own declaration by."

    return {
        (str(op["process"]), str(job))
        for op in run.ops
        if str(op.get("op")) == "register" and op.get("plain_registration")
        for job in op.get("window_jobs", ())
    }


def _beside_the_holder(run: Run) -> list[dict[str, Any]]:
    "A class one worker holds at a time is bounded by that worker's window."

    declared = _declared_windows(run)
    failures: list[dict[str, Any]] = []
    for delivery in run.annotated:
        index = int(delivery["op_index"])
        process, job_class = run.process_of(index), str(delivery["job_class"])
        if str(delivery["process"]) != process or not run.exclusive(job_class):
            continue
        if (process, str(delivery["job"])) in declared:
            continue
        holder = run.holder_at(process, job_class, index)
        worker, window = str(delivery["worker"]), run.window(job_class)
        if holder is None or worker == holder:
            continue
        held = int(dict(delivery.get("holdings_before", {})).get(holder, 0))
        if held < window:
            continue
        failures.append(_fail(
            "job_run_beside_the_holder", process=process, job=str(delivery["job"]),
            job_class=job_class, worker=worker, holder=str(holder),
            window=window, holder_was_holding=held,
        ))
    return failures


def _registry(run: Run) -> list[dict[str, Any]]:
    "The fleet's claims belong to the fleet, and to this scheduler alone."

    failures = [
        _fail("stale_worker_ran_after_a_restart", job=str(x["job"]),
              process=run.process_of(int(x["op_index"])), job_class=str(x["job_class"]),
              worker=str(x["worker"]), worker_from=str(x["process"]))
        for x in run.deliveries
        if str(x["process"]) != run.process_of(int(x["op_index"]))
        and run.after_restart(int(x["op_index"]))
    ]
    submitted = {
        (str(op["process"]), str(op["job"])) for op in run.submits
    }
    earlier_jobs = {str(op["job"]) for op in run.submits}
    failures += [
        _fail(
            "stale_waiting_job_ran_after_a_restart", job=str(x["job"]),
            process=run.process_of(int(x["op_index"])),
            job_class=str(x["job_class"]), worker=str(x["worker"]),
        )
        for x in run.deliveries
        if run.after_restart(int(x["op_index"]))
        and str(x["job"]) in earlier_jobs
        and (run.process_of(int(x["op_index"])), str(x["job"])) not in submitted
    ]
    for op in run.submits:
        process, job, job_class = str(op["process"]), str(op["job"]), str(op["class"])
        waiting = run.claims_on(process, job_class, int(op["index"]))
        if waiting and op.get("after_restart") and not run.ran(op):
            failures.append(_fail(
                "class_silent_after_a_restart", process=process, job=job,
                job_class=job_class, worker_waiting=str(waiting[0]["worker"]),
            ))
    groups: dict[str, list[str]] = {}
    for process in run.programme:
        if process.get("compare_group"):
            group = str(process["compare_group"])
            groups.setdefault(group, []).append(str(process["label"]))
    for members in groups.values():
        if len(members) < 2:
            continue
        signatures = {
            label: sorted(
                f"{x['worker']}:{x['job']}" for x in run.deliveries
                if str(x["process"]) == label
                and run.process_of(int(x["op_index"])) == label
            )
            for label in members
        }
        first, second = members[0], members[1]
        if signatures[first] == signatures[second]:
            continue
        ran = {
            label: Counter(item.split(":")[0] for item in signatures[label])
            for label in (first, second)
        }
        names = sorted(set(ran[first]) | set(ran[second]))
        differing = [name for name in names if ran[first][name] != ran[second][name]]
        failures.append(_fail(
            "deliveries_depend_on_the_link_split", process=second,
            job_class="partner-settlement",
            jobs_run_on_one_link=len(signatures[first]),
            jobs_run_when_split=len(signatures[second]),
            worker=(differing or names)[0],
        ))
    return failures


def _stickiness(run: Run) -> list[dict[str, Any]]:
    'A build that says nothing about a class does not widen it.'

    failures: list[dict[str, Any]] = []


    cascades = bool(_beside_the_holder(run))
    for op in run.ops:
        if str(op.get("op")) != "register" or not op.get("plain_registration"):
            continue
        process, job_class = str(op["process"]), str(op["class"])
        performed = sorted(
            (x for job in op.get("window_jobs", ())
             for x in run.runs.get((process, str(job)), [])),
            key=lambda item: int(item["op_index"]),
        )
        workers = list(dict.fromkeys(str(x["worker"]) for x in performed))
        if len(workers) > 1 and not cascades:
            failures.append(_fail(
                "exclusivity_lost_after_a_plain_registration", process=process,
                job=str(performed[-1]["job"]), job_class=job_class,
                workers_that_ran_it=len(workers), workers=", ".join(sorted(workers)),
            ))
        before = run.holder_at(process, job_class, int(op["index"]))
        if before is not None and workers and workers[0] != before:
            failures.append(_fail(
                "lease_moved_on_a_plain_registration", process=process,
                job=str(performed[0]["job"]), job_class=job_class,
                worker_before=str(before), worker_after=str(workers[0]),
            ))
    return failures


def _preemptions(run: Run) -> list[dict[str, Any]]:
    'Each time a higher-ranked claim takes a class from a worker.'

    windows: list[dict[str, Any]] = []
    for op in run.ops:
        if str(op.get("op")) != "claim":
            continue
        process, job_class, index = str(op["process"]), str(op["class"]), int(op["index"])
        if not run.exclusive(job_class):
            continue
        holding = [
            entry for entry in run.claims_on(process, job_class, index)
            if int(entry["opened_at"]) < index
        ]
        if not holding:
            continue
        entry = min(holding, key=lambda x: (-int(x["rank"]), int(x["opened_at"])))
        incumbent = str(entry["worker"])
        if int(op.get("rank", 0)) <= int(entry["rank"]) or incumbent == str(op["worker"]):
            continue
        moved = next((
            int(x["op_index"]) for x in run.deliveries
            if run.process_of(int(x["op_index"])) == process
            and str(x["job_class"]) == job_class and int(x["op_index"]) > index
        ), int(run.ops[-1]["index"]))
        windows.append({
            "process": process, "worker": incumbent,
            "ops": set(range(index, moved + 1)),
            "taken_by": str(op["worker"]), "job_class": job_class,
        })
    return windows


def _notices(run: Run) -> list[dict[str, Any]]:
    'A worker that loses a class it did not give up is told, once.'

    windows = _preemptions(run)

    def explained(entry: Mapping[str, Any], index: int) -> bool:
        'Whether this operation really did take the class off this worker.'
        if (entry["closed_at"] is not None
                and entry["closed_by"] != "the worker gave it up"
                and index == int(entry["closed_at"])):
            return True
        if any(
            entry["process"] == window["process"]
            and entry["worker"] == window["worker"]
            and index in window["ops"]
            for window in windows
        ):
            return True
        return False

    failures = [
        _fail("removal_error_reached_the_caller", at_op=index, op=str(x.get("op")),
              process=str(x.get("process")), error=str(x.get("error") or "none given"),
              link=str(run.by_index.get(index, {}).get("link") or ""))
        for index, x in run.failed_ops(_TEARDOWN_OPS)
    ]
    for entry in run.claims.values():
        expected = run.claim_id(entry)
        if not expected:
            continue
        for notice in run.notices:
            if (str(notice["process"]) == str(entry["process"])
                    and str(notice["worker"]) == str(entry["worker"])
                    and str(notice.get("claim_id") or "") != expected):
                failures.append(_fail(
                    "notice_named_the_wrong_claim",
                    process=str(entry["process"]), worker=str(entry["worker"]),
                    job_class=str(entry["job_class"]), at_op=int(notice["op_index"]),
                    expected_claim_id=expected,
                    received_claim_id=str(notice.get("claim_id") or "nothing"),
                ))
    for window in windows:
        process, worker = str(window["process"]), str(window["worker"])
        told = sorted(set(window["ops"]).intersection(run.notice_ops(process, worker)))
        if not told:
            failures.append(_fail(
                "demoted_worker_not_told", process=process, worker=worker,
                job_class=str(window["job_class"]), taken_by=str(window["taken_by"]),
            ))
        elif len(told) > 1:
            failures.append(_fail(
                "notice_delivered_twice", process=process, worker=worker,
                job_class=str(window["job_class"]), notices=len(told), at_op=told[0],
            ))
    for op in run.ops:
        kind, process, index = str(op.get("op")), str(op["process"]), int(op["index"])
        if kind not in ("drop_link", "retire"):
            continue
        dropped = kind == "drop_link"
        field = "link" if dropped else "job_class"
        value = str(op["link"] if dropped else op["class"])
        mode = ("worker_not_told_when_its_link_dropped" if dropped
                else "worker_not_told_when_the_class_was_retired")
        for entry in run.claims.values():
            if (entry["process"] == process and entry[field] == value
                    and index in _open_window(entry)
                    and index not in run.notice_ops(process, str(entry["worker"]))):
                failures.append(_fail(
                    mode, process=process, worker=str(entry["worker"]),
                    job_class=str(entry["job_class"]), link=str(entry["link"]),
                ))
    for entry in run.claims.values():
        indices = run.notice_ops(str(entry["process"]), str(entry["worker"]))
        for index in sorted(set(indices)):
            if indices.count(index) > 1:
                failures.append(_fail(
                    "notice_delivered_twice", process=str(entry["process"]),
                    worker=str(entry["worker"]), job_class=str(entry["job_class"]),
                    notices=indices.count(index), at_op=index,
                ))
            voluntary = (
                entry["closed_by"] == "the worker gave it up"
                and entry["closed_at"] is not None
                and index == int(entry["closed_at"])
            )
            if voluntary:
                failures.append(_fail(
                    "worker_told_after_releasing_the_class",
                    process=str(entry["process"]), worker=str(entry["worker"]),
                    job_class=str(entry["job_class"]), at_op=index,
                ))
            elif not explained(entry, index):
                failures.append(_fail(
                    "worker_told_it_lost_a_class_it_still_had",
                    process=str(entry["process"]), worker=str(entry["worker"]),
                    job_class=str(entry["job_class"]), at_op=index,
                ))
    return failures


def _selection(run: Run) -> list[dict[str, Any]]:
    'Rank decides who runs a class, and nobody holds more than the window.'

    failures: list[dict[str, Any]] = []
    for (process, worker), held in sorted(run.peak.items()):
        entry = run.claims.get((process, worker))
        window = 0 if entry is None else run.window(str(entry["job_class"]))
        if entry is not None and int(held) > window:
            failures.append(_fail(
                "worker_held_more_than_its_window", process=process, worker=worker,
                job_class=str(entry["job_class"]), most_jobs_held_at_once=int(held),
                window=window,
            ))
    for delivery in run.annotated:
        index = int(delivery["op_index"])
        process = run.process_of(index)
        this = run.claims.get((process, str(delivery["worker"])))
        if this is None or str(delivery["process"]) != process:
            continue
        job_class = str(delivery["job_class"])
        holdings = dict(delivery.get("holdings_before", {}))
        better = [
            x for x in run.claims_on(process, job_class, index)
            if int(x["rank"]) > int(this["rank"])
            and int(holdings.get(str(x["worker"]), 0)) < run.window(job_class)
        ]
        if better:
            failures.append(_fail(
                "lower_ranked_worker_ran_the_class", process=process,
                job=str(delivery["job"]), job_class=job_class,
                worker=str(delivery["worker"]), worker_rank=int(this["rank"]),
                higher_ranked_worker=str(better[0]["worker"]),
                higher_rank=int(better[0]["rank"]),
            ))
    for op in run.ops:
        if str(op.get("op")) != "claim" or not op.get("equal_rank_newcomer"):
            continue
        process, job_class, index = str(op["process"]), str(op["class"]), int(op["index"])
        before = run.last_runner(process, job_class, index)
        after = next((
            x for x in run.deliveries
            if run.process_of(int(x["op_index"])) == process
            and str(x["job_class"]) == job_class and int(x["op_index"]) > index
        ), None)
        if (before is not None and after is not None
                and str(after["worker"]) == str(op["worker"]) != before):
            failures.append(_fail(
                "lease_moved_to_an_equal_ranked_newcomer", process=process,
                job_class=job_class, worker_before=str(before),
                newcomer=str(op["worker"]), rank=int(op.get("rank", 0)),
            ))
    for op in run.submits:
        process, job, job_class = str(op["process"]), str(op["job"]), str(op["class"])
        index = int(op["index"])
        if run.exclusive(job_class) or [
            x for x in run.ran(op) if int(x["op_index"]) == index
        ]:
            continue
        holdings = run.holdings_at.get(index, {})
        with_room = [
            x for x in run.claims_on(process, job_class, index)
            if int(holdings.get(str(x["worker"]), 0)) < run.window(job_class)
        ]
        if with_room:
            failures.append(_fail(
                "job_waited_while_a_worker_had_room", process=process, job=job,
                job_class=job_class, worker_with_room=str(with_room[0]["worker"]),
            ))
    return failures


def _stub_analysis(error: str) -> dict[str, Any]:
    failure = _fail(CANDIDATE_FAILURE, process=PRIVATE_PROGRAMME, error=str(error))
    analysis: dict[str, Any] = {"harness_error": str(error)}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _analyse(
    ledger: Mapping[str, Any], programme: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    run = Run(ledger, programme)
    return {
        "conservation_failures": _conservation(run), "registry_failures": _registry(run),
        "stickiness_failures": _stickiness(run), "notice_failures": _notices(run),
        "selection_failures": _selection(run), "jobs_submitted": len(run.submits),
        "jobs_handed_over": len(run.deliveries),
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private settlement week once against this workspace.'

    def compute() -> Mapping[str, Any]:
        payload = {"processes": build_programme(PRIVATE_PROGRAMME)}
        outcome = PROJECT.invoke(artifact_dir, payload)
        analysis = (
            _analyse(outcome, payload["processes"])
            if outcome.get("ok")
            else _stub_analysis(str(outcome.get("error", "the scheduler did not run")))
        )
        case = {"programme": PRIVATE_PROGRAMME, "processes": len(payload["processes"])}
        return {**analysis, "case": case}

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
