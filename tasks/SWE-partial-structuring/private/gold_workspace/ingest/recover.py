"""Read a provider payload column by column, keeping exactly what the file gave us.

A column is the provider's only when the file carried it and it read cleanly.
Everything else is a gap: it falls back to the value declared in the contract,
and it is named as a gap so support can chase the column. A nested block of
which part still reads keeps its own partly-read value and stays a gap in its
parent, because part of what we publish under it is ours rather than theirs.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    MISSING,
    MISSING_FIELD_MESSAGE,
    Record,
    StructureErrors,
    build,
    field_names,
    field_problems,
    field_value,
    init_fields,
    record_problems,
)


class Reading:
    """One payload as we read it: what we can publish, and what we cannot."""

    __slots__ = (
        "value",
        "is_complete",
        "structured_fields",
        "failed_fields",
        "errors",
        "_record",
        "_raw",
    )

    def __init__(self, record, raw, value, structured, failed, errors):
        self.value = value
        self.structured_fields = frozenset(structured)
        self.failed_fields = frozenset(failed)
        self.is_complete = not self.failed_fields
        self.errors = errors
        self._record = record
        self._raw = raw

    def refine(self, patch: Mapping[str, Any]) -> "Reading":
        """Fold one of support's corrections into this reading, leaving it alone."""

        raw = dict(self._raw) if isinstance(self._raw, Mapping) else {}
        for name, value in dict(patch).items():
            if name in self.failed_fields:
                raw[name] = value
        return recover(raw, self._record)


def recover(payload: Mapping[str, Any], record: Record) -> Reading:
    """Read one payload, publishing it only when every gap has a fallback."""

    structured: list[str] = []
    failed: list[str] = []
    values: dict[str, Any] = {}
    producible = True
    if not isinstance(payload, Mapping):
        return Reading(
            record,
            payload,
            None,
            (),
            field_names(record),
            StructureErrors(record_problems(payload, record, "$")),
        )
    for spec in init_fields(record):
        if spec.name in payload:
            raw = payload[spec.name]
            if not field_problems(spec, raw, f"$.{spec.name}"):
                structured.append(spec.name)
                values[spec.name] = field_value(spec, raw)
                continue
            failed.append(spec.name)
            if spec.record is not None and isinstance(raw, Mapping):
                child = recover(raw, spec.record)
                if child.value is not None:
                    values[spec.name] = child.value
                    continue
        else:
            failed.append(spec.name)
        if spec.default is MISSING:
            producible = False
        else:
            values[spec.name] = spec.default
    problems = record_problems(payload, record, "$")
    return Reading(
        record,
        dict(payload),
        build(record, values) if producible else None,
        structured,
        failed,
        StructureErrors(problems) if problems else None,
    )


__all__ = ("MISSING_FIELD_MESSAGE", "Reading", "recover")
