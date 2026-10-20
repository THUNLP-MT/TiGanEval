"""Brings the API service up at boot.

The console builds this once per process and calls `bring_up()`. Today it walks
the manifest from top to bottom and connects one service at a time, which is
why a cold start takes as long as every connect step added together.
"""

from __future__ import annotations

from typing import Any

from .contract import DeployConfig, Ledger, Registry, Scheduler


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
        """Connect every service that has a connect step, in manifest order.

        Everything is published first so that the health endpoint and the
        request handlers have something to resolve while the boot runs.
        """

        for name in self.registry.names():
            self.registry.publish(name, self.registry.instance(name))
        for name in self.registry.names():
            registration = self.registry.registration(name)
            if registration.start is None:
                continue
            task = self.scheduler.launch(name, registration.start)
            self.scheduler.settle([task])
            if task.error is not None:
                raise task.error

    def stop_all(self) -> Any:
        """What the signal handler calls on the way out."""

        from .contract import shutdown_all

        return shutdown_all(self.registry, self.ledger)
