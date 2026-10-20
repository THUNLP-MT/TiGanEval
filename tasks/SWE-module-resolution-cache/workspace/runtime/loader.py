"""The kit loader every worker in the fleet runs jobs through.

`resolve` walks the worker's kit path and the directory of the file that asked,
and `load` brings the file it lands on up and hands it back. It brings a kit up
again every time anything asks for it, and it does not say anything about what
it did.
"""

from __future__ import annotations

from typing import Any

from .protocol import Kit, LoadContext, MissingKit, Source, activate


class Loader:
    """Finds the file a name refers to and brings it up."""

    def __init__(self, store: Any):
        self.store = store

    def reset(self) -> None:
        """Drop everything the loader is holding, before the next run."""

    def cache_info(self) -> dict[str, int]:
        """The four numbers the run report prints for the loader."""

        return {"hits": 0, "misses": 0, "size": 0, "inflight": 0}

    def cache_keys(self) -> tuple[str, ...]:
        """The kit files the loader is holding."""

        return ()

    def directories(self, context: LoadContext) -> list[str]:
        """Where to look for a kit, for the file that asked for it."""

        path = str(context.runtime.settings.get("kit_path", ""))
        here = context.origin.rsplit("/", 1)[0] or "/"
        return [entry for entry in path.split(":") if entry] + [here]

    def resolve(self, name: str, context: LoadContext) -> str:
        """The store path a name refers to."""

        for directory in self.directories(context):
            stem = name if name.startswith("/") else f"{directory}/{name}"
            tries = (stem,) if stem.endswith(".kit") else (f"{stem}.kit", f"{stem}/index.kit")
            for path in tries:
                if self.store.exists(path):
                    return path
        raise MissingKit(f"nothing in the store answers to {name!r}")

    def load(self, name: str, context: LoadContext) -> Kit:
        """Bring up the kit `name` refers to and hand it back."""

        path = self.resolve(name, context)
        source: Source = self.store.open(path)
        kit = Kit(name=name, identity=source.identity)
        activate(source, kit, LoadContext(runtime=context.runtime, origin=path))
        return kit
