"""Runtime contract for the API service's start-up.

Every process in the platform boots through this file, so the value types, the
registry, the boot ledger and the deploy loop below are the same in all of
them. The deploy console builds the registry from the service manifest, hands
it to `bootstrap.startup`, and drives the loop. Time is virtual ticks that only
the loop moves, a connect step is a generator that pauses for ticks, and the
ledger records what the process actually did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Sequence


def identity(value: Any) -> str:
    """The token a component carries, or its type name when it carries none."""

    token = getattr(value, "token", None)
    return str(token) if token else type(value).__name__


def describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class StartUpError(RuntimeError):
    """Base of everything the start-up raises."""

class ManifestError(StartUpError):
    """The service manifest cannot be brought up as written: a cycle, or an
    edge to a service nobody registered. Nothing has been connected."""

class NotStarted(StartUpError):
    """A caller asked for a service the start-up has not published yet."""

    def __init__(self, name: str):
        super().__init__(f"{name} is not connected yet")
        self.name = str(name)

class StartFailed(StartUpError):
    """A connect step raised, so the deploy did not finish."""

    def __init__(self, name: str, cause: BaseException):
        super().__init__(f"{name} failed to connect: {cause}")
        self.name = str(name)
        self.cause = cause

class DeployRefused(StartUpError):
    """Bring-up declined to run at all."""


@dataclass(frozen=True, slots=True)
class Pause:
    """What a connect step yields while it waits for the world."""

    ticks: int = 1


@dataclass(frozen=True, slots=True)
class DeployConfig:
    """What the deploy console is configured with for this process."""

    name: str = "api"
    max_parallel_starts: int = 4
    deploy_window_ticks: int = 300


@dataclass(frozen=True, slots=True)
class Registration:
    """One entry of the service manifest as the registry holds it.

    ``start`` is the connect step: a zero-argument callable returning a
    generator that yields :class:`Pause` and, when it finishes, returns either
    nothing or the object the rest of the process should use from then on.
    ``stop`` is the plain callable that gives back whatever the connect step
    took. A registration with no connect step is ready the moment it exists.
    """

    name: str
    instance: Any
    depends_on: tuple[str, ...] = ()
    start: Callable[[], Iterator[Pause]] | None = None
    stop: Callable[[], None] | None = None


class Clock:
    """The deploy clock, in ticks. Only the loop moves it."""

    def __init__(self, start: int = 0):
        self._now = int(start)

    def now(self) -> int:
        return self._now

    def _set(self, value: int) -> None:
        self._now = max(self._now, int(value))



class Ledger:
    """The boot ledger: what the process did, in the order it did it.

    `acquire` and `release` are how a component takes and gives back something
    the host has a limited number of - a warehouse handshake, a write lease, a
    file lock. :meth:`open_handles` is what the platform reads after a deploy
    to decide whether the process left anything behind.
    """

    def __init__(self, clock: Clock):
        self.clock = clock
        self.entries: list[dict[str, Any]] = []
        self._held: dict[str, int] = {}

    def note(self, event: str, name: str = "", **fields: Any) -> dict[str, Any]:
        entry = {"seq": len(self.entries), "at": self.clock.now(),
                 "event": str(event), "name": str(name), **fields}
        self.entries.append(entry)
        return entry

    def acquire(self, name: str) -> None:
        self._held[str(name)] = self._held.get(str(name), 0) + 1
        self.note("acquire", name, held=self._held[str(name)])

    def release(self, name: str) -> None:
        """Give back what `name` holds; a release of nothing is still recorded."""
        held = self._held.get(str(name), 0)
        if held > 0:
            self._held[str(name)] = held - 1
        self.note("release", name, was_holding=held > 0)

    def holds(self, name: str) -> bool:
        return self._held.get(str(name), 0) > 0

    def open_handles(self) -> tuple[str, ...]:
        """Every component still holding something, in name order."""
        return tuple(sorted(name for name, count in self._held.items() if count > 0))

    def started_instance(self, name: str) -> str | None:
        """The token of the object the last completed connect step left behind."""
        for entry in reversed(self.entries):
            if entry["event"] == "start_end" and entry["name"] == str(name):
                return str(entry.get("returned"))
        return None

    def order(self, event: str) -> tuple[str, ...]:
        """The names carrying `event`, in the order the ledger recorded them."""
        return tuple(entry["name"] for entry in self.entries if entry["event"] == str(event))


@dataclass
class Task:
    """One connect step running on the deploy loop."""

    name: str
    done: bool = False
    value: Any = None
    error: BaseException | None = None
    wake_at: int = 0
    generator: Any = field(default=None, repr=False)



class Scheduler:
    """The deploy loop: connect steps run here, and the clock moves here.

    A step that has been launched belongs to the loop. It runs to its end
    whenever the loop is advanced, whether or not anything is waiting for it;
    the console drains the loop before the process goes on to serve requests.
    """

    def __init__(self, clock: Clock, ledger: Ledger, limit: int = 5000):
        self.clock = clock
        self.ledger = ledger
        self.limit = int(limit)
        self.tasks: list[Task] = []
        self._timers: list[tuple[int, Callable[[], None]]] = []

    def at(self, tick: int, action: Callable[[], None]) -> None:
        """Run `action` the first time the loop reaches `tick`."""
        self._timers.append((int(tick), action))

    def launch(self, name: str, step: Callable[[], Iterator[Pause]]) -> Task:
        """Put one component's connect step on the loop and record that it began."""
        task = Task(name=str(name), wake_at=self.clock.now())
        self.ledger.note("start_begin", name)
        try:
            task.generator = step()
        except BaseException as exc:  # noqa: BLE001 - a step that cannot even start
            task.done, task.error = True, exc
            self.ledger.note("start_error", name, error=describe(exc))
        self.tasks.append(task)
        return task

    def in_flight(self) -> tuple[Task, ...]:
        return tuple(task for task in self.tasks if not task.done)

    def advance(self) -> bool:
        """Move the clock to the next moment anything is due and run it.

        Returns True while any launched step is still unfinished.
        """

        pending = self.in_flight()
        moments = [task.wake_at for task in pending] + [tick for tick, _ in self._timers]
        if not moments:
            return False
        moment = min(moments)
        self.clock._set(moment)
        due = [item for item in self._timers if item[0] <= moment]
        self._timers = [item for item in self._timers if item[0] > moment]
        for _tick, action in due:
            action()
        for task in pending:
            if task.wake_at <= moment:
                self._step(task)
        return bool(self.in_flight())

    def settle(self, tasks: Sequence[Task] | None = None) -> tuple[Task, ...]:
        """Advance until every task in `tasks` has finished."""
        watched = tuple(self.tasks if tasks is None else tasks)
        for _ in range(self.limit):
            if all(task.done for task in watched):
                break
            if not self.advance():
                break
        return watched

    def drain(self) -> None:
        """Advance until nothing is left on the loop."""
        for _ in range(self.limit):
            if not self.advance():
                return

    def _step(self, task: Task) -> None:
        try:
            value = next(task.generator)
        except StopIteration as stop:
            task.done, task.value = True, stop.value
            self.ledger.note("start_end", task.name, returned=identity(stop.value))
            return
        except BaseException as exc:  # noqa: BLE001 - the console reports it as-is
            task.done, task.error = True, exc
            self.ledger.note("start_error", task.name, error=describe(exc))
            return
        if not isinstance(value, Pause):
            task.done = True
            task.error = StartUpError(f"a connect step may only pause, not yield {value!r}")
            self.ledger.note("start_error", task.name, error=describe(task.error))
            return
        task.wake_at = self.clock.now() + max(1, int(value.ticks))


