"""Incremental scan engine.

A cached entry is addressed by everything that can change its findings: the
file path, the exact bytes of the file, and the set of checks the configuration
actually runs. Entries carry their own integrity digest, so damaged or foreign
data is treated as unusable instead of served.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .protocol import (
    SECONDS_PER_DAY,
    CacheStore,
    RunContext,
    ScanOptions,
    SourceTree,
    canonical_json,
    effective_checks,
    run_checks,
    sorted_findings,
)


ENTRY_SCHEMA = 1
ENTRY_PREFIX = "e:"


def content_digest(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def cache_key(path: str, content_sha: str, checks: tuple[str, ...]) -> str:
    material = canonical_json(["scan-cache", ENTRY_SCHEMA, str(path), content_sha, list(checks)])
    return ENTRY_PREFIX + hashlib.sha256(material).hexdigest()


def _seal(body: Mapping[str, Any]) -> bytes:
    payload = dict(body)
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return canonical_json({"body": payload, "digest": digest})


def _open(raw: bytes | None) -> dict[str, Any] | None:
    """Return a verified entry body, or None when the bytes are not trustworthy."""

    if not isinstance(raw, (bytes, bytearray)):
        return None
    try:
        envelope = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(envelope, dict):
        return None
    body = envelope.get("body")
    digest = envelope.get("digest")
    if not isinstance(body, dict) or not isinstance(digest, str):
        return None
    if hashlib.sha256(canonical_json(body)).hexdigest() != digest:
        return None
    if body.get("schema") != ENTRY_SCHEMA:
        return None
    if not isinstance(body.get("path"), str):
        return None
    if not isinstance(body.get("content_sha"), str):
        return None
    if not isinstance(body.get("checks"), list):
        return None
    findings = body.get("findings")
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        return None
    if not isinstance(body.get("written_at"), (int, float)):
        return None
    return body


def open_entry(raw: bytes | None) -> dict[str, Any] | None:
    return _open(raw)


def build_entry(
    path: str,
    content_sha: str,
    checks: tuple[str, ...],
    findings: list[dict[str, Any]],
    now: float,
) -> bytes:
    return _seal(
        {
            "schema": ENTRY_SCHEMA,
            "path": str(path),
            "content_sha": content_sha,
            "checks": list(checks),
            "findings": findings,
            "written_at": float(now),
        }
    )


def _maintain(
    store: CacheStore,
    tree: SourceTree,
    context: RunContext,
    live_keys: set[str],
) -> None:
    """Discard unusable, orphaned, and expired non-current generations, then cap."""

    live_paths = set(tree.paths())
    expiry_days = float(context.cache_expiry_days)
    survivors: dict[str, float] = {}
    for key in store.keys():
        if key in live_keys:
            continue
        body = _open(store.get(key))
        if body is None:
            store.delete(key)
            continue
        if str(body["path"]) not in live_paths:
            store.delete(key)
            continue
        written_at = float(body["written_at"])
        if expiry_days >= 0 and (float(context.now) - written_at) > expiry_days * SECONDS_PER_DAY:
            store.delete(key)
            continue
        survivors[key] = written_at

    limit = int(context.cache_size_limit_bytes)
    if limit < 0:
        return
    while store.total_bytes() > limit:
        if survivors:
            victim = min(survivors, key=lambda key: (survivors[key], key))
            del survivors[victim]
        elif live_keys:
            victim = sorted(live_keys)[0]
            live_keys.discard(victim)
        else:
            break
        store.delete(victim)


def scan(
    tree: SourceTree,
    store: CacheStore,
    options: ScanOptions,
    context: RunContext,
) -> Mapping[str, Any]:
    """Analyse the tree, reusing only cached findings that are still valid."""

    checks = effective_checks(options)
    paths = tree.paths()
    findings: list[dict[str, Any]] = []
    reused: list[str] = []
    live_keys: set[str] = set()
    hits = 0
    misses = 0

    for path in paths:
        content = tree.read_text(path)
        content_sha = content_digest(content)
        key = cache_key(path, content_sha, checks)
        live_keys.add(key)
        body = _open(store.get(key)) if context.incremental else None
        if (
            body is not None
            and str(body["path"]) == path
            and str(body["content_sha"]) == content_sha
            and list(body["checks"]) == list(checks)
        ):
            findings.extend(dict(row) for row in body["findings"])
            reused.append(path)
            hits += 1
            continue
        if body is None and context.incremental and store.get(key) is not None:
            store.delete(key)
        misses += 1
        produced = [
            finding.as_dict() for finding in run_checks(path, content, options)
        ]
        findings.extend(produced)
        if context.incremental:
            store.put(key, build_entry(path, content_sha, checks, produced, context.now))

    if context.incremental:
        _maintain(store, tree, context, live_keys)

    return {
        "findings": sorted_findings(findings),
        "cache_info": {
            "total_files": len(paths),
            "cache_hits": hits,
            "cache_misses": misses,
            "reused_paths": list(reused),
            "cached_entry_count": store.entry_count(),
            "cache_bytes": store.total_bytes(),
        },
    }
