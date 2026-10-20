"""Runs a recorded session again in a console here.

A bundle is a document another machine produced, so it is admitted or refused
whole: nothing runs until the file has been read and checked against the
format. The console doing the replaying keeps its own numbering.
"""

from __future__ import annotations

from typing import Any

from .protocol import (
    BundleRejected,
    ReplayReport,
    Shell,
    read_bundle,
    schema_errors,
)

def load_bundle(path: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The metadata and the events of the bundle at `path`, or a refusal.

    Reading a file is never the thing that runs it, so this checks the whole
    document before any caller can execute a line of it.
    """
    metadata, events = read_bundle(path)
    errors = schema_errors(metadata, events)
    if errors:
        raise BundleRejected(path, errors)
    return metadata, events

def replay_bundle(
    shell: Shell, path: Any, *, stop_on_error: bool = True, store_history: bool = True
) -> ReplayReport:
    """Run the recorded cells of the bundle at `path` in `shell`.

    Only the recorded source is read; the numbers in the file belong to the
    session it came from and the console here keeps its own, advancing once per
    cell when the caller asked for history and not at all when it did not.
    """
    _metadata, events = load_bundle(path)
    executed: list[int] = []
    for event in events:
        result = shell.run_cell(event["code"], store_history=store_history)
        executed.append(int(event["seq"]))
        if not result.success and stop_on_error:
            return ReplayReport(executed=tuple(executed), stopped_at=int(event["seq"]))
    return ReplayReport(executed=tuple(executed), stopped_at=None)
