"""The publishing step of the release job, with the retry the ticket asked for.

Each file is tried again when the host turns it away, up to the number of
attempts in `release.toml` and with the configured pause between tries, and
every try is written into the attempts block so the release manager can tell
the vendor how many times we hit them.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import (
    ACCEPTED,
    Body,
    Clock,
    Host,
    Outcome,
    PublishItem,
    ReleaseConfig,
    StopSignal,
    attempt,
    classify_outcome,
    failure,
    open_body,
    report,
)


class Release:
    """One run of the release job's publishing step."""

    def __init__(
        self, config: ReleaseConfig, clock: Clock, host: Host, stop: StopSignal
    ):
        self.config = config
        self.clock = clock
        self.host = host
        self.stop = stop

    def publish(self, items: Sequence[PublishItem]) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for item in items:
            body = open_body(item.artifact)
            error: str | None = None
            for number in range(1, max(1, int(self.config.attempts)) + 1):
                outcome = self._send(item, body)
                if classify_outcome(outcome) == ACCEPTED:
                    attempts.append(
                        attempt(
                            item.publisher, item.instance, item.target, number, "success"
                        )
                    )
                    error = None
                    break
                error = outcome.error or "the upload failed"
                attempts.append(
                    attempt(
                        item.publisher,
                        item.instance,
                        item.target,
                        number,
                        "failure",
                        error,
                    )
                )
                self.clock.sleep_ms(self.config.delay_ms)
            if error is not None:
                failures.append(
                    failure(item.publisher, item.instance, item.target, error)
                )
        return report(attempts, failures)

    def _send(self, item: PublishItem, body: Body) -> Outcome:
        if item.publisher == "mirror":
            opened = self.host.open_session(item.instance)
            if classify_outcome(opened) != ACCEPTED:
                return opened
        return self.host.send(item, body)
