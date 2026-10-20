"""Runtime contract for the catalogue bulk-import project.

The storage substrate, the source feed, and the invariant rules below are the
frozen part of the project. Everything is deterministic: durability is defined
by what a transaction commits, and cost is counted in transactions and rows
rather than wall clock time.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping, Sequence


TABLES: tuple[str, ...] = ("products", "variants")

REJECTION_REASONS: tuple[str, ...] = (
    "duplicate_product_id",
    "duplicate_product_sku",
    "empty_product_sku",
    "duplicate_variant_id",
    "missing_parent_product",
    "negative_price",
    "unknown_row_type",
)

REPORT_FIELDS: tuple[str, ...] = (
    "status",
    "rows_read",
    "rows_committed",
    "resumed_from",
    "rejected",
)
STATUS_VALUES: tuple[str, ...] = ("completed", "interrupted", "refused")
"""The three outcomes ``run_import`` may report to the scheduler.

``completed``
    The run reached the end of its export.
``interrupted``
    The run stopped early. :class:`SourceInterrupted` and :class:`StorageFailure`
    are the two ways that happens; both are raised out of the substrate and are
    the run's to catch. A run that lets one of them leave ``run_import`` returns
    no report at all, which the scheduler reads as a crashed job rather than a
    restartable one.
``refused``
    The run declined the job and left durable state exactly as it found it.
"""


class SourceInterrupted(RuntimeError):
    """Raised when the source feed dies part way through the import."""


class StorageFailure(RuntimeError):
    """Raised when a commit is lost before it reaches durable storage."""


class TransactionError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


class Meter:
    """Records the source and transaction activity of one process."""

    def __init__(self) -> None:
        self.rows_read = 0
        self.commit_marks: list[dict[str, int]] = []

    def reset(self) -> None:
        self.rows_read = 0
        self.commit_marks.clear()


METER = Meter()


def admit(state: Mapping[str, Mapping[str, Any]], row: Mapping[str, Any]) -> str | None:
    """Return why this row cannot join the committed state, or None if it can.

    A row is judged against the rows already admitted before it in source order.
    """

    products = dict(state.get("products", {}))
    variants = dict(state.get("variants", {}))
    kind = str(row.get("op", ""))
    if kind == "product":
        identifier = str(row.get("id"))
        sku = str(row.get("sku", ""))
        existing = products.get(identifier)
        if existing is not None:
            # Re-stating a row exactly as stored is a no-op, not a conflict.
            return None if dict(existing) == stored_row(row) else "duplicate_product_id"
        if not sku.strip():
            return "empty_product_sku"
        if any(str(other.get("sku")) == sku for other in products.values()):
            return "duplicate_product_sku"
        return None
    if kind == "variant":
        identifier = str(row.get("id"))
        existing = variants.get(identifier)
        if existing is not None:
            return None if dict(existing) == stored_row(row) else "duplicate_variant_id"
        if str(row.get("product_id")) not in products:
            return "missing_parent_product"
        if int(row.get("price_cents", 0)) < 0:
            return "negative_price"
        return None
    return "unknown_row_type"


def stored_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the persisted shape of an admissible source row."""

    kind = str(row.get("op", ""))
    if kind == "product":
        return {
            "id": str(row.get("id")),
            "sku": str(row.get("sku", "")),
            "name": str(row.get("name", "")),
        }
    return {
        "id": str(row.get("id")),
        "product_id": str(row.get("product_id")),
        "price_cents": int(row.get("price_cents", 0)),
        "label": str(row.get("label", "")),
    }


def table_of(row: Mapping[str, Any]) -> str:
    return "products" if str(row.get("op", "")) == "product" else "variants"


