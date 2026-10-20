"""What the lineage audit means by a personal field leaving the company.

`lineage/` is the checker security runs over the record pipeline before a
release goes out. This module is the part the privacy office signed off and the
triage console imports, so it ships as it is: the field table, the masking
helpers, the export calls and the one argument of each that actually leaves,
the rule that reads one expression, the report shape the audit gate diffs, and
the checks the audit already had.

The pipeline is a set of modules and a step is a module-level function. Step
names are unique across the pipeline and `ModuleSet` refuses a set where two
modules define the same one, so a call by name always names one step.

The office states the audit like this. A personal field enters a step where its
source names one: `row["email"]`, `row.email` or `row.get("email")` for any name
in `PERSONAL_FIELDS`. Anything built out of a value that carries one carries it
too, and only a helper in `MASKS` hands back something that does not. What a
step hands back carries a personal field when the step's own body builds it out
of a source, or when the call being read passes one into an argument the step
builds its answer out of; a step is handed whatever its callers pass it,
wherever in the pipeline that call is written. An export leaks when the
argument the sink sends carries one:
`warehouse.write_rows(dataset, rows, marker)` sends `rows`, where `dataset`
names the table and `marker` is the key the warehouse dedupes on, and
`notify.publish(channel, body)` sends `body`.

A body is a module, a step, or a hand-off written inside one, and each is read
on its own terms: names arrive empty unless the step itself was handed a
personal field.

`reference_flows` states all of that for one module read on its own, which is
what the office runs when it re-audits a single step file by hand.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, NamedTuple, Sequence

#: The field names the privacy office treats as personal data.
PERSONAL_FIELDS = frozenset({"email", "ssn", "phone", "birthdate"})

#: Helpers that hand back a value the office does not treat as personal.
MASKS = frozenset({"mask", "redact", "hash_id", "coarse_age"})

#: The check id the audit already reported before lineage was added to it.
BASELINE_CHECK = "PL001"

#: How many expression nodes one pass over a module set may read before the
#: audit gives up on it, so a pass that does not settle fails the gate rather
#: than holding the release train.
STEP_BUDGET = 400_000


class LineageError(RuntimeError):
    """Anything the audit refuses to read."""


class ModuleSetError(LineageError):
    """The pipeline as handed over cannot be read as a module set."""


class ReportError(LineageError):
    """A report the audit gate cannot diff."""


class StepBudgetExceeded(LineageError):
    """A pass read more of the pipeline than the audit allows one pass."""


#: One export call: which argument leaves, and the check it reports under.
class Sink(NamedTuple):
    position: int
    keyword: str
    check: str


#: What one export call sends, and the table or channel it names.
class ExportCall(NamedTuple):
    check: str
    sent: Any
    dataset: str


#: The calls that put data outside the company.
EXPORT_SINKS: Mapping[str, Sink] = {
    "write_rows": Sink(1, "rows", "PL101"),
    "publish": Sink(1, "body", "PL102"),
}


@dataclass(frozen=True, slots=True)
class Finding:
    """One row of the audit report."""

    module: str
    line: int
    col: int
    check: str
    dataset: str = ""


def finding_key(finding: Finding) -> tuple[str, int, int, str]:
    """How the triage console keys a row: the export it sits on, and the check."""
    return (str(finding.module), int(finding.line), int(finding.col), str(finding.check))


def sort_findings(rows: Any) -> tuple[Finding, ...]:
    """The rows in the order the audit gate diffs them."""
    return tuple(sorted(rows, key=finding_key))


def require_report(rows: Any) -> tuple[Finding, ...]:
    """Read a report the way the gate does, or say what is wrong with it."""
    listed = list(rows)
    for row in listed:
        if not isinstance(row, Finding):
            raise ReportError(f"a report row must be a Finding, not {type(row).__name__}")
    if [finding_key(row) for row in listed] != sorted(finding_key(row) for row in listed):
        raise ReportError("the report is out of the order the gate diffs it in")
    return tuple(listed)


class ModuleSet:
    """The pipeline's modules, in the order the checkout handed them over.

    The order is how the set arrived and not what the set is: the checkout step
    walks the working tree and hands the audit whatever order it found, which is
    not the same order on two build workers.
    """

    def __init__(self, modules: Mapping[str, str], order: Sequence[str] | None = None):
        self._sources = {str(name): str(text) for name, text in dict(modules).items()}
        self._order = tuple(self._checked(order) if order is not None else self._sources)
        self._trees = {name: ast.parse(text, name) for name, text in self._sources.items()}
        self._steps: dict[str, tuple[str, Any]] = {}
        for name in sorted(self._sources):
            for node in self._trees[name].body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name in self._steps:
                    raise ModuleSetError(
                        f"two modules define the step {node.name!r}; step names are unique"
                    )
                self._steps[node.name] = (name, node)
        _METER["read"] = 0

    def _checked(self, order: Any) -> list[str]:
        names = [str(name) for name in order]
        if sorted(names) != sorted(self._sources):
            raise ModuleSetError("an order must list every module of the set exactly once")
        return names

    def names(self) -> tuple[str, ...]:
        """The modules in the order the checkout handed them over."""
        return self._order

    def source(self, name: str) -> str:
        return self._sources[str(name)]

    def tree(self, name: str) -> Any:
        return self._trees[str(name)]

    def steps(self) -> Mapping[str, tuple[str, Any]]:
        """Every step: its name, the module it is in, and its definition."""
        return dict(self._steps)

    def iter_modules(self, order: Any = None) -> Iterator[tuple[str, Any]]:
        """Walk the set: as handed over, `"sorted"`, `"reverse"`, or a listing."""
        if order is None:
            names: Sequence[str] = self._order
        elif order == "sorted":
            names = sorted(self._order)
        elif order == "reverse":
            names = list(reversed(self._order))
        else:
            names = self._checked(order)
        for name in names:
            yield name, self._trees[name]


_METER = {"read": 0}


def nodes_read() -> int:
    """How many expression nodes this pass over the module set has read."""
    return int(_METER["read"])


def _constant(node: Any) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def carries(node: Any, tainted: Any, hands_back: Mapping[str, bool] | None = None) -> bool:
    """Whether one expression hands out a personal field.

    `tainted` is the set of local names that already carry one. `hands_back` says,
    for each step this expression calls, whether that call gives back a personal
    field, so a step handed one somewhere else in the pipeline is not thereby
    handing one back here; a step it does not name hands on whatever it was
    given, which is all one module knows about the rest of the pipeline.
    """
    return _carries(node, frozenset(str(name) for name in tainted), dict(hands_back or {}))


def _carries(node: Any, tainted: frozenset[str], hands_back: Mapping[str, bool]) -> bool:
    _METER["read"] += 1
    if _METER["read"] > STEP_BUDGET:
        raise StepBudgetExceeded(
            f"one pass read more than {STEP_BUDGET} expression nodes without settling"
        )
    if node is None or isinstance(node, ast.Constant):
        return False
    if isinstance(node, ast.Name):
        return node.id in tainted
    if isinstance(node, (ast.Subscript, ast.Attribute)):
        named = node.attr if isinstance(node, ast.Attribute) else _constant(node.slice)
        return named in PERSONAL_FIELDS or _carries(node.value, tainted, hands_back)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in MASKS:
            return False
        if isinstance(func, ast.Name) and func.id in hands_back:
            return bool(hands_back[func.id])
        if isinstance(func, ast.Attribute):
            if func.attr == "get" and node.args and _constant(node.args[0]) in PERSONAL_FIELDS:
                return True
            if _carries(func.value, tainted, hands_back):
                return True
        parts: Sequence[Any] = [*node.args, *(item.value for item in node.keywords)]
    else:
        # Anything else is read through: a value built out of one that carries a
        # personal field carries it, whichever way it was put together.
        parts = [item for item in ast.iter_child_nodes(node) if isinstance(item, ast.expr)]
    return any(_carries(item, tainted, hands_back) for item in parts if item is not None)


def body_nodes(statements: Any) -> tuple[Any, ...]:
    """Every node of one body, stopping at a step defined inside it.

    A step defined inside another step is a body of its own and is read
    separately, so nothing here belongs to two bodies at once.
    """

    collected: list[Any] = []
    frontier = list(statements)
    while frontier:
        node = frontier.pop(0)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        collected.append(node)
        frontier.extend(ast.iter_child_nodes(node))
    return tuple(collected)


def assignments(nodes: Any) -> tuple[tuple[str, Any], ...]:
    """Every `name, value` one body binds: `=`, `+=`, `:=`, an annotation, a loop."""
    bound: list[tuple[str, Any]] = []
    for node in nodes:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.For):
            targets, value = [node.target], node.iter
        else:
            continue
        if value is None:
            continue
        for target in targets:
            bound.extend((name, value) for name in _target_names(target))
    return tuple(bound)


def _target_names(target: Any) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for item in target.elts for name in _target_names(item))
    return ()


def export_call(node: Any) -> ExportCall | None:
    """What one call sends out of the company, or None when it sends nothing."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    sink = EXPORT_SINKS.get(node.func.attr)
    if sink is None:
        return None
    sent = next(
        (item.value for item in node.keywords if item.arg == sink.keyword),
        node.args[sink.position] if len(node.args) > sink.position else None,
    )
    if sent is None:
        return None
    return ExportCall(sink.check, sent, (node.args and _constant(node.args[0])) or "")


