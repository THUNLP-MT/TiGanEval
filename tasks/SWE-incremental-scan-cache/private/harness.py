'Deterministic analysis of one incremental-scan-cache workspace.'

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    CACHE_BYTES_PER_FILE,
    CAPACITY_EXPIRY_DAYS,
    REVISIT_LABEL,
    STEADY_STATE_WRITE_BASE_BYTES,
    STEADY_STATE_WRITE_BYTES_PER_FILE,
    build_program,
    build_tree,
    cache_size_limit,
    file_count,
    steady_state_write_allowance,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("scanner/engine.py", "scanner/exchange.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-scan-cache-",
    timeout=60.0,
)


PRIVATE_WORKLOAD: Mapping[str, Any] = {"profile": "release", "seed": 37, "scale": 2}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "nightly-rescan": {"profile": "nightly", "seed": 5, "scale": 1},
    "cache-damage-drill": {"profile": "damage", "seed": 8, "scale": 1},
    "capacity-week": {"profile": "capacity", "seed": 13, "scale": 1},
    "fleet-handoff": {"profile": "handoff", "seed": 21, "scale": 1},
}


DAMAGE_CORRECTNESS_LABELS = (
    "after-truncation",
    "after-corruption",
    "after-bit-flip",
    "after-misdirected-write",
    "after-malformed-import",
    "after-stale-bundle-import",
)


WARM_START_LABEL = "ci-2-warm"

BUCKETS: Mapping[str, str] = {
    "clean_scan_finding_equivalence": "correctness_failures",
    "fail_closed_cache_integrity": "integrity_failures",
    "honest_cache_accounting": "accounting_failures",
    "bounded_cache_growth": "capacity_failures",
    "portable_cache_exchange": "portability_failures",
}

_CACHE = AnalysisCache()


def _scans(
    records: Sequence[Mapping[str, Any]], phase: str | None = None
) -> list[Mapping[str, Any]]:
    return [
        record
        for record in records
        if record.get("type") == "scan" and (phase is None or record.get("phase") == phase)
    ]


def _bundles(
    records: Sequence[Mapping[str, Any]], kind: str, phase: str | None = None
) -> list[Mapping[str, Any]]:
    return [
        record
        for record in records
        if record.get("type") == kind and (phase is None or record.get("phase") == phase)
    ]


def _by_label(records: Sequence[Mapping[str, Any]], label: str) -> Mapping[str, Any] | None:
    return next((record for record in records if record.get("label") == label), None)


