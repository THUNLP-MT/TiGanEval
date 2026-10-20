'Deterministic, sandboxed review of one nightly-archive workspace.'

from __future__ import annotations

import base64
from collections import defaultdict
import hashlib
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

from .workload import JOB, all_keys, build_program, night_facts


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("nightly/pipeline.py", "nightly/restore.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-nightly-",
    timeout=60.0,
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "retention-window-drill": "retention-window-drill",
    "key-was-not-set": "key-was-not-set",
    "vault-declined-a-write": "vault-declined-a-write",
    "rotation-and-the-copied-key": "rotation-and-the-copied-key",
}

BUCKETS: Mapping[str, str] = {
    "published_object_restores": "restore_failures",
    "destination_inventory_conserved": "inventory_failures",
    "report_equals_restorable_state": "report_failures",
    "key_provenance_recorded": "provenance_failures",
    "window_drill_opens_any_night": "drill_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `nightly/protocol.py`, loaded from the project's own tree, so     the read path the review uses is the one the drill laptop runs."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "nightly" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_nightly_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _blob(text: Any) -> bytes:
    return base64.b64decode(str(text or ""))


class Review:
    'Everything the five checks read from one run of the nights.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.protocol = reference_protocol()
        self.candidate, self.program = candidate, program
        self.job = str(program.get("job", JOB))
        self.facts = {row["night"]: row for row in night_facts(program)}
        self.keys = [self.protocol.decode_key(value) for value in sorted(all_keys(program))]
        self.nights = [dict(row) for row in candidate.get("nights", ())]
        self.listings = {
            name: [dict(row) for row in rows]
            for name, rows in dict(candidate.get("listings", {})).items()
        }
        self.stored = {
            name: {str(key): _blob(value) for key, value in dict(rows).items()}
            for name, rows in dict(candidate.get("stored", {})).items()
        }
        self.drill = [dict(row) for row in candidate.get("drill", ())]


    def dump(self, night: str) -> bytes:
        fact = self.facts[night]
        return self.protocol.dump_bytes(self.job, night, int(fact["rows"]))

    def report(self, record: Mapping[str, Any]) -> Mapping[str, Any] | None:
        value = record.get("report")
        return dict(value) if isinstance(value, Mapping) else None

    def status(self, record: Mapping[str, Any]) -> str | None:
        report = self.report(record)
        status = None if report is None else report.get("status")
        return str(status) if status in self.protocol.STATUSES else None

    def handed(self, record: Mapping[str, Any], destination: str) -> dict[str, bytes]:
        rows = dict(record.get("handed", {})).get(destination, {})
        return {str(name): _blob(value) for name, value in dict(rows).items()}

    def refused(self, record: Mapping[str, Any]) -> list[str]:
        return sorted(
            destination
            for destination, events in dict(record.get("events", {})).items()
            if any(str(item.get("event")) == "refused" for item in events)
        )

    def objects_for(self, destination: str, night: str) -> list[dict[str, Any]]:
        return [row for row in self.listings.get(destination, ()) if night in str(row["object"])]


    def unseal(self, data: bytes) -> tuple[bytes | None, str, bytes | None]:
        'Take one object through the published read path with every key the         console put anywhere. Returns (payload, diagnosis, key).'

        diagnosis = "the object is empty"
        for key in self.keys:
            try:
                return self.protocol.restore_stream(data, key), "", key
            except self.protocol.ArchiveError as exc:
                diagnosis = f"{type(exc).__name__}: {exc}"
        return None, diagnosis, None

    def recover(self, data: bytes) -> tuple[bytes | None, str]:
        'Both steps of the runbook over one object.'

        payload, diagnosis, _ = self.unseal(data)
        if payload is None:
            return None, diagnosis
        try:
            return self.protocol.decompress(payload), ""
        except self.protocol.ArchiveError as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def holds_the_dump(self, data: bytes, night: str) -> bool:
        recovered, _ = self.recover(data)
        return recovered is not None and recovered == self.dump(night)


def _restore_failures(review: Review) -> list[dict[str, Any]]:
    'What the job handed a destination is what the runbook can open.'

    failures: list[dict[str, Any]] = []
    for record in review.nights:
        night = str(record["night"])
        fact = review.facts[night]
        if fact["ambiguous"] or fact["key_unavailable"]:
            continue
        for destination in sorted(review.listings):
            if destination in fact["scripted"]:
                continue
            for name, data in sorted(review.handed(record, destination).items()):
                if not data:
                    continue
                payload, diagnosis, _ = review.unseal(data)
                common = {"night": night, "destination": destination, "object": name,
                          "handed_bytes": len(data), "dump_bytes": len(review.dump(night))}
                if payload is None:
                    failures.append(_fail("restore_path_would_not_open_it",
                                          diagnosis=diagnosis, recovered_bytes=0, **common))
                    continue
                try:
                    recovered = review.protocol.decompress(payload)
                except review.protocol.ArchiveError as exc:
                    failures.append(_fail("the_recovered_stream_is_not_compressed",
                                          diagnosis=f"{type(exc).__name__}: {exc}",
                                          recovered_bytes=len(payload), **common))
                    continue
                if recovered != review.dump(night):
                    failures.append(_fail("restored_bytes_are_not_the_dump",
                                          diagnosis="what came out is not that night's dump",
                                          recovered_bytes=len(recovered), **common))
    return failures


def _inventory_failures(review: Review) -> list[dict[str, Any]]:
    'A night that could not finish leaves the window as it found it; a night     that finished leaves one object at each destination, and a night nothing was     wrong with is a night the job took to them; every object opened is closed..'

    failures: list[dict[str, Any]] = []
    for record in review.nights:
        night = str(record["night"])
        fact = review.facts[night]
        refused = review.refused(record)
        timeline = [dict(item) for item in record.get("timeline", ())]
        opened_events = [item for item in timeline if item.get("event") == "opened"]
        left = [(destination, row) for destination in sorted(review.listings)
                for row in review.objects_for(destination, night)]
        if fact["key_unavailable"] and left:
            destination, row = left[0]
            failures.append(_fail("object_left_after_a_key_failure", night=night,
                                  destination=destination, object=str(row["object"]),
                                  objects_left=len(left), stored_bytes=int(row["stored_bytes"])))
        elif refused and left:
            destination, row = left[0]
            failures.append(_fail("object_left_after_a_write_failed", night=night,
                                  destination=destination, object=str(row["object"]),
                                  objects_left=len(left), refused_by=refused[0]))
        if (fact["key_unavailable"] or fact["ambiguous"]) and opened_events:
            first = opened_events[0]
            failures.append(_fail(
                "destination_opened_without_one_usable_key", night=night,
                destination=str(first.get("destination", "unknown")),
                object=str(first.get("object", "unknown")),
                objects_opened=len(opened_events),
                key_problem="ambiguous" if fact["ambiguous"] else "unavailable"))


        first_finalize = next(
            (index for index, item in enumerate(timeline)
             if item.get("event") == "finalized" and night in str(item.get("object", ""))),
            None,
        )
        if first_finalize is not None:
            before = timeline[:first_finalize]
            finalized = timeline[first_finalize]
            verified: list[str] = []
            missing: list[str] = []
            finalized_name = str(finalized.get("object", ""))
            for destination in sorted(review.listings):
                writes = [index for index, item in enumerate(before)
                          if item.get("event") == "wrote"
                          and item.get("destination") == destination
                          and str(item.get("object", "")) == finalized_name]
                reads = [index for index, item in enumerate(before)
                         if item.get("event") == "read"
                         and item.get("destination") == destination
                         and str(item.get("object", "")) == finalized_name]
                if writes and reads and reads[-1] > writes[-1]:
                    verified.append(destination)
                else:
                    missing.append(destination)
            if missing:
                failures.append(_fail(
                    "object_finalized_before_all_destinations_read_back", night=night,
                    destination=str(finalized.get("destination", "unknown")),
                    object=finalized_name, destinations_verified=len(verified),
                    destinations_required=len(review.listings),
                    missing_destination=missing[0]))


        never_opened = not any(
            str(item.get("event")) == "opened"
            for events in dict(record.get("events", {})).values()
            for item in events
        )
        restorable_handoff = any(
            review.holds_the_dump(data, night)
            for destination in sorted(review.listings)
            for data in review.handed(record, destination).values()
            if data
        )
        if (review.status(record) == "completed"
                or (fact["good"] and (never_opened or restorable_handoff))):
            for destination in sorted(review.listings):
                rows = [row for row in review.objects_for(destination, night) if row["finalized"]]
                if len(rows) != 1:
                    failures.append(_fail("night_missing_from_a_destination", night=night,
                                          destination=destination, objects_found=len(rows)))
    sessions: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for record in review.nights:
        for destination, events in dict(record.get("events", {})).items():
            for item in events:
                if str(item.get("event")) in ("opened", "closed"):
                    index = 0 if str(item["event"]) == "opened" else 1
                    sessions[(str(destination), str(item.get("object")))][index] += 1
    for (destination, name), (opened, closed) in sorted(sessions.items()):
        if closed < opened:
            failures.append(_fail("object_left_open", destination=destination, object=name,
                                  opened=opened, closed=closed, still_open=opened - closed))
    return failures


def _report_failures(review: Review) -> list[dict[str, Any]]:
    'The nights the job calls complete are the nights that can be restored.'

    failures: list[dict[str, Any]] = []
    for record in review.nights:
        night = str(record["night"])
        fact = review.facts[night]
        status = review.status(record)
        if status is None:
            diagnosis = str(record.get("raised") or f"the job returned {record.get('report')!r}")
            failures.append(_fail("no_report_for_the_night", night=night,
                                  diagnosis=diagnosis[:180]))
            continue
        if status == "completed":
            for destination in sorted(review.listings):
                rows = [row for row in review.objects_for(destination, night)
                        if row["finalized"]]
                if not rows:
                    failures.append(_fail(
                        "reported_complete_without_a_published_object", night=night,
                        destination=destination, objects_found=0))
                    continue
                for row in rows:
                    data = review.stored.get(destination, {}).get(str(row["object"]), b"")
                    if review.holds_the_dump(data, night):
                        continue
                    failures.append(_fail(
                        "reported_complete_but_not_restorable", night=night,
                        destination=destination, stored_bytes=len(data),
                        object=str(row["object"]),
                        diagnosis=review.recover(data)[1] or "what came out is not that night's dump"))
            continue
        if not fact["good"]:
            continue
        handed = [data for destination in sorted(review.listings)
                  for data in review.handed(record, destination).values() if data]
        if all(review.holds_the_dump(data, night) for data in handed):
            failures.append(_fail("usable_night_reported_as_lost", night=night, status=status,
                                  objects_written=len(handed)))
    return failures


def _provenance_failures(review: Review) -> list[dict[str, Any]]:
    'Every published object names the generation that opens it, and a night     with two configured key sources is not published at all.'

    failures: list[dict[str, Any]] = []
    for record in review.nights:
        night = str(record["night"])
        fact = review.facts[night]
        if fact["ambiguous"]:
            for destination in sorted(review.listings):
                for row in review.objects_for(destination, night):
                    data = review.stored.get(destination, {}).get(str(row["object"]), b"")
                    failures.append(_fail(
                        "ambiguous_key_configuration_was_resolved", night=night,
                        destination=destination, object=str(row["object"]),
                        key_id_used=_recorded_key(review, data)))
            continue
        if fact["key_unavailable"]:
            continue
        configured = review.protocol.key_id(review.protocol.decode_key(fact["configured_key"]))
        for destination in sorted(review.listings):
            if destination in fact["scripted"]:
                continue
            for row in review.objects_for(destination, night):
                if not row["finalized"]:
                    continue
                data = review.stored.get(destination, {}).get(str(row["object"]), b"")
                recorded = _recorded_key(review, data)
                _, _, key = review.unseal(data)
                opened = review.protocol.key_id(key) if key is not None else "none"
                common = {"night": night, "destination": destination,
                          "object": str(row["object"]), "key_id_recorded": recorded,
                          "key_id_configured": configured}
                if opened == "none":


                    if recorded == "none":
                        failures.append(_fail("object_does_not_name_the_key_that_sealed_it",
                                              key_id_used=opened, **common))
                elif recorded != opened:
                    failures.append(_fail("object_does_not_name_the_key_that_sealed_it",
                                          key_id_used=opened, **common))
                elif opened != configured:
                    failures.append(_fail("object_sealed_with_a_retired_key",
                                          key_id_used=opened, **common))
    return failures


def _recorded_key(review: Review, data: bytes) -> str:
    try:
        return str(review.protocol.parse_header(data).key_id)
    except review.protocol.ArchiveError:
        return "none"


def _drill_failures(review: Review) -> list[dict[str, Any]]:
    'The drill opens whichever night it picks out of the window.'

    rows = {str(row.get("object")): row for row in review.drill}
    failures: list[dict[str, Any]] = []
    for item in review.program.get("seeded", ()):
        name, night = str(item["object"]), str(item["night"])
        sealed, suffixed = bool(item.get("key")), name.endswith(".enc")
        kind = ("renamed_object_opened_as_the_wrong_kind" if sealed != suffixed
                else "sealed_night_would_not_open" if sealed else "plain_night_would_not_open")
        expected = review.protocol.dump_bytes(review.job, night, int(item["rows"]))
        row = rows.get(name, {})
        digest = hashlib.sha256(expected).hexdigest()[:16]
        if str(row.get("digest", "")) == digest:
            continue
        failures.append(_fail(
            kind, object=name, night=night, destination=str(item["destination"]),
            opened_bytes=int(row.get("opened_bytes", 0)), dump_bytes=len(expected),
            diagnosis=str(row.get("error") or ("the drill got nothing back for it" if not row
                          else "what came back is not that night's dump"))[:180]))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "restore_failures": _restore_failures(review),
        "inventory_failures": _inventory_failures(review),
        "report_failures": _report_failures(review),
        "provenance_failures": _provenance_failures(review),
        "drill_failures": _drill_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a stretch of nights did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the job ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the job ended without saying why"
    return f"the job stopped part way through the nights: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private nights against this workspace and bucket what went wrong.'

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
        analysis["case"] = {"nights": len(program["nights"]), "window": len(program["seeded"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _recorded_key_id(protocol: Any, data: bytes | None, text: str | None = None) -> str | None:
    'What an object says its key is, or the id of a key the console holds.'

    try:
        if text is not None:
            return str(protocol.key_id(protocol.decode_key(text)))
        return str(protocol.parse_header(bytes(data or b"")).key_id)
    except protocol.ArchiveError:
        return None


def _keyring_ids(program: Mapping[str, Any]) -> list[str | None]:
    'The generations the ops key file lists for this stretch.'

    protocol = reference_protocol()
    return [_recorded_key_id(protocol, None, str(value)) for value in program.get("keyring", ())]


def _key_configuration(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'What the console was holding for each night before it ran.'

    protocol = reference_protocol()
    rows = []
    for night in program.get("nights", ()):
        config = dict(night.get("key_config", {}))
        values = {**dict(night.get("env", {})), **dict(night.get("files", {}))}
        rows.append(
            {
                "night": str(night["night"]),
                "dump_rows": int(night["rows"]),
                "key_sources_named": [name for name in ("env_var", "key_file") if config.get(name)],
                "values_present": [
                    {"source": name, "characters": len(str(value)),
                     "key_id": _recorded_key_id(protocol, None, str(value))}
                    for name, value in sorted(values.items())
                ],
                "console_made_the_destination": dict(night.get("script", {})),
            }
        )
    return rows


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "nights": [str(night["night"]) for night in program.get("nights", ())],
                "window_already_holds": [str(item["object"]) for item in program.get("seeded", ())],
                "generations_the_ops_key_file_lists": _keyring_ids(program) if program else [],
            }
        )
    return {
        "summary": "The nightly archive job and the stretches of nights the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "job_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "nightly").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _holdings(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'What each destination is holding at the end, and what it is made of.'

    protocol = reference_protocol()
    job = str(program.get("job", JOB))
    sizes = {str(night["night"]): int(night["rows"]) for night in program.get("nights", ())}
    sizes.update({str(item["night"]): int(item["rows"]) for item in program.get("seeded", ())})
    rows = []
    for destination, listing in sorted(dict(candidate.get("listings", {})).items()):
        stored = dict(dict(candidate.get("stored", {})).get(destination, {}))
        for entry in listing:
            name = str(entry["object"])
            data = _blob(stored.get(name))
            night = next((value for value in sorted(sizes) if value in name), None)
            rows.append(
                {
                    "destination": destination,
                    "object": name,
                    "stored_bytes": int(entry["stored_bytes"]),
                    "finalized": bool(entry["finalized"]),
                    "leading_bytes": data[:4].hex(),
                    "names_key": _recorded_key_id(protocol, data),
                    "dump_bytes": len(protocol.dump_bytes(job, night, sizes[night])) if night else None,
                }
            )
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded stretch of nights and report what the console saw.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} nights could not run against this job.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    return {
        "summary": f"The {record_id} nights ran against this job.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "what_the_console_was_holding": _key_configuration(program),
            "generations_the_ops_key_file_lists": _keyring_ids(program),
            "window_already_held": [str(item["object"]) for item in program.get("seeded", ())],
        },
        "public": {
            "what_each_night_returned": [
                {"night": str(record["night"]),
                 "report": record.get("report"), "raised": record.get("raised")}
                for record in candidate.get("nights", ())
            ],
            "what_the_destinations_saw": [
                {"night": str(record["night"]), "events": record.get("events")}
                for record in candidate.get("nights", ())
            ],
            "what_each_destination_holds": _holdings(candidate, program),
            "what_the_drill_got_back": list(candidate.get("drill", ())),
        },
    }
