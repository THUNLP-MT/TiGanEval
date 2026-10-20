'Deterministic, sandboxed measurement of the workflow engine.'

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
)

from ..workspace.fulfilment.protocol import Chart
from .workload import (
    PRIVATE_RUNS,
    SCENARIOS,
    ReferenceRun,
    chart_spec,
    payload_for,
    reference_reports,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("fulfilment/scopes.py", "fulfilment/helpers.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-state-scope-",
    timeout=60.0,
)

BUCKETS: Mapping[str, str] = {
    "scope_ownership": "ownership_failures",
    "entry_isolation": "isolation_failures",
    "resume_depth": "resume_failures",
    "change_audit": "audit_failures",
    "refused_writes": "refusal_failures",
}


AUDIT_WINDOW = 6

_CACHE = AnalysisCache()


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= 90 else text[:87] + "..."


def _route_step(chart: Chart, point: str) -> str:
    'The step a resume route puts work back into, as the chart declares it.'

    try:
        return str(chart.resume_state(str(point)))
    except KeyError:
        return str(point)


def _standing_at(chart: Chart, state: str) -> str:
    '``state`` and the steps it sits inside, the way the tooling shows a claim.'

    try:
        chain = chart.scope_chain(str(state))
    except KeyError:
        return str(state)
    return " > ".join(reversed(chain))


def _change_key(record: Mapping[str, Any]) -> str:
    return json.dumps(
        [record.get("state"), record.get("field"), record.get("before"), record.get("after")],
        ensure_ascii=False,
        default=str,
    )


def _refusal_sites(records: Any) -> dict[tuple[str, str], str]:
    'The site each refusal names, mapped to the reason the engine gave for it.'
    sites: dict[tuple[str, str], str] = {}
    for item in records or ():
        site = (str(item.get("state")), str(item.get("field")))
        sites.setdefault(site, str(item.get("code")))
    return sites


def _with_data(chart: Chart, values: Any) -> dict[str, Any]:
    'The states of one ``values()`` reading that declare fields of their own.'
    kept: dict[str, Any] = {}
    for state, body in dict(values or {}).items():
        try:
            declares = bool(dict(chart.declared(state)))
        except KeyError:
            declares = True
        if declares:
            kept[str(state)] = body
    return kept


def _reportable_error(error: str) -> str:
    text = str(error).strip()
    if text.startswith(("candidate process exited", "candidate returned")):
        return "the engine stopped before it produced a single event"
    return text


def _stub_analysis(error: str, programme: str) -> dict[str, Any]:
    failure = {
        "kind": CANDIDATE_FAILURE,
        "programme": str(programme),
        "error": _reportable_error(error),
    }
    analysis: dict[str, Any] = {"harness_error": str(error), "events": 0}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _ownership(
    chart: Chart, step: Mapping[str, Any], observed: Mapping[str, Any], expected: Mapping[str, Any]
) -> list[dict[str, Any]]:
    want = _with_data(chart, expected.get("values"))
    got = _with_data(chart, observed.get("values"))
    common = {"order": str(step["order"]), "event": str(step["event"])}
    findings: list[dict[str, Any]] = []
    for state in sorted(set(want) | set(got)):
        if state not in got:
            findings.append({"kind": "state_lost_its_data", "state": state, **common})
            continue
        if state not in want:
            findings.append({"kind": "left_state_still_carried", "state": state, **common})
            continue
        here, there = dict(want[state]), dict(got[state])
        for field in sorted(set(here) | set(there)):
            if field in here and field in there and here[field] == there[field]:
                continue
            findings.append({
                "kind": "value_read_back_wrong",
                "state": state,
                "field": field,
                "reading": _short(there.get(field)),
                "should_read": _short(here.get(field)),
                **common,
            })
    return findings


def _entries(
    step: Mapping[str, Any], observed: Mapping[str, Any], expected: Mapping[str, Any]
) -> list[dict[str, Any]]:
    want = {str(item["state"]): dict(item["values"]) for item in expected.get("entered") or ()}
    got = {str(item["state"]): dict(item["values"]) for item in observed.get("entered") or ()}
    common = {"order": str(step["order"]), "event": str(step["event"])}
    findings: list[dict[str, Any]] = []
    for state, fields in want.items():
        here = got.get(state, {})
        for field, value in fields.items():
            if field in here and here[field] == value:
                continue
            findings.append({
                "kind": "entry_started_from_the_last_pass",
                "state": state,
                "field": field,
                "reading": _short(here.get(field)),
                "should_read": _short(value),
                **common,
            })
    return findings


def _carrying(chart: Chart, state: str, values: Any) -> int:
    "How many of ``state``'s own fields are at something other than where the     flow starts them, as the tooling shows the step to whoever picks work up."

    try:
        declared = dict(chart.declared(str(state)))
    except KeyError:
        return 0
    held = dict(values or {})
    return sum(1 for field, default in declared.items() if held.get(field) != default)


def _resume(
    chart: Chart, step: Mapping[str, Any], observed: Mapping[str, Any], expected: Mapping[str, Any]
) -> list[dict[str, Any]]:
    want = dict(expected.get("values") or {})
    got = dict(observed.get("values") or {})
    point = str(expected.get("resume"))
    route_step = _route_step(chart, point)
    common = {
        "order": str(step["order"]),
        "event": str(step["event"]),
        "point": point,


        "came_back_into": route_step,
        "came_back_into_carrying": _carrying(chart, route_step, got.get(route_step)),
    }
    findings: list[dict[str, Any]] = []
    for state in sorted(want):
        here = dict(want[state])
        there = dict(got.get(state) or {})
        for field in sorted(here):
            if field in there and there[field] == here[field]:
                continue
            default = dict(chart.declared(state)).get(field)
            reading, should = there.get(field), here[field]
            if should != default and reading == default:
                kind = "resume_came_back_empty"
            elif should == default and reading != default:
                kind = "resume_restored_too_deep"
            else:
                kind = "resume_came_back_changed"
            findings.append({
                "kind": kind,
                "state": state,
                "field": field,
                "reading": _short(reading),
                "should_read": _short(should),
                "standing_at": _standing_at(chart, state),
                **common,
            })
    return findings


def _site(key: str) -> tuple[str, str]:
    raw = json.loads(key)
    return str(raw[0]), str(raw[1])


def _tells_the_truth(
    state: str,
    field: str,
    lines: Sequence[Mapping[str, Any]],
    values_now: Any,
    values_before: Any,
    entered: set[str],
    left: set[str],
) -> bool:
    "Whether this run's lines for one site account for this run's own data."

    if state in entered and state not in left:
        opened: Any = None
    else:
        was = dict(dict(values_before or {}).get(state) or {})
        if field not in was:
            return False
        opened = was[field]
    if state in left and state not in entered:
        closed: Any = None
    else:
        now = dict(dict(values_now or {}).get(state) or {})
        if field not in now:
            return False
        closed = now[field]
    for line in lines:
        if line.get("before") != opened or line.get("before") == line.get("after"):
            return False
        opened = line.get("after")
    return opened == closed


def _drop_truthful_sites(
    missing: Counter,
    extra: Counter,
    observed: Mapping[str, Any],
    values_before: Any,
) -> None:
    "Take out the sites where the run's lines describe the run's own data."

    entered = {str(item.get("state")) for item in observed.get("entered") or ()}
    left = {str(state) for state in observed.get("left") or ()}
    records = [dict(item) for item in observed.get("changes") or ()]
    shared = {_site(key) for key in missing} & {_site(key) for key in extra}
    for state, field in sorted(shared):
        here = [key for key in missing if _site(key) == (state, field)]
        there = [key for key in extra if _site(key) == (state, field)]
        lines = [
            item
            for item in records
            if (str(item.get("state")), str(item.get("field"))) == (state, field)
        ]
        if not _tells_the_truth(
            state, field, lines, observed.get("values"), values_before, entered, left
        ):
            continue
        for key in here:
            del missing[key]
        for key in there:
            del extra[key]


def _audit(
    step: Mapping[str, Any],
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
    previous: Sequence[Mapping[str, Any]],
    previous_event: str,
    values_before: Any = None,
) -> list[dict[str, Any]]:
    want = Counter(_change_key(item) for item in expected.get("changes") or ())
    got = Counter(_change_key(item) for item in observed.get("changes") or ())
    if want == got:
        return []
    missing = want - got
    extra = got - want
    _drop_truthful_sites(missing, extra, observed, values_before)
    if not missing and not extra:
        return []
    common = {
        "order": str(step["order"]),
        "event": str(step["event"]),
        "lines_the_step_should_write": sum(want.values()),
        "lines_the_run_wrote": sum(got.values()),
    }
    carried = Counter(_change_key(item) for item in previous)
    if carried and not (carried - extra):
        sample = json.loads(next(iter(carried)))
        return [{
            "kind": "audit_carried_the_previous_step",
            "state": str(sample[0]),
            "field": str(sample[1]),
            "previous_event": str(previous_event),
            "reading": _short(sample[3]),
            **common,
        }]
    shared = sorted({_site(key) for key in missing} & {_site(key) for key in extra})
    if shared:
        state, field = shared[0]
        wrote = next(
            (json.loads(key) for key in extra if _site(key) == (state, field)), None
        )


        held = dict(dict(observed.get("values") or {}).get(state) or {}).get(field)
        return [{
            "kind": "audit_line_wrong_values",
            "state": str(state),
            "field": str(field),
            "reading": _short(None if wrote is None else wrote[3]),
            "should_read": _short(held),
            **common,
        }]
    if extra:
        sample = json.loads(sorted(extra)[0])
        return [{
            "kind": "audit_line_repeated",
            "state": str(sample[0]),
            "field": str(sample[1]),
            "reading": _short(sample[3]),
            **common,
        }]
    sample = json.loads(sorted(missing)[0])
    return [{
        "kind": "audit_line_missing",
        "state": str(sample[0]),
        "field": str(sample[1]),
        "reading": _short(sample[3]),
        **common,
    }]


def _refusals(
    chart: Chart,
    step: Mapping[str, Any],
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'The distinct things that happen at a handler step, kept apart: a step the     flow does not allow is served anyway, turned away for the wrong reason, or     brings the engine down instead of being turned away, and a step the flow     does allow is served or turned away.'

    want = _refusal_sites(expected.get("refusals"))
    got = _refusal_sites(observed.get("refusals"))
    broke = {
        (str(item.get("state")), str(item.get("field")))
        for item in observed.get("step_errors") or ()
    }
    common = {"order": str(step["order"]), "event": str(step["event"])}
    findings: list[dict[str, Any]] = [
        {"kind": "step_broke_instead_of_refusing", "state": state, "field": field, **common}
        for state, field in sorted(broke)
    ]
    for (state, field), code in sorted(want.items()):
        if (state, field) in broke:
            continue
        site = {"state": state, "field": field, **common}
        if (state, field) not in got:
            findings.append({"kind": "bad_write_went_through", "code": code, **site})
            continue
        gave = got[(state, field)]
        if gave != code:
            findings.append(
                {"kind": "refused_with_the_wrong_code", "code": gave, "should_read": code, **site}
            )
        reading = _site_value(chart, observed.get("values"), state, field)
        should_read = _site_value(chart, expected.get("values"), state, field)
        if reading != should_read:
            findings.append({
                "kind": "refusal_changed_the_data",
                "code": gave,
                "reading": _site_reading(reading),
                "should_read": _site_reading(should_read),
                **site,
            })
    findings.extend(
        {"kind": "good_write_refused", "state": state, "field": field, "code": code, **common}
        for (state, field), code in sorted(got.items())
        if (state, field) not in want
    )
    return findings


def _site_value(chart: Chart, values: Any, state: str, field: str) -> tuple[bool, Any]:
    'The actual stored value addressed by a handler site.'
    try:
        owner = chart.declaring_state(state, field)
    except KeyError:
        owner = None
    bag = dict(dict(values or {}).get(str(owner or state)) or {})
    return field in bag, deepcopy(bag.get(field))


def _site_reading(site: tuple[bool, Any]) -> str:
    'Render presence as well as value for an addressed storage site.'

    present, value = site
    return _short(value) if present else "no stored value"


def _isolation(
    orders: Sequence[str],
    steps: Sequence[Mapping[str, Any]],
    interleaved: Sequence[Mapping[str, Any]],
    alone: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    "One order's data may not depend on which other orders shared the process."
    findings: list[dict[str, Any]] = []
    for order in orders:
        together = [
            (dict(step), dict(record))
            for step, record in zip(steps, interleaved)
            if str(step["order"]) == order
        ]
        apart = [dict(record) for record in alone.get(order, ())]
        for (step, mixed), single in zip(together, apart):
            here = dict(mixed.get("values") or {})
            there = dict(single.get("values") or {})
            for state in sorted(set(here) | set(there)):
                fields = dict(here.get(state) or {})
                others = dict(there.get(state) or {})
                for field in sorted(set(fields) | set(others)):
                    if fields.get(field) == others.get(field):
                        continue
                    findings.append({
                        "kind": "orders_reading_each_others_data",
                        "order": order,
                        "event": str(step["event"]),
                        "state": state,
                        "field": field,
                        "reading": _short(fields.get(field)),
                        "alone": _short(others.get(field)),
                    })
    return findings


def _declarations(chart: Chart, outcome: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The chart every run of the night started from is the chart it ends with.'

    if "declarations_after" not in outcome:
        return []
    after = dict(outcome.get("declarations_after") or {})
    findings: list[dict[str, Any]] = []
    for state in chart.states():
        due = dict(chart.declared(state))
        now = dict(after.get(state) or {})
        for field in sorted(set(due) | set(now)):
            if field in now and now[field] == due[field]:
                continue
            findings.append({
                "kind": "the_chart_itself_was_changed",
                "state": str(state),
                "field": str(field),
                "reading": _short(now.get(field)),
                "should_read": _short(due.get(field)),
            })
    return findings


def _analyse(
    outcome: Mapping[str, Any], spec: Mapping[str, Any], steps: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    chart = Chart(deepcopy(dict(spec)))
    reports = [dict(item) for item in outcome.get("interleaved") or ()]
    ownership: list[dict[str, Any]] = []
    isolation: list[dict[str, Any]] = []
    resume: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    refusal: list[dict[str, Any]] = []
    runs: dict[str, ReferenceRun] = {}
    last_values, last_changes, last_event = {}, {}, {}

    for step, record in zip(steps, reports):
        order = str(step["order"])
        event = str(step["event"])
        run = runs.get(order)
        if run is None:
            run = runs[order] = ReferenceRun(chart, order)
        expected = run.expect(
            event,
            dict(step.get("payload") or {}),
            config_before=record.get("config_before"),
            values_before=last_values.get(order),
        )
        if expected.get("resume"):
            resume.extend(_resume(chart, step, record, expected))
        else:
            ownership.extend(_ownership(chart, step, record, expected))
            isolation.extend(_entries(step, record, expected))
        previous = last_changes.get(order, [])
        audit.extend(
            _audit(
                step,
                record,
                expected,
                previous,
                last_event.get(order, "start"),
                last_values.get(order),
            )
        )
        refusal.extend(_refusals(chart, step, record, expected))
        last_values[order] = dict(record.get("values") or {})
        last_changes[order] = list(expected.get("changes") or ())
        last_event[order] = event

    isolation.extend(_declarations(chart, outcome))
    orders = [str(name) for name in outcome.get("orders") or ()]
    alone = {str(key): list(value) for key, value in dict(outcome.get("alone") or {}).items()}
    isolation.extend(_isolation(orders, steps, reports, alone))
    if len(reports) != len(steps):
        ownership.append({
            "kind": "state_lost_its_data",
            "order": str(steps[len(reports)]["order"]) if reports else "R-88",
            "event": str(steps[len(reports)]["event"]) if reports else "start",
            "state": "Assessing",
        })
    return {
        "ownership_failures": ownership,
        "isolation_failures": isolation,
        "resume_failures": resume,
        "audit_failures": audit,
        "refusal_failures": refusal,
        "events": len(reports),
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run both private programmes against this workspace and read them.'
    def compute() -> Mapping[str, Any]:
        combined: dict[str, Any] = {
            bucket: [] for bucket in BUCKETS.values()
        }
        combined["events"] = 0
        cases: list[dict[str, Any]] = []
        for programme, private_run in PRIVATE_RUNS.items():
            payload = payload_for(programme)
            steps = payload["steps"]
            outcome = PROJECT.invoke(artifact_dir, payload)
            if not outcome.get("ok"):
                analysis = _stub_analysis(
                    str(outcome.get("error", "the engine could not be run")),
                    programme,
                )
            else:
                analysis = _analyse(outcome, payload["chart"], steps)
            for bucket in BUCKETS.values():
                combined[bucket].extend(analysis.get(bucket) or ())
            combined["events"] += int(analysis.get("events", 0))
            cases.append({
                "programme": programme,
                "chart": str(private_run["chart"]),
                "orders": len({str(step["order"]) for step in steps}),
                "steps": len(steps),
            })
        return {**combined, "cases": cases}

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _declares(chart: Chart, state: str) -> dict[str, Any]:
    return {
        field: {"type": type(default).__name__, "starts_at": deepcopy(default)}
        for field, default in dict(chart.declared(state)).items()
    }


def _chart_summary(spec: Mapping[str, Any]) -> dict[str, Any]:
    chart = Chart(deepcopy(dict(spec)))
    return {
        "states": {
            state: {"parent": chart.parent_of(state), "declares": _declares(chart, state)}
            for state in chart.states()
        },
        "resume_points": {
            point: {"state": chart.resume_state(point), "reaches": chart.resume_kind(point)}
            for point in chart.resume_points()
        },
    }


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The workflow engine workspace and the recorded scenarios are available.",
        "measurements": {
            "workspace_hash": artifact_hash(artifact_dir),
            "project_records": [f"project_records/{path.name}" for path in records],
            "chart": "fulfilment/order_flow.py",
            **_chart_summary(chart_spec("order_flow")),
        },
        "observed": {},
    }


_FLOOR_NOTES: Mapping[str, str] = {
    "overnight-hold-drill": (
        "What the floor wrote down the last time an order was held overnight, before the "
        "generic runner landed: when the late shift picked it back up the same evening it "
        "carried on from the three lines it had already picked, was still on its first "
        "picker attempt, and the two shelf holds it had taken were still against it. The "
        "next morning's re-plan carried on from the four lines and the second attempt it "
        "had reached by then, and the picker took its shelf holds again from nothing. The "
        "floor's own screen for each of those two mornings is under "
        "`what_the_floor_screen_showed`, step by step."
    ),
    "evening-batch-run": (
        "The evening batch puts every order of the shift through one process, one event at a "
        "time, in the order the floor raises them. Each order is replayed here on its own as "
        "well, so the two accounts of the same order can be set beside each other."
    ),
}

_SCREEN_NOTE = (
    "The floor's tooling screen for the order the moment it came back, kept from before the "
    "generic runner landed: one entry per route the order came back through, listing the "
    "steps the order was standing in and what each of them was holding. Nothing here is a "
    "judgement of the current build; it is what the screen showed on those two mornings."
)

_KEPT_LINES_NOTES: Mapping[str, str] = {
    "handler-typo-drill": (
        "The audit reader keeps its own copy of the first few events of every scenario; "
        "these are the lines it holds for this one from before the generic runner landed."
    ),
    "overnight-hold-drill": (
        "The reader keeps the hold and the pick-up either side of an overnight break as "
        "well, because finance reconcile a held order by hand; these are the lines it holds "
        "for those two events from before the generic runner landed."
    ),
}


def _kept_audit_lines(
    spec: Mapping[str, Any], steps: Sequence[Mapping[str, Any]], record_id: str
) -> list[dict[str, Any]] | None:
    'The events of one scenario the audit reader kept its own copy of.'

    if record_id not in _KEPT_LINES_NOTES:
        return None
    reports = reference_reports(spec, steps)
    if record_id == "handler-typo-drill":
        kept = reports[:AUDIT_WINDOW]
    else:
        back = next(
            (index for index, report in enumerate(reports) if report.get("resume")), None
        )
        kept = [] if back is None else reports[max(back - 1, 0) : back + 1]
    return [
        {"event": str(report.get("event")), "lines": list(report.get("changes") or ())}
        for report in kept
    ]


def _floor_screen(
    spec: Mapping[str, Any], steps: Sequence[Mapping[str, Any]], record_id: str
) -> list[dict[str, Any]] | None:
    "What the floor's screen showed each time an order came back off a hold."

    if record_id != "overnight-hold-drill":
        return None
    return [
        {
            "came_back_through": str(report.get("resume")),
            "the_order_was_standing_in": list(report.get("config") or ()),
            "what_each_step_was_holding": dict(report.get("values") or {}),
        }
        for report in reference_reports(spec, steps)
        if report.get("resume")
    ]


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in SCENARIOS:
        raise ValueError(f"unknown project record: {record_id}")
    payload = payload_for(record_id)
    steps = payload["steps"]
    outcome = PROJECT.invoke(artifact_dir, payload)
    measurements: dict[str, Any] = {
        "record_id": record_id,
        "chart": str(SCENARIOS[record_id]["chart"]),
        "orders": sorted({str(step["order"]) for step in steps}),
        "events": len(steps),
    }
    if record_id in _FLOOR_NOTES:
        measurements["what_the_floor_noted"] = _FLOOR_NOTES[record_id]
    screen = _floor_screen(payload["chart"], steps, record_id)
    if screen:
        measurements["what_the_floor_screen_showed"] = screen
        measurements["what_the_floor_screen_showed_note"] = _SCREEN_NOTE
    kept = _kept_audit_lines(payload["chart"], steps, record_id)
    if kept:
        measurements["audit_lines_the_reader_kept"] = kept
        measurements["audit_lines_note"] = _KEPT_LINES_NOTES[record_id]
    if not outcome.get("ok"):
        return {
            "summary": "The recorded scenario could not be run against this workspace.",
            "measurements": measurements,
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    alone = {str(key): list(value) for key, value in dict(outcome.get("alone") or {}).items()}
    timeline = []
    for index, (step, record) in enumerate(zip(steps, outcome.get("interleaved") or ())):
        record = dict(record)
        entry = {
            "order": record.get("order"),
            "event": record.get("event"),
            "states_the_order_is_in": record.get("config"),
            "states_it_left": record.get("left"),
            "data_after_the_event": record.get("values"),
            "data_as_each_state_was_entered": record.get("entered"),
            "came_back_through": record.get("resume"),
            "audit_lines_for_this_event": record.get("changes"),
            "steps_the_engine_would_not_serve": record.get("refusals"),
            "steps_that_broke": record.get("step_errors"),
        }
        if record_id == "evening-batch-run":
            same = alone.get(str(step["order"]), [])
            earlier = steps[:index]
            position = sum(1 for item in earlier if str(item["order"]) == str(step["order"]))
            if position < len(same):
                entry["data_when_this_order_runs_alone"] = dict(same[position]).get("values")
        timeline.append(entry)
    return {
        "summary": "The recorded scenario ran against this workspace.",
        "measurements": measurements,
        "observed": {"run_timeline": timeline},
    }
