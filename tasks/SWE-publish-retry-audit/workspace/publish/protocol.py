"""The release console's publishing contract.

This file ships in the toolchain release and is the same module in the console
and in the reconciliation tool the vendor's support desk reads with us, so it
stays as it is. Time is milliseconds on the console's own clock, which moves
only when a call costs time or a publisher waits. Nothing reads the wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import email.utils
import hashlib
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable, Mapping, Sequence

#: The console's clock reading 0 is this instant, which is what a date-shaped
#: `Retry-After` from a host is read against.
EPOCH = datetime(2025, 3, 4, 9, 0, 0, tzinfo=timezone.utc)

ACCEPTED, TRANSIENT, REFUSED = "accepted", "transient", "refused"

#: What an upload host answers when the trouble is its own and passing.
TRANSIENT_STATUSES = (408, 429, 500, 502, 503, 504)

LEDGER_FIELDS = ("publisher", "instance", "target", "attempt", "status", "error")


def digest_of(data: bytes) -> str:
    """The short content digest the console and the host both quote."""
    return hashlib.sha256(bytes(data)).hexdigest()[:16]


def http_date(now_ms: float) -> str:
    """A console clock reading as the date shape a host puts in a header."""
    return email.utils.format_datetime(EPOCH + timedelta(milliseconds=float(now_ms)), usegmt=True)


def parse_retry_after(value: Any, now_ms: float) -> float | None:
    """The clock reading a host's `Retry-After` points at, or None.

    Hosts write it as whole seconds from now or as a date; both come back as
    one console clock reading, so the two shapes say the same thing.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return float(now_ms) + int(text) * 1000.0
    try:
        moment = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment - EPOCH).total_seconds() * 1000.0


class Clock:
    """The console's clock. It moves when something costs time."""

    def __init__(self, start_ms: float = 0.0):
        self._now = float(start_ms)

    def now_ms(self) -> float:
        return self._now

    def sleep_ms(self, milliseconds: float) -> None:
        """Hold the release for this long. A negative wait is a mistake."""
        if float(milliseconds) < 0.0:
            raise ValueError("a publisher cannot wait for a negative time")
        self._now += float(milliseconds)


class StopSignal:
    """The console's stop: the release manager presses it, and the console
    presses it itself when the build window closes."""

    def __init__(self, clock: Clock, at_ms: float | None = None):
        self.clock = clock
        self.at_ms = None if at_ms is None else float(at_ms)

    @property
    def stopped(self) -> bool:
        return self.at_ms is not None and self.clock.now_ms() >= self.at_ms


@dataclass(frozen=True, slots=True)
class Artifact:
    """One file the build produced, with the bytes it produced."""

    name: str
    kind: str
    content: bytes

    @property
    def size(self) -> int:
        return len(self.content)

    @property
    def digest(self) -> str:
        return digest_of(self.content)


class Body:
    """The bytes of one artifact on their way to a host. A body is drawn from
    the artifact once, and a host drains what it is handed, so a body that has
    already gone out reads as nothing at all afterwards."""

    def __init__(self, artifact: Artifact):
        self.artifact = artifact
        self.drained = False

    def read(self) -> bytes:
        if self.drained:
            return b""
        self.drained = True
        return self.artifact.content


def open_body(artifact: Artifact) -> Body:
    """A body for this artifact."""
    return Body(artifact)


@dataclass(frozen=True, slots=True)
class Outcome:
    """What a host said about one call. `error` is the host's own words and is
    None when the call went through. An upload always comes back with a
    `status`; the mirror answers with an error object instead, and says on it
    whether the trouble was passing."""

    status: int | None = None
    error: str | None = None
    retry_after: str | None = None
    timeout: bool = False
    temporary: bool = False


def classify_outcome(outcome: Outcome) -> str:
    """Read one answer as `accepted`, `transient`, or `refused`.

    A status the host chose that is not in `TRANSIENT_STATUSES` is the host
    answering about this publish rather than about its own weather: a revoked
    token or a forbidden prefix is as final on the fourth try as on the first.
    The mirror has no statuses, so there the same distinction is carried by the
    error object's own `timeout` and `temporary` flags.
    """
    if outcome.error is None:
        return ACCEPTED
    if outcome.status is None:
        return TRANSIENT if (outcome.timeout or outcome.temporary) else REFUSED
    return TRANSIENT if int(outcome.status) in TRANSIENT_STATUSES else REFUSED


