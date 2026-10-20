'Deterministic, sandboxed review of one publishing workspace.'

from __future__ import annotations

from collections import defaultdict
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

from .workload import build_program, reconciled_block


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("publish/uploader.py", "publish/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-publish-",
    timeout=60.0,
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "2.4.0-partial": "partial",
    "2.3.7-throttled": "throttled",
    "2.4.1-token-revoked": "revoked",
    "2.3.9-reconciled": "reconciled",
}

BUCKETS: Mapping[str, str] = {
    "published_bytes_match_the_build": "body_failures",
    "attempt_ledger_matches_the_host_log": "ledger_failures",
    "refusals_are_answered_not_retried": "answer_failures",
    "waits_follow_the_hosts_direction": "wait_failures",
    "release_is_independent_of_publish_order": "order_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None
_TOLERANCE = 0.5


def reference_protocol() -> Any:
    "The frozen `publish/protocol.py`, loaded from the project's own tree."
    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "publish" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_publish_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _ms(value: Any) -> float | int:
    'A clock reading as the console prints it: whole milliseconds where it can.'
    number = round(float(value), 3)
    return int(number) if number == int(number) else number


def _lines(report: Any) -> list[dict[str, Any]]:
    'The attempts block a release job printed, read defensively.'
    raw = report.get("publish_attempts") if isinstance(report, Mapping) else None
    rows: list[dict[str, Any]] = []
    for entry in raw if isinstance(raw, list) else ():
        if not isinstance(entry, Mapping):
            continue
        try:
            number = int(entry.get("attempt"))
        except (TypeError, ValueError):
            number = 0
        rows.append({
            "publisher": str(entry.get("publisher", "")),
            "instance": str(entry.get("instance", "")),
            "target": str(entry.get("target", "")), "attempt": number,
            "status": str(entry.get("status", "")), "error": entry.get("error")})
    return rows


def _failure_lines(report: Any) -> list[dict[str, Any]]:
    raw = report.get("failures") if isinstance(report, Mapping) else None
    return [dict(entry) for entry in (raw if isinstance(raw, list) else ()) if isinstance(entry, Mapping)]


class Review:
    'Everything the five checks read from one run of the release work.'

    def __init__(self, candidate: Mapping[str, Any]):
        self.settings = dict(candidate.get("settings", {}))
        self.releases = {str(entry.get("phase")): dict(entry)
                         for entry in candidate.get("releases", ())}

    def release(self, phase: str) -> dict[str, Any]:
        return self.releases.get(phase, {})

    def items(self, phase: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self.release(phase).get("items", ())]

    def puts(self, phase: str) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.release(phase).get("log", ())
                if str(entry.get("call")) == "put"]

    def calls(self, phase: str) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.release(phase).get("log", ())]

    def puts_for(self, phase: str, instance: str, target: str) -> list[dict[str, Any]]:
        return [entry for entry in self.puts(phase)
                if entry["instance"] == instance and entry["target"] == target]

    def ledger(self, phase: str) -> list[dict[str, Any]]:
        return _lines(self.release(phase).get("report"))

    def objects(self, phase: str) -> dict[tuple[str, str], tuple[int, str]]:
        return {
            (str(row["instance"]), str(row["target"])): (int(row["bytes"]), str(row["digest"]))
            for row in self.release(phase).get("objects", ())
        }

    def said_about(self, phase: str, instance: str, target: str) -> str:
        for entry in _failure_lines(self.release(phase).get("report")):
            if str(entry.get("instance")) == instance and str(entry.get("target")) == target:
                return str(entry.get("message", ""))
        return ""

    def setting(self, field: str, default: float) -> float:
        try:
            return float(self.settings.get(field, default))
        except (TypeError, ValueError):
            return float(default)

    def verdict(self, put: Mapping[str, Any]) -> str:
        'How the toolchain itself reads the answer the host gave.'
        protocol = reference_protocol()
        return protocol.classify_outcome(protocol.Outcome(
            status=put.get("status"), error=put.get("error"),
            timeout=bool(put.get("timeout", False)),
            temporary=bool(put.get("temporary", False))))


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _status_word(put: Mapping[str, Any]) -> str:
    status = put.get("status")
    return "an error with no status" if status is None else str(int(status))


