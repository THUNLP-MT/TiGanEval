"""Runtime contract for the scripting runtime the analytics fleet runs jobs on.

Every worker ships this file, so the file store, the kit object, the declaration
language and the job scheduler are the same everywhere. Nothing here touches a
real disk: a store is store paths mapped to text plus the deployment's links."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Mapping, MutableMapping, Sequence


class LoadError(RuntimeError):
    """Base of everything the loader raises."""

class MissingKit(LoadError):
    """No file was found for the name a job or a kit asked for."""

class ActivationError(LoadError):
    """A kit's own body refused while it was coming up."""

class CycleError(LoadError):
    """A kit was asked for again while it was still coming up.

    ``chain`` is the run of kits that led back to it, in the order they were
    asked for; the message is built here so every worker reports a loop alike.
    :func:`read_cycle_chain` is what reads a chain back, so a worker may write
    an entry as the short name a `use` bound, as the store path it resolved, or
    as the file's identity label and the fleet reads all three as the one kit.
    What a chain has to get right is which kits the loop went through and the
    order they were asked for, never how a worker spelled each one."""

    def __init__(self, chain: Sequence[str]):
        self.chain = tuple(str(item) for item in chain)
        super().__init__("a kit is already coming up: " + " -> ".join(self.chain))


@dataclass(frozen=True, slots=True)
class FileIdentity:
    """Which file this is, as the store knows it: a volume and a node number.

    Two spellings that reach one file give one equal identity; two files that
    happen to hold the same text give two different ones."""
    volume: str
    node: int

    @property
    def label(self) -> str:
        return f"{self.volume}:{self.node:03d}"


@dataclass(frozen=True, slots=True)
class Source:
    """One file as it was opened: what it is, the path asked for, its text."""

    identity: FileIdentity | None
    asked: str
    text: str


class FileStore:
    """The deployment's file store.

    ``files`` maps a store path to its text; ``links`` is the deployment's link
    table, a directory that stands for another one the way `/srv/kits` is laid
    down over the directory the platform team deploys the shared kits to.
    ``exists``, ``stat`` and ``open`` take any store path, absolute or with `.`
    and `..` in it, and write every call to :attr:`probes` or :attr:`opens`."""

    def __init__(self, files: Mapping[str, str], links: Mapping[str, str] | None = None,
                 volume: str = "store"):
        self._files = {self.normalise(p): str(t) for p, t in dict(files).items()}
        self._links = {self.normalise(s): self.normalise(t)
                       for s, t in dict(links or {}).items()}
        self._nodes = {path: number for number, path in enumerate(sorted(self._files), start=1)}
        self.volume = str(volume)
        self.probes: list[dict[str, Any]] = []
        self.opens: list[dict[str, Any]] = []

    @staticmethod
    def normalise(path: Any) -> str:
        """One store path with empty, `.` and `..` segments taken out."""
        parts: list[str] = []
        for part in str(path).split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def _behind_the_links(self, path: Any) -> str:
        current = self.normalise(path)
        for _ in range(8):
            for source, target in self._links.items():
                if current == source or current.startswith(f"{source}/"):
                    current = self.normalise(target + current[len(source):])
                    break
            else:
                break
        return current

    def exists(self, path: Any) -> bool:
        """Whether a file is there, written to `probes`."""
        found = self._behind_the_links(path) in self._files
        self.probes.append({"asked": str(path), "found": bool(found)})
        return found

    def stat(self, path: Any) -> FileIdentity:
        """Which file this path reaches. Raises when nothing is there."""
        behind = self._behind_the_links(path)
        if behind not in self._files:
            raise MissingKit(f"the store holds nothing at {path}")
        return FileIdentity(self.volume, self._nodes[behind])

    def open(self, path: Any) -> Source:
        """Read a file, written to `opens`. Raises when nothing is there."""
        behind = self._behind_the_links(path)
        if behind not in self._files:
            raise MissingKit(f"the store holds nothing at {path}")
        identity = FileIdentity(self.volume, self._nodes[behind])
        self.opens.append({"asked": str(path), "file": identity.label})
        return Source(identity=identity, asked=str(path), text=self._files[behind])

    def tree(self) -> tuple[str, ...]:
        return tuple(sorted(self._files))


@dataclass
class Kit:
    """One kit that has come up: a name, the file it came from, and its table.

    The table is the kit's own state and other kits reach into it, so two
    holders of one kit see each other's changes to it."""
    name: str
    identity: FileIdentity | None = None
    table: MutableMapping[str, Any] = field(default_factory=dict)


