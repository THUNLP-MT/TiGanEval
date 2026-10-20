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
    itself, so its outcome belongs in the mapping it returns: a bundle this
    worker cannot read or does not support is described there and the store is
    left as it was, rather than the whole job going down with an exception.
    """

    payload = json.loads(bytes(blob).decode("utf-8"))
    entries = dict(payload.get("entries", {}))
    for key, value in entries.items():
        store.put(str(key), bytes.fromhex(str(value)))
    return {"accepted": len(entries)}
