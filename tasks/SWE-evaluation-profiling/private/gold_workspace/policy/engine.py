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
        # The report has to tell a body that ran from a value the decision
        # already had, so the reuse is counted exactly where the cache answered.
        computed = False

        def compute() -> Any:
            nonlocal computed
            computed = True
            return self._compute(evaluation, path)

        value = evaluation.lookup(path, compute)
        if evaluation.profile is not None and not computed:
            for definition in self.policy.definitions_for(path):
                report.count_reuse(evaluation.profile, definition)
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
        if evaluation.profile is not None:
            report.count_eval(evaluation.profile, definition)
        for node in evaluation.body(definition):
            if isinstance(node, Ref):
                if self.rule_value(evaluation, node.target) != node.expect:
                    return False
            elif not evaluation.test(node):
                return False
        if evaluation.profile is not None:
            report.count_success(evaluation.profile, definition)
        return True
