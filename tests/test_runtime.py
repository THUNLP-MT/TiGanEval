import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tiganeval.client import ContextWindowExceededError
from tiganeval.prompts import build_agent_system_prompt
from tiganeval.protocol import Action, AgentTurn, Event, EventKind, RubricResult
from tiganeval.registry import EvidenceRegistry, Observation
from tiganeval.report import summarize
from tiganeval.runner import Budget, Episode
from tiganeval.sandbox import SandboxUnavailable
from tiganeval.taskkit import control_tools, experiment_tool, file_tools
from tiganeval.tools import load_tools


class ScriptedAgent:
    build_system_prompt = staticmethod(build_agent_system_prompt)

    def __init__(self, turns):
        self.turns = iter(turns)
        self.events = []

    def reset(self, prompt, tools):
        self.prompt, self.tools = prompt, tools

    def step(self, events):
        self.events.extend(events)
        next_turn = next(self.turns)
        if isinstance(next_turn, Exception):
            raise next_turn
        return AgentTurn(tuple(Action(n, a) for n, a in next_turn))


class ScriptedUser:
    def __init__(self):
        self.selections = []

    def start_episode(self, **kwargs):
        self.start = kwargs

    def feedback(self, selection):
        self.selections.append(selection)
        return Event(EventKind.INSTRUCTION, "I still see the issue.", "user")

    def answer(self, message):
        return Event(EventKind.INSTRUCTION, "I do not know.", "user")