def _finding_delta(record: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    reported = sorted(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in record.get("reported_findings") or ()
    )
    clean = sorted(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in record.get("clean_findings") or ()
    )
    only_reported = sorted(set(reported).difference(clean))
    only_clean = sorted(set(clean).difference(reported))
    if reported != clean and not only_reported and not only_clean:


        counts, clean_counts = Counter(reported), Counter(clean)
        only_reported = sorted(item for item in counts if counts[item] > clean_counts[item])
        only_clean = sorted(item for item in clean_counts if clean_counts[item] > counts[item])
    return only_reported, only_clean


def _finding_file(finding_id: str) -> str:
    'The file named by one canonical finding row.'

    try:
        row = json.loads(str(finding_id))
    except json.JSONDecodeError:
        return "<malformed finding>"
    return str(row.get("path", "<malformed finding>")) if isinstance(row, dict) else "<malformed finding>"


def _finding_summary(findings: Any) -> dict[str, Any]:
    'Count and fingerprint one side without comparing it with the other.'

    if findings is None:
        return {"count": None, "sha256": None}
    canonical = sorted(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in findings
    )
    material = ("[" + ",".join(canonical) + "]").encode("utf-8")
    return {"count": len(canonical), "sha256": hashlib.sha256(material).hexdigest()}


def _delta_fields(
    only_reported: Sequence[str], only_clean: Sequence[str]
) -> dict[str, Any]:
    'Scalars naming the files behind one report/re-analysis disagreement.'

    fields: dict[str, Any] = {
        "differing_finding_count": len(only_reported) + len(only_clean)
    }
    if only_reported:
        fields["reported_file"] = _finding_file(only_reported[0])
    if only_clean:
        fields["missing_file"] = _finding_file(only_clean[0])
    fields["disputed_file"] = fields.get("reported_file") or fields.get("missing_file")
    return fields


def _cache_info(record: Mapping[str, Any]) -> Mapping[str, Any]:
    info = record.get("cache_info")
    return dict(info) if isinstance(info, Mapping) else {}


def _paths(record: Mapping[str, Any], key: str) -> set[str]:
    return {str(item) for item in record.get(key) or ()}


_PROCESS_ERROR_PHRASES = (
    ("candidate process exited with status", "the scanner process exited with status"),
    ("candidate returned invalid JSON", "the scanner run produced unreadable output"),
    ("candidate returned non-object", "the scanner run produced unreadable output"),
)


def _project_error(error: Any) -> str:
    'One execution failure, phrased as the pipeline would report it.'

    text = str(error or "the scanner could not be run")
    for phrase, replacement in _PROCESS_ERROR_PHRASES:
        text = text.replace(phrase, replacement)
    return text


def _inventory(entry_count: Any, byte_count: Any) -> str:
    'One store inventory as the volume panel and the report both phrase it.'

    return f"{entry_count} saved results and {byte_count} bytes"


def _completed_before(
    scans: Sequence[Mapping[str, Any]], label: str
) -> list[str]:
    'The runs that produced a report before this one stopped.'

    done: list[str] = []
    for record in scans:
        if str(record.get("label")) == label:
            break
        if record.get("ok"):
            done.append(str(record.get("label")))
    return done[:8]


def _correctness_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Nightly and capacity runs that disagree with a full re-analysis.'

    failures: list[dict[str, Any]] = []
    checked = [
        record
        for record in _scans(records)
        if record.get("phase") in {"nightly", "capacity"}
    ]
    nightly = _scans(records, "nightly")
    for record in checked:
        label = str(record.get("label"))
        if not record.get("ok"):


            if record.get("phase") != "nightly":
                continue
            failures.append(
                {
                    "kind": "nightly_scan_failed",
                    "label": label,
                    "error": record.get("error"),
                    "completed_runs_before": _completed_before(nightly, label),
                }
            )
            continue
        only_reported, only_clean = _finding_delta(record)
        if only_reported and not only_clean:
            kind = "stale_findings_reported"
        elif only_clean and not only_reported:
            kind = "findings_missing_after_change"
        elif only_reported or only_clean:
            kind = "findings_differ_from_clean_scan"
        else:
            continue
        failures.append(
            {
                "kind": kind,
                "label": label,
                **_delta_fields(only_reported, only_clean),
                "only_in_report": only_reported[:6],
                "only_in_clean_scan": only_clean[:6],
            }
        )
    return failures


def _damage_before(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[str, Any]:
    'What the drill last did to the stored bytes before this run started.'

    latest: dict[str, Any] = {
        "damage_mode_before_run": "none",
        "damaged_entries_before_run": 0,
    }
    for record in records:
        if record.get("type") == "damage":
            latest = {
                "damage_mode_before_run": str(record.get("mode")),
                "damaged_entries_before_run": int(record.get("damaged_entries") or 0),
            }
        elif record.get("type") == "scan" and str(record.get("label")) == label:
            break
    return latest


def _reported_hits(info: Mapping[str, Any]) -> int:
    'The hit count a run published, or -1 when it published nothing usable.'

    value = info.get("cache_hits")
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _files_not_reused(record: Mapping[str, Any], reanalysed: Sequence[str]) -> int:
    "How many of a run's files were not served from the store."

    if reanalysed:
        return len(reanalysed)
    hits = _cache_info(record).get("cache_hits")
    live_files = int(record.get("total_files", 0))
    if isinstance(hits, int) and not isinstance(hits, bool):
        return max(0, live_files - hits)
    return live_files


def _integrity_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The reliability drill: damaged storage and a re-imported bundle.'

    failures: list[dict[str, Any]] = []
    for record in _bundles(records, "import", "damage"):
        if not record.get("ok"):
            failures.append(
                {
                    "kind": "import_aborted_the_run",
                    "label": str(record.get("label")),
                    "bundle_condition": record.get("mutate"),
                    "error": str(record.get("error") or "no error text"),
                }
            )
    for record in _scans(records, "damage"):
        label = str(record.get("label"))
        if not record.get("ok"):
            failures.append(
                {
                    "kind": "cache_failure_aborted_scan",
                    "label": label,
                    "error": str(record.get("error") or "no error text"),
                    **_damage_before(records, label),
                }
            )
            continue
        if label not in DAMAGE_CORRECTNESS_LABELS:
            continue
        only_reported, only_clean = _finding_delta(record)
        if not only_reported and not only_clean:
            continue
        if label == "after-malformed-import":
            kind = "import_poisoned_cache"
        elif label == "after-stale-bundle-import":
            kind = "stale_bundle_served"
        else:
            kind = "damaged_entry_served"
        entry = {
            "kind": kind,
            "label": label,
            **_delta_fields(only_reported, only_clean),
            "only_in_report": only_reported[:6],
            "only_in_clean_scan": only_clean[:6],
        }
        if kind == "damaged_entry_served":
            entry.update(_damage_before(records, label))
        failures.append(entry)
    return failures


def _capacity_failures(
    records: Sequence[Mapping[str, Any]], scale: int
) -> list[dict[str, Any]]:
    "The capacity week: the volume's published size, age, and write envelope."

    failures: list[dict[str, Any]] = []
    scans = _scans(records, "capacity")
    allowance = steady_state_write_allowance(scale)
    for record in scans:
        label = str(record.get("label"))
        if not record.get("ok"):
            failures.append(
                {
                    "kind": "capacity_run_failed",
                    "label": label,
                    "error": record.get("error"),
                    "completed_runs_before": _completed_before(scans, label),
                }
            )
            continue
        store = dict(record.get("store", {}))
        limit = int(dict(record.get("config", {})).get("cache_size_limit_bytes", 0))
        if int(store.get("total_bytes", 0)) > limit:
            failures.append(
                {
                    "kind": "cache_size_limit_exceeded",
                    "label": label,
                    "cache_bytes_after_run": int(store.get("total_bytes", 0)),
                    "cache_size_limit_bytes": limit,
                    "cache_size_limit_bytes_per_file": CACHE_BYTES_PER_FILE,
                }
            )
        if label == "cap-unchanged" and int(store.get("put_bytes", 0)) > allowance:
            failures.append(
                {
                    "kind": "steady_state_write_amplification",
                    "label": label,
                    "bytes_written": int(store.get("put_bytes", 0)),
                    "steady_state_write_allowance_bytes": allowance,
                }
            )
    repeat = _by_label(scans, "cap-repeat")
    if repeat is None:
        failures.append(
            {
                "kind": "capacity_run_failed",
                "label": "cap-repeat",
                "error": "the immediately repeated run produced no record",
            }
        )
        return failures
    if repeat.get("ok"):
        reanalysed = sorted(_paths(repeat, "analysis_calls"))
        info = _cache_info(repeat)
        live_files = int(repeat.get("total_files", 0))


        if reanalysed or _reported_hits(info) < live_files:
            failures.append(
                {
                    "kind": "reusable_entry_evicted",
                    "label": "cap-repeat",
                    "files_not_reused": _files_not_reused(repeat, reanalysed),
                    "reanalysed_paths": reanalysed[:6],
                    "cache_hits": info.get("cache_hits"),
                    "live_file_count": live_files,
                }
            )
    removal = _by_label(scans, "cap-after-removal")
    restored = _by_label(scans, "cap-after-restore")
    if restored is not None and restored.get("ok") and removal is not None:
        returning = sorted(_paths(restored, "paths").difference(_paths(removal, "paths")))
        reanalysed = _paths(restored, "analysis_calls")
        served = [path for path in returning if path not in reanalysed]
        if served:
            failures.append(
                {
                    "kind": "unreclaimed_entries_retained",
                    "label": "cap-after-restore",
                    "served_path": served[0],
                    "served_path_count": len(served),
                    "paths_served_from_cache_after_deletion": served[:6],
                    "cache_expiry_days": CAPACITY_EXPIRY_DAYS,
                }
            )


    idle = _by_label(scans, "cap-after-idle")
    if idle is not None and idle.get("ok"):
        left = int(dict(idle.get("store", {})).get("entry_count", 0))
        live_files = int(idle.get("total_files", 0))
        if left > live_files:
            failures.append(
                {
                    "kind": "expired_entries_retained",
                    "label": "cap-after-idle",
                    "cached_entry_count_after_run": left,
                    "live_file_count": live_files,
                    "cache_expiry_days": CAPACITY_EXPIRY_DAYS,
                    "idle_days_before_this_run": round(
                        (float(idle.get("now", 0.0)) - float((restored or {}).get("now", 0.0)))
                        / 86_400.0,
                        1,
                    ),
                }
            )
    failures.extend(_warm_start_write_failures(records, allowance))
    failures.extend(_revisit_failures(records))
    return failures


def _revisit_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The night the pipeline runs a configuration it already ran this week.'

    run = _by_label(_scans(records, "nightly"), REVISIT_LABEL)
    if run is None or not run.get("ok"):
        return []
    reanalysed = sorted(_paths(run, "analysis_calls"))
    info = _cache_info(run)
    live_files = int(run.get("total_files", 0))
    if not live_files or (not reanalysed and _reported_hits(info) >= live_files):
        return []
    return [
        {
            "kind": "unexpired_entry_discarded",
            "label": REVISIT_LABEL,
            "files_not_reused": _files_not_reused(run, reanalysed),
            "reanalysed_paths": reanalysed[:6],
            "cache_hits": info.get("cache_hits"),
            "live_file_count": live_files,
            "cached_entry_count_after_run": int(
                dict(run.get("store", {})).get("entry_count", 0)
            ),
        }
    ]


def _warm_start_write_failures(
    records: Sequence[Mapping[str, Any]], allowance: int
) -> list[dict[str, Any]]:
    "The volume's write budget on the night a second worker starts warm."

    run = _by_label(_scans(records, "handoff"), WARM_START_LABEL)
    if run is None or not run.get("ok"):
        return []
    info = _cache_info(run)
    live_files = int(run.get("total_files", 0))
    if _paths(run, "analysis_calls") or _reported_hits(info) != live_files or not live_files:
        return []
    written = int(dict(run.get("store", {})).get("put_bytes", 0))
    if written <= allowance:
        return []
    return [
        {
            "kind": "warm_start_rewrites_the_store",
            "label": WARM_START_LABEL,
            "bytes_written": written,
            "steady_state_write_allowance_bytes": allowance,
            "checkout_root": str(run.get("root")),
            "machine": str(run.get("machine")),
            "live_file_count": live_files,
        }
    ]


def _portability_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "The fleet handoff: one worker's export warming a second worker."

    failures: list[dict[str, Any]] = []
    exports = _bundles(records, "export", "handoff")
    imports = _bundles(records, "import", "handoff")
    warm = _by_label(exports, "warm")
    repeat = _by_label(exports, "warm-repeat")
    if warm is None or repeat is None:
        return [{"kind": "export_contract_incomplete", "label": "warm", "error": "no export"}]
    for record in (warm, repeat):
        if (
            not record.get("ok")
            or not record.get("is_json_object")
            or not isinstance(record.get("format_version"), int)
        ):
            failures.append(
                {
                    "kind": "export_contract_incomplete",
                    "label": str(record.get("label")),
                    "error": record.get("error"),
                    "is_json_object": record.get("is_json_object"),
                    "declared_format_version": record.get("format_version"),
                }
            )
    if warm.get("ok") and repeat.get("ok") and warm.get("sha256") != repeat.get("sha256"):
        failures.append(
            {
                "kind": "export_not_deterministic",
                "label": "warm-repeat",
                "byte_counts": [warm.get("byte_count"), repeat.get("byte_count")],
            }
        )

    foreign = next(
        (record for record in imports if str(record.get("mutate")) == "bad_version"), None
    )
    if foreign is not None:
        if not foreign.get("ok"):
            failures.append(
                {
                    "kind": "unsupported_bundle_import_failed",
                    "label": str(foreign.get("label")),
                    "declared_format_version": foreign.get("declared_format_version"),
                    "error": str(foreign.get("error") or "no error text"),
                }
            )
        elif foreign.get("entries_digest_before") != foreign.get("entries_digest_after"):
            failures.append(
                {
                    "kind": "unsupported_bundle_accepted",
                    "label": str(foreign.get("label")),
                    "declared_format_version": foreign.get("declared_format_version"),
                    "entry_count_after": foreign.get("entry_count_after"),
                }
            )

    accepted = next(
        (record for record in imports if str(record.get("mutate")) == "none"), None
    )
    if (
        accepted is None
        or not accepted.get("ok")
        or int(accepted.get("entry_count_after", 0)) <= 0
    ):
        failures.append(
            {
                "kind": "warm_bundle_not_accepted",
                "label": "warm",
                "declared_format_version": (
                    None if accepted is None else accepted.get("declared_format_version")
                ),
                "error": None if accepted is None else accepted.get("error"),


                "entry_count_after": (
                    0 if accepted is None else int(accepted.get("entry_count_after") or 0)
                ),
            }
        )

    scans = _scans(records, "handoff")
    for label in ("ci-2-after-rejected-bundle", "ci-2-warm"):
        record = _by_label(scans, label)
        if record is None or not record.get("ok"):
            failures.append(
                {
                    "kind": "handoff_scan_failed",
                    "label": label,
                    "error": None if record is None else record.get("error"),
                }
            )
            continue
        only_reported, only_clean = _finding_delta(record)
        if only_reported or only_clean:
            failures.append(
                {
                    "kind": "warm_import_findings_wrong",
                    "label": label,
                    **_delta_fields(only_reported, only_clean),
                    "only_in_report": only_reported[:6],
                    "only_in_clean_scan": only_clean[:6],
                }
            )
    warm_scan = _by_label(scans, "ci-2-warm")
    if warm_scan is not None and warm_scan.get("ok"):
        reanalysed = sorted(_paths(warm_scan, "analysis_calls"))
        info = _cache_info(warm_scan)
        live_files = int(warm_scan.get("total_files", 0))


        if reanalysed or _reported_hits(info) < live_files:
            failures.append(
                {
                    "kind": "warm_import_not_reused",
                    "label": "ci-2-warm",
                    "machine": str(warm_scan.get("machine")),
                    "checkout_root": str(warm_scan.get("root")),
                    "files_not_reused": _files_not_reused(warm_scan, reanalysed),
                    "reanalysed_paths": reanalysed[:6],
                    "cache_hits": info.get("cache_hits"),
                    "live_file_count": live_files,
                }
            )
    return failures


def _accounting_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "Every run's cache summary against what that run actually did."

    failures: list[dict[str, Any]] = []
    every_run = _scans(records)
    for record in every_run:
        label = str(record.get("label"))
        if not record.get("ok"):
            error = str(record.get("error") or "")


            unreadable = bool(record.get("report_invalid")) or any(
                phrase in error
                for phrase in (
                    "scan report is missing fields",
                    "cache_info is missing fields",
                    "scan must return a mapping",
                    "cache_info must be a mapping",
                )
            )
            entry: dict[str, Any] = {
                "kind": "report_contract_incomplete" if unreadable else "scan_run_failed",
                "label": label,
                "error": str(record.get("error") or "no error text"),
                "completed_runs_before": _completed_before(every_run, label),
            }
            if unreadable:

                entry["cache_info"] = record.get("cache_info")
            failures.append(entry)
            continue
        info = _cache_info(record)
        store = dict(record.get("store", {}))
        paths = [str(item) for item in record.get("paths", ())]
        analysed = _paths(record, "analysis_calls")
        reused = info.get("reused_paths")
        live_files = int(record.get("total_files", 0))
        if not isinstance(reused, list) or any(not isinstance(item, str) for item in reused):
            failures.append(
                {
                    "kind": "report_contract_incomplete",
                    "label": label,
                    "cache_info": dict(info),
                }
            )
            continue
        hits = info.get("cache_hits")
        misses = info.get("cache_misses")
        count_fields = (
            "total_files",
            "cache_hits",
            "cache_misses",
            "cached_entry_count",
            "cache_bytes",
        )
        if any(
            not isinstance(info.get(field), int) or isinstance(info.get(field), bool)
            for field in count_fields
        ):
            failures.append(
                {"kind": "report_contract_incomplete", "label": label, "cache_info": dict(info)}
            )
            continue
        if (
            info["total_files"] != live_files
            or hits + misses != live_files
            or len(reused) != hits
            or len(set(reused)) != len(reused)
            or not set(reused).issubset(paths)
        ):
            failures.append(
                {
                    "kind": "accounting_totals_inconsistent",
                    "label": label,
                    "cache_info": {
                        key: info.get(key)
                        for key in ("total_files", "cache_hits", "cache_misses")
                    },
                    "reused_path_count": len(reused),
                    "live_file_count": live_files,
                }
            )
            continue
        if set(reused) != set(paths).difference(analysed):
            failures.append(
                {
                    "kind": "reuse_claim_contradicts_analysis",
                    "label": label,
                    "reused_paths_claimed_but_analysed": sorted(set(reused) & analysed)[:6],
                    "reused_paths_omitted": sorted(
                        set(paths).difference(analysed).difference(reused)
                    )[:6],
                }
            )
            continue
        if info["cached_entry_count"] != int(
            store.get("entry_count", -2)
        ) or info["cache_bytes"] != int(store.get("total_bytes", -2)):
            failures.append(
                {
                    "kind": "cache_inventory_misreported",
                    "label": label,


                    "reported_inventory": _inventory(
                        info.get("cached_entry_count"), info.get("cache_bytes")
                    ),
                    "inventory_on_the_volume": _inventory(
                        store.get("entry_count"), store.get("total_bytes")
                    ),
                    "reported": {
                        "cached_entry_count": info.get("cached_entry_count"),
                        "cache_bytes": info.get("cache_bytes"),
                    },
                    "left_on_the_volume": {
                        "cached_entry_count": store.get("entry_count"),
                        "cache_bytes": store.get("total_bytes"),
                    },
                }
            )
    return failures


def _analyse(candidate: Mapping[str, Any], scale: int) -> dict[str, Any]:
    records = [
        dict(record) for record in candidate.get("records", ()) if isinstance(record, Mapping)
    ]
    return {
        "correctness_failures": _correctness_failures(records),
        "integrity_failures": _integrity_failures(records),
        "capacity_failures": _capacity_failures(records, scale),
        "portability_failures": _portability_failures(records),
        "accounting_failures": _accounting_failures(records),
    }


def _case(scale: int) -> dict[str, Any]:
    return {
        "workload": "one pipeline week: nightly runs, drill, capacity, handoff",
        "live_file_count": file_count(scale),
        "cache_size_limit_bytes": cache_size_limit(scale),
        "cache_expiry_days": CAPACITY_EXPIRY_DAYS,
        "steady_state_write_allowance_bytes": steady_state_write_allowance(scale),
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private workload once per workspace content and bucket its failures.'

    scale = int(PRIVATE_WORKLOAD["scale"])

    def compute() -> Mapping[str, Any]:
        candidate = PROJECT.invoke(
            artifact_dir,
            {
                "fixture": build_tree(int(PRIVATE_WORKLOAD["seed"]), scale),
                "events": build_program(
                    str(PRIVATE_WORKLOAD["profile"]), int(PRIVATE_WORKLOAD["seed"]), scale
                ),
                "root": "/srv/ci-1/checkout",
            },
        )
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(
                    _project_error(candidate.get("error")), tuple(BUCKETS.values())
                )
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)[-500:]
        else:
            analysis = _analyse(candidate, scale)
        return {**analysis, "case": _case(scale)}

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def published_envelope(scale: int) -> dict[str, Any]:
    "The volume's published operating envelope for a tree of this size."

    return {
        "live_file_count": file_count(scale),
        "cache_size_limit_bytes": cache_size_limit(scale),
        "cache_size_limit_bytes_per_file": CACHE_BYTES_PER_FILE,
        "cache_expiry_days": CAPACITY_EXPIRY_DAYS,
        "steady_state_write_allowance_bytes": steady_state_write_allowance(scale),
        "steady_state_write_allowance_bytes_per_file": STEADY_STATE_WRITE_BYTES_PER_FILE,
        "steady_state_write_allowance_base_bytes": STEADY_STATE_WRITE_BASE_BYTES,
    }


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": (
            "The scanner workspace, the volume's published cache envelope, and the "
            "recorded pipeline rehearsals."
        ),
        "measurements": {
            "artifact_hash": artifact_hash(artifact_dir),
            "editable_files": list(EDITABLE_FILES),
            "public_records": [f"project_records/{path.name}" for path in records],
            "published_envelope_per_rehearsal": published_envelope(1),
        },
        "public": {},
    }


