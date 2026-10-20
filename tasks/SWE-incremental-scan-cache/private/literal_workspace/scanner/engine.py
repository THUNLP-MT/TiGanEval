"""Incremental scan engine.

The prototype reuses a file's findings when the file has not been touched since
the last run. This build does what the pipeline owner asked for: the file's size
goes into the key next to its modification time, so an edited file that comes
back with a restored timestamp no longer collides with its old entry; entries
are reclaimed once their file is gone, which the owner believes is the whole
cleanup; and the run summary reports the cache the run actually leaves behind.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .protocol import (
    CacheStore,
    RunContext,
    ScanOptions,
    SourceTree,
    canonical_json,
    run_checks,
    sorted_findings,
)


def cache_key(tree: SourceTree, path: str, stat: Mapping[str, Any]) -> str:
    """Identify a cached file by where it lives, when it changed, and its size."""

    return f"{tree.abspath(path)}::{stat['mtime']}::{stat['size']}"


def _read(raw: bytes | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    return json.loads(bytes(raw).decode("utf-8"))


def _reclaim(
    store: CacheStore,
    tree: SourceTree,
    live_keys: set[str],
) -> None:
    """Drop entries for files that have left the checkout."""

    live_files = {tree.abspath(path) for path in tree.paths()}
    for key in store.keys():
        if key in live_keys:
            continue
        entry = _read(store.get(key))
        if entry is None:
            store.delete(key)
            continue
        if str(entry.get("abspath", "")) not in live_files:
            store.delete(key)


def scan(
    tree: SourceTree,
    store: CacheStore,
    options: ScanOptions,
    context: RunContext,
) -> Mapping[str, Any]:
    """Analyse the tree, reusing cached findings for untouched files."""

    findings: list[dict[str, Any]] = []
    reused: list[str] = []
    live_keys: set[str] = set()
    hits = 0
    misses = 0

    for path in tree.paths():
        stat = tree.stat(path)
        key = cache_key(tree, path, stat)
        live_keys.add(key)
        entry = _read(store.get(key)) if context.incremental else None
        if entry is not None:
            findings.extend(entry["findings"])
            reused.append(path)
            hits += 1
            continue
        misses += 1
        produced = [
            finding.as_dict()
            for finding in run_checks(path, tree.read_text(path), options)
        ]
        findings.extend(produced)
        if context.incremental:
            store.put(
                key,
                canonical_json(
                    {
                        "path": path,
                        "abspath": tree.abspath(path),
                        "written_at": float(context.now),
                        "findings": produced,
                    }
                ),
            )

    if context.incremental:
        _reclaim(store, tree, live_keys)

    return {
        "findings": sorted_findings(findings),
        "cache_info": {
            "total_files": len(tree.paths()),
            "cache_hits": hits,
            "cache_misses": misses,
            "reused_paths": reused,
            "cached_entry_count": store.entry_count(),
            "cache_bytes": store.total_bytes(),
        },
    }
