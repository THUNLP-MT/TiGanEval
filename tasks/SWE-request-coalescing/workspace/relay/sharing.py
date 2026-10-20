"""Share one rendering between the desks that ask for the same thing.

Started during the invoice run and not finished. The table keys an in-flight
rendering by the document that was asked for, the first caller starts it, and
the desks that turn up while it is running are parked on the entry.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RelayRuntime


class InFlightTable:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.by_execution: dict[str, dict[str, Any]] = {}
        self.executions = 0

    def key_for(self, call: Mapping[str, Any]) -> str:
        return str(call["document_id"])

    def arrive(self, call: Mapping[str, Any], runtime: RelayRuntime) -> None:
        key = self.key_for(call)
        entry = self.entries.get(key)
        if entry is not None:
            entry["waiting"].append(str(call["call_id"]))
            return
        execution_id = runtime.begin_upstream(call["document_id"], call["principal"])
        self.executions += 1
        entry = {"key": key, "leader": str(call["call_id"]),
                 "principal": str(call["principal"]),
                 "document_id": str(call["document_id"]),
                 "request_id": str(call["request_id"]), "pieces": [], "waiting": []}
        self.entries[key] = entry
        self.by_execution[execution_id] = entry

    def piece(self, execution_id: str, index: int, chunk: str) -> None:
        entry = self.by_execution.get(execution_id)
        if entry is not None:
            entry["pieces"].append(chunk)

    def finished(self, execution_id: str, runtime: RelayRuntime) -> None:
        entry = self.by_execution.get(execution_id)
        if entry is None:
            return
        pieces = list(entry["pieces"])
        runtime.deliver(entry["leader"], pieces)
        for call_id in entry["waiting"]:
            runtime.deliver(call_id, pieces)
        runtime.record_usage({
            "call_id": entry["leader"], "principal": entry["principal"],
            "tenant": runtime.tenant_of(entry["principal"]),
            "request_id": entry["request_id"],
            "document_id": entry["document_id"], "outcome": "summary",
        })
