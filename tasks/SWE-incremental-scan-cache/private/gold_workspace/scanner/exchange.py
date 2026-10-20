"""Cache export and import, used to start a fresh CI worker warm."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .protocol import CacheStore, RunContext, canonical_json
from .engine import open_entry


EXPORT_FORMAT_VERSION = 2


def export_cache(store: CacheStore, context: RunContext) -> bytes:
    """Serialise the cache so another worker can start warm."""

    return canonical_json(
        {
            "format_version": EXPORT_FORMAT_VERSION,
            "entries": store.export_entries(),
        }
    )


def import_cache(
    store: CacheStore,
    blob: bytes,
    context: RunContext,
) -> Mapping[str, Any]:
    """Merge a previously exported cache into this store, rejecting bad input.

    The warm-start step calls this inline in the scan job, before the run
    itself, so its outcome belongs in the mapping it returns: a bundle this
    worker cannot read or does not support is described there and the store is
    left as it was, rather than the whole job going down with an exception.
    """

    try:
        payload = json.loads(bytes(blob).decode("utf-8"))
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return {"accepted": 0, "rejected": "unreadable"}
    if not isinstance(payload, dict):
        return {"accepted": 0, "rejected": "unreadable"}
    if payload.get("format_version") != EXPORT_FORMAT_VERSION:
        return {"accepted": 0, "rejected": "unsupported_format_version"}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return {"accepted": 0, "rejected": "unreadable"}

    accepted = 0
    for key, value in sorted(entries.items()):
        if not isinstance(key, str) or not key or not isinstance(value, str):
            continue
        try:
            raw = bytes.fromhex(value)
        except ValueError:
            continue
        if open_entry(raw) is None:
            continue
        store.put(key, raw)
        accepted += 1
    return {"accepted": accepted}
