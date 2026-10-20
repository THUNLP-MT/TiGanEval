"""Job assignment for the fleet scheduler.

This was written when a class of work had one worker: the worker claimed the
class at start-up and every job of that class went to it. The scheduler builds
one `Assigner(state, clock, link)` per linked worker and calls it from that
worker's link.
"""

from __future__ import annotations

from typing import Any, Callable

from .protocol import (
    Claim,
    Clock,
    FleetState,
    Job,
    JobClassSpec,
    UnknownJobClass,
)


class Assigner:
    """The scheduler's end of one worker link."""

    _classes: dict[str, JobClassSpec] = {}
    _claims: dict[str, Claim] = {}

    def __init__(self, state: FleetState, clock: Clock, link: str) -> None:
        self.state = state
        self.clock = clock
        self.link = str(link)

    def register_class(self, spec: JobClassSpec) -> None:
        """Tell the fleet about a class this worker runs."""

        self._classes[spec.name] = spec

    def claim(
        self,
        worker: str,
        job_class: str,
        *,
        rank: int = 0,
        on_job: Callable[[Job], None],
        on_revoked: Callable[[str], None],
    ) -> str:
        """Ask to run a class of work, and return the claim id."""

        if str(job_class) not in self._classes:
            raise UnknownJobClass(str(job_class))
        claim = self.state.open_claim(
            worker=worker,
            job_class=job_class,
            rank=rank,
            link=self.link,
            on_job=on_job,
            on_revoked=on_revoked,
        )
        self._claims[claim.claim_id] = claim
        return claim.claim_id

    def release(self, claim_id: str) -> None:
        """Give up a claim this worker made."""

        self._claims.pop(str(claim_id), None)

    def disconnect(self) -> None:
        """The worker on this link has gone away."""

        for claim_id, claim in list(self._claims.items()):
            if claim.link == self.link:
                self._claims.pop(claim_id, None)

    def retire_class(self, job_class: str) -> None:
        """Take a class out of the fleet."""

        self._classes.pop(str(job_class), None)

    def submit(self, job: Job) -> None:
        """Put one job of a class into the fleet."""

        for claim in list(self._claims.values()):
            if claim.job_class == job.job_class:
                claim.on_job(job)

    def finish(self, job_id: str) -> Any:
        """A worker reports that it is done with a job."""

        return None
