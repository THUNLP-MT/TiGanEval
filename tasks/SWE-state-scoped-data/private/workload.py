'Charts, event programmes, and the reference scope layer they are read against.'

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from ..workspace.fulfilment.engine import Engine
from ..workspace.fulfilment.protocol import Chart, ChangeRecord, ScopeError
from ..workspace.fulfilment.order_flow import ORDER_FLOW


CLAIM_REVIEW: Mapping[str, Any] = {
    "id": "claim_review",
    "initial": "Received",
    "states": {
        "Received": {"parent": None, "data": {}},
        "Assessing": {
            "parent": None,
            "initial": "Triage",
            "data": {"claim_id": ["str", ""], "tries": ["int", 0], "notes": ["list", []]},
        },
        "Triage": {
            "parent": "Assessing",
            "initial": "Inspecting",
            "data": {"queue": ["list", []], "index": ["int", 0]},
        },
        "Inspecting": {
            "parent": "Triage",
            "initial": "Measuring",
            "data": {"marks": ["list", []], "tries": ["int", 0]},
        },
        "Measuring": {"parent": "Inspecting", "data": {"readings": ["list", []]}},
        "Grading": {"parent": "Triage", "data": {"scores": ["list", []]}},
        "Refunding": {"parent": "Assessing", "data": {"ledger": ["list", []]}},
        "Parked": {"parent": None, "data": {}},
        "Closed": {"parent": None, "data": {}},
    },
    "resume_points": {
        "pick_up": {"state": "Assessing", "kind": "full"},
        "next_day": {"state": "Assessing", "kind": "direct"},


        "back_to_bench": {"state": "Triage", "kind": "full"},
    },
    "transitions": (
        {"event": "opened", "source": "Received", "target": "Assessing"},
        {"event": "remeasure", "source": "Measuring", "target": "Measuring", "internal": True},
        {"event": "audit", "source": "Measuring", "target": "Measuring", "internal": True},
        {"event": "sampled", "source": "Measuring", "target": "Grading"},
        {"event": "reinspect", "source": "Grading", "target": "Inspecting"},
        {"event": "regrade", "source": "Grading", "target": "Grading"},
        {"event": "escalate", "source": "Triage", "target": "Refunding"},
        {"event": "park", "source": "Assessing", "target": "Parked"},
        {"event": "pick_up", "source": "Parked", "target": "Assessing", "resume": "pick_up"},
        {"event": "next_day", "source": "Parked", "target": "Assessing", "resume": "next_day"},
        {
            "event": "back_to_bench",
            "source": "Parked",
            "target": "Triage",
            "resume": "back_to_bench",
        },
        {"event": "settled", "source": "Refunding", "target": "Closed"},
    ),
    "callbacks": {
        "enter:Assessing": (("set", "claim_id", "@claim"),),
        "on:remeasure": (("bump", "tries", 1), ("append", "readings", "@value")),
        "on:audit": (
            ("bump_in", "Triage", "tres", 1),
            ("set_in", "Grading", "scores", ["late"]),


            ("set_in", "Closed", "ghost", "many"),
            ("set_in", "Refunding", "ledger", "many"),
            ("set", "index", "many"),
        ),
        "on:sampled": (("carry", "queue", "readings"),),
        "exit:Measuring": (("touch", "index"),),
        "exit:Inspecting": (("carry", "notes", "marks"),),
        "enter:Grading": (("bump", "index", 1),),
        "on:regrade": (("append", "scores", "@grade"),),
        "on:reinspect": (("bump", "tries", 1),),
        "exit:Triage": (("carry", "notes", "queue"),),
        "enter:Refunding": (("append", "ledger", "@amount"),),
        "exit:Assessing": (("touch", "claim_id"),),
    },
}


def _script(text: str) -> list[dict[str, Any]]:
    'Turn "4471:rescan label=A1; 4471:reserved" into one ordered event programme.'

    steps: list[dict[str, Any]] = []
    for item in text.replace("\n", " ").split(";"):
        if not item.strip():
            continue
        who, _, rest = item.strip().partition(":")
        event, *fields = rest.split()
        steps.append(
            {
                "order": who.strip(),
                "event": event,
                "payload": dict(field.split("=", 1) for field in fields),
            }
        )
    return steps


ESCALATION = """
4471:start; 4471:accepted order=4471; 4471:rescan label=A1; 4471:rescan label=A2;
4471:reserved; 4471:retry; 4471:rescan label=A3; 4471:reserved; 4471:shelf sku=S-9;
4471:recheck; 4471:retry; 4471:rescan label=A4; 4471:reserved;
4471:picked carton=C-1; 4471:shipped
"""

