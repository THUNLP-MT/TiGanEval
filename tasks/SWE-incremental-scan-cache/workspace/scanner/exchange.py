"""Cache export and import, used to start a fresh CI worker warm."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .protocol import CacheStore, RunContext, canonical_json


def export_cache(store: CacheStore, context: RunContext) -> bytes:
    """Serialise the cache so another worker can start warm."""

    return canonical_json({"entries": store.export_entries()})


def import_cache(
    store: CacheStore,
    blob: bytes,
    context: RunContext,
) -> Mapping[str, Any]:
    """Merge a previously exported cache into this store.

    The warm-start step calls this inline in the scan job, before the run
    itself, so whatever this call has to say about the bundle belongs in the
    mapping it returns: an exception here takes the whole job down and the
    worker produces no report that night.
    """

    payload = json.loads(bytes(blob).decode("utf-8"))
    entries = dict(payload.get("entries", {}))
    for key, value in entries.items():
        store.put(str(key), bytes.fromhex(str(value)))
    return {"accepted": len(entries)}
