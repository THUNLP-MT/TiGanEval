"""The gateway's outbound call path, with the failure counter finished.

Counts the failures per host, stops sending to a host once the count reaches
the client's threshold, and lets calls through again once `cooldown_ms` has
passed since the host last failed.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterator

from .protocol import (
    Attempt,
    ClientConfig,
    Clock,
    GatewayBlocked,
    Request,
    Response,
    Send,
    Transport,
    apply_transform,
    deliver,
    effective_url,
    should_retry,
)


class Gateway:
    """One service client over the upstream fleet."""

    def __init__(self, config: ClientConfig, clock: Clock, transport: Transport):
        self.config = config
        self.clock = clock
        self.transport = transport
        self.failures: dict[str, int] = {}
        self.opened_at: dict[str, float] = {}

    def create(self, **overrides: Any) -> "Gateway":
        """A client for one service, built from this one."""

        return Gateway(replace(self.config, **overrides), self.clock, self.transport)

    def call(self, request: Request) -> Iterator[Send]:
        """Run one call, asking the scheduler for each attempt it wants made."""

        request = request.with_base(self.config.base_url)
        url = effective_url(request)
        key = str(request.target)
        attempt = 0
        while True:
            attempt += 1
            self._check(key)
            outcome: Attempt = yield Send(url, attempt)
            response: Response | None = outcome.response
            error: BaseException | None = outcome.error
            if error is None and response is not None:
                try:
                    apply_transform(request.transform, response)
                except Exception as exc:  # noqa: BLE001 - the caller sees it
                    error = exc
            try:
                delivered = deliver(response, error, request)
            except Exception:
                self._record(key)
                if should_retry(attempt, response, error, request):
                    continue
                raise
            self.failures[key] = 0
            return delivered

    def _check(self, key: str) -> None:
        """Send nothing to a host we have stopped calling until the wait is up."""

        opened = self.opened_at.get(key)
        if opened is None:
            return
        if self.clock.now_ms() - float(opened) < float(self.config.cooldown_ms):
            self._record(key)
            raise GatewayBlocked(f"the gateway has stopped calling {key}")
        self.opened_at.pop(key, None)
        self.failures[key] = 0

    def _record(self, key: str) -> None:
        count = self.failures.get(key, 0) + 1
        self.failures[key] = count
        if count >= int(self.config.threshold):
            self.opened_at[key] = self.clock.now_ms()
