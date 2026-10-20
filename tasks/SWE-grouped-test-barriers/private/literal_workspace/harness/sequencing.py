"""What runs a recorded night on the lab's benches.

The handsets on one bench now run a case together instead of one after the
other, and the runner sets the handset the running step is driving so a step
can read it.
"""

from __future__ import annotations

from typing import Any, Iterator

from . import protocol
from .rendezvous import Gates


class SuiteRunner:
    """Runs one session: the lab phases, each bench, and each bench's cases."""

    def __init__(self, session: protocol.Session):
        self.session = session
        self.gates = Gates(session)
        self.handset: protocol.Handset | None = None
        self.handset_id: str | None = None
        self.record: protocol.CaseRecord | None = None

    def run(self) -> None:
        self._phase(protocol.Execution(protocol.LAB_OPEN))
        for bench in self.session.benches:
            self._bench(bench)
        self._phase(protocol.Execution(protocol.LAB_CLOSE))

    def _bench(self, bench: str) -> None:
        handsets = self.session.bench_handsets(bench)
        lead = handsets[0]
        for handset_id in handsets:
            self.session.pool.check_out(handset_id, self.session.scheduler.now())
        self.handset, self.handset_id = self.session.handset(lead), lead
        opened = self._phase(protocol.Execution(protocol.BENCH_OPEN, bench, lead))
        if opened is not False:
            for case in self.session.case_order:
                self._case(bench, case)
        self._phase(protocol.Execution(protocol.BENCH_CLOSE, bench, lead))
        for handset_id in handsets:
            self.session.pool.release(handset_id, self.session.scheduler.now())

    def _case(self, bench: str, case: str) -> None:
        """Run the case on every handset of this bench at the same time."""

        scheduler, steps = self.session.scheduler, self.session.case_program(case)
        keys = []
        for handset_id in self.session.bench_handsets(bench):
            execution = protocol.Execution(protocol.CASE, bench, handset_id, case)
            record = self.session.ledger.open_record(case, handset_id, bench)
            key = self._key(execution)
            keys.append((key, record))
            scheduler.spawn(key, self._fiber(execution, record, steps))
        scheduler.run()
        for key, record in keys:
            _, error = scheduler.outcome(key)
            outcome = "errored" if error is not None else ("flagged" if record.flags else "passed")
            self.session.ledger.close_record(record, outcome)

    def _fiber(self, execution: protocol.Execution, record: protocol.CaseRecord,
               steps: Any) -> Iterator[Any]:
        self.handset = self.session.handset(str(execution.handset))
        self.handset_id = str(execution.handset)
        self.record = record
        self.gates.execution = execution
        yield from protocol.interpret(self.session, execution, steps, self)

    def _phase(self, execution: protocol.Execution) -> Any:
        steps = self.session.phase_program(execution.phase, execution.bench)
        key = self._key(execution)
        self.gates.execution = execution
        self.session.scheduler.spawn(
            key, protocol.interpret(self.session, execution, steps, self))
        self.session.scheduler.run()
        value, error = self.session.scheduler.outcome(key)
        if error is not None:
            raise error
        return value

    @staticmethod
    def _key(execution: protocol.Execution) -> str:
        return "|".join(str(part) for part in (
            execution.phase, execution.bench, execution.case, execution.handset))

    def wait_at_gate(self, name: str, timeout: float | None = None) -> Any:
        return self.gates.wait(self, name, timeout)

    def read_context(self, field: str) -> Any:
        return getattr(self, field)

    def flag(self, text: str) -> None:
        self.session.ledger.flag(self.record, text)