def invariant_violations(tables: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    """Return the invariant failures of a committed database state."""

    products = dict(tables.get("products", {}))
    variants = dict(tables.get("variants", {}))
    problems: list[str] = []
    skus: dict[str, str] = {}
    for key, row in sorted(products.items()):
        sku = str(dict(row).get("sku", ""))
        if not sku.strip():
            problems.append(f"empty_product_sku:{key}")
        if sku in skus:
            problems.append(f"duplicate_product_sku:{sku}")
        else:
            skus[sku] = key
    for key, row in sorted(variants.items()):
        data = dict(row)
        if str(data.get("product_id")) not in products:
            problems.append(f"missing_parent_product:{key}")
        if int(data.get("price_cents", 0)) < 0:
            problems.append(f"negative_price:{key}")
    return tuple(problems)


class SourceFeed:
    """A restartable, position-addressed view of the import source."""

    def __init__(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        name: str = "catalogue.jsonl",
        fail_after: int | None = None,
        available_from: int = 0,
    ):
        self._rows = [dict(row) for row in rows]
        self.name = str(name)
        self.fail_after = None if fail_after is None else int(fail_after)
        #: The upstream export only retains rows from this position onward.
        self.available_from = max(0, int(available_from))
        self.rows_read = 0
        self.max_position = self.available_from

    def total_rows(self) -> int:
        return len(self._rows)

    def digest(self) -> str:
        return digest_of({"name": self.name, "rows": self._rows})

    def read(self, start: int, limit: int) -> tuple[dict[str, Any], ...]:
        """Return up to ``limit`` rows beginning at source position ``start``."""

        begin = max(0, int(start))
        count = int(limit)
        if count < 1:
            raise ValueError("read limit must be at least 1")
        if begin < self.available_from:
            raise SourceInterrupted(
                f"source feed {self.name} no longer retains rows before "
                f"position {self.available_from}"
            )
        end = min(len(self._rows), begin + count)
        if self.fail_after is not None and end > self.fail_after:
            end = max(begin, self.fail_after)
            delivered = tuple(deepcopy(row) for row in self._rows[begin:end])
            self.rows_read += len(delivered)
            self.max_position = max(self.max_position, end)
            METER.rows_read += len(delivered)
            raise SourceInterrupted(
                f"source feed {self.name} stopped after row {self.fail_after}"
            )
        delivered = tuple(deepcopy(row) for row in self._rows[begin:end])
        self.rows_read += len(delivered)
        self.max_position = max(self.max_position, end)
        METER.rows_read += len(delivered)
        return delivered


@dataclass(frozen=True, slots=True)
class ImportConfig:
    """The published operating envelope of one import run."""

    checkpoint_interval: int = 25
    source_name: str = "catalogue.jsonl"
    source_digest: str = ""
    total_rows: int = 0
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ImportConfig":
        return cls(
            checkpoint_interval=int(value.get("checkpoint_interval", 25)),
            source_name=str(value.get("source_name", "catalogue.jsonl")),
            source_digest=str(value.get("source_digest", "")),
            total_rows=int(value.get("total_rows", 0)),
            extra=dict(value.get("extra", {})),
        )


class Transaction:
    """One atomic unit of durable change."""

    def __init__(self, storage: "Storage"):
        self._storage = storage
        self._tables = {table: {} for table in TABLES}
        self._removed = {table: set() for table in TABLES}
        self._meta: dict[str, Any] = {}
        self._meta_removed: set[str] = set()
        self._writes = 0
        self.open = True

    def _require_open(self) -> None:
        if not self.open:
            raise TransactionError("transaction is already finished")

    def get(self, table: str, key: str) -> Mapping[str, Any] | None:
        self._require_open()
        name, identifier = self._address(table, key)
        if identifier in self._removed[name]:
            return None
        staged = self._tables[name].get(identifier)
        if staged is not None:
            return deepcopy(staged)
        row = self._storage.committed["tables"][name].get(identifier)
        return deepcopy(row) if row is not None else None

    def scan(self, table: str) -> Mapping[str, Mapping[str, Any]]:
        self._require_open()
        name = self._table(table)
        merged = dict(self._storage.committed["tables"][name])
        merged.update(self._tables[name])
        for identifier in self._removed[name]:
            merged.pop(identifier, None)
        return deepcopy(merged)

    def put(self, table: str, key: str, row: Mapping[str, Any]) -> None:
        self._require_open()
        name, identifier = self._address(table, key)
        self._tables[name][identifier] = deepcopy(dict(row))
        self._removed[name].discard(identifier)
        self._writes += 1

    def delete(self, table: str, key: str) -> None:
        self._require_open()
        name, identifier = self._address(table, key)
        self._tables[name].pop(identifier, None)
        self._removed[name].add(identifier)

    def get_meta(self, key: str) -> Any:
        self._require_open()
        if str(key) in self._meta_removed:
            return None
        if str(key) in self._meta:
            return deepcopy(self._meta[str(key)])
        return deepcopy(self._storage.committed["meta"].get(str(key)))

    def set_meta(self, key: str, value: Any) -> None:
        self._require_open()
        self._meta[str(key)] = deepcopy(value)
        self._meta_removed.discard(str(key))

    def delete_meta(self, key: str) -> None:
        self._require_open()
        self._meta.pop(str(key), None)
        self._meta_removed.add(str(key))

    def commit(self) -> None:
        self._require_open()
        self.open = False
        self._storage._commit(self)

    def rollback(self) -> None:
        self._require_open()
        self.open = False
        self._storage._rollback(self)

    def __enter__(self) -> "Transaction":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.open:
            self.rollback()

    @staticmethod
    def _table(table: str) -> str:
        name = str(table)
        if name not in TABLES:
            raise TransactionError(f"unknown table: {name}")
        return name

    def _address(self, table: str, key: str) -> tuple[str, str]:
        identifier = str(key)
        if not identifier:
            raise TransactionError("row keys must be non-empty")
        return self._table(table), identifier


class Storage:
    """Durable storage. Only committed transactions survive a restart."""

    def __init__(
        self,
        committed: Mapping[str, Any] | None = None,
        *,
        fail_on_commit: int | None = None,
    ):
        source = dict(committed or {})
        self.committed: dict[str, Any] = {
            "tables": {
                table: {
                    str(key): deepcopy(dict(row))
                    for key, row in dict(dict(source.get("tables", {})).get(table, {})).items()
                }
                for table in TABLES
            },
            "meta": {str(key): deepcopy(value) for key, value in dict(source.get("meta", {})).items()},
        }
        self.fail_on_commit = None if fail_on_commit is None else int(fail_on_commit)
        self.transactions = 0
        self.commits = 0
        self.rollbacks = 0
        self.rows_written = 0
        self.max_rows_per_transaction = 0
        self.commit_snapshots: list[dict[str, Any]] = []
        self._open: Transaction | None = None

    def begin(self) -> Transaction:
        if self._open is not None and self._open.open:
            raise TransactionError("a transaction is already open")
        self.transactions += 1
        self._open = Transaction(self)
        return self._open

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.committed)

    def read_meta(self, key: str) -> Any:
        """Read committed bookkeeping without opening a transaction."""

        return deepcopy(self.committed["meta"].get(str(key)))

    def read_table(self, table: str) -> dict[str, Any]:
        """Read a committed table without opening a transaction."""

        name = str(table)
        if name not in TABLES:
            raise TransactionError(f"unknown table: {name}")
        return deepcopy(self.committed["tables"][name])

    def _rollback(self, transaction: Transaction) -> None:
        self.rollbacks += 1
        if self._open is transaction:
            self._open = None

    def _commit(self, transaction: Transaction) -> None:
        if self._open is transaction:
            self._open = None
        self.commits += 1
        if self.fail_on_commit is not None and self.commits == self.fail_on_commit:
            raise StorageFailure(f"commit {self.commits} was lost before reaching storage")
        for table in TABLES:
            for identifier in transaction._removed[table]:
                self.committed["tables"][table].pop(identifier, None)
            self.committed["tables"][table].update(
                {key: deepcopy(row) for key, row in transaction._tables[table].items()}
            )
        for key in transaction._meta_removed:
            self.committed["meta"].pop(key, None)
        self.committed["meta"].update(
            {key: deepcopy(value) for key, value in transaction._meta.items()}
        )
        self.rows_written += transaction._writes
        self.max_rows_per_transaction = max(self.max_rows_per_transaction, transaction._writes)
        METER.commit_marks.append(
            {"rows_read": METER.rows_read, "rows_in_transaction": transaction._writes}
        )
        self.commit_snapshots.append(self.snapshot())


