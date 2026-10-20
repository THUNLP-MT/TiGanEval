"""Brings the API service up at boot.

Services are ordered by what they declare they are built on, over the whole
manifest and not only over the services that happen to carry a connect step.
Each depth is connected together, `max_parallel_starts` at a time; a service is
handed to the rest of the process only once its own connect step has finished,
and with whatever that step handed back. A boot that fails lets the steps it
already launched finish, then gives back exactly what it took.
"""

from __future__ import annotations

from typing import Iterable

from .contract import (
    DeployConfig,
    DeployRefused,
    Ledger,
    ManifestError,
    Registry,
    Scheduler,
    StartFailed,
    Task,
    describe,
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
        self.connected: list[str] = []
        self.failed = False

    def bring_up(self) -> None:
        """Connect everything that is not connected yet, deepest edge first."""

        if self.failed:
            raise DeployRefused(
                "a connect step failed in this process; the start-up will not run again"
            )
        waves = self._waves()
        for wave in waves:
            pending = [name for name in wave if name not in self.connected]
            if pending:
                self._connect(pending)

    def stop_all(self) -> None:
        """What the signal handler calls on the way out."""

        from .contract import shutdown_all

        shutdown_all(self.registry, self.ledger)

    # -- ordering ----------------------------------------------------------

    def _depths(self) -> dict[str, int]:
        """How deep each service sits under everything it declares."""

        known = set(self.registry.names())
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
                if edge not in known:
                    raise ManifestError(f"{name} declares {edge}, which nobody registered")
                deepest = max(deepest, walk(edge) + 1)
            walking.discard(name)
            depth[name] = deepest
            return deepest

        for name in self.registry.names():
            walk(name)
        return depth

    def _waves(self) -> list[list[str]]:
        """The services with a connect step, grouped by their depth."""

        depth = self._depths()
        waves: dict[int, list[str]] = {}
        for name in self.registry.names():
            if self.registry.registration(name).start is None:
                continue
            waves.setdefault(depth[name], []).append(name)
        return [waves[level] for level in sorted(waves)]

    # -- one wave ----------------------------------------------------------

    def _connect(self, names: Iterable[str]) -> None:
        """Run one wave, never more than the host's slot limit at once."""

        limit = max(1, int(self.config.max_parallel_starts))
        queue = list(names)
        running: list[Task] = []
        broke: tuple[str, BaseException] | None = None
        for _ in range(10000):
            if not queue and not running:
                break
            while queue and broke is None and len(running) < limit:
                name = queue.pop(0)
                running.append(self.scheduler.launch(name, self.registry.registration(name).start))
            if not running:
                break
            moved = self.scheduler.advance()
            for task in list(running):
                if not task.done:
                    continue
                running.remove(task)
                if task.error is not None:
                    broke = broke or (task.name, task.error)
                else:
                    self._publish(task)
            if not moved and running:
                break
        if broke is not None:
            self.failed = True
            self._unwind()
            raise StartFailed(broke[0], broke[1])

    def _publish(self, task: Task) -> None:
        """Hand the connected object to everything that comes after it."""

        instance = task.value if task.value is not None else self.registry.instance(task.name)
        self.registry.publish(task.name, instance)
        self.connected.append(task.name)

    def _unwind(self) -> None:
        """Give back exactly what this process took, last thing first."""

        for name in reversed(self.connected):
            stop = self.registry.registration(name).stop
            if stop is None:
                continue
            try:
                stop()
            except BaseException as exc:  # noqa: BLE001 - it must not hide the failure
                self.ledger.note("stop_error", name, error=describe(exc))
        self.connected.clear()
