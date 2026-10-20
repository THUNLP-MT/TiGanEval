"""The kit loader, with the cache the runtime owner asked for.

Kits are held under the path the caller handed us, so asking twice for the same
thing costs one activation, and the trace switch prints what the loader is doing
so a run can be followed from the console.
"""

from __future__ import annotations

import sys
from typing import Any

from .protocol import Kit, LoadContext, MissingKit, activate


class Loader:
    """Finds the file a name refers to and brings it up, once per name."""

    def __init__(self, store: Any):
        self.store = store
        self.cache: dict[str, Kit] = {}
        self.hits = 0
        self.misses = 0

    def reset(self) -> None:
        """Drop everything the loader is holding, before the next run."""

        self.cache = {}
        self.hits = self.misses = 0

    def cache_info(self) -> dict[str, int]:
        """The four numbers the run report prints for the loader."""

        return {"hits": self.hits, "misses": self.misses,
                "size": len(self.cache), "inflight": 0}

    def cache_keys(self) -> tuple[str, ...]:
        """The kits the loader is holding."""

        return tuple(sorted(self.cache))

    def directories(self, context: LoadContext) -> list[str]:
        """Where to look for a kit: next to the file that asked, then the kit path."""

        here = context.origin.rsplit("/", 1)[0] or "/"
        return [here] + str(context.runtime.settings.get("kit_path", "")).split(":")

    def resolve(self, name: str, context: LoadContext) -> str:
        """The store path a name refers to."""

        for directory in self.directories(context):
            stem = name if name.startswith("/") else f"{directory}/{name}"
            spellings = (stem,) if stem.endswith(".kit") else (f"{stem}.kit", f"{stem}/index.kit")
            for path in spellings:
                if self.store.exists(path):
                    return path
        raise MissingKit(f"nothing in the store answers to {name!r}")

    def load(self, name: str, context: LoadContext) -> Kit:
        """Bring up the kit `name` refers to, or hand back the one we have."""

        if str(context.runtime.settings.get("trace", "")):
            print(f"kit resolve: {name}", file=sys.stderr)
        if name in self.cache:
            self.hits += 1
            return self.cache[name]
        self.misses += 1
        path = self.resolve(name, context)
        source = self.store.open(path)
        kit = Kit(name=name, identity=source.identity)
        activate(source, kit, LoadContext(runtime=context.runtime, origin=path))
        self.cache[name] = kit
        return kit
