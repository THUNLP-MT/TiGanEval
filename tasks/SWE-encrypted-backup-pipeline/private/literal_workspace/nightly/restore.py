"""The drill helper: hand it one object out of the vault and get the night's
dump back.

The window holds two kinds of object, so the sealed ones go through the read
path first and the plain `.sql.gz` ones straight to the decompressor.
"""

from __future__ import annotations

from typing import Mapping

from .protocol import KeyUnavailable, decompress, parse_header, restore_stream


def open_archive(name: str, data: bytes, keyring: Mapping[str, bytes]) -> bytes:
    """Open one object the drill pulled out of a destination."""

    if not name.endswith(".enc"):
        return decompress(data)
    header = parse_header(bytes(data))
    key = keyring.get(header.key_id)
    if key is None:
        raise KeyUnavailable(f"the key file lists no generation {header.key_id}")
    return decompress(restore_stream(data, key))
