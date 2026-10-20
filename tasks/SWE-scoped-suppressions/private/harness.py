'Deterministic, sandboxed analysis of one estate-audit workspace.'

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    EXPECTED_WAIVERS,
    EXPECTED_SPLIT,
    LAYOUT_PAIRS,
    POLICY_PROFILES,
    SITES,
    build_program,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("audit/waivers.py", "audit/shared.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-estate-",
)


PRIVATE_CASE: Mapping[str, Any] = {"session": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "release-review": "release-review",
    "incident-shell-injection": "incident-shell-injection",
    "march-re-export": "march-re-export",
    "quarterly-audit": "quarterly-audit",
}

BUCKETS: Mapping[str, str] = {
    "unit_scope_coverage": "scope_failures",
    "region_extent": "region_failures",
    "selector_resolution": "selector_failures",
    "suppression_accounting": "accounting_failures",
    "audit_run_equality": "audit_failures",
}

_CACHE = AnalysisCache()
_CONTRACT: Any = None


def reference_contract() -> Any:
    "The frozen `audit/contract.py`, loaded from the project's own tree."

    global _CONTRACT
    if _CONTRACT is None:
        path = TASK_ROOT / "workspace" / "audit" / "contract.py"
        spec = importlib.util.spec_from_file_location("_estate_audit_contract", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _CONTRACT = module
    return _CONTRACT


def _rule_name(rule_id: str) -> str:
    rule = reference_contract().rule_of(rule_id)
    return rule.name if rule is not None else str(rule_id)


def _entry(path: str) -> str:
    return str(path).rsplit(".", 1)[-1]


class Review:
    'Everything the five checks read from one run of the private session.'

    def __init__(self, candidate: Mapping[str, Any]):
        self.rows = [dict(row) for row in candidate.get("runs", ())]

    def errors(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if row.get("error")]

    def weekly(self, document: str) -> dict[str, Any] | None:
        for row in self.rows:
            if row["document"] == document and not row["ignore_waivers"]:
                return row
        return None

    def audits(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if row["ignore_waivers"]]

    @staticmethod
    def reported(row: Mapping[str, Any]) -> Counter:
        return Counter(
            (str(item["path"]), str(item["rule"])) for item in row.get("findings", ())
        )

    @staticmethod
    def baseline(row: Mapping[str, Any]) -> Counter:
        return Counter(
            (str(item["path"]), str(item["rule"])) for item in row.get("baseline", ())
        )

    @staticmethod
    def line_of(row: Mapping[str, Any], path: str, rule: str) -> int:
        for item in row.get("baseline", ()):
            if str(item["path"]) == path and str(item["rule"]) == rule:
                return int(item["line"])
        return 0

    @staticmethod
    def counters(row: Mapping[str, Any]) -> tuple[int, int, int]:
        counters = dict(row.get("counters") or {})
        return (
            int(counters.get("reported", -1)),
            int(counters.get("blanket", -1)),
            int(counters.get("by_rule", -1)),
        )

    @staticmethod
    def identities(
        row: Mapping[str, Any], field: str = "findings"
    ) -> list[tuple[str, int, int, str, str]]:
        return [
            (
                str(item["rule"]),
                int(item["unit"]),
                int(item["line"]),
                str(item["path"]),
                str(item["value"]),
            )
            for item in row.get(field, ())
        ]


def _expected_rows(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Build the exact private oracle from the frozen detector and waiver marks.'

    contract = reference_contract()
    rows: list[dict[str, Any]] = []
    for raw in program.get("runs", ()):
        spec = dict(raw)
        name = str(spec["document"])
        ignore = bool(spec.get("ignore_waivers", False))
        profile = contract.Profile(
            name=str(spec.get("profile", "release")), ignore_waivers=ignore
        )
        document = contract.parse_document(str(spec["text"]), name)
        baseline = list(contract.baseline_findings(document, profile))
        classes = EXPECTED_WAIVERS.get(name, {})
        findings = []
        blanket = by_rule = 0
        for item in baseline:
            mark = "reported" if ignore else classes.get((item.path, item.rule_id), "reported")
            if mark == "blanket":
                blanket += 1
            elif mark == "by_rule":
                by_rule += 1
            else:
                findings.append(item)

        def serialise(item: Any) -> dict[str, Any]:
            return {
                "rule": str(item.rule_id),
                "unit": int(item.unit),
                "line": int(item.line),
                "path": str(item.path),
                "value": str(item.value),
            }

        rows.append({
            "document": name,
            "profile": profile.name,
            "ignore_waivers": ignore,
            "baseline": [serialise(item) for item in baseline],
            "findings": [serialise(item) for item in findings],
            "counters": {
                "reported": len(findings),
                "blanket": blanket,
                "by_rule": by_rule,
            },
        })
    return rows


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _site_failure(row: Mapping[str, Any], site: Mapping[str, str]) -> dict[str, Any] | None:
    'Whether one entry of one document came out as the review expects.'

    path, rule = str(site["path"]), str(site["rule"])
    is_open = Review.reported(row)[(path, rule)] > 0
    wanted_open = str(site["expect"]) == "open"
    if is_open == wanted_open:
        return None
    return _fail(
        str(site["mode"]),
        document=str(row["document"]),
        profile=str(row["profile"]),
        path=path,
        entry=_entry(path),
        rule=rule,
        rule_name=_rule_name(rule),
        line=Review.line_of(row, path, rule),
    )


def _sites_in(review: Review, bucket: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for site in SITES:
        if str(site["bucket"]) != bucket:
            continue
        row = review.weekly(str(site["document"]))
        if row is None:
            continue
        failure = _site_failure(row, site)
        if failure is not None:
            failures.append(failure)
    return failures


def _scope_failures(review: Review, expected_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    'A waiver covers the entry it was written on, whatever its layout.'

    failures = _sites_in(review, "scope_failures")
    for first, second in LAYOUT_PAIRS:
        left, right = review.weekly(first), review.weekly(second)
        if left is None or right is None:
            continue
        difference = (Review.reported(left) - Review.reported(right)) + (
            Review.reported(right) - Review.reported(left)
        )
        for (path, rule), _ in sorted(difference.items()):
            failures.append(_fail(
                "coverage_changed_with_layout",
                document=first,
                other_document=second,
                document_count=Review.reported(left)[(path, rule)],
                other_count=Review.reported(right)[(path, rule)],
                profile=str(left["profile"]),
                path=path,
                entry=_entry(path),
                rule=rule,
                rule_name=_rule_name(rule),
                line=Review.line_of(left, path, rule),
            ))
    expected_weekly = {
        str(row["document"]): row for row in expected_rows if not row["ignore_waivers"]
    }
    for document, expected in expected_weekly.items():
        row = review.weekly(document)
        if row is None:
            continue
        wanted = Counter(
            (str(item["path"]), str(item["rule"]), int(item["line"]))
            for item in expected["findings"]
        )
        actual = Counter(
            (str(item["path"]), str(item["rule"]), int(item["line"]))
            for item in row.get("findings", ())
        )
        difference = (wanted - actual) + (actual - wanted)
        if difference:
            path, rule, line = sorted(difference)[0]
            failures.append(_fail(
                "report_filter_disagreed",
                document=document,
                profile=str(row["profile"]),
                path=path,
                entry=_entry(path),
                rule=rule,
                rule_name=_rule_name(rule),
                line=line,
                expected_count=wanted[(path, rule, line)],
                actual_count=actual[(path, rule, line)],
            ))
    return failures


def _region_failures(review: Review) -> list[dict[str, Any]]:
    'A region covers the block it was opened in, and stops where it ends.'

    return _sites_in(review, "region_failures")


def _selector_failures(review: Review) -> list[dict[str, Any]]:
    'A token nobody can place names no rule, and a named rule names one rule.'

    return _sites_in(review, "selector_failures")


def _accounting_failures(review: Review, expected_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    'Every finding is accounted once, and a blanket waiver is booked as one.'

    failures: list[dict[str, Any]] = []
    expected_by_run = {
        (str(row["document"]), bool(row["ignore_waivers"])): row for row in expected_rows
    }
    for row in review.rows:
        reported, blanket, by_rule = Review.counters(row)
        listed = len(list(row.get("findings", ())))
        expected = expected_by_run[(str(row["document"]), bool(row["ignore_waivers"]))]
        total = len(expected["baseline"])
        if reported + blanket + by_rule != total:
            failures.append(_fail(
                "counts_do_not_sum",
                document=str(row["document"]),
                profile=str(row["profile"]),
                baseline_total=total,
                open_count=reported,
                blanket=blanket,
                by_rule=by_rule,
                counted_total=reported + blanket + by_rule,
            ))
        elif reported != listed:
            failures.append(_fail(
                "reported_count_disagrees",
                document=str(row["document"]),
                profile=str(row["profile"]),
                open_count=reported,
                listed=listed,
            ))
        expected_counters = Review.counters(expected)
        if (reported, blanket, by_rule) != expected_counters:
            failures.append(_fail(
                "counter_split_disagreed",
                document=str(row["document"]),
                profile=str(row["profile"]),
                ignore_waivers=bool(row["ignore_waivers"]),
                open_count=reported,
                blanket=blanket,
                by_rule=by_rule,
                expected_open=expected_counters[0],
                expected_blanket=expected_counters[1],
                expected_by_rule=expected_counters[2],
            ))
    for document, expected in EXPECTED_SPLIT.items():
        row = review.weekly(document)
        if row is None:
            continue
        _, blanket, by_rule = Review.counters(row)
        if blanket < int(expected["blanket"]) and by_rule > int(expected["by_rule"]):
            failures.append(_fail(
                "blanket_booked_as_specific",
                document=document,
                profile=str(row["profile"]),
                blanket=blanket,
                by_rule=by_rule,
                expected_blanket=int(expected["blanket"]),
            ))
    return failures


def _audit_failures(review: Review, expected_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    'The reconciliation run reads the estate as the rule table wrote it.'

    failures: list[dict[str, Any]] = []
    expected_by_run = {
        (str(row["document"]), bool(row["ignore_waivers"])): row for row in expected_rows
    }
    for row in review.rows:
        expected = expected_by_run[(str(row["document"]), bool(row["ignore_waivers"]))]
        reported = Review.identities(row)
        baseline = Review.identities(expected, "baseline")
        if row["ignore_waivers"] and reported != baseline:
            missing_counts = Counter(baseline) - Counter(reported)
            if missing_counts:
                first = next(item for item in baseline if missing_counts[item])
                failures.append(_fail(
                    "audit_hid_findings",
                    document=str(row["document"]),
                    profile=str(row["profile"]),
                    baseline_total=len(baseline),
                    open_count=len(reported),
                    missing=sum(missing_counts.values()),
                    rule=first[0],
                    rule_name=_rule_name(first[0]),
                    unit=first[1],
                    line=first[2],
                    path=first[3],
                    value=first[4],
                    entry=_entry(first[3]),
                ))
            else:
                position, first = next(
                    (index, item) for index, item in enumerate(reported, start=1)
                    if index > len(baseline) or item != baseline[index - 1]
                )
                failures.append(_fail(
                    "report_altered_a_finding",
                    document=str(row["document"]),
                    profile=str(row["profile"]),
                    rule=first[0],
                    rule_name=_rule_name(first[0]),
                    unit=first[1],
                    line=first[2],
                    path=first[3],
                    value=first[4],
                    entry=_entry(first[3]),
                    position=position,
                ))
            continue
        remaining = list(baseline)
        altered: tuple[str, int, int, str, str] | None = None
        altered_position = 0
        for position, item in enumerate(reported, start=1):
            while remaining and remaining[0] != item:
                remaining.pop(0)
            if not remaining:
                altered = item
                altered_position = position
                break
            remaining.pop(0)
        if altered is not None:
            failures.append(_fail(
                "report_altered_a_finding",
                document=str(row["document"]),
                profile=str(row["profile"]),
                rule=altered[0],
                rule_name=_rule_name(altered[0]),
                unit=altered[1],
                line=altered[2],
                path=altered[3],
                value=altered[4],
                entry=_entry(altered[3]),
                position=altered_position,
            ))
            continue
    return failures


def _analyse(candidate: Mapping[str, Any], expected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    review = Review(candidate)
    return {
        "scope_failures": _scope_failures(review, expected_rows),
        "region_failures": _region_failures(review),
        "selector_failures": _selector_failures(review),
        "accounting_failures": _accounting_failures(review, expected_rows),
        "audit_failures": _audit_failures(review, expected_rows),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a review did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the audit ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the audit ended without saying why"
    return f"the audit stopped part way through the estate: {line[:200]}"


def _row_error(row: Mapping[str, Any]) -> str:
    return (
        f"the audit stopped part way through the estate: reading "
        f"{row['document']} ended with {str(row.get('error'))[:160]}"
    )


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Read the private review session with this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["session"]))
        expected_rows = _expected_rows(program)
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        buckets = tuple(BUCKETS.values())
        if not candidate.get("ok"):
            analysis = dict(failed_analysis(_console_error(candidate), buckets))
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            broken = Review(candidate).errors()
            if broken:
                analysis = dict(failed_analysis(_row_error(broken[0]), buckets))
            else:
                analysis = _analyse(candidate, expected_rows)
        analysis["case"] = {
            "session": "release",
            "documents": len(program["runs"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _reconciliation(root: Path) -> Mapping[str, Any]:
    path = root / "reconciliation.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, Mapping) else {}


def _signed_off(root: Path, document: str) -> Mapping[str, Any] | None:
    for entry in _reconciliation(root).get("documents", ()):
        if isinstance(entry, Mapping) and str(entry.get("document")) == f"{document}.policy":
            return dict(entry)
    return None


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _document_view(root: Path, name: str) -> dict[str, Any]:
    contract = reference_contract()
    text = (root / "policies" / f"{name}.policy").read_text(encoding="utf-8")
    document = contract.parse_document(text, name)
    profile = contract.Profile(name=POLICY_PROFILES.get(name, "release"))
    return {
        "document": f"policies/{name}.policy",
        "profile": profile.name,
        "lines": len(document.lines),
        "entries": [
            f"{unit.path} lines {unit.start_line}-{unit.end_line} depth {unit.depth}"
            for unit in document.units
        ],
        "the_rule_table_objects_to": [
            f"{item.rule_id} line {item.line} {item.path}"
            for item in contract.baseline_findings(document, profile)
        ],
    }


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    contract = reference_contract()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        session = PUBLIC_RECORDS.get(record_id)
        program = build_program(session) if session else {"runs": ()}
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "reads": [
                f"{run['document']}.policy under {run['profile']}"
                + (" with waivers ignored" if run["ignore_waivers"] else "")
                for run in program.get("runs", ())
            ],
        })
    return {
        "summary": "The estate audit workspace and the review sessions the estate replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "audit_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "audit").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "profiles": {
                name: list(ids) for name, ids in dict(contract.PROFILES).items()
            },
            "rules": [f"{rule.id} ({rule.name})" for rule in contract.RULES],
        },
        "documents": [_document_view(root, name) for name in sorted(POLICY_PROFILES)],
        "records": records,
    }


def _run_view(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    reported, blanket, by_rule = Review.counters(row)
    view: dict[str, Any] = {
        "document": f"{row['document']}.policy",
        "profile": row["profile"],
        "waivers_ignored": bool(row["ignore_waivers"]),
        "the_rule_table_objects_to": [
            f"{item['rule']} line {item['line']} {item['path']}"
            for item in row.get("baseline", ())
        ],
        "the_report_came_back_with": [
            f"{item['rule']} line {item['line']} {item['path']}"
            for item in row.get("findings", ())
        ],
        "counters": {
            "open": reported,
            "waived_without_a_rule": blanket,
            "waived_for_a_named_rule": by_rule,
        },
    }
    if row.get("error"):
        view["error"] = row["error"]
    signed = _signed_off(root, str(row["document"]))
    if signed is not None:
        view["last_signed_off"] = signed
    return view


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded review session and report what it printed.'

    root = Path(artifact_dir)
    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    session = PUBLIC_RECORDS.get(record_id)
    if session is None:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(session)
    candidate = PROJECT.invoke(root, dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} session could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    rows = [dict(row) for row in candidate.get("runs", ())]
    return {
        "summary": f"The {record_id} session ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "documents_read": len(rows),
        },
        "public": {
            "what_each_document_produced": [_run_view(root, row) for row in rows],
            "console": candidate.get("stdout", ""),
        },
    }
