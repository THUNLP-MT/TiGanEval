"""Read what we can out of a provider payload instead of dropping the whole file.

Sketch so far: walk the columns, wrap each one in a try/except, fall back to the
schema's own value when a column will not read, and hand back the record we
managed to put together plus the names of the columns that gave trouble.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import MISSING, Record, build, read_field


class Recovered:
    """What one payload came back as."""

    def __init__(self, value: Any, bad_fields: Any):
        self.value = value
        self.bad_fields = tuple(bad_fields)


def _fallback(spec: Any) -> Any:
    return None if spec.default is MISSING else spec.default


def recover(payload: Mapping[str, Any], record: Record) -> Recovered:
    """Read one payload column by column, keeping whatever reads."""

    values: dict[str, Any] = {}
    bad_fields: list[str] = []
    for spec in record.fields:
        if spec.name not in payload:
            continue
        try:
            values[spec.name] = read_field(spec, payload[spec.name], f"$.{spec.name}")
        except Exception:
            bad_fields.append(spec.name)
            values[spec.name] = _fallback(spec)
    for spec in record.fields:
        values.setdefault(spec.name, _fallback(spec))
    return Recovered(build(record, values), bad_fields)


__all__ = ("Recovered", "recover")
