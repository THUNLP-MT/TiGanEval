"""Share one rendering between the desks that ask for the same thing.

An entry is keyed by the document the desks asked for, with the per-call noise
the front door stamps on a request left out of the key. The first caller starts
the rendering, the desks that turn up while it runs are parked on the entry and
handed the whole buffer when it ends, and the entry is dropped when the call
finishes so the next request starts fresh.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RelayRuntime


class InFlightTable:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.by_execution: dict[str, dict[str, Any]] = {}
        self.executions = 0
        self.answered = 0

    def key_for(self, call: Mapping[str, Any]) -> str:
        # request_id, trace_id and retry_budget are per-call noise: two desks
        # asking for the same document are asking for the same thing.
        return str(call["document_id"])

    def arrive(self, call: Mapping[str, Any], runtime: RelayRuntime) -> None:
        key = self.key_for(call)
        entry = self.entries.get(key)
        if entry is None:
            entry = {"key": key, "pieces": {}, "waiting": [], "closed": False}
            self.entries[key] = entry
            execution_id = runtime.begin_upstream(call["document_id"], call["principal"])
            self.executions += 1
            entry["execution_id"] = execution_id
            entry["leader"] = dict(call)
            self.by_execution[execution_id] = entry
        entry["waiting"].append(dict(call))

    def piece(self, execution_id: str, index: int, chunk: str) -> None:
        entry = self.by_execution.get(execution_id)
        if entry is not None:
            entry["pieces"][int(index)] = chunk

    def finished(self, execution_id: str, runtime: RelayRuntime) -> None:
        entry = self._close(execution_id)
        if entry is None:
            return
        pieces = [entry["pieces"][index] for index in sorted(entry["pieces"])]
        for call in entry["waiting"]:
            runtime.deliver(str(call["call_id"]), pieces)
            self.answered += 1
        self._billed(runtime, entry["leader"], "summary")

    def failed(self, execution_id: str, reason: str, runtime: RelayRuntime) -> None:
        entry = self._close(execution_id)
        if entry is None:
            return
        for call in entry["waiting"]:
            runtime.refuse(str(call["call_id"]), str(reason))
            self.answered += 1
        self._billed(runtime, entry["leader"], "refused")

    def hung_up(self, call_id: str) -> None:
        target = str(call_id)
        for entry in self.entries.values():
            entry["waiting"] = [
                call for call in entry["waiting"] if str(call["call_id"]) != target
            ]

    def _close(self, execution_id: str) -> dict[str, Any] | None:
        entry = self.by_execution.pop(execution_id, None)
        if entry is None or entry["closed"]:
            return None
        entry["closed"] = True
        if self.entries.get(entry["key"]) is entry:
            del self.entries[entry["key"]]
        return entry

    def _billed(self, runtime: RelayRuntime, call: Mapping[str, Any], outcome: str) -> None:
        # The ledger entry goes in where it always went in: beside the call the
        # relay actually made to the backend.
        principal = str(call["principal"])
        runtime.record_usage(
            {
                "call_id": str(call["call_id"]),
                "principal": principal,
                "tenant": runtime.tenant_of(principal),
                "request_id": str(call["request_id"]),
                "document_id": str(call["document_id"]),
                "outcome": str(outcome),
            }
        )
