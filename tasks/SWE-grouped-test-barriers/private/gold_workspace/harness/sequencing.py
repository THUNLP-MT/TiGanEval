"""What runs a recorded night on the lab's benches.

`lab_open` once, then each bench, then `lab_close` once, whatever happened in
between. A bench takes its handsets out of the pool, opens, runs every case
once on each of its own handsets at the same time, closes, and puts its
handsets back; a bench that cannot open still closes and still gives its
handsets back, and the benches after it still run.

Everything a step can ask about -- which handset it is driving, which row of
the report it is writing to, which bench it is meeting on -- belongs to the
execution that is taking its turn, not to the runner. The runner keeps a
stack of running executions and pushes the right one back on every time the
scheduler resumes a fiber, so two handsets working through the same case body
never read or write each other's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from . import protocol
from .rendezvous import Gates


@dataclass
class Run:
    """One phase running for one handset, and everything bound to it."""

    execution: protocol.Execution
    key: str
    handset: protocol.Handset | None = None
    record: protocol.CaseRecord | None = None


class SuiteRunner:
    """Runs one session: the lab phases, each bench, and each bench's cases."""

    def __init__(self, session: protocol.Session):
        self.session = session
        self.gates = Gates(session)
        self._running: list[Run] = []
        self._cancelled: set[str] = set()

    # -- the night ---------------------------------------------------------

    def run(self) -> None:
        try:
            self._solo_quietly(protocol.Execution(protocol.LAB_OPEN))
            for bench in self.session.benches:
                self._bench(bench)
        finally:
            self._solo_quietly(protocol.Execution(protocol.LAB_CLOSE))

    def _bench(self, bench: str) -> None:
        handsets = self.session.bench_handsets(bench)
        lead = handsets[0]
        taken = self.session.scheduler.now()
        for handset_id in handsets:
            self.session.pool.check_out(handset_id, taken)
        try:
            opened = self._solo(protocol.Execution(protocol.BENCH_OPEN, bench, lead))
            if opened is not False:
                for case in self.session.case_order:
                    self._case(bench, case)
        except (protocol.LabError, protocol.SuiteError, ValueError):
            pass  # this bench is lost for the night; the rest of the lab is not
        finally:
            self._solo_quietly(protocol.Execution(protocol.BENCH_CLOSE, bench, lead))
            given_back = self.session.scheduler.now()
            for handset_id in handsets:
                self.session.pool.release(handset_id, given_back)

    def _case(self, bench: str, case: str) -> None:
        """Run one case on every handset of this bench at the same time."""

        scheduler, steps = self.session.scheduler, self.session.case_program(case)
        runs = []
        for handset_id in self.session.bench_handsets(bench):
            execution = protocol.Execution(protocol.CASE, bench, handset_id, case)
            run = Run(
                execution, self._key(execution),
                handset=self.session.handset(handset_id),
                record=self.session.ledger.open_record(case, handset_id, bench),
            )
            runs.append(run)
            scheduler.spawn(run.key, self._fiber(run, steps))
        scheduler.run()
        run_keys = {run.key for run in runs}
        unfinished = {
            str(row["fiber"]) for row in scheduler.waiting()
            if str(row["fiber"]) in run_keys
        }
        failed = any(scheduler.outcome(run.key)[1] is not None for run in runs)
        if failed and unfinished:
            self._cancelled.update(unfinished)
            self.gates.cancel_case(bench, case)
            scheduler.run()
        for run in runs:
            _, error = scheduler.outcome(run.key)
            outcome = "errored" if error is not None else ("flagged" if run.record.flags else "passed")
            self.session.ledger.close_record(run.record, outcome)
            self._cancelled.discard(run.key)

    def _solo(self, execution: protocol.Execution) -> Any:
        """Run a phase that belongs to the lab or to a bench as a whole."""

        steps = self.session.phase_program(execution.phase, execution.bench)
        run = Run(execution, self._key(execution),
                  handset=self.session.handset(execution.handset) if execution.handset else None)
        self.session.scheduler.spawn(run.key, self._fiber(run, steps))
        self.session.scheduler.run()
        value, error = self.session.scheduler.outcome(run.key)
        if error is not None:
            raise error
        return value

    def _solo_quietly(self, execution: protocol.Execution) -> Any:
        try:
            return self._solo(execution)
        except (protocol.LabError, protocol.SuiteError, ValueError):
            return None

    @staticmethod
    def _key(execution: protocol.Execution) -> str:
        return "|".join(str(part) for part in (
            execution.phase, execution.bench, execution.case, execution.handset))

    def _fiber(self, run: Run, steps: Any) -> Iterator[Any]:
        """Drive one execution, putting its bindings back on every resume."""

        inner = protocol.interpret(self.session, run.execution, steps, self)
        while True:
            self._running.append(run)
            try:
                if run.key in self._cancelled:
                    raise protocol.LabError("another handset ended this case")
                value = next(inner)
            except StopIteration as stop:
                return stop.value
            finally:
                self._running.pop()
            yield value

    # -- what a suite step asks the runner for ------------------------------

    def current_run(self) -> Run:
        """The execution taking its turn right now."""

        if not self._running:
            raise protocol.suite_error("nothing is taking a turn", entry_point="current_run")
        return self._running[-1]

    def wait_at_gate(self, name: str, timeout: float | None = None) -> Any:
        return self.gates.wait(self, name, timeout)

    def read_context(self, field: str) -> Any:
        run = self._running[-1] if self._running else None
        phase = run.execution.phase if run is not None else "no phase"
        if run is None or run.handset is None or phase not in protocol.HANDSET_PHASES:
            raise protocol.unbound_context(field, phase)
        return run.handset.id if field == "handset_id" else run.handset

    def flag(self, text: str) -> None:
        run = self.current_run()
        if run.record is None:
            raise protocol.suite_error("nothing is being written down here",
                                       phase=run.execution.phase)
        self.session.ledger.flag(run.record, text)
