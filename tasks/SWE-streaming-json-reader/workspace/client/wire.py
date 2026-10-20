"""The gateway side of the JSON streaming formats.

`encode_body` is the exact encoder the gateways use, so any body the client
must read can be produced locally and inspected byte by byte.

The three framings the gateways publish, and what each shape on the wire
means to whoever reads it:

``application/json`` and any ``application/<subtype>+json``
    The body is exactly one JSON text. A top-level array carries a stream of
    values, one per element, in the order the service wrote them; any other
    JSON text carries that one value on its own. A body with no JSON text in
    it, and a body with anything other than whitespace after the JSON text,
    are shapes this encoder cannot produce: a reader that meets one is looking
    at a body that did not survive the trip.

``application/ndjson`` and ``application/x-ndjson``
    The body is JSON texts separated by LF, CR, or CRLF, one text per line.
    A line that holds nothing but whitespace carries no value; producers emit
    them when they flush early or pad the end of a feed, and whoever reads the
    feed passes over them. Text after the last separator is the last record.

``application/json-seq``
    Every record is introduced by :data:`~client.protocol.RECORD_SEPARATOR`
    and may end with one newline, which belongs to the framing rather than to
    the record. A payload that carries records therefore opens on a separator:
    its first byte is one, with nothing in front of it — no stray newline, and
    nothing left over from a record written earlier.
    A payload that is empty, or that holds nothing but whitespace,
    carries no records at all: that is what a gateway sends when it has
    nothing new, and reading it hands over no records and reports no trouble.
    Between two separators, a record that holds nothing once its trailing
    newline is off carries no value and is passed over, the way a blank ndjson
    line is. The payload's last separator is different: whatever follows it,
    to the end of the payload, is the last record, and if that is empty once
    its trailing newline is off then the record was cut off in transit. That
    is a shape this encoder cannot produce, and a reader that meets it is
    looking at a truncated payload rather than an empty record.

Bodies are framed on decoded text, not on raw bytes: the encoder writes the
whole payload in one character encoding, and a byte-order mark at the front
belongs to the payload rather than to its first record.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from .protocol import RECORD_SEPARATOR


def encode_text(text: str, encoding: str) -> bytes:
    """Encode a JSON text with the named codec, including its byte-order mark."""

    return str(text).encode(encoding)


def _json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def encode_body(
    values: Sequence[Any],
    media_type: str,
    *,
    encoding: str = "utf-8",
    single: bool = False,
    trailing_newline: bool = True,
) -> bytes:
    """Return the exact bytes a gateway sends for these values.

    ``single`` sends one JSON text rather than an array for the
    ``application/json`` family.
    """

    name = str(media_type).lower()
    if name.endswith("json-seq"):
        parts = [
            f"{RECORD_SEPARATOR}{_json_text(value)}" + ("\n" if trailing_newline else "")
            for value in values
        ]
        text = "".join(parts)
    elif "ndjson" in name:
        text = "".join(f"{_json_text(value)}\n" for value in values)
        if not trailing_newline and text.endswith("\n"):
            text = text[:-1]
    else:
        payload = list(values)[0] if single else list(values)
        text = _json_text(payload)
    return encode_text(text, encoding)


def chunked(body: bytes, size: int) -> list[bytes]:
    """Split a body into fixed-size transport chunks."""

    width = max(1, int(size))
    raw = bytes(body)
    return [raw[index : index + width] for index in range(0, len(raw), width)] or [b""]


__all__ = ("chunked", "encode_body", "encode_text")
