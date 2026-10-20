"""Runtime contract for the device lab's night runner.

Every bench controller ships this file, so the phase names, the inventory and
session formats, the scheduler, the ledger and the shared handset pool are the
same on all eight. Lab time is virtual: it moves only when a suite step spends
it, and each handset carries its own reading. The runner in ``harness/`` turns a
recorded session into a night; this file gives it the pieces."""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import json
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

#: The phases of one night, in the order the lab runs them.
LAB_OPEN, BENCH_OPEN, CASE, BENCH_CLOSE, LAB_CLOSE = (
    "lab_open", "bench_open", "case", "bench_close", "lab_close")
PHASES: tuple[str, ...] = (LAB_OPEN, BENCH_OPEN, CASE, BENCH_CLOSE, LAB_CLOSE)
#: The phases in which a handset is claimed, so a step can read which one it is
#: driving; the lab phases run before any is claimed and after all have gone back.
HANDSET_PHASES: tuple[str, ...] = (BENCH_OPEN, CASE, BENCH_CLOSE)
CONTEXT_FIELDS: tuple[str, ...] = ("handset", "handset_id")  #: what a step may ask for
#: The name a suite author sees in an alert about a wrong gate request.
GATE_ENTRY_POINT = "wait_at_gate"
#: What a fiber yields to give the other handsets a turn.
WAIT = "wait"

class LabError(RuntimeError):
    """Something the lab did: a handset dropped, a chamber door opened. The lab
    on-call is paged for these, and the night carries on around them."""

class SuiteError(RuntimeError):
    """Something the suite did that no handset could have caused.

    The suite author is paged for these; ``details`` carries what that author
    needs to find the offending line. Like a lab fault, one of these is that
    author's to fix in the morning and the night is worked to the end around
    it: what a case cannot get past is that case's, not the bench's and not
    the lab's."""

    def __init__(self, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})

def suite_error(message: str, **details: Any) -> SuiteError:
    """Build the error that pages the suite author."""
    return SuiteError(str(message), details)

def unbound_context(field_name: str, phase: str) -> SuiteError:
    """What a step gets when it asks which handset it is driving and none is.

    A leftover id here would power-cycle, reflash or wipe a handset that has
    gone back to the pool, so the question comes back as an error rather than
    as the last value that happened to be lying around."""
    return suite_error(f"{field_name} is not available in {phase}",
                       field=str(field_name), phase=str(phase))

def check_gate_request(phase: str, timeout: float | None) -> None:
    """Check one gate request before it reaches the runner's gate table.

    The rota splits on the type raised, so the two failures stay apart. A
    timeout that cannot exist is the suite author's arithmetic: a negative one
    is a plain ``ValueError`` raised before anything else about the request is
    looked at, and a zero one is a wait that can never be met, so a
    :class:`SuiteError`. A gate asked for from a phase that has claimed no
    handset is a :class:`SuiteError` naming the entry point."""
    if timeout is not None:
        number = float(timeout)
        if number < 0:
            raise ValueError(f"a gate timeout cannot be negative: {timeout}")
        if number == 0:
            raise suite_error("a gate with no time to wait can never be met",
                              entry_point=GATE_ENTRY_POINT, phase=str(phase))
    if str(phase) not in HANDSET_PHASES:
        raise suite_error(f"{GATE_ENTRY_POINT} needs a claimed handset",
                          entry_point=GATE_ENTRY_POINT, phase=str(phase))

@dataclass(frozen=True, slots=True)
class Handset:
    """One phone in the lab, on the bench it is wired to."""
    id: str
    bench: str
    model: str = ""

@dataclass(frozen=True, slots=True)
class Execution:
    """One phase running for one handset: what a step belongs to."""
    phase: str
    bench: str | None = None
    handset: str | None = None
    case: str | None = None

@dataclass
class CaseRecord:
    """One row of the morning report: what one case did on one handset."""
    case: str
    handset: str
    bench: str
    flags: list[str] = field(default_factory=list)
    outcome: str | None = None

