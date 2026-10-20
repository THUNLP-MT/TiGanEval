"""Runtime contract for the provider ingest.

This module is the shape the provider's file is read against and the shape the
nightly publisher and the support tooling are built on, so it is fixed here:
the column model, the strict reading the archived incidents were produced by,
and the rendering of a reading's problems into the lines support works from.

The strict reading is deliberately all-or-nothing. :func:`structure` collects
every problem a payload has and raises before it assembles anything, so a
reading that fails leaves no half-built object anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Mapping, Sequence


class _Missing:
    """The absence of a fallback value, distinct from ``None``."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()

MISSING_FIELD_MESSAGE = "required field is missing"
UNKNOWN_KEY_MESSAGE = "unknown key"
NOT_AN_OBJECT_MESSAGE = "expected an object"
NOT_A_LIST_MESSAGE = "expected a list"

_DAY = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
_POSTCODE = re.compile(r"\A[A-Z]{1,2}\d{1,2} \d[A-Z]{2}\Z")
_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class StructureErrors(ValueError):
    """Every problem one reading found, each carrying the path it happened at."""

    def __init__(self, problems: Sequence[tuple[str, str]]):
        self.problems: tuple[tuple[str, str], ...] = tuple(
            (str(path), str(message)) for path, message in problems
        )
        super().__init__(f"{len(self.problems)} column(s) could not be read")


def describe_errors(errors: Any) -> tuple[str, ...]:
    """Render a reading's problems as the support lines, in canonical order."""

    if errors is None:
        return ()
    if not isinstance(errors, StructureErrors):
        raise TypeError("describe_errors takes a StructureErrors or None")
    return tuple(sorted(f"{message} @ {path}" for path, message in errors.problems))


def show(value: Any) -> str:
    """How a rejected raw value is written into a support line."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    return type(value).__name__


def parse_scalar(kind: str, raw: Any) -> Any:
    """Read one raw value as ``kind``; raise ValueError with the support text."""

    if kind == "text":
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    elif kind == "count":
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            return raw
    elif kind == "pence":
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            return raw
    elif kind == "day":
        match = _DAY.match(raw) if isinstance(raw, str) else None
        if match is not None:
            year, month, day = (int(part) for part in match.groups())
            if 1 <= month <= 12 and 1 <= day <= _DAYS_IN_MONTH[month - 1]:
                return f"{year:04d}-{month:02d}-{day:02d}"
    elif kind == "postcode":
        if isinstance(raw, str) and _POSTCODE.match(raw.strip().upper()):
            return raw.strip().upper()
    else:
        raise ValueError(f"unknown column kind: {kind}")
    raise ValueError(f"expected {kind}, got {show(raw)}")


@dataclass(frozen=True)
class Field:
    """One column of a record type."""

    name: str
    scalar: str = "text"
    record: "Record | None" = None
    element: "Record | None" = None
    default: Any = MISSING
    init: bool = True
    derive: Callable[[Mapping[str, Any]], Any] | None = None

    @property
    def kind(self) -> str:
        if self.record is not None:
            return "record"
        if self.element is not None:
            return "list"
        return "scalar"


@dataclass(frozen=True)
class Record:
    """A record type: its columns, and whether the file may carry others."""

    name: str
    fields: tuple[Field, ...]
    closed: bool = True

    def field(self, name: str) -> Field:
        for spec in self.fields:
            if spec.name == str(name):
                return spec
        raise KeyError(f"{self.name} has no column {name!r}")


def init_fields(record: Record) -> tuple[Field, ...]:
    """The columns the file supplies, in declaration order."""

    return tuple(spec for spec in record.fields if spec.init)


def field_names(record: Record) -> tuple[str, ...]:
    """The names of the columns the file supplies."""

    return tuple(spec.name for spec in init_fields(record))


def derived_names(record: Record) -> tuple[str, ...]:
    """The names of the columns the ingest computes for itself."""

    return tuple(spec.name for spec in record.fields if not spec.init)


class Row:
    """One assembled record."""

    __slots__ = ("record_name", "_values")

    def __init__(self, record_name: str, values: Mapping[str, Any]):
        self.record_name = str(record_name)
        self._values = dict(values)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__getattribute__("_values")[name]
        except KeyError:
            raise AttributeError(f"{self.record_name} has no column {name!r}") from None

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Row):
            return NotImplemented
        return self.record_name == other.record_name and self._values == other._values

    def __repr__(self) -> str:
        return f"{self.record_name}({self.as_dict()!r})"

    def as_dict(self) -> dict[str, Any]:
        """The record as plain data, nested rows and lists included."""

        return {name: _plain(value) for name, value in self._values.items()}


def _plain(value: Any) -> Any:
    if isinstance(value, Row):
        return value.as_dict()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, _Missing):
        return None
    return value


def build(record: Record, values: Mapping[str, Any]) -> Row:
    """Assemble a record from one value per supplied column."""

    resolved: dict[str, Any] = {}
    for spec in init_fields(record):
        if spec.name not in values:
            raise KeyError(f"{record.name}.{spec.name} has no value")
        resolved[spec.name] = values[spec.name]
    for spec in record.fields:
        if spec.init:
            continue
        resolved[spec.name] = spec.derive(dict(resolved)) if spec.derive else None
    return Row(record.name, resolved)


def field_problems(spec: Field, raw: Any, path: str) -> tuple[tuple[str, str], ...]:
    """Every problem the strict reading of one column's raw value has."""

    if spec.kind == "record":
        return record_problems(raw, spec.record, path)
    if spec.kind == "list":
        if not isinstance(raw, (list, tuple)) or isinstance(raw, (str, bytes)):
            return ((path, NOT_A_LIST_MESSAGE),)
        problems: list[tuple[str, str]] = []
        for index, item in enumerate(raw):
            problems.extend(record_problems(item, spec.element, f"{path}[{index}]"))
        return tuple(problems)
    try:
        parse_scalar(spec.scalar, raw)
    except ValueError as exc:
        return ((path, str(exc)),)
    return ()


