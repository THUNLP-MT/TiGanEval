'Deterministic, sandboxed review of one incident-console workspace.'

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import build_program, entry_table, recorded_notes


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("console/rich_pane.py", "console/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-console-",
)


PRIVATE_CASE: Mapping[str, Any] = {"session": "release"}


PUBLIC_RECORDS: tuple[str, ...] = (
    "retry-burst",
    "scroll-back-to-end",
    "divider-drag",
    "long-line-then-prune",
)

BUCKETS: Mapping[str, str] = {
    "paused_anchor_holds": "anchor_failures",
    "liveness_follows_position": "liveness_failures",
    "follow_transitions_exactly_once": "audit_failures",
    "render_matches_reference": "render_failures",
    "extent_matches_retained": "extent_failures",
}


_MOVERS = frozenset({"write", "resize", "set_min_width"})

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `console/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "console" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_console_protocol_review", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the console contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _badge(following: bool) -> str:
    return "Live" if following else "Paused"


def _anchor_at(
    strips: Sequence[tuple[str, tuple[str, ...]]], scroll_y: int
) -> tuple[str, int] | None:
    'Which entry, and which line inside it, sits at the top of the viewport.'

    index = 0
    for entry_id, lines in strips:
        if index + len(lines) > scroll_y:
            return (entry_id, scroll_y - index)
        index += len(lines)
    return None


def _offset_of(
    strips: Sequence[tuple[str, tuple[str, ...]]],
    anchor: tuple[str, int],
    drawn_before: Mapping[str, tuple[str, ...]],
) -> int | None:
    'Where the line the reader was holding sits now, or None once it is gone.'

    entry_id, line = anchor
    index = 0
    for held, lines in strips:
        if held == entry_id:
            if tuple(drawn_before.get(entry_id, ())) != tuple(lines):
                return index
            return index + int(line)
        index += len(lines)
    return None


def _drawn_the_same(
    strips: Sequence[tuple[str, tuple[str, ...]]],
    anchor: tuple[str, int],
    drawn_before: Mapping[str, tuple[str, ...]],
) -> bool:
    'Whether the held entry is still on the pane, drawn exactly as it was.'

    entry_id = anchor[0]
    for held, lines in strips:
        if held == entry_id:
            return tuple(drawn_before.get(entry_id, ())) == tuple(lines)
    return False


def _widest_entry(strips: Sequence[tuple[str, tuple[str, ...]]]) -> str:
    best, width = "nothing", -1
    for entry_id, lines in strips:
        longest = max((len(line) for line in lines), default=0)
        if longest > width:
            best, width = entry_id, longest
    return best


class Review:
    'One run of one session, read back the way the console reads its pane.'

    def __init__(self, result: Mapping[str, Any], program: Mapping[str, Any]):
        protocol = reference_protocol()
        pane = dict(program.get("pane", {}))
        self.protocol = protocol
        self.name = str(pane.get("name", "rich"))
        self.height = max(1, int(pane.get("height", 8)))
        self.max_entries = int(pane.get("max_entries", 0))
        self.table = entry_table(program)
        self.pre_layout = self._pre_layout(program)
        self.rows = self._rows(result, program, int(pane.get("min_width", 0)))

    @staticmethod
    def _pre_layout(program: Mapping[str, Any]) -> frozenset[str]:
        'Entries the console wrote before the layout gave the pane a width.'

        written: list[str] = []
        for op in program.get("operations", ()):
            kind = str(op.get("op"))
            if kind == "resize":
                break
            if kind == "write":
                written.append(str(op["entry"]))
        return frozenset(written)

    def _rows(
        self, result: Mapping[str, Any], program: Mapping[str, Any], min_width: int
    ) -> list[dict[str, Any]]:
        width = 0
        entries: list[str] = []
        pending: list[str] = []
        rows: list[dict[str, Any]] = []
        for raw, op in zip(result.get("operations", ()), program.get("operations", ())):
            kind = str(op.get("op"))
            if kind == "write":
                entry_id = str(op["entry"])
                if width <= 0:
                    pending.append(entry_id)
                else:
                    entries.append(entry_id)
                    if self.max_entries:
                        entries = entries[-self.max_entries :]
            elif kind == "resize":
                width = int(op["width"])
                if width > 0 and pending:
                    entries.extend(pending)
                    pending.clear()
                    if self.max_entries:
                        entries = entries[-self.max_entries :]
            elif kind == "set_min_width":
                min_width = int(op["min_width"])
            elif kind == "clear":
                entries.clear()
                pending.clear()
            strips = [
                (str(entry_id), tuple(str(line) for line in lines))
                for entry_id, lines in raw.get("strips", ())
            ]
            flat = [line for _, lines in strips for line in lines]
            row = dict(raw)
            row.update(
                {
                    "strips": strips,
                    "flat": flat,
                    "top": self.protocol.max_scroll_y(len(flat), self.height),
                    "anchor": _anchor_at(strips, int(raw.get("scroll_y", 0))),
                    "width": width,
                    "min_width": min_width,
                    "posted": [dict(item) for item in raw.get("posted", ())],
                    "expected_entries": tuple(entries),
                }
            )
            rows.append(row)
        return rows

    @property
    def audit_entries(self) -> int:
        return sum(len(row["posted"]) for row in self.rows)

    @property
    def badge_flips(self) -> int:
        flips, previous = 0, True
        for row in self.rows:
            if bool(row["following"]) != previous:
                flips += 1
            previous = bool(row["following"])
        return flips


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _anchor_failures(review: Review) -> list[dict[str, Any]]:
    'A reader who is not on the newest line keeps their place.'

    at_end = review.protocol.at_end
    failures: list[dict[str, Any]] = []
    for previous, row in zip(review.rows, review.rows[1:]):
        if str(row["event"]) not in _MOVERS or previous["anchor"] is None:
            continue
        if at_end(int(previous["scroll_y"]), int(previous["top"])):
            continue
        drawn_before = dict(previous["strips"])
        held = _offset_of(row["strips"], previous["anchor"], drawn_before)
        expected = 0 if held is None else min(held, int(row["top"]))
        if int(row["scroll_y"]) == expected:
            continue
        if at_end(int(row["scroll_y"]), int(row["top"])):
            kind = "paused_view_jumped_to_the_end"
        elif str(row["event"]) == "write":
            kind = "paused_view_slid_under_prune"
        elif _drawn_the_same(row["strips"], previous["anchor"], drawn_before):
            kind = "paused_view_lost_the_row_on_an_unchanged_entry"
        elif str(row["event"]) == "resize":
            kind = "paused_view_slid_after_reflow"
        else:
            kind = "paused_view_slid_after_the_reading_minimum"
        failures.append(
            _fail(
                kind,
                label=str(row["label"]),
                top_before=str(previous["anchor"][0]),
                top_after=str(row["anchor"][0]) if row["anchor"] else "nothing",
                entries_kept=review.max_entries,
                width=int(row["width"]),
                rows_moved=abs(int(row["scroll_y"]) - expected),
            )
        )
    return failures


def _liveness_failures(review: Review) -> list[dict[str, Any]]:
    'The badge is what the viewport is doing, not what anyone last pressed.'

    at_end = review.protocol.at_end
    failures: list[dict[str, Any]] = []
    for row in review.rows:
        scroll_y = int(row["scroll_y"])
        expected_max = int(row["top"])
        reported_max = int(row["max_scroll_y"])
        position = at_end(scroll_y, expected_max)
        if bool(row["following"]) == position:
            if reported_max == expected_max and 0 <= scroll_y <= expected_max:
                continue
            kind = "vertical_scrollbar_disagrees_with_pane"
        else:
            kind = (
                "badge_live_while_scrolled_up"
                if row["following"]
                else "badge_paused_at_the_end"
            )
        failures.append(
            _fail(
                kind,
                label=str(row["label"]),
                badge=_badge(bool(row["following"])),
                lines_from_the_end=expected_max - scroll_y,
                newest_entry=str(row["strips"][-1][0]) if row["strips"] else "nothing",
                top_entry=str(row["anchor"][0]) if row["anchor"] else "nothing",
                reported_scroll_y=scroll_y,
                reported_max_scroll_y=reported_max,
                expected_max_scroll_y=expected_max,
            )
        )
    return failures


def _audit_failures(review: Review) -> list[dict[str, Any]]:
    'One record for one change of the badge, carrying where the pane settled.'

    failures: list[dict[str, Any]] = []
    totals = {"audit_entries": review.audit_entries, "badge_flips": review.badge_flips}
    previous = True
    for row in review.rows:
        following = bool(row["following"])
        flips = 1 if following != previous else 0
        posted = list(row["posted"])
        kind = None
        extra: dict[str, Any] = {}
        if len(posted) > flips:
            kind = "record_posted_without_a_flip"
        elif len(posted) < flips:
            kind = "transition_not_posted"
        elif flips == 1:
            record = posted[0]
            settled = (
                bool(record.get("is_following_end")) == following
                and int(record.get("scroll_y", -1)) == int(row["scroll_y"])
                and int(record.get("max_scroll_y", -1)) == int(row["top"])
                and str(record.get("pane")) == review.name
            )
            if not settled:
                kind = "record_carried_unsettled_position"
                extra = {
                    "recorded_lines_from_the_end": int(record.get("max_scroll_y", 0))
                    - int(record.get("scroll_y", 0)),
                    "settled_lines_from_the_end": int(row["top"])
                    - int(row["scroll_y"]),
                    "recorded_badge": _badge(bool(record.get("is_following_end"))),
                }
        if kind is not None:
            failures.append(
                _fail(
                    kind,
                    label=str(row["label"]),
                    badge_before=_badge(previous),
                    badge_after=_badge(following),
                    records_here=len(posted),
                    **totals,
                    **extra,
                )
            )
        previous = following
    return failures


def _render_failures(review: Review) -> list[dict[str, Any]]:
    'Every entry on the pane is drawn the way the exporter draws it.'

    protocol = review.protocol
    failures: list[dict[str, Any]] = []
    for row in review.rows:
        width, min_width = int(row["width"]), int(row["min_width"])
        if width <= 0:
            continue
        expected_entries = tuple(str(item) for item in row["expected_entries"])
        pane_entries = tuple(entry_id for entry_id, _ in row["strips"])
        if pane_entries != expected_entries:
            difference = next(
                index
                for index in range(max(len(expected_entries), len(pane_entries)))
                if expected_entries[index : index + 1] != pane_entries[index : index + 1]
            )
            failures.append(
                _fail(
                    "retained_entries_disagree",
                    label=str(row["label"]),
                    expected_entry_count=len(expected_entries),
                    pane_entry_count=len(pane_entries),
                    first_difference=difference + 1,
                    expected_entry=(
                        expected_entries[difference]
                        if difference < len(expected_entries)
                        else "nothing"
                    ),
                    pane_entry=(
                        pane_entries[difference]
                        if difference < len(pane_entries)
                        else "nothing"
                    ),
                    expected_entries=list(expected_entries),
                    pane_entries=list(pane_entries),
                )
            )
            continue
        for entry_id, lines in row["strips"]:
            source = review.table[entry_id]
            expected = protocol.render_entry(
                source["text"], width, min_width, source["full_width"]
            )
            if tuple(lines) == expected:
                continue
            plain = protocol.render_entry(source["text"], width, min_width, False)
            if entry_id in review.pre_layout:
                kind = "deferred_entry_rendered_before_layout"
            elif source["full_width"] and tuple(lines) == plain:
                kind = "full_width_entry_not_expanded"
            elif str(row["event"]) == "set_min_width":
                kind = "entry_ignored_the_reading_minimum"
            else:
                kind = "entry_kept_its_old_width"
            cell = protocol.effective_width(width, min_width)
            failures.append(
                _fail(
                    kind,
                    label=str(row["label"]),
                    entry=entry_id,
                    width=width,
                    min_width=min_width,
                    pane_rows=len(lines),
                    console_rows=len(expected),
                    first_row_that_differs=next(
                        i + 1 for i in range(max(len(lines), len(expected)))
                        if lines[i : i + 1] != expected[i : i + 1]
                    ),
                    short_by=max(0, cell - max((len(line) for line in lines), default=0)),
                )
            )
            break
    return failures


def _extent_failures(review: Review) -> list[dict[str, Any]]:
    'Both scrollbars describe the log that is on the pane now.'

    protocol = review.protocol
    failures: list[dict[str, Any]] = []
    for row in review.rows:
        actual = protocol.extent_of_lines(row["flat"])
        if int(row["extent_widest"]) > int(actual.widest):
            kind = "content_width_kept_a_pruned_entry"
        elif int(row["extent_widest"]) < int(actual.widest):
            kind = "content_width_stops_short_of_the_widest_line"
        elif int(row["extent_line_count"]) != int(actual.line_count):
            kind = "line_count_disagrees_with_the_pane"
        else:
            continue
        failures.append(
            _fail(
                kind,
                label=str(row["label"]),
                reported_width=int(row["extent_widest"]),
                actual_width=int(actual.widest),
                reported_lines=int(row["extent_line_count"]),
                rows_on_the_pane=int(actual.line_count),
                widest_entry=_widest_entry(row["strips"]),
            )
        )
    return failures


def _analyse(result: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(result, program)
    return {
        "anchor_failures": _anchor_failures(review),
        "liveness_failures": _liveness_failures(review),
        "audit_failures": _audit_failures(review),
        "render_failures": _render_failures(review),
        "extent_failures": _extent_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(result: Mapping[str, Any]) -> str:
    'The one line the console shows when a session did not run to the end.'

    reported = str(result.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still drawing after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(result.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the pane stopped without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the pane stopped without saying why"
    return f"the pane stopped drawing: {line[:200]}"


def _stalled_row(result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for row in result.get("operations", ()):
        if isinstance(row, Mapping) and not row.get("ok", False):
            return row
    return None


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Drive the private session against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["session"]))
        result = PROJECT.invoke(artifact_dir, dict(program))
        stalled = _stalled_row(result) if result.get("ok") else None
        if not result.get("ok") or stalled is not None:
            message = (
                _console_error(result)
                if not result.get("ok")
                else "the pane stopped drawing: "
                + str(dict(stalled or {}).get("error", "no reason given"))[:200]
            )
            analysis = dict(failed_analysis(message, tuple(BUCKETS.values())))
            diagnostic = result.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(result, program)
        analysis["case"] = {
            "session": str(PRIVATE_CASE["session"]),
            "events": len(program["operations"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _console_settings(root: Path) -> Mapping[str, Any]:
    path = root / "console.toml"
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(record_id) if record_id in PUBLIC_RECORDS else {}
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "pane": dict(program.get("pane", {})),
                "events": len(program.get("operations", ())),
            }
        )
    return {
        "summary": "The console workspace and the sessions the shift leads replay.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "console_files": sorted(
                path.relative_to(root).as_posix()
                for path in (root / "console").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "console_toml": _console_settings(root),
        },
        "records": records,
    }


def _console_view(review: Review) -> list[dict[str, Any]]:
    'What an operator watching the pane would have seen at each event.'

    rows = []
    for row in review.rows:
        if not row.get("ok", True):
            rows.append(
                {
                    "label": row.get("label"),
                    "event": row.get("event"),
                    "completed": False,
                    "error": row.get("error"),
                }
            )
            continue
        scroll_y = int(row["scroll_y"])
        rows.append(
            {
                "label": row.get("label"),
                "event": row.get("event"),
                "completed": True,
                "pane_width": int(row["width"]),
                "reading_minimum": int(row["min_width"]),
                "scroll_y": scroll_y,
                "max_scroll_y": int(row["max_scroll_y"]),
                "badge": _badge(bool(row["following"])),
                "line_count": int(row["extent_line_count"]),
                "widest_line": int(row["extent_widest"]),
                "entries_on_the_pane": [entry_id for entry_id, _ in row["strips"]],
                "entry_at_the_top": row["anchor"][0] if row["anchor"] else None,
                "line_inside_that_entry": row["anchor"][1] if row["anchor"] else None,
                "posted_to_the_audit": row["posted"],
                "on_screen": row["flat"][scroll_y : scroll_y + review.height],
            }
        )
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded console session and report what the pane did.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(record_id)
    result = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not result.get("ok"):
        return {
            "summary": f"The {record_id} session could not run against this console.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": result.get("error", "unknown failure"),
                "diagnostic": result.get("diagnostic"),
            },
        }
    review = Review(result, program)
    public: dict[str, Any] = {
        "what_the_pane_did": _console_view(review),
        "what_the_console_recorded": recorded_notes(record_id),
    }
    if result.get("reference"):
        public["the_plain_pane_on_the_same_script"] = result["reference"]
    return {
        "summary": f"The {record_id} session ran against this console.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "pane": dict(program.get("pane", {})),
            "events": len(result.get("operations", ())),
            "records_posted_to_the_audit": review.audit_entries,
        },
        "public": public,
    }
