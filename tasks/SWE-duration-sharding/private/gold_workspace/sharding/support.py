"""Small operating-system helpers used by the planner."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path
from typing import Iterator


@contextmanager
def history_lock(history_path: str) -> Iterator[None]:
    """Serialize read/merge/publish transactions for one history file."""

    lock_path = Path(f"{history_path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