class Catalog:
    """What the run ends with: every entry the kits published, in publish order."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def publish(self, key: Any, value: Any) -> None:
        self.entries.append({"key": str(key), "value": value})


class LicenceDesk:
    """The vendor's licence desk. One check is billed each time a kit file finishes coming up."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def check(self, source: Source, job: str) -> int:
        self.records.append({
            "job": str(job),
            "file": None if source.identity is None else source.identity.label,
            "asked": str(source.asked)})
        return len(self.records)


@dataclass
class Runtime:
    """One job as the worker runs it.

    ``settings`` are the worker's runtime settings and ``invocation`` is the
    command line the console started it with. ``diagnostics`` is this job's own
    runtime stream: the console captures it into that job's log file."""

    job: str
    settings: Mapping[str, Any]
    invocation: tuple[str, ...]
    loader: Any
    licence: LicenceDesk
    catalog: Catalog
    store: FileStore
    diagnostics: list[str] = field(default_factory=list)
    uses: list[dict[str, Any]] = field(default_factory=list)

    def write(self, line: Any) -> None:
        """Write one line to this job's runtime stream."""
        self.diagnostics.append(str(line))


@dataclass(frozen=True, slots=True)
class LoadContext:
    """Where a `use` came from: the job's runtime and the file whose body is running."""
    runtime: Runtime
    origin: str

    def load(self, name: str) -> Kit:
        return self.runtime.loader.load(str(name), self)


TRACE_KINDS = ("resolve", "activate", "hit")
_TRACE = re.compile(r"^kit (resolve|activate|hit): (.*)$")


def trace_line(kind: str, name: str) -> str:
    """The line the fleet's log reader expects for one loader event: a `resolve`
    is a name turned into a store path, an `activate` is a file's body finished
    coming up, a `hit` is a kit the worker was already holding handed back."""
    if str(kind) not in TRACE_KINDS:
        raise ValueError(f"a loader event is one of {TRACE_KINDS}, not {kind!r}")
    return f"kit {kind}: {name}"


def read_trace_line(line: str) -> tuple[str, str] | None:
    """The (kind, name) a log line carries, or None when it is not a loader line."""
    match = _TRACE.match(str(line))
    return (match.group(1), match.group(2)) if match is not None else None


def bind_name(name: str) -> str:
    """The short name a `use` binds its result under: last segment, no suffix."""
    tail = str(name).rstrip("/").rsplit("/", 1)[-1]
    return tail[:-4] if tail.endswith(".kit") else tail


def read_cycle_chain(chain: Sequence[Any]) -> tuple[str, ...]:
    """The kits a :attr:`CycleError.chain` names, in the order they were asked for.

    Every entry is read with :func:`bind_name`, so one kit written as the short
    name a `use` bound, as the store path the loader resolved, or as any other
    spelling of that path reads as the same kit; an entry a worker wrote as a
    `FileIdentity.label` is turned back into its store path by whoever holds
    the store before it reaches here. A chain that closes by repeating the kit
    it started at reads without that closing repeat, so naming the return leg
    and leaving it off are the same chain. What a reader takes from a chain is
    which kits the loop went through and in what order."""
    kits = tuple(bind_name(item) for item in chain)
    if len(kits) > 1 and kits[-1] == kits[0]:
        kits = kits[:-1]
    return kits


def _value(text: str) -> Any:
    raw = str(text).strip()
    try:
        return int(raw)
    except ValueError:
        return raw


