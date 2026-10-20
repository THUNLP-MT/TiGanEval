'Deterministic, sandboxed review of one plugin-sandbox workspace.'

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

from .workload import build_program, plugin_specs


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("plugins/coordinator.py", "plugins/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-sandbox-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "handoff-burst": "handoff",
    "overnight-review": "overnight",
    "grow-then-capture": "chain",
    "restore-drill": "restore",
}

BUCKETS: Mapping[str, str] = {
    "consistent_cut": "cut_failures",
    "capture_holds_still": "stillness_failures",
    "incremental_chain": "chain_failures",
    "restore_all_or_nothing": "restore_failures",
    "restored_arena_exact": "fidelity_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `plugins/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "plugins" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_sandbox_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _delta_row(delta: Any) -> dict[str, Any]:
    return {"length": int(delta.length),
            "edits": [[int(e.offset), int(e.before), int(e.after)] for e in delta.edits]}


class Review:
    'Everything the five checks read from one run of the sandbox.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.candidate, self.program = candidate, program
        self.operations = [dict(row) for row in candidate.get("operations", ())]
        self.expected = dict(candidate.get("expected", {}))
        self.declared_total = int(program.get("declared_total", 0))
        self.captures = {
            str(row["capture"]): row
            for row in self.operations
            if row.get("op") in ("capture", "incremental") and row.get("capture")
        }

    def probes(self, name: str) -> list[dict[str, Any]]:
        'Every reading of one dump the console took before it edited a buffer.'

        edited = min((int(row["index"]) for row in self.edits()
                      if str(row.get("capture")) == name), default=None)
        return [row for row in self.operations
                if row.get("op") == "probe" and str(row.get("capture")) == name
                and (edited is None or int(row["index"]) < edited)]

    def edits(self) -> list[dict[str, Any]]:
        return [row for row in self.operations if row.get("op") == "edit_probe"]

    def unfinished_incrementals(self) -> list[dict[str, Any]]:
        'Every dump after a baseline that the console asked for and did not get.'

        return [row for row in self.operations
                if row.get("op") == "incremental" and not row.get("ok")]

    def restores(self) -> list[dict[str, Any]]:
        return [row for row in self.operations if row.get("op") == "restore"]

    def reference_image(self, name: str, key: str) -> str | None:
        'The arena independently recorded before candidate code ran.'

        return dict(self.expected.get(name, {}).get("images", {})).get(key)

    def captured_state(self, name: str) -> dict[str, Any]:
        return dict(self.expected.get(name, {}).get("state", {}))

    def captured_image(self, name: str, key: str) -> str | None:
        'What the arena actually held when the console asked for the dump.'

        return dict(self.expected.get(name, {}).get("images", {})).get(key)

    def images(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {str(key): dict(value) for key, value in dict(row.get("images", {})).items()}


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _epoch(value: Any) -> int:
    'The epoch a dump names, as a number the owner can read out.'

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _cut_failures(review: Review) -> list[dict[str, Any]]:
    'One dump names one instant of the sandbox.'

    failures: list[dict[str, Any]] = []
    for name, row in sorted(review.captures.items()):
        if row.get("op") != "capture":
            continue
        if not row.get("ok"):
            failures.append(_fail(
                "full_capture_not_taken", capture=name, phase=str(row.get("phase", "")),
                plugins_offered=len(list(row.get("targets", ()))),
                error=_console_line(row.get("error"))))
            continue
        targets = [str(key) for key in row.get("targets", ())]
        keys = [str(key) for key in row.get("keys", ())]
        images = review.images(row)
        missing = sorted(set(targets) - (set(keys) & set(images)))
        unexpected = sorted((set(keys) | set(images)) - set(targets))
        duplicate = next((key for key in keys if keys.count(key) > 1), None)
        if missing or unexpected or duplicate is not None or len(keys) != len(targets):
            direction = "missing" if missing else "unexpected" if unexpected else "duplicate"
            plugin = (missing or unexpected or [duplicate or ""])[0]
            failures.append(_fail(
                "capture_target_set_mismatch", capture=name, plugin=plugin,
                direction=direction, phase=str(row.get("phase", "")),
                plugins_offered=len(targets), plugins_in_the_dump=len(keys)))
            continue
        requested_epoch = _epoch(row.get("host_epoch_before"))
        recorded_epoch = _epoch(row.get("recorded_epoch"))
        if recorded_epoch != requested_epoch:
            failures.append(_fail(
                "capture_named_wrong_epoch", capture=name,
                phase=str(row.get("phase", "")), requested_epoch=requested_epoch,
                recorded_epoch=recorded_epoch, plugins_in_the_dump=len(keys)))
        book = row.get("book_in_the_capture")
        if isinstance(book, Mapping) and int(book.get("total", 0)) != review.declared_total:
            failures.append(_fail(
                "captured_books_do_not_balance", capture=name, phase=str(row.get("phase", "")),
                declared_total=review.declared_total, total_in_the_dump=int(book.get("total", 0)),
                rolled=int(book.get("rolled", 0)), outstanding=int(book.get("outstanding", 0)),
                recorded_epoch=_epoch(row.get("recorded_epoch"))))
        for key, image in sorted(review.images(row).items()):
            reference = review.reference_image(name, key)
            if reference is not None and str(image.get("hex")) == reference:
                continue
            failures.append(_fail(
                "capture_read_across_epochs", capture=name, plugin=key,
                phase=str(row.get("phase", "")),
                recorded_epoch=_epoch(row.get("recorded_epoch")),
                epoch_after_the_walk=_epoch(row.get("host_epoch_after")),
                plugins_in_the_dump=len(review.images(row)),
                bytes_in_the_dump=int(image.get("length", 0))))
    return failures


def _stillness_failures(review: Review) -> list[dict[str, Any]]:
    "A dump is the moment it was taken, and what it hands out is the caller's."

    failures: list[dict[str, Any]] = []
    for name, row in sorted(review.captures.items()):
        taken = review.images(row)
        for probe in review.probes(name):
            later = review.images(probe)
            for key, image in sorted(taken.items()):
                if key in later and str(later[key].get("hex")) != str(image.get("hex")):
                    failures.append(_fail(
                        "capture_followed_the_host", capture=name, plugin=key,
                        phase=str(row.get("phase", "")), read_again_at=str(probe.get("label")),
                        bytes_when_taken=int(image.get("length", 0)),
                        bytes_when_read_again=int(later[key].get("length", 0))))
    for row in review.edits():
        before, after = dict(row.get("before_edit", {})), dict(row.get("after_edit", {}))
        if before.get("hex") is not None and before.get("hex") != after.get("hex"):
            failures.append(_fail(
                "capture_handed_out_the_stored_buffer", capture=str(row.get("capture")),
                plugin=str(row.get("key")), phase=str(row.get("phase", "")),
                bytes_written_over=int(after.get("length", 0))))
    return failures


def _chain_failures(review: Review) -> list[dict[str, Any]]:
    'An incremental dump reads back as the whole arena at its own epoch.'

    protocol = reference_protocol()
    failures: list[dict[str, Any]] = []
    for row in review.unfinished_incrementals():
        failures.append(_fail(
            "incremental_not_taken", capture=str(row.get("capture") or row.get("label")),
            baseline=str(row.get("baseline") or ""), phase=str(row.get("phase", "")),
            plugins_offered=len(list(row.get("targets", ()))),
            error=_console_line(row.get("error"))))
    for name, row in sorted(review.captures.items()):
        if row.get("op") != "incremental":
            continue
        baseline = str(row.get("baseline") or "")
        base_reference = dict(review.expected.get(baseline, {}).get("images", {}))
        targets = [str(key) for key in row.get("targets", ())]
        keys = [str(key) for key in row.get("keys", ())]
        images = review.images(row)
        missing = sorted(set(targets) - (set(keys) & set(images)))
        unexpected = sorted((set(keys) | set(images)) - set(targets))
        duplicate = next((key for key in keys if keys.count(key) > 1), None)
        if missing or unexpected or duplicate is not None or len(keys) != len(targets):
            direction = "missing" if missing else "unexpected" if unexpected else "duplicate"
            plugin = (missing or unexpected or [duplicate or ""])[0]
            failures.append(_fail(
                "incremental_target_set_mismatch", capture=name, plugin=plugin,
                baseline=baseline, direction=direction, phase=str(row.get("phase", "")),
                plugins_offered=len(targets), plugins_in_the_dump=len(keys)))
            continue
        requested_epoch = _epoch(row.get("host_epoch_before"))
        recorded_epoch = _epoch(row.get("recorded_epoch"))
        if recorded_epoch != requested_epoch:
            failures.append(_fail(
                "incremental_named_wrong_epoch", capture=name, baseline=baseline,
                phase=str(row.get("phase", "")), requested_epoch=requested_epoch,
                recorded_epoch=recorded_epoch, plugins_in_the_dump=len(keys)))
        for key, image in sorted(images.items()):
            reference = review.reference_image(name, key)
            stored = dict(row.get("deltas", {})).get(key)
            if reference is not None and str(image.get("hex")) != reference:
                failures.append(_fail(
                    "chain_reconstruction_mismatch", capture=name, plugin=key,
                    baseline=baseline, phase=str(row.get("phase", "")),
                    bytes_read_back=int(image.get("length", 0)),
                    bytes_in_the_arena=len(reference) // 2))
                continue
            if stored is None:
                failures.append(_fail(
                    "incremental_stored_the_whole_arena", capture=name, plugin=key,
                    baseline=baseline, phase=str(row.get("phase", "")),
                    bytes_stored=int(image.get("length", 0))))
                continue
            if reference is None:
                continue
            base_hex = base_reference.get(key)
            wanted = _delta_row(protocol.diff(
                b"" if base_hex is None else bytes.fromhex(str(base_hex)),
                bytes.fromhex(str(reference))))
            if not isinstance(stored, Mapping) or dict(stored) != wanted:
                changed = len(dict(stored).get("edits", ())) if isinstance(stored, Mapping) else 0
                failures.append(_fail(
                    "delta_not_against_reconstructed_baseline", capture=name, plugin=key,
                    baseline=baseline, phase=str(row.get("phase", "")),
                    changed_bytes_stored=changed, changed_bytes_in_the_arena=len(wanted["edits"])))
    return failures


def _restore_plan(review: Review, row: Mapping[str, Any]) -> dict[str, Any]:
    'What the sandbox looked like when this restore was asked for.'

    name = str(row.get("capture"))
    held = review.captured_state(name)
    before = {str(key): dict(value) for key, value in dict(row.get("plugins_before", {})).items()}
    after = {str(key): dict(value) for key, value in dict(row.get("plugins_after", {})).items()}
    offered = {str(key): dict(value) for key, value in dict(row.get("targets_before", {})).items()}
    targets = [str(key) for key in row.get("targets", ())]
    reasons: list[dict[str, str]] = []
    missing = sorted(set(held) - set(targets))
    if missing:
        reasons.append({"kind": "missing", "plugin": missing[0],
                        "why": "it is in the dump and not in the sandbox any more"})
    for key in sorted(set(targets) & set(held)):
        image = review.captured_image(name, key)
        length = len(str(image)) // 2 if image is not None else 0
        state = offered.get(key, {})
        if bool(state.get("detached")):
            reasons.append({"kind": "detached", "plugin": key,
                            "why": "it is not loaded any more"})
        elif not bool(state.get("is_live")):
            reasons.append({"kind": "foreign", "plugin": key,
                            "why": "the offered object is not the plugin loaded in the host"})
        elif str(state.get("layout")) != str(held[key].get("layout")):
            reasons.append({"kind": "layout", "plugin": key,
                            "why": "it was reloaded with another layout"})
        elif int(state.get("capacity", 0)) < length:
            reasons.append({"kind": "capacity", "plugin": key,
                            "why": "it is too small for what the dump holds"})
    touched = {key: int(after.get(key, {}).get("write_seq", 0)) - int(value.get("write_seq", 0))
               for key, value in before.items()}
    return {"capture": name, "held": held, "targets": targets, "reasons": reasons,
            "touched": touched, "before": before, "after": after, "offered": offered}


def _dump_size(review: Review, row: Mapping[str, Any], plan: Mapping[str, Any]) -> int:
    'How many plugins the dump the console offered actually holds.'

    keys = row.get("keys")
    return len(keys) if isinstance(keys, list) else len(plan["held"])


def _restore_failures(review: Review) -> list[dict[str, Any]]:
    'A restore happens to every plugin in the dump, or to none of them.'

    failures: list[dict[str, Any]] = []
    for row in review.restores():
        plan = _restore_plan(review, row)
        written = sorted(key for key, count in plan["touched"].items() if count)
        common = {"capture": plan["capture"], "attempt": str(row.get("label")),
                  "phase": str(row.get("phase", "")),
                  "plugins_in_the_dump": _dump_size(review, row, plan)}
        blocker = plan["reasons"][0] if plan["reasons"] else None
        if blocker is not None:
            if written:
                failures.append(_fail(
                    "refused_restore_wrote_anyway", plugin=written[0],
                    plugins_written=len(written), blocked_by=blocker["plugin"],
                    reason=blocker["why"], **common))
            elif row.get("raised") is None:
                accepted_mode = {
                    "detached": "detached_target_accepted",
                    "foreign": "foreign_target_accepted",
                }.get(blocker["kind"], "mismatched_target_accepted")
                failures.append(_fail(
                    accepted_mode, plugin=blocker["plugin"],
                    reason=blocker["why"], plugins_loaded=len(plan["before"]), **common))
            else:
                refusal = dict(row.get("refusal") or {})
                reported = (str(refusal.get("reason")), str(refusal.get("plugin")))
                known = {(reason["kind"], reason["plugin"])
                         for reason in plan["reasons"]}
                if (str(refusal.get("exception")) != "RestoreRefused"
                        or reported not in known):
                    failures.append(_fail(
                        "restore_reported_wrong_reason", plugin=blocker["plugin"],
                        expected_reason=blocker["kind"],
                        reported_reason=str(refusal.get("reason") or "no structured reason"),
                        reported_plugin=str(refusal.get("plugin") or "no plugin"), **common))
            continue
        if row.get("raised") is not None:
            failures.append(_fail(
                "sound_restore_refused", plugins_loaded=len(plan["before"]), **common))
            continue
        wanted = {key: 1 if key in plan["held"] else 0 for key in plan["touched"]}
        if plan["touched"] != wanted:
            off = sorted(key for key in plan["touched"] if plan["touched"][key] != wanted[key])
            failures.append(_fail(
                "restore_touched_the_wrong_plugins", plugin=off[0] if off else "",
                writes_to_that_plugin=int(plan["touched"].get(off[0], 0)) if off else 0,
                plugins_written=len(written), **common))
    return failures


def _fidelity_failures(review: Review) -> list[dict[str, Any]]:
    'After a restore the arena is the arena the dump recorded.'

    failures: list[dict[str, Any]] = []
    for row in review.restores():
        plan = _restore_plan(review, row)
        if plan["reasons"] or row.get("raised") is not None:
            continue
        arenas = {str(key): dict(value)
                  for key, value in dict(row.get("arenas_after", {})).items()}
        common = {"capture": plan["capture"], "attempt": str(row.get("label")),
                  "phase": str(row.get("phase", ""))}
        for key in sorted(plan["held"]):
            image = review.captured_image(plan["capture"], key)
            arena = arenas.get(key)
            if image is None or arena is None:
                continue
            if str(arena.get("hex")) == image:
                continue
            recorded, now = len(image) // 2, int(arena.get("length", 0))
            if now > recorded:
                failures.append(_fail(
                    "post_capture_bytes_survived", plugin=key, bytes_recorded=recorded,
                    bytes_after_the_restore=now, bytes_left_over=now - recorded, **common))
            else:
                failures.append(_fail(
                    "restored_arena_differs", plugin=key, bytes_recorded=recorded,
                    bytes_after_the_restore=now, **common))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "cut_failures": _cut_failures(review),
        "stillness_failures": _stillness_failures(review),
        "chain_failures": _chain_failures(review),
        "restore_failures": _restore_failures(review),
        "fidelity_failures": _fidelity_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-<>]+/)+")


_FINGERPRINT = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-f]*[a-f])[0-9a-f]{12,}(?![0-9A-Za-z])")

