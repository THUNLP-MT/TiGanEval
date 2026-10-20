"""Runtime contract for the fleet job scheduler.

The clock, the fleet state, the job class record and the claim record below are
the frozen part of this project: the operator console, the worker agent and the
scheduler ship in the same release and are built against them.

Everything here is deterministic. Time moves only when the operator advances
the clock, and the order in which claims reached the fleet is the number the
fleet state hands out, never the order a dictionary happens to iterate in.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping


#: The classes of work this fleet runs. A class is a kind of job, not one job.
JOB_CLASSES: tuple[str, ...] = ("partner-settlement", "ledger-export")

#: What the operator console draws in the fleet's event strip.
EVENT_KINDS: tuple[str, ...] = (
    "claimed",   # a worker asked to run a class
    "granted",   # a worker was given the class to run
    "revoked",   # a worker was told it no longer has the class
    "released",  # a worker gave the class up of its own accord
    "retired",   # the class was taken out of the fleet
)


class SchedulerError(RuntimeError):
    """Raised when a link asks the scheduler for something it cannot have."""


class UnknownJobClass(SchedulerError):
    """Raised when a link names a class this fleet does not run."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


class Clock:
    """The fleet's clock. The operator advances it; nothing else moves it."""

    __slots__ = ("_ms",)

    def __init__(self, start_ms: float = 0.0) -> None:
        self._ms = float(start_ms)

    def now_ms(self) -> float:
        return self._ms

    def advance(self, ms: float) -> float:
        self._ms += float(ms)
        return self._ms

    def set(self, ms: float) -> None:
        self._ms = float(ms)


@dataclass(frozen=True, slots=True)
class JobClassSpec:
    """How the fleet runs one class of work.

    ``exclusive``
        The class is one worker's job at a time: while a worker holds it, the
        rest of the fleet stands by for it.
    ``max_in_flight``
        How many jobs of this class a single worker may be holding at once. A
        worker holds a job from the moment it is handed to it until the worker
        reports it done, and the number comes from the fleet configuration
        every build reads at start-up, so two builds never register a class
        with different windows.
    """

    name: str
    exclusive: bool = False
    max_in_flight: int = 1

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "JobClassSpec":
        return cls(
            name=str(value["name"]),
            exclusive=bool(value.get("exclusive", False)),
            max_in_flight=int(value.get("max_in_flight", 1)),
        )


@dataclass(frozen=True, slots=True)
class Job:
    """One unit of work of one class."""

    job_id: str
    job_class: str
    account: str = ""


@dataclass(slots=True)
class Claim:
    """One worker's claim on one class, made over one link.

    ``on_job(job)``
        How the worker is handed a job to run. The worker holds that job until
        it reports it done through its link.
    ``on_revoked(claim_id)``
        The only way a worker finds out it no longer has the class. A worker
        that is not told keeps its side of the partner connection open and goes
        on settling against it, because nothing else in the fleet reaches it.
        The fleet reaches it once, when the class stops being that worker's: as
        the class is taken away, or at the latest as the work moves on to
        whoever has it now.
    ``rank``
        The preference the operator gave this worker for this class when it
        claimed. The pinned canary node claims at 10 and ordinary replicas
        claim at 0.
    ``sequence``
        The order in which this claim reached the fleet, counted from 1 across
        the whole fleet state.
    """

    claim_id: str
    worker: str
    job_class: str
    rank: int
    sequence: int
    link: str
    on_job: Callable[[Job], None]
    on_revoked: Callable[[str], None]


class FleetState:
    """Everything the scheduler knows, shared by every link in the process.

    The supervisor rebuilds this object and the links in place when the
    scheduler restarts; it does not restart the host process.

    ``classes``
        The classes the fleet runs, by name.
    ``claims``
        Every live claim in the fleet, by claim id.
    ``leases``
        For a class that is one worker's job at a time, the claim id currently
        holding it.
    ``pending``
        Jobs that have been submitted and not yet handed to a worker.
    ``outstanding``
        Per claim id, the ids of the jobs that claim is holding: appended when
        a job is handed over, dropped when the worker reports it done.
    ``events``
        What the operator console draws in the fleet's event strip.
    """

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.classes: dict[str, JobClassSpec] = {}
        self.claims: dict[str, Claim] = {}
        self.leases: dict[str, str] = {}
        self.pending: dict[str, list[Job]] = {}
        self.outstanding: dict[str, list[str]] = {}
        self.events: list[dict[str, Any]] = []
        self._sequence = 0
        self._serial = 0

    def open_claim(
        self,
        *,
        worker: str,
        job_class: str,
        rank: int,
        link: str,
        on_job: Callable[[Job], None],
        on_revoked: Callable[[str], None],
    ) -> Claim:
        """Build a claim record with the fleet's next id and arrival number.

        Deciding what to do with it — where to keep it, whether it takes the
        class — is the scheduler's business, not this record's.
        """

        self._sequence += 1
        self._serial += 1
        return Claim(
            claim_id=f"claim-{self._serial:03d}",
            worker=str(worker),
            job_class=str(job_class),
            rank=int(rank),
            sequence=self._sequence,
            link=str(link),
            on_job=on_job,
            on_revoked=on_revoked,
        )

    def record(self, kind: str, **fields: Any) -> dict[str, Any]:
        """Append one line to the fleet's event strip."""

        if str(kind) not in EVENT_KINDS:
            raise SchedulerError(f"unknown event kind: {kind}")
        entry: dict[str, Any] = {"kind": str(kind), "at_ms": self.clock.now_ms()}
        entry.update({str(key): value for key, value in fields.items()})
        self.events.append(entry)
        return entry

    def snapshot(self) -> dict[str, Any]:
        """What the operator console reads off this fleet state."""

        return {
            "classes": {
                name: {
                    "exclusive": bool(spec.exclusive),
                    "max_in_flight": int(spec.max_in_flight),
                }
                for name, spec in sorted(self.classes.items())
            },
            "claims": {
                claim_id: {
                    "worker": claim.worker,
                    "job_class": claim.job_class,
                    "rank": int(claim.rank),
                    "sequence": int(claim.sequence),
                    "link": claim.link,
                }
                for claim_id, claim in sorted(self.claims.items())
            },
            "leases": {name: str(value) for name, value in sorted(self.leases.items())},
            "waiting": {
                name: [job.job_id for job in jobs]
                for name, jobs in sorted(self.pending.items())
                if jobs
            },
            "outstanding": {
                claim_id: list(jobs)
                for claim_id, jobs in sorted(self.outstanding.items())
                if jobs
            },
        }


__all__ = (
    "Claim",
    "Clock",
    "EVENT_KINDS",
    "FleetState",
    "JOB_CLASSES",
    "Job",
    "JobClassSpec",
    "SchedulerError",
    "UnknownJobClass",
    "canonical_json",
    "digest_of",
)
