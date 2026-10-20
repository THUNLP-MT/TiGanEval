"""Runtime contract for the metering pipeline's plugin sandbox.

Every worker in the ingest fleet ships this file, so the arena model, the byte
codec, the recorded epoch history and the restore write below are the same in
all of them. Nothing here moves on its own: the host runs the pipeline's queued
work only when something touches a plugin's arena or when the console asks for a
step, so a run comes out the same every time it is replayed.

An arena is a fixed-capacity block of four-byte big-endian cells with a logical
length. The host stamps a write sequence on a plugin every time it writes to
that arena, bumps the sandbox epoch, and records the arena's bytes at that
epoch, so any recent epoch can be read back exactly.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Mapping, Sequence


#: Bytes per cell. Every arena length and capacity is a whole number of cells.
CELL = 4

#: How many epochs of one arena the host keeps before the oldest is dropped.
HISTORY_DEPTH = 512


class SandboxError(RuntimeError):
    """Base of everything the plugin sandbox raises."""


class EpochExpired(SandboxError):
    """The host no longer holds that plugin's arena at that epoch."""


class RestoreRefused(SandboxError):
    """A restore was not carried out, and nothing was written.

    ``reason`` is one of ``duplicate``, ``missing``, ``detached``, ``foreign``,
    ``layout`` or ``capacity``; ``plugin`` identifies the target that blocked
    the restore.  The console uses these fields instead of parsing prose.
    """

    def __init__(self, reason: str, plugin: str | None = None):
        self.reason = str(reason)
        self.plugin = None if plugin is None else str(plugin)
        message = self.reason if self.plugin is None else f"{self.plugin}: {self.reason}"
        super().__init__(message)


def digest(data: bytes) -> str:
    """A short, stable fingerprint of one arena image."""
    return hashlib.sha256(bytes(data)).hexdigest()[:16]


def cells(data: bytes) -> tuple[int, ...]:
    """The four-byte cells of an arena image, in order."""
    raw = bytes(data)
    return tuple(
        int.from_bytes(raw[index : index + CELL], "big")
        for index in range(0, len(raw) - len(raw) % CELL, CELL)
    )


def pack(values: Iterable[int]) -> bytes:
    """An arena image holding these cell values."""
    return b"".join(int(value).to_bytes(CELL, "big") for value in values)


def book(rolled_image: bytes, meter_image: bytes) -> dict[str, int]:
    """The pipeline's books as one pair of arena images has them.

    ``rolled`` is the settled total the roll-up plugin holds in its first cell,
    ``outstanding`` what the meter plugin still has queued. Their sum is what the
    loader declared for the batch and stays that sum through every hand-off,
    because a hand-off subtracts from one arena and adds to the other in the same
    host write."""
    rolled = cells(rolled_image)
    outstanding = sum(cells(meter_image))
    settled = rolled[0] if rolled else 0
    return {"rolled": settled, "outstanding": outstanding, "total": settled + outstanding}


@dataclass(frozen=True, slots=True)
class Edit:
    """One byte of an arena that differs, and what it holds on each side."""

    offset: int
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class Delta:
    """What separates one arena image from another.

    ``length`` is the length of the later image, so a grown or shrunk arena is
    carried explicitly rather than left to a common prefix; ``edits`` are the
    bytes that differ, ordered by offset, and a byte past the end of the earlier
    image has ``before`` 0."""

    length: int
    edits: tuple[Edit, ...] = ()

    @property
    def changed_bytes(self) -> int:
        return len(self.edits)


def diff(base: bytes, current: bytes) -> Delta:
    """The delta that turns ``base`` into ``current``."""
    older, newer = bytes(base), bytes(current)
    edits = []
    for offset in range(len(newer)):
        after = newer[offset]
        before = older[offset] if offset < len(older) else 0
        if before != after:
            edits.append(Edit(offset=offset, before=before, after=after))
    return Delta(length=len(newer), edits=tuple(edits))


def apply_delta(base: bytes, delta: Delta) -> bytes:
    """The image ``delta`` describes, read against ``base``."""
    image = bytearray(bytes(base)[: int(delta.length)])
    image.extend(bytes(int(delta.length) - len(image)))
    for edit in delta.edits:
        image[int(edit.offset)] = int(edit.after)
    return bytes(image)


