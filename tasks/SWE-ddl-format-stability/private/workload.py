'Migration corpora for the formatter project.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


LINE_WIDTH = 88
INDENT = 4

_NOUNS = ("account", "invoice", "shipment", "ledger", "session", "device", "coupon", "region")
_TYPES = ("int", "bigint", "text", "varchar(255)", "timestamp", "numeric(12, 2)", "boolean")


def _table(index: int, seed: int) -> str:
    noun = _NOUNS[(seed + index) % len(_NOUNS)]
    columns = [
        f"id {_TYPES[(seed + index) % len(_TYPES)]} primary key",
        f"{noun}_ref varchar(64) not null",
        f"amount {_TYPES[(seed + index + 3) % len(_TYPES)]} default 0",
        "created timestamp not null",
    ]
    return (
        f"create table {noun}s ({', '.join(columns)}, "
        f"constraint {noun}_ck check (created > '2020-01-01'))"
    )


def _name(seed: int, index: int, stem: str) -> str:
    "The migration file's own name, as it appears in the schema repository."

    return f"migrations/{100 + seed + index:04d}_{stem}.sql"


def build_cases(seed: int, scale: int) -> list[dict[str, Any]]:
    'One deterministic run of migration files from the schema repository.'

    noun = _NOUNS[seed % len(_NOUNS)]
    long_columns = ", ".join(
        f"very_long_column_name_number_{index:02d} varchar(255) not null default 'placeholder'"
        for index in range(2 + scale)
    )
    cases: list[dict[str, Any]] = [
        {
            "label": _name(seed, 0, f"create_{noun}s"),
            "text": ";\n".join(_table(index, seed) for index in range(2 + scale)) + ";",
        },
        {


            "label": _name(seed, 1, f"create_{noun}_notes"),
            "text": (
                f"create table {noun}_notes (id int, "
                "label text default 'First, Second, Third', "
                "shape struct<width int, height int, depth int>, "
                "tags array<string>, body text, "
                "retention_note text default "
                "'Retained for seven years, then archived, and finally deleted');"
            ),
        },
        {


            "label": _name(seed, 2, f"create_{noun}_payouts"),
            "text": (
                "-- ledger of external payouts\n"
                f"create table {noun}_payouts (\n"
                "  id bigint primary key, -- surrogate key\n"
                "  /* denormalised for the finance export,\n"
                "     since the nightly join against the ledger is too slow */"
                " payee text not null,\n"
                "  amount numeric(12, 2) not null,\n"
                "  primary key (id)\n"
                ");"
            ),
        },
        {
            "label": _name(seed, 3, f"create_{noun}_wide"),
            "text": f"create table {noun}_wide ({long_columns});",
        },
        {
            "label": _name(seed, 4, f"create_{noun}_events"),
            "text": (
                f"create table if not exists analytics.{noun}_events "
                "(id bigint, payload struct<a int, b string>, ts timestamp not null) "
                "partition by ts cluster by id options(description='event stream');"
            ),
        },
        {
            "label": _name(seed, 5, f"create_{noun}_views"),


            "text": (
                f"create table {noun}_live (id int, name text);\n"
                f"CREATE TABLE {noun}_arch AS SELECT id, 'North  America' AS export_region, upper(name) FROM {noun}_live;\n"
                f"CREATE TABLE {noun}_copy LIKE {noun}_live;\n"
                f"DROP TABLE {noun}_old;\n"
                f"create index {noun}_idx on {noun}_live (name);"
            ),
        },
    ]


    dense = _name(seed, 6, f"create_{noun}_pairs")
    sparse = _name(seed, 7, f"recreate_{noun}_pairs")
    cases.append(
        {
            "label": dense,
            "text": f"create table {noun}_pairs (id int primary key, note text not null);",
            "equivalent_to": sparse,
        }
    )
    cases.append(
        {
            "label": sparse,
            "text": (
                f"CREATE   TABLE   {noun}_pairs\n"
                "(\n        ID INT PRIMARY KEY,\n"
                "        Note   TEXT   NOT NULL\n)\n;"
            ),
            "equivalent_to": dense,
        }
    )
    cases.append(
        {


            "label": _name(seed, 8, f"create_{noun}_settlements"),
            "text": (
                f"create table {noun}_settlements"
                " -- one row per settlement the finance export reads\n"
                "(\n"
                "  id bigint primary key,\n"
                "  settled timestamp not null,\n"
                "  amount bigint not null\n"
                ");"
            ),
        }
    )
    return cases


def _options(line_width: int = LINE_WIDTH, indent: int = INDENT) -> dict[str, Any]:
    return {"line_width": int(line_width), "indent": int(indent)}


def _event(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "format",
        "label": str(case["label"]),
        "text": str(case["text"]),
        "options": _options(),
        "equivalent_to": case.get("equivalent_to"),
    }


def build_program(seed: int, scale: int) -> list[dict[str, Any]]:
    'The private workload: every generated file, formatted once.'

    return [_event(case) for case in build_cases(seed, scale)]


def read_migrations(workspace: Path, record: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The program one project record names, read from the workspace itself.'

    root = Path(workspace).resolve()
    partner: dict[str, str] = {}
    for pair in record.get("same_schema", ()):
        first, second = (str(item) for item in pair)
        partner[first] = second
        partner[second] = first
    events: list[dict[str, Any]] = []
    for raw in record.get("files", ()):
        relative = str(raw)
        path = (root / relative).resolve()
        if root not in path.parents or path.suffix != ".sql" or not path.is_file():
            raise ValueError(f"project record names a missing migration file: {relative}")
        events.append(
            _event(
                {
                    "label": relative,
                    "text": path.read_text(encoding="utf-8"),
                    "equivalent_to": partner.get(relative),
                }
            )
        )
    if not events:
        raise ValueError("project record names no migration files")
    return events


def load_record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("project record must contain a JSON object")
    return raw


__all__ = (
    "INDENT",
    "LINE_WIDTH",
    "build_cases",
    "build_program",
    "load_record",
    "read_migrations",
)
