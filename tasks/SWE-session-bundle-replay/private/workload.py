'Deterministic console sessions: the cells, the bundles, and the schedules.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

def _console(name: str, execution_count: int = 1) -> dict[str, Any]:
    return {"op": "console", "console": name, "label": f"console-{name}",
            "execution_count": int(execution_count)}

def _cell(label: str, console: str, code: str, numbered: bool = True) -> dict[str, Any]:
    return {"op": "cell", "console": console, "code": code, "label": label,
            "store_history": bool(numbered)}

def _start(label: str, console: str, path: str, **options: Any) -> dict[str, Any]:
    return {"op": "start", "console": console, "path": path, "label": label, **options}

def _stop(label: str, console: str, **options: Any) -> dict[str, Any]:
    return {"op": "stop", "console": console, "label": label, **options}

def _status(label: str, console: str) -> dict[str, Any]:
    return {"op": "status", "console": console, "label": label}

def _inspect(label: str, path: str) -> dict[str, Any]:
    return {"op": "inspect", "path": path, "label": label}

def _load(label: str, path: str) -> dict[str, Any]:
    return {"op": "load", "path": path, "label": label}

def _replay(label: str, console: str, path: str, **options: Any) -> dict[str, Any]:
    return {"op": "replay", "console": console, "path": path, "label": label, **options}

def _fixture(label: str, path: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "fixture", "path": path, "label": label, "metadata": dict(bundle["metadata"]),
            "events": [dict(event) for event in bundle["events"]]}

def _phase(name: str, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**dict(op), "phase": name} for op in ops]


HANDOVER_CELLS: tuple[tuple[str, str, str, bool], ...] = (
    ("stage = 'loaded'\nprint('stage', stage)", "stage loaded\n", "", True),
    ("rows = [3, 5, 8]\nsum(rows)", "", "16", True),
    ("share = rows[0] / (len(rows) - 3)", "", "", False),
    ("stage = 'after the failure'\nprint('stage', stage)", "stage after the failure\n", "", True),
    ("carried = sum(rows) * 2\ncarried", "", "32", True),
)

AUDIT_CELLS: tuple[tuple[str, str, str, bool], ...] = (
    ("phase = 'opened'\nprint('phase', phase)", "phase opened\n", "", True),
    ("counts = [2, 7, 4]\nsum(counts)", "", "13", True),
    ("ratio = counts[0] / (len(counts) - 3)", "", "", False),
    ("phase = 'past the failure'\nprint('phase', phase)", "phase past the failure\n", "", True),
    ("tally = sum(counts) * 3\ntally", "", "39", True),
)

def _metadata(count: int, **overrides: Any) -> dict[str, Any]:
    metadata = {"format": "session-bundle", "format_version": 1, "console_version": "3.4.1",
                "created_at": "2026-02-18T14:03:11Z", "python_version": "3.12",
                "platform": "console-desktop", "redacted_patterns": 0, "event_count": int(count)}
    metadata.update(overrides)
    return metadata

def _event(position: int, cell: tuple[str, str, str, bool]) -> dict[str, Any]:
    code, stdout, result, success = cell
    event: dict[str, Any] = {
        "type": "cell", "seq": position, "execution_count": position, "code": code,
        "recorded_at": f"2026-02-18T14:0{position}:00Z", "success": success,
        "stdout": stdout, "stderr": "",
        "execute_result": {"text/plain": result} if result else {}}
    if not success:
        event["error"] = {"ename": "ZeroDivisionError", "evalue": "division by zero",
                          "traceback": ["  in <module>", "ZeroDivisionError: division by zero"]}
    return event

def sound_bundle(cells: Sequence[tuple[str, str, str, bool]]) -> dict[str, Any]:
    'A bundle a console can run: contiguous, complete, counted.'
    events = [_event(index, cell) for index, cell in enumerate(cells, start=1)]
    return {"metadata": _metadata(len(events)), "events": events}

