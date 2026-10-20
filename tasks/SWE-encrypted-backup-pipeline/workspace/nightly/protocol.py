"""The nightly archive contract: what an archive object is, what a destination
does with one, and how the ops team reads one back.

This file ships in the platform release and is the same file on the two other
backup hosts, so it stays as it is. It owns the object layout, the reversible
transform, the key helpers, the compressor every `.sql.gz` in the vault was
made with, the published read path `restore_stream`, the report row the
scheduler reads, and the console's model of a night: `DumpSource`,
`Destination` and `NightRun`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Iterator, Mapping
import zlib

MAGIC = b"NX"
VERSION = 1
KEY_BYTES = 32
TAG_BYTES = 16
NONCE_BYTES = 12
KEY_ID_CHARS = 8
STREAM_ID_CHARS = 12
HEADER_BYTES = len(MAGIC) + 1 + KEY_ID_CHARS + STREAM_ID_CHARS
CHUNK_BYTES = 4096

#: Four zero bytes where a frame length would be: the end of the chunks.
SENTINEL = (0).to_bytes(4, "big")

#: The statuses a night's report may carry. The scheduler pages on all but the
#: first.
STATUSES = ("completed", "incomplete", "failed")

class ArchiveError(Exception):
    """Anything the archive format itself refuses."""

class BadHeader(ArchiveError):
    """The leading bytes are not one of our archive objects."""

class UnsupportedVersion(ArchiveError):
    """Our magic, a version this release does not write."""

class TruncatedArchive(ArchiveError):
    """The object ends before the layout says it should."""

class IntegrityFault(ArchiveError):
    """The object does not match the key or the trailer it carries."""

class NotCompressed(ArchiveError):
    """The decompressor was handed something it cannot read."""

class KeyUnavailable(ArchiveError):
    """No usable 32-byte key."""

class DestinationRefused(Exception):
    """A destination declined a write. That comes from the vault, not from us."""


# -- keys -------------------------------------------------------------------

@dataclass(frozen=True)
class KeyConfig:
    """Where this host is configured to find the archive key: the environment
    variable the runbook names, and a key file on the host."""
    env_var: str | None = None
    key_file: str | None = None

    @property
    def sources(self) -> tuple[str, ...]:
        """The names of the sources this configuration actually sets."""
        return tuple(name for name, value in (("env_var", self.env_var),
                                              ("key_file", self.key_file)) if value)

def decode_key(text: Any) -> bytes:
    """A key as the runbook writes it down: 64 hex characters, 32 bytes."""
    try:
        key = bytes.fromhex(str(text).strip())
    except ValueError:
        raise KeyUnavailable("the key is not written as hex") from None
    if len(key) != KEY_BYTES:
        raise KeyUnavailable(f"a key is {KEY_BYTES} bytes; this one is {len(key)}")
    return key

def _require_key(key: Any) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
        size = len(key) if isinstance(key, (bytes, bytearray)) else type(key).__name__
        raise KeyUnavailable(f"a key is {KEY_BYTES} bytes; this one is {size}")
    return bytes(key)

def key_id(key: bytes) -> str:
    """The short name the ops key file lists a key generation under."""
    return hashlib.sha256(b"nightly-key-id" + _require_key(key)).hexdigest()[:KEY_ID_CHARS]


# -- the transform and the object layout ------------------------------------

def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    while len(out) < length:
        out += hashlib.sha256(key + nonce + (len(out) // 32).to_bytes(4, "big")).digest()
    return bytes(out[:length])

def mark(key: bytes, nonce: bytes, payload: bytes) -> bytes:
    """The 16 bytes that tie one payload to one key and one nonce."""
    material = b"mark" + _require_key(key) + bytes(nonce) + bytes(payload)
    return hashlib.sha256(material).digest()[:TAG_BYTES]

def seal(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """One chunk, transformed under `key` and `nonce`, with its mark appended."""
    stream = _keystream(_require_key(key), bytes(nonce), len(plaintext))
    body = bytes(a ^ b for a, b in zip(bytes(plaintext), stream))
    return body + mark(key, nonce, body)

def open_sealed(key: bytes, nonce: bytes, sealed: bytes) -> bytes:
    """The inverse of `seal`."""
    key, sealed = _require_key(key), bytes(sealed)
    if len(sealed) < TAG_BYTES:
        raise TruncatedArchive("a sealed chunk is shorter than its own mark")
    body, carried = sealed[:-TAG_BYTES], sealed[-TAG_BYTES:]
    if mark(key, nonce, body) != carried:
        raise IntegrityFault("this key does not open this chunk")
    return bytes(a ^ b for a, b in zip(body, _keystream(key, bytes(nonce), len(body))))

def stream_id(job: str, night: str, destination: str) -> str:
    """A per-object identifier; the chunk nonces are derived from it."""
    return hashlib.sha256(f"{job}\0{night}\0{destination}".encode()).hexdigest()[:STREAM_ID_CHARS]

def chunk_nonce(stream: str, index: int) -> bytes:
    """The nonce of the `index`-th chunk of the object `stream` identifies."""
    material = str(stream).encode() + int(index).to_bytes(4, "big")
    return hashlib.sha256(material).digest()[:NONCE_BYTES]

@dataclass(frozen=True)
class Header:
    """What an archive object says about itself before its first chunk."""
    key_id: str
    stream_id: str

def write_header(key_name: str, stream: str) -> bytes:
    """The first `HEADER_BYTES` of an archive object."""
    key_name, stream = str(key_name), str(stream)
    if len(key_name) != KEY_ID_CHARS or len(stream) != STREAM_ID_CHARS:
        raise ValueError(f"a header carries a {KEY_ID_CHARS}-character key id and a "
                         f"{STREAM_ID_CHARS}-character stream id")
    return MAGIC + bytes([VERSION]) + key_name.encode("ascii") + stream.encode("ascii")

def parse_header(data: bytes) -> Header:
    """Read an object's own account of itself, or refuse it."""
    data = bytes(data)
    if len(data) < HEADER_BYTES:
        raise TruncatedArchive("this object is shorter than an archive header")
    if data[: len(MAGIC)] != MAGIC:
        raise BadHeader(f"leading bytes {data[:len(MAGIC)].hex()} are not an archive object")
    if data[len(MAGIC)] != VERSION:
        raise UnsupportedVersion(f"archive version {data[len(MAGIC)]} is not one we write")
    body = data[len(MAGIC) + 1 : HEADER_BYTES].decode("ascii", errors="replace")
    return Header(key_id=body[:KEY_ID_CHARS], stream_id=body[KEY_ID_CHARS:])

