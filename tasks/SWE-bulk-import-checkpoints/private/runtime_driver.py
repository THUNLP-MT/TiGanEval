'Sandboxed candidate runner for the catalogue bulk-import simulator.'

from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
import sys
from typing import Any, Mapping, Sequence


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def _stable_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    'Return keys whose presence or value differs between two mappings.'

    return sorted(
        str(key)
        for key in set(before).union(after)
        if key not in before or key not in after or before[key] != after[key]
    )


def _state_difference(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    tables: Sequence[str],
) -> dict[str, Any]:
    'Measure durable changes not produced by an audited transaction.'

    expected_tables = dict(expected.get("tables", {}))
    actual_tables = dict(actual.get("tables", {}))
    changed_rows: list[str] = []
    for table in tables:
        before_rows = dict(expected_tables.get(table, {}))
        after_rows = dict(actual_tables.get(table, {}))
        changed_rows.extend(
            f"{table}:{key}" for key in _changed_keys(before_rows, after_rows)
        )
    changed_meta = _changed_keys(
        dict(expected.get("meta", {})), dict(actual.get("meta", {}))
    )
    return {
        "durable_entries_changed_without_transaction": (
            len(changed_rows) + len(changed_meta)
        ),
        "catalogue_rows_changed_without_transaction": len(changed_rows),
        "metadata_entries_changed_without_transaction": len(changed_meta),
        "sample_entries_changed_without_transaction": (
            changed_rows[:4] + [f"meta:{key}" for key in changed_meta[:4]]
        )[:6],
    }


