"""Tonight's archive: take the dump, compress it, seal it with the key in
`ARCHIVE_KEY`, and put a copy in every destination.

The drill has to keep working, so the object is laid out the way
`restore_stream` takes one apart: a header, the compressed dump in sealed
frames, the sentinel and the trailer.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    CHUNK_BYTES,
    SENTINEL,
    NightRun,
    chunk_nonce,
    compress,
    decode_key,
    frame,
    key_id,
    night_report,
    object_name,
    seal,
    seal_trailer,
    stream_id,
    write_header,
)


def run_night(run: NightRun) -> Mapping[str, Any]:
    """Run one night and report how it went."""

    key = decode_key(run.env[run.key_config.env_var])
    dump = run.dump.read()
    payload = compress(dump)
    stream = stream_id(run.job, run.night, "archive")
    body = b"".join(
        frame(seal(key, chunk_nonce(stream, index), payload[start : start + CHUNK_BYTES]))
        for index, start in enumerate(range(0, len(payload), CHUNK_BYTES))
    )
    data = write_header(key_id(key), stream) + body + SENTINEL + seal_trailer(key, body)
    name = object_name(run.job, run.night, sealed=True)
    landed = []
    for destination in run.destinations.values():
        destination.begin(name)
        for start in range(0, len(data), CHUNK_BYTES):
            destination.write(name, data[start : start + CHUNK_BYTES])
        destination.finalize(name)
        destination.close(name)
        landed.append(destination.name)
    return night_report(run.night, "completed", object=name, destinations=landed,
                        source_bytes=len(dump), stored_bytes=len(data))
