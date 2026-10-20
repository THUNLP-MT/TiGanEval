"Task-independent scaffolding shared by code-executing tasks."

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .builtin import (
    ask_user_tool,
    list_files,
    read_text,
    replace_text,
    submit_tool,
    write_text,
)
from .protocol import RubricResult
from .sandbox import SandboxPolicy, deterministic_environment, run_sandboxed

_IGNORED_TREE_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".tiganeval"}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_FAILURE = "candidate_process_failure"
EXECUTION_FAILURE_MODE = "candidate_execution_failed"


def artifact_hash(artifact_dir: Path) -> str:
    "A stable content hash of one candidate workspace."

    digest = hashlib.sha256()
    root = Path(artifact_dir).resolve()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if _IGNORED_TREE_PARTS.intersection(relative.parts) or path.suffix in {
            ".pyc",
            ".pyo",
        }:
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _reject_symlinks(source: Path) -> None:
    "A symlink in a copied tree could smuggle a private path into the sandbox."

    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError(
                f"workspace contains a symlink: {path.relative_to(source)}"
            )


def _interpreter_root() -> Path:
    "The interpreter's install tree, which the private roots may otherwise deny."

    return Path(sys.base_prefix).resolve()


def _private_roots(*extra: Path) -> tuple[Path, ...]:
    "Everything a candidate process must never read."

    roots = (
        _REPOSITORY_ROOT,
        Path.home(),
        Path(tempfile.gettempdir()),
        Path("/private/tmp"),
        *extra,
    )
    return tuple(dict.fromkeys(Path(root).expanduser().resolve() for root in roots))


WORKSPACE_TOKEN = "<workspace>"
TEMPORARY_ROOT_TOKEN = "<tmp>"


def _sandbox_path_folder(throwaway_workspace: str | Path) -> Callable[[Any], Any]:
    "Fold one run's throwaway directories out of the text it produces."

    pairs: list[tuple[str, str]] = []
    for spelling in dict.fromkeys(
        (Path(throwaway_workspace), Path(throwaway_workspace).resolve())
    ):
        pairs.append((str(spelling), WORKSPACE_TOKEN))
        pairs.append((str(spelling.parent), TEMPORARY_ROOT_TOKEN))

    ordered = sorted(dict.fromkeys(pairs), key=lambda pair: len(pair[0]), reverse=True)

    def fold(value: Any) -> Any:
        if isinstance(value, str):
            for needle, token in ordered:
                value = value.replace(needle, token)
            return value
        if isinstance(value, Mapping):
            return {fold(key): fold(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [fold(item) for item in value]
        return value

    return fold


def _folded_exception(exc: BaseException, fold: Callable[[Any], Any]) -> BaseException:
    "The same exception with the throwaway directories folded out of its text."

    try:
        exc.args = tuple(fold(argument) for argument in exc.args)
    except Exception:
        return exc
    return exc


class SandboxedProject:
    "Runs a task's candidate code under the shared fail-closed sandbox."

    def __init__(
        self,
        *,
        task_root: Path,
        driver: Path,
        editable_files: Sequence[str],
        workspace_name: str = "workspace",
        prefix: str = "tiganeval-task-",
        timeout: float = 30.0,
    ):
        self.task_root = Path(task_root).resolve()
        self.canonical_workspace = self.task_root / workspace_name
        self.driver = Path(driver).resolve()
        self.editable_files = tuple(Path(item) for item in editable_files)
        self.prefix = str(prefix)
        self.timeout = float(timeout)

    def _overlay(self, source: Path, destination: Path) -> None:
        source = Path(source).resolve()
        _reject_symlinks(source)
        shutil.copytree(
            self.canonical_workspace,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".tiganeval"),
        )
        for relative in self.editable_files:
            candidate_path = source / relative
            if candidate_path.is_file():
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate_path, target)

    def invoke(
        self,
        artifact_dir: Path,
        payload: Mapping[str, Any],
        *,
        timeout: float | None = None,
    ) -> Mapping[str, Any]:
        "Run the task driver on this candidate and return its JSON result."

        limit = float(self.timeout if timeout is None else timeout)
        with tempfile.TemporaryDirectory(prefix=self.prefix) as directory:
            root = Path(directory).resolve()
            workspace = root / "workspace"
            fold = _sandbox_path_folder(Path(directory) / "workspace")
            driver = root / self.driver.name
            try:
                self._overlay(Path(artifact_dir), workspace)
                shutil.copy2(self.driver, driver)
            except Exception as exc:
                raise _folded_exception(exc, fold) from None
            environment = deterministic_environment()
            environment.update({"PYTHONNOUSERSITE": "1", "PYTHONPATH": str(workspace)})
            policy = SandboxPolicy(
                private_roots=_private_roots(self.task_root.parents[1]),
                readable_roots=(_interpreter_root(), root),
                writable_roots=(root,),
            )
            try:
                completed = run_sandboxed(
                    (str(Path(sys.executable).resolve()), str(driver)),
                    cwd=workspace,
                    env=environment,
                    input=json.dumps(payload, ensure_ascii=False),
                    timeout=limit,
                    policy=policy,
                )
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"project rehearsal exceeded {limit:g}s"}
            if completed.returncode != 0:
                return fold(
                    {
                        "ok": False,
                        "error": f"candidate process exited with status {completed.returncode}",
                        "diagnostic": completed.stderr.strip()[-500:],
                    }
                )
            try:
                value = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"candidate returned invalid JSON: {exc}"}
            if not isinstance(value, Mapping):
                return {"ok": False, "error": "candidate returned non-object"}
            return fold(value)


