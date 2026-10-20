"""The named points where the handsets working on one case meet.

A gate is not its name. It belongs to the bench that is meeting, to the phase
and case that reached it, and to that one meeting: the moment the last handset
of the bench arrives, the gate is gone, and the next time that name comes up --
later in the same case body, in a later case, on a later bench -- a new one is
made. A gate reached from a bench-wide phase has one handset to wait for,
because a bench-wide phase runs once for the bench.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import protocol


@dataclass
class Gate:
    """One meeting: who has to arrive, who has, and who is parked."""

    party: int
    arrived: list[str] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)


class Gates:
    """The gates that are open right now, one per meeting."""

    def __init__(self, session: protocol.Session):
        self.session = session
        self._open: dict[tuple[Any, ...], Gate] = {}

    def party(self, execution: protocol.Execution) -> int:
        """How many handsets meet at a gate reached from this phase."""

        if execution.phase == protocol.CASE:
            return len(self.session.bench_handsets(str(execution.bench)))
        return 1

    def cancel_case(self, bench: str, case: str) -> None:
        """Retire a failed case's meetings and wake its parked fibers to stop."""

        for key, gate in list(self._open.items()):
            belongs_to_case = (
                str(key[0]) == str(bench)
                and key[1] == protocol.CASE
                and str(key[2]) == str(case)
            )
            if not belongs_to_case:
                continue
            del self._open[key]
            for waiter in gate.parked:
                self.session.scheduler.unpark(waiter)

    def wait(self, runner: Any, name: str, timeout: float | None = None) -> Any:
        """Hold the running handset at `name` until its bench is all there."""

        run = runner.current_run()
        execution = run.execution
        protocol.check_gate_request(execution.phase, timeout)
        key = (execution.bench, execution.phase, execution.case, str(name))
        gate = self._open.get(key)
        if gate is None:
            gate = self._open[key] = Gate(self.party(execution))
        gate.arrived.append(str(execution.handset))
        if len(gate.arrived) >= gate.party:
            del self._open[key]  # this meeting is over; the name is free again
            for waiter in gate.parked:
                self.session.scheduler.unpark(waiter)
            return
        gate.parked.append(run.key)
        self.session.scheduler.park(run.key, f"{name} on {execution.bench}")
        yield protocol.WAIT