class Ledger:
    """The night's result records, in the order they were opened."""
    def __init__(self) -> None:
        self.records: list[CaseRecord] = []
    def open_record(self, case: str, handset: str, bench: str) -> CaseRecord:
        record = CaseRecord(str(case), str(handset), str(bench))
        self.records.append(record)
        return record
    def flag(self, record: CaseRecord, text: str) -> None:
        """Note one thing that went wrong without ending the case."""
        record.flags.append(str(text))
    def close_record(self, record: CaseRecord, outcome: str) -> None:
        record.outcome = str(outcome)
    def rows(self) -> list[dict[str, Any]]:
        return [{"case": r.case, "handset": r.handset, "bench": r.bench,
                 "flags": list(r.flags), "outcome": r.outcome} for r in self.records]

class HandsetPool:
    """The lab's shared handsets, and who has them right now. A handset still
    checked out in the morning is one the next night's session cannot get, so
    every checkout and every return is written down."""
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.held: set[str] = set()
    def check_out(self, handset_id: str, at_ms: float = 0.0) -> None:
        self.events.append({"handset": str(handset_id), "action": "check_out", "at_ms": float(at_ms)})
        self.held.add(str(handset_id))
    def release(self, handset_id: str, at_ms: float = 0.0) -> None:
        self.events.append({"handset": str(handset_id), "action": "release", "at_ms": float(at_ms)})
        self.held.discard(str(handset_id))

class Scheduler:
    """Cooperative turn-taking over whatever is running right now.

    Each fiber carries its own reading of lab time, moved only by its own
    ``work`` steps. The turn goes to the runnable fiber reading earliest, so a
    night is worked through in lab-time order and fibers reading the same
    moment go in spawn order. A parked fiber takes no turns. The scheduler
    knows nothing about what a fiber waits for: parking is the runner's."""
    def __init__(self, start_ms: float = 0.0):
        self.start_ms = float(start_ms)
        self.steps = 0
        self.exhausted = False
        self._order: list[str] = []
        self._fibers: dict[str, Iterator[Any]] = {}
        self._clock: dict[str, float] = {}
        self._parked: dict[str, str] = {}
        self._done: dict[str, tuple[Any, BaseException | None]] = {}
        self._current: str | None = None
        self._high = float(start_ms)
    def spawn(self, key: str, fiber: Iterator[Any], at_ms: float | None = None) -> None:
        """Register one running phase. It starts where the night has got to."""
        name = str(key)
        if name in self._fibers:
            raise suite_error(f"{name} is already running", key=name)
        self._order.append(name)
        self._fibers[name] = fiber
        self._clock[name] = self._high if at_ms is None else float(at_ms)
        self._high = max(self._high, self._clock[name])
    def now(self) -> float:
        """The lab-time reading of the fiber taking its turn."""
        return self._clock.get(self._current, self._high) if self._current else self._high
    def advance(self, ms: float) -> None:
        """Spend lab time on the fiber taking its turn."""
        if self._current is None:
            raise suite_error("nothing is taking a turn", entry_point="advance")
        self._clock[self._current] += float(ms)
        self._high = max(self._high, self._clock[self._current])
    def park(self, key: str, waiting_for: str = "") -> None:
        """Take a fiber out of the turn order until something unparks it."""
        self._parked[str(key)] = str(waiting_for)
    def unpark(self, key: str) -> None:
        """Put a parked fiber back in the turn order.

        It was waiting, so it comes back at the moment it was let go: its
        reading moves forward to the reading of whoever released it."""
        name, released_at = str(key), self.now()
        if self._clock.get(name, released_at) < released_at:
            self._clock[name] = released_at
        self._high = max(self._high, self._clock.get(name, released_at))
        self._parked.pop(name, None)
    def clock(self, key: str) -> float:
        return self._clock.get(str(key), self.start_ms)
    def outcome(self, key: str) -> tuple[Any, BaseException | None]:
        """What a finished fiber returned, and what it raised if it did."""
        return self._done.get(str(key), (None, None))
    def run(self, limit: int = 20000) -> None:
        """Give turns until nobody can take one."""
        while self.steps < int(limit):
            key = self._next_runnable()
            if key is None:
                return
            self._current, self.steps = key, self.steps + 1
            try:
                next(self._fibers[key])
            except StopIteration as stop:
                self._done[key] = (stop.value, None)
            except BaseException as exc:  # noqa: BLE001 - handed back by outcome()
                self._done[key] = (None, exc)
            finally:
                self._current = None
        self.exhausted = True
    def _next_runnable(self) -> str | None:
        chosen: tuple[float, str] | None = None
        for key in self._order:
            if key in self._done or key in self._parked:
                continue
            if chosen is None or self._clock[key] < chosen[0]:
                chosen = (self._clock[key], key)
        return None if chosen is None else chosen[1]
    def waiting(self) -> list[dict[str, Any]]:
        """Fibers that never finished, and what each was waiting for."""
        return [{"fiber": key, "waiting_for": self._parked.get(key, "its own turn"),
                 "parked": key in self._parked, "at_ms": self._clock.get(key, self.start_ms)}
                for key in self._order if key not in self._done]