class AnalysisCache:
    "Memoise one analysis per candidate content, so resubmitting unchanged files is free."

    def __init__(self) -> None:
        self._entries: dict[str, Mapping[str, Any]] = {}

    def get_or_compute(
        self,
        artifact_dir: Path,
        compute: Callable[[], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        key = artifact_hash(artifact_dir)
        if key not in self._entries:
            self._entries[key] = deepcopy(dict(compute()))
        return deepcopy(self._entries[key])


_SCALAR_TYPES = (str, int, float, bool)


def observed_fields(
    failures: Sequence[Mapping[str, Any]], failure_mode: str
) -> dict[str, Any]:
    "The measured scalar fields of the failure record behind ``failure_mode``."

    records = [item for item in failures if isinstance(item, Mapping)]
    if not records:
        return {"kind": failure_mode}
    chosen = next(
        (item for item in records if str(item.get("kind", "")) == failure_mode),
        records[0],
    )
    observed = {
        str(key): value
        for key, value in chosen.items()
        if isinstance(value, _SCALAR_TYPES)
    }
    observed.setdefault("kind", failure_mode)
    return observed


def failed_analysis(error: str, buckets: Sequence[str]) -> dict[str, Any]:
    "The analysis to report when the candidate could not be run at all."

    stub = [{"kind": CANDIDATE_FAILURE, "error": error}]
    analysis: dict[str, Any] = {"harness_error": error, "records": []}
    for bucket in buckets:
        analysis[bucket] = list(stub)
    return analysis


class RubricSet:
    "Turn one analysis into the task's five binary project judgements."

    def __init__(
        self,
        *,
        failure_modes: Mapping[str, Sequence[str]],
        priority: Mapping[str, Sequence[str]],
        buckets: Mapping[str, str],
        analyse: Callable[[Path], Mapping[str, Any]],
    ):
        self.failure_modes = {key: tuple(value) for key, value in failure_modes.items()}
        self.priority = {key: tuple(value) for key, value in priority.items()}
        self.buckets = dict(buckets)
        self.analyse = analyse
        for rubric_id, modes in self.failure_modes.items():
            expected = set(modes) - {EXECUTION_FAILURE_MODE}
            if set(self.priority.get(rubric_id, ())) != expected:
                raise ValueError(
                    f"{rubric_id} priority order must cover every non-execution failure mode"
                )

    def select_mode(
        self,
        rubric_id: str,
        analysis: Mapping[str, Any],
        failures: Sequence[Mapping[str, Any]],
    ) -> str:
        if analysis.get("harness_error"):
            return EXECUTION_FAILURE_MODE
        kinds = [str(item.get("kind", "")) for item in failures]
        if CANDIDATE_FAILURE in kinds:
            return EXECUTION_FAILURE_MODE
        for candidate in self.priority[rubric_id]:
            if candidate in kinds:
                return candidate

        raise ValueError(
            f"{rubric_id} produced unmapped failure kinds: {sorted(set(kinds))}"
        )

    def evaluate(self, artifact_dir: Path, context: Any) -> RubricResult:
        rubric_id = str(context.rubric_id)
        analysis = self.analyse(Path(artifact_dir))
        failures = list(analysis.get(self.buckets[rubric_id], ()))
        mode: str | None = None
        details: dict[str, Any] = {
            "failures": failures[:8],
            "case": analysis.get("case"),
        }
        if failures:
            mode = self.select_mode(rubric_id, analysis, failures)
            if mode not in self.failure_modes[rubric_id]:
                raise ValueError(f"unregistered failure mode for {rubric_id}: {mode}")
            details["observed"] = observed_fields(failures, mode)
        return RubricResult(
            rubric_id=rubric_id,
            passed=not failures,
            failure_mode=mode,
            details=details,
        )


def observation(first: str, second: str, detail: str) -> dict[str, str]:
    "One failure mode's escalating owner contexts."

    if not first.strip() or not second.strip() or not detail.strip():
        raise ValueError("observation first, second, and detail must be non-empty")
    if detail not in second:
        raise ValueError(
            f"observation detail {detail!r} must appear in the second context"
        )
    if detail in first:
        raise ValueError(
            f"observation detail {detail!r} must not appear in the first context"
        )
    return {"first": first, "second": second, "detail": detail}


def file_tools(
    *,
    editable_paths: Sequence[str],
    workspace_description: str,
    max_chars: int = 50_000,
) -> tuple[Mapping[str, Any], ...]:
    "The standard read/write surface over one task workspace."

    editable = ", ".join(editable_paths)
    return (
        {
            "name": "list_files",
            "description": f"List files in the {workspace_description}.",
            "handler": list_files,
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
                "additionalProperties": False,
            },
        },
        {
            "name": "read_text",
            "description": "Read one UTF-8 project file.",
            "handler": read_text,
            "config": {"max_chars": int(max_chars)},
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_text",
            "description": f"Create or replace {editable}.",
            "handler": write_text,
            "config": {"allowed_paths": tuple(editable_paths)},
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
        {
            "name": "replace_text",
            "description": f"Replace one exact span in {editable}.",
            "handler": replace_text,
            "config": {"allowed_paths": tuple(editable_paths)},
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "expected_replacements": {"type": "integer", "default": 1},
                },
                "required": ["path", "old", "new"],
                "additionalProperties": False,
            },
        },
    )


