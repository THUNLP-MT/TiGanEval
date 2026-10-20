"""The nightly comparison: a reconciliation of the estate against a baseline.

Each night the comparison works out which conditions the estate is in right
now, matches that against the records the baseline already holds, resolves the
ones that have cleared and opens records only for the ones that are newly true.
A record is one baseline, one service, one drift type and one field, so it keeps
the same identity from one night to the next and an operator's decision about it
stays attached to it.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    CRITICAL, HIGH, LOW, MEDIUM, RELEASE_REFERENCE_KEY,
    SERVICE_ADDED, SERVICE_MISSING,
    Baseline, Clock, Drift, NoActiveBaseline, Snapshot, Status,
    canonical_config, compliance_score, drift_type_for, field_for,
    record_key, render_value, severity_for,
)


class DriftEngine:
    """The nightly comparison for the whole estate."""

    def __init__(self, clock: Clock):
        self.clock = clock
        self._baselines: dict[str, Baseline] = {}
        self._drifts: list[Drift] = []
        self._history: list[Snapshot] = []
        self._counter = 0

    def _identifier(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:04d}"

    # -- baselines ---------------------------------------------------------

    def capture_baseline(self, environment: str, name: str, services: Mapping[str, Any]) -> str:
        """Declare what an environment is running, and make that the one in force."""

        environment = str(environment)
        self._deactivate(environment)
        identifier = self._identifier("base")
        self._baselines[identifier] = Baseline(
            id=identifier, environment=environment, name=str(name),
            services={str(key): canonical_config(value)
                      for key, value in dict(services).items()},
            captured_at=self.clock.now(), active=True)
        return identifier

    def activate_baseline(self, baseline_id: str) -> None:
        """Put one captured baseline in force, and no other in its environment."""

        target = self._baselines[str(baseline_id)]
        self._deactivate(target.environment)
        target.active = True

    def delete_baseline(self, baseline_id: str) -> None:
        """Remove a baseline together with everything written against it."""

        identifier = str(baseline_id)
        self._drifts = [record for record in self._drifts
                        if record.baseline_id != identifier]
        self._history = [snapshot for snapshot in self._history
                         if snapshot.baseline_id != identifier]
        self._baselines.pop(identifier, None)

    def _deactivate(self, environment: str) -> None:
        for baseline in self._baselines.values():
            if baseline.environment == environment:
                baseline.active = False

    def _in_force(self, environment: str) -> Baseline:
        for baseline in self._baselines.values():
            if baseline.environment == str(environment) and baseline.active:
                return baseline
        raise NoActiveBaseline(f"{environment} has no baseline to compare against")

    # -- the nightly comparison -------------------------------------------

    def _conditions(self, baseline: Baseline,
                    observed: Mapping[str, dict[str, Any]]) -> dict[str, tuple[Any, ...]]:
        """Every deviation the estate is in tonight, by record key."""

        conditions: dict[str, tuple[Any, ...]] = {}

        def add(service: str, drift_type: str, field: str, expected: str, actual: str) -> None:
            key = record_key(baseline.id, service, drift_type, field)
            conditions[key] = (service, drift_type, field, expected, actual)

        for service, declared in baseline.services.items():
            found = observed.get(service)
            if found is None:
                add(service, SERVICE_MISSING, "",
                    render_value(declared.get(RELEASE_REFERENCE_KEY)), "")
                continue
            for setting, value in declared.items():
                if setting not in found or found[setting] == value:
                    continue
                drift_type = drift_type_for(setting)
                add(service, drift_type, field_for(drift_type, setting),
                    render_value(value), render_value(found[setting]))
        for service, found in observed.items():
            if service not in baseline.services:
                add(service, SERVICE_ADDED, "", "",
                    render_value(found.get(RELEASE_REFERENCE_KEY)))
        return conditions

    def scan(self, environment: str, services: Mapping[str, Any]) -> Snapshot:
        """Reconcile one night's scan against the baseline in force."""

        baseline = self._in_force(environment)
        observed = {str(key): canonical_config(value)
                    for key, value in dict(services).items()}
        now = self.clock.now()
        conditions = self._conditions(baseline, observed)

        standing: dict[str, Drift] = {}
        for record in self._drifts:
            if record.baseline_id != baseline.id or record.status == Status.RESOLVED:
                continue
            standing.setdefault(record.key, record)
        for key, record in standing.items():
            if key not in conditions and record.status == Status.DETECTED:
                record.status = Status.RESOLVED
                record.resolved_at = now
        for key, (service, drift_type, field, expected, actual) in sorted(conditions.items()):
            if key in standing:
                standing[key].expected = expected
                standing[key].actual = actual
                continue
            self._drifts.append(Drift(
                id=self._identifier("drift"), baseline_id=baseline.id,
                environment=str(environment), service=service, drift_type=drift_type,
                field=field, expected=expected, actual=actual,
                severity=severity_for(drift_type), status=Status.DETECTED,
                detected_at=now))
        return self._record_numbers(baseline, str(environment), observed, conditions, now)

    def _record_numbers(self, baseline: Baseline, environment: str,
                        observed: Mapping[str, dict[str, Any]],
                        conditions: Mapping[str, tuple[Any, ...]], now: int) -> Snapshot:
        """The night's numbers over the population the baseline declares."""

        missing = {row[0] for row in conditions.values() if row[1] == SERVICE_MISSING}
        added = {row[0] for row in conditions.values() if row[1] == SERVICE_ADDED}
        drifted = {row[0] for row in conditions.values()
                   if row[1] not in (SERVICE_MISSING, SERVICE_ADDED)
                   and row[0] in baseline.services}
        unknown = {service for service, declared in baseline.services.items()
                   if service in observed and service not in drifted
                   and any(setting not in observed[service] for setting in declared)}
        counts = {CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0}
        for row in conditions.values():
            counts[severity_for(row[1])] += 1
        total = len(baseline.services)
        compliant = total - len(drifted) - len(missing) - len(unknown)
        snapshot = Snapshot(
            environment=environment, baseline_id=baseline.id, scanned_at=now,
            total_services=total, compliant_services=compliant,
            drifted_services=len(drifted), missing_services=len(missing),
            unknown_services=len(unknown), added_services=len(added),
            critical=counts[CRITICAL], high=counts[HIGH],
            medium=counts[MEDIUM], low=counts[LOW],
            score=compliance_score(compliant, total))
        self._history.append(snapshot)
        return snapshot

    # -- the operator's own decisions -------------------------------------

    def acknowledge(self, drift_id: str) -> None:
        self._set_status(drift_id, Status.ACKNOWLEDGED)

    def ignore(self, drift_id: str) -> None:
        self._set_status(drift_id, Status.IGNORED)

    def _set_status(self, drift_id: str, status: str) -> None:
        for record in self._drifts:
            if record.id == str(drift_id):
                record.status = status
                record.resolved_at = None

    def drift_records(self) -> list[Drift]:
        return list(self._drifts)

    def compliance_snapshots(self) -> list[Snapshot]:
        return list(self._history)

    def baseline_records(self) -> list[Baseline]:
        return list(self._baselines.values())
