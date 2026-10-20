'Deterministic response bodies and read programs for the reader project.'

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from ..workspace.client.protocol import READ_AHEAD_SLACK_BYTES, RECORD_SEPARATOR
from ..workspace.client.wire import encode_body


SLACK_BYTES = READ_AHEAD_SLACK_BYTES
PACKET_SIZES = (1, 3, 7, 4096)
PACKET_SIZE_PHRASE = "1, 3, 7 and 4096"

_REGIONAL_VALUES = [
    {"name": "café", "region": "eu"},
    {"name": "über", "region": "eu"},
    {"name": "naïve", "region": "eu"},
]
_WORDS = ("harbor", "lantern", "cinder", "meadow", "quarry", "willow", "kestrel", "summit")


def build_values(offset: int, count: int) -> list[Any]:
    'Return one deterministic list of JSON values.'

    values: list[Any] = []
    for index in range(count):
        slot = (offset + index) % 6
        word = _WORDS[(offset + index) % len(_WORDS)]
        if slot == 0:
            values.append({"id": 1000 + index, "name": f"{word}-é☃", "tags": [word, index]})
        elif slot == 1:
            values.append([index, index * 3, {"deep": {"k": word}}])
        elif slot == 2:
            values.append(f"{word} value {index}")
        elif slot == 3:
            values.append(index * 7 - 3)
        elif slot == 4:
            values.append(None if index % 2 else True)
        else:
            values.append({"nested": {"list": [1, 2, {"z": f"ü{index}"}], "flag": False}})
    return values


def _text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def value_offsets(values: Sequence[Any], media_type: str, encoding: str) -> list[int]:
    "Boundary bytes each value's complete framing needs."

    name = str(media_type).lower()
    total = len(encode_body(values, media_type, encoding=encoding))
    offsets: list[int] = []
    if "ndjson" in name:
        for index in range(len(values)):
            offsets.append(len(encode_body(values[: index + 1], media_type, encoding=encoding)))
        return offsets
    if name.endswith("json-seq"):
        separator = len(RECORD_SEPARATOR.encode(encoding)) if encoding != "utf-8" else 1
        for index in range(len(values)):
            prefix = len(encode_body(values[: index + 1], media_type, encoding=encoding))
            offsets.append(total if index == len(values) - 1 else prefix + separator)
        return offsets
    running = "["
    for index, value in enumerate(values):
        running += ("," if index else "") + _text(value)
        offsets.append(len(running.encode(encoding)))
    return offsets


def value_minimum_offsets(
    values: Sequence[Any], media_type: str, encoding: str
) -> list[int]:
    'Minimum metered bytes that physically contain each JSON value.'

    name = str(media_type).lower()
    if "ndjson" in name or name.endswith("json-seq"):
        terminator = len("\n".encode(encoding)) - len("".encode(encoding))
        return [
            len(encode_body(values[: index + 1], media_type, encoding=encoding))
            - terminator
            for index in range(len(values))
        ]
    return value_offsets(values, media_type, encoding)


def _case(
    label: str,
    scenario: str,
    situation: str,
    content_type: str,
    body: bytes,
    *,
    chunk_size: int = 5,
    streaming: bool = True,
    mode: str = "full",
    values: Sequence[Any] | None = None,
    error: str | None = None,
    prefix: Sequence[Any] | None = None,
    prefix_of: Sequence[Any] | None = None,
    offsets: Sequence[int] | None = None,
    minimum_offsets: Sequence[int] | None = None,
    fault: str | None = None,
    refusal: str | None = None,
    accepted: str | None = None,
    yielded: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "read",
        "label": label,
        "scenario": scenario,
        "situation": situation,
        "content_type": content_type,
        "body_hex": bytes(body).hex(),
        "chunk_size": int(chunk_size),
        "streaming": bool(streaming),
        "mode": mode,
        "expect": {
            "values": None if values is None else list(values),
            "error": error,
            "prefix": None if prefix is None else list(prefix),
            "prefix_of": None if prefix_of is None else list(prefix_of),
            "offsets": None if offsets is None else list(offsets),
            "minimum_offsets": (
                None if minimum_offsets is None else list(minimum_offsets)
            ),


            "fault": fault,
            "refusal": refusal,
            "accepted": accepted,
            "yielded": yielded,
        },
    }


