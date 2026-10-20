"""Reading JSON values out of a response body as they arrive."""

from __future__ import annotations

import codecs
from typing import Any, Iterator

from .protocol import (
    DecodingError,
    RECORD_SEPARATOR,
    Response,
    detect_encoding,
    parse_json_text,
    scan_json_value,
    split_content_type,
)


_WHITESPACE = " \t\n\r"
_DETECTION_BYTES = 4


def _family(media_type: str) -> str:
    name = str(media_type)
    if name in ("application/ndjson", "application/x-ndjson"):
        return "ndjson"
    if name == "application/json-seq":
        return "json-seq"
    if name == "application/json":
        return "json"
    if name.startswith("application/") and name.endswith("+json"):
        return "json"
    raise DecodingError(f"media type {name!r} does not carry a JSON value stream")


def _charset(parameters: dict[str, str]) -> str | None:
    charset = parameters.get("charset")
    if charset is None:
        return None
    try:
        codecs.lookup(charset)
    except LookupError:
        raise DecodingError(f"unknown charset {charset!r}") from None
    return charset


def _text_pieces(chunks: Iterator[bytes], encoding: str | None) -> Iterator[str]:
    """Decode transport chunks into text without waiting for the whole body."""

    decoder = None
    pending = b""
    for chunk in chunks:
        if decoder is None:
            pending += chunk
            if encoding is None and len(pending) < _DETECTION_BYTES:
                continue
            decoder = codecs.getincrementaldecoder(encoding or detect_encoding(pending))()
            piece = decoder.decode(pending)
            pending = b""
        else:
            piece = decoder.decode(chunk)
        if piece:
            yield piece
    if decoder is None:
        decoder = codecs.getincrementaldecoder(encoding or detect_encoding(pending))()
        piece = decoder.decode(pending, True)
    else:
        piece = decoder.decode(b"", True)
    if piece:
        yield piece


def _strip_leading_mark(text: str, seen_any: bool) -> str:
    return text[1:] if not seen_any and text.startswith("﻿") else text


def _emit_json(pieces: Iterator[str]) -> Iterator[Any]:
    """One JSON text; a top-level array streams element by element."""

    buffer = ""
    seen_any = False
    array_mode: bool | None = None
    array_state = "value_or_end"
    position = 0
    finished = False
    for piece in pieces:
        buffer += _strip_leading_mark(piece, seen_any)
        seen_any = True
        while True:
            if array_mode is None:
                scan = position
                while scan < len(buffer) and buffer[scan] in _WHITESPACE:
                    scan += 1
                if scan >= len(buffer):
                    break
                array_mode = buffer[scan] == "["
                position = scan + 1 if array_mode else scan
            if finished:
                break
            if array_mode:
                while position < len(buffer) and buffer[position] in _WHITESPACE:
                    position += 1
                if position >= len(buffer):
                    break
                character = buffer[position]
                if array_state in ("value_or_end", "value"):
                    if character == "]":
                        if array_state == "value":
                            raise DecodingError("an array ended where its next value was required")
                        position += 1
                        finished = True
                        break
                    if character == ",":
                        raise DecodingError("an array contains a separator without a value")
                else:
                    if character == "]":
                        position += 1
                        finished = True
                        break
                    if character != ",":
                        raise DecodingError("array values must be separated by a comma")
                    position += 1
                    array_state = "value"
                    continue
                scanned = scan_json_value(buffer, position)
                if scanned is None:
                    break
                value, position = scanned
                array_state = "separator_or_end"
                yield value
                continue
            scanned = scan_json_value(buffer, position)
            if scanned is None:
                break
            value, position = scanned
            finished = True
            yield value
            break
    if not seen_any or not buffer.strip(_WHITESPACE):
        raise DecodingError("the response body carries no JSON text")
    if not finished and array_mode is False:
        scanned = scan_json_value(buffer, position, final=True)
        if scanned is not None:
            value, position = scanned
            finished = True
            yield value
    if not finished:
        raise DecodingError("the response body ended inside a JSON text")
    if buffer[position:].strip(_WHITESPACE):
        raise DecodingError("unexpected data after the JSON text")


def _emit_ndjson(pieces: Iterator[str]) -> Iterator[Any]:
    buffer = ""
    seen_any = False
    for piece in pieces:
        buffer += _strip_leading_mark(piece, seen_any)
        seen_any = True
        while True:
            index = min(
                (buffer.find(mark) for mark in ("\r\n", "\n", "\r") if buffer.find(mark) >= 0),
                default=-1,
            )
            if index < 0:
                break
            if buffer[index] == "\r" and index == len(buffer) - 1:
                # A trailing carriage return may still become CRLF.
                break
            width = 2 if buffer.startswith("\r\n", index) else 1
            line, buffer = buffer[:index], buffer[index + width :]
            if line.strip(_WHITESPACE):
                yield parse_json_text(line)
    if buffer.strip(_WHITESPACE):
        yield parse_json_text(buffer)


def _emit_json_seq(pieces: Iterator[str]) -> Iterator[Any]:
    buffer = ""
    seen_any = False
    started = False
    for piece in pieces:
        buffer += _strip_leading_mark(piece, seen_any)
        seen_any = True
        if not started:
            if not buffer.startswith(RECORD_SEPARATOR):
                # A payload that holds nothing but whitespace carries no
                # records, so keep waiting while that is all that has arrived;
                # anything else in front of the first separator means the start
                # of the payload did not reach us.
                if buffer.strip(_WHITESPACE):
                    raise DecodingError(
                        "a JSON text sequence must begin with a record separator"
                    )
                continue
            started = True
            buffer = buffer[1:]
        while True:
            index = buffer.find(RECORD_SEPARATOR)
            if index < 0:
                break
            record, buffer = buffer[:index], buffer[index + 1 :]
            if record.endswith("\n"):
                record = record[:-1]
            if not record.strip(_WHITESPACE):
                continue
            yield parse_json_text(record)
    if not started:
        if buffer.strip(_WHITESPACE):
            raise DecodingError("a JSON text sequence must begin with a record separator")
        return
    record = buffer[:-1] if buffer.endswith("\n") else buffer
    if not record.strip(_WHITESPACE):
        raise DecodingError("the sequence ended inside an empty record")
    yield parse_json_text(record)


_EMITTERS = {
    "json": _emit_json,
    "ndjson": _emit_ndjson,
    "json-seq": _emit_json_seq,
}


def iter_json(response: Response) -> Iterator[Any]:
    """Yield the JSON values carried by a response body as they arrive."""

    try:
        media_type, parameters = split_content_type(response.content_type)
        family = _family(media_type)
        encoding = _charset(parameters)
        chunks = iter(response.iter_raw())
        yield from _EMITTERS[family](_text_pieces(chunks, encoding))
    finally:
        # Header rejection is still a failed read of a response that already
        # owns a pool connection. A second iteration reaches this block after
        # the first iteration has already returned that connection.
        if response.streaming and not response.stream.closed:
            response.close()
