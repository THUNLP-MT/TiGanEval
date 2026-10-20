'Deterministic, sandboxed analysis of one write-path workspace.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import PUBLIC_BUILDERS, private_sessions, public_session


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("engine/durability.py", "engine/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-engine-",
)


PRIVATE_SEED = 47

BUCKETS: Mapping[str, str] = {
    "durable_watermark_matches_log": "watermark_failures",
    "release_never_precedes_the_log": "release_failures",
    "one_event_per_sync_commit": "event_failures",
    "waiters_settle_exactly_once": "waiter_failures",
    "accounting_independent_of_pipeline_shape": "invariance_failures",
}

_CACHE = AnalysisCache()
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _steps(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in session.get("steps", ()) if isinstance(row, Mapping)]


def _listed(values: Sequence[Any]) -> str:
    rows = [str(item) for item in values]
    if not rows:
        return "nothing"
    if len(rows) == 1:
        return rows[0]
    return f"{', '.join(rows[:-1])} and {rows[-1]}"


def _reported(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("reported")
    return dict(value) if isinstance(value, Mapping) else {"watermark": None, "err": None}


def _stat(row: Mapping[str, Any], name: str) -> Any:
    value = row.get("stats")
    return dict(value).get(name) if isinstance(value, Mapping) else None


def _outstanding(row: Mapping[str, Any]) -> int:
    return sum(1 for waiter in row.get("waiters", ()) if not waiter.get("resolutions"))


def _record(kind: str, session: str, row: Mapping[str, Any], **fields: Any) -> dict[str, Any]:
    'One failure, labelled with the session and the step it was measured at.'
    return {"kind": kind, "session": session, "label": str(row.get("label")), **fields}


def _outcome(waiter: Mapping[str, Any]) -> str:
    resolutions = list(waiter.get("resolutions") or ())
    if not resolutions:
        return "still waiting"
    return "released" if resolutions[0] is None else "failed with an error"


def _clean(text: Any) -> str:
    line = _DIRECTORY_PART.sub("", str(text or "").strip()) or "no output"
    lowered = line.lower()
    if any(word in lowered for word in FORBIDDEN_VOCABULARY):
        return "the write path stopped without saying why"
    return line[:200]


def _expected_program(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    timeline = [dict(step) for step in session.get("timeline", ())]
    return [
        {"op": "start", "label": "start"},
        *timeline,
        {"op": "close", "label": "close"},
    ]


def _structure_failures(
    candidate: Mapping[str, Any], expected_sessions: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Fail closed when the candidate process suppresses or truncates telemetry.'

    expected_names = [str(session["name"]) for session in expected_sessions]
    sessions = {
        str(name): dict(value)
        for name, value in dict(candidate.get("sessions", {})).items()
        if isinstance(value, Mapping)
    }
    failures: list[dict[str, Any]] = []
    order = [str(name) for name in candidate.get("order", ())]
    if order != expected_names:
        failures.append(
            {
                "kind": "session_output_incomplete",
                "session": "release",
                "label": "session list",
                "error": f"session order was {order!r}, expected {expected_names!r}",
            }
        )
        return failures
    if set(sessions) != set(expected_names):
        failures.append(
            {
                "kind": "session_output_incomplete",
                "session": "release",
                "label": "session list",
                "error": "the console did not return every requested session",
            }
        )
        return failures
    required_row_fields = {
        "index",
        "label",
        "op",
        "ok",
        "error",
        "log",
        "reference_watermark",
        "recoverable_seqs",
        "reported",
        "stats",
        "events",
        "waiters",
        "released_here",
        "released_so_far",
    }
    for specification in expected_sessions:
        name = str(specification["name"])
        session = sessions[name]
        if session.get("error"):
            continue
        rows = _steps(session)
        program = _expected_program(specification)
        if len(rows) != len(program):
            failures.append(
                {
                    "kind": "session_output_incomplete",
                    "session": name,
                    "label": "session length",
                    "error": f"the console returned {len(rows)} of {len(program)} step rows",
                }
            )
            continue
        for index, (row, step) in enumerate(zip(rows, program)):
            expected_op = str(step.get("op", "probe"))
            expected_label = str(step.get("label", f"{expected_op}-{index}"))
            missing = sorted(required_row_fields - set(row))
            if (
                row.get("index") != index
                or str(row.get("op")) != expected_op
                or str(row.get("label")) != expected_label
                or missing
            ):
                reason = (
                    f"step {index} was not the requested {expected_op} `{expected_label}`"
                    if not missing
                    else f"step {index} omitted {', '.join(missing)}"
                )
                failures.append(
                    {
                        "kind": "session_output_incomplete",
                        "session": name,
                        "label": expected_label,
                        "error": reason,
                    }
                )
                break
    return failures


def _call_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for name, session in sessions.items():
        if session.get("error"):
            raw_error = str(session["error"])
            protocol_changed = "ProtocolMutationError" in raw_error
            kind = "session_output_incomplete" if protocol_changed else "tracker_call_failed"
            error = (
                "the write path changed the shared engine protocol"
                if protocol_changed
                else _clean(raw_error)
            )
            failures.append(
                {"kind": kind, "session": name, "label": "start", "error": error}
            )
            continue
        for row in _steps(session):
            if not row.get("ok"):
                failures.append(
                    _record("tracker_call_failed", name, row, error=_clean(row.get("error")))
                )
                break
    return failures


def _watermark_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for name, session in sessions.items():
        previous = 0
        for row in _steps(session):
            reported = _reported(row).get("watermark")
            reference = int(row.get("reference_watermark", 0))
            if not isinstance(reported, int):
                continue
            if reported < previous:
                failures.append(
                    _record("watermark_went_backwards", name, row,
                            reported=reported, previous=previous)
                )
            elif reported != reference:
                kind = (
                    "watermark_ahead_of_the_log"
                    if reported > reference
                    else "watermark_behind_the_log"
                )
                failures.append(
                    _record(kind, name, row, reported=reported, reference=reference)
                )
            previous = max(previous, reported)
    return failures


def _release_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for name, session in sessions.items():
        for row in _steps(session):
            recoverable = {int(seq) for seq in row.get("recoverable_seqs", ())}
            for item in row.get("released_here", ()):
                seq = int(item.get("seq", 0))
                if seq in recoverable:
                    continue
                kind = (
                    "event_released_an_unlogged_write"
                    if str(item.get("by")) == "event"
                    else "waiter_released_an_unlogged_write"
                )
                failures.append(
                    _record(kind, name, row, seq=seq,
                            log_holds_up_to=max(recoverable, default=0))
                )
    return failures


def _expected_events(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    'What the feed is owed, worked out from the commits and the fsyncs.'

    expected: dict[int, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    refusal: str | None = None
    for row in rows:
        if isinstance(row.get("commit"), Mapping):
            pending.append(dict(row["commit"]))
        sync = row.get("sync")
        if not isinstance(sync, Mapping):
            continue
        if sync.get("err") is not None and refusal is None:
            refusal = _clean(sync["err"])
        if refusal is not None:


            covered = [commit for commit in pending if commit.get("requests_sync")]
            pending = [commit for commit in pending if not commit.get("requests_sync")]
        else:
            offset = int(sync.get("synced_offset", 0))
            covered = [c for c in pending if int(c.get("end_offset", 0)) <= offset]
            pending = [c for c in pending if int(c.get("end_offset", 0)) > offset]
        recoverable = {int(seq) for seq in row.get("recoverable_seqs", ())}
        for commit in covered:
            if not commit.get("requests_sync"):
                continue
            stranded = int(commit["seq"]) not in recoverable
            expected[int(commit["seq"])] = {
                "correlation_id": str(commit.get("correlation_id")),
                "size": int(commit.get("size", 0)),
                "key_count": int(commit.get("key_count", 0)),


                "err_required": stranded,
                "expected_err": refusal if stranded else None,
                "label": str(row.get("label")),
                "first_error": refusal if stranded else None,
            }
    return expected


def _event_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for name, session in sessions.items():
        if not session.get("listener", True):
            continue
        rows = _steps(session)
        expected = _expected_events(rows)
        commits = {
            int(row["commit"]["seq"]): dict(row["commit"])
            for row in rows
            if isinstance(row.get("commit"), Mapping)
        }
        actual: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            for event in row.get("events", ()):
                seq = event.get("seq")
                if isinstance(seq, int):
                    delivered = dict(event)
                    delivered["_label"] = str(row.get("label"))
                    actual.setdefault(seq, []).append(delivered)

        def note(kind: str, seq: int, due: Mapping[str, Any], **fields: Any) -> None:
            failures.append({"kind": kind, "session": name, "seq": seq,
                             "correlation_id": due["correlation_id"], **fields})

        for seq, due in sorted(expected.items()):
            delivered = actual.get(seq, [])
            errors = [item.get("err") for item in delivered]
            if not delivered:


                if due["err_required"]:
                    note("durability_event_missing_for_a_stranded_write", seq, due,
                         first_error=str(due["first_error"]))
                else:
                    note("durability_event_missing_for_a_landed_write", seq, due,
                         label=due["label"])
                continue
            if due["err_required"] and any(err is None for err in errors):
                note("durability_event_claimed_a_lost_write", seq, due)
            elif due["err_required"] and any(
                str(err) != str(due["expected_err"]) for err in errors
            ):
                note(
                    "durability_event_carried_wrong_error",
                    seq,
                    due,
                    reported=_clean(next(
                        err for err in errors if str(err) != str(due["expected_err"])
                    )),
                    expected=str(due["expected_err"]),
                )
            elif not due["err_required"] and any(err is not None for err in errors):
                note("durability_event_carried_a_false_error", seq, due,
                     label=due["label"],
                     reported=_clean(next(err for err in errors if err is not None)))
            if len(delivered) > 1:
                note("durability_event_duplicated", seq, due, events=len(delivered))
            for field in ("correlation_id", "size", "key_count"):
                if delivered[0].get(field) != due[field]:
                    note("durability_event_fields_wrong", seq, due,
                         field=field.replace("_", " "),
                         reported=str(delivered[0].get(field)),
                         expected=str(due[field]))
                    break
            actual_label = str(delivered[0].get("_label"))
            if actual_label != str(due["label"]):
                note(
                    "durability_event_at_wrong_step",
                    seq,
                    due,
                    actual_label=actual_label,
                    expected_label=str(due["label"]),
                )
        for seq in sorted(set(actual) - set(expected)):
            commit = commits.get(seq, {})
            delivered = actual[seq][0]
            common = {
                "session": name,
                "seq": seq,
                "correlation_id": str(
                    commit.get("correlation_id", delivered.get("correlation_id"))
                ),
            }
            if commit.get("requests_sync"):
                failures.append(
                    {
                        "kind": "durability_event_without_sync_completion",
                        **common,
                        "actual_label": str(delivered.get("_label")),
                        "reported": (
                            "no error"
                            if delivered.get("err") is None
                            else _clean(delivered.get("err"))
                        ),
                    }
                )
            else:
                failures.append(
                    {"kind": "durability_event_without_a_sync", **common}
                )
    return failures


def _waiter_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for name, session in sessions.items():
        rows = _steps(session)
        if not rows:
            continue
        closed, before = rows[-1], rows[-2] if len(rows) > 1 else rows[-1]
        fault = next(
            (
                row
                for row in rows
                if isinstance(row.get("sync"), Mapping) and row["sync"].get("err")
            ),
            None,
        )
        first_error = _clean(fault["sync"]["err"]) if fault is not None else None
        landed_at_close = int(closed.get("reference_watermark", 0))
        for waiter in closed.get("waiters", ()):
            common = {
                "session": name,
                "waiter": str(waiter.get("label")),
                "seq": int(waiter.get("seq", 0)),
            }
            resolutions = list(waiter.get("resolutions") or ())
            if not resolutions:
                failures.append({"kind": "waiter_left_unresolved_at_close", **common})
            elif len(resolutions) > 1:
                failures.append(
                    {
                        "kind": "waiter_resolved_more_than_once",
                        **common,
                        "resolutions": len(resolutions),
                    }
                )
            elif int(waiter.get("seq", 0)) <= landed_at_close and resolutions[0] is not None:
                failures.append(
                    {
                        "kind": "waiter_failed_a_landed_write",
                        **common,
                        "reported": _clean(resolutions[0]),
                    }
                )
            elif int(waiter.get("seq", 0)) > landed_at_close and resolutions[0] is None:
                failures.append(
                    {"kind": "waiter_resolved_without_required_error", **common}
                )
            elif (
                int(waiter.get("seq", 0)) > landed_at_close
                and first_error is not None
                and str(resolutions[0]) != first_error
            ):
                failures.append(
                    {
                        "kind": "waiter_error_did_not_match_first_failure",
                        **common,
                        "reported": _clean(resolutions[0]),
                        "expected": first_error,
                    }
                )
        landed = int(before.get("reference_watermark", 0))
        for waiter in before.get("waiters", ()):
            if not waiter.get("resolutions") and int(waiter.get("seq", 0)) <= landed:
                failures.append(
                    _record("waiter_left_parked_on_a_landed_write", name, before,
                            waiter=str(waiter.get("label")), seq=int(waiter.get("seq", 0)),
                            log_holds_up_to=landed)
                )
        if fault is not None:
            stuck = int(before.get("reference_watermark", 0))
            for waiter in before.get("waiters", ()):
                if not waiter.get("resolutions") and int(waiter.get("seq", 0)) > stuck:
                    failures.append(
                        {"kind": "waiter_blocked_after_the_log_broke", "session": name,
                         "waiter": str(waiter.get("label")),
                         "seq": int(waiter.get("seq", 0)), "first_error": first_error}
                    )
            for row in rows[int(fault.get("index", 0)) :]:
                reported = _reported(row).get("err")
                if str(reported) != first_error:
                    failures.append(
                        _record(
                            "error_not_latched",
                            name,
                            row,
                            reported="no error" if reported is None else _clean(reported),
                            expected=first_error,
                        )
                    )
                    break
        for row in rows:
            reported = _stat(row, "pending_waiters")
            actual = _outstanding(row)
            if reported != actual:
                failures.append(
                    _record("pending_waiter_count_wrong", name, row,
                            reported=str(reported), actual=actual)
                )
                break
    return failures


def _session_outcome(session: Mapping[str, Any]) -> dict[str, Any]:
    'What a session came to. Clients are read from the step before the close,     so a node that settles everybody only on the way out still reads as having     left them waiting.'

    rows = _steps(session)
    last = rows[-1] if rows else {}
    before = rows[-2] if len(rows) > 1 else last
    return {
        "released": sorted(int(seq) for seq in last.get("released_so_far", ())),
        "waiters": {
            str(waiter.get("label")): (_outcome(waiter), int(waiter.get("seq", 0)))
            for waiter in before.get("waiters", ())
        },
        "events": _stat(last, "durability_events"),
    }


def _invariance_failures(sessions: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    primary = sessions.get("primary")
    replica = sessions.get("replica")
    regrouped = sessions.get("regrouped")
    if not isinstance(primary, Mapping):
        return failures
    if isinstance(replica, Mapping):
        with_listener, without = _session_outcome(primary), _session_outcome(replica)
        for label, (outcome, seq) in with_listener["waiters"].items():
            other = without["waiters"].get(label, ("still waiting", seq))
            if outcome != "still waiting" and other[0] == "still waiting":
                failures.append(
                    {"kind": "wait_stalled_without_a_listener", "waiter": label, "seq": seq}
                )
        for left, right in zip(_steps(primary), _steps(replica)):
            if _reported(left).get("watermark") != _reported(right).get("watermark"):
                failures.append(
                    {
                        "kind": "state_differed_without_a_listener",
                        "label": str(left.get("label")),
                        "with_listener": str(_reported(left).get("watermark")),
                        "without_listener": str(_reported(right).get("watermark")),
                    }
                )
                break
        if with_listener["events"] != without["events"]:
            failures.append(
                {
                    "kind": "event_count_lost_without_a_listener",
                    "with_listener": str(with_listener["events"]),
                    "without_listener": str(without["events"]),
                }
            )
    if isinstance(regrouped, Mapping):
        grouped, spread = _session_outcome(primary), _session_outcome(regrouped)
        difference: tuple[str, str, str] | None = None
        if grouped["released"] != spread["released"]:
            difference = (
                "the writes it released",
                _listed(grouped["released"]),
                _listed(spread["released"]),
            )
        else:
            for label, (outcome, _seq) in grouped["waiters"].items():
                other = spread["waiters"].get(label, ("never registered", 0))[0]
                if other != outcome:
                    difference = (f"the client parked at `{label}`", outcome, other)
                    break
            if difference is None and grouped["events"] != spread["events"]:
                difference = (
                    "the durability events it counted",
                    str(grouped["events"]),
                    str(spread["events"]),
                )
        if difference is not None:
            failures.append(
                {
                    "kind": "grouping_changed_what_became_durable",
                    "subject": difference[0],
                    "when_grouped": difference[1],
                    "when_regrouped": difference[2],
                }
            )
    return failures


def _analyse(
    candidate: Mapping[str, Any], expected_sessions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    sessions = {
        str(name): dict(value)
        for name, value in dict(candidate.get("sessions", {})).items()
        if isinstance(value, Mapping)
    }
    stopped = _structure_failures(candidate, expected_sessions) or _call_failures(sessions)
    if stopped:
        return {bucket: list(stopped) for bucket in BUCKETS.values()}
    return {
        "watermark_failures": _watermark_failures(sessions),
        "release_failures": _release_failures(sessions),
        "event_failures": _event_failures(sessions),
        "waiter_failures": _waiter_failures(sessions),
        "invariance_failures": _invariance_failures(sessions),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the node console shows when a session did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the drill box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the node ended without saying why"
    return f"the node stopped before the session finished: {_clean(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private sessions against this workspace and bucket what broke.'

    def compute() -> Mapping[str, Any]:
        sessions = private_sessions(PRIVATE_SEED)
        candidate = PROJECT.invoke(artifact_dir, {"sessions": sessions})
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, sessions)
        analysis["case"] = {
            "run": "release",
            "sessions": [str(session["name"]) for session in sessions],
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _scene(path)
        records.append(
            {"record": f"project_records/{path.name}", "scene": raw.get("scene")}
        )
    return {
        "summary": "The write path and the sessions the storage team replays before a change ships.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "engine_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "engine").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded session against this workspace and report what happened.'

    raw = _scene(Path(specification))
    record_id = str(raw.get("record_id", Path(specification).stem))
    session = public_session(record_id)
    candidate = PROJECT.invoke(Path(artifact_dir), {"sessions": [session]})
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} session could not run this write path to the end.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    result = dict(dict(candidate.get("sessions", {})).get(record_id, {}))
    return {
        "summary": f"The {record_id} session ran against this write path.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "durability_listener_attached": bool(session["listener"]),
            "commits_per_fsync_at_the_start": int(session["sync_grouping"]),
            "steps": len(result.get("steps", ())),
        },
        "public": {
            "step_rows": result.get("steps", []),
            "engine_error": result.get("error"),
        },
    }