class Session:
    """One recorded night, resolved against the lab inventory: the handsets
    taking part, the benches they belong to, every phase's step program, the
    scheduler, the ledger and the pool."""
    def __init__(self, name: str, handsets: Sequence[Handset], phase_programs: Mapping[str, Any],
                 cases: Mapping[str, Sequence[Mapping[str, Any]]], case_order: Sequence[str],
                 start_ms: float = 0.0):
        self.name = str(name)
        self.handsets: tuple[Handset, ...] = tuple(handsets)
        self._by_id = {item.id: item for item in self.handsets}
        grouped: dict[str, list[str]] = {}
        for item in self.handsets:
            grouped.setdefault(item.bench, []).append(item.id)
        self._benches = {name: tuple(ids) for name, ids in grouped.items()}
        self.benches: tuple[str, ...] = tuple(self._benches)
        self._phase_programs = dict(phase_programs)
        self._cases = {str(k): tuple(dict(s) for s in v) for k, v in cases.items()}
        self.case_order: tuple[str, ...] = tuple(str(item) for item in case_order)
        self.scheduler = Scheduler(start_ms)
        self.ledger = Ledger()
        self.pool = HandsetPool()
        self.trace: list[dict[str, Any]] = []
    def handset(self, handset_id: str) -> Handset:
        try:
            return self._by_id[str(handset_id)]
        except KeyError:
            raise suite_error(f"no such handset in this session: {handset_id}") from None
    def bench_handsets(self, bench: str) -> tuple[str, ...]:
        """The handsets this session put on that bench, in inventory order."""
        return self._benches.get(str(bench), ())
    def phase_program(self, phase: str, bench: str | None = None) -> tuple[dict[str, Any], ...]:
        """The steps of one phase; a bench phase may differ per bench."""
        program = self._phase_programs.get(str(phase), ())
        if isinstance(program, Mapping):
            program = program.get(str(bench), program.get("*", ()))
        return tuple(dict(step) for step in program)
    def case_program(self, case: str) -> tuple[dict[str, Any], ...]:
        return self._cases.get(str(case), ())
    def report(self) -> dict[str, Any]:
        """Everything the night wrote down, as the console prints it."""
        return {"session": self.name, "case_order": list(self.case_order),
                "benches": {n: list(ids) for n, ids in self._benches.items()},
                "steps": [dict(row) for row in self.trace], "records": self.ledger.rows(),
                "pool": [dict(row) for row in self.pool.events],
                "still_checked_out": sorted(self.pool.held),
                "unfinished_at_quiescence": self.scheduler.waiting(),
                "turns_taken": self.scheduler.steps,
                "turns_exhausted": bool(self.scheduler.exhausted)}