def edited_bundle(cells: Sequence[tuple[str, str, str, bool]]) -> dict[str, Any]:
    'The same session after someone opened the file and took a cell out: the     third lost its traceback, the fourth is gone while the fifth keeps its     number, and the metadata still counts the session that was recorded..'
    events = [_event(index, cell) for index, cell in enumerate(cells, start=1)]
    kept = [events[0], events[1], dict(events[2]), events[4]]
    kept[2]["error"] = {"ename": "ZeroDivisionError", "evalue": "division by zero",
                        "traceback": []}
    return {"metadata": _metadata(len(cells)), "events": kept}

def stale_bundle(cells: Sequence[tuple[str, str, str, bool]]) -> dict[str, Any]:
    'A file an older console build wrote, before the format settled.'
    events = [_event(index, cell) for index, cell in enumerate(cells[:2], start=1)]
    metadata = _metadata(len(events), format="ipy-session", format_version=0)
    metadata.pop("redacted_patterns")
    return {"metadata": metadata,
            "events": [{k: v for k, v in e.items() if k != "stderr"} for e in events]}


SAMPLE_SOUND = "samples/clinic-handover.bundle"
SAMPLE_EDITED = "samples/clinic-handover-edited.bundle"


QUEUE_SOUND = "inbox/ward-audit.bundle"
QUEUE_EDITED = "inbox/ward-audit-edited.bundle"
QUEUE_STALE = "inbox/ward-audit-stale.bundle"


REPLAY_MARKERS: Mapping[str, tuple[str, str, str]] = {
    QUEUE_SOUND: ("phase", "opened", "past the failure"),
    SAMPLE_SOUND: ("stage", "loaded", "after the failure"),
}


PRIVATE_PATTERNS = ("upl_live_9d33ba", "acct-40917", "session-bundle", "console-desktop")

_WARD_CELLS = (
    ("intake-note", "notes = 'stay-length review'\nprint('opened', notes)", True),
    ("stay-rows", "stays = [4, 9, 6, 11, 7, 5]\nprint('cases', len(stays))", True),
    ("stay-mean", "sum(stays) / len(stays)", True),
    ("inspector-peek", "print('inspector: stays holds', len(stays), 'cases')", False),
    ("longest-stay", "longest = max(stays)\nprint('longest', longest)\nlongest", True),
    ("window-warning",
     "import sys\nprint('two cases sit outside the window', file=sys.stderr)\n"
     "shortest = min(stays)\nshortest", True),
    ("recall-mean", "print('the mean stay was', Out[4])", True),
    ("inspector-count", "len(stays)", False),
    ("banded-stays", "banded = sorted(stays)\nbanded", True),
    ("cohort-split", "print('splitting the cohort')\nratio = longest / (len(stays) - 6)", True),
    ("stay-summary", "summary = {'cases': len(stays), 'longest': longest}\nsummary", True),
)


_WARD_DESK = ("opened_at = '08:40'\nprint('desk open')", "print('desk closed')",
              "leavers = [1, 2, 4]\nprint('leavers', len(leavers))", "sum(leavers)",
              "handover = 'night staff briefed'\nprint(handover)")

_CREDENTIAL_CELLS = (
    ("upload-token", "token = 'upl_live_9d33ba'\nprint('uploading as', token)", True),
    ("upload-config",
     "config = {'endpoint': 'https://intake.internal/v2', 'key': token, "
     "'account': 'acct-40917'}\nconfig", True),
    ("retry-warning",
     "import sys\nprint('account acct-40917 retry 1 of 3', file=sys.stderr)", True),
    ("push-attempt",
     "def push(payload):\n    raise ValueError('upload rejected for ' + token)\n"
     "push({'cases': 6})", True),
    ("batch-ready", "print('batch ready for acct-40917')\n'ok'", True),
)

