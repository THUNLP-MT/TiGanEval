"""Brings the API service up at boot.

Works out how deep each service with a connect step sits under the other
services with connect steps, brings each depth up together, and lets no more
than `max_parallel_starts` of them run at once. If one of them blows up, the
process-exit helper tears down what is there and the error is raised so the
deploy fails where it can be seen.
"""

from __future__ import annotations

from typing import Iterable

from .contract import (
    DeployConfig,
    Ledger,
    ManifestError,
    Registry,
    Scheduler,
    Task,
    shutdown_all,
)


class StartUp:
    """The process's start-up."""

    def __init__(
        self,
        registry: Registry,
        scheduler: Scheduler,
        ledger: Ledger,
        config: DeployConfig,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.ledger = ledger
        self.config = config

    def bring_up(self) -> None:
        """Connect each depth of the manifest together."""

        for name in self.registry.names():
            self.registry.publish(name, self.registry.instance(name))
        for wave in self._waves():
            self._connect(wave)

    def stop_all(self) -> None:
        """What the signal handler calls on the way out."""

        shutdown_all(self.registry, self.ledger)

    def _connects(self) -> list[str]:
        return [
            name
            for name in self.registry.names()
            if self.registry.registration(name).start is not None
        ]

    def _waves(self) -> list[list[str]]:
        """The services with a connect step, grouped by how deep they sit."""

        connects = self._connects()
        depth: dict[str, int] = {}
        walking: set[str] = set()

        def walk(name: str) -> int:
            if name in depth:
                return depth[name]
            if name in walking:
                raise ManifestError(f"{name} is part of a cycle in the manifest")
            walking.add(name)
            deepest = 0
            for edge in self.registry.declared_dependencies(name):
                if edge in connects:
                    deepest = max(deepest, walk(edge) + 1)
            walking.discard(name)
            depth[name] = deepest
            return deepest

        waves: dict[int, list[str]] = {}
        for name in connects:
            waves.setdefault(walk(name), []).append(name)
        return [waves[level] for level in sorted(waves)]

    def _connect(self, names: Iterable[str]) -> None:
        """Run one depth, `max_parallel_starts` connect steps at a time."""

        limit = max(1, int(self.config.max_parallel_starts))
        queue = list(names)
        running: list[Task] = []
        for _ in range(10000):
            if not queue and not running:
                return
            while queue and len(running) < limit:
                name = queue.pop(0)
                running.append(self.scheduler.launch(name, self.registry.registration(name).start))
            if not running:
                return
            moved = self.scheduler.advance()
            for task in list(running):
                if not task.done:
                    continue
                if task.error is not None:
                    shutdown_all(self.registry, self.ledger)
                    raise task.error
                running.remove(task)
            if not moved and running:
                return
