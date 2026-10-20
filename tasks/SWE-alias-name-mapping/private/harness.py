'Deterministic, sandboxed review of one partner-intake workspace.'

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

from .workload import build_program, private_expectations


TASK_ROOT = Path(__file__).resolve().parents[1]
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `intake/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "intake" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_intake_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


EDITABLE_FILES = ("intake/mapper.py", "intake/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-intake-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "partner-onboarding": "onboarding",
    "partner-cutover": "cutover",
    "strict-and-collect": "strictness",
    "config-review": "review",
}

BUCKETS: Mapping[str, str] = {
    "single_key_consumption": "consumption_failures",
    "key_partition_accounting": "partition_failures",
    "namespace_validation": "namespace_failures",
    "client_contract_agreement": "contract_failures",
    "alias_derivation": "derivation_failures",
}

_CACHE = AnalysisCache()


def merged_config(configs: Mapping[str, Sequence[Mapping[str, Any]]], name: str) -> Any:
    "One partner's configuration, its layers folded by the frozen contract."

    return reference_protocol().merge_configs(*configs[name])


def accepted_keys(
    fields: Sequence[Mapping[str, Any]], config: Any
) -> dict[str, tuple[str, ...]]:
    "Every input key that carries one field's value, its published key first."

    protocol = reference_protocol()
    resolved: dict[str, tuple[str, ...]] = {}
    for field in fields:
        field_id = str(field["id"])
        key = field_id
        if config.trim_trailing_underscore:
            key = key.rstrip("_")
        if config.name_style:
            key = protocol.convert_name(key, config.name_style)
        key = str(dict(config.rename or {}).get(field_id, key))
        spellings = [key, *protocol.declared_aliases(config, field_id)]
        spellings += [
            protocol.convert_name(field_id, style)
            for style in protocol.declared_styles(config)
        ]
        resolved[field_id] = tuple(dict.fromkeys(spellings))
    return resolved


def _listed(values: Sequence[str]) -> str:
    items = [str(item) for item in values]
    return ", ".join(items) if items else "nothing"


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


class Review:
    'Everything the five checks read from one run of the posts.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.rows = {
            str(row.get("label")): dict(row) for row in candidate.get("operations", ())
        }
        self.program = program
        self.expect = private_expectations()
        protocol = reference_protocol()
        self.fields = tuple(
            protocol.FieldSpec(**dict(field)) for field in program["shape"]["fields"]
        )
        self._accepted: dict[str, dict[str, tuple[str, ...]]] = {}

    def accepted(self, partner: str) -> dict[str, tuple[str, ...]]:
        "Every input key that carries each field's value, for one partner."

        if partner not in self._accepted:
            config = merged_config(self.program["configs"], partner)
            self._accepted[partner] = accepted_keys(
                self.program["shape"]["fields"], config
            )
        return self._accepted[partner]

    def field_of(self, partner: str, key: str) -> str:
        for field_id, keys in self.accepted(partner).items():
            if key in keys:
                return field_id
        return "no field of ours"

    def row(self, label: str) -> dict[str, Any]:
        return self.rows.get(label, {})

    def error(self, label: str) -> str:
        return str(self.row(label).get("error") or "")

    def trail(self, label: str) -> tuple[str, ...]:
        'The keys this failure quotes back to the partner, in the order given.'

        return tuple(str(item) for item in (self.row(label).get("trail") or ()))

    def result(self, label: str) -> Any:
        return self.row(label).get("result")

    def wrong_record(self, label: str) -> str:
        'How this post ended, when it did not end as the record we expect.'

        return self.error(label) or "a record that does not match what they sent"

    def nothing_written(self, label: str) -> str:
        'What came back where a record written for the readers should be.'

        return self.error(label) or "something that is not a record at all"


def _consumption_failures(review: Review) -> list[dict[str, Any]]:
    "One field's value comes out of exactly one key the partner sent."

    failures: list[dict[str, Any]] = []
    for label in ("ravel-both-differ", "ravel-three-spellings", "ravel-both-agree"):
        expected = review.expect[label]
        base = {
            "partner": expected["partner"], "payload_id": expected["id"],
            "field": expected["field"], "keys": " and ".join(expected["keys"]),
        }
        if review.error(label) != "AmbiguousKeysError":
            failures.append(_fail("two_spellings_one_field_accepted", **base))
        elif tuple(sorted(review.trail(label))) != tuple(sorted(expected["keys"])):
            failures.append(_fail(
                "refusal_named_the_wrong_keys", **base,
                reported=_listed(review.trail(label))))
    for label in ("ravel-alias-only", "ravel-primary-only"):
        expected = review.expect[label]
        if review.error(label) or review.result(label) != expected["record"]:
            failures.append(_fail(
                "one_spelling_payload_refused", partner=expected["partner"],
                payload_id=expected["id"], key=expected["spelling"],
                error=review.wrong_record(label)))
    label = "ravel-required-missing"
    expected = review.expect[label]
    if review.error(label) != expected["error"]:
        failures.append(_fail(
            "missing_required_field_not_refused", partner=expected["partner"],
            payload_id=expected["id"], field=expected["field"],
            error=review.wrong_record(label)))
    return failures


def _partition_failures(review: Review) -> list[dict[str, Any]]:
    'Every key a partner sends is consumed or reported, once, never both.'

    failures: list[dict[str, Any]] = []
    clean = review.expect["sable-strict-aliases"]
    if review.error("sable-strict-aliases") or review.result(
        "sable-strict-aliases"
    ) != clean["record"]:
        failures.append(_fail(
            "alias_key_not_recognised", partner=clean["partner"], payload_id=clean["id"],
            key=clean["spelling"], error=review.wrong_record("sable-strict-aliases")))
    typo = review.expect["sable-strict-typo"]
    if review.error("sable-strict-typo") != typo["error"]:
        failures.append(_fail(
            "unknown_key_not_reported", partner=typo["partner"], payload_id=typo["id"],
            key=typo["key"]))
    elif review.trail("sable-strict-typo") != typo["trail"]:
        stray = [key for key in review.trail("sable-strict-typo") if key != typo["key"]]
        failures.append(_fail(
            "alias_key_not_recognised", partner=typo["partner"], payload_id=typo["id"],
            key=stray[0] if stray else typo["spelling"], error="a bounced payload"))
    collect = review.expect["tessel-collect-mixed"]
    loaded = review.result("tessel-collect-mixed")
    if review.error("tessel-collect-mixed") or not isinstance(loaded, Mapping):
        failures.append(_fail(
            "alias_key_not_recognised", partner=collect["partner"],
            payload_id=collect["id"], key=collect["spelling"],
            error=review.wrong_record("tessel-collect-mixed")))
        return failures
    kept = dict(loaded.get(collect["extra_in"]) or {})
    accepted = {key for keys in review.accepted(collect["partner"]).values() for key in keys}
    body = {key: value for key, value in loaded.items() if key != collect["extra_in"]}
    if body != collect["record"]:
        failures.append(_fail(
            "alias_key_not_recognised", partner=collect["partner"],
            payload_id=collect["id"], key=collect["spelling"],
            error=review.wrong_record("tessel-collect-mixed")))
    for key in sorted(key for key in kept if key in accepted):
        failures.append(_fail(
            "alias_collected_as_extra", partner=collect["partner"],
            payload_id=collect["id"], key=key,
            field=review.field_of(collect["partner"], key)))
    for key in sorted(set(kept) - set(collect["extra"]) - accepted):
        failures.append(_fail(
            "unknown_key_was_invented", partner=collect["partner"],
            payload_id=collect["id"], key=key))
    for key, value in sorted(collect["extra"].items()):
        if key not in kept or kept[key] != value:
            failures.append(_fail(
                "unknown_key_not_collected", partner=collect["partner"],
                payload_id=collect["id"], key=key))
    return failures


def _namespace_failures(review: Review) -> list[dict[str, Any]]:
    'Two fields never share a key; one field naming a key twice is one key.'

    failures: list[dict[str, Any]] = []
    for label in ("build-tarn", "build-umbra", "build-wold"):
        expected = review.expect[label]
        named = " and ".join(expected["fields"])
        if not review.error(label):
            failures.append(_fail(
                "colliding_fields_built_anyway", partner=expected["partner"],
                fields=named, key=expected["key"]))
        elif review.error(label) != "ConfigError":


            failures.append(_fail(
                "collision_refused_outside_the_error_family",
                partner=expected["partner"], fields=named, key=expected["key"],
                error=review.error(label)))
    for label in ("build-vesper", "build-northgate"):
        expected = review.expect[label]
        if review.error(label):
            failures.append(_fail(
                "live_config_refused_at_build", partner=expected["partner"],
                key=expected["key"], error=review.error(label)))
    for label in ("vesper-load", "northgate-load"):
        expected = review.expect[label]
        if review.error(f"build-{expected['partner']}"):
            continue
        if review.error(label) or review.result(label) != expected["record"]:
            failures.append(_fail(
                "live_config_refused_every_payload", partner=expected["partner"],
                payload_id=expected["id"], key=expected["self_key"],
                error=review.wrong_record(label)))
    return failures


def _property_type(fragment: Any) -> str:
    if isinstance(fragment, Mapping) and fragment.get("type"):
        return str(fragment["type"])
    return "no type at all"


def _fragment_parts(fragment: Any) -> str:
    'What one published entry says about a key, by name.'

    if isinstance(fragment, Mapping):
        return _listed(sorted(str(name) for name in fragment))
    return "nothing a partner can read"


def _contract_failures(review: Review) -> list[dict[str, Any]]:
    'The accepted-key catalogue and bounce trail stay faithful to intake.'

    protocol = reference_protocol()
    failures: list[dict[str, Any]] = []
    for label in ("schema-sable", "schema-quill", "schema-pellworm"):
        partner = review.expect[label]["partner"]
        published = review.result(label) if isinstance(review.result(label), Mapping) else {}
        properties = dict(published.get("properties") or {})
        required = [str(item) for item in (published.get("required") or ())]
        accepted = review.accepted(partner)
        expected_properties: dict[str, Any] = {}
        expected_required: set[str] = set()
        for field in review.fields:
            fragment = protocol.schema_property(field)
            keys = accepted[field.id]
            expected_properties.update({key: fragment for key in keys})
            if field.required and len(keys) == 1:
                expected_required.add(keys[0])
            for key in keys:
                if key not in properties:
                    failures.append(_fail(
                        "schema_omits_an_accepted_key", partner=partner, key=key,
                        field=field.id))
                    continue
                entry = properties[key]
                if _property_type(entry) != _property_type(fragment):
                    failures.append(_fail(
                        "schema_key_typed_unlike_the_field", partner=partner, key=key,
                        field=field.id, field_type=_property_type(fragment),
                        published_type=_property_type(entry)))
                elif entry != fragment:
                    failures.append(_fail(
                        "schema_key_published_unlike_the_field", partner=partner,
                        key=key, field=field.id,
                        published_parts=_fragment_parts(entry),
                        expected_parts=_fragment_parts(fragment)))
            demanded = [key for key in required if key in keys]
            if demanded and (len(keys) > 1 or not field.required):
                failures.append(_fail(
                    "schema_demanded_one_spelling", partner=partner, key=demanded[0],
                    field=field.id))
        for key in sorted(set(properties) - set(expected_properties)):
            failures.append(_fail(
                "schema_published_an_unaccepted_key", partner=partner, key=key))
        for key in sorted(expected_required - set(required)):
            failures.append(_fail(
                "schema_omitted_a_required_key", partner=partner, key=key,
                field=review.field_of(partner, key)))
        for key in sorted(set(required) - set(expected_properties)):
            failures.append(_fail(
                "schema_published_an_unaccepted_key", partner=partner, key=key))
    quoted = review.expect["sable-bad-value"]
    if review.error("sable-bad-value") != quoted["error"] or review.trail(
        "sable-bad-value"
    ) != quoted["trail"]:
        failures.append(_fail(
            "error_trail_named_an_unsent_key", partner=quoted["partner"],
            payload_id=quoted["id"], sent=quoted["key"],
            reported=_listed(review.trail("sable-bad-value"))))
    return failures


def _derivation_failures(review: Review) -> list[dict[str, Any]]:
    "A spelling is taken as written, or made from the field's own name."

    failures: list[dict[str, Any]] = []
    for label, kind in (
        ("pellworm-generated", "generated_alias_not_accepted"),
        ("quill-literal", "explicit_alias_was_rewritten"),
        ("yarrow-second-style", "generated_alias_not_accepted"),
    ):
        expected = review.expect[label]
        if review.error(label) or review.result(label) != expected["record"]:
            failures.append(_fail(
                kind, partner=expected["partner"], payload_id=expected["id"],
                key=expected["spelling"], field=expected["field"]))
    for label in ("dump-ravel", "dump-pellworm", "dump-partial"):
        expected = review.expect[label]
        partner = expected["partner"]
        published = {keys[0] for keys in review.accepted(partner).values()}
        written = review.result(label)
        if not isinstance(written, Mapping):
            failures.append(_fail(
                "dump_did_not_write_a_record", partner=partner,
                ended_as=review.nothing_written(label)))
            continue
        stray = sorted(key for key in written if key not in published)
        if stray:
            failures.append(_fail(
                "alias_leaked_into_the_output", partner=partner, key=stray[0],
                field=review.field_of(partner, stray[0])))
        if dict(written) != expected["record"]:
            different = sorted(
                key for key in set(written) | set(expected["record"])
                if written.get(key) != expected["record"].get(key)
            )
            failures.append(_fail(
                "dump_record_disagrees", partner=partner, key=different[0]))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "consumption_failures": _consumption_failures(review),
        "partition_failures": _partition_failures(review),
        "namespace_failures": _namespace_failures(review),
        "contract_failures": _contract_failures(review),
        "derivation_failures": _derivation_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the intake console shows when a run did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "intake ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "intake ended without saying why"
    return f"intake stopped part way through the posts: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private week of posts against this workspace and bucket what went wrong.'

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
        analysis["case"] = {
            "run": "release",
            "operations": len(program["operations"]),
            "partners": len(program["configs"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _shape_rows(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(field) for field in program["shape"]["fields"]]


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
            "shape": program["shape"]["name"] if program else None,
            "partners": sorted(program.get("configs", {})),
        })
    return {
        "summary": "The intake workspace and the recorded runs of partner posts.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "intake_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "intake").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _payload_keys(op: Mapping[str, Any]) -> list[str]:
    payload = dict(op.get("payload") or {})
    body = next(
        (value for key, value in payload.items() if isinstance(value, Mapping)), {}
    )
    return sorted(str(key) for key in body)


def _operation_rows(
    candidate: Mapping[str, Any], program: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'Every operation the console drove and what intake did with it.'

    posted = {str(op["label"]): dict(op) for op in program.get("operations", ())}
    rows: list[dict[str, Any]] = []
    for record in candidate.get("operations", ()):
        label = str(record.get("label"))
        op = posted.get(label, {})
        row: dict[str, Any] = {
            "label": label,
            "operation": record.get("op"),
            "partner": record.get("config"),
            "completed": bool(record.get("ok")),
        }
        if str(record.get("op")) == "load":
            row["envelopes_in_the_payload"] = sorted(
                str(key) for key in dict(op.get("payload") or {})
            )
            row["keys_the_partner_sent"] = _payload_keys(op)
            row["value_taken_from"] = [
                f"{entry.get('field')} <- {entry.get('key')}"
                for entry in record.get("consumed", ())
            ]
        if record.get("error"):
            row["bounced_with"] = record.get("error")
            row["message"] = record.get("message")
            row["trail"] = record.get("trail")
        if record.get("result") is not None:
            row["result"] = record.get("result")
        rows.append(row)
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded run of partner posts and report the intake log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} posts could not run against this workspace.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    return {
        "summary": f"The {record_id} posts ran against this workspace.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "shape": {"name": program["shape"]["name"], "fields": _shape_rows(program)},
            "partner_settings": candidate.get("configs", {}),
        },
        "public": {"what_intake_did": _operation_rows(candidate, program)},
    }