def _try_word(number: int | None) -> str:
    return "none of the tries" if not number else f"try {int(number)}"


def _body_failures(review: Review) -> list[dict[str, Any]]:
    'What the host holds is what the build made, for every file.'
    return [failure for phase in review.releases
            for failure in _phase_body_failures(review, phase)]


def _phase_body_failures(review: Review, phase: str) -> list[dict[str, Any]]:
    stored = review.objects(phase)
    failures: list[dict[str, Any]] = []
    for item in review.items(phase):
        key = (item["instance"], item["target"])
        found = stored.get(key)
        puts = review.puts_for(phase, *key)
        accepted = [put for put in puts if put.get("accepted")]
        expected = (int(item["bytes"]), str(item["digest"]))
        common = {
            "phase": phase,
            "artifact": item["artifact"],
            "target": item["target"],
            "instance": item["instance"],
            "built_bytes": int(item["bytes"]),
        }


        if found is None and (phase == "main" or accepted):
            failures.append(_fail(
                "artifact_never_landed", **common,
                tries=len(puts)))
        elif found is not None and found != expected:
            failures.append(_fail(
                "stored_body_is_not_the_artifact", **common, stored_bytes=int(found[0])))
        else:
            wrong = next((put for put in accepted
                          if (int(put["bytes"]), str(put["digest"])) != expected), None)
            if wrong is not None:
                failures.append(_fail(
                    "stored_body_is_not_the_artifact", **common,
                    stored_bytes=int(wrong["bytes"]), attempt=int(wrong["try"])))
    return failures


def _ledger_failures(review: Review) -> list[dict[str, Any]]:
    'One line for every try the host was actually handed, and no others.'
    return [failure for phase in review.releases
            for failure in _phase_ledger_failures(review, phase)]


