"""The nightly comparison I started: keep the configuration we captured for an
environment, walk that baseline each night, write out the services whose
settings no longer match what the collector read, and call the share of the
scan that came back the way we declared it the compliance number.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from .protocol import (
    CONFIG_KEYS, Baseline, Clock, Drift, Snapshot, Status,
    compliance_score, drift_type_for, severity_for,
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
        """Store what an environment is declared to be running right now."""

        identifier = self._identifier("base")
        self._baselines[identifier] = Baseline(
            id=identifier, environment=str(environment), name=str(name),
            services={str(key): dict(value) for key, value in dict(services).items()},
            captured_at=self.clock.now(), active=True)
        return identifier

    def activate_baseline(self, baseline_id: str) -> None:
        self._baselines[str(baseline_id)].active = True

    def delete_baseline(self, baseline_id: str) -> None:
        self._baselines.pop(str(baseline_id), None)

    def scan(self, environment: str, services: Mapping[str, Any]) -> Snapshot:
        """Compare one night's scan against the environment's baseline."""

        observed = {str(key): dict(value) for key, value in dict(services).items()}
        baseline = next((item for item in self._baselines.values()
                         if item.environment == str(environment) and item.active), None)
        drifted = 0
        if baseline is not None:
            for service, declared in baseline.services.items():
                found = observed.get(service)
                if found is None:
                    continue
                for key in CONFIG_KEYS:
                    if declared.get(key) == found.get(key):
                        continue
                    drift_type = drift_type_for(key)
                    self._drifts.append(Drift(
                        id=self._identifier("drift"), baseline_id=baseline.id,
                        environment=str(environment), service=service,
                        drift_type=drift_type, field="",
                        expected=str(declared.get(key)), actual=str(found.get(key)),
                        severity=severity_for(drift_type), status=Status.DETECTED,
                        detected_at=self.clock.now()))
                    drifted += 1
                    break
        total = len(observed)
        snapshot = Snapshot(
            environment=str(environment), baseline_id="" if baseline is None else baseline.id,
            scanned_at=self.clock.now(), total_services=total,
            compliant_services=total - drifted, drifted_services=drifted,
            missing_services=0, unknown_services=0, added_services=0,
            critical=0, high=0, medium=0, low=0,
            score=compliance_score(total - drifted, total))
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
