"""Runtime contract for the nightly rating run.

The rating engine reads the pricing rulebook, evaluates one rule per order and
writes what it decides to the billing ledger. This module is the engine: the
ledger and the rating leases, the faults a rule
body can raise, the two signals that are not faults, and `run_night`. Finance
reconciles the month against the rows the ledger ends up holding, so this file
ships unchanged with the rating release and is the same one the invoicing
service imports.

The one thing it does not decide is what happens around a recovery region: a
`rescue` node is handed to `pricing.recovery.run_region`, and the triage label
a fault carries comes from `pricing.triage.label_for`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .grammar import Node, parse, region


class RuleFault(Exception):
    """Base of the faults evaluating a rule body can produce."""
class LookupFault(RuleFault):
    """A line, a field or a lane the order does not have."""
class ConvertFault(RuleFault):
    """A value that cannot be read as the number the rule wants."""
class DeclaredFault(RuleFault):
    """`reject(...)`: the rule itself refused to price this order."""
class AttemptsExhausted(Exception):
    """No attempt is left for this order and a rule body still has to be run.

    `run_night` ends such an order under `exhausted`, which operations counts
    as its own row on the morning board rather than as one of the incidents a
    rule raised."""
class StepBudgetExceeded(Exception):
    """The rule ran past `step_budget` and the engine stopped evaluating it.

    The budget exists because one runaway lane comprehension held a night open
    until morning. It is a fact about the run, not about the order."""
class RunHalted(Exception):
    """The desk pulled the halt switch while this order was being priced."""

#: The faults evaluating a rule body can produce. Anything else that comes out
#: of an evaluation belongs to the run rather than to the order being priced.
EVALUATION_FAULTS: tuple[type[BaseException], ...] = (LookupFault, ConvertFault, DeclaredFault)

#: The triage label operations files an incident under, by the class raised;
#: a fault of a class not listed here is `OTHER_LABEL`.
ERROR_KINDS: Mapping[type[BaseException], str] = {
    LookupFault: "lookup", ConvertFault: "conversion",
    DeclaredFault: "declared", AttemptsExhausted: "exhausted"}
OTHER_LABEL = "other"

#: What one order's pricing ended as.
PRICED, RECOVERED, FAULTED = "priced", "recovered", "faulted"
EXHAUSTED, ABORTED, HALTED = "exhausted", "aborted", "halted"


@dataclass(frozen=True, slots=True)
class Rule:
    """One pricing rule as `rulebook.json` declares it."""
    name: str
    body: str
    on_error: str | None = None
    retry_on_error: bool = False
    guard: str | None = None
    cleanup: str | None = None
    @property
    def node(self) -> Node:
        """The rule compiled to a recovery region around its body."""
        return region(parse(self.body),
                      None if self.on_error is None else parse(self.on_error),
                      retry=self.retry_on_error, guard=self.guard,
                      cleanup=None if self.cleanup is None else parse(self.cleanup))


@dataclass(frozen=True, slots=True)
class Rulebook:
    """The rules the run prices with, and the limits it prices under."""
    rules: Mapping[str, Rule]
    limits: Mapping[str, Any]
    @property
    def max_attempts(self) -> int:
        return int(self.limits.get("max_attempts", 2))
    @property
    def step_budget(self) -> int:
        return int(self.limits.get("step_budget", 400))
    @property
    def max_open_leases(self) -> int:
        return int(self.limits.get("max_open_leases", 1))


def load_rulebook(path: str | Path | None = None) -> Rulebook:
    """Read `pricing/rulebook.json`, or another file in the same shape."""
    target = Path(path) if path else Path(__file__).resolve().with_name("rulebook.json")
    raw = json.loads(Path(target).read_text(encoding="utf-8"))
    rules = {str(entry["name"]): Rule(
        name=str(entry["name"]), body=str(entry["body"]), on_error=entry.get("on_error"),
        retry_on_error=bool(entry.get("retry_on_error", False)),
        guard=entry.get("guard"), cleanup=entry.get("cleanup"))
        for entry in raw.get("rules", ())}
    return Rulebook(rules=rules, limits=dict(raw.get("limits", {})))


@dataclass
class Env:
    """The night's billing ledger, rating leases and vendor connection.

    `effect_log` is the ledger: append-only, one row per committed effect, in
    the order the run committed them; `mark()` reads its current end and
    `discard_after(mark)` drops everything committed since. `open_leases` maps
    a reservation reference to the sequence number it was opened at, and the
    rating vendor charges by the hour for every one still held. `fault_log` is
    the night's incident list: one row per fault a rule raised, written
    where it was raised, carrying the class and the triage label."""
    step_budget: int = 400
    vendor: list[Any] = field(default_factory=list)
    halt: Mapping[str, Any] | None = None
    effect_log: list[dict[str, Any]] = field(default_factory=list)
    fault_log: list[dict[str, Any]] = field(default_factory=list)
    lease_log: list[dict[str, Any]] = field(default_factory=list)
    open_leases: dict[str, int] = field(default_factory=dict)
    lease_peaks: dict[str, int] = field(default_factory=dict)
    steps: int = 0
    leases: int = 0
    quotes: int = 0
    def mark(self) -> int:
        return len(self.effect_log)
    def discard_after(self, mark: int) -> list[dict[str, Any]]:
        """Drop every ledger row committed since `mark` and return the rows."""
        dropped = self.effect_log[int(mark) :]
        del self.effect_log[int(mark) :]
        return dropped
    def lease_mark(self) -> int:
        return self.leases
    def open_lease(self, reference: str, order: str, rule: str) -> None:
        """Reserve rating capacity. The reference is new every time it is asked for."""
        self.leases += 1
        self.open_leases[str(reference)] = self.leases
        at_once = sum(1 for key in self.open_leases if key.startswith(f"{order}:"))
        self.lease_peaks[order] = max(self.lease_peaks.get(order, 0), at_once)
        self.lease_log.append({"action": "open", "reference": str(reference), "order": order,
                               "rule": rule, "held_at_once": at_once})
    def close_lease(self, reference: str) -> bool:
        """Give one reservation back; a reference already back is logged too."""
        held = self.open_leases.pop(str(reference), None) is not None
        self.lease_log.append({"action": "close", "reference": str(reference),
                               "order": str(reference).split(":")[0], "held": held})
        return held
    def close_since(self, mark: int) -> tuple[str, ...]:
        """Give back every reservation opened after `mark`, oldest first."""
        stale = tuple(reference for reference, sequence
                      in sorted(self.open_leases.items(), key=lambda item: item[1])
                      if sequence > int(mark))
        for reference in stale:
            self.close_lease(reference)
        return stale
    def next_quote(self) -> Any:
        answer = self.vendor[min(self.quotes, len(self.vendor) - 1)] if self.vendor else 5.0
        self.quotes += 1
        return answer


@dataclass
class RunContext:
    """One order being priced, and the budget it is priced under."""
    env: Env
    order: Mapping[str, Any]
    rule: Rule
    max_attempts: int = 2
    attempts: int = 0
    used_fallback: bool = False
    frames: list[tuple[str, int]] = field(default_factory=lambda: [("body", 0)])
    @property
    def order_id(self) -> str:
        return str(self.order.get("id", ""))
    def attempts_left(self) -> int:
        """How many more times a rule body may be evaluated for this order."""
        return max(0, int(self.max_attempts) - int(self.attempts))
    def tick(self) -> None:
        """One unit of evaluation work, against the budget and the halt switch."""
        self.env.steps += 1
        halt = self.env.halt or {}
        if str(halt.get("order", "")) == self.order_id and self.env.steps == int(
                halt.get("step", -1)):
            raise RunHalted(f"the desk halted the run during order {self.order_id}")
        if self.env.steps > int(self.env.step_budget):
            raise StepBudgetExceeded(
                f"{self.rule.name} ran past {self.env.step_budget} steps on order {self.order_id}")
    def commit(self, kind: str, **fields: Any) -> None:
        """Append one effect to the ledger, tagged with the branch that made it."""
        branch, attempt = self.frames[-1]
        self.env.effect_log.append({"kind": kind, "order": self.order_id, "rule": self.rule.name,
                                    "branch": branch, "attempt": attempt, **fields})
    def fault(self, fault: RuleFault) -> RuleFault:
        """Write one raised fault to the incident list and hand it back to raise."""
        from . import triage
        self.env.fault_log.append({
            "order": self.order_id, "rule": self.rule.name, "attempt": self.attempts,
            "fault_class": type(fault).__name__, "message": str(fault),
            "label": str(triage.label_for(fault))})
        return fault


def _number(value: Any, what: str, run: RunContext) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise run.fault(ConvertFault(f"cannot read {what} as a number")) from None


def call_builtin(name: str, arguments: Sequence[Any], run: RunContext) -> Any:
    """The functions a rule body may call; the rulebook uses every one of them."""
    order, env = run.order, run.env
    if name == "base":
        return _number(order.get("base"), f"the base amount on order {run.order_id}", run)
    if name == "line":
        lines, index = list(order.get("lines", ())), int(arguments[0])
        if not lines:
            raise run.fault(LookupFault(f"order {run.order_id} was filed with no lines at all"))
        if index < 1 or index > len(lines):
            raise run.fault(LookupFault(
                f"line {index} is out of range for an order with {len(lines)} lines"))
        return float(lines[index - 1])
    if name == "field":
        key, fields = str(arguments[0]), dict(order.get("fields", {}))
        if key not in fields:
            raise run.fault(LookupFault(f"there is no value for {key!r} on order {run.order_id}"))
        return fields[key]
    if name == "number":
        return _number(arguments[0], repr(arguments[0]), run)
    if name == "charge":
        amount = round(float(arguments[0]), 4)
        run.commit("charge", amount=amount)
        return amount
    if name == "audit":
        run.commit("audit", note=str(arguments[0]))
        return 0.0
    if name == "hold":
        reference = f"{run.order_id}:{arguments[0]}-{env.leases + 1}"
        env.open_lease(reference, run.order_id, run.rule.name)
        return 4.0
    if name == "quote":
        answer = env.next_quote()
        if isinstance(answer, Mapping):
            raise run.fault(ConvertFault(str(answer.get("message", "the vendor sent no number"))))
        return float(answer)
    if name == "reject":
        raise run.fault(DeclaredFault(str(arguments[0])))
    if name == "scan":
        total = 0.0
        for _ in range(int(arguments[0])):
            run.tick()
            total += 0.01
        return total
    raise run.fault(LookupFault(f"the rulebook calls {name}(), which this release does not have"))


def eval_node(node: Node, env: Env, run: RunContext) -> Any:
    """Evaluate one node; operands are evaluated left to right.

    A `region` node is handed to `pricing.recovery.run_region`, which owns
    everything that happens around a recovery region."""
    kind = node.kind
    if kind == "body":
        # Entering a body is what an attempt is, whatever the evaluation then
        # does with it, so the count always agrees with the vendor's invoice.
        run.attempts += 1
    run.tick()
    if kind in ("number", "text"):
        return node.value
    if kind == "binary":
        left = _number(eval_node(node.children[0], env, run), "the left operand", run)
        right = _number(eval_node(node.children[1], env, run), "the right operand", run)
        return left + right if node.value == "+" else left * right
    if kind == "call":
        return call_builtin(str(node.value),
                            [eval_node(child, env, run) for child in node.children], run)
    if kind in ("body", "fallback", "cleanup"):
        if kind == "fallback":
            run.used_fallback = True
        run.frames.append((kind, run.attempts))
        try:
            return eval_node(node.children[0], env, run)
        finally:
            run.frames.pop()
    if kind == "region":
        from . import recovery
        return recovery.run_region(node, env, run)
    raise ValueError(f"the rating engine has no node kind {kind!r}")


def run_night(program: Mapping[str, Any], rulebook: Rulebook | None = None) -> dict[str, Any]:
    """Price every order in one night's program and return the night's telemetry.

    `program` carries `orders` (each with `id`, `rule`, and whatever the rules
    read from it), `vendor` (what `quote()` answers, in order; the last entry
    repeats), and optionally `halt` (`{"order": ..., "step": ...}`), which is
    the desk pulling the halt switch while that order is being priced."""
    book = rulebook or load_rulebook()
    env = Env(step_budget=book.step_budget, vendor=list(program.get("vendor", ())),
              halt=program.get("halt"))
    rows: list[dict[str, Any]] = []
    for order in program.get("orders", ()):
        from . import triage
        rule = book.rules[str(order["rule"])]
        run = RunContext(env=env, order=dict(order), rule=rule, max_attempts=book.max_attempts)
        env.steps = 0
        row: dict[str, Any] = {"order": str(order.get("id", "")), "rule": rule.name,
                               "value": None, "outcome": PRICED, "fault": None, "label": "none"}
        try:
            row["value"] = round(float(eval_node(rule.node, env, run)), 4)
            row["outcome"] = RECOVERED if run.used_fallback else PRICED
        except AttemptsExhausted as signal:
            row.update(outcome=EXHAUSTED, fault=str(signal), label="exhausted")
        except StepBudgetExceeded as signal:
            row.update(outcome=ABORTED, fault=str(signal))
        except RunHalted as signal:
            row.update(outcome=HALTED, fault=str(signal))
        except Exception as fault:  # noqa: BLE001 - the night's summary reports it
            row.update(outcome=FAULTED, fault=str(fault), label=str(triage.label_for(fault)))
        row.update(attempts=run.attempts, steps=env.steps, used_fallback=run.used_fallback)
        rows.append(row)
        if row["outcome"] == HALTED:
            break
    labels: dict[str, int] = {}
    for entry in env.fault_log:
        labels[str(entry["label"])] = labels.get(str(entry["label"]), 0) + 1
    for row in rows:
        # An order that ran out of attempts is a row on the board in its own
        # right; no rule raised it, so it is not in the incident list.
        if row["outcome"] == EXHAUSTED:
            labels[str(row["label"])] = labels.get(str(row["label"]), 0) + 1
    return {"orders": rows, "effects": list(env.effect_log), "faults": list(env.fault_log),
            "leases": list(env.lease_log), "open_leases": sorted(env.open_leases),
            "leases_held_at_once": dict(sorted(env.lease_peaks.items())),
            "labels": dict(sorted(labels.items()))}
