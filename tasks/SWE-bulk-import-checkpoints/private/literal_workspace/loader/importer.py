"""Bulk catalogue import in checkpointed batches.

Reads the export `checkpoint_interval` rows at a time, commits each batch, and
records how far it got so the next run carries on from there instead of
starting the export again from row 0.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    ImportConfig,
    SourceFeed,
    SourceInterrupted,
    Storage,
    StorageFailure,
    stored_row,
    table_of,
)


PROGRESS_KEY = "catalogue_import_position"


def _resume_position(storage: Storage) -> int:
    progress = storage.read_meta(PROGRESS_KEY)
    if isinstance(progress, Mapping):
        return int(progress.get("position", 0))
    return 0


def run_import(
    storage: Storage,
    feed: SourceFeed,
    config: ImportConfig,
) -> Mapping[str, Any]:
    """Load the export in batches, committing every `checkpoint_interval` rows."""

    interval = max(1, int(config.checkpoint_interval))
    total = int(config.total_rows) or feed.total_rows()
    resumed_from = _resume_position(storage)
    position = resumed_from
    rows_committed = 0
    rows_read = 0

    try:
        while position < total:
            batch = feed.read(position, interval)
            if not batch:
                break
            rows_read += len(batch)
            with storage.begin() as transaction:
                for row in batch:
                    stored = stored_row(row)
                    transaction.put(table_of(row), stored["id"], stored)
                position += len(batch)
                transaction.set_meta(PROGRESS_KEY, {"position": position})
                transaction.commit()
                rows_committed += len(batch)
    except (SourceInterrupted, StorageFailure):
        return {
            "status": "interrupted",
            "rows_read": rows_read,
            "rows_committed": rows_committed,
            "resumed_from": resumed_from,
            "rejected": [],
        }

    return {
        "status": "completed",
        "rows_read": rows_read,
        "rows_committed": rows_committed,
        "resumed_from": resumed_from,
        "rejected": [],
    }
