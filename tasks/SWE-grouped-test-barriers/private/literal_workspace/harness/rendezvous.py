"""The named points where the handsets stop and wait for each other."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import protocol


@dataclass
class Gate:
    """One named waiting point: who has arrived, and who is parked on it."""

    arrived: list[str] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)


class Gates:
    """Every named waiting point in the session, by name."""

    def __init__(self, session: protocol.Session):
        self.session = session
        self.execution: protocol.Execution | None = None
        self.party = len(session.handsets)
        self._gates: dict[str, Gate] = {}

    def wait(self, runner: Any, name: str, timeout: float | None = None) -> Any:
        """Stop here until everyone taking part has arrived."""

        execution = self.execution
        gate = self._gates.setdefault(str(name), Gate())
        gate.arrived.append(str(execution.handset))
        if len(gate.arrived) >= self.party:
            for waiter in gate.parked:
                self.session.scheduler.unpark(waiter)
            gate.parked.clear()
            return
        key = "|".join(str(part) for part in (
            execution.phase, execution.bench, execution.case, execution.handset))
        gate.parked.append(key)
        self.session.scheduler.park(key, str(name))
        yield protocol.WAIT
