'Deterministic, sandboxed review of one order-platform workspace.'

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("orders/policy.py", "orders/contract.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-orders-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "rehearsal", "variant": 90}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "checkout-admissions": {"profile": "checkout", "variant": 11},
    "fulfilment-escalation": {"profile": "fulfilment", "variant": 23},
    "schema-publication": {"profile": "publication", "variant": 37},
    "support-dashboard-sweep": {"profile": "dashboard", "variant": 51},
}

BUCKETS: Mapping[str, str] = {
    "admission_matches_reference": "admission_failures",
    "update_guarded_by_the_store": "update_failures",
    "stored_items_stay_reachable": "reach_failures",
    "contract_agrees_with_the_writer": "contract_failures",
    "declarations_are_enforceable": "declaration_failures",
}

_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The storage client as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "orders" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_orders_protocol", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module

        written, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = written
        _FROZEN = module
    return _FROZEN


def _value_at(scope: Any, path: str) -> Any:
    value: Any = scope
    for part in str(path).split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def owed(attributes: Mapping[str, Any], scope: Mapping[str, Any], prefix: str = "") -> list[str]:
    "The attributes this scope still owes, by the document's own rules."

    missing: list[str] = []
    for name, attr in dict(attributes).items():
        value = scope.get(name)
        if attr.kind == "map" and isinstance(value, Mapping):
            missing.extend(owed(attr.attributes, value, f"{prefix}{name}."))
        binding = attr.required or any(
            scope.get(rule.controller) is not None and scope.get(rule.controller) in tuple(rule.values)
            for rule in attr.required_when
        )
        if binding and value is None:
            missing.append(f"{prefix}{name}")
    return missing