EVENING_BATCH = """
5001:start; 5002:start; 5001:accepted order=5001; 5002:accepted order=5002;
5001:rescan label=L1; 5002:rescan label=R1; 5001:rescan label=L2; 5002:reserved;
5001:reserved; 5002:retry; 5001:retry; 5002:rescan label=R2; 5001:rescan label=L3;
5002:reserved; 5001:reserved; 5002:picked carton=C-R; 5001:picked carton=C-L;
5002:shipped; 5001:shipped
"""

OVERNIGHT_HOLD = """
6001:start; 6001:accepted order=6001; 6001:rescan label=H1; 6001:rescan label=H2;
6001:reserved; 6001:retry; 6001:rescan label=H3; 6001:reserved; 6001:shelf sku=S-2;
6001:shelf sku=S-5; 6001:hold; 6001:carry_on order=6001; 6001:retry;
6001:rescan label=H4; 6001:reserved; 6001:shelf sku=S-7; 6001:hold;
6001:replan order=6001; 6001:picked carton=C-6; 6001:shipped
"""

HANDLER_TYPO = """
7001:start; 7001:accepted order=7001; 7001:rescan label=T1; 7001:recount;
7001:rescan label=T2; 7001:reserved; 7001:retry; 7001:rescan label=T3;
7001:reserved; 7001:picked carton=C-7; 7001:shipped
"""

CLAIM_REVIEW_NIGHT = """
R-88:start; R-91:start; R-88:opened claim=R-88; R-91:opened claim=R-91;
R-88:remeasure value=m12; R-91:remeasure value=m31; R-88:remeasure value=m15;
R-88:audit; R-91:remeasure value=m33; R-88:sampled; R-91:sampled;
R-88:regrade grade=B; R-88:reinspect; R-91:reinspect; R-88:remeasure value=m18;
R-91:audit; R-88:park; R-91:remeasure value=m35; R-88:pick_up claim=R-88;
R-88:remeasure value=m21; R-88:park; R-91:park; R-88:next_day claim=R-88;
R-91:back_to_bench claim=R-91; R-88:sampled; R-91:sampled; R-88:escalate amount=a4;
R-91:escalate amount=a7; R-88:settled; R-91:settled
"""


ORDER_FLOW_NIGHT = """
P-42:start; P-42:accepted order=P-42; P-42:rescan label=P1;
P-42:rescan label=P2; P-42:reserved; P-42:retry; P-42:rescan label=P3;
P-42:reserved; P-42:shelf sku=S-4; P-42:recheck; P-42:retry;
P-42:rescan label=P4; P-42:reserved; P-42:picked carton=C-42; P-42:shipped
"""


SCENARIOS: Mapping[str, Mapping[str, Any]] = {
    "stuck-order-escalation": {"chart": "order_flow", "steps": ESCALATION},
    "evening-batch-run": {"chart": "order_flow", "steps": EVENING_BATCH},
    "overnight-hold-drill": {"chart": "order_flow", "steps": OVERNIGHT_HOLD},
    "handler-typo-drill": {"chart": "order_flow", "steps": HANDLER_TYPO},
}

PRIVATE_RUNS: Mapping[str, Mapping[str, Any]] = {
    "order_flow_night": {"chart": "order_flow", "steps": ORDER_FLOW_NIGHT},
    "claim_review_night": {"chart": "claim_review", "steps": CLAIM_REVIEW_NIGHT},
}


PRIVATE_RUN: Mapping[str, Any] = PRIVATE_RUNS["claim_review_night"]

CHARTS: Mapping[str, Mapping[str, Any]] = {
    "order_flow": ORDER_FLOW,
    "claim_review": CLAIM_REVIEW,
}


def chart_spec(name: str) -> Mapping[str, Any]:
    return deepcopy(dict(CHARTS[str(name)]))


def payload_for(name: str) -> dict[str, Any]:
    if name in SCENARIOS:
        case = dict(SCENARIOS[name])
    elif name in PRIVATE_RUNS:
        case = dict(PRIVATE_RUNS[name])
    else:
        raise KeyError(f"unknown event programme: {name}")
    return {"chart": chart_spec(str(case["chart"])), "steps": _script(str(case["steps"]))}


