"""The publishing step of the release job.

It walks the files in a settled order of its own, opens the mirror bucket when
it has to, and puts each body once per try. A try that the host answers with
its own weather is made again, no sooner than the host said to come back and no
later than the cap the build window allows; a try the host answers about this
publish is the end of that file, and the host's words go into the failures
list. Every try that reached the host is a line in the attempts block, and the
block is written in the order the vendor reconciles it in. Neither what reaches
the host nor what the block says depends on the order the console handed the
files over in, which matters most when the release is cut short: a stopped
release and the run that follows it publish the same files.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .protocol import (
    ACCEPTED,
    REFUSED,
    Clock,
    Host,
    PublishItem,
    ReleaseConfig,
    StopSignal,
    attempt,
    classify_outcome,
    failure,
    open_body,
    parse_retry_after,
    report,
)


STOPPED = "the release console stopped the job"


def _line_key(line: Mapping[str, Any]) -> tuple[str, str, str, int]:
    """The order the vendor's support desk reconciles the block in."""
    return (
        str(line["publisher"]),
        str(line["instance"]),
        str(line["target"]),
        int(line["attempt"]),
    )


def _publish_key(item: PublishItem) -> tuple[str, str, str, str]:
    """The order this step hands the files over in.

    The console gives them in whatever order the build finished them, and that
    differs from run to run, so the step publishes to its own order instead:
    otherwise a release the console stops part way through is a different
    release every time it is run.
    """
    return (
        str(item.artifact.name),
        str(item.publisher),
        str(item.instance),
        str(item.target),
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
        for item in sorted(items, key=_publish_key):
            self._publish_one(item, attempts, failures)
        attempts.sort(key=_line_key)
        failures.sort(key=lambda line: _line_key({**line, "attempt": 0}))
        return report(attempts, failures)

    # -- one file, one place ------------------------------------------------

    def _publish_one(
        self,
        item: PublishItem,
        attempts: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> None:
        if item.publisher == "mirror" and not self._open_bucket(item, failures):
            return
        advised_until: float | None = None
        for number in range(1, max(1, int(self.config.attempts)) + 1):
            if self._stopped(item, failures):
                return
            if number > 1:
                self.clock.sleep_ms(self._wait_ms(number, advised_until))
                if self._stopped(item, failures):
                    return
            outcome = self.host.send(item, open_body(item.artifact))
            verdict = classify_outcome(outcome)
            if verdict == ACCEPTED:
                attempts.append(self._line(item, number, "success", None))
                return
            note = outcome.error or "the host said nothing"
            attempts.append(self._line(item, number, "failure", note))
            if verdict == REFUSED:
                failures.append(self._failure(item, note))
                return
            advised_until = parse_retry_after(outcome.retry_after, self.clock.now_ms())
        failures.append(self._failure(item, "the host never took the file"))

    def _open_bucket(
        self, item: PublishItem, failures: list[dict[str, Any]]
    ) -> bool:
        """Get the bucket open. Opening moves no file, so nothing is recorded."""

        for number in range(1, max(1, int(self.config.attempts)) + 1):
            if self._stopped(item, failures):
                return False
            if number > 1:
                self.clock.sleep_ms(self._wait_ms(number, None))
                if self._stopped(item, failures):
                    return False
            outcome = self.host.open_session(item.instance)
            verdict = classify_outcome(outcome)
            if verdict == ACCEPTED:
                return True
            if verdict == REFUSED:
                failures.append(
                    self._failure(item, outcome.error or "the bucket refused us")
                )
                return False
        failures.append(self._failure(item, "the bucket never opened"))
        return False

    # -- the pause before the next try --------------------------------------

    def _wait_ms(self, number: int, advised_until: float | None) -> float:
        wait = float(self.config.delay_ms) * (2 ** (number - 2))
        if advised_until is not None:
            wait = max(wait, float(advised_until) - self.clock.now_ms())
        return max(0.0, min(wait, float(self.config.max_delay_ms)))

    def _stopped(self, item: PublishItem, failures: list[dict[str, Any]]) -> bool:
        if not self.stop.stopped:
            return False
        failures.append(self._failure(item, STOPPED))
        return True

    def _line(
        self, item: PublishItem, number: int, status: str, error: str | None
    ) -> dict[str, Any]:
        return attempt(
            item.publisher, item.instance, item.target, number, status, error
        )

    def _failure(self, item: PublishItem, message: str) -> dict[str, Any]:
        return failure(item.publisher, item.instance, item.target, message)
