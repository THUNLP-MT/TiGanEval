from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .plugins import load_symbol
from .registry import EvidenceRegistry, load_evidence_registry
from .rubrics import EvaluationContext, LoadedRubric, load_rubrics
from .tools import LoadedTool, load_task_actions

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"
TOOL_NAMES = {
    "list_files",
    "read_text",
    "write_text",
    "replace_text",
    "run_project",
    "run_experiment",
    "ask_user",
    "submit",
}


@dataclass(frozen=True)
class Task:
    root: Path
    task_id: str
    domain: str
    title: str
    tools: tuple[LoadedTool, ...]
    rubrics: tuple[LoadedRubric, ...]
    registry: EvidenceRegistry
    editable_paths: tuple[str, ...]

    def instruction(self, mode: str) -> str:
        return (
            (self.root / ("full.md" if mode == "full" else "partial.md"))
            .read_text()
            .strip()
        )

    def evaluate(self, workspace: Path):
        return tuple(
            r.evaluate(
                workspace,
                EvaluationContext(
                    task_id=self.task_id,
                    rubric_id=r.spec.rubric_id,
                    run_id="evaluation",
                    private_state={"task_root": str(self.root)},
                ),
            )
            for r in self.rubrics
        )


def load_task(root: Path) -> Task:
    root = root.resolve()
    data = yaml.safe_load((root / "task.yaml").read_text())
    required = {"id", "domain", "title", "rubrics"}
    if set(data) not in (required, required | {"seed_sources"}):
        raise ValueError(f"Invalid task manifest: {root}")
    if "seed_sources" in data:
        sources = data["seed_sources"]
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"Invalid seed sources: {root}")
        for source in sources:
            if (
                not isinstance(source, dict)
                or set(source) != {"name", "url"}
                or not all(isinstance(v, str) and v.strip() for v in source.values())
            ):
                raise ValueError(f"Invalid seed source: {root}")
            url = urlsplit(source["url"])
            if url.scheme not in {"http", "https"} or not url.netloc:
                raise ValueError(f"Invalid seed source URL: {root}")
    task_id = data["id"]
    if task_id != root.name or not re.fullmatch(
        r"(SWE|Research)-[a-z0-9]+(?:-[a-z0-9]+)*", task_id
    ):
        raise ValueError(f"Invalid task name: {task_id}")
    if data["domain"] != task_id.split("-")[0]:
        raise ValueError(f"Domain does not match task name: {task_id}")
    ids = data["rubrics"]
    if len(ids) != 5 or len(set(ids)) != 5:
        raise ValueError(f"{task_id} must define five distinct requirements.")
    rubrics = load_rubrics(
        [
            {"id": rid, "evaluator": f"private/rubrics.py:{rid}", "priority": 5 - i}
            for i, rid in enumerate(ids)
        ],
        root,
    )
    modes = load_symbol("private/rubrics.py:FAILURE_MODES", root)
    if set(modes) != set(ids):
        raise ValueError(f"Failure modes do not match requirements: {task_id}")
    registry = load_evidence_registry(root / "evidence.py", modes)
    tools = load_task_actions("actions.py:get_actions", root)
    if {t.definition.name for t in tools} != TOOL_NAMES:
        raise ValueError(f"{task_id} must expose the eight paper tools.")
    editable = tuple(
        dict.fromkeys(str(p) for t in tools for p in t.config.get("allowed_paths", ()))
    )
    for name in ("partial.md", "full.md"):
        if not (root / name).read_text().strip():
            raise ValueError(f"Empty initial instruction: {task_id}/{name}")
    return Task(
        root, task_id, data["domain"], data["title"], tools, rubrics, registry, editable
    )


def select_tasks(
    root: Path = TASKS_ROOT,
    *,
    names: list[str] | None = None,
    domain: str | None = None,
) -> list[Path]:
    paths = {p.parent.name: p.parent for p in sorted(root.glob("*/task.yaml"))}
    if names:
        missing = set(names) - paths.keys()
        if missing:
            raise ValueError(f"Unknown tasks: {sorted(missing)}")
        paths = {name: paths[name] for name in dict.fromkeys(names)}
    selected = [
        p for p in paths.values() if domain is None or p.name.startswith(domain + "-")
    ]
    if not selected:
        raise ValueError("No tasks selected.")
    return selected
