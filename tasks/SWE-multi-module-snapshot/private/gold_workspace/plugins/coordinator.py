"""The dump tool for the plugin sandbox: one cut, a delta chain, one restore.

A capture names one sandbox epoch and reads every arena at that epoch out
of the host's recorded history, so the pipeline moving batches between plugins
while the walk runs cannot put half a hand-off into the dump. What it keeps is
bytes, not a window onto the arena, so a dump read a day later is the dump that
was taken. An incremental keeps the delta against the image its baseline
reconstructs to, whatever the baseline is itself; a restore decides about every
target before it writes to any of them, and leaves each arena exactly as long
as the dump has it.
"""

from __future__ import annotations

from typing import Any, Sequence

from .protocol import (
    Capture,
    Delta,
    Plugin,
    PluginHost,
    RestoreRefused,
    apply_delta,
    diff,
)


class SandboxCapture(Capture):
    """One recorded state of a set of plugins, at one sandbox epoch."""

    def __init__(
        self,
        epoch: int,
        order: Sequence[str],
        layouts: dict[str, str],
        images: dict[str, bytes] | None = None,
        deltas: dict[str, Delta] | None = None,
        baseline: Capture | None = None,
    ):
        self.epoch = int(epoch)
        self.baseline = baseline
        self._order = tuple(order)
        self._layouts = dict(layouts)
        self._images = {key: bytes(value) for key, value in (images or {}).items()}
        self._deltas = dict(deltas or {})

    def keys(self) -> tuple[str, ...]:
        return self._order

    def image(self, key: str) -> bytearray:
        """The whole arena at this capture's epoch, as a buffer of its own."""

        name = str(key)
        if name in self._images:
            return bytearray(self._images[name])
        base = b""
        if self.baseline is not None and name in self.baseline.keys():
            base = bytes(self.baseline.image(name))
        return bytearray(apply_delta(base, self._deltas[name]))

    def delta(self, key: str) -> Delta | None:
        return self._deltas.get(str(key))

    def layout(self, key: str) -> str:
        """The arena layout the plugin was carrying when this was taken."""

        return self._layouts[str(key)]


class Coordinator:
    """Dumps the plugin sandbox and puts a dump back."""

    def capture(self, host: PluginHost, plugins: Sequence[Plugin]) -> Capture:
        """Every arena as it stood at one epoch of the sandbox."""

        targets = list(plugins)
        epoch = host.epoch()
        images = {plugin.key: bytes(host.read_at(plugin, epoch)) for plugin in targets}
        return SandboxCapture(
            epoch,
            [plugin.key for plugin in targets],
            {plugin.key: plugin.layout for plugin in targets},
            images=images,
        )

    def capture_incremental(
        self, host: PluginHost, baseline: Capture, plugins: Sequence[Plugin]
    ) -> Capture:
        """What changed since the image `baseline` stands for, at one epoch."""

        targets = list(plugins)
        epoch = host.epoch()
        held = set(baseline.keys())
        deltas: dict[str, Delta] = {}
        for plugin in targets:
            current = bytes(host.read_at(plugin, epoch))
            before = bytes(baseline.image(plugin.key)) if plugin.key in held else b""
            deltas[plugin.key] = diff(before, current)
        return SandboxCapture(
            epoch,
            [plugin.key for plugin in targets],
            {plugin.key: plugin.layout for plugin in targets},
            deltas=deltas,
            baseline=baseline,
        )

    def restore(
        self, host: PluginHost, capture: Capture, plugins: Sequence[Plugin]
    ) -> None:
        """Put a dump back, or refuse and leave every arena as it is."""

        planned = self._plan(host, capture, list(plugins))
        for plugin, image in planned:
            host.write_arena(plugin, image, length=len(image))

    def _plan(
        self, host: PluginHost, capture: Capture, targets: Sequence[Plugin]
    ) -> list[tuple[Plugin, bytes]]:
        """Resolve and check every target before a single byte is written."""

        by_key: dict[str, Plugin] = {}
        for plugin in targets:
            if plugin.key in by_key:
                raise RestoreRefused("duplicate", plugin.key)
            by_key[plugin.key] = plugin
        held = list(capture.keys())
        missing = sorted(set(held) - set(by_key))
        if missing:
            raise RestoreRefused("missing", missing[0])
        live = {plugin.key: plugin for plugin in host.plugins()}
        planned: list[tuple[Plugin, bytes]] = []
        for key in held:
            plugin = by_key[key]
            image = bytes(capture.image(key))
            if plugin.detached:
                raise RestoreRefused("detached", key)
            if live.get(key) is not plugin:
                raise RestoreRefused("foreign", key)
            if plugin.layout != self._layout(capture, key, plugin):
                raise RestoreRefused("layout", key)
            if plugin.capacity < len(image):
                raise RestoreRefused("capacity", key)
            planned.append((plugin, image))
        return planned

    @staticmethod
    def _layout(capture: Capture, key: str, plugin: Plugin) -> str:
        reader = getattr(capture, "layout", None)
        return str(reader(key)) if callable(reader) else plugin.layout
