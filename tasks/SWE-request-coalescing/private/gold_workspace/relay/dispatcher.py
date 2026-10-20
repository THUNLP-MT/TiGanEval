"""The relay's request path: ``build_dispatcher`` is what the front door calls
once per process, and everything a caller experiences goes through the object
it returns.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RelayRuntime
from .sharing import InFlightTable


def build_dispatcher(runtime: RelayRuntime) -> "Relay":
    return Relay(runtime)


class Relay:
    def __init__(self, runtime: RelayRuntime):
        self.runtime = runtime
        self.table = InFlightTable()
        self.calls_accepted = 0

    def on_call(self, call: Mapping[str, Any]) -> None:
        self.calls_accepted += 1
        self.table.arrive(call, self.runtime)

    def on_chunk(self, execution_id: str, index: int, chunk: str) -> None:
        self.table.piece(execution_id, index, chunk)

    def on_upstream_complete(self, execution_id: str) -> None:
        self.table.finished(execution_id, self.runtime)

    def on_upstream_error(self, execution_id: str, reason: str) -> None:
        self.table.failed(execution_id, reason, self.runtime)

    def on_abandon(self, call_id: str) -> None:
        self.table.hung_up(call_id)

    def statistics(self) -> Mapping[str, int]:
        return {"calls_accepted": self.calls_accepted,
                "upstream_executions": self.table.executions,
                "calls_answered": self.table.answered}
