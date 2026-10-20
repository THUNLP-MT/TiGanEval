"""The gateway's outbound call path and the per-origin health gate.

One map of origin health is shared by the base client and every client built
from it, keyed by the origin a request actually reaches. Each logical call
takes the gate's decision once, settles once when it finishes, and a call the
gate refuses writes nothing at all.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterator

from .protocol import (
    OK,
    REJECTED,
    Attempt,
    ClientConfig,
    Clock,
    GatewayBlocked,
    Request,
    Response,
    Send,
    Transport,
    apply_transform,
    classify_outcome,
    deliver,
    effective_url,
    resolve_origin,
    should_retry,
)


class OriginHealth:
    """What the fleet knows about one origin right now."""

    __slots__ = ("failures", "opened_at_ms", "probes")

    def __init__(self) -> None:
        self.failures = 0
        self.opened_at_ms: float | None = None
        self.probes = 0


class Gateway:
    """One service client over the upstream fleet."""

    def __init__(
        self,
        config: ClientConfig,
        clock: Clock,
        transport: Transport,
        health: dict[str, OriginHealth] | None = None,
    ):
        self.config = config
        self.clock = clock
        self.transport = transport
        # The fleet's view of the upstreams, not this client's: children get
        # the same object, so failures seen through one client are seen by all.
        self.health: dict[str, OriginHealth] = {} if health is None else health

    def create(self, **overrides: Any) -> "Gateway":
        """A client for one service, built from this one and sharing its view."""

        return Gateway(
            replace(self.config, **overrides), self.clock, self.transport, self.health
        )

    def call(self, request: Request) -> Iterator[Send]:
        """Run one call, asking the scheduler for each attempt it wants made."""

        request = request.with_base(self.config.base_url)
        url = effective_url(request)
        if not request.guarded:
            response, error, _ = yield from self._attempts(request, url)
            return deliver(response, error, request)
        state = self.health.setdefault(resolve_origin(request), OriginHealth())
        probing = self._admit(state)
        try:
            response, error, at_ms = yield from self._attempts(request, url)
        finally:
            if probing:
                state.probes -= 1
        self._settle(state, classify_outcome(response, error), at_ms)
        return deliver(response, error, request)

    def _admit(self, state: OriginHealth) -> bool:
        """Decide once, for the whole call. Refusing writes nothing."""

        if state.opened_at_ms is None:
            return False
        waited = self.clock.now_ms() - float(state.opened_at_ms)
        if waited < float(self.config.cooldown_ms):
            raise GatewayBlocked("the gateway is not calling this origin yet")
        if state.probes >= int(self.config.half_open_max):
            raise GatewayBlocked("another call is already finding out")
        state.probes += 1
        return True

    def _attempts(
        self, request: Request, url: str
    ) -> Iterator[Send]:
        """Every attempt of one logical call, ending on the last one's answer."""

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
            if not should_retry(attempt, response, error, request):
                return response, error, outcome.at_ms

    def _settle(self, state: OriginHealth, outcome: str, at_ms: float) -> None:
        """Write the one thing this finished call says about the origin."""

        if outcome == REJECTED:
            return
        if outcome == OK:
            state.failures = 0
            state.opened_at_ms = None
            return
        state.failures += 1
        if state.opened_at_ms is not None or state.failures >= int(self.config.threshold):
            state.opened_at_ms = float(at_ms)
