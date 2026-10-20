"""Records a console session into one bundle file. Dana's prototype.

It hooks the console after every cell and keeps one entry per cell, then writes
the whole lot out when the session is stopped. What a cell put on screen is
read back out of the console's store under that cell's counter.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import (
    Shell,
    console_metadata,
    format_error,
    now,
    write_bundle,
)

class SessionRecorder:
    """One recorder attached to one console."""
    def __init__(self, shell: Shell):
        self.shell = shell
        self.path: str | None = None
        self.patterns: tuple[str, ...] = ()
        self.events: list[dict[str, Any]] = []

    def start(self, path: str, *, overwrite: bool = False, redact: Sequence[str] = ()) -> str:
        """Begin recording this console into `path`."""
        self.path = str(path)
        self.patterns = tuple(str(item) for item in redact)
        self.events = []
        self.shell.events.register("post_run_cell", self._after_cell)
        return self.path

    def stop(self) -> str:
        """Write the bundle out and stop recording."""
        path = str(self.path)
        metadata = {
            **console_metadata(),
            "created_at": now(),
            "redacted_patterns": len(self.patterns),
            "event_count": len(self.events),
        }
        write_bundle(path, metadata, self.events, overwrite=True)
        self.path = None
        return path

    def status(self) -> dict[str, Any]:
        return {"recording": self.path is not None, "path": self.path}

    def _after_cell(self, result: Any) -> None:
        printed = "".join(entry.text for entry in self.shell.history.of(result.counter))
        event = {
            "type": "cell",
            "seq": len(self.events) + 1,
            "recorded_at": now(),
            "execution_count": result.execution_count,
            "code": result.code,
            "success": result.success,
            "stdout": printed,
            "stderr": "",
            "execute_result": {},
        }
        if not result.success:
            event["error"] = format_error(result.error)
        self.events.append(event)