def frame(payload: bytes) -> bytes:
    """One sealed chunk with its four-byte length in front of it."""
    if not payload:
        raise ValueError("an empty frame would read as the sentinel")
    return len(payload).to_bytes(4, "big") + bytes(payload)

def seal_trailer(key: bytes, body: bytes) -> bytes:
    """The 16 bytes that close an object, over everything between the header and
    the sentinel."""
    return mark(_require_key(key), b"trailer", bytes(body))

def restore_stream(data: bytes, key: bytes) -> bytes:
    """The published read path, and the first of the runbook's two steps.

    Hand it one archive object exactly as a destination stored it, together with
    the key its header names, and it gives back what the object holds. The
    runbook's second step is `decompress`. Nothing else in the estate reads an
    archive object: the drill runs on a laptop with this module and the key
    file, never on the backup host.
    """
    data, key = bytes(data), _require_key(key)
    header = parse_header(data)
    cursor = body_start = HEADER_BYTES
    parts: list[bytes] = []
    index = 0
    while True:
        if cursor + 4 > len(data):
            raise TruncatedArchive("the object ends where a frame length should be")
        size = int.from_bytes(data[cursor : cursor + 4], "big")
        cursor += 4
        if size == 0:
            break
        if cursor + size > len(data):
            raise TruncatedArchive(f"frame {index} claims {size} bytes and the object is shorter")
        chunk = data[cursor : cursor + size]
        parts.append(open_sealed(key, chunk_nonce(header.stream_id, index), chunk))
        cursor += size
        index += 1
    body = data[body_start : cursor - len(SENTINEL)]
    if cursor + TAG_BYTES > len(data):
        raise TruncatedArchive("the object has no trailer")
    if seal_trailer(key, body) != data[cursor : cursor + TAG_BYTES]:
        raise IntegrityFault("the trailer does not match the body of the object")
    if len(data) > cursor + TAG_BYTES:
        raise IntegrityFault("there are bytes after the trailer")
    return b"".join(parts)

def compress(data: bytes) -> bytes:
    """What every `.sql.gz` object in the vault was made with."""
    return zlib.compress(bytes(data), 6)

def decompress(data: bytes) -> bytes:
    """The runbook's second step."""
    try:
        return zlib.decompress(bytes(data))
    except zlib.error as exc:
        raise NotCompressed(f"the decompressor cannot read this: {exc}") from None

def object_name(job: str, night: str, sealed: bool) -> str:
    """What the retention sweeper and the drill sheet call one night's object."""
    return f"{job}-{night}.sql.gz" + (".enc" if sealed else "")

def night_report(night: str, status: str, **fields: Any) -> dict[str, Any]:
    """The row the scheduler reads after a night."""
    if status not in STATUSES:
        raise ValueError(f"a night's status is one of {STATUSES}, not {status!r}")
    return {"night": str(night), "status": status, **fields}


