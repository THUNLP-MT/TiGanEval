"""Runs a recorded session again in a console here.

It reads the bundle and feeds every recorded cell back into the console it is
given, in the order they were recorded.
"""

from __future__ import annotations

from typing import Any

from .protocol import ReplayReport, Shell, read_bundle

def load_bundle(path: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The metadata and the events of the bundle at `path`."""
    return read_bundle(path)

def replay_bundle(
    shell: Shell, path: Any, *, stop_on_error: bool = True, store_history: bool = True
) -> ReplayReport:
    """Run every recorded cell of the bundle at `path` in `shell`."""
    _metadata, events = load_bundle(path)
    executed: list[int] = []
    for event in events:
        shell.run_cell(event["code"])
        executed.append(int(event["seq"]))
    return ReplayReport(executed=tuple(executed), stopped_at=None)
