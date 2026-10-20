'Deterministic, sandboxed reading of one rating workspace.'

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    CLEANUP_ORDER,
    CLOSING_ORDERS,
    GUARDED_ORDERS,
    HALT_ORDER,
    HALTED_CLOSING_ORDER,
    NESTED_ORDER,
    PAIRED_ORDERS,
    RETRY_FALLBACK_ORDER,
    RETRY_PRICED_ORDERS,
    RUNAWAY_ORDER,
    UNNAMED_LABEL_ORDER,
    UNPRICED_CLOSING_ORDER,
    build_night,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("pricing/recovery.py", "pricing/triage.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-rating-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "night-0714-invoices": "invoices",
    "pallet-board-0722": "board",
    "vendor-hold-0726": "vendor",
    "tier-runaway-0803": "tier",
}

BUCKETS: Mapping[str, str] = {
    "single_branch_effects": "effect_failures",
    "signal_transparency": "signal_failures",
    "lease_conservation": "lease_failures",
    "attempt_budget": "attempt_failures",
    "label_invariance": "label_failures",
}

PRICED, RECOVERED = "priced", "recovered"
ABORTED, EXHAUSTED = "aborted", "exhausted"
_SETTLED = (PRICED, RECOVERED)


CLASS_LABELS: Mapping[str, str] = {
    "LookupFault": "lookup", "ConvertFault": "conversion",
    "DeclaredFault": "declared", "AttemptsExhausted": "exhausted"}
OTHER_LABEL = "other"
_CACHE = AnalysisCache()
_REFERENCE_CACHE = AnalysisCache()
_REFERENCE_WORKSPACE = TASK_ROOT / "private" / "gold_workspace"


