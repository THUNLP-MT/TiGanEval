"""Records a console session into one bundle file.

One entry per executed cell, holding the cell's source and what the console
printed under that cell's counter, split into the three fields the format asks
for. Patterns handed to start are taken out of the recorded code.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import (
    REDACTION_MARKER,
    CellResult,
    Shell,
    console_metadata,
    format_error,
    now,
    split_outputs,
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
        self.shell.events.unregister("post_run_cell", self._after_cell)
        self.path = None
        return path

    def status(self) -> dict[str, Any]:
        return {"recording": self.path is not None, "path": self.path}

    def _after_cell(self, result: CellResult) -> None:
        outputs = split_outputs(self.shell.history.of(result.counter))
        event: dict[str, Any] = {
            "type": "cell",
            "seq": len(self.events) + 1,
            "recorded_at": now(),
            "execution_count": result.execution_count,
            "code": self._cleaned(result.code),
            "success": bool(result.success),
            "stdout": outputs["stdout"],
            "stderr": outputs["stderr"],
            "execute_result": (
                {"text/plain": outputs["execute_result"]} if outputs["execute_result"] else {}
            ),
        }
        if not result.success and result.error is not None:
            event["error"] = format_error(result.error)
        self.events.append(event)

    def _cleaned(self, code: str) -> str:
        for pattern in self.patterns:
            code = code.replace(pattern, REDACTION_MARKER)
        return code