_MEDIA_FAMILIES = (
    ("json-document", "application/json", False),
    ("vendor-json-document", "application/vnd.readings.v2+json", False),
    ("single-json-value", "application/json", True),
    ("ndjson-feed", "application/ndjson", False),
    ("x-ndjson-feed", "application/x-ndjson", False),
    ("json-seq-feed", "application/json-seq", False),
)


FAMILY_PHRASES: Mapping[str, str] = {
    "json-document": "the json document",
    "vendor-json-document": "the vendor +json document",
    "single-json-value": "the single-value json document",
    "ndjson-feed": "the ndjson feed",
    "x-ndjson-feed": "the x-ndjson feed",
    "json-seq-feed": "the json-seq feed",
    "top-level-number": "the top-level JSON number",
    "top-level-string": "the top-level JSON string",
    "top-level-boolean": "the top-level JSON boolean",
    "top-level-null": "the top-level JSON null",
    "cr-only-ndjson-feed": "the ndjson feed delimited by carriage returns",
}


def _chunking(offset: int, scale: int) -> list[dict[str, Any]]:
    values = build_values(offset, 4 + 2 * scale)
    cases: list[dict[str, Any]] = []
    for family, media_type, single in _MEDIA_FAMILIES:
        expected = values[:1] if single else values
        body = encode_body(values, media_type, single=single)
        for chunk_size in PACKET_SIZES:
            cases.append(
                _case(
                    f"{family}-at-{chunk_size}-byte-packets",
                    "chunking",
                    f"{FAMILY_PHRASES[family]} arriving in {chunk_size}-byte packets",
                    media_type,
                    body,
                    chunk_size=chunk_size,
                    values=expected,
                )
            )
    return cases


def _release_chunking_boundaries(offset: int, scale: int) -> list[dict[str, Any]]:
    'Release-only cross-products of already published JSON wire rules.'

    scalar_values = (
        ("top-level-number", offset * 7 - 3),
        ("top-level-string", f"{_WORDS[offset % len(_WORDS)]}-é☃"),
        ("top-level-boolean", True),
        ("top-level-null", None),
    )
    cases: list[dict[str, Any]] = []
    for family, value in scalar_values:
        body = encode_body([value], "application/json", single=True)
        for chunk_size in PACKET_SIZES:
            cases.append(
                _case(
                    f"{family}-at-{chunk_size}-byte-packets",
                    "chunking",
                    f"{FAMILY_PHRASES[family]} arriving in {chunk_size}-byte packets",
                    "application/json",
                    body,
                    chunk_size=chunk_size,
                    values=[value],
                )
            )

    values = build_values(offset + 4, 3 + scale)
    cr_body = ("\r".join(_text(value) for value in values) + "\r").encode("utf-8")
    for chunk_size in PACKET_SIZES:
        family = "cr-only-ndjson-feed"
        cases.append(
            _case(
                f"{family}-at-{chunk_size}-byte-packets",
                "chunking",
                f"{FAMILY_PHRASES[family]} arriving in {chunk_size}-byte packets",
                "application/ndjson",
                cr_body,
                chunk_size=chunk_size,
                values=values,
            )
        )
    return cases


