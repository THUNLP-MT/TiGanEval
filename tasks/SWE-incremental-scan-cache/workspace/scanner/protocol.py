"""Runtime contract for the incremental security-scan project.

The scanner analyses one source tree inside a single process. Every measurement
is deterministic: analysis cost is counted in check invocations rather than wall
clock time, the cache store reports exact persisted bytes, and the current
instant is supplied by the caller instead of the system clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Iterable, Mapping, Sequence


SEVERITY_RANK: Mapping[str, int] = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE_RANK: Mapping[str, int] = {"low": 0, "medium": 1, "high": 2}

#: The instant a run is handed, and any instant it records for itself, are in
#: seconds. The build volume states its retention in days, so the two meet here
#: rather than in every caller.
SECONDS_PER_DAY = 86_400.0

#: Fields every ``scan`` report must contain. ``reused_paths`` names the files
#: this run served from the cache instead of analysing.
REPORT_FIELDS = (
    "findings",
    "cache_info",
)
FINDING_FIELDS = (
    "check_id",
    "path",
    "line",
    "severity",
    "confidence",
    "message",
)
#: The volume panel reads these straight from the report, so they describe this
#: run: ``cached_entry_count`` and ``cache_bytes`` are the store as the run
#: leaves it, not the store it found when it started.
CACHE_INFO_FIELDS = (
    "total_files",
    "cache_hits",
    "cache_misses",
    "reused_paths",
    "cached_entry_count",
    "cache_bytes",
)


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    pattern: str
    severity: str
    confidence: str
    message: str
    since_version: tuple[int, int, int]


CHECKS: tuple[Check, ...] = (
    Check(
        "SEC101",
        r"^\s*assert\s",
        "low",
        "high",
        "assert statement outside a test module",
        (1, 0, 0),
    ),
    Check(
        "SEC105",
        r"(?i)\b(password|passwd|secret|api_key|token)\s*=\s*[\"'][^\"']+[\"']",
        "medium",
        "medium",
        "credential assigned from a string literal",
        (1, 0, 0),
    ),
    Check(
        "SEC307",
        r"\beval\s*\(",
        "medium",
        "high",
        "dynamic evaluation of a runtime expression",
        (1, 0, 0),
    ),
    Check(
        "SEC324",
        r"(?i)\bhashlib\.(md5|sha1)\s*\(",
        "medium",
        "high",
        "weak hash primitive",
        (3, 1, 0),
    ),
    Check(
        "SEC602",
        r"shell\s*=\s*True",
        "high",
        "high",
        "subprocess started through a shell",
        (1, 0, 0),
    ),
    Check(
        "SEC608",
        r"(?i)\.execute\s*\(\s*(f[\"']|[\"'][^\"']*[\"']\s*[%+])",
        "high",
        "medium",
        "SQL statement assembled by string formatting",
        (3, 2, 0),
    ),
)
CHECKS_BY_ID: Mapping[str, Check] = {check.check_id: check for check in CHECKS}
_COMPILED: Mapping[str, re.Pattern[str]] = {
    check.check_id: re.compile(check.pattern) for check in CHECKS
}


def parse_version(value: str) -> tuple[int, int, int]:
    parts = str(value).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"analyzer version must be MAJOR.MINOR.PATCH: {value!r}")
    major, minor, patch = (int(part) for part in parts)
    return (major, minor, patch)


@dataclass(frozen=True, slots=True)
class Finding:
    check_id: str
    path: str
    line: int
    severity: str
    confidence: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "path": self.path,
            "line": self.line,
            "severity": self.severity,
            "confidence": self.confidence,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """The complete analysis configuration of one scan run.

    Every field here feeds ``effective_checks``, so two runs over identical
    bytes can produce different findings whenever any of these values differ.
    """

    analyzer_version: str = "3.2.0"
    severity_floor: str = "low"
    confidence_floor: str = "low"
    profile_name: str = "default"
    profile_checks: tuple[str, ...] = ()
    selected_checks: tuple[str, ...] | None = None
    skipped_checks: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScanOptions":
        raw_selected = value.get("selected_checks")
        return cls(
            analyzer_version=str(value.get("analyzer_version", "3.2.0")),
            severity_floor=str(value.get("severity_floor", "low")),
            confidence_floor=str(value.get("confidence_floor", "low")),
            profile_name=str(value.get("profile_name", "default")),
            profile_checks=tuple(str(item) for item in value.get("profile_checks", ())),
            selected_checks=(
                None if raw_selected is None else tuple(str(item) for item in raw_selected)
            ),
            skipped_checks=tuple(str(item) for item in value.get("skipped_checks", ())),
        )


def effective_checks(options: ScanOptions) -> tuple[str, ...]:
    """Return the check identifiers this configuration actually runs."""

    version = parse_version(options.analyzer_version)
    severity_floor = SEVERITY_RANK[options.severity_floor]
    confidence_floor = CONFIDENCE_RANK[options.confidence_floor]
    selected = options.selected_checks
    profile = set(options.profile_checks)
    skipped = set(options.skipped_checks)
    chosen: list[str] = []
    for check in CHECKS:
        if check.since_version > version:
            continue
        if profile and check.check_id not in profile:
            continue
        if selected is not None and check.check_id not in selected:
            continue
        if check.check_id in skipped:
            continue
        if SEVERITY_RANK[check.severity] < severity_floor:
            continue
        if CONFIDENCE_RANK[check.confidence] < confidence_floor:
            continue
        chosen.append(check.check_id)
    return tuple(chosen)


class AnalysisMeter:
    """Records every check invocation so analysis reuse stays measurable."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def reset(self) -> None:
        self.calls.clear()

    def record(self, path: str) -> None:
        self.calls.append(str(path))


