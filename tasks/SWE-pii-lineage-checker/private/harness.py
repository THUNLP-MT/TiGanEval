'Deterministic, sandboxed review of one lineage-checker workspace.'

from __future__ import annotations

import ast
from collections import Counter
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("lineage/tracer.py", "lineage/summaries.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-lineage-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "number": 61}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "audit-baseline": {"profile": "audit", "number": 12},
    "checkout-order-drill": {"profile": "checkout", "number": 45},
    "extract-step-regression": {"profile": "extract", "number": 34},
    "field-review": {"profile": "review", "number": 27},
}

BUCKETS: Mapping[str, str] = {
    "flow_matches_the_field_rules": "rule_failures",
    "verdict_survives_step_extraction": "refactor_failures",
    "report_independent_of_scan_order": "order_failures",
    "one_row_per_leaking_export": "identity_failures",
    "existing_audit_rows_unchanged": "baseline_failures",
}

_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The audit contract as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "lineage" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_lineage_protocol", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the triage console would show it: the directory part     of any path stripped, and a line the owner would not say replaced.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the step ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _dataset(value: Any) -> str:
    'The table or channel a row names, as the owner would say it aloud. A row     that sits on no export at all names nothing, and the owner still has to     have words for it.'

    return str(value or "").strip() or "a table it does not name"


def _key(row: Mapping[str, Any]) -> tuple[str, int, int, str]:
    return (str(row["module"]), int(row["line"]), int(row["col"]), str(row["check"]))


def _label(key: Sequence[Any]) -> str:
    return f"{key[0]} line {key[1]}"


def _exports(protocol: Any, module_set: Any) -> dict[tuple[str, int, int, str], str]:
    'Every export call of one pipeline, keyed the way a row is keyed.'

    found: dict[tuple[str, int, int, str], str] = {}
    for name in module_set.names():
        for node in ast.walk(module_set.tree(name)):
            if protocol.export_call(node) is None:
                continue
            row = protocol.finding_at(name, node)
            found[(name, row.line, row.col, row.check)] = row.dataset
    return found


def _standalone(protocol: Any, module_set: Any) -> set[str]:
    'The modules that neither call a step of this pipeline nor are called.'

    steps = module_set.steps()
    defined: dict[str, set[str]] = {}
    for step, (module, _node) in steps.items():
        defined.setdefault(module, set()).add(step)
    calls_out: dict[str, set[str]] = {}
    called: set[str] = set()
    for name in module_set.names():
        names = {
            node.func.id
            for node in ast.walk(module_set.tree(name))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in steps
        }
        calls_out[name] = names
        called |= names
    return {
        name
        for name in module_set.names()
        if not calls_out[name] and not (defined.get(name, set()) & called)
    }


def _reference(protocol: Any, module_set: Any, standalone: set[str]) -> dict:
    "What the office's own single-module pass says about each standalone step."

    found: dict[tuple[str, int, int, str], str] = {}
    for name in sorted(standalone):
        for row in protocol.reference_flows(module_set.source(name), name):
            found[(name, row.line, row.col, row.check)] = row.dataset
    return found


def _baseline(protocol: Any, module_set: Any) -> dict:
    found: dict[tuple[str, int, int, str], str] = {}
    for name in module_set.names():
        for row in protocol.baseline_findings(name, module_set.source(name)):
            found[(name, row.line, row.col, row.check)] = row.dataset
    return found


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One row per drill step, with the frozen contract's own reading beside it."

    protocol = frozen_protocol()
    steps: list[dict[str, Any]] = []
    for event, record in zip(program, candidate.get("records", ())):
        step = {**dict(record), "event": dict(event)}
        modules = dict(event.get("modules") or {})
        module_set = protocol.ModuleSet(modules, event.get("order"))
        standalone = _standalone(protocol, module_set)
        step["modules"] = modules
        step["standalone"] = standalone
        step["exports"] = _exports(protocol, module_set)
        step["reference"] = _reference(protocol, module_set, standalone)
        step["existing"] = _baseline(protocol, module_set)
        step["rows"] = [dict(row) for row in (record.get("rows") or ())]
        keys = [_key(row) for row in step["rows"]]
        driver_shape = step.get("report_shape_ok") is True
        ordered = keys == sorted(keys)
        step["report_shape_ok"] = driver_shape and ordered
        if driver_shape and not ordered:
            step["report_shape_error"] = "the report is out of the order the gate diffs it in"
        steps.append(step)
    _attach_expected_flows(steps)
    return steps