def admission_truth(schema: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    protocol = frozen_protocol()
    item = protocol.apply_defaults(schema, dict(payload))
    missing = owed(schema.attributes, item)
    return {"accepted": not missing, "missing": missing, "item": item}


def _apply_changes(view: Mapping[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    protocol = frozen_protocol()
    after = json.loads(json.dumps(dict(view)))
    for path, value in dict(changes.get("set") or {}).items():
        if value is None:
            protocol.remove_path(after, str(path))
        else:
            protocol.write_path(after, str(path), value)
    for path in changes.get("remove") or ():
        protocol.remove_path(after, str(path))
    return after


def _trail_for(schema: Any, name: str) -> tuple[Any, ...]:
    protocol = frozen_protocol()
    for trail in protocol.walk(schema.attributes):
        if protocol.logical_path(trail) == name:
            return tuple(trail)
    raise ValueError(f"{schema.name} has no attribute at {name}")


def _stored_value(attr: Any, value: Any, where: str) -> Any:
    if attr.kind != "map":
        return value
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be a map")
    stored: dict[str, Any] = {}
    for name, child_value in dict(value).items():
        child = attr.attributes.get(str(name))
        if child is None:
            raise ValueError(f"{where} has no attribute called {name}")
        if child_value is not None:
            stored[child.stored_as] = _stored_value(child, child_value, f"{where}.{name}")
    return stored


def _expected_stored_after(schema: Any, event: Mapping[str, Any]) -> dict[str, Any]:
    protocol = frozen_protocol()
    patch: dict[str, Any] = {"set": {}, "remove": []}
    for name, value in dict(dict(event["changes"]).get("set") or {}).items():
        trail = _trail_for(schema, str(name))
        stored = protocol.physical_path(trail)
        if value is None:
            patch["remove"].append(stored)
        else:
            patch["set"][stored] = _stored_value(trail[-1], value, str(name))
    for name in dict(event["changes"]).get("remove") or ():
        patch["remove"].append(protocol.stored_paths(schema, [str(name)])[0])
    key = str(event["key"])
    store = protocol.Store({key: dict(event["stored"])})
    store.update(key, patch)
    return dict(store.get(key) or {})


def _touches(path: str, changed: set[str]) -> bool:
    return path in changed or any(path.startswith(f"{name}.") for name in changed)


def condition_of(spec: Any) -> Any:
    protocol = frozen_protocol()
    if not spec:
        return None
    operation = str(dict(spec).get("op"))
    if operation == "equals":
        return protocol.Equals(str(spec["path"]), spec.get("value"))
    if operation == "exists":
        return protocol.Exists(str(spec["path"]))
    raise ValueError(f"unknown condition in the program: {operation}")


def update_truth(schema: Any, event: Mapping[str, Any]) -> dict[str, Any]:
    'Whether this change set may commit, and what would make it not.'

    protocol = frozen_protocol()
    stored = dict(event["stored"])
    changes = dict(event["changes"])
    before = protocol.from_stored(schema, stored)
    after = _apply_changes(before, changes)
    touched = {str(name) for name in dict(changes.get("set") or {})} | {
        str(name) for name in changes.get("remove") or ()
    }
    violations: list[dict[str, Any]] = []
    for trail in protocol.walk(schema.attributes):
        attr = trail[-1]
        prefix = protocol.logical_path(trail[:-1])
        dependent = protocol.logical_path(trail)
        for rule in attr.required_when:
            controller = f"{prefix}.{rule.controller}" if prefix else rule.controller
            if not _touches(controller, touched) and not _touches(dependent, touched):
                continue
            held = _value_at(after, controller)
            if held is not None and held in tuple(rule.values) and _value_at(after, dependent) is None:
                violations.append(
                    {
                        "attribute": dependent,
                        "controller": controller,
                        "value": held,
                        "by_removal": _touches(dependent, touched),
                    }
                )
    caller_holds = protocol.evaluate(condition_of(event.get("condition")), stored)
    commit = bool(caller_holds and not violations)
    return {
        "commit": commit,
        "caller_holds": bool(caller_holds),
        "violations": violations,
        "item_afterwards": _expected_stored_after(schema, event) if commit else stored,
    }


def declaration_problems(schema: Any) -> list[dict[str, Any]]:
    'Every declaration in this document the store could not honour.'

    protocol = frozen_protocol()
    problems: list[dict[str, Any]] = []
    for trail in protocol.walk(schema.attributes):
        attr = trail[-1]
        siblings = schema.attributes if len(trail) == 1 else trail[-2].attributes
        for rule in attr.required_when:
            where = protocol.logical_path(trail)
            if attr.is_key:
                why = "the store cannot make a key attribute conditional"
            elif rule.controller == attr.name:
                why = "the declaration names the attribute it is on"
            elif rule.controller not in dict(siblings):
                why = f"there is no attribute called {rule.controller} beside it"
            else:
                continue
            problems.append({"attribute": where, "controller": rule.controller, "why": why})
    return problems


def document_truth(schema: Any) -> dict[str, Any]:
    'Whether a document may go live, and the first reason it may not.'

    protocol = frozen_protocol()
    physical: dict[str, str] = {}
    keys: list[str] = []
    collision: str | None = None
    for trail in protocol.walk(schema.attributes):
        stored, logical = protocol.physical_path(trail), protocol.logical_path(trail)
        if stored in physical and collision is None:
            collision = f"{logical} is stored as {stored}, which {physical[stored]} already uses"
        physical.setdefault(stored, logical)
        if trail[-1].is_key:
            keys.append(logical)
    problems = declaration_problems(schema)
    refuse = bool(collision) or len(keys) != 1 or bool(problems)
    return {"acceptable": not refuse, "collision": collision, "keys": keys, "problems": problems}


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the write log shows it: the directory part of any path     stripped, and a line the owner would not say replaced.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the step ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _document_of(event: Mapping[str, Any]) -> Mapping[str, Any]:
    document = event.get("document")
    if document is not None:
        return dict(document)
    path = TASK_ROOT / "workspace" / str(event["document_path"])
    return json.loads(path.read_text(encoding="utf-8"))


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'One row per replay step, with what the documents imply beside each.'

    protocol = frozen_protocol()
    schemas: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    for event, record in zip(program, candidate.get("records", ())):
        step = {**dict(record), "event": dict(event)}
        kind = str(event.get("type"))
        if kind in ("load", "review"):
            document = _document_of(event)
            built = protocol.load_schema(document)
            if kind == "load":
                schemas[str(event["schema"])] = built
            step["schema"] = built
            step["truth"] = document_truth(built)
        else:
            schema = schemas.get(str(event.get("schema", "")))
            step["schema"] = schema
            if schema is None:
                pass
            elif kind == "admit":
                step["truth"] = admission_truth(schema, dict(event["payload"]))
            elif kind == "update":
                step["truth"] = update_truth(schema, event)
            elif kind == "read":
                projection = event.get("projection")
                physical = list(protocol.stored_paths(schema, projection)) if projection else None
                fetched = protocol.Store({str(event["key"]): dict(event["stored"])}).get(
                    str(event["key"]), physical
                )
                step["truth"] = {
                    "stored_item": fetched,
                    "view": protocol.from_stored(schema, dict(fetched or {})),
                }
            elif kind in ("publish", "rebuild"):
                step["truth"] = {
                    "verdicts": [
                        {
                            "payload": str(entry["label"]),
                            **admission_truth(schema, dict(entry["payload"])),
                        }
                        for entry in event["payloads"]
                    ]
                }
        steps.append(step)
    return steps


def _of_kind(steps: Sequence[Mapping[str, Any]], *kinds: str) -> list[Mapping[str, Any]]:
    return [step for step in steps if str(step.get("type")) in kinds]


def _admission_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_kind(steps, "admit"):
        payload, entity = str(step.get("label")), str(step["event"].get("schema"))
        truth = dict(step.get("truth") or {})
        if not step.get("ok") or step.get("accepted") is None:
            failures.append(
                _failure(
                    "write_path_operation_failed", payload=payload, entity=entity,
                    error=_safe_error(step.get("error")),
                )
            )
            continue
        accepted = bool(step.get("accepted"))
        if truth["accepted"] and not accepted:
            failures.append(
                _failure(
                    "payload_wrongly_refused", payload=payload, entity=entity,
                    refusal=_safe_error(step.get("refusal")),
                )
            )
        elif accepted and not truth["accepted"]:
            failures.append(
                _failure(
                    "payload_wrongly_accepted", payload=payload, entity=entity,
                    missing=str(truth["missing"][0]),
                )
            )
        elif accepted and step.get("item") != truth.get("item"):
            failures.append(
                _failure(
                    "admitted_item_wrong", payload=payload, entity=entity,
                    attribute=_first_difference(dict(truth.get("item") or {}), step.get("item")),
                )
            )
    return failures


def _update_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_kind(steps, "update"):
        if str(step["event"].get("bucket", "update")) != "update":
            continue
        label, key = str(step.get("label")), str(step["event"].get("key"))
        truth = dict(step.get("truth") or {})
        if not step.get("ok"):
            failures.append(
                _failure(
                    "update_path_operation_failed", update=label, key=key,
                    error=_safe_error(step.get("error")),
                )
            )
            continue
        committed = bool(step.get("committed"))
        if truth["commit"] and not committed:
            failures.append(
                _failure(
                    "harmless_update_refused", update=label, key=key,
                    refusal=_safe_error(step.get("refusal")),
                )
            )
        elif committed and not truth["commit"]:
            violations = list(truth["violations"])
            if not truth["caller_holds"]:
                failures.append(
                    _failure(
                        "caller_condition_dropped", update=label, key=key,
                        condition=json.dumps(step.get("caller_condition"), sort_keys=True),
                    )
                )
            elif violations[0]["by_removal"]:
                failures.append(
                    _failure(
                        "dependent_removal_committed", update=label, key=key,
                        attribute=str(violations[0]["attribute"]),
                        controller=str(violations[0]["controller"]),
                    )
                )
            else:
                failures.append(
                    _failure(
                        "violating_update_committed", update=label, key=key,
                        attribute=str(violations[0]["attribute"]),
                        controller=str(violations[0]["controller"]),
                    )
                )
        elif committed and step.get("item_afterwards") != truth.get("item_afterwards"):
            failures.append(
                _failure(
                    "update_result_wrong", update=label, key=key,
                    attribute=_logical_difference(
                        step.get("schema"),
                        dict(truth.get("item_afterwards") or {}),
                        step.get("item_afterwards"),
                    ),
                )
            )
    return failures


def _first_difference(expected: Mapping[str, Any], seen: Any) -> str:
    if not isinstance(seen, Mapping):
        return "the whole item"
    for name in sorted(dict(expected)):
        if name not in seen or seen[name] != expected[name]:
            return name
    for name in sorted(dict(seen)):
        if name not in expected:
            return name
    return "the whole item"


def _logical_difference(schema: Any, expected: Mapping[str, Any], seen: Any) -> str:
    protocol = frozen_protocol()
    if not isinstance(seen, Mapping):
        return "the whole item"
    for trail in protocol.walk(schema.attributes):
        physical = protocol.physical_path(trail)
        if protocol.read_stored(expected, physical) != protocol.read_stored(seen, physical):
            return protocol.logical_path(trail)
    return "the stored item"


def _reach_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_kind(steps, "read"):
        label, key = str(step.get("label")), str(step["event"].get("key"))
        projection = step["event"].get("projection")
        expected = dict(step.get("truth") or {}).get("view")
        view = step.get("view")
        broke = (not step.get("ok")) or view is None or view != expected
        if not broke:
            continue
        error = _safe_error(step.get("error") or "the read came back with something else")
        if projection:
            failures.append(
                _failure(
                    "projected_read_failed", read=label, key=key,
                    projection=", ".join(str(name) for name in projection), error=error,
                )
            )
        elif view is None or not step.get("ok"):
            failures.append(
                _failure("read_path_operation_failed", read=label, key=key, error=error)
            )
        else:
            failures.append(
                _failure(
                    "stored_item_not_returned", read=label, key=key,
                    attribute=_first_difference(dict(expected or {}), view),
                )
            )
    for step in _of_kind(steps, "update"):
        if str(step["event"].get("bucket", "update")) != "legacy":
            continue
        truth = dict(step.get("truth") or {})
        if not step.get("ok") or bool(step.get("committed")) != bool(truth["commit"]):
            failures.append(
                _failure(
                    "legacy_item_update_refused",
                    update=str(step.get("label")),
                    key=str(step["event"].get("key")),
                    refusal=_safe_error(step.get("error") or step.get("refusal")),
                )
            )
        elif truth["commit"] and step.get("item_afterwards") != truth.get("item_afterwards"):
            failures.append(
                _failure(
                    "legacy_item_update_wrong",
                    update=str(step.get("label")),
                    key=str(step["event"].get("key")),
                    attribute=_logical_difference(
                        step.get("schema"),
                        dict(truth.get("item_afterwards") or {}),
                        step.get("item_afterwards"),
                    ),
                )
            )
    return failures


def _contract_transition(here: Sequence[Any], there: Sequence[Any]) -> tuple[str, str]:
    before, after = list(here), list(there)
    if not before:
        return "accepted", "refused"
    if not after:
        return "refused", "accepted"
    return "refused for one set of reasons", "refused for a different set of reasons"


def _contract_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_kind(steps, "publish", "rebuild"):
        label, entity = str(step.get("label")), str(step["event"].get("schema"))
        if not step.get("ok"):
            failures.append(
                _failure(
                    "contract_operation_failed", label=label, entity=entity,
                    error=_safe_error(step.get("error")),
                )
            )
            continue
        writer = {
            str(dict(row).get("payload")): dict(row)
            for row in step.get("write_path_verdicts") or ()
        }
        for row in step.get("contract_verdicts") or ():
            payload = str(dict(row).get("payload"))
            complaints = list(dict(row).get("complaints") or ())
            write_verdict = writer.get(payload)
            if write_verdict is None or write_verdict.get("accepted") is None:
                failures.append(
                    _failure(
                        "contract_operation_failed", label=label, entity=entity,
                        error=_safe_error(
                            (write_verdict or {}).get("error")
                            or "the write path did not return a verdict"
                        ),
                    )
                )
            elif not complaints and not write_verdict.get("accepted"):
                failures.append(
                    _failure(
                        "contract_accepts_what_the_writer_refuses", label=label, entity=entity,
                        payload=payload,
                        refusal=_safe_error(write_verdict.get("refusal")),
                    )
                )
            elif complaints and write_verdict.get("accepted"):
                failures.append(
                    _failure(
                        "contract_refuses_what_the_writer_accepts", label=label, entity=entity,
                        payload=payload, complaint=_safe_error(complaints[0]),
                    )
                )
        for row in step.get("round_trip") or ():
            entry = dict(row)
            same_writer = entry.get("here") == entry.get("after_rebuilding")
            same_contract = list(entry.get("contract_here") or ()) == list(
                entry.get("contract_after_rebuilding") or ()
            )
            if same_writer and same_contract:
                continue
            if not same_writer:
                surface = "write-path decision"
                before = "taken" if entry.get("here") else "turned away"
                after = "taken" if entry.get("after_rebuilding") else "turned away"
            else:
                surface = "published-contract result"
                before, after = _contract_transition(
                    entry.get("contract_here") or (),
                    entry.get("contract_after_rebuilding") or (),
                )
            failures.append(
                _failure(
                    "rebuilt_schema_behaves_differently", label=label, entity=entity,
                    payload=str(entry.get("payload")),
                    surface=surface, before=before, after=after,
                )
            )
    return failures


def _declaration_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _of_kind(steps, "load", "review"):
        draft = str(step.get("label"))
        truth = dict(step.get("truth") or {})
        verdict = str(step.get("verdict", ""))
        if not step.get("ok") or verdict == "error":
            failures.append(
                _failure("review_operation_failed", draft=draft, error=_safe_error(step.get("error")))
            )
            continue
        problems = list(truth.get("problems") or ())
        if verdict == "accepted" and not truth.get("acceptable", True):
            if truth.get("collision"):
                failures.append(
                    _failure(
                        "physical_name_collision_accepted", draft=draft,
                        collision=str(truth["collision"]),
                    )
                )
            elif len(truth.get("keys") or ()) != 1:
                failures.append(
                    _failure(
                        "key_count_declaration_accepted", draft=draft,
                        key_count=len(truth.get("keys") or ()),
                    )
                )
            else:
                first = problems[0]
                failures.append(
                    _failure(
                        "unenforceable_declaration_accepted", draft=draft,
                        attribute=str(first["attribute"]), controller=str(first["controller"]),
                        why=str(first["why"]),
                    )
                )
        elif verdict == "refused" and truth.get("acceptable", False):
            failures.append(
                _failure(
                    "enforceable_declaration_refused", draft=draft,
                    error=_safe_error(step.get("error")),
                )
            )
    return failures


def _analyse(candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    steps = read_steps(candidate, program)
    return {
        "admission_failures": _admission_failures(steps),
        "update_failures": _update_failures(steps),
        "reach_failures": _reach_failures(steps),
        "contract_failures": _contract_failures(steps),
        "declaration_failures": _declaration_failures(steps),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the write log shows when a replay did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the replay box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the write path ended without saying why"
    return f"the platform stopped part way through the replay: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private rehearsal against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["variant"]))
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"replay": "rehearsal"}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
