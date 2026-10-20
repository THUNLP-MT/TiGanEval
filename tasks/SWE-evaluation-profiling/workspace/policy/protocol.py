"""The evaluation contract of the decision service.

The rule language, the cost model, the per-decision evaluation object and the
result shape below are the fixed part of the project: the API gateway, the
operator console and the bundle owners' tooling are all built against them and
ship in the gateway's release. Everything here is deterministic; cost is
counted in work units and never in wall-clock time.

An evaluation of one request works like this. A rule is a set of definitions
that share a path; asking for a rule's value enters every one of its
definitions in source order, and a definition's body holds when all of its
conjuncts hold, evaluated left to right and abandoned at the first one that
fails. A rule's value is cached for the life of the one decision that computed
it, so a rule referenced many times inside a decision runs once. Two
definitions of one rule that hold with different values are a conflict.

`Evaluation` is the only thing that charges work and the only thing that
records what a decision evaluated: `body()` records that a definition's body
was entered and, when the engine finishes iterating its conjuncts, that the
body held; `test()` records one conjunct; `lookup()` records that a rule's
value was asked for and owns the per-decision cache. `trace_ops()` collects
those records for anything running inside it.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping, Sequence

#: Work units one decision may spend before the gateway gives up on it.
DEFAULT_BUDGET = 200

#: What the gateway reports for a rule conflict, for an entry rule with no
#: value, and for a decision that ran out of work units.
CONFLICT = "conflict"
DENY = "deny"
INDETERMINATE = "indeterminate"


class PolicyError(RuntimeError):
    pass


class RuleConflict(PolicyError):
    """Two definitions of one rule held with different values."""


class BudgetExceeded(PolicyError):
    """The decision spent more work units than the gateway allows it."""


@dataclass(frozen=True, slots=True)
class Test:
    """One conjunct over the request input.

    ``op`` is ``eq``, ``ne`` or ``gt`` for a scalar at ``path``; ``has`` for
    membership in the collection at ``path``, which costs one work unit per
    element examined; and ``size_gt`` for that collection's length.
    """

    node_id: str
    path: str
    op: str
    operand: Any


@dataclass(frozen=True, slots=True)
class Ref:
    """One conjunct that holds when another rule's value is ``expect``."""

    node_id: str
    target: str
    expect: Any


@dataclass(frozen=True, slots=True)
class Definition:
    """One body of one rule, at ``index`` in the source order of that rule."""

    package: str
    rule: str
    index: int
    value: Any
    body: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class Policy:
    """One loaded bundle."""

    entry: str
    definitions: tuple[Definition, ...]
    defaults: Mapping[str, Any] = field(default_factory=dict)

    def paths(self) -> tuple[str, ...]:
        return tuple({rule_path(item): None for item in self.definitions})

    def definitions_for(self, path: str) -> tuple[Definition, ...]:
        return tuple(item for item in self.definitions if rule_path(item) == str(path))

    def default_for(self, path: str) -> Any:
        return self.defaults.get(str(path))


@dataclass(frozen=True, slots=True)
class Decision:
    """What the gateway hands back for one request.

    ``profile`` is whatever the rule report for this decision is, and is
    ``None`` on a decision that was not asked for one.
    """

    outcome: str
    work: int
    profile: Any = None


@dataclass(slots=True)
class RuleStat:
    """One row of a rule report, as the console and the nightly job read it.

    ``reuse`` is a property of a rule rather than of one body: where a
    reference is answered from a value the decision already has, the console
    shows that reuse against every definition of the rule it names.
    """

    evals: int = 0
    successes: int = 0
    reuse: int = 0


def rule_path(definition: Definition) -> str:
    """The fully qualified path of the rule this definition belongs to."""

    return f"data.{definition.package}.{definition.rule}"


def definition_id(definition: Definition) -> str:
    """The identity of one definition: its rule path and its source index."""

    return f"{rule_path(definition)}#{definition.index}"


def package_of(identifier: str) -> str:
    """The package an identifier belongs to: ``data.authz.allow#1`` -> ``data.authz``."""

    return str(identifier).split("#", 1)[0].rsplit(".", 1)[0]


def success_rate(evals: int, successes: int) -> float:
    """The rate the console prints for a report row; a row that never ran reads 0."""

    return 0.0 if int(evals) <= 0 else float(successes) / float(evals)


def read_path(request: Mapping[str, Any], path: str) -> Any:
    value: Any = request
    for part in str(path).split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def node_cost(node: Any, request: Mapping[str, Any]) -> int:
    """The work units one conjunct costs against this request."""

    if isinstance(node, Ref):
        return 0
    value = read_path(request, node.path)
    if node.op == "has" and isinstance(value, Sequence) and not isinstance(value, str):
        return max(1, len(value))
    return 1


def holds(node: Test, request: Mapping[str, Any]) -> bool:
    """Whether one input conjunct holds. Reference conjuncts are the engine's."""

    value = read_path(request, node.path)
    if node.op == "eq":
        return value == node.operand
    if node.op == "ne":
        return value != node.operand
    if node.op == "gt":
        return isinstance(value, (int, float)) and value > node.operand
    if node.op == "has":
        return isinstance(value, Sequence) and node.operand in value
    if node.op == "size_gt":
        return isinstance(value, Sequence) and len(value) > node.operand
    raise PolicyError(f"unknown conjunct: {node.op}")


