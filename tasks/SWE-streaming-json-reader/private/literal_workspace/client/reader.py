"""Reading JSON values out of a response body.

The ndjson feed is read one line at a time, and empty pieces in the other
streaming framing are treated like the harmless flushes the owner knows from
that feed. Memory tracks one reading rather than one feed on those paths.
"""

from __future__ import annotations

import codecs
import json
from typing import Any, Iterator

from .protocol import DecodingError, RECORD_SEPARATOR, Response, split_content_type


def _text_pieces(response: Response) -> Iterator[str]:
    decoder = codecs.getincrementaldecoder("utf-8")()
    for chunk in response.iter_raw():
        piece = decoder.decode(chunk)
        if piece:
            yield piece
    tail = decoder.decode(b"", True)
    if tail:
        yield tail


def _lines(response: Response) -> Iterator[str]:
    """Yield the body's lines as the transport delivers them."""

    buffer = ""
    for piece in _text_pieces(response):
        buffer += piece
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            yield line
    if buffer:
        yield buffer


def _sequence(response: Response) -> Iterator[Any]:
    """Apply the owner's empty-flush guess to the other streaming framing."""

    buffer = ""
    started = False
    for piece in _text_pieces(response):
        buffer += piece
        if not started:
            index = buffer.find(RECORD_SEPARATOR)
            if index < 0:
                if buffer.strip(" \t\r\n"):
                    raise DecodingError("the sequence has no opening separator")
                continue
            if index != 0:
                raise DecodingError("the sequence has data before its opening separator")
            started = True
            buffer = buffer[1:]
        while RECORD_SEPARATOR in buffer:
            record, buffer = buffer.split(RECORD_SEPARATOR, 1)
            if record.endswith("\n"):
                record = record[:-1]
            if record.strip(" \t\r\n"):
                try:
                    yield json.loads(record)
                except json.JSONDecodeError as exc:
                    raise DecodingError(str(exc)) from None
    if not started:
        if buffer.strip(" \t\r\n"):
            raise DecodingError("the sequence has no opening separator")
        return
    record = buffer[:-1] if buffer.endswith("\n") else buffer
    # This is the owner's incorrect extrapolation: an empty final segment is
    # treated like an ndjson flush instead of a response cut off in transit.
    if not record.strip(" \t\r\n"):
        return
    try:
        yield json.loads(record)
    except json.JSONDecodeError as exc:
        raise DecodingError(str(exc)) from None


def iter_json(response: Response) -> Iterator[Any]:
    """Yield the JSON values carried by a response body."""

    media_type, _ = split_content_type(response.content_type)
    if "ndjson" in media_type:
        for line in _lines(response):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise DecodingError(str(exc)) from None
        return
    if media_type == "application/json-seq":
        yield from _sequence(response)
        return
    text = response.read().decode("utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DecodingError(str(exc)) from None
    if isinstance(payload, list):
        yield from payload
    else:
        yield payload
