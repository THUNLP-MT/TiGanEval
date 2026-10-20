'Deterministic, sandboxed measurement of one nightly catalogue load.'

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
)

from .workload import (
    CHECKPOINT_INTERVAL,
    TRANSACTION_SLACK,
    build_next_day_source,
    build_program,
    build_source,
    reference_outcome,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("loader/importer.py", "loader/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-bulk-import-",
    timeout=60.0,
)


PRIVATE_WORKLOAD: Mapping[str, Any] = {"profile": "release", "seed": 41, "scale": 2}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "interrupted-load": {"profile": "interruption", "seed": 4, "scale": 1},
    "dirty-export": {"profile": "dirty", "seed": 9, "scale": 1},
    "capacity-load": {"profile": "capacity", "seed": 15, "scale": 1},
    "rerun-drill": {"profile": "rerun", "seed": 22, "scale": 1},
}

BUCKETS: Mapping[str, str] = {
    "exactly_once_import_completion": "completion_failures",
    "invalid_row_rejection_integrity": "rejection_failures",
    "resume_state_integrity": "resume_failures",
    "bounded_transaction_work": "work_failures",
    "clean_idempotent_completion": "terminal_failures",
}

_CACHE = AnalysisCache()


def _payload(profile: str, seed: int, scale: int) -> Mapping[str, Any]:
    events = build_program(profile, seed, scale)
    builders = {
        "primary": lambda: build_source(seed, scale, variant="primary"),
        "foreign": lambda: build_source(seed + 1, scale, variant="foreign"),
        "next_day": lambda: build_next_day_source(seed, scale),
    }
    wanted = {"primary"} | {str(event.get("source", "primary")) for event in events}
    return {
        "sources": {name: builders[name]() for name in sorted(wanted)},
        "checkpoint_interval": CHECKPOINT_INTERVAL,
        "events": events,


        "initial_state": {
            "tables": {"products": {}, "variants": {}},
            "meta": {"warehouse_window": {"generation": int(seed)}},
        },
    }


def _transaction_allowance(total_rows: int) -> int:
    return math.ceil(int(total_rows) / CHECKPOINT_INTERVAL) + TRANSACTION_SLACK


def _row_total(tables: Mapping[str, Any]) -> int:
    return sum(len(dict(rows)) for rows in dict(tables).values())


