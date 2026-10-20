'Deterministic, sandboxed analysis of one scene-checkpoint workspace.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import build_program, registry_entries


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("scene/checkpoint.py", "scene/tools.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-scene-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "review", "variant": 7}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "tuesday-batch-paint": {"profile": "paint", "variant": 1},
    "slot-reuse-revert": {"profile": "slots", "variant": 2},
    "revert-twice-drift": {"profile": "drift", "variant": 3},
    "panel-parity-check": {"profile": "panel", "variant": 4},
    "yesterday-file-offer": {"profile": "refusal", "variant": 5},
}

BUCKETS: Mapping[str, str] = {
    "isolated_checkpoint_value": "isolation_failures",
    "exact_prop_restore": "restore_failures",
    "preserved_prop_identity": "identity_failures",
    "refused_revert_leaves_level": "refusal_failures",
    "canonical_change_report": "report_failures",
}

PHASES = ("paint", "slots", "drift", "refusal", "handover", "panel")


RESTORE_PHASES = ("paint",)
IDENTITY_PHASES = ("paint", "slots", "handover")


REFUSAL_PHASES = ("refusal", "handover")

CHANGE_FIELDS = ("added", "removed", "changed")
SESSION_TRAIT = "Selection"

_CACHE = AnalysisCache()


def _phase(records: Sequence[Mapping[str, Any]], phase: str) -> list[Mapping[str, Any]]:
    return [record for record in records if str(record.get("phase")) == phase]


def _names(record: Mapping[str, Any]) -> dict[int, str]:
    return {int(value): str(key) for key, value in dict(record.get("props", {})).items()}


def _rows(record: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row["id"]): dict(row) for row in record.get("scene", ())}


