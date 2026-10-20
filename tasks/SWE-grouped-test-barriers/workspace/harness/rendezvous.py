"""Where handsets on one bench are meant to stop and wait for each other.

Sketched at the handover post-mortem and wired into the runner, but the body is
still a placeholder: a handset reaching a gate gives up its turn and goes on.
"""

from __future__ import annotations

from typing import Any

from . import protocol


class Gates:
    """The bench's named waiting points."""

    def __init__(self, session: protocol.Session):
        self.session = session

    def wait(self, runner: Any, name: str, timeout: float | None = None) -> Any:
        """Stop the running handset at `name` until the rest of its bench arrives."""

        yield protocol.WAIT
