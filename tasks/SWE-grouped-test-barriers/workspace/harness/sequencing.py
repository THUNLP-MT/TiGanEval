"""What runs a recorded night on the lab's benches.

One case runs once on a bench, driving that bench's first handset, and the
benches are worked through one after another. `lab_devices.json` now carries a
bench for every handset; nothing here uses that yet beyond picking the first.
"""

from __future__ import annotations

from typing import Any

from . import protocol
from .rendezvous import Gates


class SuiteRunner:
    """Runs one session: the lab phases, each bench, and each bench's cases."""

    def __init__(self, session: protocol.Session):
        self.session = session
        self.gates = Gates(session)
        #: What the phase now running is driving, and writing to.
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
        self.handset = self.session.handset(lead)
        self.handset_id = lead
        opened = self._phase(protocol.Execution(protocol.BENCH_OPEN, bench, lead))
        if opened is not False:
            for case in self.session.case_order:
                self._case(bench, case, lead)
        self._phase(protocol.Execution(protocol.BENCH_CLOSE, bench, lead))
        for handset_id in handsets:
            self.session.pool.release(handset_id, self.session.scheduler.now())

    def _case(self, bench: str, case: str, handset_id: str) -> None:
        self.record = self.session.ledger.open_record(case, handset_id, bench)
        self._phase(protocol.Execution(protocol.CASE, bench, handset_id, case))
        self.session.ledger.close_record(
            self.record, "flagged" if self.record.flags else "passed")
        self.record = None

    def _phase(self, execution: protocol.Execution) -> Any:
        """Run one phase to the end and hand back what it returned."""
        if execution.phase == protocol.CASE:
            steps = self.session.case_program(str(execution.case))
        else:
            steps = self.session.phase_program(execution.phase, execution.bench)
        key = f"{execution.phase}|{execution.bench}|{execution.case}|{execution.handset}"
        scheduler = self.session.scheduler
        scheduler.spawn(key, protocol.interpret(self.session, execution, steps, self))
        scheduler.run()
        value, error = scheduler.outcome(key)
        if error is not None:
            raise error
        return value

    # -- what a suite step asks the runner for --
    def wait_at_gate(self, name: str, timeout: float | None = None) -> Any:
        return self.gates.wait(self, name, timeout)

    def read_context(self, field: str) -> Any:
        return getattr(self, field)

    def flag(self, text: str) -> None:
        self.session.ledger.flag(self.record, text)