_NOTHING_TO_QUOTE = "the sandbox ended without saying why"


def _console_line(reported: Any) -> str:
    'One console line, in words the sandbox owner can read back.'

    line = _DIRECTORY_PART.sub("", str(reported or "").strip())[:200]
    if not line or _FINGERPRINT.search(line):
        return _NOTHING_TO_QUOTE
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return _NOTHING_TO_QUOTE
    return line


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a run did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or _NOTHING_TO_QUOTE
    return f"the run stopped part way through: {_console_line(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private sandbox run against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"run": "release", "operations": len(program["operations"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


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
            "plugins": plugin_specs(program) if program else {},
            "declared_total": program.get("declared_total"),
        })
    return {
        "summary": "The plugin sandbox workspace and the runs the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "sandbox_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "plugins").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _without_hex(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _without_hex(item) for key, item in value.items() if key != "hex"}
    if isinstance(value, list):
        return [_without_hex(item) for item in value]
    return value


_PUBLIC_FIELDS = (
    "recorded_epoch", "keys", "images", "deltas", "book_in_the_capture", "baseline",
    "targets", "host_epoch_before", "host_epoch_after", "steps_run", "read_error",
    "before_edit", "after_edit", "raised", "refusal", "plugins_before", "plugins_after",
    "targets_before", "targets_after",
    "arenas_before", "arenas_after", "target_arenas_before", "target_arenas_after",
    "balance", "epoch", "pending", "plugins", "capture", "key",
)


def _operation_rows(candidate: Mapping[str, Any], declared_total: int) -> list[dict[str, Any]]:
    'Every step the console drove, and what it read afterwards.'

    rows: list[dict[str, Any]] = []
    for record in candidate.get("operations", ()):
        row: dict[str, Any] = {
            "step": record.get("label"),
            "operation": record.get("op"),
            "completed": bool(record.get("ok")),
            "error": record.get("error"),
        }
        for field in _PUBLIC_FIELDS:
            if field in record:
                row[field] = _without_hex(record[field])
        if "book_in_the_capture" in row:
            row["declared_total"] = declared_total
        rows.append(row)
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded sandbox run and report the console log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} run could not be replayed against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    declared = int(program.get("declared_total", 0))
    return {
        "summary": f"The {record_id} run replayed against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "plugins": plugin_specs(program),
            "declared_total": declared,
            "roll_up_plugin": program.get("roll_key"),
            "meter_plugin": program.get("meter_key"),
            "operation_count": len(candidate.get("operations", ())),
        },
        "public": {"what_the_console_did": _operation_rows(candidate, declared)},
    }
