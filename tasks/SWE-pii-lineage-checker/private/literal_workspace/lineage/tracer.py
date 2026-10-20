"""The lineage pass, built to the plan in the audit mail.

Mark the locals a personal field is assigned into, then flag an export when one
of those names turns up inside it. The rows the audit already had are carried
through so the gate stays green.
"""

from __future__ import annotations

import ast
from typing import Any

from .protocol import (
    Finding,
    ModuleSet,
    assignments,
    baseline_findings,
    body_nodes,
    carries,
    export_call,
    finding_at,
)


def scan(modules: ModuleSet) -> list[Finding]:
    """Every export this pass flags, module by module."""

    rows: list[Finding] = []
    for name, tree in modules.iter_modules():
        rows.extend(baseline_findings(name, tree))
        rows.extend(_module_rows(name, tree))
    return rows


def _module_rows(name: str, tree: Any) -> list[Finding]:
    rows: list[Finding] = []
    for statements in _bodies(tree):
        nodes = body_nodes(statements)
        marked = {
            bound for bound, value in assignments(nodes) if carries(value, ())
        }
        for node in nodes:
            export = export_call(node)
            if export is None:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name) and inner.id in marked:
                    rows.append(finding_at(name, node))
    return rows


def _bodies(tree: Any) -> list[list[Any]]:
    bodies: list[list[Any]] = [list(tree.body)]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bodies.append(list(node.body))
    return bodies
