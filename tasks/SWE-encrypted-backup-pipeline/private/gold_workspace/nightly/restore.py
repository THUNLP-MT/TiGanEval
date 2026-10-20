"""The drill helper: hand it one object out of a destination and get the
night's dump back.

The window holds both eras at once and the tier move left names that no longer
say what an object is, so what an object is comes from the object.
"""

from __future__ import annotations

from typing import Mapping

from .protocol import (
    ArchiveError,
    KeyUnavailable,
    decompress,
    parse_header,
    restore_stream,
)


def open_archive(name: str, data: bytes, keyring: Mapping[str, bytes]) -> bytes:
    """Open one object the drill pulled out of a destination.

    `keyring` is the ops key file as the laptop reads it: every key generation
    we have published, filed under the id `key_id` gives for it. An object that
    is neither an archive object nor one of the plain compressed dumps is refused
    rather than guessed at.
    """

    try:
        header = parse_header(bytes(data))
    except ArchiveError:
        return decompress(data)
    key = keyring.get(header.key_id)
    if key is None:
        raise KeyUnavailable(f"the key file lists no generation {header.key_id}")
    return decompress(restore_stream(data, key))
