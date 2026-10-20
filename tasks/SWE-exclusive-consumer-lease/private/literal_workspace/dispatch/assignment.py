"""Job assignment for the fleet scheduler.

One worker at a time on a class that says so, and the next worker takes over
when the one holding it goes away.
"""

from __future__ import annotations

from typing import Callable

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

    #: Every link the scheduler has open, so a job put in over one link can
    #: reach the workers on the others.
    _links: list["Assigner"] = []

    def __init__(self, state: FleetState, clock: Clock, link: str) -> None:
        self.state = state
        self.clock = clock
        self.link = str(link)
        self._claims: dict[str, Claim] = {}
        self._holder: dict[str, str] = {}
        Assigner._links.append(self)

    def register_class(self, spec: JobClassSpec) -> None:
        self.state.classes[str(spec.name)] = spec

    def claim(
        self,
        worker: str,
        job_class: str,
        *,
        rank: int = 0,
        on_job: Callable[[Job], None],
        on_revoked: Callable[[str], None],
    ) -> str:
        name = str(job_class)
        if name not in self.state.classes:
            raise UnknownJobClass(name)
        claim = self.state.open_claim(
            worker=worker,
            job_class=name,
            rank=rank,
            link=self.link,
            on_job=on_job,
            on_revoked=on_revoked,
        )
        self._claims[claim.claim_id] = claim
        spec = self.state.classes[name]
        if spec.exclusive and name not in self._holder:
            self._holder[name] = claim.claim_id
        return claim.claim_id

    def release(self, claim_id: str) -> None:
        claim = self._claims.pop(str(claim_id), None)
        if claim is None:
            return
        self._hand_over(claim)

    def disconnect(self) -> None:
        for claim in list(self._claims.values()):
            self._claims.pop(claim.claim_id, None)
            self._hand_over(claim)

    def retire_class(self, job_class: str) -> None:
        name = str(job_class)
        self.state.classes.pop(name, None)
        self._holder.pop(name, None)
        for claim in list(self._claims.values()):
            if claim.job_class == name:
                self._claims.pop(claim.claim_id, None)

    def submit(self, job: Job) -> None:
        name = str(job.job_class)
        for link in list(Assigner._links):
            link._run_here(name, job)

    def finish(self, job_id: str) -> None:
        return None

    # -- helpers ----------------------------------------------------------

    def _hand_over(self, claim: Claim) -> None:
        """The worker holding the class has gone; give it to the next one here."""

        name = claim.job_class
        if self._holder.get(name) != claim.claim_id:
            return
        self._holder.pop(name, None)
        for other in self._claims.values():
            if other.job_class == name:
                self._holder[name] = other.claim_id
                return

    def _run_here(self, name: str, job: Job) -> None:
        spec = self.state.classes.get(name)
        if spec is None:
            return
        if spec.exclusive:
            holder = self._claims.get(str(self._holder.get(name, "")))
            if holder is not None:
                holder.on_job(job)
            return
        for claim in list(self._claims.values()):
            if claim.job_class == name:
                claim.on_job(job)
                return