def _require_report(
    report: Any,
    *,
    report_fields: Sequence[str],
    status_values: Sequence[str],
) -> Mapping[str, Any]:
    'Validate a candidate report without consulting its mutable module.'

    if not isinstance(report, Mapping):
        raise TypeError("run_import must return a mapping")
    missing = [name for name in report_fields if name not in report]
    if missing:
        raise ValueError(f"import report is missing fields: {', '.join(missing)}")
    if str(report["status"]) not in status_values:
        raise ValueError(f"import report status must be one of {tuple(status_values)}")
    rejected = report["rejected"]
    if not isinstance(rejected, Sequence) or isinstance(rejected, (str, bytes)):
        raise TypeError("import report rejected must be a sequence")
    for entry in rejected:
        if not isinstance(entry, Mapping) or "index" not in entry or "reason" not in entry:
            raise ValueError("each rejected entry needs index and reason")
    return report


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from loader import protocol


    tables = tuple(protocol.TABLES)
    report_fields = tuple(protocol.REPORT_FIELDS)
    status_values = tuple(protocol.STATUS_VALUES)
    invariant_violations = protocol.invariant_violations
    meter = protocol.METER
    meter_reset = type(meter).reset
    storage_type = protocol.Storage
    transaction_type = protocol.Transaction
    transaction_error = protocol.TransactionError
    storage_failure = protocol.StorageFailure
    feed_type = protocol.SourceFeed
    feed_read = protocol.SourceFeed.read

    sources = {
        str(name): [dict(row) for row in rows]
        for name, rows in dict(payload["sources"]).items()
    }
    interval = int(payload.get("checkpoint_interval", 25))
    initial_state = dict(payload.get("initial_state", {}))
    initial_tables = dict(initial_state.get("tables", {}))
    committed: dict[str, Any] = {
        "tables": {
            table: {
                str(key): deepcopy(dict(row))
                for key, row in dict(initial_tables.get(table, {})).items()
            }
            for table in tables
        },
        "meta": {
            str(key): deepcopy(value)
            for key, value in dict(initial_state.get("meta", {})).items()
        },
    }
    high_water: dict[str, int] = {name: 0 for name in sources}
    night_metadata_baselines: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            if str(event.get("type", "")) != "import":
                records.append({"type": "driver_error", "index": index, "error": "unknown event"})
                continue
            source_name = str(event.get("source", "primary"))
            rows = sources[source_name]
            retained_from = max(0, high_water[source_name] - interval)
            raw_fail_after = event.get("fail_after")
            raw_fail_commit = event.get("fail_on_commit")
            raw_fail_cleanup = bool(event.get("fail_on_cleanup", False))
            export_name = event.get("export_name") or f"{source_name}-export.jsonl"

            night = str(event.get("night", "load-night"))
            night_metadata_baselines.setdefault(
                night, deepcopy(dict(committed.get("meta", {})))
            )
            audited_committed = deepcopy(committed)

            feed_audit: dict[str, Any] = {"rows_read": 0, "max_position": retained_from}
            storage_audit: dict[str, Any] = {
                "transactions": 0,
                "commits": 0,
                "rollbacks": 0,
                "rows_written": 0,
                "max_rows_per_transaction": 0,
                "commit_marks": [],
                "commit_snapshots": [],
            }

            class AuditedFeed(feed_type):
                def read(self, start: int, limit: int) -> tuple[dict[str, Any], ...]:
                    begin = max(0, int(start))
                    count = int(limit)
                    if count < 1 or begin < self.available_from:
                        return feed_read(self, start, limit)
                    end = min(len(rows), begin + max(0, count))
                    delivered_end = end
                    if self.fail_after is not None and end > self.fail_after:
                        delivered_end = max(begin, int(self.fail_after))
                    feed_audit["rows_read"] += max(0, delivered_end - begin)
                    feed_audit["max_position"] = max(
                        int(feed_audit["max_position"]), delivered_end
                    )
                    return feed_read(self, start, limit)

            class AuditedStorage(storage_type):
                def begin(self):
                    if self._open is not None and self._open.open:
                        raise transaction_error("a transaction is already open")
                    self.transactions += 1
                    storage_audit["transactions"] += 1
                    self._open = transaction_type(self)
                    return self._open

                def _rollback(self, transaction):
                    self.rollbacks += 1
                    storage_audit["rollbacks"] += 1
                    if self._open is transaction:
                        self._open = None

                def _commit(self, transaction):
                    if self._open is transaction:
                        self._open = None
                    self.commits += 1
                    storage_audit["commits"] += 1
                    if (
                        self.fail_on_commit is not None
                        and storage_audit["commits"] == self.fail_on_commit
                    ):
                        raise storage_failure(
                            f"commit {storage_audit['commits']} was lost before reaching storage"
                        )
                    if raw_fail_cleanup and transaction._meta_removed:
                        raise storage_failure(
                            "completion cleanup commit was lost before reaching storage"
                        )


                    for target in (self.committed, audited_committed):
                        for table in tables:
                            for identifier in transaction._removed[table]:
                                target["tables"][table].pop(identifier, None)
                            target["tables"][table].update(
                                {
                                    key: deepcopy(row)
                                    for key, row in transaction._tables[table].items()
                                }
                            )
                        for key in transaction._meta_removed:
                            target["meta"].pop(key, None)
                        target["meta"].update(
                            {
                                key: deepcopy(value)
                                for key, value in transaction._meta.items()
                            }
                        )
                    writes = int(transaction._writes)
                    self.rows_written += writes
                    self.max_rows_per_transaction = max(
                        self.max_rows_per_transaction, writes
                    )
                    storage_audit["rows_written"] += writes
                    storage_audit["max_rows_per_transaction"] = max(
                        int(storage_audit["max_rows_per_transaction"]), writes
                    )
                    mark = {
                        "rows_read": int(feed_audit["rows_read"]),
                        "rows_in_transaction": writes,
                    }
                    meter.commit_marks.append(
                        {
                            "rows_read": int(meter.rows_read),
                            "rows_in_transaction": writes,
                        }
                    )
                    self.commit_snapshots.append(deepcopy(self.committed))
                    storage_audit["commit_marks"].append(mark)
                    storage_audit["commit_snapshots"].append(deepcopy(self.committed))

            state_before = deepcopy(committed)
            feed = AuditedFeed(
                rows,
                name=str(export_name),
                fail_after=None if raw_fail_after is None else int(raw_fail_after),
                available_from=retained_from,
            )
            storage = AuditedStorage(
                committed,
                fail_on_commit=None if raw_fail_commit is None else int(raw_fail_commit),
            )
            config = protocol.ImportConfig(
                checkpoint_interval=interval,
                source_name=feed.name,
                source_digest=_stable_digest({"name": feed.name, "rows": rows}),
                total_rows=len(rows),
            )
            module = importlib.reload(importlib.import_module("loader.importer"))
            meter_reset(meter)
            record: dict[str, Any] = {
                "type": "import",
                "index": index,
                "label": str(event.get("label", f"run-{index}")),
                "night": night,
                "source": source_name,
                "export_name": feed.name,
                "retained_from": retained_from,
                "fail_after": raw_fail_after,
                "fail_on_commit": raw_fail_commit,
                "fail_on_cleanup": raw_fail_cleanup,
                "total_rows": len(rows),
            }
            try:
                report = module.run_import(storage, feed, config)
                _require_report(
                    report,
                    report_fields=report_fields,
                    status_values=status_values,
                )
                record["ok"] = True
                record["report"] = {
                    "status": str(report["status"]),
                    "rows_read": report.get("rows_read"),
                    "rows_committed": report.get("rows_committed"),
                    "resumed_from": report.get("resumed_from"),
                    "rejected": [
                        {"index": entry.get("index"), "reason": entry.get("reason")}
                        for entry in report["rejected"]
                    ],
                }
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                record["report"] = None
            committed = deepcopy(storage.committed)
            storage_audit.update(
                _state_difference(audited_committed, committed, tables=tables)
            )
            if (
                raw_fail_after is None
                and raw_fail_commit is None
                and not raw_fail_cleanup
            ):

                high_water[source_name] = 0
            else:
                high_water[source_name] = max(
                    high_water[source_name], int(feed_audit["max_position"])
                )
            record["storage"] = {
                "transactions": storage_audit["transactions"],
                "commits": storage_audit["commits"],
                "rollbacks": storage_audit["rollbacks"],
                "rows_written": storage_audit["rows_written"],
                "max_rows_per_transaction": storage_audit["max_rows_per_transaction"],
                "durable_entries_changed_without_transaction": storage_audit[
                    "durable_entries_changed_without_transaction"
                ],
                "catalogue_rows_changed_without_transaction": storage_audit[
                    "catalogue_rows_changed_without_transaction"
                ],
                "metadata_entries_changed_without_transaction": storage_audit[
                    "metadata_entries_changed_without_transaction"
                ],
                "sample_entries_changed_without_transaction": storage_audit[
                    "sample_entries_changed_without_transaction"
                ],
            }
            record["meter"] = {
                "rows_read": feed_audit["rows_read"],
                "first_commit_mark": (
                    dict(storage_audit["commit_marks"][0])
                    if storage_audit["commit_marks"]
                    else None
                ),
                "commit_count": len(storage_audit["commit_marks"]),
            }
            record["committed_invariant_violations"] = [
                {
                    "commit": position,
                    "violations": list(
                        invariant_violations(snapshot.get("tables", {}))
                    )[:8],
                }
                for position, snapshot in enumerate(
                    storage_audit["commit_snapshots"], start=1
                )
                if invariant_violations(snapshot.get("tables", {}))
            ]
            record["database"] = committed["tables"]
            record["meta_keys"] = sorted(committed["meta"])
            if record["ok"] and record["report"]["status"] == "completed":
                baseline_meta = night_metadata_baselines[night]
                current_meta = dict(committed.get("meta", {}))
                handoff_changes = _changed_keys(
                    baseline_meta, current_meta
                )
                record["night_handoff"] = {
                    "status": "closed" if not handoff_changes else "held_for_review",
                    "metadata_changes_since_night_started": handoff_changes[:6],
                    "metadata_added_since_night_started": sorted(
                        set(current_meta).difference(baseline_meta)
                    )[:6],
                    "metadata_removed_since_night_started": sorted(
                        set(baseline_meta).difference(current_meta)
                    )[:6],
                    "metadata_changed_since_night_started": sorted(
                        key
                        for key in set(baseline_meta).intersection(current_meta)
                        if baseline_meta[key] != current_meta[key]
                    )[:6],
                }
            else:
                record["night_handoff"] = None
            record["database_digest"] = _stable_digest(committed["tables"])
            record["durable_state_before"] = state_before
            record["durable_state_after"] = deepcopy(committed)
            meter_reset(meter)
            records.append(record)

    return {
        "ok": True,
        "records": records,
        "candidate_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload)
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