def _phase_ledger_failures(review: Review, phase: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in review.ledger(phase):
        grouped[(line["instance"], line["target"])].append(line)
    keys = list(dict.fromkeys(
        [(item["instance"], item["target"]) for item in review.items(phase)]
        + [(put["instance"], put["target"]) for put in review.puts(phase)]
        + sorted(grouped)
    ))
    for key in keys:
        puts = review.puts_for(phase, *key)
        lines = grouped.get(key, [])
        logged, recorded = len(puts), len(lines)
        common = {
            "phase": phase,
            "target": key[1],
            "instance": key[0],
            "tries_the_host_logged": logged,
            "lines_in_the_block": recorded,
        }
        if recorded < logged:
            failures.append(_fail("attempt_missing_from_the_ledger", **common))
            continue
        if recorded > logged:
            failures.append(_fail("ledger_recorded_an_attempt_that_never_happened", **common))
            continue
        numbers = sorted(line["attempt"] for line in lines)
        if numbers != list(range(1, recorded + 1)):
            failures.append(_fail(
                "attempt_numbers_do_not_match_the_tries", **common,
                numbers=", ".join(str(number) for number in numbers) or "nothing at all"))
            continue
        took = next((index for index, put in enumerate(puts, start=1) if put.get("accepted")), 0)
        claimed = [line["attempt"] for line in lines if line["status"] == "success"]
        if len(claimed) > 1 or (claimed and claimed[0] != took) or (took and not claimed):
            failures.append(_fail(
                "ledger_called_a_refused_attempt_a_success", **common,
                claimed_try=_try_word(claimed[0] if claimed else 0),
                try_the_host_took=_try_word(took)))
            continue
        publisher = next(
            (str(item["publisher"]) for item in review.items(phase)
             if (item["instance"], item["target"]) == key),
            "",
        )
        expected = [
            (
                publisher,
                str(put["instance"]),
                str(put["target"]),
                index,
                "success" if put.get("accepted") else "failure",
                None if put.get("accepted") else str(put.get("error") or "the host said nothing"),
            )
            for index, put in enumerate(puts, start=1)
        ]
        actual = [
            (
                line["publisher"], line["instance"], line["target"],
                line["attempt"], line["status"], line["error"],
            )
            for line in sorted(lines, key=lambda line: line["attempt"])
        ]
        if actual != expected:
            difference = next(
                (index for index in range(recorded)
                 if actual[index] != expected[index]),
                0,
            )
            failures.append(_fail(
                "ledger_line_disagrees_with_host", **common,
                attempt=difference + 1,
                block_line=_ledger_word(actual[difference]),
                host_line=_ledger_word(expected[difference])))
    return failures


def _answer_failures(review: Review) -> list[dict[str, Any]]:
    "The host's own weather is tried again; the host's answer is not."
    failures: list[dict[str, Any]] = []
    allowed = int(review.setting("attempts", 1))
    for item in review.items("refusal"):
        puts = review.puts_for("refusal", item["instance"], item["target"])
        if not puts:
            failures.append(_fail(
                "planned_item_was_skipped", target=item["target"],
                instance=item["instance"], publisher=item["publisher"]))
            continue
        first, tries = puts[0], len(puts)
        note = str(first.get("error") or "")
        common = {"target": item["target"], "instance": item["instance"], "tries": tries}
        verdict = review.verdict(first)
        if verdict == reference_protocol().REFUSED:
            if tries > 1:
                failures.append(_fail(
                    "mirror_answer_retried" if item["publisher"] == "mirror"
                    else "refusal_retried",
                    **common, host_said=note, status=_status_word(first)))
            said = review.said_about("refusal", item["instance"], item["target"])
            if note and note not in said:
                failures.append(_fail(
                    "host_message_replaced", target=item["target"],
                    instance=item["instance"], host_said=note,
                    summary_said=said or "nothing at all"))
        elif verdict == reference_protocol().TRANSIENT and allowed > 1 and tries < 2:
            failures.append(_fail(
                "transient_failure_abandoned", **common, status=_status_word(first),
                attempts_allowed=allowed, host_said=note))
    for item in review.items("throttle"):
        puts = review.puts_for("throttle", item["instance"], item["target"])
        if not puts:
            continue
        first = puts[0]
        if (review.verdict(first) == reference_protocol().TRANSIENT
                and allowed > 1 and len(puts) < 2):
            failures.append(_fail(
                "transient_failure_abandoned", target=item["target"],
                instance=item["instance"], tries=len(puts),
                status=_status_word(first), attempts_allowed=allowed,
                host_said=str(first.get("error") or "")))
    return failures


def _wait_failures(review: Review) -> list[dict[str, Any]]:
    'The configured or host-directed pause, under the build-window cap.'
    failures: list[dict[str, Any]] = []
    delay = review.setting("delay_ms", 0.0)
    cap = review.setting("max_delay_ms", 0.0)
    for item in review.items("throttle"):
        puts = review.puts_for("throttle", item["instance"], item["target"])
        for previous, current in zip(puts, puts[1:]):
            finished = float(previous["finished_at_ms"])
            sent = float(current["sent_at_ms"])
            gap = sent - finished
            common = {
                "target": item["target"],
                "instance": item["instance"],
                "waited_ms": _ms(gap),
            }
            advises = previous.get("advises_until_ms")
            if advises is not None:
                if sent < min(float(advises), finished + cap) - _TOLERANCE:
                    failures.append(_fail(
                        "retried_before_the_host_allowed_it", **common,
                        advised_ms=_ms(float(advises) - finished), max_delay_ms=_ms(cap)))
                    continue
            elif gap < delay - _TOLERANCE:
                failures.append(_fail(
                    "retried_without_the_configured_pause", **common, delay_ms=_ms(delay)))
                continue
            if gap > cap + _TOLERANCE:
                failures.append(_fail(
                    "one_wait_ran_past_the_release_window", **common, max_delay_ms=_ms(cap)))
    for phase in review.releases:
        stop_at = review.release(phase).get("stop_at_ms")
        if stop_at is None:
            continue
        after = [call for call in review.calls(phase)
                 if float(call["sent_at_ms"]) >= float(stop_at) - _TOLERANCE]
        if after:
            failures.append(_fail(
                "kept_publishing_after_the_stop",
                target=str(after[0]["target"] or after[0]["instance"]),
                instance=str(after[0]["instance"]), calls_after_the_stop=len(after),
                stopped_at_ms=_ms(stop_at)))
            break
    return failures


def _order_failures(review: Review) -> list[dict[str, Any]]:
    'The release is a fact about the release, not about the publish order.'
    failures: list[dict[str, Any]] = []
    first, second = review.objects("order-a"), review.objects("order-b")
    puts_a, puts_b = review.puts("order-a"), review.puts("order-b")
    if not puts_a or not puts_b:
        failures.append(_fail(
            "release_made_no_attempt_before_stop",
            calls_first_run=len(puts_a), calls_second_run=len(puts_b)))
    if first != second:
        differing = sorted(set(first) ^ set(second)) or sorted(
            key for key in set(first) & set(second) if first[key] != second[key])
        failures.append(_fail(
            "what_shipped_depends_on_the_order",
            differs_at=differing[0][1] if differing else "something",
            objects_first_run=len(first), objects_second_run=len(second)))
    lines_a = [tuple(line[field] for field in ("publisher", "instance", "target", "attempt", "status", "error"))
               for line in review.ledger("order-a")]
    lines_b = [tuple(line[field] for field in ("publisher", "instance", "target", "attempt", "status", "error"))
               for line in review.ledger("order-b")]
    if lines_a != lines_b:
        index = next((position for position in range(max(len(lines_a), len(lines_b)))
                      if lines_a[position:position + 1] != lines_b[position:position + 1]), 0)
        failures.append(_fail(
            "ledger_order_follows_the_run", first_difference=index + 1,
            line_first_run=_line_word(lines_a, index), line_second_run=_line_word(lines_b, index),
            lines_first_run=len(lines_a), lines_second_run=len(lines_b)))
    for phase in review.releases:
        lines = review.ledger(phase)
        ordered = sorted(lines, key=_ledger_sort_key)
        if lines != ordered:
            index = next(
                position for position in range(len(lines))
                if lines[position] != ordered[position]
            )
            failures.append(_fail(
                "ledger_not_in_vendor_order", run=phase,
                first_difference=index + 1,
                line_in_block=_line_mapping_word(lines[index]),
                line_expected_there=_line_mapping_word(ordered[index])))
            break
    return failures


def _line_word(lines: Sequence[tuple[Any, ...]], index: int) -> str:
    if index >= len(lines):
        return "nothing"
    line = lines[index]
    return f"{line[2]} try {line[3]}"


def _ledger_sort_key(line: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(line["publisher"]), str(line["instance"]), str(line["target"]),
        int(line["attempt"]),
    )


def _line_mapping_word(line: Mapping[str, Any]) -> str:
    return f"{line['publisher']} {line['target']} try {line['attempt']}"


def _ledger_word(line: Sequence[Any]) -> str:
    error = "" if line[5] is None else f" ({line[5]})"
    return f"{line[0]} {line[2]} try {line[3]} {line[4]}{error}"


def _analyse(candidate: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate)
    return {
        "body_failures": _body_failures(review),
        "ledger_failures": _ledger_failures(review),
        "answer_failures": _answer_failures(review),
        "wait_failures": _wait_failures(review),
        "order_failures": _order_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a release did not run to the end.'
    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the release job ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the release job ended without saying why"
    return f"the release job stopped part way through the publish: {line[:200]}"


def _release_error(candidate: Mapping[str, Any]) -> str | None:
    for entry in candidate.get("releases", ()):
        if entry.get("error"):
            return _console_error({"error": "candidate process exited", "diagnostic": str(entry["error"])})
    return None


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private release work against this workspace and bucket the faults.'
    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        error = _console_error(candidate) if not candidate.get("ok") else _release_error(candidate)
        if error is not None:
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate)
        analysis["case"] = {"work": "release", "releases": len(program["releases"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _plan_summary(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "release": str(entry["manifest"]["version"]),
            "artifacts": [
                f"{item['name']} ({item['kind']}, {item['bytes']} bytes)"
                for item in entry["manifest"]["artifacts"]
            ],
            "publishers": [
                f"{item['publisher']} -> {item['instance']}"
                for item in entry["manifest"]["publishers"]
            ],
            "order_the_console_hands_them_over": list(entry["order"]),
            "console_stop_at_ms": entry.get("stop_at_ms"),
        }
        for entry in program["releases"]
    ]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    protocol = reference_protocol()
    settings = protocol.load_release_config(root / "release.toml")
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else None
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "releases": _plan_summary(program) if program else [],
            }
        )
    return {
        "summary": "The publishing workspace and the releases the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "publish_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "publish").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "release_settings": {
                "attempts": settings.attempts,
                "delay_ms": settings.delay_ms,
                "max_delay_ms": settings.max_delay_ms,
            },
        },
        "records": records,
    }


