"""The nightly publisher: what one provider drop hands the ledger and support.

Two things about a reading matter downstream and neither of them is "did we
manage to build an object".

``structured_fields`` is what we tell the provider we hold as *their* value.
The ledger stores it as the row's confirmed columns, and the finance team
reconciles against those columns. Anything not in it is a column support has to
chase, so the ticket is built from ``failed_fields`` and from the lines
``describe_errors`` renders.

The daily file is a drop, not a query: once it is read it cannot be fetched
again. Support's corrections therefore arrive later, in pieces, and are folded
into the reading we already have through ``refine``.

The support console can echo columns from the open record beside the columns
on the ticket. Those echoed columns are context, not corrections: only a
column in ``failed_fields`` is one support is answering, so an already
confirmed provider value is not replaced by an echoed value.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import describe_errors
from .recover import recover
from .schema import SUBSCRIBER


class Ledger:
    """The billing table one night's drop is published into."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.withheld: list[dict[str, Any]] = []

    def write(self, record_id: str, value: Any, confirmed: Sequence[str]) -> None:
        columns = value.as_dict()
        lines = list(columns.get("lines") or ())
        self.rows.append(
            {
                "record_id": str(record_id),
                "columns": columns,
                "confirmed_columns": sorted(str(name) for name in confirmed),
                "null_columns": sorted(
                    name for name, held in columns.items() if held is None
                ),
                "published_line_count": len(lines),
                "invoice_pence": sum(
                    int(line["quantity"]) * int(line["unit_pence"]) for line in lines
                ),
            }
        )

    def hold(self, record_id: str, why: Sequence[str]) -> None:
        self.withheld.append({"record_id": str(record_id), "why": list(why)})


def publish_drop(drop: Sequence[Mapping[str, Any]], ledger: Ledger, record: Any = SUBSCRIBER):
    """Read every payload in one drop, publish what may be published, raise tickets."""

    readings: dict[str, Any] = {}
    tickets: list[dict[str, Any]] = []
    for entry in drop:
        record_id = str(entry["record_id"])
        reading = recover(dict(entry["payload"]), record)
        readings[record_id] = reading
        if reading.value is None:
            ledger.hold(record_id, describe_errors(reading.errors))
        else:
            ledger.write(record_id, reading.value, reading.structured_fields)
        lines = describe_errors(reading.errors)
        if lines or not reading.is_complete:
            tickets.append(
                {
                    "record_id": record_id,
                    "columns_to_chase": sorted(str(name) for name in reading.failed_fields),
                    "lines": list(lines),
                }
            )
    return {"readings": readings, "tickets": tickets}


def apply_correction(reading: Any, patch: Mapping[str, Any]) -> Any:
    """Fold one of support's partial corrections into a reading we already have."""

    return reading.refine(dict(patch))


__all__ = ("Ledger", "apply_correction", "publish_drop")
