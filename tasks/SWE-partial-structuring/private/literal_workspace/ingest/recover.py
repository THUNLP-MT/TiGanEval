"""Read what we can out of a provider payload instead of dropping the whole file.

Finishing the sketch as the email describes it: walk the columns, wrap each one
in a try/except, fall back to the schema's own value when a column will not
read, and hand back the record we managed to put together plus the names of the
columns that gave trouble, so support can chase the provider column by column.
The publisher wants the trouble list under `failed_fields`, the confirmed ones
under `structured_fields`, a flag, the problems, and a way to fold support's
later corrections in, so all of that is here too.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import MISSING, Record, StructureErrors, build, read_field


class Reading:
    """What one payload came back as."""

    def __init__(self, record, payload, value, bad_fields, errors):
        self.value = value
        self.failed_fields = frozenset(bad_fields)
        self.structured_fields = frozenset(
            spec.name for spec in record.fields if spec.name not in self.failed_fields
        )
        self.is_complete = not self.failed_fields
        self.errors = errors
        self._record = record
        self._payload = dict(payload)

    def refine(self, patch: Mapping[str, Any]) -> "Reading":
        """Read the payload again with support's correction applied over it."""

        return recover({**self._payload, **dict(patch)}, self._record)


def _fallback(spec: Any) -> Any:
    return None if spec.default is MISSING else spec.default


def recover(payload: Mapping[str, Any], record: Record) -> Reading:
    """Read one payload column by column, keeping whatever reads."""

    values: dict[str, Any] = {}
    bad_fields: list[str] = []
    problems: list[tuple[str, str]] = []
    for spec in record.fields:
        if spec.name not in payload:
            values[spec.name] = _fallback(spec)
            continue
        try:
            values[spec.name] = read_field(spec, payload[spec.name], f"$.{spec.name}")
        except StructureErrors as exc:
            bad_fields.append(spec.name)
            message = exc.problems[0][1] if exc.problems else "could not be read"
            problems.append((f"$.{spec.name}", message))
            values[spec.name] = _fallback(spec)
    return Reading(
        record,
        payload,
        build(record, values),
        bad_fields,
        StructureErrors(problems) if problems else None,
    )


__all__ = ("Reading", "recover")