def _table_differences(
    expected: Mapping[str, Mapping[str, Any]],
    actual: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    for table in sorted(set(expected).union(actual)):
        expected_rows = dict(expected.get(table, {}))
        actual_rows = dict(actual.get(table, {}))
        missing = sorted(set(expected_rows).difference(actual_rows))
        unexpected = sorted(set(actual_rows).difference(expected_rows))
        changed = sorted(
            key
            for key in set(expected_rows).intersection(actual_rows)
            if expected_rows[key] != actual_rows[key]
        )
        if missing or unexpected or changed:
            differences[table] = {
                "missing_count": len(missing),
                "unexpected_count": len(unexpected),
                "changed_count": len(changed),
                "sample_missing": missing[:3],
                "sample_unexpected": unexpected[:3],
                "sample_changed": changed[:3],
            }
    return differences


def _difference_counts(differences: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    return {
        name: sum(int(value.get(name, 0)) for value in differences.values())
        for name in ("missing_count", "unexpected_count", "changed_count")
    }


def _durable_state_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, int]:
    table_differences = _table_differences(
        dict(before.get("tables", {})), dict(after.get("tables", {}))
    )
    table_counts = _difference_counts(table_differences)
    before_meta = dict(before.get("meta", {}))
    after_meta = dict(after.get("meta", {}))
    metadata_changes = sum(
        1
        for key in set(before_meta).union(after_meta)
        if (
            key not in before_meta
            or key not in after_meta
            or before_meta[key] != after_meta[key]
        )
    )
    catalogue_changes = sum(table_counts.values())
    return {
        "catalogue_rows_changed": catalogue_changes,
        "metadata_entries_changed": metadata_changes,
        "durable_state_changes": catalogue_changes + metadata_changes,
    }


def _raised_kind(error: Any) -> str:
    'Which failure a run that returned no report handed back.'

    text = str(error or "")
    if text.startswith("SourceInterrupted"):
        return "run_raised_the_feed_error"
    if text.startswith("StorageFailure"):
        return "run_raised_the_warehouse_error"
    return "run_raised_its_own_error"


_PROCESS_DEATH_PREFIXES = ("candidate process exited", "candidate returned")


def _reportable_error(error: str) -> str:
    'The failure text the owner reads off a replay that produced no timeline.'

    text = str(error).strip()
    if text.startswith(_PROCESS_DEATH_PREFIXES):
        return "the loader's process died before it returned anything"
    return text


def _stub_analysis(error: str) -> dict[str, Any]:
    'The measurement to report when the loader could not be run at all.'

    failure = {
        "kind": CANDIDATE_FAILURE,
        "label": "first-attempt",
        "error": _reportable_error(error),
    }
    analysis: dict[str, Any] = {"harness_error": str(error), "records": []}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _analyse(
    candidate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    sources: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = list(sources["primary"])
    reference = reference_outcome(rows)


    next_day_rows = list(sources.get("next_day") or ())
    next_day_reference = (
        reference_outcome(next_day_rows) if next_day_rows else reference
    )
    references_by_role = {
        "primary": reference,
        "next_day": next_day_reference,
    }
    interval = CHECKPOINT_INTERVAL
    admissible = _row_total(reference["tables"])
    per_table = {
        table: len(dict(entries)) for table, entries in dict(reference["tables"]).items()
    }
    records = [
        dict(record)
        for record in candidate.get("records", ())
        if isinstance(record, Mapping) and record.get("type") == "import"
    ]
    plan = {str(event.get("label")): dict(event) for event in events}
    expected_role_by_night: dict[str, str] = {}
    for event in events:
        role = str(event.get("source", "primary"))
        if role not in references_by_role:
            continue
        night = str(event.get("night", "load-night"))
        previous_role = expected_role_by_night.setdefault(night, role)
        if previous_role != role:
            raise ValueError(
                f"night {night!r} mixes catalogue roles {previous_role!r} and {role!r}"
            )

    completion: list[dict[str, Any]] = []
    rejection: list[dict[str, Any]] = []
    resume: list[dict[str, Any]] = []
    work: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []

    reported_rejections_by_night: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
    rows_written_before_completion = 0
    runs_that_stopped_early = 0
    runs_counted_before_completion: list[str] = []
    load_finished = False
    previous_row_total: int | None = None
    previous_database: dict[str, Any] | None = None
    catalogue_export_records: list[dict[str, Any]] = []
    next_day_record: dict[str, Any] | None = None

    for record in records:
        label = str(record.get("label"))
        night = str(record.get("night", "load-night"))
        export = str(record.get("export_name") or record.get("source"))
        spec = plan.get(label, {})
        faulted = (
            spec.get("fail_after") is not None
            or spec.get("fail_on_commit") is not None
            or bool(spec.get("fail_on_cleanup", False))
        )
        export_role = str(spec.get("source", "primary"))
        foreign = export_role == "foreign"
        if export_role == "primary":
            catalogue_export_records.append(record)
        elif export_role == "next_day":
            next_day_record = record
        storage = dict(record.get("storage", {}))
        meter = dict(record.get("meter", {}))
        database = dict(record.get("database", {}))
        row_total = _row_total(database)
        rows_written = int(storage.get("rows_written", 0))
        report = dict(record.get("report") or {})
        status = str(report.get("status", ""))
        ran = bool(record.get("ok"))


        if export_role == "primary" and not load_finished:
            rows_written_before_completion += rows_written
            runs_counted_before_completion.append(label)
            if faulted:
                runs_that_stopped_early += 1


        if not ran:
            completion.append(
                {
                    "kind": _raised_kind(record.get("error")),
                    "label": label,
                    "export": export,
                    "error": str(record.get("error") or "no error was reported"),
                }
            )
        else:
            if export_role in references_by_role:


                for entry in report.get("rejected", ()):
                    reported_rejections_by_night[night].append(
                        (entry.get("index"), entry.get("reason"))
                    )
            if (
                not faulted
                and export_role == "primary"
                and label != "scheduled-rerun"
                and status != "completed"
            ):
                completion.append(
                    {
                        "kind": "import_did_not_complete",
                        "label": label,
                        "export": export,
                        "status": status,
                    }
                )


        violations = list(record.get("committed_invariant_violations", ()))
        if violations:
            rejection.append(
                {
                    "kind": "invariant_violated_in_committed_state",
                    "label": label,
                    "commits_with_violations": len(violations),
                    "violations": violations[:4],
                }
            )


        if foreign:
            state_changes = _durable_state_changes(
                dict(record.get("durable_state_before", {})),
                dict(record.get("durable_state_after", {})),
            )
            if state_changes["durable_state_changes"]:
                resume.append(
                    {
                        "kind": "foreign_source_changed_state",
                        "label": label,
                        "export": export,
                        "status": status if ran else "no report",
                        "rows_written": rows_written,
                        **state_changes,
                    }
                )
            if not ran:
                resume.append(
                    {
                        "kind": "foreign_source_returned_no_report",
                        "label": label,
                        "export": export,
                        "error": str(record.get("error") or "no error was reported"),
                    }
                )
            elif status != "refused":
                resume.append(
                    {
                        "kind": "foreign_source_not_refused",
                        "label": label,
                        "export": export,
                        "status": status,
                    }
                )
        elif export_role == "primary" and spec.get("fail_after") is not None:


            boundary = max(0, int(spec["fail_after"]) - interval)
            required = _row_total(reference_outcome(rows[:boundary])["tables"])
            if row_total < required:
                resume.append(
                    {
                        "kind": "progress_not_checkpointed",
                        "label": label,
                        "retention_boundary_row": boundary,
                        "source_retention_rows": interval,
                        "durable_rows_required": required,
                        "committed_rows": row_total,
                    }
                )


        allowance = _transaction_allowance(int(record.get("total_rows") or len(rows)))
        untracked = int(storage.get("durable_entries_changed_without_transaction", 0))
        if untracked:
            work.append(
                {
                    "kind": "durable_state_changed_without_transaction",
                    "label": label,
                    "durable_entries_changed_without_transaction": untracked,
                    "catalogue_rows_changed_without_transaction": int(
                        storage.get("catalogue_rows_changed_without_transaction", 0)
                    ),
                    "metadata_entries_changed_without_transaction": int(
                        storage.get("metadata_entries_changed_without_transaction", 0)
                    ),
                    "sample_entries_changed_without_transaction": list(
                        storage.get("sample_entries_changed_without_transaction", ())
                    )[:6],
                }
            )
        first_mark = meter.get("first_commit_mark")
        if isinstance(first_mark, Mapping) and int(first_mark.get("rows_read", 0)) > interval:
            work.append(
                {
                    "kind": "source_buffered_before_first_commit",
                    "label": label,
                    "rows_read_at_first_commit": first_mark.get("rows_read"),
                    "rows_in_the_export": int(record.get("total_rows") or len(rows)),
                    "checkpoint_interval": interval,
                }
            )
        if int(storage.get("max_rows_per_transaction", 0)) > interval:
            work.append(
                {
                    "kind": "transaction_batch_too_large",
                    "label": label,
                    "rows_in_largest_transaction": storage.get("max_rows_per_transaction"),
                    "rows_per_transaction_allowance": interval,
                }
            )
        if int(storage.get("transactions", 0)) > allowance:
            work.append(
                {
                    "kind": "transaction_count_exceeded",
                    "label": label,
                    "transactions_opened": storage.get("transactions"),
                    "transaction_allowance": allowance,
                }
            )


        if label == "scheduled-rerun":
            if not ran or status != "completed":
                terminal.append(
                    {
                        "kind": "repeat_import_did_not_complete",
                        "label": label,
                        "status": status if ran else "no report",
                    }
                )
            repeat_differences = _table_differences(previous_database or {}, database)
            if repeat_differences:
                repeat_counts = _difference_counts(repeat_differences)
                terminal.append(
                    {
                        "kind": "repeat_import_rewrote_database",
                        "label": label,
                        "rows_the_export_admits": admissible,
                        "rows_in_the_catalogue_before": previous_row_total,
                        "rows_in_the_catalogue_after": row_total,
                        "rows_missing_after_repeat": repeat_counts["missing_count"],
                        "rows_unexpected_after_repeat": repeat_counts["unexpected_count"],
                        "rows_changed_after_repeat": repeat_counts["changed_count"],
                        "catalogue_differences_after_repeat": sum(
                            repeat_counts.values()
                        ),
                        "differences": repeat_differences,
                    }
                )
        handoff = dict(record.get("night_handoff") or {})
        handoff_added = list(handoff.get("metadata_added_since_night_started", ()))
        handoff_removed = list(
            handoff.get("metadata_removed_since_night_started", ())
        )
        handoff_changed = list(
            handoff.get("metadata_changed_since_night_started", ())
        )
        if (
            ran
            and status == "completed"
            and handoff.get("status") == "held_for_review"
            and handoff_added
        ):
            terminal.append(
                {
                    "kind": "import_bookkeeping_retained",
                    "label": label,
                    "handoff_status": str(handoff.get("status")),
                    "bookkeeping_key_left_behind": str(handoff_added[0]),
                    "bookkeeping_keys": handoff_added[:6],
                }
            )
        if ran and status == "completed" and (handoff_removed or handoff_changed):
            kind = "removed" if handoff_removed else "changed"
            keys = handoff_removed if handoff_removed else handoff_changed
            terminal.append(
                {
                    "kind": "completion_metadata_not_restored",
                    "label": label,
                    "handoff_status": str(handoff.get("status")),
                    "metadata_change_kind": kind,
                    "metadata_key_not_restored": str(keys[0]),
                    "metadata_keys_not_restored": keys[:6],
                }
            )

        if ran and export_role == "primary" and status == "completed":
            load_finished = True
        previous_row_total = row_total
        previous_database = database


    if catalogue_export_records:
        final = catalogue_export_records[-1]
        database = dict(final.get("database", {}))
        differences = _table_differences(dict(reference["tables"]), database)
        if differences:
            if any(int(value["missing_count"]) for value in differences.values()):
                kind = "rows_missing_after_resume"
            elif any(int(value["unexpected_count"]) for value in differences.values()):
                kind = "rows_duplicated_after_resume"
            else:
                kind = "rows_incorrect_after_resume"
            completion.append(
                {
                    "kind": kind,
                    "label": str(final.get("label")),
                    "rows_the_export_admits": admissible,
                    "rows_in_the_catalogue": _row_total(database),
                    "tables": {
                        table: {
                            "in_the_export": count,
                            "in_the_catalogue": len(dict(database.get(table, {}))),
                        }
                        for table, count in sorted(per_table.items())
                    },
                    "differences": differences,
                }
            )
    else:
        completion.append(
            {
                "kind": "run_raised_its_own_error",
                "label": "first-attempt",
                "export": "",
                "error": "the night produced no import runs at all",
            }
        )


    if next_day_record is not None:
        database = dict(next_day_record.get("database", {}))
        report = dict(next_day_record.get("report") or {})
        next_status = (
            str(report.get("status", "")) if next_day_record.get("ok") else "no report"
        )
        if next_status != "completed":
            terminal.append(
                {
                    "kind": "next_export_did_not_complete",
                    "label": str(next_day_record.get("label")),
                    "export": str(next_day_record.get("export_name")),
                    "status": next_status,
                }
            )
        differences = _table_differences(dict(next_day_reference["tables"]), database)
        if differences:
            counts = _difference_counts(differences)
            if counts["missing_count"]:
                kind = "next_export_rows_missing"
            elif counts["unexpected_count"]:
                kind = "next_export_rows_unexpected"
            else:
                kind = "next_export_rows_incorrect"
            terminal.append(
                {
                    "kind": kind,
                    "label": str(next_day_record.get("label")),
                    "export": str(next_day_record.get("export_name")),
                    "status": next_status,
                    "rows_the_new_export_admits": _row_total(next_day_reference["tables"]),
                    "rows_in_the_catalogue": _row_total(database),
                    "rows_missing_from_the_catalogue": counts["missing_count"],
                    "rows_unexpected_in_the_catalogue": counts["unexpected_count"],
                    "rows_incorrect_in_the_catalogue": counts["changed_count"],
                    "differences": differences,
                }
            )


    reference_rejection_count = 0
    for night, role in expected_role_by_night.items():
        expected_entries = [
            (entry["index"], entry["reason"])
            for entry in references_by_role[role]["rejected"]
        ]
        expected = Counter(expected_entries)
        reported = Counter(reported_rejections_by_night.get(night, ()))
        reference_rejection_count = max(reference_rejection_count, sum(expected.values()))

        unexpected = sorted(
            (entry for entry in reported if entry not in expected), key=str
        )
        missing_counter = expected - reported
        missing = sorted(missing_counter.elements(), key=str)
        duplicate_counts = {
            entry: reported[entry] - expected[entry]
            for entry in expected
            if reported[entry] > expected[entry]
        }
        correct = sum(min(reported[entry], count) for entry, count in expected.items())

        if unexpected:
            unexpected_occurrences = sum(reported[entry] for entry in unexpected)
            rejection.append(
                {
                    "kind": "rejection_reason_incorrect",
                    "night": night,
                    "rejections_the_rules_give": sum(expected.values()),
                    "rejections_the_report_gets_right": correct,
                    "rejections_the_rules_do_not_give": unexpected_occurrences,
                    "reasons_not_reported": sorted(
                        {str(reason) for _, reason in missing}
                    ),
                    "reasons_reported_that_do_not_apply": sorted(
                        {str(reason) for _, reason in unexpected}
                    ),
                    "unreported_invalid_rows": missing[:6],
                    "unexpected_rejections": unexpected[:6],
                }
            )
        elif missing:
            rejection.append(
                {
                    "kind": "invalid_row_not_reported",
                    "night": night,
                    "rejections_the_rules_give": sum(expected.values()),
                    "rejections_the_report_gets_right": correct,
                    "reasons_not_reported": sorted(
                        {str(reason) for _, reason in missing}
                    ),
                    "unreported_invalid_rows": missing[:6],
                }
            )
        elif duplicate_counts:
            rejection.append(
                {
                    "kind": "invalid_row_reported_more_than_once",
                    "night": night,
                    "rejections_the_rules_give": sum(expected.values()),
                    "rejections_reported_more_than_once": len(duplicate_counts),
                    "duplicate_rejection_occurrences": sum(duplicate_counts.values()),
                    "repeated_rejections": sorted(duplicate_counts, key=str)[:6],
                }
            )


    repeat_allowance = admissible + interval * max(1, runs_that_stopped_early)
    if load_finished and rows_written_before_completion > repeat_allowance:
        resume.append(
            {
                "kind": "committed_work_repeated",
                "rows_written_before_completion": rows_written_before_completion,
                "runs_counted": list(runs_counted_before_completion),
                "runs_that_stopped_early": runs_that_stopped_early,
                "allowance": repeat_allowance,
                "rows_the_export_admits": admissible,
            }
        )

    return {
        "completion_failures": completion,
        "rejection_failures": rejection,
        "resume_failures": resume,
        "work_failures": work,
        "terminal_failures": terminal,
        "records": records,
        "reference_row_total": admissible,
        "reference_rejection_count": reference_rejection_count,
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private nightly load once against this workspace and measure it.'

    def compute() -> Mapping[str, Any]:
        payload = _payload(
            str(PRIVATE_WORKLOAD["profile"]),
            int(PRIVATE_WORKLOAD["seed"]),
            int(PRIVATE_WORKLOAD["scale"]),
        )
        outcome = PROJECT.invoke(artifact_dir, payload)
        if not outcome.get("ok"):
            analysis = _stub_analysis(str(outcome.get("error", "the loader could not be run")))
        else:
            analysis = _analyse(outcome, payload["events"], payload["sources"])
        return {
            **analysis,
            "case": {
                "profile": str(PRIVATE_WORKLOAD["profile"]),
                "scale": int(PRIVATE_WORKLOAD["scale"]),
                "source_rows": len(payload["sources"]["primary"]),
            },
        }

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The loader workspace and the recorded nights are available.",
        "measurements": {


            "project_records": [f"project_records/{path.name}" for path in records],
            "checkpoint_interval": CHECKPOINT_INTERVAL,
            "rows_per_transaction_allowance": CHECKPOINT_INTERVAL,
            "rows_read_before_first_commit_allowance": CHECKPOINT_INTERVAL,
            "transaction_allowance_formula": (
                f"ceil(total_rows / {CHECKPOINT_INTERVAL}) + {TRANSACTION_SLACK}"
            ),
            "source_retention_rows": CHECKPOINT_INTERVAL,
        },
        "observed": {},
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    payload = _payload(str(case["profile"]), int(case["seed"]), int(case["scale"]))
    outcome = PROJECT.invoke(artifact_dir, payload)
    rows = payload["sources"]["primary"]
    if not outcome.get("ok"):
        return {
            "summary": "The recorded night could not be run against this workspace.",
            "measurements": {"record_id": record_id, "source_row_count": len(rows)},
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    allowance = _transaction_allowance(len(rows))
    timeline = []
    for record in outcome.get("records", ()):
        record = dict(record)
        if record.get("type") != "import":
            continue
        report = dict(record.get("report") or {})
        storage = dict(record.get("storage", {}))
        meter = dict(record.get("meter", {}))
        timeline.append(
            {
                "label": record.get("label"),
                "night": record.get("night"),
                "export": record.get("export_name"),
                "export_retained_from_row": record.get("retained_from"),
                "returned_a_report": bool(record.get("ok")),
                "error": record.get("error"),
                "reported_status": report.get("status"),
                "reported_rows_read": report.get("rows_read"),
                "reported_rows_committed": report.get("rows_committed"),
                "reported_resumed_from": report.get("resumed_from"),
                "reported_rejections": [
                    dict(entry) for entry in report.get("rejected", ())
                ][:8],
                "reported_rejection_count": len(report.get("rejected", ())),
                "transactions_opened": storage.get("transactions"),
                "transaction_allowance": allowance,
                "rows_in_largest_transaction": storage.get("max_rows_per_transaction"),
                "rows_per_transaction_allowance": CHECKPOINT_INTERVAL,
                "rows_read_before_first_commit": (
                    dict(meter.get("first_commit_mark") or {}).get("rows_read")
                ),
                "rows_read_before_first_commit_allowance": CHECKPOINT_INTERVAL,
                "rows_written": storage.get("rows_written"),
                "committed_row_counts": {
                    table: len(dict(entries))
                    for table, entries in dict(record.get("database", {})).items()
                },
                "invariant_violations_in_committed_snapshots": record.get(
                    "committed_invariant_violations"
                ),
                "durable_metadata_keys": record.get("meta_keys"),
                "night_handoff": {
                    "status": dict(record.get("night_handoff") or {}).get("status"),
                    "metadata_changes_since_night_started": dict(
                        record.get("night_handoff") or {}
                    ).get("metadata_changes_since_night_started", ()),
                }
                if record.get("night_handoff")
                else None,
                "catalogue_digest": record.get("database_digest"),
            }
        )
    plan = {str(event.get("label")): dict(event) for event in payload["events"]}
    written_before_the_finish = 0
    runs_counted: list[str] = []
    stopped_early = 0
    finished = False
    for entry in timeline:
        label = str(entry.get("label"))
        spec = plan.get(label, {})
        if str(spec.get("source", "primary")) != "primary" or finished:
            continue
        written_before_the_finish += int(entry.get("rows_written") or 0)
        runs_counted.append(label)
        if (
            spec.get("fail_after") is not None
            or spec.get("fail_on_commit") is not None
            or bool(spec.get("fail_on_cleanup", False))
        ):
            stopped_early += 1
        if entry.get("returned_a_report") and entry.get("reported_status") == "completed":
            finished = True
    catalogue_rows = (
        sum(int(count) for count in dict(timeline[-1]["committed_row_counts"]).values())
        if timeline
        else 0
    )
    measurements: dict[str, Any] = {
        "record_id": record_id,
        "source_row_count": len(rows),
        "checkpoint_interval": CHECKPOINT_INTERVAL,
        "transaction_allowance": allowance,
        "rows_per_transaction_allowance": CHECKPOINT_INTERVAL,
        "source_retention_rows": CHECKPOINT_INTERVAL,
        "rows_written_before_the_load_finished": written_before_the_finish,
        "runs_counted_for_that_total": runs_counted,
        "runs_that_stopped_early": stopped_early,
        "rows_in_the_catalogue_at_the_end": catalogue_rows,
        "rows_written_allowance": (
            catalogue_rows + CHECKPOINT_INTERVAL * max(1, stopped_early)
        ),
    }
    if record_id == "dirty-export":
        measurements["source_rows_sample"] = [dict(row) for row in rows[:14]]
    return {
        "summary": "The recorded night ran against this workspace.",
        "measurements": measurements,
        "observed": {"run_timeline": timeline},
    }