def _attach_expected_flows(steps: Sequence[dict[str, Any]]) -> None:
    'Attach the leaking export keys implied by the frozen references.'

    by_label: dict[str, dict[str, Any]] = {}
    for step in steps:
        label = str(step.get("label"))
        earlier = str(step["event"].get("variant_of") or "")
        same_set = str(step["event"].get("same_set_as") or "")
        if earlier:
            before = by_label.get(earlier)
            if before is None:
                raise ValueError(f"variant {label!r} precedes its reference {earlier!r}")
            wanted = Counter((key[3], dataset) for key, dataset in before["expected"].items())
            expected: dict[tuple[str, int, int, str], str] = {}
            for tag, count in sorted(wanted.items()):
                matches = sorted(
                    key for key, dataset in step["exports"].items()
                    if (key[3], dataset) == tag
                )
                if len(matches) != count:
                    raise ValueError(
                        f"variant {label!r} has {len(matches)} exports for {tag!r}; expected {count}"
                    )
                expected.update((key, step["exports"][key]) for key in matches)
        elif same_set:
            before = by_label.get(same_set)
            if before is None:
                raise ValueError(f"order variant {label!r} precedes {same_set!r}")
            expected = dict(before["expected"])
            if set(expected) - set(step["exports"]):
                raise ValueError(f"order variant {label!r} does not contain the same exports")
        else:
            expected = dict(step["reference"])
        step["expected"] = expected
        by_label[label] = step