def _capture_ops(console: str, cells: Sequence[tuple[str, str, bool]], first: str,
                 second: str, desk: Sequence[str],
                 panel: str | None = None) -> list[dict[str, Any]]:
    'One handed-over session, then a second one with a start refused inside it.'
    ops = [_console(console), _cell("before-start", console, desk[0]),
           _start("start-first", console, first), _status("status-recording", console)]
    if panel is not None:
        ops += [_start("start-from-the-menu", console, panel, recorder="menu"),
                _status("status-after-the-menu", console)]
    ops += [_cell(label, console, code, numbered) for label, code, numbered in cells]
    ops += [_stop("stop-first", console), _status("status-after-stop", console),
            _cell("after-stop", console, desk[1]),
            _inspect("first-file-before-refusal", first),
            _start("start-over-first", console, first),
            _inspect("first-file-after-refusal", first),
            _start("start-second", console, second),
            _cell("handover-rows", console, desk[2]), _cell("handover-total", console, desk[3]),
            _start("start-second-again", console, second),
            _status("status-after-refusal", console),
            _cell("handover-note", console, desk[4]),
            _stop("stop-second", console), _inspect("second-file", second)]
    if panel is not None:
        ops += [_stop("stop-from-the-menu", console, recorder="menu"),
                _inspect("menu-file", panel)]
    return ops

def _credential_ops() -> list[dict[str, Any]]:
    'The same upload session recorded twice: with patterns, and with none.'
    ops: list[dict[str, Any]] = []
    for console, path, patterns, suffix in (
            ("cleaned", "exports/upload-cleaned.bundle", list(PRIVATE_PATTERNS), ""),
            ("plain", "exports/upload-plain.bundle", [], "-unfiltered")):
        ops += [_console(console), _start(f"start-{console}", console, path, redact=patterns)]
        ops += [_cell(f"{label}{suffix}", console, code, numbered)
                for label, code, numbered in _CREDENTIAL_CELLS]
        ops += [_stop(f"stop-{console}", console), _inspect(f"file-{console}", path)]
    return ops

def _admission_ops() -> list[dict[str, Any]]:
    'Three files off the support queue, two of them not what they claim.'
    sound, edited, stale = QUEUE_SOUND, QUEUE_EDITED, QUEUE_STALE
    return [
        _fixture("write-sound", sound, sound_bundle(AUDIT_CELLS)),
        _fixture("write-edited", edited, edited_bundle(AUDIT_CELLS)),
        _fixture("write-stale", stale, stale_bundle(AUDIT_CELLS)),
        _console("desk-a"), _load("load-edited", edited),
        _replay("replay-edited", "desk-a", edited),
        _console("desk-b"), _load("load-stale", stale),
        _replay("replay-stale", "desk-b", stale),
        _console("desk-c"), _load("load-sound", sound),
        _replay("replay-sound", "desk-c", sound)]

def _review_ops() -> list[dict[str, Any]]:
    'One sound file opened three ways in a console that is already in use.'
    return [_console("review-1", 41), _replay("review-numbered", "review-1", QUEUE_SOUND),
            _console("review-2", 41),
            _replay("review-quiet", "review-2", QUEUE_SOUND, store_history=False),
            _console("review-3", 41),
            _replay("review-through", "review-3", QUEUE_SOUND, stop_on_error=False)]

def _ward_ops() -> list[dict[str, Any]]:
    return _capture_ops("ward", _WARD_CELLS, "exports/ward-morning.bundle",
                        "exports/ward-afternoon.bundle", _WARD_DESK,
                        panel="exports/ward-morning-again.bundle")
PRIVATE_PHASES = (("capture", _ward_ops), ("credentials", _credential_ops),
                  ("admission", _admission_ops), ("review", _review_ops))


PUBLIC_PATTERNS = ("upl_live_4f21c8", "cust-88213", "session-bundle", "console-desktop")

