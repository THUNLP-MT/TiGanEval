'Sandboxed candidate runner for the incremental scan-cache simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
import re
import sys
from typing import Any, Mapping, Sequence


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


_FINDING_FIELDS = (
    "check_id",
    "path",
    "line",
    "severity",
    "confidence",
    "message",
)
_COUNT_FIELDS = (
    "total_files",
    "cache_hits",
    "cache_misses",
    "cached_entry_count",
    "cache_bytes",
)


def _finding_rows(rows: Any) -> list[dict[str, Any]]:
    'Return validated finding rows without trusting candidate coercions.'

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise TypeError("scan report findings must be a sequence")
    normalised: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("every finding must be a mapping")
        missing = [field for field in _FINDING_FIELDS if field not in row]
        if missing:
            raise ValueError(f"finding is missing fields: {', '.join(missing)}")
        if (
            not isinstance(row["check_id"], str)
            or not isinstance(row["path"], str)
            or not isinstance(row["line"], int)
            or isinstance(row["line"], bool)
            or not isinstance(row["severity"], str)
            or not isinstance(row["confidence"], str)
            or not isinstance(row["message"], str)
        ):
            raise TypeError("finding fields have invalid types")
        normalised.append({field: row[field] for field in _FINDING_FIELDS})
    normalised.sort(key=lambda row: (row["path"], row["line"], row["check_id"]))
    return normalised