def record_problems(data: Any, record: Record, path: str = "$") -> tuple[tuple[str, str], ...]:
    """Every problem the strict reading of one payload has, with its paths."""

    if not isinstance(data, Mapping):
        return ((path, NOT_AN_OBJECT_MESSAGE),)
    problems: list[tuple[str, str]] = []
    for spec in init_fields(record):
        if spec.name not in data:
            problems.append((f"{path}.{spec.name}", MISSING_FIELD_MESSAGE))
            continue
        problems.extend(field_problems(spec, data[spec.name], f"{path}.{spec.name}"))
    if record.closed:
        known = set(field_names(record))
        for key in sorted(str(key) for key in data):
            if key not in known:
                problems.append((f"{path}.{key}", UNKNOWN_KEY_MESSAGE))
    return tuple(problems)


def field_value(spec: Field, raw: Any) -> Any:
    """The value one column's raw content reads as. The raw content must be clean."""

    if spec.kind == "record":
        return structure(raw, spec.record)
    if spec.kind == "list":
        return tuple(structure(item, spec.element) for item in raw)
    return parse_scalar(spec.scalar, raw)


def read_field(spec: Field, raw: Any, path: str = "$") -> Any:
    """Read one column strictly, or raise the problems it has."""

    problems = field_problems(spec, raw, path)
    if problems:
        raise StructureErrors(problems)
    return field_value(spec, raw)


def structure(data: Any, record: Record) -> Row:
    """Read one whole payload strictly, or raise every problem it has.

    Nothing is assembled unless the payload is clean, so a caller that catches
    the error gets the problems and no object.
    """

    problems = record_problems(data, record, "$")
    if problems:
        raise StructureErrors(problems)
    return build(
        record,
        {spec.name: field_value(spec, data[spec.name]) for spec in init_fields(record)},
    )


__all__ = (
    "MISSING",
    "MISSING_FIELD_MESSAGE",
    "NOT_AN_OBJECT_MESSAGE",
    "NOT_A_LIST_MESSAGE",
    "UNKNOWN_KEY_MESSAGE",
    "Field",
    "Record",
    "Row",
    "StructureErrors",
    "build",
    "derived_names",
    "describe_errors",
    "field_names",
    "field_problems",
    "field_value",
    "init_fields",
    "parse_scalar",
    "read_field",
    "record_problems",
    "show",
    "structure",
)
