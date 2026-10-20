"""The rule engine behind /v1/decide: one loaded bundle, one decision at a time."""

from __future__ import annotations

from typing import Any, Mapping
from . import profile as report
from .protocol import (
    CONFLICT, DEFAULT_BUDGET, DENY, INDETERMINATE, BudgetExceeded, Decision,
    Definition, Evaluation, Policy, Ref, RuleConflict,
)


class Engine:
    def __init__(self, policy: Policy, budget: int = DEFAULT_BUDGET):
        self.policy = policy
        self.budget = int(budget)

    def decide(self, request: Mapping[str, Any], profile: bool = False) -> Decision:
        evaluation = Evaluation(self.policy, request, budget=self.budget)
        if profile:
            evaluation.profile = report.new_profile()
        try:
            value = self.rule_value(evaluation, self.policy.entry)
            outcome = DENY if value is None else str(value)
        except RuleConflict:
            outcome = CONFLICT
        except BudgetExceeded:
            outcome = INDETERMINATE
        return Decision(outcome, evaluation.work, evaluation.profile)

    def rule_value(self, evaluation: Evaluation, path: str) -> Any:
        value = evaluation.lookup(path, lambda: self._compute(evaluation, path))
        if evaluation.profile is not None:
            report.record(evaluation.profile, path, value is not None)
        return value

    def _compute(self, evaluation: Evaluation, path: str) -> Any:
        found: list[Any] = []
        for definition in self.policy.definitions_for(path):
            if self._body_holds(evaluation, definition):
                found.append(definition.value)
        if not found:
            return self.policy.default_for(path)
        if any(value != found[0] for value in found[1:]):
            raise RuleConflict(path)
        return found[0]

    def _body_holds(self, evaluation: Evaluation, definition: Definition) -> bool:
        for node in evaluation.body(definition):
            if isinstance(node, Ref):
                if self.rule_value(evaluation, node.target) != node.expect:
                    return False
            elif not evaluation.test(node):
                return False
        return True
