"""The lineage pass: which exports of this pipeline hand out a personal field.

One row per export the field rules reach, keyed where the export is, whichever
step the personal field entered and whichever step the export ended up in. The
rows the audit already had are carried through untouched beside them.
"""

from __future__ import annotations

from typing import Any

from .protocol import (
    Finding,
    ModuleSet,
    baseline_findings,
    export_call,
    finding_at,
    sort_findings,
)
from .summaries import Pipeline, carries_here, carrying_names, settle


def scan(modules: ModuleSet) -> list[Finding]:
    """Every export of the pipeline that leaks, plus the rows already signed off."""

    pipeline = settle(modules)
    rows: list[Finding] = []
    for body in pipeline.bodies:
        rows.extend(_body_rows(body, pipeline))
    for name, tree in modules.iter_modules():
        rows.extend(baseline_findings(name, tree))
    return list(sort_findings(rows))


def _body_rows(body: Any, pipeline: Pipeline) -> list[Finding]:
    tainted = carrying_names(body.nodes, pipeline.given.get(body.step, ()), pipeline)
    return _leaks(body.module, body.nodes, tainted, pipeline)


def _leaks(name: str, nodes: Any, tainted: Any, pipeline: Pipeline) -> list[Finding]:
    rows: list[Finding] = []
    for node in nodes:
        export = export_call(node)
        if export is not None and carries_here(export.sent, tainted, pipeline):
            rows.append(finding_at(name, node))
    return rows
