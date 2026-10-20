'Deterministic, sandboxed analysis of one relay workspace.'

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import build_program


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("relay/vault.py", "relay/extras.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-relay-",
)


PRIVATE_PROFILE = "release"


PUBLIC_RECORDS: Mapping[str, str] = {
    "nightly-vendor-sweep": "sweep",
    "assets-through-the-edge": "edge",
    "session-rotation": "rotation",
    "desk-audit": "audit",
}

BUCKETS: Mapping[str, str] = {
    "grant_audience": "audience_failures",
    "grant_lifetime": "lifetime_failures",
    "grant_identity_and_bounds": "identity_failures",
    "fold_invariance": "folding_failures",
    "grant_send_order": "order_failures",
}

_CACHE = AnalysisCache()
_WIRE: Any = None


def reference_wire() -> Any:
    "The frozen `relay/wire.py`, loaded from the project's own tree."

    global _WIRE
    if _WIRE is None:
        path = TASK_ROOT / "workspace" / "relay" / "wire.py"
        spec = importlib.util.spec_from_file_location("_relay_wire_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _WIRE = module
    return _WIRE


def _seconds(value: Any) -> float | int:
    number = round(float(value), 3)
    return int(number) if number == int(number) else number


class Review:
    'Everything the five checks read from one run of the sweep.'

    def __init__(self, result: Mapping[str, Any], program: Mapping[str, Any]):
        self.program = program
        self.profile = dict(program.get("profile", {}))
        self.steps = [dict(row) for row in result.get("steps", ())]
        self.rows = {str(row.get("label")): row for row in self.steps}

    def row(self, label: str) -> dict[str, Any]:
        return self.rows.get(label, {})

    def names(self, label: str) -> list[str]:
        return [str(item) for item in self.row(label).get("grant_names", ())]

    def pairs(self, label: str) -> list[tuple[str, str]]:
        wire = reference_wire()
        return list(wire.read_grant_header(str(self.row(label).get("presented", ""))))

    def issued_values(self, label: str) -> set[str]:
        wire = reference_wire()
        address = wire.parse_address(str(self.row(label).get("url", "")))
        spec = dict(self.program.get("hosts", {})).get(address.origin, {})
        return {str(value) for value in dict(spec.get("issued", {}))}

    def reason(self, label: str) -> str:
        return str(self.row(label).get("reason", ""))

    def host(self, label: str) -> str:
        return str(self.row(label).get("host", ""))

    def setting(self, field: str, default: Any) -> Any:
        return self.profile.get(field, default)

    def handed(self, name: str, before: float) -> tuple[float, str] | None:
        'When a grant of this name was last handed over before `before`.'

        found: tuple[float, str] | None = None
        for row in self.steps:
            moment = float(row.get("at_s", 0.0))
            if moment > before:
                continue
            for line in row.get("handed_back", ()):
                head = str(line).split(";")[0].strip()
                if head.startswith(f"{name}="):
                    found = (moment, str(line))
        return found

    def granted_for(self, directive: str, handed_at: float) -> float | int:
        'How long the host said that grant would stay live.'

        wire = reference_wire()
        for chunk in str(directive).split(";")[1:]:
            key, mark, item = chunk.partition("=")
            key = key.strip().lower()
            if not mark:
                continue
            if key == "ttl":
                try:
                    return _seconds(float(item.strip()))
                except ValueError:
                    return 0
            if key == "until":
                moment = wire.parse_stamp(item.strip())
                if moment is not None:
                    return _seconds(moment - handed_at)
        return 0

    def attribute(self, directive: str, wanted: str) -> str:
        for chunk in str(directive).split(";")[1:]:
            key, mark, item = chunk.partition("=")
            if mark and key.strip().lower() == wanted:
                return item.strip()
        return ""


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _unissued_failures(
    review: Review, phase: str, *, exclude: Sequence[str] = ()
) -> list[dict[str, Any]]:
    'Credential values a host rejected, attributed to their traffic family.'

    failures: list[dict[str, Any]] = []
    excluded = set(exclude)
    for row in review.steps:
        label = str(row.get("label", ""))
        if (str(row.get("phase", "")) != phase or label in excluded
                or str(row.get("reason", "")) != "unexpected_grant"):
            continue
        issued = review.issued_values(label)
        invalid = next(
            ((name, value) for name, value in review.pairs(label) if value not in issued),
            ("a grant", ""),
        )
        failures.append(_fail(
            "grant_rejected_as_unissued", label=label, host=str(row.get("host", "")),
            grant_name=invalid[0], reason="unexpected_grant"))
    return failures


_MUST_CARRY = (
    ("audience-desk", "sid"),
    ("audience-files", "sid"),
    ("audience-open-plan", "room"),
    ("audience-tools-edit", "kit"),
    ("audience-odd-check", "trail"),
)
_MUST_NOT_CARRY = (("audience-openroom", "room", "/open"),
                   ("audience-desk-other", "kit", "/desk/tools"))
_HOST_ONLY_SIBLINGS = (
    ("audience-sibling-open", "room"),
    ("audience-sibling-tools", "kit"),
    ("audience-sibling-trail", "trail"),
)


def _audience_failures(review: Review) -> list[dict[str, Any]]:
    'Which hosts, paths and schemes a grant reaches.'

    failures: list[dict[str, Any]] = []
    for label in ("audience-lookalike", "audience-partner"):
        if review.reason(label) == "unexpected_grant":
            failures.append(_fail(
                "grant_sent_beyond_its_scope", label=label, host=review.host(label),
                grant_name=(review.names(label) or ["a grant"])[0],
                scope="grounds.example"))
    if review.reason("audience-plain") == "unexpected_grant":
        failures.append(_fail(
            "sealed_grant_sent_in_the_clear", label="audience-plain",
            host=review.host("audience-plain"),
            grant_name=(review.names("audience-plain") or ["a grant"])[0],
            scheme=str(review.row("audience-plain").get("scheme", "http"))))
    for label, name in _MUST_CARRY:
        if name not in review.names(label):
            failures.append(_fail(
                "grant_withheld_from_its_scope", label=label, host=review.host(label),
                grant_name=name, reason=review.reason(label)))
    for label, name, under in _MUST_NOT_CARRY:
        if name in review.names(label):
            failures.append(_fail(
                "grant_sent_outside_its_path", label=label, host=review.host(label),
                grant_name=name, path=str(review.row(label).get("path", "")), under=under))
    for label, name in _HOST_ONLY_SIBLINGS:
        if name in review.names(label):
            failures.append(_fail(
                "host_only_grant_sent_to_sibling", label=label, host=review.host(label),
                grant_name=name))


    specific = {
        "audience-lookalike", "audience-partner", "audience-plain",
        *(label for label, _name, _under in _MUST_NOT_CARRY),
        *(label for label, _name in _HOST_ONLY_SIBLINGS),
    }
    failures.extend(_unissued_failures(review, "audience", exclude=tuple(specific)))
    return failures


_EXPIRED_SITES = (("life-at-deadline", "pass"), ("life-late", "pass"),
                  ("life-after-ttl", "pass"), ("life-slip-late", "slip"))


def _lifetime_failures(review: Review) -> list[dict[str, Any]]:
    'How long a grant stays live, and when it stops.'

    failures: list[dict[str, Any]] = []
    for label, name in _EXPIRED_SITES:
        if name not in review.names(label):
            continue
        moment = float(review.row(label).get("at_s", 0.0))
        handed = review.handed(name, moment)
        handed_at, directive = handed if handed else (moment, "")
        failures.append(_fail(
            "expired_grant_still_presented", label=label, host=review.host(label),
            grant_name=name, waited_s=_seconds(moment - handed_at),
            lasted_s=review.granted_for(directive, handed_at)))
    if "pass" in review.names("life-after-logout"):
        failures.append(_fail(
            "revoked_grant_still_presented", label="life-after-logout",
            host=review.host("life-after-logout"), grant_name="pass",
            presented=str(review.row("life-after-logout").get("presented", ""))))
    if "note" not in review.names("life-odd-check"):
        handed = review.handed("note", float(review.row("life-odd-check").get("at_s", 0.0)))
        directive = handed[1] if handed else ""
        failures.append(_fail(
            "unreadable_deadline_dropped_the_grant", label="life-odd-check",
            host=review.host("life-odd"), grant_name="note",
            stamp=review.attribute(directive, "until") or "next Tuesday"))
    failures.extend(_unissued_failures(review, "lifetime"))
    return failures


def _identity_failures(review: Review) -> list[dict[str, Any]]:
    'One live entry per grant, and how many a run keeps.'

    failures: list[dict[str, Any]] = []
    for label in ("ident-probe-1", "ident-probe-2", "ident-key-after"):
        if review.reason(label) == "repeated_grant":
            names = review.names(label)
            failures.append(_fail(
                "same_grant_presented_twice", label=label, host=review.host(label),
                grant_name=next((name for name in names if names.count(name) > 1), "key"),
                presented_count=len(names)))
    held = review.names("ident-probe-2").count("key")
    if held > 1:
        failures.append(_fail(
            "refresh_left_two_live_grants", label="ident-probe-2",
            host=review.host("ident-probe-2"), grant_name="key", presented_count=held))
    limit = int(review.setting("max_grants_per_scope", 6))
    probe = review.row("ident-tile-probe")
    tiles = [name for name in review.names("ident-tile-probe") if name.startswith("tile")]
    if len(tiles) > limit or review.reason("ident-tile-probe") == "grant_header_too_large":
        failures.append(_fail(
            "bounds_exceeded", label="ident-tile-probe", host=review.host("ident-tile-probe"),
            presented_count=len(tiles), max_grants_per_scope=limit,
            header_bytes=int(probe.get("header_bytes", 0)),
            max_header_bytes=int(probe.get("max_header_bytes", 0))))
    if "key" not in review.names("ident-key-after"):
        failures.append(_fail(
            "trim_dropped_the_established_grant", label="ident-key-after",
            host=review.host("ident-key-after"), grant_name="key",
            max_grants_per_scope=limit))
    tile_steps = [
        op for op in review.program.get("operations", ())
        if re.fullmatch(r"ident-tile-\d+", str(op.get("label", "")))
    ]
    survivor = f"tile{len(tile_steps) - limit + 1}"
    after_retirement = [
        name for name in review.names("ident-retire-probe") if name.startswith("tile")
    ]
    if survivor not in after_retirement:
        failures.append(_fail(
            "pressure_survivor_missing_after_retirement", label="ident-retire-probe",
            host=review.host("ident-retire-probe"), grant_name=survivor,
            presented_count=len(after_retirement), max_grants_per_scope=limit))
    returned = [name for name in after_retirement if name != survivor]
    if returned:
        failures.append(_fail(
            "trimmed_grant_returned_after_retirement", label="ident-retire-probe",
            host=review.host("ident-retire-probe"), grant_name=returned[0],
            presented_count=len(after_retirement), expected_survivor=survivor,
            max_grants_per_scope=limit))
    failures.extend(_unissued_failures(review, "identity"))
    return failures


def _folding_failures(review: Review) -> list[dict[str, Any]]:
    'The same replies, one grant per header or several folded into one.'

    failures: list[dict[str, Any]] = []
    for letter in ("a", "b", "c"):
        plain, folded = f"fold-plain-{letter}", f"fold-edge-{letter}"
        one, several = set(review.names(plain)), set(review.names(folded))
        for missing in sorted(one - several):
            failures.append(_fail(
                "folded_reply_lost_a_grant", label=folded, host=review.host(folded),
                missing_grant=missing, one_per_header=len(one), folded=len(several)))
        for extra in sorted(several - one):
            failures.append(_fail(
                "junk_segment_stored_as_a_grant", label=folded, host=review.host(folded),
                junk_grant=extra, folded=len(several)))
        one_pairs, several_pairs = set(review.pairs(plain)), set(review.pairs(folded))
        for name in sorted(one & several):
            expected = sorted(value for held_name, value in one_pairs if held_name == name)
            actual = sorted(value for held_name, value in several_pairs if held_name == name)
            if expected != actual:
                failures.append(_fail(
                    "folded_reply_changed_a_grant", label=folded,
                    host=review.host(folded), grant_name=name,
                    one_per_header=len(one_pairs), folded=len(several_pairs)))
    failures.extend(_unissued_failures(review, "folding"))
    return failures


_ORDER_SITES = (("order-team-report", "wrong_desk_on_a_scoped_page"),
                ("order-desk-a", "wrong_desk_after_re_entering"),
                ("order-desk-b", "wrong_desk_after_re_entering"))


def _order_failures(review: Review) -> list[dict[str, Any]]:
    'Which grant of a name the host reads first.'

    failures: list[dict[str, Any]] = []
    for label, kind in _ORDER_SITES:
        row = review.row(label)
        entered = str(row.get("entered_as", ""))
        acted = str(row.get("acted_for", ""))
        if acted == entered:
            continue


        if "tag" not in review.names(label):
            kind = "page_read_with_no_desk_grant"
        failures.append(_fail(
            kind, label=label, host=review.host(label), acted_for=acted or "no desk at all",
            entered_as=entered, path=str(row.get("path", ""))))
    failures.extend(_unissued_failures(review, "order"))
    return failures


def _analyse(result: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(result, program)
    return {
        "audience_failures": _audience_failures(review),
        "lifetime_failures": _lifetime_failures(review),
        "identity_failures": _identity_failures(review),
        "folding_failures": _folding_failures(review),
        "order_failures": _order_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(result: Mapping[str, Any]) -> str:
    'The one line the console shows when a sweep did not finish.'

    reported = str(result.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(result.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the run ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the run ended without saying why"
    return f"the sweep stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private sweep against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(PRIVATE_PROFILE)
        result = PROJECT.invoke(artifact_dir, dict(program))
        if not result.get("ok"):
            analysis = dict(failed_analysis(_console_error(result), tuple(BUCKETS.values())))
            diagnostic = result.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(result, program)
        analysis["case"] = {
            "traffic": PRIVATE_PROFILE,
            "requests": sum(
                1 for op in program["operations"] if str(op.get("op")) == "get"
            ),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _fleet(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "origin": origin,
            "session_name": spec.get("session_name") or None,
            "needs_session_under": list(spec.get("needs_session_under", ())),
            "max_header_bytes": spec.get("max_header_bytes"),
            "writes_several_grants_into_one_header": bool(spec.get("folds")),
        }
        for origin, spec in sorted(dict(program.get("hosts", {})).items())
    ]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        records.append({
            "record": f"project_records/{path.name}",
            "scene": raw.get("scene"),
            "requests": sum(
                1 for op in program.get("operations", ()) if str(op.get("op")) == "get"
            ),
            "hosts": [row["origin"] for row in _fleet(program)] if program else [],
        })
    return {
        "summary": "The relay workspace and the stretches of traffic the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "relay_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "relay").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "job_profile": dict(build_program(PRIVATE_PROFILE)["profile"]),
        },
        "records": records,
    }


def _log_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "step": row.get("step"),
            "label": row.get("label"),
            "url": row.get("url"),
            "at_s": row.get("at_s"),
            "entered_as": row.get("entered_as"),
            "grant_header": row.get("presented"),
            "grant_names": list(row.get("grant_names", ())),
            "grant_count": len(list(row.get("grant_names", ()))),
            "grant_header_bytes": row.get("header_bytes"),
            "host_max_header_bytes": row.get("max_header_bytes"),
            "status": row.get("status"),
            "reason": row.get("reason"),
            "acted_for": row.get("acted_for"),
            "handed_back": list(row.get("handed_back", ())),
        }
        for row in result.get("steps", ())
    ]


def run_public_replay(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    "Replay one recorded stretch of traffic and report the job's request log."

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    result = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not result.get("ok"):
        return {
            "summary": f"The {record_id} traffic could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": result.get("error", "unknown failure"),
                "diagnostic": result.get("diagnostic"),
            },
        }
    return {
        "summary": f"The {record_id} traffic ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "job_profile": dict(program.get("profile", {})),
            "request_count": len(result.get("steps", ())),
        },
        "public": {
            "the_fleet": _fleet(program),
            "request_log": _log_rows(result),
        },
    }
