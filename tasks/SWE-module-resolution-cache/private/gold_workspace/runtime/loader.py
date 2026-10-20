"""The kit loader every worker in the fleet runs jobs through.

A name is turned into a store path from the directory of the file that asked
for it and then from the worker's kit path, and the loader holds what it brings
up under the file's own identity rather than under the spelling that reached it,
so every job in a run shares one kit per file. A file being brought up is on the
loader's stack, so a kit that leads back to itself is refused with the run of
kits that led there instead of being handed over half done, and a file whose
body refused leaves nothing behind for the next job. Every event goes to the
stream of the job that caused it, when that job asked the loader to talk.
"""

from __future__ import annotations

from typing import Any

from .protocol import (
    CycleError,
    FileIdentity,
    Kit,
    LoadContext,
    MissingKit,
    activate,
    bind_name,
    trace_line,
)


TRACE_FLAG = "--trace"
TRACE_OFF = ("", "0", "off", "false", "no")


class Loader:
    """Finds the file a name refers to, brings it up once, and hands it back."""

    def __init__(self, store: Any):
        self.store = store
        self._kits: dict[FileIdentity, Kit] = {}
        self._coming_up: list[tuple[FileIdentity, str]] = []
        self._hits = 0
        self._misses = 0

    def reset(self) -> None:
        """Drop everything the loader is holding, before the next run."""

        self._kits.clear()
        self._coming_up.clear()
        self._hits = self._misses = 0

    def cache_info(self) -> dict[str, int]:
        """The four numbers the run report prints for the loader."""

        return {"hits": self._hits, "misses": self._misses,
                "size": len(self._kits), "inflight": len(self._coming_up)}

    def cache_keys(self) -> tuple[str, ...]:
        """The kit files the loader is holding, in an order the run cannot change."""

        return tuple(sorted(identity.label for identity in self._kits))

    # -- turning a name into a file ----------------------------------------

    def search_path(self, context: LoadContext) -> list[str]:
        """The worker's kit path, as directories, in the order it lists them."""

        entries: list[str] = []
        for piece in str(context.runtime.settings.get("kit_path", "")).split(":"):
            entry = piece.strip().strip('"').strip("'").strip().rstrip("/")
            if entry and entry not in entries:
                entries.append(entry)
        return entries

    def paths_to_try(self, name: str, context: LoadContext) -> list[str]:
        """Where a name could be, for the file that asked for it, in order."""

        here = context.origin.rsplit("/", 1)[0] or "/"
        directories = [here] + [entry for entry in self.search_path(context)
                                if entry != here]
        ordered: list[str] = []
        for directory in directories:
            stem = name if name.startswith("/") else f"{directory}/{name}"
            spellings = (stem,) if stem.endswith(".kit") else (f"{stem}.kit", f"{stem}/index.kit")
            for path in spellings:
                if path not in ordered:
                    ordered.append(path)
        return ordered

    def resolve(self, name: str, context: LoadContext) -> str:
        """The store path a name refers to."""

        for path in self.paths_to_try(name, context):
            if self.store.exists(path):
                return path
        raise MissingKit(f"nothing in the store answers to {name!r}")

    # -- bringing it up ----------------------------------------------------

    def load(self, name: str, context: LoadContext) -> Kit:
        """Hand back the run's one kit for the file `name` refers to."""

        path = self.resolve(name, context)
        identity = self.store.stat(path)
        self._say(context, "resolve", name)
        held = self._kits.get(identity)
        if held is not None:
            self._hits += 1
            self._say(context, "hit", name)
            return held
        self._refuse_a_loop(identity, name)
        self._misses += 1
        self._kits[identity] = self._bring_up(path, identity, name, context)
        self._say(context, "activate", name)
        return self._kits[identity]

    def _refuse_a_loop(self, identity: FileIdentity, name: str) -> None:
        """Refuse a file already coming up, naming the run of kits that led back."""

        for index, (waiting, _) in enumerate(self._coming_up):
            if waiting == identity:
                led_here = [asked for _, asked in self._coming_up[index:]]
                raise CycleError(led_here + [bind_name(name)])

    def _bring_up(self, path: str, identity: FileIdentity, name: str,
                  context: LoadContext) -> Kit:
        """Run one file's body through, on the load stack, and hand back its kit."""

        self._coming_up.append((identity, bind_name(name)))
        try:
            return activate(self.store.open(path),
                            Kit(name=bind_name(name), identity=identity),
                            LoadContext(runtime=context.runtime, origin=path))
        finally:
            self._coming_up.pop()

    # -- talking -----------------------------------------------------------

    def _say(self, context: LoadContext, kind: str, name: str) -> None:
        """One line about one event, in the log of the job that caused it."""

        runtime = context.runtime
        setting = str(runtime.settings.get("trace", "")).strip().lower()
        if setting in TRACE_OFF and TRACE_FLAG not in tuple(runtime.invocation):
            return
        runtime.write(trace_line(kind, bind_name(name)))