def require_report(report: Any) -> Mapping[str, Any]:
    """Validate the shape of an import report and return it unchanged.

    Each entry of ``rejected`` describes one source row the run would not take:
    ``index`` is that row's position in the export, counted from 0, and
    ``reason`` is what ``admit`` returned for that row.
    """

    if not isinstance(report, Mapping):
        raise TypeError("run_import must return a mapping")
    missing = [name for name in REPORT_FIELDS if name not in report]
    if missing:
        raise ValueError(f"import report is missing fields: {', '.join(missing)}")
    if str(report["status"]) not in STATUS_VALUES:
        raise ValueError(f"import report status must be one of {STATUS_VALUES}")
    rejected = report["rejected"]
    if not isinstance(rejected, Sequence) or isinstance(rejected, (str, bytes)):
        raise TypeError("import report rejected must be a sequence")
    for entry in rejected:
        if not isinstance(entry, Mapping) or "index" not in entry or "reason" not in entry:
            raise ValueError("each rejected entry needs index and reason")
    return report


__all__ = (
    "ImportConfig",
    "METER",
    "REJECTION_REASONS",
    "REPORT_FIELDS",
    "STATUS_VALUES",
    "SourceFeed",
    "SourceInterrupted",
    "Storage",
    "StorageFailure",
    "TABLES",
    "Transaction",
    "TransactionError",
    "admit",
    "canonical_json",
    "digest_of",
    "invariant_violations",
    "require_report",
    "stored_row",
    "table_of",
)
