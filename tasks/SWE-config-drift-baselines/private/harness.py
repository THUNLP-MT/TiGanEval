'Deterministic, sandboxed analysis of one estate compliance workspace.'

from __future__ import annotations

from collections import defaultdict
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import PRIVATE_PROFILE, build_program


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("estate/reconcile.py", "estate/notes.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-estate-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": PRIVATE_PROFILE}


PUBLIC_RECORDS: Mapping[str, str] = {
    "reboot-night": "reboot",
    "nightly-scans": "nightly",
    "triage-log": "triage",
    "baseline-events": "baselines",
}

BUCKETS: Mapping[str, str] = {
    "drift_record_identity": "identity_failures",
    "drift_lifecycle": "lifecycle_failures",
    "compliance_accounting": "accounting_failures",
    "baseline_state_integrity": "baseline_failures",
    "observed_config_normalisation": "normalisation_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `estate/protocol.py` from the project's own tree, so the canonical     forms, drift vocabulary, severity table and arithmetic here are what ships."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "estate" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_estate_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


_PHRASE: Mapping[str, str] = {
    "image_changed": "the image", "restart_policy_changed": "the restart policy",
    "network_changed": "the network", "env_changed": "the environment settings",
    "binding_changed:ports": "the port bindings", "binding_changed:mounts": "the mounts",
    "resource_changed:memory_mb": "the memory limit",
    "resource_changed:cpu_share": "the CPU share", "label_changed": "the labels",
    "service_missing": "the service being gone", "service_added": "the service being new",
}


def _phrase(drift_type: str, field: str) -> str:
    return _PHRASE.get(f"{drift_type}:{field}", _PHRASE.get(drift_type, drift_type))


def _conditions(protocol: Any, declared: Mapping[str, Any],
                observed: Mapping[str, Any]) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    'Every deviation an estate is in on one night, by what the record is about.'

    conditions: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for service, want in declared.items():
        found = observed.get(service)
        if found is None:
            conditions[(service, protocol.SERVICE_MISSING, "")] = (
                protocol.render_value(want.get(protocol.RELEASE_REFERENCE_KEY)),
                "", protocol.CRITICAL)
            continue
        for setting, value in want.items():
            if setting not in found or found[setting] == value:
                continue
            drift_type = protocol.drift_type_for(setting)
            conditions[(service, drift_type, protocol.field_for(drift_type, setting))] = (
                protocol.render_value(value), protocol.render_value(found[setting]),
                protocol.severity_for(drift_type))
    for service, found in observed.items():
        if service not in declared:
            conditions[(service, protocol.SERVICE_ADDED, "")] = (
                "", protocol.render_value(found.get(protocol.RELEASE_REFERENCE_KEY)),
                protocol.MEDIUM)
    return conditions


def _numbers(protocol: Any, declared: Mapping[str, Any], observed: Mapping[str, Any],
             conditions: Mapping[tuple[str, str, str], tuple[str, str, str]]) -> dict[str, Any]:
    "The night's numbers over the population the baseline declares."

    missing = {key[0] for key in conditions if key[1] == protocol.SERVICE_MISSING}
    added = {key[0] for key in conditions if key[1] == protocol.SERVICE_ADDED}
    drifted = {key[0] for key in conditions
               if key[1] not in (protocol.SERVICE_MISSING, protocol.SERVICE_ADDED)
               and key[0] in declared}
    unknown = {service for service, expected in declared.items()
               if service in observed and service not in drifted
               and any(setting not in observed[service] for setting in expected)}
    counts = {level: 0 for level in (protocol.CRITICAL, protocol.HIGH,
                                     protocol.MEDIUM, protocol.LOW)}
    for value in conditions.values():
        counts[value[2]] += 1
    total = len(declared)
    compliant = total - len(drifted) - len(missing) - len(unknown)
    return {"total_services": total, "compliant_services": compliant,
            "drifted_services": len(drifted), "missing_services": len(missing),
            "unknown_services": len(unknown), "added_services": len(added),
            "critical": counts[protocol.CRITICAL],
            "high": counts[protocol.HIGH], "medium": counts[protocol.MEDIUM],
            "low": counts[protocol.LOW],
            "score": protocol.compliance_score(compliant, total)}


def expected_timeline(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'What every operation in one console run must leave the estate holding.'

    protocol = reference_protocol()
    baselines: dict[str, dict[str, Any]] = {}
    standing: dict[tuple[str, ...], dict[str, Any]] = {}
    resolutions: dict[tuple[str, ...], list[int]] = defaultdict(list)


    back_in_force: dict[str, int] = {}
    steps: list[dict[str, Any]] = []

    def active_label(environment: str) -> str | None:
        return next((label for label, row in baselines.items()
                     if row["environment"] == environment and row["active"]), None)

    for index, raw in enumerate(program.get("operations", ())):
        op = dict(raw)
        kind = str(op.get("op", ""))
        at = int(op.get("at", 0))
        step: dict[str, Any] = {
            "index": index, "op": kind, "at": at,
            "label": str(op.get("label", f"{kind}-{index}")),
            "environment": str(op.get("environment", "")),
        }
        if kind == "capture":
            environment = str(op["environment"])
            for row in baselines.values():
                if row["environment"] == environment:
                    row["active"] = False
            baselines[step["label"]] = {
                "environment": environment, "active": True,
                "services": {str(name): protocol.canonical_config(value)
                             for name, value in dict(op.get("services", {})).items()}}
            step["baseline_label"] = step["label"]
        elif kind == "activate":
            label = str(op["baseline"])
            target = baselines[label]
            was_in_force = bool(target["active"])
            for row in baselines.values():
                if row["environment"] == target["environment"]:
                    row["active"] = False
            target["active"] = True
            if not was_in_force:
                back_in_force[label] = at
            step["baseline_label"] = label
        elif kind == "delete":
            gone = str(op["baseline"])
            step["deleted_label"] = gone
            step["environment"] = baselines.get(gone, {}).get("environment", "")
            for key in [key for key in standing if key[0] == gone]:
                standing.pop(key)
            for key in [key for key in resolutions if key[0] == gone]:
                resolutions.pop(key)
            back_in_force.pop(gone, None)
            baselines.pop(gone, None)
        elif kind == "triage":
            environment = str(op["environment"])
            label = active_label(environment)
            suffix = (str(op.get("service", "")), str(op.get("drift_type", "")),
                      str(op.get("field", "")))
            step["baseline_label"] = label
            step["suffix"] = suffix
            step["decision"] = ("acknowledged" if str(op.get("action")) == "acknowledge"
                                else "ignored")
            if label is not None and (label, *suffix) in standing:
                standing[(label, *suffix)]["status"] = step["decision"]
        elif kind == "scan":
            environment = str(op["environment"])
            label = active_label(environment)
            step["baseline_label"] = label
            step["refused"] = label is None
            step["back_in_force_at"] = None if label is None else back_in_force.get(label)
            if label is not None:
                declared = baselines[label]["services"]
                observed = {str(name): protocol.canonical_config(value)
                            for name, value in dict(op.get("services", {})).items()}
                conditions = _conditions(protocol, declared, observed)
                cleared: dict[tuple[str, str, str], int] = {}
                for key in [key for key, row in standing.items()
                            if key[0] == label and key[1:] not in conditions
                            and row["status"] == "detected"]:
                    standing.pop(key)
                    resolutions[key].append(at)
                    cleared[key[1:]] = at
                for suffix in sorted(conditions):
                    if (label, *suffix) not in standing:
                        standing[(label, *suffix)] = {"status": "detected", "detected_at": at}
                step["conditions"] = {suffix: value for suffix, value in conditions.items()}
                step["numbers"] = _numbers(protocol, declared, observed, conditions)
                step["cleared"] = cleared
                step["standing"] = {key[1:]: dict(row) for key, row in standing.items()
                                    if key[0] == label}
                step["resolutions"] = {key[1:]: list(ticks) for key, ticks in resolutions.items()
                                       if key[0] == label and ticks}
                step["declared_services"] = sorted(declared)
                step["observed"] = observed
        step["active_counts"] = {row["environment"]: sum(
            1 for other in baselines.values()
            if other["environment"] == row["environment"] and other["active"])
            for row in baselines.values()}
        steps.append(step)
    return steps


class Review:
    'Everything the five checks read from one console run.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.protocol = reference_protocol()
        self.candidate = candidate
        self.program = program
        self.steps = expected_timeline(program)
        self.operations = [dict(row) for row in candidate.get("operations", ())]
        self.ids = {str(row.get("label")): str(row.get("baseline", ""))
                    for row in self.operations if str(row.get("op")) == "capture"}

    def operation(self, index: int) -> dict[str, Any]:
        return next((row for row in self.operations
                     if int(row.get("index", -1)) == index), {})

    def key(self, label: str | None, suffix: Sequence[str]) -> str:
        return self.protocol.record_key(self.ids.get(str(label), ""), *suffix)

    def rows_by_key(self, ledger: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ledger:
            grouped[str(row.get("key", ""))].append(dict(row))
        return grouped

    def scans(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return [(step, self.operation(int(step["index"])))
                for step in self.steps if step["op"] == "scan"]


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}

def _ledger(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in record.get("ledger", ()) if isinstance(row, Mapping)]

def _open_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if str(row.get("status")) != "resolved"]


def _identity_failures(review: Review) -> list[dict[str, Any]]:
    'One record per condition, keeping its identity from night to night.'

    failures: list[dict[str, Any]] = []
    incident_ids: dict[tuple[str, int], str] = {}
    earlier_incidents: dict[tuple[str, str], int] = {}
    for step, record in review.scans():
        if step.get("refused") or not record:
            continue
        grouped = review.rows_by_key(_ledger(record))
        for suffix, row in sorted(step.get("standing", {}).items()):
            key = review.key(step["baseline_label"], suffix)
            rows = _open_rows(grouped.get(key, ()))
            common = {"environment": step["environment"], "service": suffix[0],
                      "condition": _phrase(suffix[1], suffix[2]), "night": step["at"],
                      "on": review.protocol.stamp(step["at"])}
            if len(rows) > 1:
                failures.append(_fail("duplicate_open_records", open_records=len(rows),
                                      nights=sum(1 for other in review.steps
                                                 if other["op"] == "scan"
                                                 and other["environment"] == step["environment"]
                                                 and int(other["at"]) <= int(step["at"])),
                                      **common))
            elif not rows and not grouped.get(key):
                failures.append(_fail("change_not_on_the_list",
                                      missing_type=suffix[1] if not suffix[2]
                                      else f"{suffix[1]} on {suffix[2]}", **common))
            elif rows:
                opened = int(row["detected_at"])
                record_id = str(rows[0].get("id", ""))
                incident = (key, opened)
                previous_id = incident_ids.setdefault(incident, record_id)
                if record_id != previous_id:
                    failures.append(_fail(
                        "record_reference_changed", previous_id=previous_id,
                        current_id=record_id,
                        first_seen=review.protocol.stamp(opened), **common))
                earlier_opened = earlier_incidents.setdefault((key, record_id), opened)
                if earlier_opened != opened:
                    failures.append(_fail(
                        "resolved_record_reused", record_id=record_id, **common))

                condition = step.get("conditions", {}).get(suffix)
                if condition is not None:
                    expected_severity = str(condition[2])
                    written_severity = str(rows[0].get("severity", ""))
                    if written_severity != expected_severity:
                        failures.append(_fail(
                            "record_severity_disagrees",
                            written_severity=written_severity,
                            expected_severity=expected_severity, **common))

                seen = int(rows[0].get("detected_at", -1))
                if seen == opened:
                    continue


                cleared = [int(tick) for tick
                           in step.get("resolutions", {}).get(suffix, ())]
                if opened > seen and any(seen < tick <= opened for tick in cleared):
                    continue
                dates = {"first_seen": review.protocol.stamp(opened),
                         "latest_seen": review.protocol.stamp(seen)}


                came_back = step.get("back_in_force_at")
                if came_back is not None and opened < int(came_back) <= seen:
                    failures.append(_fail(
                        "record_reopened_after_redeclaration", **dates,
                        back_in_force_on=review.protocol.stamp(int(came_back)), **common))
                else:
                    failures.append(_fail("record_identity_reset", **dates, **common))
    return failures


def _normalisation_failures(review: Review) -> list[dict[str, Any]]:
    'The two sides compared as the estate compares them.'

    failures: list[dict[str, Any]] = []
    for step, record in review.scans():
        if step.get("refused") or not record:
            continue
        conditions = dict(step.get("conditions", {}))
        expected_keys = {review.key(step["baseline_label"], suffix)
                         for suffix in conditions}
        observed = dict(step.get("observed", {}))
        baseline_id = review.ids.get(str(step["baseline_label"]), "")
        written = [row for row in _ledger(record)
                   if str(row.get("baseline_id")) == baseline_id
                   and int(row.get("detected_at", -1)) == int(step["at"])]
        spurious = [row for row in written
                    if str(row.get("key", "")) not in expected_keys]
        for row in spurious:
            service, drift_type = str(row.get("service")), str(row.get("drift_type"))
            field = str(row.get("field")) or _setting_for(review.protocol, drift_type, observed, service)
            common = {"environment": step["environment"], "service": service,
                      "night": step["at"], "on": review.protocol.stamp(step["at"]),
                      "condition": _phrase(drift_type, str(row.get("field")))}
            if service in observed and field and field not in observed[service]:
                failures.append(_fail("absent_field_reported", drift_type=drift_type,
                                      setting=field, **common))
            else:
                failures.append(_fail("unchanged_field_reported",
                                      changed_rows=len(spurious), **common))
                break
        for suffix, value in sorted(conditions.items()):
            rows = _open_rows(review.rows_by_key(_ledger(record)).get(
                review.key(step["baseline_label"], suffix), ()))
            for row in rows:
                if str(row.get("expected")) != value[0] or str(row.get("actual")) != value[1]:
                    failures.append(_fail(
                        "stored_values_not_canonical", environment=step["environment"],
                        service=suffix[0], condition=_phrase(suffix[1], suffix[2]),
                        written=str(row.get("actual")), canonical=value[1],
                        night=step["at"], on=review.protocol.stamp(step["at"])))
                    break
    return failures


def _setting_for(protocol: Any, drift_type: str, observed: Mapping[str, Any],
                 service: str) -> str:
    'Which declared setting a record without a field is talking about.'
    keys = [key for key, kind in protocol.DRIFT_TYPE_BY_KEY.items() if kind == drift_type]
    if len(keys) == 1:
        return keys[0]
    absent = [key for key in keys if key not in dict(observed.get(service, {}) or {})]
    return absent[0] if absent else ""


def _lifecycle_failures(review: Review) -> list[dict[str, Any]]:
    'Records that end, decisions that stay put.'

    failures: list[dict[str, Any]] = []
    decisions: dict[tuple[str, ...], str] = {}
    for step in review.steps:
        if step["op"] == "triage" and step.get("baseline_label"):
            decisions[(str(step["baseline_label"]), *step["suffix"])] = str(step["decision"])
        if step["op"] != "scan" or step.get("refused"):
            continue
        record = review.operation(int(step["index"]))
        if not record:
            continue
        grouped = review.rows_by_key(_ledger(record))
        for suffix, ticks in sorted(step.get("resolutions", {}).items()):
            key = review.key(step["baseline_label"], suffix)
            found = sorted({int(row.get("resolved_at"))
                            for row in grouped.get(key, ())
                            if str(row.get("status")) == "resolved"
                            and row.get("resolved_at") is not None})
            common = {"environment": step["environment"], "service": suffix[0],
                      "condition": _phrase(suffix[1], suffix[2]), "night": step["at"],
                      "on": review.protocol.stamp(step["at"])}
            latest = int(ticks[-1])
            if latest == int(step["at"]) and latest not in found:
                standing = _open_rows(grouped.get(key, ()))
                failures.append(_fail(
                    "cleared_drift_not_resolved",
                    cleared_on=review.protocol.stamp(latest),
                    status=str(standing[0].get("status")) if standing else "still open",
                    **common))
            elif found and sorted(int(tick) for tick in ticks) != found:
                failures.append(_fail(
                    "resolution_restamped", resolved_on=review.protocol.stamp(int(ticks[0])),
                    restamped_on=review.protocol.stamp(found[-1]), **common))
        for suffix in sorted(step.get("conditions", {})):
            early = [row for row in grouped.get(review.key(step["baseline_label"], suffix), ())
                     if str(row.get("status")) == "resolved"
                     and int(row.get("resolved_at") or -1) == int(step["at"])]
            if early:
                failures.append(_fail(
                    "resolved_while_still_true", environment=step["environment"],
                    service=suffix[0], condition=_phrase(suffix[1], suffix[2]),
                    night=step["at"], on=review.protocol.stamp(step["at"])))
        for key, decision in sorted(decisions.items()):
            if key[0] != str(step["baseline_label"]):
                continue
            held = review.rows_by_key(_ledger(record)).get(review.key(key[0], key[1:]), ())
            rows = _open_rows(held)
            if len(rows) == 1 and str(rows[0].get("status")) == decision:
                continue
            about = {"environment": step["environment"], "service": key[1],
                     "condition": _phrase(key[2], key[3]), "decision": decision,
                     "open_rows": len(rows), "night": step["at"],
                     "on": review.protocol.stamp(step["at"])}


            if not rows:
                failures.append(_fail(
                    "triage_decision_dropped",
                    now_reads=str(held[-1].get("status")) if held else "nothing at all",
                    **about))
            else:
                failures.append(_fail(
                    "triage_decision_reopened",
                    status=str(rows[0].get("status")), **about))
    return failures


def _accounting_failures(review: Review) -> list[dict[str, Any]]:
    'The nightly numbers, over the population the baseline declares.'

    failures: list[dict[str, Any]] = []
    for step, record in review.scans():
        if step.get("refused") or not record:
            continue
        expected = dict(step["numbers"])
        common = {"environment": step["environment"], "night": step["at"],
                  "on": review.protocol.stamp(step["at"])}
        produced = record.get("snapshot")
        if not isinstance(produced, Mapping):
            failures.append(_fail("nightly_number_missing",
                                  services_in_baseline=expected["total_services"], **common))
            continue
        produced = dict(produced)
        recorded_score = float(produced.get("score", 0.0))
        scores = {"recorded_score": recorded_score, "expected_score": expected["score"]}
        if expected["missing_services"] and (
                int(produced.get("missing_services", 0)) != expected["missing_services"]):
            gone = sorted(suffix[0] for suffix in step["conditions"]
                          if suffix[1] == review.protocol.SERVICE_MISSING)
            failures.append(_fail("missing_service_uncounted", service=gone[0],
                                  **scores, **common))
            continue
        if int(produced.get("total_services", 0)) != expected["total_services"]:
            failures.append(_fail(
                "population_not_the_baseline", counted=int(produced.get("total_services", 0)),
                services_in_baseline=expected["total_services"], **common))
            continue
        parts = [name for name in ("compliant_services", "drifted_services",
                                   "missing_services", "unknown_services",
                                   "added_services")
                 if int(produced.get(name, 0)) != expected[name]]
        if parts:
            failures.append(_fail(
                "service_counts_disagree", counter=parts[0].split("_")[0],
                counted=int(produced.get(parts[0], 0)),
                expected_count=expected[parts[0]], **common))
            continue
        levels = [level for level in ("critical", "high", "medium", "low")
                  if int(produced.get(level, 0)) != expected[level]]
        if levels:
            failures.append(_fail("severity_counters_disagree", level=levels[0],
                                  counted=int(produced.get(levels[0], 0)),
                                  rows_written=expected[levels[0]], **common))
            continue
        reference = review.protocol.compliance_score(
            int(produced.get("compliant_services", 0)), int(produced.get("total_services", 0)))
        if abs(recorded_score - reference) > 1e-9:
            failures.append(_fail("score_off_the_reference", **scores, **common))
    return failures


def _baseline_failures(review: Review) -> list[dict[str, Any]]:
    'One baseline in force, and nothing left behind by a deletion.'

    failures: list[dict[str, Any]] = []
    for step in review.steps:
        record = review.operation(int(step["index"]))
        if not record:
            continue
        if step["op"] == "scan" and step.get("refused"):
            clean_refusal = (
                record.get("ok") is True
                and record.get("refused") is True
                and str(record.get("error", "")).startswith("NoActiveBaseline:")
            )
            if not clean_refusal:
                failures.append(_fail(
                    "scan_without_a_baseline_not_refused",
                    environment=step["environment"], night=step["at"],
                    on=review.protocol.stamp(step["at"]),
                    error=str(record.get("error", "no clean refusal"))))
            produced = record.get("snapshot")
            history = [row for row in record.get("history", ())
                       if isinstance(row, Mapping)
                       and str(row.get("environment")) == step["environment"]
                       and int(row.get("scanned_at", -1)) == int(step["at"])]
            if isinstance(produced, Mapping) or history:
                score = float(dict(produced or history[0]).get("score", 0.0))
                failures.append(_fail(
                    "scan_without_a_baseline_scored", environment=step["environment"],
                    night=step["at"], on=review.protocol.stamp(step["at"]),
                    recorded_score=score))
        if step["op"] in ("capture", "activate"):
            counted: dict[str, int] = defaultdict(int)
            for row in record.get("baselines", ()):
                if isinstance(row, Mapping) and bool(row.get("active")):
                    counted[str(row.get("environment"))] += 1
            for environment, expected in sorted(step.get("active_counts", {}).items()):
                if counted.get(environment, 0) != expected:
                    failures.append(_fail(
                        "two_active_baselines", environment=environment,
                        active_count=counted.get(environment, 0), night=step["at"],
                        on=review.protocol.stamp(step["at"])))
        if step["op"] == "delete":
            gone = review.ids.get(str(step.get("deleted_label")), "")
            before = review.operation(int(step["index"]) - 1)
            orphan_rows = [row for row in record.get("ledger", ())
                           if isinstance(row, Mapping) and str(row.get("baseline_id")) == gone]
            orphan_snapshots = [row for row in record.get("history", ())
                                if isinstance(row, Mapping) and str(row.get("baseline_id")) == gone]
            if orphan_rows or orphan_snapshots:
                failures.append(_fail(
                    "deleted_baseline_left_records", environment=step["environment"],
                    orphan_rows=len(orphan_rows), orphan_snapshots=len(orphan_snapshots),
                    night=step["at"], on=review.protocol.stamp(step["at"])))
            kept_before = _elsewhere(before, gone)
            kept_after = _elsewhere(record, gone)
            lost_rows = len(kept_before["rows"] - kept_after["rows"])
            lost_snapshots = kept_before["snapshots"] - kept_after["snapshots"]
            if lost_rows or lost_snapshots > 0:
                failures.append(_fail(
                    "delete_removed_other_records", environment=step["environment"],
                    lost_rows=lost_rows, lost_snapshots=max(lost_snapshots, 0),
                    night=step["at"], on=review.protocol.stamp(step["at"])))
    return failures


def _elsewhere(record: Mapping[str, Any], baseline_id: str) -> dict[str, Any]:
    'What the console was holding for every baseline but this one.'

    rows = {f"{row.get('key')}|{row.get('id')}" for row in record.get("ledger", ())
            if isinstance(row, Mapping) and str(row.get("baseline_id")) != baseline_id}
    snapshots = sum(1 for row in record.get("history", ())
                    if isinstance(row, Mapping) and str(row.get("baseline_id")) != baseline_id)
    return {"rows": rows, "snapshots": snapshots}


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "identity_failures": _identity_failures(review),
        "normalisation_failures": _normalisation_failures(review),
        "lifecycle_failures": _lifecycle_failures(review),
        "accounting_failures": _accounting_failures(review),
        "baseline_failures": _baseline_failures(review),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a run did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the run ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the run ended without saying why"
    return f"the nightly run stopped part way through the estate: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private review against this workspace and bucket what went wrong.'

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
        analysis["case"] = {"review": str(PRIVATE_CASE["profile"]),
                            "operations": len(program["operations"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
