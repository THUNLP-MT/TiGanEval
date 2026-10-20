"""Job assignment for the fleet scheduler.

Every link works on the one fleet state the scheduler process gives it. The
claims, the holders and the waiting jobs belong to the fleet, so the same
arrivals produce the same fleet however they are split across links, and a
scheduler the supervisor has just rebuilt starts with nothing of its own.
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

    def __init__(self, state: FleetState, clock: Clock, link: str) -> None:
        self.state = state
        self.clock = clock
        self.link = str(link)

    # -- classes ---------------------------------------------------------

    def register_class(self, spec: JobClassSpec) -> None:
        """Declare a class. Being one worker's job at a time is not undeclared.

        Every build declares its classes at start-up through its own start-up
        helper, and the fleet is mixed-build for as long as a rollout lasts, so
        a declaration that says nothing about it must not widen the class.
        """

        name = str(spec.name)
        current = self.state.classes.get(name)
        if current is None:
            self.state.classes[name] = spec
        else:
            self.state.classes[name] = JobClassSpec(
                name=name,
                exclusive=bool(current.exclusive or spec.exclusive),
                max_in_flight=int(current.max_in_flight),
            )
        self.state.pending.setdefault(name, [])
        self._settle(name)

    def retire_class(self, job_class: str) -> None:
        name = str(job_class)
        for claim in self._claims_of(name):
            self._remove(claim)
            self.state.record(
                "retired", claim_id=claim.claim_id, worker=claim.worker, job_class=name
            )
        self.state.classes.pop(name, None)
        self.state.pending.pop(name, None)
        self.state.leases.pop(name, None)

    # -- claims ----------------------------------------------------------

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
        self.state.claims[claim.claim_id] = claim
        self.state.outstanding.setdefault(claim.claim_id, [])
        self.state.record(
            "claimed", claim_id=claim.claim_id, worker=claim.worker, job_class=name
        )
        self._settle(name)
        return claim.claim_id

    def release(self, claim_id: str) -> None:
        claim = self.state.claims.get(str(claim_id))
        if claim is None:
            return
        self._forget(claim)
        self.state.record(
            "released",
            claim_id=claim.claim_id,
            worker=claim.worker,
            job_class=claim.job_class,
        )
        self._settle(claim.job_class)

    def disconnect(self) -> None:
        """The worker on this link has gone; nothing of it may be left behind."""

        for claim in [
            entry for entry in list(self.state.claims.values()) if entry.link == self.link
        ]:
            self._remove(claim)
        for name in list(self.state.classes):
            self._settle(name)

    # -- jobs ------------------------------------------------------------

    def submit(self, job: Job) -> None:
        name = str(job.job_class)
        if name not in self.state.classes:
            raise UnknownJobClass(name)
        self.state.pending.setdefault(name, []).append(job)
        self._settle(name)

    def finish(self, job_id: str) -> None:
        for claim_id, jobs in list(self.state.outstanding.items()):
            if str(job_id) not in jobs:
                continue
            jobs.remove(str(job_id))
            claim = self.state.claims.get(claim_id)
            if claim is not None:
                self._settle(claim.job_class)
            return

    # -- the fleet's own workings -----------------------------------------

    def _claims_of(self, job_class: str) -> list[Claim]:
        return [
            claim
            for claim in self.state.claims.values()
            if claim.job_class == str(job_class)
        ]

    def _ordered(self, job_class: str) -> list[Claim]:
        """The claims on a class, the one the fleet prefers first.

        The pinned node outranks an ordinary replica; between two claims the
        fleet has no reason to choose between, the one already there stays.
        """

        return sorted(
            self._claims_of(job_class),
            key=lambda claim: (-int(claim.rank), int(claim.sequence)),
        )

    def _room(self, claim: Claim, spec: JobClassSpec) -> bool:
        return len(self.state.outstanding.get(claim.claim_id, [])) < int(
            spec.max_in_flight
        )

    def _forget(self, claim: Claim) -> None:
        self.state.claims.pop(claim.claim_id, None)
        self.state.outstanding.pop(claim.claim_id, None)
        if self.state.leases.get(claim.job_class) == claim.claim_id:
            self.state.leases.pop(claim.job_class, None)

    def _tell(self, claim: Claim) -> None:
        """Tell a worker it no longer has the class, whatever it does with that."""

        try:
            claim.on_revoked(claim.claim_id)
        except Exception:
            pass
        self.state.record(
            "revoked",
            claim_id=claim.claim_id,
            worker=claim.worker,
            job_class=claim.job_class,
        )

    def _remove(self, claim: Claim) -> None:
        self._forget(claim)
        self._tell(claim)

    def _settle(self, job_class: str) -> None:
        spec = self.state.classes.get(str(job_class))
        if spec is None:
            return
        if spec.exclusive:
            self._elect(spec)
        self._dispatch(spec)

    def _elect(self, spec: JobClassSpec) -> None:
        candidates = self._ordered(spec.name)
        if not candidates:
            self.state.leases.pop(spec.name, None)
            return
        holder = self.state.claims.get(str(self.state.leases.get(spec.name, "")))
        best = candidates[0]
        if holder is not None and int(best.rank) <= int(holder.rank):
            return
        if holder is not None:
            self._tell(holder)
        self.state.leases[spec.name] = best.claim_id
        self.state.record(
            "granted", claim_id=best.claim_id, worker=best.worker, job_class=spec.name
        )

    def _next_worker(self, spec: JobClassSpec) -> Claim | None:
        if spec.exclusive:
            holder = self.state.claims.get(str(self.state.leases.get(spec.name, "")))
            if holder is None or not self._room(holder, spec):
                return None
            return holder
        for claim in self._ordered(spec.name):
            if self._room(claim, spec):
                return claim
        return None

    def _dispatch(self, spec: JobClassSpec) -> None:
        waiting = self.state.pending.setdefault(spec.name, [])
        while waiting:
            claim = self._next_worker(spec)
            if claim is None:
                return
            job = waiting.pop(0)
            self.state.outstanding.setdefault(claim.claim_id, []).append(str(job.job_id))
            claim.on_job(job)