def _timeline(record: Mapping[str, Any], scale: int) -> dict[str, Any]:
    store = dict(record.get("store", {}))
    config = dict(record.get("config", {}))
    return {
        "label": record.get("label"),
        "phase": record.get("phase"),


        "run_instant": float(record.get("now", 0.0)),
        "now_days": round(float(record.get("now", 0.0)) / 86_400.0, 2),
        "machine": record.get("machine"),
        "checkout_root": record.get("root"),
        "completed": bool(record.get("ok")),
        "error": record.get("error"),
        "live_file_count": record.get("total_files"),
        "analysed_paths": sorted(_paths(record, "analysis_calls")),
        "reported_findings_summary": _finding_summary(record.get("reported_findings")),
        "clean_scan_findings_summary": _finding_summary(record.get("clean_findings")),
        "cache_info": record.get("cache_info"),
        "cache_on_the_volume_after_run": {
            "entry_count": store.get("entry_count"),
            "total_bytes": store.get("total_bytes"),
            "cache_size_limit_bytes": config.get("cache_size_limit_bytes"),
            "bytes_written_by_this_run": store.get("put_bytes"),
            "steady_state_write_allowance_bytes": steady_state_write_allowance(scale),
            "cache_expiry_days": config.get("cache_expiry_days"),
            "puts": store.get("puts"),
            "deletes": store.get("deletes"),
        },
    }