def _validated_report(report: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    'Validate the public report contract in driver-owned code.'

    if not isinstance(report, Mapping):
        raise TypeError("scan must return a mapping")
    missing = [name for name in ("findings", "cache_info") if name not in report]
    if missing:
        raise ValueError(f"scan report is missing fields: {', '.join(missing)}")
    findings = _finding_rows(report["findings"])
    cache_info = report["cache_info"]
    if not isinstance(cache_info, Mapping):
        raise TypeError("scan report cache_info must be a mapping")
    absent = [
        name
        for name in (*_COUNT_FIELDS, "reused_paths")
        if name not in cache_info
    ]
    if absent:
        raise ValueError(f"cache_info is missing fields: {', '.join(absent)}")
    if any(
        not isinstance(cache_info[name], int) or isinstance(cache_info[name], bool)
        for name in _COUNT_FIELDS
    ):
        raise TypeError("cache_info count fields must be integers")
    reused = cache_info["reused_paths"]
    if (
        not isinstance(reused, Sequence)
        or isinstance(reused, (str, bytes, bytearray))
        or any(not isinstance(path, str) for path in reused)
    ):
        raise TypeError("cache_info reused_paths must be a sequence of paths")
    normalised_info = {name: cache_info[name] for name in _COUNT_FIELDS}
    normalised_info["reused_paths"] = list(reused)
    return findings, normalised_info


def _json_mapping(value: Any) -> dict[str, Any] | None:
    'Copy a candidate mapping only when it is safe for the driver output.'

    if not isinstance(value, Mapping):
        return None
    try:
        items = dict(value).items()
    except BaseException:
        return None
    copied: dict[str, Any] = {}
    for key, item in items:
        try:
            copied[str(key)] = json.loads(json.dumps(item))
        except BaseException:
            continue
    return copied


def _reference_checks(raw_options: Mapping[str, Any], checks: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    'The effective check ids, evaluated from a driver-owned snapshot.'

    parts = str(raw_options.get("analyzer_version", "3.2.0")).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("analyzer version must be MAJOR.MINOR.PATCH")
    version = tuple(int(part) for part in parts)
    severity_rank = {"low": 0, "medium": 1, "high": 2}
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    severity_floor = severity_rank[str(raw_options.get("severity_floor", "low"))]
    confidence_floor = confidence_rank[str(raw_options.get("confidence_floor", "low"))]
    profile = {str(item) for item in raw_options.get("profile_checks", ())}
    selected_raw = raw_options.get("selected_checks")
    selected = None if selected_raw is None else {str(item) for item in selected_raw}
    skipped = {str(item) for item in raw_options.get("skipped_checks", ())}
    active: list[str] = []
    for check in checks:
        check_id = str(check["check_id"])
        if tuple(check["since_version"]) > version:
            continue
        if profile and check_id not in profile:
            continue
        if selected is not None and check_id not in selected:
            continue
        if check_id in skipped:
            continue
        if severity_rank[str(check["severity"])] < severity_floor:
            continue
        if confidence_rank[str(check["confidence"])] < confidence_floor:
            continue
        active.append(check_id)
    return tuple(active)


def _reference_findings(
    files: Mapping[str, Mapping[str, Any]],
    raw_options: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'Full-scan findings computed outside the candidate-controlled protocol.'

    active = set(_reference_checks(raw_options, checks))
    findings: list[dict[str, Any]] = []
    for path in sorted(files):
        text = str(files[path]["content"])
        for line_number, line in enumerate(text.splitlines(), start=1):
            for check in checks:
                check_id = str(check["check_id"])
                if check_id in active and re.search(str(check["pattern"]), line):
                    findings.append(
                        {
                            "check_id": check_id,
                            "path": str(path),
                            "line": line_number,
                            "severity": str(check["severity"]),
                            "confidence": str(check["confidence"]),
                            "message": str(check["message"]),
                        }
                    )
    findings.sort(key=lambda row: (row["path"], row["line"], row["check_id"]))
    return findings


def _entries_digest(entries: Mapping[str, str]) -> str:
    material = json.dumps(dict(sorted(entries.items())), sort_keys=True).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _damage(value: str, mode: str) -> str:
    raw = bytes.fromhex(value)
    if mode == "truncate":
        return raw[: max(0, len(raw) // 2)].hex()
    if mode == "garbage":
        return b"\x00\xffnot-a-cache-entry".hex()
    if mode == "flip_byte":
        if not raw:
            return raw.hex()


        mutated = bytearray(raw)
        for fraction in (0.25, 0.5, 0.75):
            index = min(len(raw) - 1, int(len(raw) * fraction))
            mutated[index] ^= 0x40
        return bytes(mutated).hex()
    raise ValueError(f"unknown damage mode: {mode}")


def _declared_version(blob: bytes) -> Any:
    'The format version a bundle declares, as the receiving worker would read it.'

    try:
        payload = json.loads(bytes(blob).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload.get("format_version") if isinstance(payload, dict) else None


def _mutate_bundle(blob: bytes, mutate: str) -> bytes:
    if mutate == "none":
        return blob
    if mutate == "garbage":
        return b"{not json at all"
    if mutate == "truncate":
        return blob[: max(1, len(blob) // 2)]
    if mutate == "bad_version":
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return blob
        if not isinstance(payload, dict):
            return blob
        payload["format_version"] = 9999
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raise ValueError(f"unknown bundle mutation: {mutate}")


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from scanner import protocol


    reference_checks = tuple(
        {
            "check_id": check.check_id,
            "pattern": check.pattern,
            "severity": check.severity,
            "confidence": check.confidence,
            "message": check.message,
            "since_version": tuple(check.since_version),
        }
        for check in protocol.CHECKS
    )
    cache_store_type = protocol.CacheStore
    cache_store_init = protocol.CacheStore.__init__
    cache_store_export = protocol.CacheStore.export_entries
    source_tree_type = protocol.SourceTree
    source_tree_init = protocol.SourceTree.__init__
    scan_options_from_mapping = protocol.ScanOptions.from_mapping
    run_context_type = protocol.RunContext
    run_context_init = protocol.RunContext.__init__
    original_run_checks = protocol.run_checks
    original_meter = protocol.METER
    original_meter_reset = protocol.AnalysisMeter.reset

    analysis_calls: list[str] = []
    store_audits: dict[int, dict[str, int]] = {}

    def audited_run_checks(path: str, text: str, options: Any):
        analysis_calls.append(str(path))
        return original_run_checks(path, text, options)

    original_get = protocol.CacheStore.get
    original_put = protocol.CacheStore.put
    original_delete = protocol.CacheStore.delete

    def audit_for(store: Any) -> dict[str, int]:
        return store_audits.setdefault(
            id(store), {"gets": 0, "puts": 0, "deletes": 0, "put_bytes": 0}
        )

    def audited_get(store: Any, key: str):
        audit_for(store)["gets"] += 1
        return original_get(store, key)

    def audited_put(store: Any, key: str, value: bytes) -> None:
        audit = audit_for(store)
        audit["puts"] += 1
        audit["put_bytes"] += len(value)
        original_put(store, key, value)

    def audited_delete(store: Any, key: str) -> None:
        audit_for(store)["deletes"] += 1
        original_delete(store, key)

    def install_audited_surface() -> None:
        protocol.METER = original_meter
        protocol.run_checks = audited_run_checks
        cache_store_type.get = audited_get
        cache_store_type.put = audited_put
        cache_store_type.delete = audited_delete

    def make_store(saved: Mapping[str, str]) -> Any:
        store = object.__new__(cache_store_type)
        cache_store_init(store, saved)
        store_audits[id(store)] = {"gets": 0, "puts": 0, "deletes": 0, "put_bytes": 0}
        return store

    def make_tree(tree_root: str, tree_files: Mapping[str, Mapping[str, Any]]) -> Any:
        tree = object.__new__(source_tree_type)
        source_tree_init(tree, tree_root, tree_files)
        return tree

    def make_context(**values: Any) -> Any:
        context = object.__new__(run_context_type)
        run_context_init(context, **values)
        return context

    def store_snapshot(store: Any) -> tuple[dict[str, str], int]:
        saved = cache_store_export(store)
        total_bytes = sum(
            len(str(key).encode("utf-8")) + len(bytes.fromhex(str(value)))
            for key, value in saved.items()
        )
        return saved, total_bytes

    install_audited_surface()

    fixture = {
        str(path): dict(entry) for path, entry in dict(payload["fixture"]).items()
    }
    files: dict[str, dict[str, Any]] = {}
    entries: dict[str, str] = {}
    bundles: dict[str, bytes] = {}
    root = str(payload.get("root", "/srv/ci-1/checkout"))
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    def load_candidate():
        engine = importlib.import_module("scanner.engine")
        exchange = importlib.import_module("scanner.exchange")
        engine = importlib.reload(engine)
        exchange = importlib.reload(exchange)
        return engine, exchange

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))

            if kind == "reset":
                files = {path: dict(entry) for path, entry in fixture.items()}
                entries = {}
                bundles = {}
                root = str(event.get("root", root))
                records.append({"type": "reset", "index": index, "root": root})
                continue

            if kind == "edit":
                for path, change in dict(event.get("files", {})).items():
                    current = files.get(str(path), {"content": "", "mtime": 0.0})
                    mtime = change.get("mtime")
                    files[str(path)] = {
                        "content": str(change.get("content", current["content"])),
                        "mtime": float(current["mtime"] if mtime is None else mtime),
                    }
                for path in list(event.get("remove", ())):
                    files.pop(str(path), None)
                records.append(
                    {
                        "type": "edit",
                        "index": index,
                        "changed": sorted(str(key) for key in dict(event.get("files", {}))),
                        "removed": sorted(str(key) for key in event.get("remove", ())),
                    }
                )
                continue

            if kind == "relocate":
                root = str(event.get("root", root))
                shift = float(event.get("mtime_shift", 0.0))
                files = {
                    path: {"content": entry["content"], "mtime": float(entry["mtime"]) + shift}
                    for path, entry in files.items()
                }
                records.append({"type": "relocate", "index": index, "root": root})
                continue

            if kind == "clear_store":
                entries = {}
                records.append({"type": "clear_store", "index": index})
                continue

            if kind == "damage":
                mode = str(event.get("mode", "garbage"))
                keys = sorted(entries)
                fraction = float(event.get("fraction", 1.0))
                affected = keys[: max(1, int(len(keys) * fraction))] if keys else []
                if mode == "misdirected_write":


                    source = entries[affected[0]] if affected else ""
                    for key in affected[1:]:
                        entries[key] = source
                else:
                    for key in affected:
                        entries[key] = _damage(entries[key], mode)
                records.append(
                    {
                        "type": "damage",
                        "index": index,
                        "mode": mode,
                        "damaged_entries": len(affected),
                    }
                )
                continue

            if kind == "export":
                label = str(event.get("label", f"bundle-{index}"))
                store = make_store(entries)
                context = make_context(
                    now=float(event.get("now", 0.0)),
                    cache_size_limit_bytes=int(event.get("cache_size_limit_bytes", 10**9)),
                    cache_expiry_days=float(event.get("cache_expiry_days", 3650.0)),
                    machine=str(event.get("machine", "ci-1")),
                )
                install_audited_surface()
                _, exchange = load_candidate()
                record: dict[str, Any] = {
                    "type": "export",
                    "index": index,
                    "label": label,
                    "phase": str(event.get("phase", "")),
                }
                try:
                    blob = exchange.export_cache(store, context)
                    if (
                        protocol.run_checks is not audited_run_checks
                        or protocol.METER is not original_meter
                        or cache_store_type.get is not audited_get
                        or cache_store_type.put is not audited_put
                        or cache_store_type.delete is not audited_delete
                    ):
                        raise RuntimeError("delivered code changed the analyzer protocol")
                    if not isinstance(blob, (bytes, bytearray)):
                        raise TypeError("export_cache must return bytes")
                    blob = bytes(blob)
                    bundles[label] = blob
                    record.update(
                        {
                            "ok": True,
                            "byte_count": len(blob),
                            "sha256": hashlib.sha256(blob).hexdigest(),
                        }
                    )
                    try:
                        parsed = json.loads(blob.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        parsed = None
                    record["is_json_object"] = isinstance(parsed, dict)
                    record["format_version"] = (
                        parsed.get("format_version") if isinstance(parsed, dict) else None
                    )
                except BaseException as exc:
                    record.update({"ok": False, "error": _describe(exc)})
                records.append(record)
                continue

            if kind == "import":
                label = str(event.get("label", ""))
                mutate = str(event.get("mutate", "none"))
                blob = _mutate_bundle(bundles.get(label, b""), mutate)
                store = make_store(entries)
                context = make_context(
                    now=float(event.get("now", 0.0)),
                    cache_size_limit_bytes=int(event.get("cache_size_limit_bytes", 10**9)),
                    cache_expiry_days=float(event.get("cache_expiry_days", 3650.0)),
                    machine=str(event.get("machine", "ci-1")),
                )
                install_audited_surface()
                _, exchange = load_candidate()
                before = _entries_digest(entries)
                record = {
                    "type": "import",
                    "index": index,
                    "label": label,
                    "phase": str(event.get("phase", "")),
                    "mutate": mutate,
                    "declared_format_version": _declared_version(blob),
                    "entries_digest_before": before,
                }
                try:
                    outcome = exchange.import_cache(store, blob, context)
                    if (
                        protocol.run_checks is not audited_run_checks
                        or protocol.METER is not original_meter
                        or cache_store_type.get is not audited_get
                        or cache_store_type.put is not audited_put
                        or cache_store_type.delete is not audited_delete
                    ):
                        raise RuntimeError("delivered code changed the analyzer protocol")
                    entries, _ = store_snapshot(store)
                    record.update(
                        {
                            "ok": True,
                            "result": _json_mapping(outcome),
                            "entries_digest_after": _entries_digest(entries),
                            "entry_count_after": len(entries),
                        }
                    )
                except BaseException as exc:
                    record.update(
                        {
                            "ok": False,
                            "error": _describe(exc),
                            "entries_digest_after": before,
                            "entry_count_after": len(entries),
                        }
                    )
                records.append(record)
                continue

            if kind != "scan":
                records.append({"type": "driver_error", "index": index, "error": f"unknown event: {kind}"})
                continue

            raw_options = dict(event.get("options", {}))
            options = scan_options_from_mapping(raw_options)
            config = dict(event.get("config", {}))
            context = make_context(
                now=float(event.get("now", 0.0)),
                cache_size_limit_bytes=int(config.get("cache_size_limit_bytes", 10**9)),
                cache_expiry_days=float(config.get("cache_expiry_days", 3650.0)),
                incremental=bool(config.get("incremental", True)),
                machine=str(event.get("machine", "ci-1")),
            )
            tree = make_tree(root, files)
            store = make_store(entries)
            paths = sorted(files)
            clean_findings = _reference_findings(files, raw_options, reference_checks)
            install_audited_surface()
            engine, _ = load_candidate()
            record = {
                "type": "scan",
                "index": index,
                "label": str(event.get("label", f"scan-{index}")),
                "phase": str(event.get("phase", "")),
                "total_files": len(paths),
                "paths": paths,
                "config": {
                    "cache_size_limit_bytes": context.cache_size_limit_bytes,
                    "cache_expiry_days": context.cache_expiry_days,
                    "incremental": context.incremental,
                },
                "now": context.now,
                "root": root,
                "machine": context.machine,
            }
            analysis_calls.clear()
            original_meter_reset(original_meter)
            try:
                report = engine.scan(tree, store, options, context)
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                record["reported_findings"] = None
                record["cache_info"] = None
            else:
                try:
                    findings, cache_info = _validated_report(report)
                except BaseException as exc:
                    record["ok"] = False
                    record["error"] = _describe(exc)
                    record["report_invalid"] = True
                    record["reported_findings"] = None
                    record["cache_info"] = None
                else:
                    record["ok"] = True
                    record["reported_findings"] = findings
                    record["cache_info"] = cache_info
            try:
                if (
                    protocol.run_checks is not audited_run_checks
                    or protocol.METER is not original_meter
                    or cache_store_type.get is not audited_get
                    or cache_store_type.put is not audited_put
                    or cache_store_type.delete is not audited_delete
                ):
                    raise RuntimeError("delivered code changed the analyzer protocol")
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                record["reported_findings"] = None
                record["cache_info"] = None
            record["analysis_calls"] = sorted(analysis_calls)
            try:
                entries, total_bytes = store_snapshot(store)
                audit = store_audits[id(store)]
                record["store"] = {
                    "entry_count": len(entries),
                    "total_bytes": total_bytes,
                    "puts": audit["puts"],
                    "gets": audit["gets"],
                    "deletes": audit["deletes"],
                    "put_bytes": audit["put_bytes"],
                }
            except BaseException as exc:
                entries = {}
                record["ok"] = False
                record["error"] = _describe(exc)
                record["store"] = {
                    "entry_count": 0,
                    "total_bytes": 0,
                    "puts": 0,
                    "gets": 0,
                    "deletes": 0,
                    "put_bytes": 0,
                }
            original_meter_reset(original_meter)
            record["clean_findings"] = clean_findings
            records.append(record)

    return {
        "ok": True,
        "records": records,
        "candidate_stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload)
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