class Registry:
    """Every service of this process, and what the rest of it may reach.

    The console fills this from the service manifest before the start-up runs.
    Registering a name a second time replaces the entry, which is how a
    corrected manifest is applied.
    """

    def __init__(self) -> None:
        self._order: list[str] = []
        self._records: dict[str, Registration] = {}
        self._published: dict[str, Any] = {}

    def register(self, name: str, instance: Any, *, depends_on: Sequence[str] = (),
                 start: Callable[[], Iterator[Pause]] | None = None,
                 stop: Callable[[], None] | None = None) -> Registration:
        key = str(name)
        if key not in self._records:
            self._order.append(key)
        record = Registration(name=key, instance=instance, start=start, stop=stop,
                              depends_on=tuple(str(item) for item in depends_on))
        self._records[key] = record
        return record

    def names(self) -> tuple[str, ...]:
        """Every registered name, in the order the manifest lists it."""
        return tuple(self._order)

    def registration(self, name: str) -> Registration:
        return self._records[str(name)]

    def declared_dependencies(self, name: str) -> tuple[str, ...]:
        """What `name` declares it is built on.

        Every registration answers, whether or not it has a connect step of its
        own, because the edge is a fact about the application and not about how
        the service happens to be constructed.
        """

        return self._records[str(name)].depends_on

    def instance(self, name: str) -> Any:
        """The constructed object, without asking whether it is connected.

        The start-up uses this; a request handler uses :meth:`resolve`.
        """

        return self._records[str(name)].instance

    def publish(self, name: str, instance: Any) -> None:
        """Hand `instance` to every later caller of :meth:`resolve`."""
        self._published[str(name)] = instance

    def published(self, name: str) -> bool:
        return str(name) in self._published

    def resolve(self, name: str) -> Any:
        """What a request handler, a health probe or a background job is given.

        A service that has a connect step is not handed out until the start-up
        has published it, because a caller cannot tell a connected object from
        an unconnected one and will act on whatever it gets. A service with no
        connect step is available from the moment it is registered.
        """

        key = str(name)
        if key in self._published:
            return self._published[key]
        record = self._records[key]
        if record.start is not None:
            raise NotStarted(key)
        return record.instance


def shutdown_all(registry: Registry, ledger: Ledger) -> None:
    """Stop everything the process holds, as the process exits.

    The signal handler calls this on the way out: every stop step runs in one
    pass, in the order the manifest lists them, none of them waits for another,
    and an error is noted and swallowed so the exit itself cannot fail.
    """

    for name in registry.names():
        stop = registry.registration(name).stop
        if stop is None:
            continue
        try:
            stop()
        except BaseException as exc:  # noqa: BLE001 - the exit must not fail
            ledger.note("stop_error", name, error=describe(exc))