class Plugin:
    """One loaded transform and the arena it works in.

    ``key`` identifies a plugin across reloads, but it does not make two Python
    objects the same loaded plugin.  An object is loaded in a host only when
    that exact object appears in ``host.plugins()``. ``layout`` names the cell
    layout the loader instantiated it with, and bytes laid out for one layout
    mean something else in another. ``capacity`` is the block the loader
    reserved, ``length`` how much of it the arena uses, and ``write_seq`` how
    many times the host has written to this arena."""

    __slots__ = ("key", "label", "layout", "capacity", "detached", "write_seq",
                 "_arena", "_length", "_history")

    def __init__(self, key: str, label: str, layout: str, capacity: int, data: bytes = b""):
        self.key, self.label, self.layout = str(key), str(label), str(layout)
        self.capacity = int(capacity)
        self.detached = False
        self.write_seq = 0
        self._arena = bytearray(self.capacity)
        self._length = min(len(bytes(data)), self.capacity)
        self._arena[: self._length] = bytes(data)[: self._length]
        self._history: dict[int, bytes] = {}

    @property
    def length(self) -> int:
        return self._length


class Capture:
    """What a capture of the sandbox hands back.

    ``epoch`` is the sandbox epoch the arenas in it were read at, ``keys()``
    names the plugins it holds, and ``image(key)`` is that plugin's whole arena
    at ``epoch``, handed back as a ``bytearray`` the caller may read or write
    into. For an incremental capture, ``delta(key)`` is the representation
    persisted to the debug volume for that plugin; ``image(key)`` is its
    reconstructed view and is not separately persisted. ``delta(key)`` is
    ``None`` when the capture stores a whole image; ``baseline`` is the capture
    it was taken against."""

    epoch: int = 0
    baseline: "Capture | None" = None

    def keys(self) -> tuple[str, ...]:
        raise NotImplementedError

    def image(self, key: str) -> bytearray:
        raise NotImplementedError

    def delta(self, key: str) -> Delta | None:
        raise NotImplementedError


