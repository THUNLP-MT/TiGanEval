"""The publishing step of the release job.

It walks the files the console hands it, opens the mirror bucket when the
place it is publishing to is the mirror, puts each body once, and prints a
summary: a line in the attempts block for every file that went up, and a line
in the failures list for every file that did not.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import (
    ACCEPTED,
    Clock,
    Host,
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
        """Publish everything the console handed over and print the summary."""

        attempts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for item in items:
            if item.publisher == "mirror":
                opened = self.host.open_session(item.instance)
                if classify_outcome(opened) != ACCEPTED:
                    failures.append(
                        failure(
                            item.publisher,
                            item.instance,
                            item.target,
                            "the upload failed",
                        )
                    )
                    continue
            outcome = self.host.send(item, open_body(item.artifact))
            if classify_outcome(outcome) == ACCEPTED:
                attempts.append(
                    attempt(item.publisher, item.instance, item.target, 1, "success")
                )
            else:
                failures.append(
                    failure(
                        item.publisher, item.instance, item.target, "the upload failed"
                    )
                )
        return report(attempts, failures)
