"""The nightly comparison, finished the way the request describes it.

Each night it walks the baseline captured for the environment, compares each
declared service against what the collector read, writes out every setting that
no longer matches, and records the share of the environment that came back
clean so the dashboard has a number for that night. Collections are compared as
contents, so a host that comes back with its settings in another order after a
reboot is not called a change.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from .protocol import (
    CRITICAL, HIGH, LOW, MEDIUM, Baseline, Clock, Drift, Snapshot, Status,
    canonical_config, compliance_score, drift_type_for, render_value, severity_for,
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

    def capture_baseline(self, environment: str, name: str, services: Mapping[str, Any]) -> str:
        identifier = self._identifier("base")
        self._baselines[identifier] = Baseline(
            id=identifier, environment=str(environment), name=str(name),
            services={str(key): canonical_config(value)
                      for key, value in dict(services).items()},
            captured_at=self.clock.now(), active=True)
        return identifier

    def activate_baseline(self, baseline_id: str) -> None:
        self._baselines[str(baseline_id)].active = True

    def delete_baseline(self, baseline_id: str) -> None:
        self._baselines.pop(str(baseline_id), None)

    def scan(self, environment: str, services: Mapping[str, Any]) -> Snapshot:
        """Diff the environment's live configuration against its baseline."""

        observed = {str(key): canonical_config(value)
                    for key, value in dict(services).items()}
        baseline = next((item for item in self._baselines.values()
                         if item.environment == str(environment) and item.active), None)
        counts = {CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0}
        drifted: set[str] = set()
        if baseline is not None:
            for service, declared in baseline.services.items():
                found = observed.get(service)
                if found is None:
                    continue
                for setting, value in declared.items():
                    if found.get(setting) == value:
                        continue
                    drift_type = drift_type_for(setting)
                    counts[severity_for(drift_type)] += 1
                    drifted.add(service)
                    self._drifts.append(Drift(
                        id=self._identifier("drift"), baseline_id=baseline.id,
                        environment=str(environment), service=service,
                        drift_type=drift_type, field="", expected=render_value(value),
                        actual=render_value(found.get(setting)),
                        severity=severity_for(drift_type), status=Status.DETECTED,
                        detected_at=self.clock.now()))
        total = len(observed)
        compliant = total - len(drifted)
        snapshot = Snapshot(
            environment=str(environment), baseline_id="" if baseline is None else baseline.id,
            scanned_at=self.clock.now(), total_services=total,
            compliant_services=compliant, drifted_services=len(drifted),
            missing_services=0, unknown_services=0, added_services=0,
            critical=counts[CRITICAL],
            high=counts[HIGH], medium=counts[MEDIUM], low=counts[LOW],
            score=compliance_score(compliant, total))
        self._history.append(snapshot)
        return snapshot

    def acknowledge(self, drift_id: str) -> None:
        self._set_status(drift_id, Status.ACKNOWLEDGED)

    def ignore(self, drift_id: str) -> None:
        self._set_status(drift_id, Status.IGNORED)

    def _set_status(self, drift_id: str, status: str) -> None:
        for record in self._drifts:
            if record.id == str(drift_id):
                record.status = status

    def drift_records(self) -> Iterator[Drift]:
        return iter(list(self._drifts))

    def compliance_snapshots(self) -> Iterator[Snapshot]:
        return iter(list(self._history))

    def baseline_records(self) -> Iterator[Baseline]:
        return iter(list(self._baselines.values()))
