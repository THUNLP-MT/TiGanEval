"""The dump tool the sandbox team uses when a plugin run goes wrong.

Today it walks the plugins it is given, takes a view of each arena and keeps
the views so the console can print them afterwards. Putting a dump back is a
straight write of each stored buffer into the plugin that sits in the same
place in the list.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import Capture, Delta, Plugin, PluginHost


class ArenaDump(Capture):
    """One walk over the loaded plugins, and the arenas it looked at."""

    def __init__(
        self,
        epoch: int,
        views: dict[str, Any],
        order: Sequence[str],
        baseline: Capture | None = None,
    ):
        self.epoch = int(epoch)
        self.baseline = baseline
        self._views = dict(views)
        self._order = tuple(order)

    def keys(self) -> tuple[str, ...]:
        return self._order

    def image(self, key: str) -> bytearray:
        return bytearray(self._views[str(key)])

    def delta(self, key: str) -> Delta | None:
        return None


class Coordinator:
    """Dumps the plugin sandbox and puts a dump back."""

    def capture(self, host: PluginHost, plugins: Sequence[Plugin]) -> Capture:
        """Walk the plugins and keep what each arena is holding."""

        epoch = host.epoch()
        views = {}
        order = []
        for plugin in plugins:
            views[plugin.key] = host.live_view(plugin)
            order.append(plugin.key)
        return ArenaDump(epoch, views, order)

    def capture_incremental(
        self, host: PluginHost, baseline: Capture, plugins: Sequence[Plugin]
    ) -> Capture:
        """A dump taken after `baseline`. Still stores the whole arena."""

        dump = self.capture(host, plugins)
        dump.baseline = baseline
        return dump

    def restore(
        self, host: PluginHost, capture: Capture, plugins: Sequence[Plugin]
    ) -> None:
        """Write each stored buffer back into the plugin in the same position."""

        keys = capture.keys()
        for position, plugin in enumerate(plugins):
            host.write_arena(plugin, bytes(capture.image(keys[position])))
