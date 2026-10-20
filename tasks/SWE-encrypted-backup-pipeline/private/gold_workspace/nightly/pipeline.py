"""Tonight's archive: take the dump, compress it, seal it, and publish it to
every destination only once every destination can be read back.

The key is resolved and checked before anything is opened, so a night that has
no usable key never touches the vault. Nothing is finalized until the object
each destination is holding has been through the runbook's two steps, and a
night that cannot get that far leaves the window exactly as it found it.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import (
    CHUNK_BYTES,
    SENTINEL,
    ArchiveError,
    DestinationRefused,
    KeyUnavailable,
    NightRun,
    chunk_nonce,
    compress,
    decode_key,
    decompress,
    frame,
    key_id,
    night_report,
    object_name,
    restore_stream,
    seal,
    seal_trailer,
    stream_id,
    write_header,
)


class NotReadable(Exception):
    """What is in the destination did not come back through the read path."""


def resolve_key(run: NightRun) -> bytes:
    """The one key this night is configured to use, or nothing at all.

    Two configured sources are two answers, and the one an operator holds a
    year later is whichever the job happened to prefer, so a configuration that
    names more than one place is not a configuration.
    """

    config = run.key_config
    sources = config.sources
    if not sources:
        raise KeyUnavailable("the job configuration names no key source")
    if len(sources) > 1:
        raise KeyUnavailable(f"the job configuration names {len(sources)} key sources: "
                             f"{', '.join(sources)}")
    if config.env_var:
        if config.env_var not in run.env:
            raise KeyUnavailable(f"{config.env_var} is not set")
        return decode_key(run.env[config.env_var])
    if config.key_file not in run.files:
        raise KeyUnavailable(f"{config.key_file} is not on this host")
    return decode_key(run.files[config.key_file])


def build_object(key: bytes, job: str, night: str, destination: str, payload: bytes) -> bytes:
    """One archive object: the compressed dump, chunked, sealed and framed."""

    stream = stream_id(job, night, destination)
    body = b"".join(
        frame(seal(key, chunk_nonce(stream, index), payload[start : start + CHUNK_BYTES]))
        for index, start in enumerate(range(0, len(payload), CHUNK_BYTES))
    )
    return write_header(key_id(key), stream) + body + SENTINEL + seal_trailer(key, body)


def reads_back(destination: Any, name: str, key: bytes, dump: bytes) -> bool:
    """Take what the destination is holding through the runbook's two steps."""

    try:
        return decompress(restore_stream(destination.read_object(name), key)) == dump
    except (ArchiveError, KeyError):
        return False


def run_night(run: NightRun) -> Mapping[str, Any]:
    """Run one night and report what is actually recoverable afterwards."""

    try:
        key = resolve_key(run)
    except KeyUnavailable as exc:
        return night_report(run.night, "failed", reason=str(exc), object=None, destinations=[])

    dump = run.dump.read()
    payload = compress(dump)
    name = object_name(run.job, run.night, sealed=True)
    opened: list[Any] = []
    try:
        for destination in run.destinations.values():
            data = build_object(key, run.job, run.night, destination.name, payload)
            destination.begin(name)
            opened.append(destination)
            for start in range(0, len(data), CHUNK_BYTES):
                destination.write(name, data[start : start + CHUNK_BYTES])
            if not reads_back(destination, name, key, dump):
                raise NotReadable(f"{destination.name} is not holding tonight's dump")
    except (DestinationRefused, NotReadable, ArchiveError) as exc:
        for destination in opened:
            destination.delete(name)
            destination.close(name)
        return night_report(run.night, "incomplete", reason=str(exc), object=None,
                            destinations=[], source_bytes=len(dump))
    for destination in opened:
        destination.finalize(name)
        destination.close(name)
    return night_report(run.night, "completed", object=name,
                        destinations=[destination.name for destination in opened],
                        key=key_id(key), source_bytes=len(dump), stored_bytes=len(payload))