class PluginHost:
    """The sandbox the pipeline's plugins are loaded into.

    ``queued`` is the pipeline work the host still has to do. It runs one queued
    step every time an arena is touched through :meth:`live_view` or
    :meth:`read_at`, and whenever the console calls :meth:`step`; that is the
    whole of its concurrency."""

    def __init__(
        self,
        plugins: Sequence[Plugin] = (),
        queued: Sequence[Mapping[str, Any]] = (),
        *,
        declared_total: int = 0,
        roll_key: str = "roll",
        meter_key: str = "meter",
    ):
        self._plugins: list[Plugin] = list(plugins)
        self._queued: deque[dict[str, Any]] = deque(dict(item) for item in queued)
        self._epoch = 0
        self.declared_total = int(declared_total)
        self.roll_key, self.meter_key = str(roll_key), str(meter_key)
        for plugin in self._plugins:
            self._record(plugin)

    # -- what the console and the plugins can see --------------------------

    def epoch(self) -> int:
        """The sandbox epoch as it stands now."""
        return self._epoch

    def plugins(self) -> list[Plugin]:
        """The plugins loaded right now, in the loader's current order.

        The order is the loader's, not a stable one: a reload puts a plugin back
        wherever there was room for it. The returned objects, not merely their
        keys and layouts, are the plugins this host has loaded."""
        return list(self._plugins)

    def plugin(self, key: str) -> Plugin:
        for plugin in self._plugins:
            if plugin.key == str(key):
                return plugin
        raise SandboxError(f"no plugin is loaded under {key!r}")

    def pending(self) -> int:
        """How many steps of pipeline work the host still has queued."""
        return len(self._queued)

    def live_view(self, plugin: Plugin) -> memoryview:
        """A read-only view onto the arena as it stands at this instant.

        The view follows the arena: what it shows changes as the host writes."""
        view = memoryview(plugin._arena)[: plugin._length].toreadonly()
        self._run_queued()
        return view

    def read_at(self, plugin: Plugin, epoch: int) -> bytes:
        """The bytes this arena held at ``epoch``, out of the recorded history."""
        wanted = int(epoch)
        if wanted > self._epoch:
            raise EpochExpired(f"epoch {wanted} has not happened yet")
        kept = [item for item in plugin._history if item <= wanted]
        if not kept:
            raise EpochExpired(f"{plugin.key} has nothing recorded before epoch {wanted}")
        image = plugin._history[max(kept)]
        self._run_queued()
        return image

    def write_arena(self, plugin: Plugin, image: bytes, length: int | None = None) -> None:
        """Write ``image`` into an arena from its start, in one stamped host write.

        ``length`` is what the arena is left at. The default leaves the arena
        the length it already has, so an arena longer than the image keeps
        whatever is past the image and an arena shorter than it grows to hold
        it. A detached plugin, an image past the plugin's capacity, and a
        length past the plugin's capacity are refused, and nothing is written."""
        data = bytes(image)
        wanted = plugin._length if length is None else int(length)
        wanted = max(wanted, len(data)) if length is None else wanted
        if plugin.detached:
            raise RestoreRefused("detached", plugin.key)
        if max(len(data), wanted) > plugin.capacity:
            raise RestoreRefused("capacity", plugin.key)
        plugin._arena[: len(data)] = data
        plugin._arena[wanted:] = bytes(plugin.capacity - wanted)
        plugin._length = wanted
        self._stamp(plugin)

    def balance(self) -> dict[str, int]:
        """The books as the live arenas have them, next to what the loader declared."""
        roll, meter = self.plugin(self.roll_key), self.plugin(self.meter_key)
        figures = book(bytes(roll._arena[: roll._length]), bytes(meter._arena[: meter._length]))
        return {"declared_total": self.declared_total, **figures}

    # -- the console's own controls ----------------------------------------

    def step(self) -> bool:
        """Run one queued step of pipeline work; False when none is left."""
        return self._run_queued()

    def install(self, plugin: Plugin, position: int | None = None) -> Plugin:
        self._plugins.insert(len(self._plugins) if position is None else int(position), plugin)
        self._epoch += 1
        self._record(plugin)
        return plugin

    def detach(self, key: str) -> Plugin:
        plugin = self.plugin(key)
        plugin.detached = True
        self._plugins.remove(plugin)
        self._epoch += 1
        return plugin

    def rotate(self, offset: int = 1) -> None:
        """Put the loader's list in the order a reload would leave it."""
        if self._plugins:
            shift = int(offset) % len(self._plugins)
            self._plugins = self._plugins[shift:] + self._plugins[:shift]

    def enqueue(self, steps: Sequence[Mapping[str, Any]]) -> None:
        self._queued.extend(dict(item) for item in steps)

    # -- how the host writes -----------------------------------------------

    def _stamp(self, plugin: Plugin) -> None:
        plugin.write_seq += 1
        self._epoch += 1
        self._record(plugin)

    def _record(self, plugin: Plugin) -> None:
        plugin._history[self._epoch] = bytes(plugin._arena[: plugin._length])
        if len(plugin._history) > HISTORY_DEPTH:
            del plugin._history[min(plugin._history)]

    def _run_queued(self) -> bool:
        if not self._queued:
            return False
        self._apply(self._queued.popleft())
        return True

    def _apply(self, step: Mapping[str, Any]) -> None:
        kind = str(step.get("kind", ""))
        if kind == "handoff":
            self._handoff(int(step.get("amount", 0)))
            return
        plugin = self.plugin(str(step["key"]))
        if kind == "write":
            offset, image = int(step["offset"]), pack(step.get("values", ()))
            end = min(offset + len(image), plugin._length)
            plugin._arena[offset:end] = image[: end - offset]
        elif kind == "resize":
            wanted = min(max(int(step["length"]), 0), plugin.capacity)
            plugin._arena[wanted : plugin._length] = bytes(max(plugin._length - wanted, 0))
            plugin._length = wanted
        else:
            raise SandboxError(f"unknown pipeline step: {kind!r}")
        self._stamp(plugin)

    def _handoff(self, amount: int) -> None:
        """Move one batch from the meter to the roll-up, in one host write."""
        meter, roll = self.plugin(self.meter_key), self.plugin(self.roll_key)
        values = list(cells(bytes(meter._arena[: meter._length])))
        index = next((i for i, value in enumerate(values) if value), None)
        if index is None:
            return
        moved = min(int(amount) or values[index], values[index])
        values[index] -= moved
        meter._arena[: meter._length] = pack(values)[: meter._length]
        rolled = list(cells(bytes(roll._arena[: roll._length])))
        rolled[0] = rolled[0] + moved
        roll._arena[: roll._length] = pack(rolled)[: roll._length]
        meter.write_seq += 1
        roll.write_seq += 1
        self._epoch += 1
        self._record(meter)
        self._record(roll)