_EXPERIMENT_SCRIPT = "_experiment.py"
_EXPERIMENT_STDOUT_CHARS = 20_000
_EXPERIMENT_STDERR_CHARS = 8_000


def _captured_text(value: Any) -> str:

    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_experiment(arguments: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
    "Run an Agent-written script on a throwaway copy of the current workspace."

    script = arguments.get("script")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("run_experiment requires a non-empty script")
    stdin = arguments.get("stdin")
    stdin = "" if stdin is None else str(stdin)
    timeout = float(context.config.get("timeout", 30.0))
    extra_private = tuple(
        Path(item) for item in context.config.get("private_roots", ())
    )
    workspace = Path(context.workspace).resolve()
    _reject_symlinks(workspace)

    with tempfile.TemporaryDirectory(prefix="tiganeval-experiment-") as directory:
        copy = Path(directory).resolve() / "workspace"
        fold = _sandbox_path_folder(Path(directory) / "workspace")
        try:
            shutil.copytree(
                workspace,
                copy,
                ignore=shutil.ignore_patterns("__pycache__", ".tiganeval"),
            )
            (copy / _EXPERIMENT_SCRIPT).write_text(script, encoding="utf-8")
        except Exception as exc:
            raise _folded_exception(exc, fold) from None
        environment = deterministic_environment()
        environment.update({"PYTHONNOUSERSITE": "1", "PYTHONPATH": str(copy)})
        policy = SandboxPolicy(
            private_roots=_private_roots(*extra_private),
            readable_roots=(_interpreter_root(), copy),
            writable_roots=(copy,),
        )
        try:
            completed = run_sandboxed(
                (str(Path(sys.executable).resolve()), _EXPERIMENT_SCRIPT),
                cwd=copy,
                env=environment,
                input=stdin,
                timeout=timeout,
                policy=policy,
            )
        except subprocess.TimeoutExpired as exc:
            return fold(
                {
                    "exit_code": None,
                    "stdout": _captured_text(exc.stdout)[-_EXPERIMENT_STDOUT_CHARS:],
                    "stderr": _captured_text(exc.stderr)[-_EXPERIMENT_STDERR_CHARS:],
                    "timed_out": True,
                }
            )
    return fold(
        {
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-_EXPERIMENT_STDOUT_CHARS:],
            "stderr": completed.stderr[-_EXPERIMENT_STDERR_CHARS:],
            "timed_out": False,
        }
    )


def experiment_tool(timeout: float = 30.0) -> Mapping[str, Any]:
    "The task-independent `run_experiment` declaration."

    return {
        "name": "run_experiment",
        "description": (
            "Run a Python script you wrote against the current workspace. The "
            "script runs inside the sandbox on a throwaway copy of the workspace "
            "with the workspace on PYTHONPATH and as the working directory; files "
            "it writes are discarded. A successful run returns what the script "
            "printed (stdout and stderr), so print what you want to observe; a "
            "failed run returns the error message. Use it to construct your own "
            "experiments."
        ),
        "handler": run_experiment,
        "config": {"timeout": float(timeout)},
        "parameters": {
            "type": "object",
            "properties": {
                "script": {"type": "string"},
                "stdin": {"type": "string"},
            },
            "required": ["script"],
            "additionalProperties": False,
        },
    }


def control_tools() -> tuple[Mapping[str, Any], ...]:
    return (ask_user_tool(), submit_tool())


__all__ = (
    "AnalysisCache",
    "CANDIDATE_FAILURE",
    "EXECUTION_FAILURE_MODE",
    "RubricSet",
    "SandboxedProject",
    "TEMPORARY_ROOT_TOKEN",
    "WORKSPACE_TOKEN",
    "artifact_hash",
    "control_tools",
    "experiment_tool",
    "failed_analysis",
    "file_tools",
    "observation",
    "observed_fields",
    "run_experiment",
)