METER = AnalysisMeter()


def run_checks(path: str, text: str, options: ScanOptions) -> tuple[Finding, ...]:
    """Analyse one file. This is the authoritative, metered analysis step."""

    METER.record(path)
    active = effective_checks(options)
    findings: list[Finding] = []
    for line_number, line in enumerate(str(text).splitlines(), start=1):
        for check_id in active:
            if _COMPILED[check_id].search(line):
                check = CHECKS_BY_ID[check_id]
                findings.append(
                    Finding(
                        check_id=check_id,
                        path=str(path),
                        line=line_number,
                        severity=check.severity,
                        confidence=check.confidence,
                        message=check.message,
                    )
                )
    findings.sort(key=lambda item: (item.path, item.line, item.check_id))
    return tuple(findings)


class SourceTree:
    """A read-only view of the scanned checkout."""

    def __init__(self, root: str, files: Mapping[str, Mapping[str, Any]]):
        self.root = str(root)
        self._files = {
            str(path): {
                "content": str(entry.get("content", "")),
                "mtime": float(entry.get("mtime", 0.0)),
            }
            for path, entry in dict(files).items()
        }

    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._files))

    def abspath(self, path: str) -> str:
        return f"{self.root.rstrip('/')}/{str(path).lstrip('/')}"

    def stat(self, path: str) -> Mapping[str, Any]:
        entry = self._files[str(path)]
        return {"size": len(entry["content"].encode("utf-8")), "mtime": entry["mtime"]}

    def read_text(self, path: str) -> str:
        return self._files[str(path)]["content"]


class CacheKeyError(KeyError):
    pass


class CacheStore:
    """A persistent key/value store with exact byte accounting."""

    def __init__(self, entries: Mapping[str, str] | None = None):
        self._entries: dict[str, bytes] = {
            str(key): bytes.fromhex(str(value))
            for key, value in dict(entries or {}).items()
        }
        self.gets = 0
        self.puts = 0
        self.deletes = 0
        self.put_bytes = 0

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def get(self, key: str) -> bytes | None:
        self.gets += 1
        return self._entries.get(str(key))

    def put(self, key: str, value: bytes) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("cache values must be bytes")
        text_key = str(key)
        if not text_key:
            raise CacheKeyError("cache keys must be non-empty")
        self.puts += 1
        self.put_bytes += len(value)
        self._entries[text_key] = bytes(value)

    def delete(self, key: str) -> None:
        self.deletes += 1
        self._entries.pop(str(key), None)

    def entry_count(self) -> int:
        return len(self._entries)

    def total_bytes(self) -> int:
        return sum(len(key.encode("utf-8")) + len(value) for key, value in self._entries.items())

    def export_entries(self) -> dict[str, str]:
        return {key: value.hex() for key, value in sorted(self._entries.items())}