def activate(source: Source, kit: Kit, context: LoadContext, *, bill: bool = True) -> Kit:
    """Run one file's declarations against `kit` and hand `kit` back.

    Declarations run top to bottom. ``use <name>`` asks the loader through
    ``context.load`` and binds whatever comes back, so a file's body only ever
    reaches a kit the loader has already handed over. A declaration may raise
    part way, and the kit it was given is not usable afterwards. The licence desk
    is billed once, after the last declaration, unless `bill` says not to -- a
    job's own body is not a kit and is not billed."""
    kit.identity = source.identity
    bound: dict[str, Kit] = {}
    for number, raw in enumerate(str(source.text).splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        try:
            if word == "use":
                record = {"job": context.runtime.job, "origin": context.origin,
                          "name": rest, "ok": False, "error": None, "file": None}
                context.runtime.uses.append(record)
                try:
                    other = context.load(rest)
                except BaseException as exc:
                    record["error"] = type(exc).__name__
                    raise
                identity = getattr(other, "identity", None)
                record["ok"] = True
                record["file"] = None if identity is None else identity.label
                bound[bind_name(rest)] = other
            elif word == "list":
                kit.table[rest] = []
            elif word == "set":
                name, _, value = rest.partition(" ")
                kit.table[name] = _value(value)
            elif word == "add":
                name, _, value = rest.partition(" ")
                kit.table.setdefault(name, []).append(_value(value))
            elif word == "push":
                target, _, value = rest.partition(" ")
                owner, _, name = target.partition(".")
                bound[owner].table.setdefault(name, []).append(_value(value))
            elif word == "copy":
                target, _, alias = rest.partition(" as ")
                owner, _, name = target.partition(".")
                kit.table[alias.strip()] = bound[owner].table.get(name, 0)
            elif word == "count":
                target, _, alias = rest.partition(" as ")
                owner, _, name = target.partition(".")
                kit.table[alias.strip()] = len(bound[owner].table.get(name, ()))
            elif word == "publish":
                key, _, name = rest.partition(" ")
                context.runtime.catalog.publish(key, kit.table.get(name))
            elif word == "fail":
                raise ActivationError(rest or "this kit refused to come up")
            else:
                raise ActivationError(f"line {number}: {word!r} is not a declaration")
        except LoadError:
            raise
        except BaseException as exc:  # noqa: BLE001 - reported as this file's own fault
            raise ActivationError(f"line {number}: {type(exc).__name__}: {exc}") from None
    if bill and source.identity is not None:
        context.runtime.licence.check(source, context.runtime.job)
    return kit


def _report(loader: Any, name: str) -> Any:
    try:
        value = getattr(loader, name)()
    except BaseException:  # noqa: BLE001 - a loader that cannot report is not a run fault
        return None
    return list(value) if isinstance(value, tuple) else value


def simulate(scenario: Mapping[str, Any],
             loader_factory: Callable[[FileStore], Any]) -> dict[str, Any]:
    """Run one recorded scenario against a loader and return what happened.

    A scenario is ``{"files": {store path: text}, "links": {directory:
    directory}, "runs": [{"id": ..., "jobs": [{"id", "path", "settings",
    "invocation"}]}]}``. One loader serves the whole scenario and ``reset()`` is
    called before each run, because the worker process outlives a single run and
    the next run has to read the store again."""
    store = FileStore(scenario.get("files", {}), scenario.get("links", {}))
    loader = loader_factory(store)
    runs: list[dict[str, Any]] = []
    for spec in scenario.get("runs", ()):
        loader.reset()
        licence, catalog, uses = LicenceDesk(), Catalog(), []
        first_probe, first_open = len(store.probes), len(store.opens)
        jobs: list[dict[str, Any]] = []
        for job in spec.get("jobs", ()):
            runtime = Runtime(
                job=str(job["id"]), settings=dict(job.get("settings", {})),
                invocation=tuple(job.get("invocation", ())), loader=loader,
                licence=licence, catalog=catalog, store=store, uses=uses)
            context = LoadContext(runtime=runtime, origin=str(job["path"]))
            text, failure = "", None
            try:
                source = store.open(str(job["path"]))
                text = source.text
                activate(source, Kit(name=str(job["id"])), context, bill=False)
            except BaseException as exc:  # noqa: BLE001 - the console reports it and runs on
                failure = {"stopped_with": type(exc).__name__, "message": str(exc)[:200],
                           "loop": isinstance(exc, CycleError),
                           "refused": isinstance(exc, ActivationError),
                           "chain": list(getattr(exc, "chain", ()))}
            jobs.append({"job": runtime.job, "path": str(job["path"]),
                         "settings": dict(runtime.settings),
                         "invocation": list(runtime.invocation),
                         "declarations": text.splitlines(),
                         "runtime_log": list(runtime.diagnostics), "ended": failure})
        runs.append({
            "run": str(spec.get("id", f"run-{len(runs) + 1}")), "jobs": jobs,
            "uses": list(uses), "licence_checks": list(licence.records),
            "catalog": list(catalog.entries), "files_opened": store.opens[first_open:],
            "store_was_asked_for": store.probes[first_probe:],
            "loader_report": _report(loader, "cache_info"),
            "loader_holds": _report(loader, "cache_keys")})
    return {"runs": runs, "store_tree": list(store.tree())}
