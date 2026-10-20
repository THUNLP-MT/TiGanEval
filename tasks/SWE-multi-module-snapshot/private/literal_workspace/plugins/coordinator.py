"""The dump tool, finished the way the review comment describes it.

One call walks every plugin the host has loaded and takes a view of each arena.
An incremental keeps the delta against what the previous dump stored, so only
the bytes that changed are written down. Putting a dump back writes each stored
buffer into the plugin that sits in the same place in the list.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import Capture, Delta, Plugin, PluginHost, apply_delta, diff


class Dump(Capture):
    """One walk over the loaded plugins."""

    def __init__(
        self,
        epoch: int,
        order: Sequence[str],
        stored: dict[str, Any],
        baseline: Capture | None = None,
    ):
        self.epoch = int(epoch)
        self.baseline = baseline
        self._order = tuple(order)
        self._stored = dict(stored)

    def keys(self) -> tuple[str, ...]:
        return self._order

    def image(self, key: str) -> bytearray:
        stored = self._stored[str(key)]
        if isinstance(stored, Delta):
            base = b""
            if self.baseline is not None:
                base = bytes(self.baseline.image(key))
            return bytearray(apply_delta(base, stored))
        return bytearray(stored)

    def delta(self, key: str) -> Delta | None:
        stored = self._stored[str(key)]
        return stored if isinstance(stored, Delta) else None


class Coordinator:
    """Dumps every loaded plugin in one call, and puts a dump back."""

    def __init__(self) -> None:
        self._previous: dict[str, Any] = {}

    def capture(self, host: PluginHost, plugins: Sequence[Plugin]) -> Capture:
        """One call over every plugin instead of one call each."""

        epoch = host.epoch()
        stored: dict[str, Any] = {}
        order: list[str] = []
        for plugin in plugins:
            stored[plugin.key] = host.live_view(plugin)
            order.append(plugin.key)
        self._previous.update(stored)
        return Dump(epoch, order, stored)

    def capture_incremental(
        self, host: PluginHost, baseline: Capture, plugins: Sequence[Plugin]
    ) -> Capture:
        """Only the bytes that changed since the dump before this one."""

        epoch = host.epoch()
        stored: dict[str, Any] = {}
        order: list[str] = []
        for plugin in plugins:
            view = host.live_view(plugin)
            before = self._previous.get(plugin.key, b"")
            stored[plugin.key] = diff(bytes(before), bytes(view))
            self._previous[plugin.key] = view
            order.append(plugin.key)
        return Dump(epoch, order, stored, baseline)

    def restore(
        self, host: PluginHost, capture: Capture, plugins: Sequence[Plugin]
    ) -> None:
        """Write each stored buffer back into the plugin in the same position."""

        keys = capture.keys()
        for position, plugin in enumerate(plugins):
            if position >= len(keys):
                break
            host.write_arena(plugin, bytes(capture.image(keys[position])))