@dataclass(slots=True)
class RunContext:
    """Everything one scan run receives besides the tree and the store.

    ``now`` is the instant the pipeline hands this run, in seconds; a run never
    reads a clock of its own.

    ``cache_size_limit_bytes`` is the space the build volume gives this run's
    cache. ``cache_expiry_days`` is the age from when a saved result was produced
    after which a result the current run does not need becomes reclaimable, in
    the days the volume's operators speak in — ``SECONDS_PER_DAY`` is published
    for that reason. Reading a saved result does not reset that age or rewrite
    it. These values describe the volume the run has to live on, not a
    preference: whatever the run leaves in the store is what the volume carries
    until the next run.
    """

    now: float
    cache_size_limit_bytes: int
    cache_expiry_days: float
    incremental: bool = True
    machine: str = "ci-1"
    extra: Mapping[str, Any] = field(default_factory=dict)


def sorted_findings(findings: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalise a findings sequence into the report's canonical order."""

    rows: list[dict[str, Any]] = []
    for item in findings:
        row = item.as_dict() if isinstance(item, Finding) else dict(item)
        rows.append(
            {
                "check_id": str(row["check_id"]),
                "path": str(row["path"]),
                "line": int(row["line"]),
                "severity": str(row["severity"]),
                "confidence": str(row["confidence"]),
                "message": str(row["message"]),
            }
        )
    rows.sort(key=lambda row: (row["path"], row["line"], row["check_id"]))
    return rows


def clean_scan(tree: SourceTree, options: ScanOptions) -> list[dict[str, Any]]:
    """Analyse every file without any cache. This defines correct output."""

    findings: list[Finding] = []
    for path in tree.paths():
        findings.extend(run_checks(path, tree.read_text(path), options))
    return sorted_findings(findings)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def require_report(report: Any) -> Mapping[str, Any]:
    """Validate the shape of a scan report and return it unchanged."""

    if not isinstance(report, Mapping):
        raise TypeError("scan must return a mapping")
    missing = [name for name in REPORT_FIELDS if name not in report]
    if missing:
        raise ValueError(f"scan report is missing fields: {', '.join(missing)}")
    findings = report.get("findings")
    if not isinstance(findings, Sequence) or isinstance(
        findings, (str, bytes, bytearray)
    ):
        raise TypeError("scan report findings must be a sequence")
    for finding in findings:
        if not isinstance(finding, Mapping):
            raise TypeError("every finding must be a mapping")
        absent = [name for name in FINDING_FIELDS if name not in finding]
        if absent:
            raise ValueError(f"finding is missing fields: {', '.join(absent)}")
        if (
            not isinstance(finding["check_id"], str)
            or not isinstance(finding["path"], str)
            or not isinstance(finding["line"], int)
            or isinstance(finding["line"], bool)
            or not isinstance(finding["severity"], str)
            or not isinstance(finding["confidence"], str)
            or not isinstance(finding["message"], str)
        ):
            raise TypeError("finding fields have invalid types")
    cache_info = report.get("cache_info")
    if not isinstance(cache_info, Mapping):
        raise TypeError("scan report cache_info must be a mapping")
    absent = [name for name in CACHE_INFO_FIELDS if name not in cache_info]
    if absent:
        raise ValueError(f"cache_info is missing fields: {', '.join(absent)}")
    for name in (
        "total_files",
        "cache_hits",
        "cache_misses",
        "cached_entry_count",
        "cache_bytes",
    ):
        if not isinstance(cache_info[name], int) or isinstance(cache_info[name], bool):
            raise TypeError("cache_info count fields must be integers")
    reused = cache_info["reused_paths"]
    if (
        not isinstance(reused, Sequence)
        or isinstance(reused, (str, bytes, bytearray))
        or any(not isinstance(path, str) for path in reused)
    ):
        raise TypeError("cache_info reused_paths must be a sequence of paths")
    return report


__all__: Sequence[str] = (
    "CACHE_INFO_FIELDS",
    "FINDING_FIELDS",
    "CHECKS",
    "CHECKS_BY_ID",
    "CacheKeyError",
    "CacheStore",
    "Check",
    "Finding",
    "METER",
    "REPORT_FIELDS",
    "RunContext",
    "SECONDS_PER_DAY",
    "ScanOptions",
    "SourceTree",
    "canonical_json",
    "clean_scan",
    "effective_checks",
    "parse_version",
    "require_report",
    "run_checks",
    "sorted_findings",
)