def _bundle_events(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") == "export":
            events.append(
                {
                    "event": "export",
                    "label": record.get("label"),
                    "completed": bool(record.get("ok")),
                    "error": record.get("error"),
                    "byte_count": record.get("byte_count"),
                    "content_sha256": record.get("sha256"),
                    "is_json_object": record.get("is_json_object"),
                    "declared_format_version": record.get("format_version"),
                }
            )
        elif record.get("type") == "import":
            events.append(
                {
                    "event": "import",
                    "label": record.get("label"),
                    "bundle_condition": record.get("mutate"),
                    "declared_format_version": record.get("declared_format_version"),
                    "completed": bool(record.get("ok")),
                    "error": record.get("error"),
                    "returned": record.get("result"),
                    "store_entries_sha256_before": record.get("entries_digest_before"),
                    "store_entries_sha256_after": record.get("entries_digest_after"),
                    "entry_count_after": record.get("entry_count_after"),
                }
            )
    return events


def _tree_events(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for record in records:
        kind = str(record.get("type", ""))
        if kind == "edit":
            events.append(
                {
                    "event": "edit",
                    "changed_paths": record.get("changed"),
                    "removed_paths": record.get("removed"),
                }
            )
        elif kind == "damage":
            events.append(
                {
                    "event": "storage_damage",
                    "mode": record.get("mode"),
                    "damaged_entries": record.get("damaged_entries"),
                }
            )
        elif kind == "relocate":
            events.append({"event": "relocate", "checkout_root": record.get("root")})
        elif kind == "clear_store":
            events.append({"event": "cache_cleared"})
    return events


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded rehearsal against this workspace and report raw telemetry.'

    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    scale = int(case["scale"])
    candidate = PROJECT.invoke(
        artifact_dir,
        {
            "fixture": build_tree(int(case["seed"]), scale),
            "events": build_program(str(case["profile"]), int(case["seed"]), scale),
            "root": "/srv/ci-1/checkout",
        },
    )
    measurements: dict[str, Any] = {"record_id": record_id, **published_envelope(scale)}
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} rehearsal could not run this scanner.",
            "measurements": measurements,
            "public": {
                "execution_error": _project_error(candidate.get("error")),
                "diagnostic": str(candidate.get("diagnostic", ""))[-1200:],
            },
        }
    records = [
        dict(item) for item in candidate.get("records", ()) if isinstance(item, Mapping)
    ]
    scans = _scans(records)
    measurements["scan_run_count"] = len(scans)
    return {
        "summary": f"The {record_id} rehearsal ran against this scanner.",
        "measurements": measurements,
        "public": {
            "run_timeline": [_timeline(record, scale) for record in scans],
            "bundle_events": _bundle_events(records),
            "tree_events": _tree_events(records),
        },
    }