class Night:
    'Everything the five checks read from one priced night.'

    def __init__(self, result: Mapping[str, Any], night: Mapping[str, Any]):
        self.result = result
        self.limits = dict(result.get("limits", {}))
        self.rows = {str(row["order"]): dict(row) for row in result.get("orders", ())}
        self.sequence = [str(row["order"]) for row in result.get("orders", ())]
        self.effects: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in result.get("effects", ()):
            self.effects[str(entry.get("order"))].append(dict(entry))
        self.faults: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in result.get("faults", ()):
            self.faults[str(entry.get("order"))].append(dict(entry))
        self.rules = {str(item["id"]): str(item["rule"]) for item in night.get("orders", ())}
        self.guards = {str(name): value for name, value in dict(result.get("guards", {})).items()}

    def limit(self, name: str, default: int) -> int:
        return int(self.limits.get(name, default))

    def guard(self, order: str) -> str:
        "The label this order's rule writes its `on_error` branch for."
        return str(self.guards.get(self.rule(order)) or "")

    def board_label(self, order: str) -> str:
        'The label this build put the order on the morning board under.'
        row_label = str(self.row(order).get("label", "none"))
        if row_label and row_label != "none":
            return row_label
        rows = self.faults.get(order, ())
        return str(rows[-1].get("label", "none")) if rows else "none"

    def raised_label(self, order: str) -> str:
        'The label the class the engine raised belongs to, or "" if none was.'
        rows = self.faults.get(order, ())
        if not rows:
            return ""
        return CLASS_LABELS.get(str(rows[-1].get("fault_class")), OTHER_LABEL)

    def row(self, order: str) -> dict[str, Any]:
        return dict(self.rows.get(order, {}))

    def outcome(self, order: str) -> str:
        return str(self.row(order).get("outcome", "not priced"))

    def rule(self, order: str) -> str:
        return str(self.rows.get(order, {}).get("rule") or self.rules.get(order, ""))

    def priced(self, order: str) -> list[dict[str, Any]]:
        'The ledger rows that survived for this order, from either branch.'
        return [entry for entry in self.effects.get(order, ())
                if str(entry.get("branch")) in ("body", "fallback")]

    def committed(self, order: str) -> list[dict[str, Any]]:
        "Every ledger row that survived for this order, the close's included."
        return [dict(entry) for entry in self.effects.get(order, ())]

    def charges(self, order: str) -> list[dict[str, Any]]:
        return [entry for entry in self.priced(order) if str(entry.get("kind")) == "charge"]

    def opened_leases(self, order: str) -> list[dict[str, Any]]:
        'The rating reservations this order opened, in the order it took them.'
        return [dict(entry) for entry in self.result.get("leases", ())
                if str(entry.get("action")) == "open" and str(entry.get("order")) == order]

    def settlement_leases(self, order: str, action: str) -> list[dict[str, Any]]:
        'Settlement-slot lease entries written for one closing branch.'

        return [dict(entry) for entry in self.result.get("leases", ())
                if str(entry.get("action")) == action
                and str(entry.get("order")) == order
                and f"{order}:settle-" in str(entry.get("reference"))]

    def orders_after(self, order: str) -> int:
        return len(self.sequence) - self.sequence.index(order) - 1 if order in self.sequence else 0


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _effect_signature(entries: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    'Business fields of ledger rows, excluding run-local bookkeeping.'

    return [(str(entry.get("branch")), str(entry.get("kind")),
             round(float(entry["amount"]), 4) if "amount" in entry else None,
             str(entry["note"]) if "note" in entry else None)
            for entry in entries]


def _effect_failures(night: Night, reference: Night) -> list[dict[str, Any]]:
    "The ledger holds one branch's work for an order, or none at all."

    failures: list[dict[str, Any]] = []
    for order in night.sequence:
        surviving = night.priced(order)
        charges = night.charges(order)
        amount = round(sum(float(entry.get("amount", 0.0)) for entry in charges), 4)
        pairs = sorted({(str(entry["branch"]), int(entry["attempt"])) for entry in surviving})
        outcome, rule = night.outcome(order), night.rule(order)
        if len(pairs) > 1:
            failures.append(_fail("duplicate_charges_for_one_order", order=order, rule=rule,
                                  charges=len(charges), attempts_kept=len(pairs), amount=amount,
                                  outcome=outcome))


        elif outcome in _SETTLED and not surviving:
            failures.append(_fail("priced_order_left_no_ledger_rows", order=order, rule=rule,
                                  value=float(night.row(order).get("value") or 0.0),
                                  outcome=outcome))
        elif outcome not in _SETTLED and night.committed(order):


            kept = [entry for entry in night.committed(order)
                    if str(entry.get("kind")) == "charge"]
            failures.append(_fail(
                "effects_kept_for_an_unpriced_order", order=order, rule=rule,
                charges=len(kept),
                amount=round(sum(float(entry.get("amount", 0.0)) for entry in kept), 4),
                outcome=outcome))
        elif outcome in _SETTLED and outcome == reference.outcome(order):
            expected_value = float(reference.row(order).get("value") or 0.0)
            value = float(night.row(order).get("value") or 0.0)
            if value != expected_value:
                failures.append(_fail(
                    "order_priced_at_wrong_value", order=order, rule=rule,
                    outcome=outcome, value=value, expected_value=expected_value))
            elif _effect_signature(surviving) != _effect_signature(reference.priced(order)):
                observed_branches = sorted({str(entry.get("branch")) for entry in surviving})
                expected_branches = sorted(
                    {str(entry.get("branch")) for entry in reference.priced(order)})
                failures.append(_fail(
                    "ledger_rows_do_not_match_winning_branch", order=order, rule=rule,
                    outcome=outcome,
                    observed_branch=",".join(observed_branches) or "none",
                    expected_branch=",".join(expected_branches) or "none",
                    observed_rows=len(surviving),
                    expected_rows=len(reference.priced(order))))
    return failures


def _signal_failures(night: Night) -> list[dict[str, Any]]:
    "The step budget and the desk's halt come out of a region, not into a price."

    failures: list[dict[str, Any]] = []
    runaway = night.row(RUNAWAY_ORDER)
    outcome = str(runaway.get("outcome"))
    if outcome != ABORTED:


        kind = ("budget_abort_absorbed" if outcome in _SETTLED
                else "budget_abort_filed_as_a_rule_fault")
        failures.append(_fail(
            kind, order=RUNAWAY_ORDER, rule=night.rule(RUNAWAY_ORDER),
            outcome=night.outcome(RUNAWAY_ORDER), steps=int(runaway.get("steps", 0)),
            step_budget=night.limit("step_budget", 400),
            label=night.board_label(RUNAWAY_ORDER),
            value=float(runaway.get("value") or 0.0)))
    if night.outcome(HALT_ORDER) != "halted" or night.orders_after(HALT_ORDER):
        failures.append(_fail(
            "halt_ignored", order=HALT_ORDER, rule=night.rule(HALT_ORDER),
            outcome=night.outcome(HALT_ORDER), orders_after=night.orders_after(HALT_ORDER)))
    return failures


def _close_count_failures(night: Night, orders: tuple[str, ...]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for order in orders:
        opens = night.settlement_leases(order, "open")
        closes = [entry for entry in night.settlement_leases(order, "close")
                  if bool(entry.get("held"))]
        if order == UNPRICED_CLOSING_ORDER and not opens:
            continue
        if len(opens) != 1 or len(closes) != 1:
            failures.append(_fail(
                "close_count_wrong_for_order", order=order, rule=night.rule(order),
                outcome=night.outcome(order), opens=len(opens), closes=len(closes)))
    return failures


def _lease_failures(night: Night, closing_halt: Night) -> list[dict[str, Any]]:
    'Every reservation is given back, and only one is held per order at a time.'

    failures: list[dict[str, Any]] = []
    still_open = [str(item) for item in night.result.get("open_leases", ())]
    if still_open:
        order = still_open[0].split(":")[0]
        failures.append(_fail("leases_open_at_the_end", order=order, rule=night.rule(order),
                              reference=still_open[0], open_leases=len(still_open)))
    limit = night.limit("max_open_leases", 1)
    for order, peak in sorted(dict(night.result.get("leases_held_at_once", {})).items()):
        if int(peak) > limit:
            failures.append(_fail("two_reservations_held_at_once", order=str(order),
                                  rule=night.rule(str(order)), held_at_once=int(peak),
                                  max_open_leases=limit))
    cleanup = night.row(CLEANUP_ORDER)
    if str(cleanup.get("outcome")) in _SETTLED:
        failures.append(_fail(
            "cleanup_failure_swallowed", order=CLEANUP_ORDER, rule=night.rule(CLEANUP_ORDER),
            outcome=night.outcome(CLEANUP_ORDER),
            value=float(cleanup.get("value") or 0.0), charges=len(night.charges(CLEANUP_ORDER))))


    unpriced = night.row(UNPRICED_CLOSING_ORDER)
    if (str(unpriced.get("outcome")) not in _SETTLED
            and not night.opened_leases(UNPRICED_CLOSING_ORDER)):
        failures.append(_fail(
            "close_never_ran_for_that_order", order=UNPRICED_CLOSING_ORDER,
            rule=night.rule(UNPRICED_CLOSING_ORDER),
            outcome=night.outcome(UNPRICED_CLOSING_ORDER),
            label=night.board_label(UNPRICED_CLOSING_ORDER)))
    failures.extend(_close_count_failures(night, CLOSING_ORDERS))
    failures.extend(_close_count_failures(closing_halt, (HALTED_CLOSING_ORDER,)))
    return failures


def _attempt_failures(night: Night) -> list[dict[str, Any]]:
    'An order is evaluated at most `max_attempts` times, wherever it is asked.'

    failures: list[dict[str, Any]] = []
    limit = night.limit("max_attempts", 2)
    for order in night.sequence:
        attempts = int(night.row(order).get("attempts", 0))
        if attempts > limit:
            failures.append(_fail("attempts_over_budget", order=order, rule=night.rule(order),
                                  attempts=attempts, max_attempts=limit,
                                  outcome=night.outcome(order)))


    retried = night.row(RETRY_FALLBACK_ORDER)
    if str(retried.get("outcome")) != RECOVERED:
        failures.append(_fail(
            "retries_spent_without_falling_back", order=RETRY_FALLBACK_ORDER,
            rule=night.rule(RETRY_FALLBACK_ORDER), outcome=night.outcome(RETRY_FALLBACK_ORDER),
            label=night.board_label(RETRY_FALLBACK_ORDER),
            attempts=int(retried.get("attempts", 0)), max_attempts=limit))


    for order in RETRY_PRICED_ORDERS:
        row = night.row(order)
        outcome = str(row.get("outcome"))
        if outcome == PRICED:
            continue
        kind = ("retried_order_priced_by_its_branch" if outcome in _SETTLED
                else "retried_order_left_unpriced")
        failures.append(_fail(
            kind, order=order, rule=night.rule(order), outcome=night.outcome(order),
            label=night.board_label(order), attempts=int(row.get("attempts", 0)),
            value=float(row.get("value") or 0.0), max_attempts=limit))


    nested = night.row(NESTED_ORDER)
    outcome = str(nested.get("outcome"))
    if outcome != EXHAUSTED:
        kind = ("exhaustion_answered_with_a_price" if outcome in _SETTLED
                else "exhaustion_reported_as_inner_fault")
        failures.append(_fail(
            kind, order=NESTED_ORDER,
            rule=night.rule(NESTED_ORDER), outcome=night.outcome(NESTED_ORDER),
            label=night.board_label(NESTED_ORDER), attempts=int(nested.get("attempts", 0)),
            value=float(nested.get("value") or 0.0), max_attempts=limit))
    return failures


def _label_failures(night: Night) -> list[dict[str, Any]]:
    'One fault of one kind is one incident, whatever its message reads.'

    failures: list[dict[str, Any]] = []


    by_class: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rows in night.faults.values():
        for entry in rows:
            by_class[(str(entry.get("rule")), str(entry.get("fault_class")))].append(entry)
    for (rule, fault_class), rows in sorted(by_class.items()):
        first = rows[0]
        odd = next((row for row in rows if str(row["label"]) != str(first["label"])), None)
        if odd is not None:
            failures.append(_fail(
                "label_follows_message_text", order=str(first["order"]),
                sibling=str(odd["order"]), rule=rule, fault_class=fault_class,
                label=str(first["label"]), sibling_label=str(odd["label"])))
    for rows in night.faults.values():
        for entry in rows:
            fault_class = str(entry.get("fault_class"))
            expected = CLASS_LABELS.get(fault_class, OTHER_LABEL)
            label = str(entry.get("label"))
            if label != expected:
                failures.append(_fail(
                    "fault_filed_under_wrong_label", order=str(entry.get("order")),
                    rule=str(entry.get("rule")), fault_class=fault_class,
                    label=label, expected_label=expected))


    left, right = PAIRED_ORDERS
    taken = [order for order in PAIRED_ORDERS if night.outcome(order) == RECOVERED]
    if len(taken) == 1:
        odd = right if taken[0] == left else left
        failures.append(_fail(
            "clause_missed_sibling_fault", order=odd, sibling=taken[0], rule=night.rule(odd),
            outcome=night.outcome(odd), sibling_outcome=night.outcome(taken[0]),
            guard=night.guard(odd), label=night.board_label(odd)))
    for order in GUARDED_ORDERS:
        if night.outcome(order) != RECOVERED:
            failures.append(_fail(
                "guard_did_not_take_its_own_label", order=order, rule=night.rule(order),
                outcome=night.outcome(order), guard=night.guard(order),
                label=night.raised_label(order)))


    unnamed, raised = night.row(UNNAMED_LABEL_ORDER), night.raised_label(UNNAMED_LABEL_ORDER)
    if str(unnamed.get("outcome")) in _SETTLED and raised not in ("", night.guard(
            UNNAMED_LABEL_ORDER)):
        failures.append(_fail(
            "guard_took_an_unnamed_label", order=UNNAMED_LABEL_ORDER,
            rule=night.rule(UNNAMED_LABEL_ORDER), outcome=night.outcome(UNNAMED_LABEL_ORDER),
            guard=night.guard(UNNAMED_LABEL_ORDER), label=raised))
    return failures


def _analyse(result: Mapping[str, Any], night: Mapping[str, Any],
             reference_result: Mapping[str, Any], closing_result: Mapping[str, Any],
             closing_night: Mapping[str, Any]) -> dict[str, Any]:
    reading = Night(result, night)
    reference = Night(reference_result, night)
    closing_halt = Night(closing_result, closing_night)
    return {
        "effect_failures": _effect_failures(reading, reference),
        "signal_failures": _signal_failures(reading),
        "lease_failures": _lease_failures(reading, closing_halt),
        "attempt_failures": _attempt_failures(reading),
        "label_failures": _label_failures(reading),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(result: Mapping[str, Any]) -> str:
    'The one line the console shows when a night did not finish.'

    reported = str(result.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(result.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the run ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the run ended without saying why"
    return f"the rating run stopped part way through the night: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Price the private scenarios against this workspace and bucket failures.'

    def compute() -> Mapping[str, Any]:
        night = build_night(str(PRIVATE_CASE["profile"]))
        result = PROJECT.invoke(artifact_dir, dict(night))
        if not result.get("ok"):
            analysis = dict(failed_analysis(_console_error(result), tuple(BUCKETS.values())))
            diagnostic = result.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            closing_night = build_night("closing-halt")
            closing_result = PROJECT.invoke(artifact_dir, dict(closing_night))
            if not closing_result.get("ok"):
                analysis = dict(failed_analysis(
                    _console_error(closing_result), tuple(BUCKETS.values())))
                diagnostic = closing_result.get("diagnostic")
                if diagnostic:
                    analysis["diagnostic"] = str(diagnostic)
                analysis["case"] = {
                    "night": "release + closing-halt",
                    "orders": len(night["orders"]) + len(closing_night["orders"]),
                }
                return analysis
            reference = _REFERENCE_CACHE.get_or_compute(
                _REFERENCE_WORKSPACE,
                lambda: PROJECT.invoke(_REFERENCE_WORKSPACE, dict(night)),
            )
            if not reference.get("ok"):
                raise RuntimeError(
                    "the frozen reference workspace could not price the private night"
                )
            analysis = _analyse(result, night, reference, closing_result, closing_night)
        analysis["case"] = {
            "night": "release + closing-halt",
            "orders": len(night["orders"]) + 1,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        night = build_night(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "orders": [str(item["id"]) for item in night.get("orders", ())],
            "rules": sorted({str(item["rule"]) for item in night.get("orders", ())}),
        })
    limits: Mapping[str, Any] = {}
    try:
        limits = dict(json.loads((root / "pricing" / "rulebook.json").read_text("utf-8"))["limits"])
    except (OSError, ValueError, KeyError):
        limits = {}
    return {
        "summary": "The rating workspace and the nights the team replays before a change.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "pricing_files": sorted(p.relative_to(root).as_posix()
                                    for p in (root / "pricing").glob("*")),
            "editable_files": list(EDITABLE_FILES),
            "limits": limits,
        },
        "records": records,
    }


def _order_rows(result: Mapping[str, Any], night: Night) -> list[dict[str, Any]]:
    'Every order, what it ended as, and what it spent getting there.'

    return [{
        "order": row.get("order"), "rule": row.get("rule"), "outcome": row.get("outcome"),
        "price": row.get("value"), "fault": row.get("fault"), "label": row.get("label"),
        "attempts_used": row.get("attempts"), "max_attempts": night.limit("max_attempts", 2),
        "steps_used": row.get("steps"), "step_budget": night.limit("step_budget", 400),
        "reached_the_on_error_branch": row.get("used_fallback"),
    } for row in result.get("orders", ())]


def _lease_rows(result: Mapping[str, Any], night: Night) -> dict[str, Any]:
    return {
        "reservations": list(result.get("leases", ())),
        "still_held_when_the_night_ended": list(result.get("open_leases", ())),
        "most_held_at_once_per_order": dict(result.get("leases_held_at_once", {})),
        "max_open_leases": night.limit("max_open_leases", 1),
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Price one recorded night and report the ledger, the incidents and the spend.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_night(PUBLIC_RECORDS[record_id])
    result = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not result.get("ok"):
        return {
            "summary": f"The {record_id} night could not be priced by this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {"execution_error": result.get("error", "unknown failure"),
                       "diagnostic": result.get("diagnostic")},
        }
    night = Night(result, program)
    return {
        "summary": f"The {record_id} night ran against this workspace.",
        "measurements": {
            "record_id": record_id, "scene": raw.get("scene"),
            "limits": dict(result.get("limits", {})),
            "order_count": len(program.get("orders", ())),
        },
        "public": {
            "what_each_order_ended_as": _order_rows(result, night),
            "what_the_ledger_holds": list(result.get("effects", ())),
            "incidents_raised": list(result.get("faults", ())),
            "incidents_by_label": dict(result.get("labels", {})),
            "rating_reservations": _lease_rows(result, night),
        },
    }
