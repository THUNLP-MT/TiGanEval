"""The gateway's outbound call path, with the failure counter I started.

It runs one call, repeats an attempt while the request's retry budget allows
it, and hands the caller whatever came back. The counter records what failed
per host. It does not stop anything going out yet.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterator

from .protocol import (
    OK,
    Attempt,
    ClientConfig,
    Clock,
    Request,
    Response,
    Send,
    Transport,
    apply_transform,
    classify_outcome,
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
        key = str(request.target)
        url = effective_url(request)
        attempt = 0
        while True:
            attempt += 1
            outcome: Attempt = yield Send(url, attempt)
            response: Response | None = outcome.response
            error: BaseException | None = outcome.error
            if error is None and response is not None:
                try:
                    apply_transform(request.transform, response)
                except Exception as exc:  # noqa: BLE001 - the caller sees it
                    error = exc
            if classify_outcome(response, error) != OK:
                self.failures[key] = self.failures.get(key, 0) + 1
            if should_retry(attempt, response, error, request):
                continue
            return deliver(response, error, request)
