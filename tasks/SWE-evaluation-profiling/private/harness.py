'Deterministic, sandboxed review of one decision-service workspace.'

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("policy/engine.py", "policy/profile.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-policy-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 33, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "authz-latency-review": {"profile": "authz", "seed": 4, "scale": 1},
    "nightly-rollup": {"profile": "rollup", "seed": 25, "scale": 1},
    "peak-hour-replay": {"profile": "peak", "seed": 17, "scale": 1},
    "role-reference-fanout": {"profile": "fanout", "seed": 9, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "profiling_is_not_causal": "causal_failures",
    "definition_level_attribution": "attribution_failures",
    "reuse_is_not_evaluation": "reuse_failures",
    "profile_scoped_to_one_decision": "scope_failures",
    "rollup_preserves_the_run": "rollup_failures",
}

_NIGHTLY = ("rollup", "merge", "rate")
_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The contract module as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "policy" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_policy_protocol", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


def simulate(policy: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    'Replay one request against the contract: the outcome and the counts.'

    protocol = frozen_protocol()
    budget = protocol.DEFAULT_BUDGET
    state = {"work": 0}
    ops: list[str] = []
    entries: dict[str, int] = {}
    holds: dict[str, int] = {}
    asks: dict[str, int] = {}
    cache: dict[str, Any] = {}

    class Stop(Exception):
        pass

    def record(op: str, cost: int) -> None:
        ops.append(op)
        state["work"] += int(cost)
        if state["work"] > budget:
            raise Stop

    def bump(table: dict[str, int], key: str) -> None:
        table[key] = table.get(key, 0) + 1

    def body_holds(definition: Any, identifier: str) -> bool:
        for node in definition.body:
            if isinstance(node, protocol.Ref):
                if rule_value(node.target) != node.expect:
                    return False
            else:
                record(node.node_id, protocol.node_cost(node, request))
                if not protocol.holds(node, request):
                    return False
        record(f"held:{identifier}", 0)
        return True

    def rule_value(path: str) -> Any:
        record(f"ask:{path}", 1)
        bump(asks, path)
        if path in cache:
            return cache[path]
        found: list[Any] = []
        for definition in policy.definitions_for(path):
            identifier = protocol.definition_id(definition)
            record(f"body:{identifier}", 1)
            bump(entries, identifier)
            if body_holds(definition, identifier):
                bump(holds, identifier)
                found.append(definition.value)
        if not found:
            value = policy.default_for(path)
        elif any(item != found[0] for item in found[1:]):
            raise protocol.RuleConflict(path)
        else:
            value = found[0]
        cache[path] = value
        return value

    try:
        value = rule_value(policy.entry)
        outcome = protocol.DENY if value is None else str(value)
    except protocol.RuleConflict:
        outcome = protocol.CONFLICT
    except Stop:
        outcome = protocol.INDETERMINATE
    rows = {
        identifier: {
            "evals": count,
            "successes": holds.get(identifier, 0),
            "reuse": asks.get(identifier.split("#", 1)[0], 0) - count,
        }
        for identifier, count in entries.items()
    }
    return {"outcome": outcome, "work": state["work"], "ops": ops, "rows": rows,
            "asks": asks, "entries": entries}


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the operator console would show it: the directory part     of any path stripped, and a line the owner would not say replaced.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the step ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def row_totals(rows: Any) -> dict[str, int]:
    total = {"evals": 0, "successes": 0, "reuse": 0}
    for stat in dict(rows or {}).values():
        for field in total:
            total[field] += int(dict(stat).get(field, 0))
    return total


def _table(step: Mapping[str, Any], field: str) -> dict[str, dict[str, int]]:
    return {str(key): dict(value) for key, value in dict(step.get(field) or {}).items()}


def _rows_of(step: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    return _table(dict(step.get("profiled") or {}), "rows")


def _transcript_problem(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> str | None:
    records = candidate.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        return "the service did not return a drill timeline"
    if len(records) != len(program):
        return f"the service returned {len(records)} of {len(program)} drill steps"
    for index, (event, record) in enumerate(zip(program, records)):
        if not isinstance(record, Mapping):
            return f"drill step {index} was not a record"
        expected_type = str(event.get("type", ""))
        expected_label = str(event.get("label", f"{expected_type}-{index}"))
        if record.get("index") != index:
            return f"drill step {index} carried the wrong position"
        if str(record.get("type", "")) != expected_type:
            return f"drill step {index} carried the wrong operation"
        if str(record.get("label", "")) != expected_label:
            return f"drill step {index} carried the wrong label"
    return None


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One row per drill step, with the contract's own answer beside each decision."
    protocol = frozen_protocol()
    rows: list[dict[str, Any]] = []
    policy = None
    known: set[str] = set()
    for event, record in zip(program, candidate.get("records", ())):
        step = {**dict(record), "phase": str(event.get("phase", "")), "event": dict(event)}
        if str(record.get("type")) == "load":
            policy = protocol.load_policy(dict(event["bundle"]))
            step["definitions"] = sorted(
                protocol.definition_id(item) for item in policy.definitions
            )
            known |= set(step["definitions"])
        step["policy"] = policy
        step["current"] = {
            protocol.definition_id(item) for item in (policy.definitions if policy else ())
        }
        step["known"] = set(known)
        if str(record.get("type")) == "decide" and policy is not None:
            step["truth"] = simulate(policy, dict(event["request"]))
        rows.append(step)
    return rows


def _decisions(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in steps if str(step.get("type")) == "decide" and step.get("ok")]


def _causal_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = [
        _failure(
            "engine_operation_failed",
            label=str(step.get("label")),
            error=_safe_error(step.get("error")),
        )
        for step in steps
        if not step.get("ok") and str(step.get("type")) not in _NIGHTLY
    ]
    if failures:
        return failures
    for step in _decisions(steps):
        plain, profiled = dict(step["plain"]), dict(step["profiled"])
        truth, request = dict(step["truth"]), str(step.get("label"))
        if plain["outcome"] != profiled["outcome"]:
            failures.append(
                _failure(
                    "decision_changed_by_profiling", request=request,
                    without_profiling=str(plain["outcome"]),
                    with_profiling=str(profiled["outcome"])
                )
            )
        if plain["outcome"] != truth["outcome"]:
            failures.append(
                _failure(
                    "decision_disagrees_with_policy", request=request,
                    decision=str(plain["outcome"]), policy_says=str(truth["outcome"])
                )
            )
        if (
            list(plain["ops"]) != list(profiled["ops"])
            or int(plain["work"]) != int(profiled["work"])
        ):
            failures.append(
                _failure(
                    "work_changed_by_profiling", request=request,
                    work_without_profiling=int(plain["work"]),
                    work_with_profiling=int(profiled["work"])
                )
            )
    return failures


def _definitions_named(policy: Any, row: str) -> int:
    'How many definitions of the bundle a row could be talking about.'
    protocol = frozen_protocol()
    base = str(row).split("#", 1)[0]
    name = base.rsplit(".", 1)[-1]
    return sum(
        1
        for item in policy.definitions
        if protocol.rule_path(item) == base or item.rule == name
    )


def _attribution_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _decisions(steps):
        rows, truth = _rows_of(step), dict(step["truth"])["rows"]
        current, request = set(step["current"]), str(step.get("label"))
        for key in sorted(rows):

            if key not in step["known"]:
                failures.append(
                    _failure(
                        "profile_row_keys_not_definitions", request=request, row=key,
                        definitions=_definitions_named(step["policy"], key)
                    )
                )
        for identifier in sorted(truth):
            if identifier not in rows:
                failures.append(
                    _failure(
                        "entered_definition_missing", request=request,
                        definition=identifier, rule=identifier.split("#", 1)[0]
                    )
                )
        for key in sorted(rows):
            if key not in current:
                continue
            if key not in truth:
                failures.append(
                    _failure(
                        "unentered_definition_reported", request=request, definition=key
                    )
                )
            elif int(rows[key].get("successes", 0)) != int(truth[key]["successes"]):
                failures.append(
                    _failure(
                        "definition_success_count_wrong", request=request, definition=key,
                        reported=int(rows[key].get("successes", 0)),
                        measured=int(truth[key]["successes"])
                    )
                )
    return failures


def _busiest_rule(truth: Mapping[str, Any], standing: Mapping[str, Any]) -> dict[str, Any]:
    'The rule with the widest gap between references resolved and bodies run.'

    best = dict(standing)
    entries = dict(truth["entries"])
    for path, asks in dict(truth["asks"]).items():
        entered = max(
            (n for key, n in entries.items() if key.split("#", 1)[0] == path), default=0
        )
        gap, held = asks - entered, int(best["asks"]) - int(best["evals"])
        if gap > held or (gap == held and gap > 0 and str(path) < str(best["rule"])):
            best = {"rule": str(path), "asks": int(asks), "evals": int(entered)}
    return best


def _reuse_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    reuse_seen = 0
    busiest: dict[str, Any] = {"rule": "", "asks": 0, "evals": 0}
    for step in _decisions(steps):
        rows, truth = _rows_of(step), dict(step["truth"])
        current, request = set(step["current"]), str(step.get("label"))
        reuse_seen += row_totals(rows)["reuse"]
        busiest = _busiest_rule(truth, busiest)
        reported, measured = row_totals(rows)["evals"], row_totals(truth["rows"])["evals"]
        if reported != measured:
            failures.append(
                _failure(
                    "evaluation_count_wrong", request=request, reported=reported,
                    measured=measured
                )
            )
        for key in sorted(rows):
            if key not in current or key not in truth["rows"]:
                continue
            expected = truth["rows"][key]
            if int(rows[key].get("evals", 0)) != int(expected["evals"]):
                failures.append(
                    _failure(
                        "evaluation_count_wrong", request=request, definition=key,
                        reported=int(rows[key].get("evals", 0)),
                        measured=int(expected["evals"])
                    )
                )
            if int(rows[key].get("reuse", 0)) != int(expected["reuse"]):
                failures.append(
                    _failure(
                        "reuse_count_wrong", request=request, definition=key,
                        reported=int(rows[key].get("reuse", 0)),
                        measured=int(expected["reuse"])
                    )
                )
    if reuse_seen == 0 and busiest["asks"] > busiest["evals"]:
        failures.append(_failure("reuse_never_recorded", **busiest))
    return failures


def _scope_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    seen: dict[str, dict[str, dict[str, int]]] = {}
    for step in steps:
        kind, label = str(step.get("type")), str(step.get("label"))
        if kind == "recheck":
            earlier = str(step["event"].get("of"))
            if step.get("ok") and earlier in seen and _table(step, "rows") != seen[earlier]:
                failures.append(
                    _failure(
                        "earlier_profile_changed_by_later_decision", request=earlier,
                        checked_at=label
                    )
                )
            continue
        if kind != "decide" or not step.get("ok"):
            continue
        rows = _rows_of(step)
        seen[label] = rows
        if not dict(step["plain"]).get("profile_is_none", True):
            failures.append(_failure("profile_attached_when_disabled", request=label))
        if dict(step["profiled"]).get("rows") is None:
            failures.append(_failure("profile_missing_when_enabled", request=label))
        retired = sorted(
            key for key in rows if key in step["known"] and key not in set(step["current"])
        )
        if retired:
            failures.append(
                _failure("retired_bundle_rules_reported", request=label, row=retired[0])
            )
        before = str(step["event"].get("same_as", ""))
        if before and before in seen and seen[before] != rows:
            failures.append(
                _failure(
                    "profile_depends_on_earlier_requests", request=label, earlier=before,
                    reported_total=row_totals(rows)["evals"],
                    earlier_total=row_totals(seen[before])["evals"]
                )
            )
    return failures


def _sum_rows(rows: Mapping[str, Any], keys: Sequence[str]) -> dict[str, int]:
    return row_totals({key: rows[key] for key in keys if key in rows})


def _rollup_view(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    protocol = frozen_protocol()
    label = str(step.get("label"))
    source, buckets = _table(step, "source"), _table(step, "totals")
    failures: list[dict[str, Any]] = []
    for field in ("source_after_rollup", "source_after_probe"):
        after = _table(step, field)
        if after != source:
            row = next(
                key for key in sorted(set(source) | set(after))
                if source.get(key) != after.get(key)
            )
            failures.append(
                _failure("derived_profile_aliases_source", label=label, row=row)
            )
            break
    known = {protocol.package_of(key) for key in source if "#" in key}
    stray = [
        _failure("package_key_not_package", label=label, bucket=name)
        for name in sorted(buckets)
        if name not in known
    ]
    if stray:
        return failures + stray
    for name in sorted(buckets):
        measured = _sum_rows(source, [k for k in source if protocol.package_of(k) == name])
        if buckets[name] != measured:
            failures.append(
                _failure(
                    "package_totals_disagree_with_run", label=label, bucket=name,
                    reported=int(buckets[name].get("evals", 0)),
                    measured=int(measured["evals"])
                )
            )
    if row_totals(source) != row_totals(buckets):
        failures.append(
            _failure(
                "package_totals_disagree_with_run",
                label=label,
                bucket="every package together",
                reported=int(row_totals(buckets)["evals"]),
                measured=int(row_totals(source)["evals"]),
            )
        )
    return failures


def _merge_view(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    label = str(step.get("label"))
    left, right = _table(step, "left_before"), _table(step, "right_before")
    merged = _table(step, "merged")
    failures: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right) | set(merged)):
        measured = row_totals({"l": left.get(key, {}), "r": right.get(key, {})})
        if merged.get(key) != measured:
            failures.append(
                _failure(
                    "merged_shard_counts_wrong", label=label, row=key,
                    reported=int(dict(merged.get(key, {})).get("evals", 0)),
                    measured=int(measured["evals"])
                )
            )
    if not step["event"].get("probe"):
        return failures
    for side, before, after in (
        ("left", left, _table(step, "left_after")),
        ("right", right, _table(step, "right_after")),
    ):
        for key in sorted(before):
            if after.get(key) != before[key]:
                failures.append(
                    _failure(
                        "derived_profile_aliases_source", label=label, row=key, side=side
                    )
                )
                break
    return failures


def _rate_view(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    protocol = frozen_protocol()
    failures: list[dict[str, Any]] = []
    for entry in step.get("rates") or ():
        row = dict(entry)
        measured = protocol.success_rate(
            int(row.get("evals", 0)), int(row.get("successes", 0))
        )
        if abs(float(row.get("reported", 0.0)) - measured) > 1e-9:
            failures.append(
                _failure(
                    "success_rate_wrong", label=str(step.get("label")),
                    row=str(row.get("key")), reported=round(float(row.get("reported", 0.0)),
                    3), measured=round(measured, 3)
                )
            )
    return failures


def _rollup_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    nightly = [step for step in steps if str(step.get("type")) in _NIGHTLY]
    raised = [
        _failure(
            "rollup_operation_failed",
            label=str(step.get("label")),
            error=_safe_error(step.get("error")),
        )
        for step in nightly
        if not step.get("ok")
    ]
    if raised:
        return raised
    views = {"rollup": _rollup_view, "merge": _merge_view, "rate": _rate_view}
    failures: list[dict[str, Any]] = []
    for step in nightly:
        failures.extend(views[str(step.get("type"))](step))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict:
    steps = read_steps(candidate, program)
    return {
        "causal_failures": _causal_failures(steps),
        "attribution_failures": _attribution_failures(steps),
        "reuse_failures": _reuse_failures(steps),
        "scope_failures": _scope_failures(steps),
        "rollup_failures": _rollup_failures(steps),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the operator console shows when a drill did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the drill box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the service ended without saying why"
    return f"the service stopped part way through the drill: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private drill against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["seed"]), int(case["scale"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            problem = _transcript_problem(candidate, program)
            analysis = (
                dict(failed_analysis(problem, tuple(BUCKETS.values())))
                if problem is not None
                else _analyse(candidate, program)
            )
        analysis["case"] = {"drill": "release"}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