def _level(record: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    return {key: row for key, row in _rows(record).items() if not row.get("session")}


def _session_row(record: Mapping[str, Any]) -> dict[str, Any] | None:
    return next((row for row in _rows(record).values() if row.get("session")), None)


def _source(
    records: Sequence[Mapping[str, Any]], position: int, name: str
) -> Mapping[str, Any] | None:
    'The step that last wrote the file this revert is reading.'
    for record in reversed(records[:position]):
        if str(record.get("checkpoint")) == str(name) and str(record.get("type")) in (
            "capture",
            "record_reference",
        ):
            return record
    return None


def _edges(row: Mapping[str, Any]) -> dict[tuple[str, int, str], int]:
    counted: dict[tuple[str, int, str], int] = {}
    for key, edges in dict(row.get("relations") or {}).items():
        for edge in edges:
            item = (str(key), int(edge["target"]), json.dumps(edge.get("data"), sort_keys=True))
            counted[item] = counted.get(item, 0) + 1
    return counted


def _listed(values: Sequence[Any]) -> str:
    'A list of things as the panel reads them out, never an empty phrase.'
    rows = [str(item) for item in values]
    if not rows:
        return "nothing"
    return rows[0] if len(rows) == 1 else f"{', '.join(rows[:-1])} and {rows[-1]}"


def _prop(names: Mapping[int, str], entity: Any) -> str:
    return names.get(int(entity), f"the prop with id {int(entity)}")


def _traits(row: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((row or {}).get("traits") or {})


def _isolation_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:


    rows = _phase(records, "drift")
    failures = [
        {"kind": "editor_step_failed", "phase": "drift",
         "label": record.get("label"), "operation": record.get("type"),
         "error": record.get("error"), "detail": "the step raised instead of completing"}
        for record in rows
        if not record.get("ok")
    ]
    if failures:
        return failures

    taken: dict[str, str] = {}
    at_capture: dict[str, str] = {}
    reverted: set[str] = set()
    results: dict[str, list[Mapping[str, Any]]] = {}
    for record in rows:
        kind, name = str(record.get("type")), str(record.get("checkpoint"))
        digests = dict(record.get("checkpoint_digests") or {})
        if kind in ("capture", "record_reference"):
            taken[name] = str(digests.get(name))
            at_capture[name] = str(record.get("digest"))
        for saved, before in list(taken.items()):
            now = str(digests.get(saved, before))
            if now == before:
                continue
            taken[saved] = now
            failures.append({
                "kind": "revert_left_the_level_wired_to_the_checkpoint"
                if saved in reverted
                else "checkpoint_moved_with_the_level",
                "phase": "drift", "label": record.get("label"), "checkpoint": saved,
                "prop": record.get("prop"), "was": before, "now": now,
                "detail": "the file changed when the level did",
            })
        if kind != "restore":
            continue
        reverted.add(name)
        results.setdefault(name, []).append(record)
        recorded = at_capture.get(name)
        if recorded is not None and str(record.get("digest")) != recorded:
            failures.append({
                "kind": "revert_did_not_reproduce_the_checkpoint", "phase": "drift",
                "label": record.get("label"), "checkpoint": name,
                "digest": str(record.get("digest")), "recorded_digest": recorded,
                "detail": "the level after the revert is not the level the file holds",
            })
    for name, rows in results.items():
        for earlier, later in zip(rows, rows[1:]):
            if str(earlier.get("digest")) == str(later.get("digest")):
                continue
            failures.append({
                "kind": "second_revert_gave_a_different_level", "phase": "drift",
                "checkpoint": name, "first_label": str(earlier.get("label")),
                "second_label": str(later.get("label")),
                "first_digest": str(earlier.get("digest")),
                "second_digest": str(later.get("digest")),
                "detail": "two reverts to one file gave two different levels",
            })


    saved_name = "crate-yesterday"
    before: str | None = None
    one_prop_reverted = False
    for record in _phase(records, "handover"):
        digests = dict(record.get("checkpoint_digests") or {})
        if str(record.get("type")) == "capture" and str(record.get("checkpoint")) == saved_name:
            before = str(digests.get(saved_name))
            continue
        if (
            str(record.get("type")) == "restore_entity"
            and str(record.get("checkpoint")) == saved_name
            and record.get("ok")
        ):
            one_prop_reverted = True
        if before is None or str(record.get("type")) != "brush_edge":
            continue
        now = str(digests.get(saved_name, before))
        if now != before:
            failures.append({
                "kind": "revert_left_the_level_wired_to_the_checkpoint"
                if one_prop_reverted else "checkpoint_moved_with_the_level",
                "phase": "handover", "label": record.get("label"),
                "checkpoint": saved_name, "prop": record.get("prop"),
                "was": before, "now": now,
                "detail": "the file changed when the level did",
            })
            before = now
    return failures


def _restore_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for phase in RESTORE_PHASES:
        rows = _phase(records, phase)
        for position, record in enumerate(rows):
            kind = str(record.get("type"))
            if kind not in ("restore", "restore_entity"):
                continue
            source = _source(rows, position, str(record.get("checkpoint")))
            if source is None:
                continue
            names, recorded, current = _names(record), _level(source), _level(record)
            if kind == "restore_entity":
                props = dict(record.get("props", {}))
                wanted = {int(props[str(record.get("prop"))])} if record.get("prop") in props else set()
            else:
                wanted = set(recorded)
            for entity in sorted(wanted & set(recorded) & set(current)):
                before, after = _traits(recorded[entity]), _traits(current[entity])
                common = {"phase": phase, "label": record.get("label"),
                          "prop": _prop(names, entity), "entity": entity}
                for key in sorted(set(after) - set(before)):
                    failures.append({**common, "kind": "revert_left_a_surplus_trait", "key": key})
                for key in sorted(set(before) - set(after)):
                    failures.append({**common, "kind": "revert_dropped_a_recorded_trait", "key": key})
                for key in sorted(set(before) & set(after)):
                    if before[key] == after[key]:
                        continue
                    mode = (
                        "revert_turned_a_tag_into_data"
                        if (before[key] is True) != (after[key] is True)
                        else "revert_kept_the_new_value"
                    )
                    failures.append({**common, "kind": mode, "key": key})
    return failures


def _identity_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for phase in IDENTITY_PHASES:
        rows = _phase(records, phase)
        for position, record in enumerate(rows):
            kind = str(record.get("type"))
            if kind not in ("restore", "restore_entity") or (
                phase == "handover" and not record.get("ok")
            ):
                continue
            source = _source(rows, position, str(record.get("checkpoint")))
            if source is None:
                continue
            names, before_names = _names(record), _names(source)
            recorded, current = _level(source), _level(record)
            common = {"phase": phase, "label": record.get("label")}
            if kind == "restore_entity":
                props = dict(record.get("props", {}))
                restored = props.get(str(record.get("prop")))
                compared = {int(restored)} if restored is not None else set()
                gone: list[int] = []
                new: list[int] = []
            else:
                compared = set(recorded) & set(current)
                gone = sorted(set(recorded) - set(current))
                new = sorted(set(current) - set(recorded))
            twins = {
                entity: next(
                    (other for other in new if _traits(current[other]) == _traits(recorded[entity])),
                    None,
                )
                for entity in gone
            }
            for entity in gone:
                twin = twins[entity]
                if twin is None:
                    failures.append({
                        **common, "kind": "destroyed_prop_not_brought_back",
                        "prop": _prop(before_names, entity), "entity": entity,
                        "slot": int(recorded[entity].get("slot", 0)),
                        "generation": int(recorded[entity].get("generation", 0)),
                    })
                else:
                    failures.append({
                        **common, "kind": "prop_came_back_under_a_new_id",
                        "prop": _prop(before_names, entity), "entity": entity,
                        "recorded_slot": int(recorded[entity].get("slot", 0)),
                        "now_slot": int(current[twin].get("slot", 0)), "now_id": twin,
                    })
            for entity in sorted(set(new) - {twin for twin in twins.values() if twin}):
                failures.append({
                    **common, "kind": "surplus_prop_survived_the_revert",
                    "prop": _prop(names, entity), "entity": entity,
                })
            for entity in sorted(compared & set(recorded) & set(current)):
                before, after = _edges(recorded[entity]), _edges(current[entity])
                shared = {**common, "prop": _prop(names, entity), "entity": entity}
                for key, target, _data in sorted(set(after) - set(before)):
                    failures.append({
                        **shared, "kind": "link_points_somewhere_else", "key": key,
                        "now_pointing_at": _prop(names, target),
                        "recorded_targets": _listed(
                            sorted(_prop(names, row[1]) for row in before if row[0] == key)
                        ),
                    })
                for key, target, _data in sorted(set(before) - set(after)):
                    failures.append({
                        **shared, "kind": "recorded_link_missing", "key": key,
                        "target": _prop(before_names, target),
                    })
                for item in sorted(set(before) & set(after)):
                    if after[item] < before[item]:
                        failures.append({
                            **shared, "kind": "recorded_link_missing", "key": item[0],
                            "target": _prop(before_names, item[1]),
                        })
                    elif after[item] > before[item]:
                        failures.append({
                            **shared, "kind": "link_recorded_twice", "key": item[0],
                            "target": _prop(names, item[1]), "copies": int(after[item]),
                        })
    for phase in PHASES:
        rows = _phase(records, phase)
        for position, record in enumerate(rows):
            if position == 0 or str(record.get("type")) not in (
                "restore", "restore_entity", "restore_broken", "offer_entity",
            ):
                continue
            before_session = _session_row(rows[position - 1])
            after_session = _session_row(record)
            if before_session is not None and _traits(after_session) != _traits(before_session):
                failures.append({
                    "phase": phase, "label": record.get("label"),
                    "kind": "session_entity_disturbed", "key": SESSION_TRAIT,
                    "detail": "the revert reached the editor's own session entity",
                })
    return failures


_WHOLE_LEVEL_MODES: Mapping[str, str] = {
    "half_changed": "broken_checkpoint_left_the_level_half_changed",
    "went_ahead": "broken_checkpoint_applied",
    "wrong_error": "refusal_used_the_wrong_error",
    "good_refused": "good_checkpoint_refused",
}
_ONE_PROP_MODES: Mapping[str, str] = {
    "half_changed": "broken_prop_file_left_the_prop_half_changed",
    "went_ahead": "broken_prop_file_applied",
    "wrong_error": "prop_refusal_used_the_wrong_error",
    "good_refused": "good_prop_file_refused",
}


_OFFERED = {"restore_broken": _WHOLE_LEVEL_MODES, "offer_entity": _ONE_PROP_MODES}


_HONOURED = {"restore": _WHOLE_LEVEL_MODES, "restore_entity": _ONE_PROP_MODES}


def _refusal_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for phase in REFUSAL_PHASES:
        rows = _phase(records, phase)
        for position, record in enumerate(rows):
            kind = str(record.get("type"))


            named = record.get("prop")
            scoped = {"prop": str(named)} if named is not None else {}
            honoured = _HONOURED.get(kind)
            if honoured is not None and not record.get("ok"):
                failures.append({
                    "kind": honoured["good_refused"], "phase": phase,
                    "label": record.get("label"), **scoped,
                    "error": str(record.get("error", "it refused")),
                    "detail": "a file that fits the level was refused",
                })
            modes = _OFFERED.get(kind)
            if modes is None:
                continue
            before = str(rows[position - 1].get("digest")) if position else ""
            raised = record.get("raised")
            common = {
                "phase": phase, "label": record.get("label"), **scoped,
                "fault": str(record.get("fault", "it does not fit the level")),
                "before_digest": before, "after_digest": str(record.get("digest")),
            }
            if before and str(record.get("digest")) != before:
                failures.append({
                    **common, "kind": modes["half_changed"],
                    "detail": "the level is neither what it was nor what the file holds",
                })
            if raised is None:
                failures.append({
                    **common, "kind": modes["went_ahead"],
                    "detail": "the revert went ahead on a file it cannot honour",
                })
            elif str(raised) != "CheckpointError":
                failures.append({
                    **common, "kind": modes["wrong_error"],
                    "error": f"{raised}: {str(record.get('raised_text', ''))[:120]}",
                    "detail": "the editor could not tell this apart from a crash",
                })
    return failures


def _keyed(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keyed = dict(snapshot.get("traits") or {})
    keyed.update(dict(snapshot.get("relations") or {}))
    return keyed


def _expected(record: Mapping[str, Any]) -> dict[str, list[Any]]:
    left, right = record.get("left_canonical"), record.get("right_canonical")
    if str(record.get("scope")) == "entity":
        before, after = _keyed(dict(left or {})), _keyed(dict(right or {}))
    else:
        before = {int(item["id"]): item for item in dict(left or {}).get("entities", ())}
        after = {int(item["id"]): item for item in dict(right or {}).get("entities", ())}
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(
            key for key in set(before) & set(after)
            if json.dumps(before[key], sort_keys=True) != json.dumps(after[key], sort_keys=True)
        ),
    }


def _order(value: Any) -> tuple[int, Any]:
    return (0, value) if isinstance(value, int) else (1, str(value))


def _report_failures(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for record in _phase(records, "panel"):
        if str(record.get("type")) != "panel":
            continue
        names, reported = _names(record), record.get("reported")
        common = {"phase": "panel", "label": record.get("label")}
        if not isinstance(reported, Mapping) or set(reported) != set(CHANGE_FIELDS):
            failures.append({
                **common, "kind": "panel_report_wrong_shape",
                "problem": f"it came back as {json.dumps(reported, sort_keys=True)[:80]}",
            })
            continue
        if any(not isinstance(reported[field], list) for field in CHANGE_FIELDS):
            failures.append({
                **common, "kind": "panel_report_wrong_shape",
                "problem": "one of its three lists is not a list",
            })
            continue
        expected = _expected(record)
        same = record.get("left_canonical") == record.get("right_canonical")
        for field in CHANGE_FIELDS:
            listed = list(reported[field])
            shown = [_prop(names, item) if isinstance(item, int) else str(item) for item in listed]
            wanted = [
                _prop(names, item) if isinstance(item, int) else str(item)
                for item in expected[field]
            ]
            if same and listed:
                failures.append({
                    **common, "kind": "panel_flagged_an_unchanged_prop",
                    "field": field, "listed": _listed(shown),
                })
                continue
            unmatched = list(wanted)
            extra = []
            for item in shown:
                if item in unmatched:
                    unmatched.remove(item)
                else:
                    extra.append(item)
            missing = unmatched
            if missing:
                failures.append({
                    **common, "kind": "panel_missed_a_change", "field": field,
                    "missing": _listed(missing), "listed": _listed(shown),
                })
            if extra:
                failures.append({
                    **common, "kind": "panel_reported_a_change_that_is_not_there",
                    "field": field, "extra": _listed(extra), "listed": _listed(shown),
                })
            if not missing and not extra and listed != sorted(listed, key=_order):
                failures.append({
                    **common, "kind": "panel_rows_out_of_order", "field": field,
                    "listed": _listed(shown),
                })
    return failures


def _records_with_phase(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    raw_records = candidate.get("records")
    if not isinstance(raw_records, list) or len(raw_records) != len(program):
        raise ValueError("the editor session returned the wrong number of steps")
    records: list[dict[str, Any]] = []
    for index, (record, event) in enumerate(zip(raw_records, program)):
        if not isinstance(record, Mapping):
            raise ValueError("the editor session returned a malformed step")
        kind = str(event.get("type", ""))
        records.append({
            **dict(record),
            "index": index,
            "type": kind,
            "label": str(event.get("label", f"{kind}-{index}")),
            "phase": str(event.get("phase", "")),
        })
    return records


def _analyse(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    try:
        records = _records_with_phase(candidate, program)
    except (TypeError, ValueError) as exc:
        return dict(failed_analysis(str(exc), tuple(BUCKETS.values())))
    return {
        "isolation_failures": _isolation_failures(records),
        "restore_failures": _restore_failures(records),
        "identity_failures": _identity_failures(records),
        "refusal_failures": _refusal_failures(records),
        "report_failures": _report_failures(records),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    "The one line the editor's log shows when a session did not finish."

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the build machine stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the editor ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the editor ended without saying why"
    return f"the editor stopped before the session finished: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private review session against this workspace and bucket what went wrong.'
    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]), int(PRIVATE_CASE["variant"]))
        candidate = PROJECT.invoke(
            artifact_dir, {"registry": registry_entries(), "events": list(program)}
        )
        if not candidate.get("ok"):
            analysis = dict(failed_analysis(_console_error(candidate), tuple(BUCKETS.values())))
            if candidate.get("diagnostic"):
                analysis["diagnostic"] = str(candidate["diagnostic"])
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"session": "review", "phases": list(PHASES)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = [
        {"record": f"project_records/{path.name}", "scene": _record_scene(path).get("scene")}
        for path in sorted((root / "project_records").glob("*.json"))
    ]
    return {
        "summary": "The editor workspace and the sessions the tools team replays before a build goes out.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "editor_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "scene").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
            "declared_keys": sorted(str(entry["key"]) for entry in registry_entries()),
        },
        "records": records,
    }


_FULL_ROWS = (
    "capture", "record_reference", "restore", "restore_entity", "restore_broken",
    "offer_entity", "destroy", "inspect",
)


_ROSTER_ROWS = ("define", "create")


def _prop_row(names: Mapping[int, str], entity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "prop": "the editor's own session entity" if entity["session"]
        else _prop(names, entity["id"]),
        "id": entity["id"], "slot": entity["slot"], "generation": entity["generation"],
        "editor_session_entity": entity["session"],
        "traits": entity["traits"], "links": entity["relations"],
    }


def _step_row(record: Mapping[str, Any]) -> dict[str, Any]:
    names, kind = _names(record), str(record.get("type"))
    row: dict[str, Any] = {
        "step": record.get("label"), "action": kind,
        "completed": bool(record.get("ok")), "level_digest": record.get("digest"),
    }
    if record.get("error") is not None:
        row["error"] = record.get("error")
    if record.get("checkpoint_digests"):
        row["saved_files"] = record.get("checkpoint_digests")
    if record.get("checkpoint") is not None:
        row["file"] = record.get("checkpoint")
    if record.get("prop") is not None:
        row["prop"] = record.get("prop")
    if kind in _FULL_ROWS:
        row["level"] = [_prop_row(names, entity) for entity in record.get("scene", ())]
    elif kind in ("brush", "brush_edge"):
        row["prop_after_this_step"] = [
            _prop_row(names, entity)
            for entity in record.get("scene", ())
            if _prop(names, entity["id"]) == str(record.get("prop"))
        ]
    elif kind in _ROSTER_ROWS:
        row["props_in_the_level"] = {
            _prop(names, entity["id"]): entity["id"]
            for entity in record.get("scene", ())
            if not entity["session"]
        }
    if kind in ("restore_broken", "offer_entity"):
        row["file_fault"] = record.get("fault")
        row["revert_raised"] = record.get("raised")
        row["revert_message"] = record.get("raised_text")
    if kind == "panel":
        row["panel_showed"] = record.get("reported")
        row["left_side_compared"] = record.get("left_canonical")
        row["right_side_compared"] = record.get("right_canonical")
    return row


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded session against this workspace and report what happened.'
    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    case = PUBLIC_RECORDS[record_id]
    program = build_program(str(case["profile"]), int(case["variant"]))
    candidate = PROJECT.invoke(
        Path(artifact_dir), {"registry": registry_entries(), "events": list(program)}
    )
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} session could not run this editor to the end.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    records = _records_with_phase(candidate, program)
    return {
        "summary": f"The {record_id} session ran against this editor.",
        "measurements": {
            "record_id": record_id, "scene": raw.get("scene"), "step_count": len(records),
        },
        "public": {"session_timeline": [_step_row(record) for record in records]},
    }