def finding_at(module: str, call: Any) -> Finding:
    """The one row an export call produces, keyed where that call is."""
    export = export_call(call)
    if export is None:
        raise ReportError(f"{module} line {getattr(call, 'lineno', '?')} is not an export")
    return Finding(
        str(module), int(call.lineno), int(call.col_offset), export.check, export.dataset
    )


def baseline_findings(module: str, source: Any) -> tuple[Finding, ...]:
    """The rows the audit already had, which every team using it has signed off:
    an export whose payload names a personal field in the source itself."""
    tree = ast.parse(source, str(module)) if isinstance(source, str) else source
    return sort_findings(
        Finding(str(module), node.lineno, node.col_offset, BASELINE_CHECK, export.dataset)
        for node, export in ((item, export_call(item)) for item in ast.walk(tree))
        if export is not None
        and isinstance(export.sent, ast.Dict)
        and any(_constant(key) in PERSONAL_FIELDS for key in export.sent.keys)
    )


def reference_flows(source: str, module: str = "<step>") -> tuple[Finding, ...]:
    """Every export one module leaks, reading that module on its own: a call to a
    step hands on whatever it was given, and a step's arguments arrive empty."""
    tree = ast.parse(source, str(module))
    bodies = [list(tree.body)] + [
        list(node.body)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    rows: list[Finding] = []
    for statements in bodies:
        nodes = body_nodes(statements)
        tainted = _carrying_names(nodes, (), None)
        rows.extend(
            finding_at(module, node)
            for node, export in ((item, export_call(item)) for item in nodes)
            if export is not None and carries(export.sent, tainted, None)
        )
    return sort_findings(rows)


def _carrying_names(nodes: Any, given: Any, hands_back: Any) -> frozenset[str]:
    tainted = {str(name) for name in given}
    bound = assignments(nodes)
    changed = True
    while changed:
        changed = False
        for name, value in bound:
            if name not in tainted and carries(value, tainted, hands_back):
                tainted.add(name)
                changed = True
    return frozenset(tainted)