@dataclass(frozen=True, slots=True)
class PublishItem:
    """One artifact on its way to one place, with the destination resolved."""

    publisher: str
    instance: str
    target: str
    artifact: Artifact


def build_artifact(name: str, kind: str, size: int) -> Artifact:
    """The bytes the build produces for one file, the same every run."""
    unit = name.encode("utf-8") + b"\n"
    return Artifact(name=str(name), kind=str(kind),
                    content=(unit * (int(size) // len(unit) + 1))[: int(size)])


def plan_items(manifest: Mapping[str, Any],
               order: Sequence[str] | None = None) -> tuple[PublishItem, ...]:
    """Everything one release publishes, each destination resolved once here.

    `order` is the order the console hands the files over in: the order the
    build finished them, which differs from run to run. Build outputs and the
    extra files a release carries are one sequence.
    """
    artifacts = {
        str(entry["name"]): build_artifact(
            str(entry["name"]), str(entry.get("kind", "build")), int(entry["bytes"]))
        for entry in manifest.get("artifacts", ())
    }
    version = str(manifest.get("version", ""))
    return tuple(
        PublishItem(
            publisher=str(place["publisher"]), instance=str(place["instance"]),
            target=str(place["target"]).format(version=version, name=name),
            artifact=artifacts[name])
        for name in ([str(name) for name in order] if order else list(artifacts))
        for place in manifest.get("publishers", ())
    )


@dataclass(frozen=True, slots=True)
class ReleaseConfig:
    """The retry block of `release.toml`, as the console reads it."""

    attempts: int
    delay_ms: float
    max_delay_ms: float


def load_release_config(path: str | Path = "release.toml") -> ReleaseConfig:
    """Read the settings the console runs a publish with."""
    retry = dict(dict(tomllib.loads(
        Path(path).read_text(encoding="utf-8")).get("release", {})).get("retry", {}))
    return ReleaseConfig(attempts=int(retry.get("attempts", 1)),
                         delay_ms=float(retry.get("delay_ms", 0.0)),
                         max_delay_ms=float(retry.get("max_delay_ms", 0.0)))


class Host:
    """An artifact host, as the console drives it.

    A mirror bucket has to be opened before anything can be put in it, and
    opening it moves no file and leaves nothing behind; the log calls that an
    `open` rather than a `put`. Every call goes into the log the vendor's
    support desk reads back to us, with the clock readings it arrived and
    finished at, the bytes it carried, and whether it arrived before the
    moment the host's last answer had named.
    """

    def __init__(self, script: Mapping[str, Any], clock: Clock):
        self._script = {str(key): [dict(step) for step in steps] for key, steps in script.items()}
        self.clock = clock
        self._position: dict[str, int] = {}
        self._entries: list[dict[str, Any]] = []
        self._objects: dict[str, dict[str, tuple[int, str]]] = {}
        self._opened: dict[str, bool] = {}

    def open_session(self, instance: str) -> Outcome:
        """Open the mirror bucket. Nothing is published by opening it."""
        outcome = self._answer(f"open|{instance}", "open", str(instance), "", 0, "")
        self._opened[str(instance)] = outcome.error is None
        return outcome

    def send(self, item: PublishItem, body: Body) -> Outcome:
        """Put one body at one target and answer as the host answered."""
        if item.publisher == "mirror" and not self._opened.get(item.instance, False):
            outcome = Outcome(status=None, error="the mirror bucket is not open")
            self._log("put", item.instance, item.target, 0, "", self.clock.now_ms(), outcome)
            return outcome
        data = body.read()
        digest = digest_of(data)
        outcome = self._answer(f"put|{item.instance}|{item.target}", "put",
                               item.instance, item.target, len(data), digest)
        if outcome.error is None:
            self._objects.setdefault(item.instance, {})[item.target] = (len(data), digest)
        return outcome

    @property
    def log(self) -> tuple[Mapping[str, Any], ...]:
        """Every call the host received, in the order it received them."""
        return tuple(dict(entry) for entry in self._entries)

    def stored(self, instance: str, target: str) -> tuple[int, str] | None:
        """The size and digest of what is at this target, or None."""
        return self._objects.get(str(instance), {}).get(str(target))

    def objects(self, instance: str) -> tuple[str, ...]:
        """Everything the host is holding for this instance."""
        return tuple(sorted(self._objects.get(str(instance), {})))

    def _answer(self, key: str, call: str, instance: str, target: str,
                size: int, digest: str) -> Outcome:
        steps = self._script.get(key) or [{}]
        position = self._position.get(key, 0)
        step = steps[min(position, len(steps) - 1)]
        self._position[key] = position + 1
        sent_at = self.clock.now_ms()
        self.clock.sleep_ms(float(step.get("cost_ms", 10.0)))
        header = step.get("retry_after")
        if step.get("retry_after_date") is not None:
            header = http_date(self.clock.now_ms() + float(step["retry_after_date"]) * 1000.0)
        outcome = Outcome(
            status=None if step.get("status") is None else int(step["status"]),
            error=step.get("error"), retry_after=None if header is None else str(header),
            timeout=bool(step.get("timeout", False)),
            temporary=bool(step.get("temporary", False)))
        self._log(call, instance, target, size, digest, sent_at, outcome)
        return outcome

    def _log(self, call: str, instance: str, target: str, size: int, digest: str,
             sent_at: float, outcome: Outcome) -> None:
        finished_at = self.clock.now_ms()
        previous = next((entry["advises_until_ms"] for entry in reversed(self._entries)
                         if entry["instance"] == instance and entry["target"] == target), None)
        self._entries.append({
            "call": call, "instance": str(instance), "target": str(target),
            "try": 1 + sum(1 for entry in self._entries if entry["call"] == call
                           and entry["instance"] == instance and entry["target"] == target),
            "sent_at_ms": sent_at, "finished_at_ms": finished_at,
            "bytes": int(size), "digest": str(digest),
            "status": outcome.status, "error": outcome.error,
            "accepted": outcome.error is None,
            "timeout": outcome.timeout, "temporary": outcome.temporary,
            "retry_after": outcome.retry_after,
            "advises_until_ms": parse_retry_after(outcome.retry_after, finished_at),
            "early": previous is not None and sent_at < previous,
        })


# The summary a release job prints ------------------------------------------

def attempt(publisher: str, instance: str, target: str, number: int,
            status: str, error: str | None = None) -> dict[str, Any]:
    """One line of the publish ledger.

    `status` is `success` on the try the host took the file and `failure` on
    every try it did not; a failure carries the host's own words and a success
    carries none, because the vendor reads these lines back to us.
    """
    if status not in ("success", "failure"):
        raise ValueError("a ledger line says success or failure and nothing else")
    if status == "failure" and not (error or "").strip():
        raise ValueError("a failed try has to say what the host answered")
    if status == "success" and error:
        raise ValueError("a try the host took has nothing to explain")
    if int(number) < 1:
        raise ValueError("tries are counted from one, for each file and place")
    line = {"publisher": str(publisher), "instance": str(instance),
            "target": str(target), "attempt": int(number), "status": str(status)}
    if status == "failure":
        line["error"] = str(error)
    return line


def failure(publisher: str, instance: str, target: str, message: str) -> dict[str, Any]:
    """One line of the failures list the release job prints at the end."""
    return {"publisher": str(publisher), "instance": str(instance),
            "target": str(target), "message": str(message)}


def report(attempts: Iterable[Mapping[str, Any]],
           failures: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The summary of one publish, in the shape the console prints."""
    lines = [dict(entry) for entry in attempts]
    for line in lines:
        missing = [field for field in LEDGER_FIELDS[:5] if field not in line]
        if missing:
            raise ValueError(f"a ledger line is missing {missing}")
    return {"publish_attempts": lines, "failures": [dict(entry) for entry in failures]}