def _reported(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    protocol = frozen_protocol()
    return [
        row for row in step["rows"] if str(row.get("check")) != protocol.BASELINE_CHECK
    ]


def _stopped(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _failure(
            "scan_step_failed",
            label=str(step.get("label")),
            error=_safe_error(step.get("error")),
        )
        for step in steps
        if not step.get("ok")
    ]


def _finished(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in steps if step.get("ok")]


def _rule_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = _stopped(steps)
    if failures:
        return failures
    for step in _finished(steps):
        label, exports = str(step.get("label")), step["exports"]
        seen = {
            _key(row): str(row.get("dataset", ""))
            for row in _reported(step)
            if _key(row) in exports
        }
        for module in sorted(step["standalone"]):
            expected = {key: value for key, value in step["reference"].items() if key[0] == module}
            reported = {key: value for key, value in seen.items() if key[0] == module}
            for key in sorted(expected):
                if key not in reported:
                    failures.append(
                        _failure(
                            "leaking_export_missed", label=label, module=module,
                            line=int(key[1]), check=str(key[3]), dataset=_dataset(expected[key]),
                        )
                    )
            for key in sorted(reported):
                if key not in expected:
                    failures.append(
                        _failure(
                            "clean_export_flagged", label=label, module=module,
                            line=int(key[1]), check=str(key[3]),
                            dataset=_dataset(exports.get(key)),
                        )
                    )
    return failures


def _tags(step: Mapping[str, Any]) -> Counter:
    exports = step["exports"]
    return Counter(
        (key[3], exports[key])
        for row in _reported(step)
        for key in (_key(row),)
        if key in exports
    )


def _refactor_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = _stopped(steps)
    if failures:
        return failures
    by_label = {str(step.get("label")): step for step in steps}
    for step in _finished(steps):
        earlier = str(step["event"].get("variant_of") or "")
        before = by_label.get(earlier)
        if not before or not before.get("ok"):
            continue
        left, right = _tags(before), _tags(step)
        for check, dataset in sorted(set(left) | set(right)):
            here, there = left[(check, dataset)], right[(check, dataset)]
            if here == there:
                continue
            kind = (
                "export_lost_when_the_step_moved"
                if here > there
                else "export_appeared_when_the_step_moved"
            )
            failures.append(
                _failure(
                    kind, dataset=_dataset(dataset), check=check, inline_label=earlier,
                    extracted_label=str(step.get("label")), inline_rows=int(here),
                    extracted_rows=int(there),
                )
            )
    return failures


def _order_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = _stopped(steps)
    if failures:
        return failures
    by_label = {str(step.get("label")): step for step in steps}
    for step in _finished(steps):
        earlier = str(step["event"].get("same_set_as") or "")
        other = by_label.get(earlier)
        if not other or not other.get("ok"):
            continue
        label = str(step.get("label"))
        here = [_key(row) for row in step["rows"]]
        there = [_key(row) for row in other["rows"]]
        missing = sorted(set(here) ^ set(there))
        if missing:
            key = missing[0]
            failures.append(
                _failure(
                    "finding_lost_in_one_order", label=label, other_label=earlier,
                    module=str(key[0]), line=int(key[1]), check=str(key[3]),
                    dataset=_dataset(step["exports"].get(key, other["exports"].get(key))),
                    rows_here=len(here), rows_there=len(there),
                )
            )
        elif here != there:
            failures.append(
                _failure(
                    "rows_ordered_by_scan_order", label=label, other_label=earlier,
                    first_module=_label(here[0]), other_first_module=_label(there[0]),
                    rows=len(here),
                )
            )
    for step in _finished(steps):
        if step.get("report_shape_ok", True):
            continue
        rows = step["rows"]
        failures.append(
            _failure(
                "report_out_of_gate_order", label=str(step.get("label")),
                error=_safe_error(step.get("report_shape_error")), rows=len(rows),
                first_module=_label(_key(rows[0])) if rows else "nowhere at all",
            )
        )
    return failures


def _identity_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = _stopped(steps)
    if failures:
        return failures
    for step in _finished(steps):
        label = str(step.get("label"))
        exports, existing, expected = step["exports"], step["existing"], step["expected"]
        counted = Counter(_key(row) for row in step["rows"])
        reported = Counter(_key(row) for row in _reported(step))
        for key in sorted(expected):
            if reported[key] == 0:
                failures.append(
                    _failure(
                        "leaking_export_unreported", label=label, module=str(key[0]),
                        line=int(key[1]), check=str(key[3]), dataset=_dataset(expected[key]),
                    )
                )
        for key, number in sorted(counted.items()):
            if number > 1:
                failures.append(
                    _failure(
                        "export_flagged_twice", label=label, module=str(key[0]),
                        line=int(key[1]), check=str(key[3]), rows=int(number),
                        dataset=_dataset(exports.get(key, existing.get(key))),
                    )
                )
        for row in _reported(step):
            key = _key(row)
            source_dataset = exports.get(key, existing.get(key))
            if source_dataset is not None and str(row.get("dataset", "")) != str(source_dataset):
                failures.append(
                    _failure(
                        "report_row_mislabels_export", label=label, module=str(key[0]),
                        line=int(key[1]), check=str(key[3]),
                        dataset=_dataset(source_dataset),
                        reported_dataset=_dataset(row.get("dataset")),
                    )
                )
        for key in sorted(reported):
            if key in expected or key not in exports:
                continue
            failures.append(
                _failure(
                    "clean_export_reported", label=label, module=str(key[0]),
                    line=int(key[1]), check=str(key[3]), dataset=_dataset(exports[key]),
                )
            )
        for key in sorted(counted):
            if key in exports or key in existing:
                continue
            failures.append(
                _failure(
                    "report_row_is_not_an_export", label=label, module=str(key[0]),
                    line=int(key[1]), check=str(key[3]),
                    dataset=_dataset(_dataset_of(step, key)),
                )
            )
    return failures


def _dataset_of(step: Mapping[str, Any], key: Sequence[Any]) -> str:
    for row in step["rows"]:
        if _key(row) == tuple(key):
            return str(row.get("dataset", ""))
    return ""


def _baseline_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures = _stopped(steps)
    if failures:
        return failures
    protocol = frozen_protocol()
    for step in _finished(steps):
        label, existing = str(step.get("label")), step["existing"]
        seen = {
            _key(row): str(row.get("dataset", ""))
            for row in step["rows"]
            if str(row.get("check")) == protocol.BASELINE_CHECK
        }
        for key in sorted(existing):
            if key not in seen:
                failures.append(
                    _failure(
                        "existing_row_dropped", label=label, module=str(key[0]),
                        line=int(key[1]), dataset=_dataset(existing[key]), kept=len(seen),
                        expected=len(existing),
                    )
                )
            elif seen[key] != existing[key]:
                failures.append(
                    _failure(
                        "existing_row_changed", label=label, module=str(key[0]),
                        line=int(key[1]), dataset=_dataset(existing[key]),
                        reported_dataset=_dataset(seen[key]), kept=len(seen),
                        expected=len(existing),
                    )
                )
        for key in sorted(seen):
            if key not in existing:
                failures.append(
                    _failure(
                        "unexpected_existing_row", label=label, module=str(key[0]),
                        line=int(key[1]), dataset=_dataset(seen[key]), kept=len(seen),
                        expected=len(existing),
                    )
                )
    return failures


def flagged_tags(step: Mapping[str, Any]) -> list[str]:
    return sorted(f"{check} {dataset}" for check, dataset in _tags(step).elements())


def report_in_order(step: Mapping[str, Any]) -> list[str]:
    return [
        f"{row['module']}:{row['line']} {row['check']} {row.get('dataset', '')}".strip()
        for row in step["rows"]
    ]


def reviewer_marks(step: Mapping[str, Any]) -> dict[str, int]:
    'How many exports the office marked on its own pass over each reviewed     step file.'

    marks: dict[str, int] = {name: 0 for name in sorted(step["standalone"])}
    for key in step["reference"]:
        marks[str(key[0])] = marks.get(str(key[0]), 0) + 1
    return marks


def existing_rows_view(step: Mapping[str, Any]) -> dict[str, Any]:
    protocol = frozen_protocol()
    existing = step["existing"]
    signed_off = [
        {
            "module": str(key[0]), "line": int(key[1]), "col": int(key[2]),
            "check": str(key[3]), "dataset": str(existing[key]),
        }
        for key in sorted(existing)
    ]
    returned = [
        dict(row) for row in step["rows"]
        if str(row.get("check")) == protocol.BASELINE_CHECK
    ]
    return {
        "existing_audit_rows_signed_off": signed_off,
        "existing_audit_rows_this_report_returned": returned,
    }


def report_rows(step: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [dict(row) for row in step["rows"]]


def _analyse(candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict:
    error = _records_error(candidate, program)
    if error:
        return failed_analysis(error, tuple(BUCKETS.values()))
    steps = read_steps(candidate, program)
    return {
        "rule_failures": _rule_failures(steps),
        "refactor_failures": _refactor_failures(steps),
        "order_failures": _order_failures(steps),
        "identity_failures": _identity_failures(steps),
        "baseline_failures": _baseline_failures(steps),
    }


def _records_error(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> str | None:
    'Why the driver result cannot represent one complete run, if any.'

    records = candidate.get("records")
    if not isinstance(records, list):
        return "the run did not return a list of scan records"
    if len(records) != len(program):
        return f"the run returned {len(records)} scan records for {len(program)} scans"
    for index, (event, record) in enumerate(zip(program, records)):
        if not isinstance(record, Mapping):
            return f"scan {index} did not return a record"
        if record.get("type") != event.get("type"):
            return f"scan {index} returned the wrong record type"
        if record.get("index") != index:
            return f"scan {index} returned the wrong record index"
        if record.get("label") != event.get("label"):
            return f"scan {index} returned the wrong record label"
        if not isinstance(record.get("ok"), bool):
            return f"scan {index} did not say whether it finished"
        if not record["ok"]:
            continue
        if not isinstance(record.get("rows"), list):
            return f"scan {index} did not return a row list"
        if not isinstance(record.get("report_shape_ok"), bool):
            return f"scan {index} did not return the gate result"
        try:
            for row in record["rows"]:
                if not isinstance(row, Mapping):
                    raise TypeError
                _key(row)
                str(row.get("dataset", ""))
        except (KeyError, TypeError, ValueError):
            return f"scan {index} returned a row the report cannot read"
    return None


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the triage console shows when a drill did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still reading the pipeline after {limit} and the box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the pass ended without saying why"
    return f"the pass stopped part way through the pipeline: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private drill against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["number"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"drill": "release"}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
