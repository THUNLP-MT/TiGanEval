"""Incremental scan engine.

The prototype reuses a file's findings when the file has not been touched since
the last run, which is what made the nightly pipeline fast enough to ship.
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
    """Identify a cached file by where it lives and when it changed."""

    return f"{tree.abspath(path)}::{stat['mtime']}"


def scan(
    tree: SourceTree,
    store: CacheStore,
    options: ScanOptions,
    context: RunContext,
) -> Mapping[str, Any]:
    """Analyse the tree, reusing cached findings for untouched files."""

    inventory_entries = store.entry_count()
    inventory_bytes = store.total_bytes()

    findings: list[dict[str, Any]] = []
    reused: list[str] = []
    hits = 0
    misses = 0

    for path in tree.paths():
        stat = tree.stat(path)
        key = cache_key(tree, path, stat)
        raw = store.get(key) if context.incremental else None
        if raw is not None:
            payload = json.loads(raw.decode("utf-8"))
            findings.extend(payload["findings"])
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
            store.put(key, canonical_json({"path": path, "findings": produced}))

    return {
        "findings": sorted_findings(findings),
        "cache_info": {
            "total_files": len(tree.paths()),
            "cache_hits": hits,
            "cache_misses": misses,
            "reused_paths": reused,
            "cached_entry_count": inventory_entries,
            "cache_bytes": inventory_bytes,
        },
    }
