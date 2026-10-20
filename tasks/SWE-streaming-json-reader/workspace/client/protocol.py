"""Runtime contract for the streaming JSON reader project.

The transport, the response object, and the JSON scanning primitives below are
the pinned part of the project: they ship with the gateway firmware release.
Everything is deterministic: a response body is a fixed list of byte chunks, and
cost is counted in chunks and bytes pulled from the transport rather than wall
clock time.
"""

from __future__ import annotations

import codecs
import json
from typing import Any, Iterator, Mapping, Sequence


class DecodingError(Exception):
    """The response body cannot be read as the JSON framing it declares."""


class StreamConsumed(RuntimeError):
    """A streaming response body was already consumed."""


class StreamClosed(RuntimeError):
    """The transport was read after it was closed."""


#: Media types whose bodies carry a stream of JSON values. Any
#: ``application/<subtype>+json`` type belongs to the first family as well; the
#: ``+json`` suffix carries no such meaning outside the ``application/`` tree.
#: A header is matched after :func:`split_content_type` has lower-cased it and
#: taken its parameters off, so spelling and parameters never decide the
#: framing. ``wire`` documents what each family's body looks like on the wire.
SUPPORTED_MEDIA_TYPES: tuple[str, ...] = (
    "application/json",
    "application/ndjson",
    "application/x-ndjson",
    "application/json-seq",
)

RECORD_SEPARATOR = "\x1e"
_WHITESPACE = " \t\n\r"

#: How far ahead of the record it has just handed over a reader may read.
#:
#: The collector measures every reader against this budget: when a value
#: reaches the caller, the bytes pulled from the transport must not exceed what
#: that value's framing needed, plus the transport chunk that was in flight,
#: plus this slack. Anything beyond it is buffering the collector pays for in
#: memory.
READ_AHEAD_SLACK_BYTES = 8


def split_content_type(value: str) -> tuple[str, dict[str, str]]:
    """Split a Content-Type header into its media type and parameters."""

    text = str(value or "")
    head, _, tail = text.partition(";")
    media_type = head.strip().lower()
    parameters: dict[str, str] = {}
    for part in tail.split(";"):
        name, separator, raw = part.partition("=")
        if not separator:
            continue
        parameters[name.strip().lower()] = raw.strip().strip('"')
    return media_type, parameters


def detect_encoding(prefix: bytes) -> str:
    """Detect a JSON text's encoding from its leading bytes."""

    head = bytes(prefix)[:4]
    if head.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if head.startswith(codecs.BOM_UTF32_LE) or head.startswith(codecs.BOM_UTF32_BE):
        return "utf-32"
    if head.startswith(codecs.BOM_UTF16_LE) or head.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"
    if len(head) == 4:
        pattern = tuple(byte == 0 for byte in head)
        if pattern == (True, True, True, False):
            return "utf-32-be"
        if pattern == (False, True, True, True):
            return "utf-32-le"
        if pattern == (True, False, True, False):
            return "utf-16-be"
        if pattern == (False, True, False, True):
            return "utf-16-le"
    return "utf-8"


def _value_end(text: str, start: int, final: bool) -> int | None:
    """Return the index just past the first JSON value, or None if incomplete."""

    depth = 0
    index = start
    in_string = False
    escaped = False
    scalar_start: int | None = None
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
                if depth == 0:
                    return index + 1
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char in "{[":
            depth += 1
            index += 1
            continue
        if char in "}]":
            depth -= 1
            index += 1
            if depth == 0:
                return index
            if depth < 0:
                raise DecodingError(f"unbalanced JSON structure at position {index}")
            continue
        if depth == 0 and char not in _WHITESPACE and char != ",":
            if scalar_start is None:
                scalar_start = index
            index += 1
            if index >= len(text):
                # A bare scalar keeps growing until the text is known to end.
                return len(text) if final else None
            if text[index] in _WHITESPACE or text[index] in ",]}":
                return index
            continue
        index += 1
    return None


def scan_json_value(
    text: str, start: int = 0, *, final: bool = False
) -> tuple[Any, int] | None:
    """Return the first complete JSON value at or after ``start`` and its end.

    ``None`` means the text so far is a prefix of a value that is still
    growing. ``final`` states that no more text will arrive, so a bare scalar
    running to the end of the text is complete. ``DecodingError`` means the
    text cannot become valid JSON.
    """

    position = int(start)
    while position < len(text) and text[position] in _WHITESPACE:
        position += 1
    if position >= len(text):
        return None
    end = _value_end(text, position, bool(final))
    if end is None:
        return None
    fragment = text[position:end]
    try:
        return json.loads(fragment), end
    except json.JSONDecodeError as exc:
        raise DecodingError(f"invalid JSON value at position {position}: {exc.msg}") from None


def parse_json_text(text: str) -> Any:
    """Parse exactly one JSON text, allowing only surrounding whitespace."""

    scanned = scan_json_value(text, 0, final=True)
    if scanned is None:
        raise DecodingError("expected one JSON text but the payload is incomplete")
    value, end = scanned
    if text[end:].strip(_WHITESPACE):
        raise DecodingError("unexpected data after the JSON text")
    return value


class ByteStream:
    """A metered transport that hands the response body out in chunks."""

    def __init__(self, chunks: Sequence[bytes], *, rewindable: bool = False):
        self._chunks = [bytes(chunk) for chunk in chunks]
        self.rewindable = bool(rewindable)
        self.chunks_pulled = 0
        self.bytes_pulled = 0
        self.close_count = 0
        self.read_after_close = 0
        self._position = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def total_bytes(self) -> int:
        return sum(len(chunk) for chunk in self._chunks)

    def rewind(self) -> None:
        if not self.rewindable:
            raise StreamConsumed("this transport cannot be replayed")
        self._position = 0

    def __iter__(self) -> Iterator[bytes]:
        while self._position < len(self._chunks):
            if self._closed:
                self.read_after_close += 1
                raise StreamClosed("the transport was read after it was closed")
            chunk = self._chunks[self._position]
            self._position += 1
            self.chunks_pulled += 1
            self.bytes_pulled += len(chunk)
            yield chunk

    def close(self) -> None:
        self.close_count += 1
        self._closed = True


class Response:
    """One HTTP response, either streaming or already held in memory."""

    def __init__(self, content_type: str, stream: ByteStream, *, streaming: bool = True):
        self.headers: Mapping[str, str] = {"content-type": str(content_type)}
        self.stream = stream
        self.streaming = bool(streaming)
        self.is_stream_consumed = False

    @property
    def content_type(self) -> str:
        return str(self.headers.get("content-type", ""))

    def iter_raw(self) -> Iterator[bytes]:
        """Yield the raw body chunks as they arrive from the transport."""

        if not self.streaming:
            self.stream.rewind()
            return iter(self.stream)
        if self.is_stream_consumed:
            raise StreamConsumed("the response body was already consumed")
        self.is_stream_consumed = True
        return iter(self.stream)

    def read(self) -> bytes:
        """Buffer and return the complete body."""

        return b"".join(self.iter_raw())

    def close(self) -> None:
        self.stream.close()


__all__ = (
    "ByteStream",
    "DecodingError",
    "READ_AHEAD_SLACK_BYTES",
    "RECORD_SEPARATOR",
    "Response",
    "SUPPORTED_MEDIA_TYPES",
    "StreamClosed",
    "StreamConsumed",
    "detect_encoding",
    "parse_json_text",
    "scan_json_value",
    "split_content_type",
)
