"""Share one rendering between the desks that ask for the same thing.

An entry is keyed by the document and the scope the backend renders it for, so
two desks share a rendering only when a solo rendering would have given them
the same bytes. The entry owns the work, not the caller that happened to start
it: every waiter is answered from the entry's own buffer when the rendering
ends, in success and in failure alike, and the key is free again the moment the
entry closes.

Every path out of ``arrive`` ends in an answer, including the one where the
directory has no entry left to read: a call the request path drops on its way
through is a connection the front door holds open for ever.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import RelayError, RelayRuntime, summary_scope


class InFlightTable:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], dict[str, Any]] = {}
        self.by_execution: dict[str, dict[str, Any]] = {}
        self.executions = 0
        self.answered = 0

    def scope_of(self, runtime: RelayRuntime, principal: str) -> str:
        return summary_scope(runtime.tenant_of(principal), runtime.clearance_of(principal))

    def arrive(self, call: Mapping[str, Any], runtime: RelayRuntime) -> None:
        call_id = str(call["call_id"])
        principal = str(call["principal"])
        document_id = str(call["document_id"])
        try:
            authorized = runtime.is_authorized(principal, document_id)
            scope = self.scope_of(runtime, principal)
        except RelayError:
            # The directory has nothing to read for this desk any more. The
            # front door is still holding its connection open, so it leaves
            # with a refusal; there is no tenant to bill it under, so nothing
            # is written down against it.
            runtime.refuse(call_id, "unknown_principal")
            self.answered += 1
            return
        if not authorized:
            runtime.refuse(call_id, "not_authorized")
            self._settled(runtime, call, "refused")
            return
        key = (document_id, scope)
        entry = self.entries.get(key)
        if entry is None:
            entry = {"key": key, "pieces": {}, "waiting": [], "closed": False}
            self.entries[key] = entry
            execution_id = runtime.begin_upstream(document_id, principal)
            self.executions += 1
            entry["execution_id"] = execution_id
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
            self._settled(runtime, call, "summary")

    def failed(self, execution_id: str, reason: str, runtime: RelayRuntime) -> None:
        entry = self._close(execution_id)
        if entry is None:
            return
        for call in entry["waiting"]:
            runtime.refuse(str(call["call_id"]), str(reason))
            self._settled(runtime, call, "refused")

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

    def _settled(self, runtime: RelayRuntime, call: Mapping[str, Any], outcome: str) -> None:
        principal = str(call["principal"])
        self.answered += 1
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