def load_policy(document: Mapping[str, Any]) -> Policy:
    """Build a policy from one bundle document."""

    definitions: list[Definition] = []
    defaults: dict[str, Any] = {}
    counters: dict[str, int] = {}
    for raw in document.get("rules", ()):
        package, rule = str(raw["package"]), str(raw["rule"])
        path = f"data.{package}.{rule}"
        if "default" in raw:
            defaults[path] = raw["default"]
            continue
        index = counters.get(path, 0)
        counters[path] = index + 1
        prefix = f"{path}#{index}"
        body = tuple(
            _conjunct(f"{prefix}.{position}", item)
            for position, item in enumerate(raw.get("body", ()))
        )
        definitions.append(
            Definition(package, rule, index, raw.get("value", True), body)
        )
    return Policy(str(document["entry"]), tuple(definitions), defaults)


def _conjunct(node_id: str, item: Sequence[Any]) -> Any:
    if str(item[0]) == "ref":
        return Ref(node_id=node_id, target=str(item[1]), expect=item[2])
    return Test(node_id=node_id, path=str(item[1]), op=str(item[2]), operand=item[3])


_TRACES: list[list[str]] = []


@contextmanager
def trace_ops() -> Iterator[list[str]]:
    """Collect what every evaluation inside this block records, in order."""

    log: list[str] = []
    _TRACES.append(log)
    try:
        yield log
    finally:
        _TRACES.remove(log)


class Evaluation:
    """One request's evaluation: the work meter, the record, and the cache.

    ``profile`` is a free slot for whatever the engine wants to carry through
    one decision; nothing in this module reads it.
    """

    def __init__(
        self,
        policy: Policy,
        request: Mapping[str, Any],
        *,
        budget: int = DEFAULT_BUDGET,
    ):
        self.policy = policy
        self.request = dict(request)
        self.budget = int(budget)
        self.work = 0
        self.ops: list[str] = []
        self.profile: Any = None
        self._values: dict[str, Any] = {}

    def _record(self, op: str, cost: int) -> None:
        self.ops.append(op)
        for log in _TRACES:
            log.append(op)
        self.work += int(cost)
        if self.work > self.budget:
            raise BudgetExceeded(f"decision spent more than {self.budget} work units")

    def body(self, definition: Definition) -> Iterator[Any]:
        """Enter one definition's body and yield its conjuncts in order.

        Entering is recorded straight away. Finishing the conjuncts records
        that the body held, so a body abandoned on a conjunct that fails is on
        record as entered and not as held.
        """

        identifier = definition_id(definition)
        self._record(f"body:{identifier}", 1)
        for node in definition.body:
            yield node
        self._record(f"held:{identifier}", 0)

    def test(self, node: Test) -> bool:
        """Evaluate one input conjunct, charging what it costs."""

        self._record(node.node_id, node_cost(node, self.request))
        return holds(node, self.request)

    def lookup(self, path: str, compute: Callable[[], Any]) -> Any:
        """Ask for a rule's value, from this decision's cache when it is there."""

        self._record(f"ask:{path}", 1)
        if path in self._values:
            return self._values[path]
        value = compute()
        self._values[path] = value
        return value


def reference_decide(policy: Policy, request: Mapping[str, Any]) -> str:
    """The outcome the policy defines for one request, ignoring cost and cache.

    This is the semantics the engine implements the fast way. It spends no
    work units and keeps no cache, so it says nothing about what a decision
    costs or how often a rule ran.
    """

    def value_of(path: str, seen: frozenset[str]) -> Any:
        if path in seen:
            raise PolicyError(f"rules refer to each other in a cycle at {path}")
        found: list[Any] = []
        for definition in policy.definitions_for(path):
            if _body_holds(definition, request, seen | {path}, value_of):
                found.append(definition.value)
        if not found:
            return policy.default_for(path)
        if any(value != found[0] for value in found[1:]):
            raise RuleConflict(path)
        return found[0]

    try:
        value = value_of(policy.entry, frozenset())
    except RuleConflict:
        return CONFLICT
    return DENY if value is None else str(value)


def _body_holds(
    definition: Definition,
    request: Mapping[str, Any],
    seen: frozenset[str],
    value_of: Callable[[str, frozenset[str]], Any],
) -> bool:
    for node in definition.body:
        if isinstance(node, Ref):
            if value_of(node.target, seen) != node.expect:
                return False
        elif not holds(node, request):
            return False
    return True


__all__ = (
    "BudgetExceeded", "CONFLICT", "DEFAULT_BUDGET", "DENY", "Decision",
    "Definition", "Evaluation", "INDETERMINATE", "Policy", "PolicyError",
    "Ref", "RuleConflict", "RuleStat", "Test", "definition_id", "holds",
    "load_policy", "node_cost", "package_of", "read_path", "reference_decide",
    "rule_path", "success_rate", "trace_ops",
)