class ReferenceScopes:
    "The scope layer the engine's hooks are supposed to reach."

    def __init__(self, chart: Chart):
        self.chart = chart
        self.bags: dict[str, dict[str, Any]] = {}
        self.put_aside: dict[str, dict[str, dict[str, Any]]] = {}
        self.log: list[ChangeRecord] = []

    def begin_event(self, event: str) -> None:
        self.log = []

    def enter(self, path: Sequence[str], resume: str | None = None) -> None:
        coming_back = self._coming_back(resume)
        for state in path:
            bag = deepcopy(dict(self.chart.declared(state)))
            bag.update(deepcopy(coming_back.get(state, {})))
            self.bags[state] = bag
            for field, value in bag.items():
                self.log.append(ChangeRecord(state, field, None, deepcopy(value)))

    def leave(self, path: Sequence[str]) -> None:
        for point in self.chart.resume_points():
            anchor = self.chart.resume_state(point)
            if anchor in path:
                self.put_aside[point] = {
                    state: deepcopy(bag)
                    for state, bag in self.bags.items()
                    if state == anchor or anchor in self.chart.scope_chain(state)[1:]
                }
        for state in path:
            bag = self.bags.pop(str(state), None)


            for field, value in dict(bag or {}).items():
                self.log.append(ChangeRecord(str(state), field, deepcopy(value), None))

    def read(self, state: str, field: str) -> Any:
        return deepcopy(self.bags[self._owner(state, field)][str(field)])

    def write(self, state: str, field: str, value: Any) -> None:
        owner = self._owner(state, field)
        name = str(field)
        declared = self.chart.field_type(owner, name)
        if declared is not None and (
            isinstance(value, bool) and declared is not bool or not isinstance(value, declared)
        ):
            raise ScopeError("wrong_type", f"{owner}.{name} does not hold that")
        before = self.bags[owner][name]
        if before == value and type(before) is type(value):
            return
        self.bags[owner][name] = deepcopy(value)
        self.log.append(ChangeRecord(owner, name, deepcopy(before), deepcopy(value)))

    def values(self) -> Mapping[str, Mapping[str, Any]]:
        return {state: deepcopy(bag) for state, bag in self.bags.items() if bag}

    def changes(self) -> Sequence[ChangeRecord]:
        return tuple(self.log)

    def _coming_back(self, resume: str | None) -> dict[str, dict[str, Any]]:
        if resume is None:
            return {}
        anchor = self.chart.resume_state(resume)
        reaches = (
            {anchor, *self.chart.children(anchor)}
            if self.chart.resume_kind(resume) == "direct"
            else {anchor, *self.chart.descendants(anchor)}
        )
        return {
            state: deepcopy(bag)
            for state, bag in self.put_aside.get(str(resume), {}).items()
            if state in reaches
        }

    def _owner(self, state: str, field: str) -> str:
        name = str(state)
        if name not in self.bags:
            raise ScopeError("inactive_state", f"{name} is not running")
        owner = self.chart.declaring_state(name, str(field))
        if owner is None or owner not in self.bags:
            raise ScopeError("undeclared_field", f"{name} does not carry {field}")
        return owner


class ReferenceRun:
    'One reference order: the report every event of it should produce.'

    def __init__(self, chart: Chart, name: str):
        self.chart = chart
        self.scopes = ReferenceScopes(chart)
        self.engine = Engine(chart, self.scopes, name=name)

    def expect(
        self,
        event: str,
        payload: Mapping[str, Any],
        *,
        config_before: Sequence[str] | None = None,
        values_before: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        'The report ``event`` should produce, starting from what the run holds.'

        if config_before is not None:
            self.engine.config = tuple(str(state) for state in config_before)
        if values_before is not None:
            self.scopes.bags = {
                state: {
                    field: deepcopy(dict(dict(values_before).get(state, {})).get(field, default))
                    for field, default in dict(self.chart.declared(state)).items()
                }
                for state in self.engine.config
            }
        if event == "start":
            return self.engine.start(payload)
        return self.engine.send(event, payload)


def reference_reports(
    spec: Mapping[str, Any], steps: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every report a correct run of ``steps`` produces, in order.'

    chart = Chart(deepcopy(dict(spec)))
    runs: dict[str, ReferenceRun] = {}
    for step in steps:
        runs.setdefault(str(step["order"]), ReferenceRun(chart, str(step["order"])))
    return [
        runs[str(step["order"])].expect(str(step["event"]), dict(step.get("payload") or {}))
        for step in steps
    ]


__all__ = (
    "CHARTS", "CLAIM_REVIEW", "PRIVATE_RUN", "PRIVATE_RUNS", "SCENARIOS",
    "ReferenceRun", "ReferenceScopes", "chart_spec", "payload_for",
    "reference_reports",
)