_CLINIC_CELLS = (
    ("reading-rows", "readings = [412, 388, 401, 455, 399]\nprint('rows', len(readings))", True),
    ("reading-mean", "sum(readings) / len(readings)", True),
    ("inspector-peek", "print('inspector: readings has', len(readings), 'rows')", False),
    ("peak-reading", "peak = max(readings)\nprint('peak', peak)\npeak", True),
    ("window-warning",
     "import sys\nprint('one reading outside the window', file=sys.stderr)\n"
     "low = min(readings)\nlow", True),
    ("recall-mean", "print('the mean was', Out[3])", True),
    ("shift-split", "print('splitting by shift')\nshare = readings[0] / 0", True),
    ("reading-summary", "totals = {'rows': len(readings), 'peak': peak}\ntotals", True),
)

_INTAKE_CELLS = (
    ("upload-token", "token = 'upl_live_4f21c8'\nprint('uploading as', token)", True),
    ("upload-config",
     "config = {'endpoint': 'https://intake.internal/v2', 'key': token, "
     "'account': 'cust-88213'}\nconfig", True),
    ("retry-warning", "import sys\nprint('account cust-88213 retry 1', file=sys.stderr)", True),
    ("push-attempt",
     "def push(payload):\n    raise ValueError('upload rejected for ' + token)\n"
     "push({'rows': 5})", True),
    ("batch-ready", "print('batch ready for cust-88213')\n'ok'", True),
)

def _handoff_program() -> dict[str, Any]:
    ops = _capture_ops(
        "clinic", _CLINIC_CELLS, "exports/clinic-handoff.bundle",
        "exports/clinic-evening.bundle", _CLINIC_DESK,
        panel="exports/clinic-menu.bundle")
    return {"secrets": (), "operations": _phase("capture", ops)}

_CLINIC_DESK = ("site = 'clinic 4'\nprint('desk open at', site)", "print('desk closed')",
                "late = [7, 9]\nprint('late', len(late))", "sum(late)",
                "closed = 'shift handed over'\nprint(closed)")

def _credential_program() -> dict[str, Any]:
    ops: list[dict[str, Any]] = []
    for console, path, patterns, suffix in (
            ("intake", "exports/intake-cleaned.bundle", list(PUBLIC_PATTERNS), ""),
            ("plain", "exports/intake-plain.bundle", [], "-unfiltered")):
        ops += [_console(console), _start(f"start-{console}", console, path, redact=patterns)]
        ops += [_cell(f"{label}{suffix}", console, code, numbered)
                for label, code, numbered in _INTAKE_CELLS]
        ops += [_stop(f"stop-{console}", console), _inspect(f"file-{console}", path)]
    return {"secrets": PUBLIC_PATTERNS, "operations": _phase("credentials", ops)}

def _shared_program() -> dict[str, Any]:
    ops = [_inspect("edited-file", SAMPLE_EDITED), _inspect("sound-file", SAMPLE_SOUND),
           _console("desk-a"), _load("load-edited", SAMPLE_EDITED),
           _replay("replay-edited", "desk-a", SAMPLE_EDITED),
           _console("desk-b"), _load("load-sound", SAMPLE_SOUND),
           _replay("replay-sound", "desk-b", SAMPLE_SOUND)]
    return {"secrets": (), "operations": _phase("admission", ops)}

def _rehearsal_program() -> dict[str, Any]:
    ops = [_console("review-1", 12), _replay("review-numbered", "review-1", SAMPLE_SOUND),
           _console("review-2", 12),
           _replay("review-quiet", "review-2", SAMPLE_SOUND, store_history=False),
           _console("review-3", 12),
           _replay("review-through", "review-3", SAMPLE_SOUND, stop_on_error=False)]
    return {"secrets": (), "operations": _phase("review", ops)}

PUBLIC_PROGRAMS = {"handoff": _handoff_program, "credentials": _credential_program,
                   "shared": _shared_program, "rehearsal": _rehearsal_program}

def build_program(profile: str) -> dict[str, Any]:
    'The console operations for one stretch of work.'
    if profile == "release":
        operations: list[dict[str, Any]] = []
        for name, builder in PRIVATE_PHASES:
            operations.extend(_phase(name, builder()))
        return {"secrets": PRIVATE_PATTERNS, "operations": operations}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown console session profile: {profile}")
    return builder()