def load_inventory(path: str | Path) -> dict[str, Handset]:
    """Read ``lab_devices.json``: every handset in the lab and its bench."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = raw["handsets"] if isinstance(raw, Mapping) else raw
    return {str(e["id"]): Handset(str(e["id"]), str(e.get("bench", "default")),
                                  str(e.get("model", ""))) for e in entries}

def load_session(spec: Mapping[str, Any], inventory: Mapping[str, Handset]) -> Session:
    """Resolve one recorded session against the lab inventory."""
    missing = [str(h) for h in spec.get("handsets", ()) if str(h) not in inventory]
    if missing:
        raise suite_error(f"the session asks for handsets the lab has not got: {missing}")
    handsets = [inventory[str(h)] for h in spec.get("handsets", ())]
    return Session(name=str(spec.get("name", "session")), handsets=handsets,
                   phase_programs=dict(spec.get("phases", {})), cases=dict(spec.get("cases", {})),
                   case_order=list(spec.get("case_order", ())),
                   start_ms=float(spec.get("start_ms", 0.0)))

def _ticks(value: Any, handset: str | None) -> float:
    """A ``work`` cost, which may be written per handset."""
    if isinstance(value, Mapping):
        return float(value.get(str(handset), value.get("*", 0)))
    return float(value)

def interpret(session: Session, execution: Execution,
              steps: Sequence[Mapping[str, Any]], runner: Any) -> Any:
    """Run one phase program for one handset, writing every step down.

    A generator: it gives up its turn at every ``work`` step and wherever the
    runner's gate does. The runner supplies ``wait_at_gate(name, timeout)``,
    ``read_context(field)`` and ``flag(text)``; the rest happens here. A step
    carrying ``only`` runs on that handset alone, and a ``check`` step is the
    lab's own conformance probe, writing down what the runner returned or
    raised and carrying on rather than ending the phase on the answer."""
    scheduler = session.scheduler
    for index, raw in enumerate(steps):
        step = dict(raw)
        op = str(step.get("op", ""))
        if "only" in step and str(step["only"]) != str(execution.handset):
            continue
        row: dict[str, Any] = {"phase": execution.phase, "bench": execution.bench,
                               "handset": execution.handset, "case": execution.case,
                               "index": index, "op": op, "at_ms": scheduler.now()}
        if op in ("note", "flag", "fail", "decline"):
            row["text"] = str(step.get("text", ""))
            session.trace.append(row)
            if op == "flag":
                runner.flag(row["text"])
            elif op == "fail":
                raise LabError(row["text"] or "the handset stopped answering")
            elif op == "decline":
                return False
        elif op == "work":
            row["ticks"] = _ticks(step.get("ticks", 0), execution.handset)
            session.trace.append(row)
            scheduler.advance(row["ticks"])
            yield WAIT
        elif op == "wait":
            row["gate"], row["timeout"] = str(step.get("gate", "gate")), step.get("timeout")
            session.trace.append(row)
            outcome = runner.wait_at_gate(row["gate"], step.get("timeout"))
            if inspect.isgenerator(outcome):
                yield from outcome
            session.trace.append({**row, "op": "resume", "at_ms": scheduler.now()})
        elif op == "check":
            ask = str(step.get("ask", "handset_id"))
            row["ask"] = ask
            try:
                if ask == "gate":
                    row["gate"], row["timeout"] = str(step.get("gate", "check")), step.get("timeout")
                    outcome = runner.wait_at_gate(row["gate"], step.get("timeout"))
                    if inspect.isgenerator(outcome):
                        yield from outcome
                    row["value"] = "returned"
                else:
                    answer = runner.read_context(ask)
                    row["value"] = answer.id if isinstance(answer, Handset) else answer
            except BaseException as exc:  # noqa: BLE001 - the probe writes it down
                row.update({"error": type(exc).__name__, "message": str(exc)[:200],
                            "details": dict(getattr(exc, "details", {}) or {})})
            session.trace.append(row)
        else:
            session.trace.append(row)
            raise suite_error(f"unknown suite step: {op}", op=op, phase=execution.phase)
    return True
