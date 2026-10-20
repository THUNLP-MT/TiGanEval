'Deterministic, sandboxed review of one schedule-engine workspace.'

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import build_program, operator_notes, zones_used


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("recur/schedule.py", "recur/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-recur-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "seed": 33, "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "berlin-standup-march": {"profile": "standup", "seed": 4, "scale": 1},
    "transition-weekend-runbook": {"profile": "transitions", "seed": 9, "scale": 1},
    "mobile-round-trip": {"profile": "export", "seed": 15, "scale": 1},
    "subscribed-feeds-night": {"profile": "subscription", "seed": 21, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "local_time_preserved": "local_failures",
    "transition_occurrence_policy": "transition_failures",
    "exported_rule_round_trip": "export_failures",
    "merged_feed_deduplication": "merge_failures",
    "window_slice_partition": "paging_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: ModuleType | None = None


_NEAR = timedelta(hours=12)


def protocol() -> ModuleType:
    'The frozen contract module, loaded from the pristine workspace.'
    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "recur" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_recur_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the frozen contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


class Rule:
    "One rule of a program, in the harness's own terms."

    def __init__(self, value: Mapping[str, Any]):
        self.summary = str(value["summary"])
        self.zone = str(value["zone"])
        self.wall_start = datetime.fromisoformat(str(value["wall_start"]))
        self.period = str(value["period"])
        self.interval = int(value.get("interval", 1))
        raw_count, raw_until = value.get("count"), value.get("until")
        self.count = None if raw_count is None else int(raw_count)
        self.until = None if raw_until is None else datetime.fromisoformat(str(raw_until))


def _resolve(wall: datetime, zone: str) -> datetime:
    'The absolute reading one wall-clock reading really happens at.'

    api = protocol()
    offsets = api.local_offsets(wall, zone)
    if len(offsets) == 1:
        return wall - timedelta(seconds=offsets[0])
    if len(offsets) > 1:
        return wall - timedelta(seconds=max(offsets))
    return wall - timedelta(seconds=min(api.zone_for(zone).offsets))


def _series(rule: Rule, horizon: datetime | None = None) -> list[tuple[datetime, datetime]]:
    'The series as (wall-clock reading, absolute reading) pairs, up to `horizon`.'

    api = protocol()
    step = api.PERIOD_STEP[rule.period] * rule.interval
    latest = (
        None if horizon is None
        else horizon + timedelta(seconds=max(api.zone_for(rule.zone).offsets))
    )
    wall = rule.wall_start
    rows: list[tuple[datetime, datetime]] = []
    for index in range(4000):
        if rule.count is not None and index >= rule.count:
            break
        if latest is not None and wall >= latest:
            break
        instant = _resolve(wall, rule.zone)
        if rule.until is not None and instant >= rule.until:
            break
        rows.append((wall, instant))
        wall += step
    return rows


def _window(value: Mapping[str, Any]) -> Any:
    return protocol().Window.from_mapping(value)


def _instants(rows: Any) -> tuple[list[datetime], str | None]:
    'The readings an operation returned, or a note about what came back.'
    values: list[datetime] = []
    for row in rows or ():
        raw = dict(row).get("instant")
        if raw is None:
            return values, str(dict(row).get("returned", "nothing"))[:120]
        values.append(datetime.fromisoformat(str(raw)))
    return values, None


_CARRIED_FIELDS = (
    "wall_kind",
    "affected_wall",
    "slice_seconds",
    "outlives_table",
    "stretch_at_table_edge",
)


def _trusted_records(
    engine: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Join candidate results to the immutable operation that requested them.'

    raw_records = engine.get("records")
    if not isinstance(raw_records, (list, tuple)):
        raise ValueError("the schedule engine returned no operation records")
    if len(raw_records) != len(program):
        raise ValueError(
            f"the schedule engine returned {len(raw_records)} records for "
            f"{len(program)} operations"
        )

    records: list[dict[str, Any]] = []
    for index, (raw_record, raw_operation) in enumerate(zip(raw_records, program)):
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"operation {index} returned a non-record")
        operation = dict(raw_operation)
        record = dict(raw_record)
        kind = str(operation.get("type", ""))
        if int(record.get("index", -1)) != index or str(record.get("type", "")) != kind:
            raise ValueError(f"operation {index} returned under another identity")

        record.update({
            "type": kind,
            "index": index,
            "label": str(operation.get("label", f"{kind}-{index}")),
            "check": str(operation.get("check", "")),
            "profile": operation.get("profile"),
        })
        for field in _CARRIED_FIELDS:
            record.pop(field, None)
            if field in operation:
                record[field] = operation[field]

        if kind in ("expand", "paging", "export"):
            record["rule"] = dict(operation["rule"])
        if kind == "merge":
            record["rules"] = [dict(rule) for rule in operation["rules"]]
        if kind in ("expand", "paging", "merge"):
            record["window"] = dict(operation["window"])

        if kind == "paging" and record.get("ok"):
            window = _window(dict(operation["window"]))
            expected_pieces = protocol().slice_window(
                window, int(operation["slice_seconds"])
            )
            raw_slices = record.get("slices")
            if not isinstance(raw_slices, (list, tuple)) or len(raw_slices) != len(expected_pieces):
                returned = len(raw_slices) if isinstance(raw_slices, (list, tuple)) else 0
                record.update({
                    "ok": False,
                    "error": (
                        f"the dispatcher received {returned} slices where its window "
                        f"defines {len(expected_pieces)}"
                    ),
                })
            else:
                record["slices"] = [
                    {
                        **dict(raw_slice),
                        "window": piece.as_dict(),
                    }
                    for raw_slice, piece in zip(raw_slices, expected_pieces)
                    if isinstance(raw_slice, Mapping)
                ]
                if len(record["slices"]) != len(expected_pieces):
                    record.update({"ok": False, "error": "a dispatcher slice was not a record"})

        if kind == "export" and record.get("ok"):
            record.pop("read_back", None)
            record.pop("read_error", None)
            try:
                read_back = protocol().parse_rule_text(str(record.get("text", "")))
                record["read_back"] = read_back.as_dict()
            except Exception as exc:
                record["read_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"

        records.append(record)
    return records


def _local(instant: datetime, zone: str) -> str:
    try:
        return protocol().from_utc(instant, zone).isoformat()
    except Exception:
        return instant.isoformat()


def _call_failure(record: Mapping[str, Any], rule: Rule | None, note: str | None = None) -> dict[str, Any]:
    return {
        "kind": "schedule_call_failed",
        "label": str(record.get("label")),
        "summary": "" if rule is None else rule.summary,
        "zone": "" if rule is None else rule.zone,
        "error": _plain(str(note or record.get("error") or "the engine stopped without saying why")),
    }


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _plain(line: str) -> str:
    'One line as the console shows it, with the throwaway path stripped.'
    text = _DIRECTORY_PART.sub("", str(line)).strip()
    if any(word in text.lower() for word in FORBIDDEN_VOCABULARY):
        return "the engine stopped without saying why"
    return text[:200]


def _by_check(records: Sequence[Mapping[str, Any]], check: str) -> list[Mapping[str, Any]]:
    return [record for record in records if str(record.get("check")) == check]


def _fail(kind: str, common: Mapping[str, Any], **fields: Any) -> dict[str, Any]:
    'One failure record: its kind, the operation it was measured on, its own fields.'
    return {"kind": kind, **dict(common), **fields}


def _at(instant: datetime, zone: str) -> str:
    'One reading as the calendar view prints it to support.'
    return _local(instant, zone).replace("T", " ")


def _clock(instant: datetime, zone: str) -> str:
    "One reading's time of day in `zone`."
    return _local(instant, zone)[11:16]


def _local_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in (
        item for item in records if str(item.get("check")) in ("local", "paging")
    ):
        rule = Rule(dict(record["rule"])) if record.get("rule") else None
        if not record.get("ok") or rule is None:
            if rule is not None and record.get("stretch_at_table_edge"):


                failures.append(_fail(
                    "late_stretch_unanswered",
                    {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone},
                    error=_plain(str(record.get("error") or "the engine stopped without saying why")),
                ))
            elif rule is not None and record.get("outlives_table"):


                failures.append(_fail(
                    "standing_series_unanswered",
                    {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone},
                    error=_plain(str(record.get("error") or "the engine stopped without saying why")),
                ))
            else:
                failures.append(_call_failure(record, rule))
            continue
        got, note = _instants(record.get("occurrences"))
        if note is not None:
            failures.append(_call_failure(record, rule, f"the engine handed back {note}"))
            continue
        window = _window(dict(record["window"]))
        expected = [
            (wall, instant)
            for wall, instant in _series(rule, window.end)
            if window.contains(instant)
        ]
        common = {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone}
        if len(got) != len(expected):
            failures.append(
                _fail("series_length_wrong", common, produced=len(got), expected=len(expected))
            )
            continue
        for instant, (wall, reference) in zip(got, expected):
            if instant != reference:
                failures.append(_fail(
                    "occurrence_drifted_from_local_time", common,
                    date=wall.date().isoformat(), expected_local=wall.strftime("%H:%M"),
                    observed_local=_clock(instant, rule.zone),
                ))
    return failures


def _transition_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in _by_check(records, "transition"):
        rule = Rule(dict(record["rule"])) if record.get("rule") else None
        if not record.get("ok") or rule is None:
            failures.append(_call_failure(record, rule))
            continue
        got, note = _instants(record.get("occurrences"))
        if note is not None:
            failures.append(_call_failure(record, rule, f"the engine handed back {note}"))
            continue
        wall = datetime.fromisoformat(str(record["affected_wall"]))
        kind = str(record.get("wall_kind"))
        expected = _resolve(wall, rule.zone)
        window = _window(dict(record["window"]))
        expected_rows = [
            (reading, instant)
            for reading, instant in _series(rule, window.end)
            if window.contains(instant)
        ]
        expected_series = [instant for _reading, instant in expected_rows]
        offsets = protocol().zone_for(rule.zone).offsets
        low = wall - timedelta(seconds=max(offsets)) - _NEAR
        high = wall - timedelta(seconds=min(offsets)) + _NEAR
        near = [instant for instant in got if low <= instant <= high]
        common = {
            "label": str(record.get("label")),
            "summary": rule.summary,
            "zone": rule.zone,
            "date": wall.date().isoformat(),
            "wall": wall.strftime("%H:%M"),
        }
        if not near:
            gone = "gap_occurrence_missing" if kind == "gap" else "ambiguous_occurrence_missing"
            failures.append(_fail(gone, common))
        elif len(near) > 1:
            duplicated = (
                "gap_occurrence_duplicated"
                if kind == "gap"
                else "ambiguous_occurrence_duplicated"
            )
            failures.append(_fail(duplicated, common, times=len(near)))
        elif near[0] != expected:
            observed = _clock(near[0], rule.zone)
            if kind == "gap":
                failures.append(_fail(
                    "gap_occurrence_moved", common,
                    observed_local=observed, expected_local=_clock(expected, rule.zone),
                ))
            else:
                failures.append(_fail(
                    "ambiguous_occurrence_moved", common, observed_local=observed,
                    minutes_apart=int(abs((near[0] - expected).total_seconds()) // 60),
                ))
        if len(got) != len(expected_series):
            failures.append(_fail(
                "transition_series_length_wrong",
                common,
                produced=len(got),
                expected=len(expected_series),
            ))
        elif got != expected_series:
            position = next(
                index
                for index, (observed, expected_instant) in enumerate(
                    zip(got, expected_series)
                )
                if observed != expected_instant
            )
            _reading, expected_instant = expected_rows[position]
            failures.append(_fail(
                "transition_series_occurrence_moved",
                common,
                position=position + 1,
                observed_at=_at(got[position], rule.zone),
                expected_at=_at(expected_instant, rule.zone),
            ))
    return failures


_EXPORT_DETAILS: Mapping[str, str] = {
    "summary": "series_name_changed_in_export", "period": "series_repeat_changed_in_export",
    "interval": "series_repeat_changed_in_export",
}


def _export_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in _by_check(records, "export"):
        rule = Rule(dict(record["rule"])) if record.get("rule") else None
        if not record.get("ok") or rule is None:
            failures.append(_call_failure(record, rule))
            continue
        common = {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone}
        if record.get("read_error") or not record.get("read_back"):
            refusal = str(record.get("read_error") or "the file came back empty")
            failures.append(_fail("export_unreadable", common, reason=_plain(refusal)))
            continue
        read_back = dict(record["read_back"])
        if str(read_back.get("zone")) != rule.zone:
            failures.append(
                _fail("zone_lost_in_export", common, read_zone=str(read_back.get("zone")))
            )
            continue
        read_start = datetime.fromisoformat(str(read_back["wall_start"]))
        if read_start != rule.wall_start:
            failures.append(_fail(
                "start_moved_in_export", common,
                expected_start=rule.wall_start.isoformat(sep=" "),
                read_start=read_start.isoformat(sep=" "),
            ))
            continue
        changed = [name for name in _EXPORT_DETAILS
                   if str(getattr(rule, name)) != str(read_back.get(name))]
        if changed:
            field = changed[0]
            failures.append(_fail(
                _EXPORT_DETAILS[field], common, field=field,
                expected_value=str(getattr(rule, field)), read_value=str(read_back.get(field)),
            ))
            continue
        raw_count = read_back.get("count")
        read_count = None if raw_count is None else int(raw_count)
        expected_is_counted = rule.count is not None
        read_is_counted = read_count is not None
        if expected_is_counted != read_is_counted:
            expected_bound = (
                f"has {rule.count} occurrences"
                if expected_is_counted
                else f"ends at {rule.until.isoformat(sep=' ')}"
            )
            raw_read_until = read_back.get("until")
            read_bound = (
                f"has {read_count} occurrences"
                if read_is_counted
                else f"ends at {datetime.fromisoformat(str(raw_read_until)).isoformat(sep=' ')}"
            )
            failures.append(_fail(
                "series_bound_kind_changed_in_export", common,
                expected_bound=expected_bound, read_bound=read_bound,
            ))
            continue
        if expected_is_counted and read_count != rule.count:
            failures.append(_fail(
                "series_count_changed_in_export", common,
                expected_value=str(rule.count), read_value=str(read_count),
            ))
            continue
        raw_until = read_back.get("until")
        read_until = None if raw_until is None else datetime.fromisoformat(str(raw_until))
        if read_until != rule.until:
            both = read_until is not None and rule.until is not None
            moved = int(abs((read_until - rule.until).total_seconds()) // 60) if both else 0
            landed = read_until.isoformat(sep=" ") if read_until else "no end at all"
            failures.append(_fail("series_end_moved", common, minutes_moved=moved, read_end=landed))
            continue
        if str(record.get("text_again")) != str(record.get("text")):
            failures.append(_fail("export_not_stable", common))
    return failures


def _merge_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in _by_check(records, "merge"):
        rules = [Rule(dict(rule)) for rule in record.get("rules", ())]
        rule = rules[0] if rules else None
        if not record.get("ok") or rule is None:
            failures.append(_call_failure(record, rule))
            continue
        merged, note = _instants(record.get("merged"))
        if note is not None:
            failures.append(_call_failure(record, rule, f"the engine handed back {note}"))
            continue
        window = _window(dict(record["window"]))
        union: list[datetime] = []
        for feed_rule in rules:
            union.extend(
                instant
                for _reading, instant in _series(feed_rule, window.end)
                if window.contains(instant)
            )
        common = {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone}
        counts = Counter(merged)
        repeated = [instant for instant, times in sorted(counts.items()) if times > 1]
        if repeated:
            failures.append(_fail(
                "duplicate_reminder_in_merge", common,
                times=counts[repeated[0]], reminder_at=_at(repeated[0], rule.zone),
            ))
            continue
        missing = sorted(set(union) - set(merged))
        if missing:
            failures.append(_fail(
                "merged_reminder_missing", common,
                reminder_at=_at(missing[0], rule.zone), short_by=len(missing),
            ))
            continue
        unexpected = sorted(set(merged) - set(union))
        if unexpected:
            failures.append(_fail(
                "merged_reminder_unexpected", common, reminder_at=_at(unexpected[0], rule.zone)
            ))
            continue
        if merged != sorted(merged):
            failures.append(_fail("merge_not_ascending", common, reminders=len(merged)))
    return failures


def _paging_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in _by_check(records, "paging"):
        rule = Rule(dict(record["rule"])) if record.get("rule") else None
        if not record.get("ok") or rule is None:
            failures.append(_call_failure(record, rule))
            continue
        whole, note = _instants(record.get("occurrences"))
        if note is not None:
            failures.append(_call_failure(record, rule, f"the engine handed back {note}"))
            continue
        window = _window(dict(record["window"]))
        common = {"label": str(record.get("label")), "summary": rule.summary, "zone": rule.zone}
        outside = [instant for instant in whole if not window.contains(instant)]
        pieces: list[tuple[Any, list[datetime]]] = []
        broken = False
        for piece in record.get("slices", ()):
            values, piece_note = _instants(dict(piece).get("occurrences"))
            if piece_note is not None:
                failures.append(_call_failure(record, rule, f"the engine handed back {piece_note}"))
                broken = True
                break
            piece_window = _window(dict(dict(piece)["window"]))
            pieces.append((piece_window, values))
            outside.extend(value for value in values if not piece_window.contains(value))
        if broken:
            continue
        if outside:
            failures.append(_fail(
                "occurrence_outside_window", common,
                reminder_at=_at(outside[0], rule.zone), stray=len(outside),
            ))
            continue
        walked = Counter(instant for _piece, values in pieces for instant in values)
        asked = Counter(whole)
        surplus = walked - asked
        extra = sorted(surplus.elements())
        if extra:
            failures.append(_fail(
                "slice_duplicated_occurrence", common,
                reminder_at=_at(extra[0], rule.zone),
                duplicated_reminders=len(surplus),
                extra_deliveries=sum(surplus.values()),
            ))
            continue
        dropped = sorted((asked - walked).elements())
        if dropped:
            failures.append(_fail(
                "slice_dropped_occurrence", common,
                reminder_at=_at(dropped[0], rule.zone), never_sent=len(dropped),
            ))
    return failures


def _analyse(
    engine: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    records = _trusted_records(engine, program)
    return {
        "records": records,
        "local_failures": _local_failures(records),
        "transition_failures": _transition_failures(records),
        "export_failures": _export_failures(records),
        "merge_failures": _merge_failures(records),
        "paging_failures": _paging_failures(records),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(engine: Mapping[str, Any]) -> str:
    'The one line the schedule console shows when a run did not finish.'
    reported = str(engine.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still working after {limit} and the box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(engine.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the engine ended without saying why"
    return f"the schedule engine stopped part way through: {_plain(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the release program against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(
            str(PRIVATE_CASE["profile"]),
            int(PRIVATE_CASE["seed"]),
            int(PRIVATE_CASE["scale"]),
        )
        engine = PROJECT.invoke(artifact_dir, {"operations": list(program)})
        if not engine.get("ok"):
            analysis = dict(failed_analysis(_console_error(engine), tuple(BUCKETS.values())))
            diagnostic = engine.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            try:
                analysis = _analyse(engine, program)
            except Exception as exc:
                analysis = dict(failed_analysis(
                    f"the schedule engine returned unusable results: {_plain(str(exc))}",
                    tuple(BUCKETS.values()),
                ))
        analysis["case"] = {"program": "release", "zones": zones_used(program)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    api = protocol()
    scenes = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        case = PUBLIC_RECORDS.get(record_id, {})
        program = (
            build_program(str(case["profile"]), int(case["seed"]), int(case["scale"]))
            if case
            else []
        )
        scenes.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "steps": [str(operation["label"]) for operation in program],
            "zones": zones_used(program),
        })
    engine_files = sorted(path.relative_to(root).as_posix() for path in (root / "recur").glob("*.py"))
    return {
        "summary": "The schedule engine, the zones it sells into, and the scenes the team replays before a change goes out.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "engine_files": engine_files,
            "editable_files": list(EDITABLE_FILES),
            "zone_table_covers": {
                "from": api.TABLE_FROM.isoformat(),
                "until": api.TABLE_UNTIL.isoformat(),
                "outside_this_range": "the table has no entry and refuses the reading",
            },
            "zones": api.describe_zones(),
        },
        "records": scenes,
    }


def _public_row(record: Mapping[str, Any]) -> dict[str, Any]:
    'One step of a scene as the console shows it.'

    kind = str(record.get("type"))
    row: dict[str, Any] = {
        "step": record.get("label"), "operation": kind,
        "completed": bool(record.get("ok")), "error": record.get("error"),
    }
    row.update(
        (carried, record[carried])
        for carried in ("rule", "rules", "window", "slice_seconds")
        if record.get(carried) is not None
    )
    if kind in ("expand", "paging"):
        row["reminders_this_build_would_send"] = record.get("occurrences")
    if kind == "paging":
        row["one_piece_at_a_time"] = record.get("slices")
    if kind == "export":
        row["written_out"] = record.get("text")
        row["read_back_by_the_importer"] = record.get("read_back") or record.get("read_error")
        row["written_out_again"] = record.get("text_again")
    if kind == "merge":
        row["each_feed_on_its_own"] = record.get("feeds")
        row["what_the_user_receives"] = record.get("merged")
    return row


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded scene against this workspace and report what happened.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    program = build_program(str(case["profile"]), int(case["seed"]), int(case["scale"]))
    engine = PROJECT.invoke(Path(artifact_dir), {"operations": list(program)})
    measurements = {
        "record_id": record_id,
        "scene": raw.get("scene"),
        "zones": zones_used(program),
        "steps": len(program),
    }
    if not engine.get("ok"):
        return {
            "summary": f"The {record_id} scene could not be run against this engine to the end.",
            "measurements": measurements,
            "operator_notes": list(operator_notes(str(case["profile"]))),
            "public": {
                "execution_error": engine.get("error", "unknown failure"),
                "diagnostic": engine.get("diagnostic"),
            },
        }
    try:
        records = _trusted_records(engine, program)
    except Exception as exc:
        return {
            "summary": f"The {record_id} scene returned results the console could not read.",
            "measurements": measurements,
            "operator_notes": list(operator_notes(str(case["profile"]))),
            "public": {"execution_error": _plain(str(exc))},
        }
    return {
        "summary": f"The {record_id} scene ran against this engine.",
        "measurements": measurements,
        "operator_notes": list(operator_notes(str(case["profile"]))),
        "public": {"steps": [_public_row(record) for record in records]},
    }