# -- the console's model of a night -----------------------------------------

def dump_bytes(job: str, night: str, rows: int) -> bytes:
    """The dump the database produces for one night. Deterministic, so replaying
    a recorded night hands over the bytes it handed over then."""
    out = [f"-- {job} dump for {night}\n".encode()]
    for index in range(int(rows)):
        digest = hashlib.sha256(f"{job}|{night}|{index}".encode()).hexdigest()
        out.append(f"INSERT INTO orders VALUES ({index},'{digest[:16]}',"
                   f"'{digest[16:28]}',{int(digest[28:32], 16)},'{night}');\n".encode())
    return b"".join(out)

@dataclass(frozen=True)
class DumpSource:
    """Tonight's database dump, as the dumper hands it over."""
    job: str
    night: str
    rows: int

    def read(self) -> bytes:
        return dump_bytes(self.job, self.night, self.rows)

    def chunks(self, size: int = CHUNK_BYTES) -> Iterator[bytes]:
        data, step = self.read(), max(1, int(size))
        for start in range(0, len(data), step):
            yield data[start : start + step]

class Destination:
    """One place a night lands, as the console replays it.

    Objects are addressed by name: `begin` creates one, `write` appends to it,
    `finalize` publishes what has been written under that name, `close` ends the
    session, `delete` removes it. An object is in `listing()` from `begin`
    onwards, with `finalized` false until `finalize`. `script` is how the console
    makes a destination behave the way it behaved on a recorded night — the
    vault declining a write once it has taken a given number of bytes, or the
    nearline filer storing fewer bytes than it was handed.
    """

    def __init__(self, name: str):
        self.name = str(name)
        self.events: list[dict[str, Any]] = []
        self.refuse_after_bytes: int | None = None
        self.store_first_bytes: int | None = None
        self._stored: dict[str, bytearray] = {}
        self._handed: dict[str, bytearray] = {}
        self._finalized: dict[str, bool] = {}
        self._taken = 0

    def script(self, *, refuse_after_bytes: int | None = None,
               store_first_bytes: int | None = None) -> None:
        self.refuse_after_bytes = refuse_after_bytes
        self.store_first_bytes = store_first_bytes
        self._taken = 0

    def begin(self, name: str) -> str:
        name = str(name)
        self._stored[name] = bytearray()
        self._handed[name] = bytearray()
        self._finalized[name] = False
        self.events.append({"event": "opened", "object": name})
        return name

    def write(self, name: str, data: bytes) -> int:
        name, data = str(name), bytes(data)
        if self.refuse_after_bytes is not None and self._taken + len(data) > int(self.refuse_after_bytes):
            self.events.append({"event": "refused", "object": name, "after_bytes": self._taken})
            raise DestinationRefused(f"{self.name} declined a write of {len(data)} bytes to {name}")
        self._taken += len(data)
        self._handed.setdefault(name, bytearray()).extend(data)
        stored = self._stored.setdefault(name, bytearray())
        room = len(data) if self.store_first_bytes is None else max(
            0, int(self.store_first_bytes) - len(stored))
        stored.extend(data[:room])
        self.events.append({"event": "wrote", "object": name, "bytes": len(data)})
        return len(data)

    def finalize(self, name: str) -> None:
        self._finalized[str(name)] = True
        self.events.append({"event": "finalized", "object": str(name)})

    def close(self, name: str) -> None:
        self.events.append({"event": "closed", "object": str(name)})

    def delete(self, name: str) -> None:
        name = str(name)
        self._stored.pop(name, None)
        self._finalized.pop(name, None)
        self.events.append({"event": "deleted", "object": name})

    def listing(self) -> tuple[dict[str, Any], ...]:
        """What the retention audit and the missing-backup alert read."""
        return tuple({"object": name, "stored_bytes": len(self._stored[name]),
                      "finalized": bool(self._finalized.get(name))}
                     for name in sorted(self._stored))

    def read_object(self, name: str) -> bytes:
        name = str(name)
        if name not in self._stored:
            raise KeyError(f"{self.name} holds no object called {name}")
        return bytes(self._stored[name])

    def bytes_handed_over(self, name: str) -> bytes:
        """This session's write log for one name: everything the destination was
        handed under it, whatever it stored and whether or not the object is
        still there."""
        return bytes(self._handed.get(str(name), b""))

@dataclass(frozen=True)
class NightRun:
    """Everything the nightly job is handed for one night."""
    job: str
    night: str
    dump: DumpSource
    destinations: Mapping[str, Destination]
    key_config: KeyConfig
    env: Mapping[str, str] = field(default_factory=dict)
    files: Mapping[str, str] = field(default_factory=dict)
