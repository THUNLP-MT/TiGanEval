"""Bulk catalogue import with checkpointed, resumable, validated batches."""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    ImportConfig,
    SourceFeed,
    SourceInterrupted,
    Storage,
    StorageFailure,
    admit,
    stored_row,
    table_of,
)


RESUME_KEY = "catalogue_import_progress"


def _report(
    status: str,
    *,
    rows_read: int,
    rows_committed: int,
    resumed_from: int,
    rejected: list[dict[str, Any]],
    detail: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": status,
        "rows_read": int(rows_read),
        "rows_committed": int(rows_committed),
        "resumed_from": int(resumed_from),
        "rejected": [dict(entry) for entry in rejected],
    }
    if detail is not None:
        report["detail"] = detail
    return report


def _load_progress(storage: Storage, config: ImportConfig) -> tuple[int, str | None]:
    """Return the durable resume position and any source-identity refusal."""

    progress = storage.read_meta(RESUME_KEY)
    if not isinstance(progress, Mapping):
        return 0, None
    if str(progress.get("source_digest", "")) != str(config.source_digest):
        return 0, "recorded progress belongs to a different source export"
    position = int(progress.get("position", 0))
    return position, None


def run_import(
    storage: Storage,
    feed: SourceFeed,
    config: ImportConfig,
) -> Mapping[str, Any]:
    """Load the export in checkpointed batches, resuming durable progress."""

    interval = max(1, int(config.checkpoint_interval))
    resumed_from, refusal = _load_progress(storage, config)
    if refusal is not None:
        return _report(
            "refused",
            rows_read=0,
            rows_committed=0,
            resumed_from=0,
            rejected=[],
            detail=refusal,
        )

    admitted = {
        "products": storage.read_table("products"),
        "variants": storage.read_table("variants"),
    }
    total = int(config.total_rows) or feed.total_rows()
    position = resumed_from
    rows_committed = 0
    # A report contains only rejections this run made durable. Earlier runs of
    # the same night already reported the batches they committed, while a batch
    # whose commit was lost will be read and reported by its restart.
    rejected: list[dict[str, Any]] = []

    try:
        while position < total:
            batch = feed.read(position, interval)
            if not batch:
                break
            with storage.begin() as transaction:
                written = 0
                batch_rejected: list[dict[str, Any]] = []
                for offset, row in enumerate(batch):
                    reason = admit(admitted, row)
                    if reason is not None:
                        batch_rejected.append(
                            {"index": position + offset, "reason": reason}
                        )
                        continue
                    table = table_of(row)
                    stored = stored_row(row)
                    if transaction.get(table, stored["id"]) != stored:
                        transaction.put(table, stored["id"], stored)
                        written += 1
                    admitted[table][stored["id"]] = stored
                position += len(batch)
                transaction.set_meta(
                    RESUME_KEY,
                    {
                        "source_digest": str(config.source_digest),
                        "position": position,
                    },
                )
                transaction.commit()
                rows_committed += written
                rejected.extend(batch_rejected)

        with storage.begin() as transaction:
            transaction.delete_meta(RESUME_KEY)
            transaction.commit()
    except (SourceInterrupted, StorageFailure) as exc:
        return _report(
            "interrupted",
            rows_read=feed.rows_read,
            rows_committed=rows_committed,
            resumed_from=resumed_from,
            rejected=rejected,
            detail=str(exc)[:200],
        )

    return _report(
        "completed",
        rows_read=feed.rows_read,
        rows_committed=rows_committed,
        resumed_from=resumed_from,
        rejected=rejected,
    )