def _framing(offset: int, scale: int) -> list[dict[str, Any]]:
    values = build_values(offset, 3)
    ndjson = encode_body(values, "application/ndjson")
    seq = encode_body(values, "application/json-seq")
    document = encode_body(values, "application/json")
    first_line = encode_body(values[:1], "application/ndjson")
    ndjson_record_with_trailing_data = (
        encode_body(
            values[:1], "application/ndjson", trailing_newline=False
        )
        + b"X\n"
        + encode_body(values[1:], "application/ndjson")
    )
    sequence_record_with_trailing_data = (
        encode_body(
            values[:1], "application/json-seq", trailing_newline=False
        )
        + b"X"
        + encode_body(values[1:], "application/json-seq")
    )
    return [
        _case(
            "plain-text-body",
            "framing",
            "a text/plain body sent instead of the feed",
            "text/plain",
            document,
            error="DecodingError",
            accepted="unsupported_media_type_accepted",
        ),
        _case(
            "svg-plus-json-body",
            "framing",
            "an image/svg+json body sent instead of the feed",
            "image/svg+json",
            document,
            error="DecodingError",
            accepted="unsupported_media_type_accepted",
        ),
        _case(
            "html-error-page",
            "framing",
            "an HTML error page sent instead of the feed",
            "text/html; charset=utf-8",
            document,
            error="DecodingError",
            accepted="unsupported_media_type_accepted",
        ),
        _case(
            "vendor-plus-json-feed",
            "framing",
            "a vendor +json media type carrying a charset parameter",
            "application/vnd.acme+json; charset=utf-8",
            document,
            values=values,
            refusal="media_type_parameters_mishandled",
        ),
        _case(
            "uppercase-ndjson-with-charset",
            "framing",
            "an ndjson media type written in capitals with a charset parameter",
            "APPLICATION/NDJSON; charset=UTF-8",
            ndjson,
            values=values,
            refusal="media_type_parameters_mishandled",
        ),
        _case(
            "empty-json-document",
            "framing",
            "a json document with no JSON text in it",
            "application/json",
            b"   \n  ",
            error="DecodingError",
            accepted="empty_document_accepted",
        ),
        _case(
            "json-document-trailing-data",
            "framing",
            "a json document with data after the end of the JSON text",
            "application/json",
            document + b" oops",
            error="DecodingError",
            prefix_of=values,
            accepted="trailing_data_accepted",
        ),
        _case(
            "json-document-cut-off",
            "framing",
            "a json document that was cut off half way",
            "application/json",
            document[: len(document) // 2],
            error="DecodingError",
            prefix_of=values,
            accepted="truncated_body_accepted",
        ),
        _case(
            "json-array-missing-separator",
            "framing",
            "a json array with two readings and no comma between them",
            "application/json",
            b"[1 2]",
            error="DecodingError",
            prefix_of=[1],
            accepted="malformed_document_accepted",
        ),
        _case(
            "json-array-repeated-separator",
            "framing",
            "a json array with two commas between consecutive readings",
            "application/json",
            b"[1,,2]",
            error="DecodingError",
            prefix_of=[1],
            accepted="malformed_document_accepted",
        ),
        _case(
            "json-array-leading-separator",
            "framing",
            "a json array with a comma before its first reading",
            "application/json",
            b"[,1]",
            error="DecodingError",
            prefix=[],
            accepted="malformed_document_accepted",
        ),
        _case(
            "json-array-trailing-separator",
            "framing",
            "a json array with a comma after its last reading",
            "application/json",
            b"[1,]",
            error="DecodingError",
            prefix_of=[1],
            accepted="malformed_document_accepted",
        ),
        _case(
            "ndjson-last-line-cut-off",
            "framing",
            "an ndjson feed whose last line was cut off",
            "application/ndjson",
            first_line + b'{"unfinished": [1, 2',
            error="DecodingError",
            prefix=values[:1],
            accepted="truncated_body_accepted",
        ),
        _case(
            "ndjson-record-with-trailing-data",
            "framing",
            "an ndjson line with data after its JSON value",
            "application/ndjson",
            ndjson_record_with_trailing_data,
            error="DecodingError",
            prefix=[],
            accepted="trailing_data_accepted",
            yielded="invalid_record_value_yielded",
        ),
        _case(
            "ndjson-empty-line-first",
            "framing",
            "an ndjson feed with an empty line before the first record",
            "application/ndjson",
            b"\n\n" + ndjson.replace(b"\n", b"\r\n") + b"\n   \n",
            values=values,
            refusal="blank_record_mishandled",
        ),
        _case(
            "sequence-without-separator",
            "framing",
            "a json-seq body whose first record has no separator in front of it",
            "application/json-seq",
            seq[1:],
            error="DecodingError",
            accepted="unframed_sequence_accepted",
        ),
        _case(
            "sequence-empty-body",
            "framing",
            "a json-seq body with nothing in it at all",
            "application/json-seq",
            b"",
            values=[],
            refusal="empty_stream_mishandled",
        ),
        _case(
            "sequence-whitespace-body",
            "framing",
            "a json-seq body holding nothing but whitespace",
            "application/json-seq",
            b"  \n ",
            values=[],
            refusal="empty_stream_mishandled",
        ),
        _case(
            "sequence-last-record-cut-off",
            "framing",
            "a json-seq body whose last record was cut off",
            "application/json-seq",
            seq + RECORD_SEPARATOR.encode("utf-8") + b"\n",
            error="DecodingError",
            prefix=values,
            accepted="truncated_body_accepted",
        ),
        _case(
            "sequence-record-with-trailing-data",
            "framing",
            "a json-seq record with data after its JSON value and before the next separator",
            "application/json-seq",
            sequence_record_with_trailing_data,
            error="DecodingError",
            prefix=[],
            accepted="trailing_data_accepted",
            yielded="invalid_record_value_yielded",
        ),
        _case(
            "sequence-empty-record-first",
            "framing",
            "a json-seq feed with an empty record before the first record",
            "application/json-seq",
            RECORD_SEPARATOR.encode("utf-8") + b"\n" + seq,
            values=values,
            refusal="blank_record_mishandled",
        ),
    ]


def _intercepted(offset: int, scale: int) -> list[dict[str, Any]]:
    'Responses that reached the collector through something in the way.'

    values = build_values(offset, 3)
    word = _WORDS[offset % len(_WORDS)]
    sidecar = encode_body(
        [
            {"event": "upstream_timeout", "site": word},
            {"event": "retry_scheduled", "site": word},
        ],
        "application/ndjson",
    )
    seq = encode_body(values, "application/json-seq")
    return [
        _case(
            "sidecar-ndjson-under-text-media-type",
            "framing",
            "an ndjson body under a text/ndjson header from the sidecar in front of a gateway",
            "text/ndjson",
            sidecar,
            error="DecodingError",
            accepted="unsupported_media_type_accepted",
        ),
        _case(
            "sequence-tail-of-a-lost-record",
            "framing",
            "a json-seq body that begins with the end of a record we never received",
            "application/json-seq",
            b"\n" + seq,
            error="DecodingError",
            accepted="unframed_sequence_accepted",
        ),
    ]


def _flow(offset: int, scale: int) -> list[dict[str, Any]]:
    values = build_values(offset, 8 + 2 * scale)
    cases: list[dict[str, Any]] = []
    for family, media_type in (
        ("ndjson-feed", "application/ndjson"),
        ("json-seq-feed", "application/json-seq"),
        ("json-document", "application/json"),
    ):
        body = encode_body(values, media_type)
        cases.append(
            _case(
                f"slow-producer-{family}",
                "flow",
                f"a slow producer sending {FAMILY_PHRASES[family]} in 4-byte packets",
                media_type,
                body,
                chunk_size=4,
                values=values,
                offsets=value_offsets(values, media_type, "utf-8"),
                minimum_offsets=value_minimum_offsets(values, media_type, "utf-8"),
            )
        )
    return cases


def _release_flow_boundaries(offset: int, scale: int) -> list[dict[str, Any]]:
    'Exercise the flow invariant at packet sizes absent from public traces.'

    values = build_values(offset + 7, 8 + 2 * scale)
    cases: list[dict[str, Any]] = []
    for family, media_type in (
        ("ndjson-feed", "application/ndjson"),
        ("json-seq-feed", "application/json-seq"),
        ("json-document", "application/json"),
    ):
        body = encode_body(values, media_type)
        for chunk_size in (2, 9):
            cases.append(
                _case(
                    f"release-slow-producer-{family}-at-{chunk_size}-byte-packets",
                    "flow",
                    f"a slow producer sending {FAMILY_PHRASES[family]} in "
                    f"{chunk_size}-byte packets",
                    media_type,
                    body,
                    chunk_size=chunk_size,
                    values=values,
                    offsets=value_offsets(values, media_type, "utf-8"),
                    minimum_offsets=value_minimum_offsets(values, media_type, "utf-8"),
                )
            )
    return cases


def _lifecycle(offset: int, scale: int) -> list[dict[str, Any]]:
    values = build_values(offset, 6)
    body = encode_body(values, "application/ndjson")
    return [
        _case(
            "read-to-the-end",
            "lifecycle",
            "reading a feed to the end",
            "application/ndjson",
            body,
            chunk_size=6,
            values=values,
        ),
        _case(
            "read-a-second-time",
            "lifecycle",
            "reading a streaming feed a second time",
            "application/ndjson",
            body,
            chunk_size=6,
            mode="twice",
            values=values,
        ),
        _case(
            "stop-after-the-first-record",
            "lifecycle",
            "stopping after the first record",
            "application/ndjson",
            body,
            chunk_size=6,
            mode="early_break",
            values=values,
        ),
        _case(
            "re-read-a-feed-in-memory",
            "lifecycle",
            "re-reading a feed that is already in memory",
            "application/ndjson",
            body,
            chunk_size=6,
            streaming=False,
            mode="twice",
            values=values,
        ),
    ]


def _release_lifecycle_boundaries(offset: int, scale: int) -> list[dict[str, Any]]:
    'Repeat-read the other documented formats while already in memory.'

    values = build_values(offset + 13, 4 + scale)
    cases: list[dict[str, Any]] = []
    for family, media_type in (
        ("json-document", "application/json"),
        ("json-seq-feed", "application/json-seq"),
    ):
        cases.append(
            _case(
                f"re-read-in-memory-{family}",
                "lifecycle",
                f"re-reading {FAMILY_PHRASES[family]} already held in memory",
                media_type,
                encode_body(values, media_type),
                chunk_size=5,
                streaming=False,
                mode="twice",
                values=values,
            )
        )
    return cases


def _encoding(offset: int, scale: int) -> list[dict[str, Any]]:
    values = build_values(offset, 5)
    return [
        _case(
            "declared-utf-16-le-feed",
            "encoding",
            "a feed whose header declares charset=utf-16-le",
            "application/ndjson; charset=utf-16-le",
            encode_body(values, "application/ndjson", encoding="utf-16-le"),
            chunk_size=3,
            values=values,
            fault="declared_charset_ignored",
        ),
        _case(
            "detected-utf-16-document",
            "encoding",
            "a document with no declared charset whose leading bytes are UTF-16",
            "application/json",
            encode_body(values, "application/json", encoding="utf-16"),
            chunk_size=3,
            values=values,
            fault="encoding_detection_wrong",
        ),
        _case(
            "detected-utf-32-sequence",
            "encoding",
            "a json-seq feed with no declared charset whose leading bytes are UTF-32",
            "application/json-seq",
            encode_body(values, "application/json-seq", encoding="utf-32"),
            chunk_size=5,
            values=values,
            fault="encoding_detection_wrong",
        ),
        _case(
            "byte-order-marked-feed",
            "encoding",
            "a feed that begins with a byte-order mark",
            "application/ndjson; charset=utf-8",
            encode_body(values, "application/ndjson", encoding="utf-8-sig"),
            chunk_size=3,
            values=values,
            fault="byte_order_mark_mishandled",
        ),
        _case(
            "declared-latin-1-feed",
            "encoding",
            "a regional feed whose header declares charset=latin-1",
            "application/ndjson; charset=latin-1",
            encode_body(_REGIONAL_VALUES, "application/ndjson", encoding="latin-1"),
            chunk_size=4,
            values=_REGIONAL_VALUES,
            fault="declared_charset_ignored",
        ),
        _case(
            "charset-that-names-no-codec",
            "encoding",
            "a document whose header names a charset no codec answers to",
            "application/json; charset=definitely-not-a-codec",
            encode_body(values, "application/json"),
            error="DecodingError",
            fault="invalid_charset_mishandled",
        ),
        _case(
            "declared-utf-16-be-document",
            "encoding",
            "a document whose header declares charset=utf-16-be",
            "application/json; charset=utf-16-be",
            encode_body(values, "application/json", encoding="utf-16-be"),
            chunk_size=7,
            values=values,
            fault="declared_charset_ignored",
        ),
    ]


def _boundary(offset: int, scale: int) -> list[dict[str, Any]]:
    return _chunking(offset, scale) + _encoding(offset, scale)


SCENARIO_BUILDERS = {
    "boundary": _boundary,
    "chunking": _chunking,
    "framing": _framing,
    "intercepted": _intercepted,
    "flow": _flow,
    "lifecycle": _lifecycle,
    "encoding": _encoding,
    "release-chunking-boundaries": _release_chunking_boundaries,
    "release-flow-boundaries": _release_flow_boundaries,
    "release-lifecycle-boundaries": _release_lifecycle_boundaries,
}


def build_program(profile: str, offset: int, scale: int) -> list[dict[str, Any]]:
    if profile == "release":
        program: list[dict[str, Any]] = []


        for scenario in (
            "chunking",
            "release-chunking-boundaries",
            "framing",
            "intercepted",
            "flow",
            "release-flow-boundaries",
            "lifecycle",
            "release-lifecycle-boundaries",
            "encoding",
        ):
            program.extend(SCENARIO_BUILDERS[scenario](offset, scale))
        return program
    builder = SCENARIO_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown read program profile: {profile}")
    return builder(offset, scale)


def driver_events(program: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Strip author-side expectations before the program reaches the reader.'

    return [
        {key: value for key, value in dict(case).items() if key != "expect"}
        for case in program
    ]


__all__ = (
    "FAMILY_PHRASES",
    "PACKET_SIZES",
    "PACKET_SIZE_PHRASE",
    "SCENARIO_BUILDERS",
    "SLACK_BYTES",
    "build_program",
    "build_values",
    "driver_events",
    "value_offsets",
    "value_minimum_offsets",
)
