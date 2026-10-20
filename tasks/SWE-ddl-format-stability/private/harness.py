'Deterministic, sandboxed analysis of one migration-formatter workspace.'

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
)

from ..workspace.ddl import protocol
from .workload import build_program, load_record, read_migrations


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("ddl/formatter.py", "ddl/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-ddl-format-",
)


PRIVATE_SEED = 27
PRIVATE_SCALE = 2

BUCKETS: Mapping[str, str] = {
    "schema_semantics_preserved": "semantic_failures",
    "formatting_is_idempotent": "stability_failures",
    "comments_preserved": "comment_failures",
    "line_width_contract": "width_failures",
    "explicit_unsupported_handling": "coverage_failures",
}


def _schemas(text: str) -> list[Any]:
    rows: list[Any] = []
    for statement in protocol.split_statements(text):
        try:
            schema = protocol.parse_schema(statement)
        except protocol.DdlError:
            rows.append("<unparsable>")
            continue
        rows.append(None if schema is None else schema.as_dict())
    return rows


def _pass(record: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = record.get(key)
    return dict(value) if isinstance(value, Mapping) else None


def _supported(statement: str) -> bool:
    try:
        return protocol.parse_schema(statement) is not None
    except protocol.DdlError:
        return False


def _breakable_comma_lines(statement: str) -> set[int]:
    'Physical lines containing a structurally breakable comma.'

    try:
        tokens = protocol.tokenize(statement)
    except protocol.DdlError:

        return set()

    depth = 0
    body_depth: int | None = None
    inside_body = False
    angle_depth = 0
    previous_code: protocol.Token | None = None
    lines: set[int] = set()

    for token in tokens:
        if token.kind == "comment":
            continue
        if token.kind != "punct":
            previous_code = token
            continue

        character = token.text
        if character == "<":
            if angle_depth or (
                previous_code is not None
                and previous_code.kind == "word"
                and previous_code.lowered in {"array", "struct"}
            ):
                angle_depth += 1
        elif character == ">" and angle_depth:
            angle_depth -= 1
        elif character in "([":
            depth += 1
            if character == "(" and body_depth is None:
                body_depth = depth
                inside_body = True
        elif character in ")]":
            if character == ")" and inside_body and depth == body_depth:
                inside_body = False
            depth = max(0, depth - 1)
        elif character == "," and angle_depth == 0 and (
            depth == 0 or (inside_body and depth == body_depth)
        ):
            lines.add(statement.count("\n", 0, token.start))
        previous_code = token

    return lines


def _rewritten_statements(source: str, formatted: str) -> list[str]:
    'Statements the formatter rewrote, excluding unsupported pass-throughs.'

    try:
        originals = list(protocol.split_statements(source))
        produced = list(protocol.split_statements(formatted))
    except protocol.DdlError:
        return [formatted]
    if len(produced) != len(originals):
        return [formatted]
    return [output for original, output in zip(originals, produced) if _supported(original)]


def _rewritten_lines(source: str, formatted: str) -> list[str]:
    'The lines the formatter wrote, excluding statements it passed through.'

    return [
        line
        for statement in _rewritten_statements(source, formatted)
        for line in statement.splitlines()
        if line.strip()
    ]


def _semantic_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        source = str(record.get("source", ""))
        formatted = str(_pass(record, "first")["formatted"])
        try:
            after = _schemas(formatted)
        except protocol.DdlError as exc:
            failures.append(
                {"kind": "formatted_output_unparsable", "label": label, "error": str(exc)}
            )
            continue
        before = _schemas(source)
        if len(before) != len(after):
            failures.append(
                {
                    "kind": "statement_lost",
                    "label": label,
                    "statements_before": len(before),
                    "statements_after": len(after),
                }
            )
            continue
        for position, (original, produced) in enumerate(zip(before, after)):


            if original is None or original == produced:
                continue
            if produced == "<unparsable>":
                kind = "formatted_output_unparsable"
            elif produced is None:


                kind = "statement_no_longer_a_table"
            else:
                kind = "schema_changed"
            failures.append(
                {
                    "kind": kind,
                    "label": label,
                    "statement": position,
                    "read_before": original,
                    "read_after": produced,
                }
            )
            break
    return failures


def _stability_failures(
    records: Sequence[Mapping[str, Any]], program: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    by_label = {str(record.get("label")): str(_pass(record, "first")["formatted"]) for record in records}
    for record in records:
        label = str(record.get("label"))
        first = str(_pass(record, "first")["formatted"])
        second = _pass(record, "second")
        repeat = _pass(record, "repeat")
        if second is None or second["formatted"] != first:
            failures.append(
                {
                    "kind": "second_pass_differs",
                    "label": label,
                    "error": record.get("second_error"),
                    "wrote": first[:120],
                    "wrote_again": None if second is None else str(second["formatted"])[:120],
                }
            )
        if repeat is None or repeat["formatted"] != first:
            failures.append({"kind": "output_not_deterministic", "label": label})
    for record in records:
        label = str(record.get("label"))
        partner = str(program.get(label, {}).get("equivalent_to") or "")
        if not partner or partner not in by_label:
            continue
        if by_label[label].strip() != by_label[partner].strip():
            failures.append(
                {
                    "kind": "output_depends_on_input_formatting",
                    "label": label,
                    "partner": partner,
                }
            )
    return failures


_STATEMENT_OPENERS = frozenset(
    {"create", "drop", "alter", "insert", "update", "delete", "select", "with"}
)


def _swallow_kind(swallowed: str) -> str:
    'Whether a `--` comment hid a whole statement or a piece of one.'

    opener = swallowed.strip().split(" ", 1)[0].casefold()
    if opener in _STATEMENT_OPENERS:
        return "header_comment_swallows_statement"
    return "line_comment_swallows_code"


def _comment_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        source = str(record.get("source", ""))
        formatted = str(_pass(record, "first")["formatted"])
        try:
            before = protocol.comments(source)
            tokens = protocol.tokenize(formatted)
        except protocol.DdlError:


            continue
        after = tuple(" ".join(token.text.split()) for token in tokens if token.kind == "comment")


        remaining = list(before)
        swallowed: tuple[str, str] | None = None
        for text in after:
            if text in remaining:
                remaining.remove(text)
                continue
            for comment in before:
                if (
                    comment.startswith("--")
                    and text.startswith(comment)
                    and text[len(comment) :].strip()
                ):
                    swallowed = (comment, text)
                    break
            if swallowed is not None:
                break
        if swallowed is not None:
            hidden = swallowed[1][len(swallowed[0]) :].strip()[:80]
            failures.append(
                {
                    "kind": _swallow_kind(hidden),
                    "label": label,
                    "comment": swallowed[0],
                    "swallowed": hidden,
                }
            )
            continue
        split_block = next(
            (
                token
                for token in tokens
                if token.kind == "comment" and token.text.startswith("/*") and "\n" in token.text
            ),
            None,
        )
        if split_block is not None:
            failures.append(
                {
                    "kind": "block_comment_split_across_lines",
                    "label": label,


                    "comment": " ".join(split_block.text.split())[:120],
                }
            )
            continue
        if before != after:
            failures.append(
                {
                    "kind": "comment_lost_or_reordered",
                    "label": label,
                    "wrote_by_the_author": list(before)[:4],
                    "came_back": list(after)[:4],
                }
            )
    return failures


def _width_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        options = dict(record.get("options", {}))
        width = int(options.get("line_width", protocol.LINE_WIDTH))
        indent = max(1, int(options.get("indent", protocol.INDENT)))
        source = str(record.get("source", ""))
        formatted = str(_pass(record, "first")["formatted"])
        statements = _rewritten_statements(source, formatted)
        lines = [line for statement in statements for line in statement.splitlines() if line.strip()]
        over = None
        for statement in statements:
            breakable_lines = _breakable_comma_lines(statement)
            over = next(
                (
                    line
                    for index, line in enumerate(statement.splitlines())
                    if line.strip() and len(line) > width and index in breakable_lines
                ),
                None,
            )
            if over is not None:
                break
        if over is not None:
            failures.append(
                {
                    "kind": "line_over_width_with_break_available",
                    "label": label,
                    "width": len(over),
                    "allowance": width,
                    "line": over[:80],
                }
            )
        wrong = sorted(
            {
                len(line) - len(line.lstrip(" "))
                for line in lines
                if line.startswith(" ") and (len(line) - len(line.lstrip(" "))) % indent
            }
        )
        if wrong:
            failures.append(
                {
                    "kind": "body_indent_wrong",
                    "label": label,
                    "indents": wrong,
                    "found_indent": wrong[0],
                    "expected": indent,
                }
            )
    return failures


def _coverage_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in records:
        label = str(record.get("label"))
        source = str(record.get("source", ""))
        formatted = str(_pass(record, "first")["formatted"])
        originals = list(protocol.split_statements(source))
        rows = list(_pass(record, "first")["statements"])
        if len(rows) != len(originals) or [int(row["index"]) for row in rows] != list(
            range(len(originals))
        ):
            failures.append(
                {
                    "kind": "statement_rows_incomplete",
                    "label": label,
                    "rows": len(rows),
                    "statements_in_the_file": len(originals),
                }
            )
            continue
        try:
            produced = list(protocol.split_statements(formatted))
        except protocol.DdlError:
            continue
        if len(produced) != len(originals):
            continue
        for row, original, output in zip(rows, originals, produced):
            status = str(row["status"])
            supported = _supported(original)
            if supported and status != "formatted":
                failures.append(
                    {
                        "kind": "supported_statement_reported_unsupported",
                        "label": label,
                        "statement": int(row["index"]),
                        "reported": status,
                        "opening": " ".join(original.split())[:60],
                    }
                )
                break
            if supported:
                continue
            if status != "unsupported":
                failures.append(
                    {
                        "kind": "unsupported_statement_reported_formatted",
                        "label": label,
                        "statement": int(row["index"]),
                        "reported": status,
                        "opening": " ".join(original.split())[:60],
                    }
                )
                break
            if output.strip() != original.strip():
                failures.append(
                    {
                        "kind": "unsupported_statement_modified",
                        "label": label,
                        "statement": int(row["index"]),
                        "opening": " ".join(original.split())[:60],
                        "came_back": " ".join(output.split())[:60],
                    }
                )
                break
    return failures


def _records(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(record)
        for record in candidate.get("records", ())
        if isinstance(record, Mapping) and record.get("type") == "format"
    ]


def _did_not_run(
    records: Sequence[Mapping[str, Any]], error: str | None, first_label: str
) -> list[dict[str, Any]]:
    'The stub every bucket carries when the formatter did not produce a file.'

    stopped = [record for record in records if _pass(record, "first") is None]
    if not stopped:
        return [
            {
                "kind": CANDIDATE_FAILURE,
                "label": first_label,
                "error": error or "the formatter did not run",
            }
        ]
    return [
        {
            "kind": CANDIDATE_FAILURE,
            "label": str(record.get("label") or first_label),
            "error": str(record.get("error") or error or "the formatter did not run"),
        }
        for record in stopped
    ]


def _analyse(candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_label = {str(event["label"]): dict(event) for event in program}
    records = _records(candidate)
    case = {"files": len(program), "line_width": protocol.LINE_WIDTH, "indent": protocol.INDENT}
    if not candidate.get("ok") or len(records) != len(program) or any(
        _pass(record, "first") is None for record in records
    ):
        error = candidate.get("error")
        first_label = str(program[0]["label"]) if program else "the migrations directory"
        if not records and program:
            records = [{"label": first_label, "error": error}]
        stub = _did_not_run(records, None if error is None else str(error), first_label)
        return {**{bucket: list(stub) for bucket in BUCKETS.values()}, "case": case}
    return {
        "semantic_failures": _semantic_failures(records),
        "stability_failures": _stability_failures(records, by_label),
        "comment_failures": _comment_failures(records),
        "width_failures": _width_failures(records),
        "coverage_failures": _coverage_failures(records),
        "case": case,
    }


_CACHE = AnalysisCache()


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private workload against one candidate workspace, once.'

    def compute() -> Mapping[str, Any]:
        program = build_program(PRIVATE_SEED, PRIVATE_SCALE)
        candidate = PROJECT.invoke(artifact_dir, {"events": list(program)})
        return _analyse(candidate, program)

    return _CACHE.get_or_compute(artifact_dir, compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = sorted(path.name for path in (root / "project_records").glob("*.json"))
    migrations = sorted(
        path.relative_to(root).as_posix() for path in (root / "migrations").glob("*.sql")
    )
    return {
        "project_records": records,
        "migration_files": migrations,
        "line_width": protocol.LINE_WIDTH,
        "indent": protocol.INDENT,
        "artifact_hash": artifact_hash(root),
    }


def run_public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Format the files one record names and report what came out, unjudged.'

    root = Path(artifact_dir)
    record = load_record(record_path)
    program = read_migrations(root, record)
    candidate = PROJECT.invoke(root, {"events": list(program)})
    if not candidate.get("ok"):
        return {
            "record_id": str(record.get("record_id", Path(record_path).stem)),
            "line_width": protocol.LINE_WIDTH,
            "indent": protocol.INDENT,
            "execution_error": str(candidate.get("error", "unknown failure")),
            "diagnostic": str(candidate.get("diagnostic", ""))[-400:],
            "files": [],
        }
    timeline: list[dict[str, Any]] = []
    for entry in _records(candidate):
        first = _pass(entry, "first")
        second = _pass(entry, "second")
        source = str(entry.get("source", ""))
        row: dict[str, Any] = {
            "file": entry.get("label"),
            "produced_a_file": first is not None,
            "error": entry.get("error"),
            "source": source,
            "formatted": None if first is None else first["formatted"],
            "statement_rows": None if first is None else first["statements"],
        }
        if first is not None:
            formatted = str(first["formatted"])
            row["line_widths"] = [len(line) for line in formatted.splitlines()]

            row["formatted_from_that_output"] = (
                None if second is None else str(second["formatted"])
            )
            row["error_on_that_second_run"] = entry.get("second_error")
        timeline.append(row)
    same_schema = [
        {"files": [str(item) for item in pair]} for pair in record.get("same_schema", ())
    ]
    return {
        "record_id": str(record.get("record_id", Path(record_path).stem)),
        "line_width": protocol.LINE_WIDTH,
        "indent": protocol.INDENT,
        "files": timeline,
        "same_schema": same_schema,
    }


__all__ = (
    "BUCKETS",
    "PRIVATE_SCALE",
    "PRIVATE_SEED",
    "evaluate_project",
    "public_status",
    "run_public_replay",
)