def fixture(root):
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "answer.txt").write_text("incomplete")
    tools = load_tools(
        (
            *file_tools(
                editable_paths=("answer.txt",), workspace_description="project"
            ),
            experiment_tool(),
            *control_tools(),
        ),
        root,
    )
    registry = EvidenceRegistry(
        "An owner",
        "Partial knowledge",
        "An incident",
        {
            f"requirement_{i}": {
                "wrong": Observation(
                    "The answer is wrong.",
                    "I read {value}.",
                    "{value}",
                    {"first": "first", "second": "second", "repeat": "repeat"},
                    ("value",),
                )
            }
            for i in range(5)
        },
    )

    def evaluate(path):
        passed = (path / "answer.txt").read_text() == "complete"
        return tuple(
            RubricResult(
                f"requirement_{i}",
                passed,
                None if passed else "wrong",
                {"observed": {"value": "incomplete"}},
            )
            for i in range(5)
        )

    return SimpleNamespace(
        root=root,
        task_id="SWE-fixture",
        domain="SWE",
        tools=tools,
        editable_paths=("answer.txt",),
        registry=registry,
        evaluate=evaluate,
        instruction=lambda mode: (
            "Full instruction" if mode == "full" else "Partial instruction"
        ),
    )


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def run_episode(self, turns, mode="partial", budget=None, task=None):
        agent, user = ScriptedAgent(turns), ScriptedUser()
        episode = Episode(
            task or self.task, mode, agent, user, self.root / "run", budget=budget
        )
        with patch("tiganeval.runner.require_backend", return_value="test"):
            result = episode.run()
        self.assertEqual(result["status"], "completed", result.get("error"))
        return result, agent, user

    def test_feedback_priority_and_escalation(self):
        result, agent, user = self.run_episode(
            [[("submit", {"summary": str(i)})] for i in range(4)]
        )
        self.assertEqual(len(result["submissions"]), 4)
        self.assertEqual([s.rubric_id for s in user.selections], ["requirement_0"] * 3)
        self.assertEqual([s.occurrence for s in user.selections], [1, 2, 3])
        self.assertEqual([s.stalled for s in user.selections], [False, False, True])
        self.assertNotIn("requirement_0", "\n".join(e.content for e in agent.events))

    def test_full_has_one_submission_and_full_owner_knowledge(self):
        result, agent, user = self.run_episode([[("submit", {})]], mode="full")
        self.assertEqual(len(result["submissions"]), 1)
        self.assertEqual(user.start["owner_knowledge"], "Full instruction")
        self.assertEqual(user.selections, [])
        self.assertIn("Budget: 1 submissions", agent.prompt)

    def test_acceptance_stops_episode(self):
        result, _, user = self.run_episode(
            [
                [("write_text", {"path": "answer.txt", "content": "complete"})],
                [("submit", {})],
            ]
        )
        self.assertEqual(result["stop_reason"], "accepted")
        self.assertEqual(result["submissions"][0]["score"], 1)
        self.assertEqual(user.selections, [])

    def test_turn_exhaustion_submits_latest_workspace(self):
        result, _, _ = self.run_episode(
            [[("write_text", {"path": "answer.txt", "content": "complete"})]],
            budget=Budget(turns=1),
        )
        self.assertTrue(result["submissions"][0]["automatic"])
        self.assertTrue(result["submissions"][0]["success"])

    def test_repeated_action_stops_before_fourth_execution(self):
        result, _, _ = self.run_episode([[("read_text", {"path": "answer.txt"})]] * 4)
        self.assertEqual(result["stop_reason"], "repeated_action")
        self.assertEqual(result["cost"]["tool_calls"], 3)
        self.assertTrue(result["submissions"][0]["automatic"])

    def test_fourth_question_stops(self):
        result, _, _ = self.run_episode(
            [[("ask_user", {"message": str(i)})] for i in range(4)]
        )
        self.assertEqual(result["stop_reason"], "consecutive_user_questions")

    def test_context_overflow_submits(self):
        result, _, _ = self.run_episode([ContextWindowExceededError("overflow")])
        self.assertEqual(result["stop_reason"], "context_window_exceeded")
        self.assertTrue(result["submissions"][0]["automatic"])

    def test_control_batch_executes_nothing(self):
        result, _, _ = self.run_episode(
            [
                [
                    ("write_text", {"path": "answer.txt", "content": "complete"}),
                    ("submit", {}),
                ],
                [("submit", {})],
            ],
            budget=Budget(submissions=1),
        )
        self.assertFalse(result["submissions"][0]["success"])
        self.assertEqual(result["cost"]["tool_calls"], 0)

    def test_literal_disallows_asking(self):
        result, agent, _ = self.run_episode(
            [[("ask_user", {"message": "help"})], [("submit", {})]],
            mode="literal",
            budget=Budget(submissions=1),
        )
        self.assertNotIn("ask_user", [t.name for t in agent.tools])
        self.assertIn("Unknown tool", agent.events[-1].content)

    def test_sandbox_failure_is_not_scored(self):
        def fail(*args):
            raise SandboxUnavailable("unavailable")

        broken = SimpleNamespace(**vars(self.task))
        broken.evaluate = fail
        with patch("tiganeval.runner.require_backend", return_value="test"):
            result = Episode(
                broken,
                "partial",
                ScriptedAgent([[("submit", {})]]),
                ScriptedUser(),
                self.root / "run",
            ).run()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["submissions"], [])

    def test_report_preserves_regression_and_excludes_errors(self):
        base = {
            "task": "task",
            "domain": "SWE",
            "status": "completed",
            "budget": {"submissions": 4},
            "mode": "partial",
            "submissions": [
                {"score": 0.8, "success": False},
                {"score": 0.4, "success": False},
            ],
        }
        full = {
            **base,
            "mode": "full",
            "budget": {"submissions": 1},
            "submissions": [{"score": 1.0, "success": True}],
        }
        result = summarize([base, full, {**base, "task": "error", "status": "error"}])
        self.assertEqual(
            [p["score"] for p in result["metrics"]["all"]["partial"]["trajectory"]],
            [0.8, 0.4, 0.4, 0.4],
        )
        self.assertEqual(result["metrics"]["all"]["partial"]["tasks"], 1)
        self.assertAlmostEqual(result["partial_minus_full_at_1"]["score"], -0.2)


if __name__ == "__main__":
    unittest.main()
