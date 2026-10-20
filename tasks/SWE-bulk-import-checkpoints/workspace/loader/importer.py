"""Bulk catalogue import.

The current loader reads the exported catalogue and writes it into the
warehouse in one transaction, which is what the staging run used.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    ImportConfig,
    SourceFeed,
    Storage,
    stored_row,
    table_of,
)


def run_import(
    storage: Storage,
    feed: SourceFeed,
    config: ImportConfig,
) -> Mapping[str, Any]:
    """Load the whole export into the warehouse."""

    rows = feed.read(0, max(1, feed.total_rows()))
    with storage.begin() as transaction:
        for row in rows:
            stored = stored_row(row)
            transaction.put(table_of(row), stored["id"], stored)
        transaction.commit()
    return {
        "status": "completed",
        "rows_read": len(rows),
        "rows_committed": len(rows),
        "resumed_from": 0,
        "rejected": [],
    }
