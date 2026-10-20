'Deterministic, sandboxed review of one tile-rendering workspace.'

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .reference import frozen_contract, modes_text, render_reference
from .workload import build_program, spelling_pairs


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("tilekit/sweep.py", "tilekit/edges.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-tilekit-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "mark": 41, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "coast-blur-rerender": {"profile": "coast", "mark": 7, "scale": 1},
    "globe-swath-nightly": {"profile": "globe", "mark": 3, "scale": 1},
    "quarantine-review": {"profile": "quarantine", "mark": 5, "scale": 1},
    "terrace-mirror-pass": {"profile": "mirror", "mark": 13, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "every_cell_is_produced": "sweep_failures",
    "boundary_reads_match_the_contract": "mapping_failures",
    "axes_are_mapped_independently": "axis_failures",
    "refuses_rather_than_substitutes": "refusal_failures",
    "recorded_passes_keep_their_output": "default_failures",
}

_CACHE = AnalysisCache()


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the batch console would show it.'

    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the pass ended without saying why"
    return line[:200]


def _failure(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One row per pass, with the contract's own tile beside what the build made."

    records = candidate.get("records")
    if not isinstance(records, (list, tuple)):
        raise TypeError("the batch result does not carry a pass list")
    if len(records) != len(program):
        raise ValueError(
            f"the batch returned {len(records)} passes for a {len(program)}-pass night"
        )
    steps: list[dict[str, Any]] = []
    for index, (event, record) in enumerate(zip(program, records)):
        if not isinstance(record, Mapping):
            raise TypeError(f"pass {index} is not a record")
        if record.get("index") != index or record.get("label") != event.get("label"):
            raise ValueError(f"pass {index} does not match the night")
        step = {**dict(record), "event": dict(event)}
        step["label"] = str(record["label"])
        step["reference"] = render_reference(event)
        steps.append(step)
    return steps


def coverage(step: Mapping[str, Any]) -> Counter:
    return Counter(tuple(int(part) for part in pair) for pair in step.get("writes", ()))


def _cell(rows: Any, row: int, col: int) -> Any:
    try:
        value = rows[row][col]
    except (TypeError, IndexError, KeyError):
        return "nothing"
    return value if isinstance(value, (int, float, bool, str)) else repr(value)


def _shape(rows: Any) -> tuple[int, int]:
    try:
        return len(rows), (len(rows[0]) if rows else 0)
    except TypeError:
        return (0, 0)


def write_counts(step: Mapping[str, Any]) -> dict[str, int]:
    'The write log of one pass, counted: cells, distinct cells, tile size.'

    rows = step.get("cells")
    if rows is None:
        rows = (step.get("reference") or {}).get("cells") or []
    if not rows:
        operands = (step.get("event") or {}).get("operands") or {}
        first = next(iter(operands.values()), {})
        rows = first.get("cells") or []
    height, width = _shape(rows)
    written = coverage(step)
    return {
        "writes": int(sum(written.values())),
        "distinct_cells": len({key for key, count in written.items() if count}),
        "tile_cells": height * width,
    }


def _runnable(step: Mapping[str, Any]) -> bool:
    return "raised" not in (step.get("reference") or {})


def _mode_bearing(step: Mapping[str, Any]) -> bool:
    reference = step.get("reference") or {}
    return _runnable(step) and not reference.get("constant_only", True)


def _sweep_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in steps:
        if not _runnable(step):
            continue
        label = str(step.get("label"))
        if not step.get("ok"):
            failures.append(
                _failure("pass_ended_with_an_error", job=label,
                         error=_safe_error(step.get("error")))
            )
            continue
        reference = step["reference"]
        applied, written = reference["applied"], coverage(step)
        missing = [
            (row, col)
            for row, line in enumerate(applied)
            for col, value in enumerate(line)
            if value and not written[(row, col)]
        ]
        twice = [key for key, count in sorted(written.items()) if count > 1]
        stray = [
            (row, col)
            for row, line in enumerate(applied)
            for col, value in enumerate(line)
            if not value and written[(row, col)]
        ]
        if missing:
            failures.append(
                _failure("cells_left_unproduced", job=label, row=missing[0][0],
                         col=missing[0][1], unproduced=len(missing))
            )
        if twice:
            failures.append(
                _failure("cell_produced_more_than_once", job=label, row=twice[0][0],
                         col=twice[0][1], writes=int(written[twice[0]]))
            )
        if stray:


            modes = reference["modes"]
            failures.append(
                _failure(
                    "frame_cell_overwritten" if modes[0] == modes[1]
                    else "constant_axis_band_overwritten",
                    job=label, row=stray[0][0], col=stray[0][1],
                    writes=int(written[stray[0]]),
                    modes=modes_text(modes),
                )
            )
    return failures


def _mapping_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in steps:
        if not _mode_bearing(step):
            continue
        label = str(step.get("label"))
        if not step.get("ok"):
            failures.append(
                _failure("pass_ended_with_an_error", job=label,
                         error=_safe_error(step.get("error")))
            )
            continue
        reference = step["reference"]
        expected, produced = reference["cells"], step.get("cells")
        seen: set[str] = set()
        for row, line in enumerate(expected):
            for col, value in enumerate(line):
                if not reference["applied"][row][col]:
                    continue
                row_out, col_out = reference["edges"][row][col]
                if row_out and col_out:
                    continue
                made = _cell(produced, row, col)
                if made == value:
                    continue
                kind = (
                    "out_of_reach_read_not_filled"
                    if reference["filled"][row][col]
                    else "edge_cell_disagrees_with_the_contract"
                )
                if kind in seen:
                    continue
                seen.add(kind)
                failures.append(
                    _failure(kind, job=label, row=row, col=col, produced=made,
                             expected=value, modes=modes_text(reference["modes"]))
                )
    return failures


def _axis_failures(
    steps: Sequence[Mapping[str, Any]], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    tiles: dict[str, Any] = {}
    for step in steps:
        label = str(step.get("label"))
        if step.get("ok"):
            tiles[label] = step.get("cells")
        if not _mode_bearing(step):
            continue
        if not step.get("ok"):
            failures.append(
                _failure("pass_ended_with_an_error", job=label,
                         error=_safe_error(step.get("error")))
            )
            continue
        reference = step["reference"]
        expected, produced = reference["cells"], step.get("cells")
        swapped = reference.get("swapped")
        if swapped is not None and produced == swapped and produced != expected:
            modes = reference["modes"]
            failures.append(
                _failure("axis_modes_swapped", job=label, modes=modes_text(modes),
                         swapped=modes_text((modes[1], modes[0])))
            )
            continue
        corners = (
            (row, col)
            for row, line in enumerate(reference["edges"])
            for col, (row_out, col_out) in enumerate(line)
            if row_out and col_out and reference["applied"][row][col]
        )
        wrong = next(
            ((row, col) for row, col in corners
             if _cell(produced, row, col) != expected[row][col]),
            None,
        )
        if wrong is not None:
            failures.append(
                _failure("corner_cell_disagrees_with_the_contract", job=label,
                         row=wrong[0], col=wrong[1],
                         produced=_cell(produced, *wrong),
                         expected=expected[wrong[0]][wrong[1]],
                         modes=modes_text(reference["modes"]))
            )
    for left, right in spelling_pairs(program):
        one, other = tiles.get(left), tiles.get(right)
        if one is None or other is None or one == other:
            continue
        height, width = _shape(one)
        spot = next(
            ((row, col) for row in range(height) for col in range(width)
             if _cell(one, row, col) != _cell(other, row, col)),
            (0, 0),
        )
        failures.append(
            _failure("mode_spelling_changes_the_tile", job=left, row=spot[0],
                     col=spot[1], one_reading=_cell(one, *spot),
                     other_reading=_cell(other, *spot))
        )
    return failures


def _refusal_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in steps:
        reference = step.get("reference") or {}
        raised = reference.get("raised")
        if not raised:
            continue
        label = str(step.get("label"))
        if step.get("ok"):
            if raised == "mode":
                failures.append(
                    _failure("unusable_mode_setting_produced_a_tile", job=label,
                             setting=str(reference.get("setting", "")))
                )
            elif raised == "cell_type":
                failures.append(
                    _failure("frame_buffer_cell_type_produced_a_tile", job=label,
                             produced_dtype=str(step.get("dtype")),
                             declared_dtype=str(reference.get("declared_dtype", "")),
                             buffer_dtype=str(reference.get("buffer_dtype", "")))
                )
            elif raised == "operand":
                failures.append(
                    _failure("out_of_reach_coefficient_read_produced_a_tile", job=label,
                             asked_row=int(reference.get("asked_row", 0)),
                             table_rows=int(reference.get("table_rows", 0)))
                )
            elif raised == "frame_shape":
                failures.append(
                    _failure(
                        "frame_buffer_shape_produced_a_tile",
                        job=label,
                        buffer_shape=str(reference.get("buffer_shape", "")),
                        tile_shape=str(reference.get("tile_shape", "")),
                    )
                )
            continue
        written = coverage(step)
        if written:
            spot = min(written)
            failures.append(
                _failure(
                    "refused_job_wrote_before_stopping",
                    job=label,
                    row=spot[0],
                    col=spot[1],
                    writes=int(sum(written.values())),
                )
            )
        before = (step["event"].get("frame") or {}).get("cells")
        after = step.get("frame_after")
        if before is None or after is None or before == after:
            continue
        height, width = _shape(before)
        spot = next(
            ((row, col) for row in range(height) for col in range(width)
             if _cell(before, row, col) != _cell(after, row, col)),
            (0, 0),
        )
        failures.append(
            _failure("refused_job_left_the_buffer_changed", job=label, row=spot[0],
                     col=spot[1], kept=_cell(before, *spot), found=_cell(after, *spot))
        )
    return failures


def _default_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in steps:
        reference = step.get("reference") or {}
        if not _runnable(step):
            continue
        label = str(step.get("label"))
        if not step.get("ok"):
            if reference.get("constant_only", False):
                failures.append(
                    _failure("pass_ended_with_an_error", job=label,
                             error=_safe_error(step.get("error")))
                )
            continue
        if str(step.get("dtype")) != str(reference["dtype"]):
            failures.append(
                _failure("declared_dtype_not_kept", job=label,
                         produced_dtype=str(step.get("dtype")),
                         declared_dtype=str(reference["dtype"]))
            )
        if step["event"].get("frame") is not None:
            expected, found = reference["cells"], step.get("frame_after")
            height, width = _shape(expected)
            spot = next(
                ((row, col) for row in range(height) for col in range(width)
                 if _cell(found, row, col) != expected[row][col]),
                None,
            )
            if spot is not None:
                failures.append(
                    _failure("frame_buffer_not_updated", job=label,
                             row=spot[0], col=spot[1],
                             found=_cell(found, *spot),
                             expected=expected[spot[0]][spot[1]])
                )
        if not reference.get("constant_only", False):
            continue
        kept_frame = step["event"].get("frame") is not None
        seen: set[str] = set()
        for row, line in enumerate(reference["cells"]):
            for col, value in enumerate(line):
                made = _cell(step.get("cells"), row, col)
                if made == value:
                    continue
                margin = kept_frame and not reference["applied"][row][col]
                kind = "kept_margin_overwritten" if margin else "default_tile_changed"
                if kind in seen:
                    continue
                seen.add(kind)
                failures.append(
                    _failure(kind, job=label, row=row, col=col, produced=made,
                             expected=value)
                )
    return failures


def _analyse(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    try:
        steps = read_steps(candidate, program)
    except (TypeError, ValueError) as exc:
        analysis = dict(
            failed_analysis(
                f"the batch result could not be read: {_safe_error(exc)}",
                tuple(BUCKETS.values()),
            )
        )
        analysis["harness_error"] = str(exc)
        return analysis
    return {
        "sweep_failures": _sweep_failures(steps),
        "mapping_failures": _mapping_failures(steps),
        "axis_failures": _axis_failures(steps, program),
        "refusal_failures": _refusal_failures(steps),
        "default_failures": _default_failures(steps),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the batch console shows when a night did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still going after {limit} and the batch box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the batch ended without saying why"
    return f"the batch stopped part way through the night: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private night against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        case = PRIVATE_CASE
        program = build_program(str(case["profile"]), int(case["mark"]), int(case["scale"]))
        candidate = PROJECT.invoke(artifact_dir, {"passes": list(program)})
        if not candidate.get("ok"):
            error = _console_error(candidate)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"night": "release"}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
