from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from .agents.literal import LiteralAgent
from .agents.react import ReActAgent
from .client import ContentFilterExhaustedError, ContextWindowExceededError
from .protocol import Action, Event, EventKind, FeedbackSelection
from .sandbox import SandboxUnavailable, require_backend
from .tasks import Task
from .tools import (
    EnvironmentInfrastructureError,
    ToolContext,
    serialize_task_tool_result,
)

MODES = ("partial", "full", "literal")
AGENTS = {
    "partial": ReActAgent,
    "full": ReActAgent,
    "literal": LiteralAgent,
}


@dataclass(frozen=True)
class Budget:
    turns: int = 120
    tool_calls: int = 360
    submissions: int = 4


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def copy_workspace(source: Path, destination: Path) -> None:
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("Workspace copies must not contain symlinks.")
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".DS_Store", ".tiganeval"
        ),
    )


class Episode:
    def __init__(
        self,
        task: Task,
        mode: str,
        agent,
        user,
        output: Path,
        *,
        budget: Budget | None = None,
        secrets: tuple[str, ...] = (),
    ):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        self.task, self.mode = task, mode
        self.agent, self.user = agent, user
        self.output = output
        self.workspace = output / "workspace"
        self.budget = budget or Budget(submissions=1 if mode == "full" else 4)
        self.secrets = tuple(s for s in secrets if s)
        self.turns = self.tool_calls = 0
        self.usage = {"agent": Counter(), "user": Counter()}
        self.submissions: list[dict] = []
        self.occurrences: Counter = Counter()
        self.stop_reason: str | None = None
        self.previous_action = None
        self.identical_actions = self.questions = self.empty_experiments = 0
        self.tools = {t.definition.name: t for t in task.tools}
        experiment = self.tools.get("run_experiment")
        if experiment:
            self.tools["run_experiment"] = replace(
                experiment,
                config={
                    **experiment.config,
                    "private_roots": (
                        str(task.root.parent),
                        str(output.resolve().parents[1]),
                    ),
                },
            )
        if mode == "literal":
            self.tools.pop("ask_user")

    def _redact(self, value):
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {k: self._redact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact(v) for v in value]
        return value

    def record(self, kind: str, **data) -> None:
        with (self.output / "trajectory.jsonl").open("a") as stream:
            stream.write(
                json.dumps(self._redact({"type": kind, **data}), ensure_ascii=False)
                + "\n"
            )

    @staticmethod
    def event(
        action: Action, text: str, *, instruction: bool = False, data=None
    ) -> Event:
        return Event(
            EventKind.INSTRUCTION if instruction else EventKind.OBSERVATION,
            text,
            "user" if instruction else f"tool:{action.name}",
            data or {},
            tool_call_id=action.tool_call_id,
        )

    def _reply(self, reply: Event, action: Action) -> Event:
        self.usage["user"].update(reply.data.get("usage", {}))
        self.record("user", message=reply.content)
        return replace(reply, tool_call_id=action.tool_call_id)

    def submit(self, action: Action, *, automatic: bool = False) -> Event | None:
        index = len(self.submissions) + 1
        artifact = self.output / "submissions" / str(index) / "workspace"
        copy_workspace(self.workspace, artifact)
        results = self.task.evaluate(artifact)
        accepted = all(r.passed for r in results)
        entry = {
            "index": index,
            "score": sum(r.passed for r in results) / 5,
            "success": accepted,
            "rubrics": {r.rubric_id: r.passed for r in results},
            "results": [r.to_dict() for r in results],
            "summary": str(action.arguments.get("summary", "")),
            "automatic": automatic,
        }
        self.submissions.append(entry)
        self.record("submission", **entry)
        if accepted:
            self.stop_reason = "accepted"
        elif not automatic and index >= self.budget.submissions:
            self.stop_reason = "submissions_exhausted"
        if automatic or self.stop_reason:
            return None
        failed = next(r for r in results if not r.passed)
        key = (failed.rubric_id, failed.failure_mode)
        self.occurrences[key] += 1
        occurrence = self.occurrences[key]
        observed = dict(failed.details.get("observed") or {})
        observation_id, payload = self.task.registry.select(
            *key, occurrence, observed=observed
        )
        selection = FeedbackSelection(
            failed.rubric_id,
            failed.failure_mode,
            occurrence,
            observation_id,
            occurrence >= 3,
            observed,
        )
        self.record("observation", observation=payload)
        return self._reply(self.user.feedback(selection), action)

    def execute(self, actions) -> list[Event]:
        controls = {"submit", "ask_user"}
        if len(actions) > 1 and any(a.name in controls for a in actions):
            return [
                self.event(
                    a,
                    "submit and ask_user must be called alone; no action was executed.",
                )
                for a in actions
            ]
        events = []
        for action in actions:
            fingerprint = json.dumps([action.name, action.arguments], sort_keys=True)
            self.identical_actions = (
                self.identical_actions + 1 if fingerprint == self.previous_action else 1
            )
            self.previous_action = fingerprint
            self.questions = self.questions + 1 if action.name == "ask_user" else 0
            if self.questions >= 4:
                self.stop_reason = "consecutive_user_questions"
                break
            if self.identical_actions >= 4:
                self.stop_reason = "repeated_action"
                break
            self.record("action", name=action.name, arguments=action.arguments)
            tool = self.tools.get(action.name)
            if tool is None:
                event = self.event(action, f"Unknown tool: {action.name}")
            elif action.name == "submit":
                event = self.submit(action)
            elif action.name == "ask_user":
                message = str(action.arguments.get("message", "")).strip()
                event = (
                    self._reply(self.user.answer(message), action)
                    if message
                    else self.event(action, "ask_user requires a non-empty message.")
                )
            elif self.tool_calls >= self.budget.tool_calls:
                self.stop_reason = "tool_calls_exhausted"
                break
            else:
                self.tool_calls += 1
                context = ToolContext(
                    self.task.task_id,
                    self.output.parent.name,
                    self.workspace,
                    config=tool.config,
                )
                try:
                    content, data = serialize_task_tool_result(
                        tool.run(action.arguments, context)
                    )
                except (SandboxUnavailable, EnvironmentInfrastructureError):
                    raise
                except Exception as exc:
                    content, data = (
                        f"Action {action.name!r} failed: {exc}",
                        {"error": type(exc).__name__},
                    )
                event = self.event(action, content, data=data)
            if event is None:
                break
            events.append(event)
            self.record("tool_result", name=action.name, content=event.content)
            blank = (
                action.name == "run_experiment"
                and event.data.get("exit_code") == 0
                and not event.data.get("stdout", "").strip()
                and not event.data.get("stderr", "").strip()
            )
            self.empty_experiments = self.empty_experiments + 1 if blank else 0
            if self.empty_experiments >= 4:
                self.stop_reason = "empty_experiment_loop"
                break
        return events

    def run(self) -> dict:
        require_backend()
        self.output.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        error = None
        try:
            copy_workspace(self.task.root / "workspace", self.workspace)
            budget = self.budget
            self.agent.reset(
                self.agent.build_system_prompt(
                    submissions=budget.submissions,
                    turns=budget.turns,
                    tool_calls=budget.tool_calls,
                ),
                tuple(t.definition for t in self.tools.values()),
            )
            initial = self.task.instruction(self.mode)
            self.user.start_episode(
                condition_id=self.mode,
                initial_instruction=initial,
                owner_knowledge=initial
                if self.mode == "full"
                else self.task.registry.user_belief,
                editable_paths=self.task.editable_paths,
            )
            self.record("instruction", content=initial)
            pending = [Event(EventKind.INSTRUCTION, initial, "user")]
            while not self.stop_reason:
                if self.turns >= budget.turns:
                    self.stop_reason = "turns_exhausted"
                    break
                self.turns += 1
                role = "agent"
                try:
                    turn = self.agent.step(pending)
                    self.usage["agent"].update(turn.usage)
                    self.record("assistant", content=turn.thought)
                    role = "user"
                    pending = self.execute(turn.actions)
                except (ContentFilterExhaustedError, ContextWindowExceededError) as exc:
                    self.usage[role].update(exc.usage)
                    self.stop_reason = (
                        "content_filter_exhausted"
                        if isinstance(exc, ContentFilterExhaustedError)
                        else "context_window_exceeded"
                    )
            if (
                self.stop_reason not in {"accepted", "submissions_exhausted"}
                and len(self.submissions) < budget.submissions
            ):
                self.submit(
                    Action(
                        "submit",
                        {"summary": f"Automatic final delivery: {self.stop_reason}."},
                    ),
                    automatic=True,
                )
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": self._redact(str(exc))}
            self.record("error", error=error)
        result = {
            "task": self.task.task_id,
            "domain": self.task.domain,
            "mode": self.mode,
            "status": "error" if error else "completed",
            "stop_reason": self.stop_reason,
            "budget": {
                "turns": self.budget.turns,
                "tool_calls": self.budget.tool_calls,
                "submissions": self.budget.submissions,
            },
            "submissions": self.submissions,
            "first_pass": {
                rid: next(
                    (s["index"] for s in self.submissions if s["rubrics"][rid]), None
                )
                for rid in (self.submissions[0]["rubrics"] if self.submissions else {})
            },
            "regressions": sum(
                before["rubrics"][rid] and not after["rubrics"][rid]
                for before, after in zip(self.submissions, self.submissions[1:])
                for rid in before["rubrics"]
            ),
            "stalls": sum(max(0, count - 2) for count in self.occurrences.values()),
            "cost": {
                "turns": self.turns,
                "tool_calls": self.tool_calls,
                "seconds": round(time.monotonic() - started, 3),
                "tokens": {k: dict(v) for k, v in self.usage.items()},
            },
        }
        if error:
            result["error"] = error
        write_json(self.output / "result.json", self._redact(result))
        return result
