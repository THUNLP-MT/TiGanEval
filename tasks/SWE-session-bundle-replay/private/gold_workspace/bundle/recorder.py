"""Records a console session into one bundle file.

Each event carries exactly what its own cell put on screen, split by kind, so
two runs of one analysis can be read side by side. The recorder is an attached
resource: a refused start changes nothing at all, a stop detaches it, and every
numbered cell run in between appears once and in order. Being recorded belongs
to the console rather than to any one recorder, so the console's own hooks are
what a start asks before it attaches.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .protocol import (
    REDACTION_MARKER,
    CellInfo,
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
        self._mark = 0

    def start(self, path: str, *, overwrite: bool = False, redact: Sequence[str] = ()) -> str:
        """Begin recording this console into `path`.

        Both refusals are decided before anything is attached or written, so a
        start that does not happen leaves the console, this recorder and the
        file that is already there exactly as they were.
        """
        if self.path is not None or self._console_is_recorded():
            raise RuntimeError("this console is already being recorded")
        target = Path(str(path))
        if target.exists() and not overwrite:
            raise FileExistsError(str(target))
        self.path = str(target)
        self.patterns = tuple(str(item) for item in redact)
        self.events = []
        self._mark = self.shell.history.count
        self.shell.events.register("pre_run_cell", self._before_cell)
        self.shell.events.register("post_run_cell", self._after_cell)
        return self.path

    def stop(self) -> str:
        """Write the bundle out and detach from the console."""
        if self.path is None:
            return ""
        path, self.path = self.path, None
        for name, callback in (
            ("pre_run_cell", self._before_cell),
            ("post_run_cell", self._after_cell),
        ):
            if callback in self.shell.events.callbacks(name):
                self.shell.events.unregister(name, callback)
        metadata = {
            **console_metadata(),
            "created_at": now(),
            "redacted_patterns": len(self.patterns),
            "event_count": len(self.events),
        }
        write_bundle(path, metadata, self.events, overwrite=True)
        return path

    def status(self) -> dict[str, Any]:
        return {"recording": self.path is not None, "path": self.path}

    def _console_is_recorded(self) -> bool:
        """Whether some recorder is already on this console's hooks.

        The app builds a recorder wherever a recording can be begun, so the
        recorder being asked is not the only one that can be holding the
        console; the hooks are where the console says it is being recorded.
        """
        return any(
            isinstance(getattr(callback, "__self__", None), SessionRecorder)
            for name in ("pre_run_cell", "post_run_cell")
            for callback in self.shell.events.callbacks(name)
        )

    def _before_cell(self, info: CellInfo) -> None:
        """Where the scrollback stands before this cell prints anything."""
        self._mark = self.shell.history.count

    def _after_cell(self, result: CellResult) -> None:
        outputs = split_outputs(self.shell.history.since(self._mark))
        if result.execution_count is None:
            return
        event: dict[str, Any] = {
            "type": "cell",
            "seq": len(self.events) + 1,
            "recorded_at": now(),
            "execution_count": int(result.execution_count),
            "code": result.code,
            "success": bool(result.success),
            "stdout": outputs["stdout"],
            "stderr": outputs["stderr"],
            "execute_result": (
                {"text/plain": outputs["execute_result"]} if outputs["execute_result"] else {}
            ),
        }
        if not result.success and result.error is not None:
            event["error"] = format_error(result.error)
        self.events.append(self._cleaned(event))

    def _cleaned(self, value: Any) -> Any:
        """The finished event with every pattern taken out of every string."""
        if isinstance(value, str):
            for pattern in self.patterns:
                value = value.replace(pattern, REDACTION_MARKER)
            return value
        if isinstance(value, dict):
            return {key: self._cleaned(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._cleaned(item) for item in value]
        return value