def _targets_view(release: Mapping[str, Any]) -> list[dict[str, Any]]:
    'What each target ended up holding, next to what the build made.'
    stored = {
        (str(row["instance"]), str(row["target"])): (int(row["bytes"]), str(row["digest"]))
        for row in release.get("objects", ())
    }
    rows = []
    for item in release.get("items", ()):
        found = stored.get((str(item["instance"]), str(item["target"])))
        rows.append(
            {
                "target": item["target"],
                "instance": item["instance"],
                "artifact": item["artifact"],
                "built_bytes": item["bytes"],
                "built_digest": item["digest"],
                "held_bytes": None if found is None else found[0],
                "held_digest": None if found is None else found[1],
                "tries_the_host_received": sum(
                    1 for entry in release.get("log", ())
                    if entry.get("call") == "put"
                    and entry.get("instance") == item["instance"]
                    and entry.get("target") == item["target"]
                ),
            }
        )
    return rows


def _pauses_view(release: Mapping[str, Any], settings: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The pause before each further try, next to the settings it is measured against.'
    puts: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for entry in release.get("log", ()):
        if entry.get("call") == "put":
            puts[(str(entry["instance"]), str(entry["target"]))].append(entry)
    rows = []
    for (instance, target), entries in sorted(puts.items()):
        for previous, current in zip(entries, entries[1:]):
            advises = previous.get("advises_until_ms")
            finished = float(previous["finished_at_ms"])
            rows.append(
                {
                    "target": target,
                    "instance": instance,
                    "before_try": current.get("try"),
                    "waited_ms": _ms(float(current["sent_at_ms"]) - finished),
                    "the_host_asked_us_to_wait_ms": (
                        None if advises is None else _ms(float(advises) - finished)),
                    "delay_ms": settings.get("delay_ms"),
                    "max_delay_ms": settings.get("max_delay_ms"),
                }
            )
    return rows


def _early_view(release: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for entry in release.get("log", ()):
        if entry.get("early"):
            counts[str(entry["instance"])] += 1
    return dict(sorted(counts.items()))


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded release and report what everyone can see.'
    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} release could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    settings = dict(candidate.get("settings", {}))
    public: dict[str, Any] = {}
    for release in candidate.get("releases", ()):
        view: dict[str, Any] = {
            "what_the_host_received": list(release.get("log", ())),
            "what_each_target_holds": _targets_view(release),
            "the_summary_the_job_printed": release.get("report"),
            "pauses_between_tries": _pauses_view(release, settings),
            "calls_that_arrived_early": _early_view(release),
        }
        if release.get("stop_at_ms") is not None:
            stop_at = float(release["stop_at_ms"])
            view["the_console_stop"] = {
                "stopped_at_ms": _ms(stop_at),
                "calls_sent_after_it": sum(
                    1 for entry in release.get("log", ())
                    if float(entry.get("sent_at_ms", 0.0)) >= stop_at),
            }
        if release.get("error"):
            view["the_job_stopped_with"] = release["error"]
        if record_id == "2.3.9-reconciled":
            view["the_block_we_agreed_with_the_vendor"] = reconciled_block(
                program["releases"][0]["manifest"])
        public[str(release.get("version") or release.get("phase"))] = view
    return {
        "summary": f"The {record_id} release ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "release_settings": settings,
            "releases": _plan_summary(program),
        },
        "public": public,
    }
