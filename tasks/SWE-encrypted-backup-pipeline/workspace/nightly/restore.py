"""The drill helper: hand it one object out of the vault and get the night's
dump back.

The job on this host has only ever written a `.sql.gz`, so this is the
runbook's second step and nothing else.
"""

from __future__ import annotations

from typing import Mapping

from .protocol import decompress


def open_archive(name: str, data: bytes, keyring: Mapping[str, bytes]) -> bytes:
    """Open one object the drill pulled out of a destination.

    `keyring` is the ops key file as the laptop reads it: every key generation
    we have published, filed under the id `key_id` gives for it.
    """

    return decompress(data)
