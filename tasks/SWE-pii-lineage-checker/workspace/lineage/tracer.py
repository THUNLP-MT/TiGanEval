"""First cut at the lineage pass, written the morning the audit finding landed.

It reads one module at a time and flags an export when something spelled like a
personal field turns up inside the call.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from .protocol import Finding, ModuleSet, export_call

#: What a personal-looking name reads like in the pipeline's own source.
PERSONAL_NAME = re.compile(r"email|ssn|phone|birth|subject|personal", re.IGNORECASE)


def scan(modules: ModuleSet) -> list[Finding]:
    """Every export this pass flags, module by module."""

    rows: list[Finding] = []
    for name, tree in modules.iter_modules():
        rows.extend(_module_rows(name, tree))
    return rows


def _module_rows(name: str, tree: Any) -> list[Finding]:
    rows: list[Finding] = []
    for node in ast.walk(tree):
        export = export_call(node)
        if export is None:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and PERSONAL_NAME.search(inner.id):
                rows.append(
                    Finding(
                        module=str(name),
                        line=int(node.lineno),
                        col=int(node.col_offset),
                        check=export.check,
                        dataset=export.dataset,
                    )
                )
    return rows
