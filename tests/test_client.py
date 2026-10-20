import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tiganeval.cli import main
from tiganeval.tasks import TASKS_ROOT, load_task


class SDKIntegrationTest(unittest.TestCase):
    def test_custom_endpoint_two_models_and_private_feedback_boundary(self):
        task = load_task(TASKS_ROOT / "SWE-implicit-method-routing")
        requests = []
        gold = task.root / "private/gold_workspace"
        scripts = [
            [("ask_user", {"message": "What else should I check?"})],
            [("submit", {"summary": "First delivery"})],
            [
                (
                    "write_text",
                    {"path": p.relative_to(gold).as_posix(), "content": p.read_text()},
                )
                for p in sorted(gold.rglob("*.py"))
            ],
            [("submit", {"summary": "Revised delivery"})],
        ]
        agent_turn = 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                nonlocal agent_turn
                request = json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                requests.append((self.path, self.headers.get("Authorization"), request))
                if request["model"] == "agent-test":
                    calls = scripts[agent_turn]
                    agent_turn += 1
                    message = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call-{agent_turn}-{i}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                            for i, (name, arguments) in enumerate(calls)
                        ],
                    }
                    finish = "tool_calls"
                else:
                    message = {
                        "role": "assistant",
                        "content": "Please investigate what the project shows.",
                    }
                    finish = "stop"
                body = json.dumps(
                    {
                        "id": "completion",
                        "object": "chat.completion",
                        "created": 1,
                        "model": request["model"],
                        "choices": [
                            {"index": 0, "message": message, "finish_reason": finish}
                        ],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1"
        try:
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.dict(
                    os.environ,
                    {
                        "TIGANEVAL_TEST_AGENT_KEY": "test-agent-secret",
                        "TIGANEVAL_TEST_USER_KEY": "test-user-secret",
                    },
                ),
            ):
                run = Path(directory) / "run"
                argv = [
                    "tiganeval",
                    "run",
                    "--model",
                    "agent-test",
                    "--base-url",
                    endpoint,
                    "--api-key-env",
                    "TIGANEVAL_TEST_AGENT_KEY",
                    "--user-model",
                    "owner-test",
                    "--user-base-url",
                    endpoint,
                    "--user-api-key-env",
                    "TIGANEVAL_TEST_USER_KEY",
                    "--modes",
                    "partial",
                    "--tasks",
                    task.task_id,
                    "--output",
                    str(run),
                ]
                with patch("sys.argv", argv):
                    main()
                output = run / task.task_id / "partial"
                result = json.loads((output / "result.json").read_text())
                request_count = len(requests)
                with patch("sys.argv", [*argv, "--resume"]):
                    main()
                self.assertEqual(len(requests), request_count)
                failed = {**result, "status": "error"}
                (output / "result.json").write_text(json.dumps(failed))
                agent_turn = 0
                with patch("sys.argv", [*argv, "--resume"]):
                    main()
                previous = list((run / "attempts").glob("*/*/*/result.json"))
                self.assertEqual(len(previous), 1)
                self.assertEqual(json.loads(previous[0].read_text())["status"], "error")
                self.assertEqual(
                    json.loads((output / "result.json").read_text())["status"],
                    "completed",
                )
                self.assertEqual(result["status"], "completed", result.get("error"))
                self.assertEqual(result["stop_reason"], "accepted")
                self.assertEqual(len(result["submissions"]), 2)
                self.assertEqual(result["submissions"][-1]["score"], 1)
                self.assertEqual(result["cost"]["tokens"]["agent"]["total_tokens"], 60)
                self.assertEqual(result["cost"]["tokens"]["user"]["total_tokens"], 30)
                for path in (output / "trajectory.jsonl", output / "result.json"):
                    self.assertNotIn("test-agent-secret", path.read_text())
                    self.assertNotIn("test-user-secret", path.read_text())
                for path, authorization, request in requests:
                    self.assertEqual(path, "/v1/chat/completions")
                    expected = (
                        "test-agent-secret"
                        if request["model"] == "agent-test"
                        else "test-user-secret"
                    )
                    self.assertEqual(authorization, f"Bearer {expected}")
                    if request["model"] == "owner-test":
                        self.assertNotIn("tools", request)
                        prompt = json.dumps(request["messages"])
                        for rubric in task.rubrics:
                            self.assertNotIn(rubric.spec.rubric_id, prompt)
                        self.assertNotIn('"score"', prompt)
                        self.assertNotIn(task.instruction("full"), prompt)
                    else:
                        names = {t["function"]["name"] for t in request["tools"]}
                        self.assertIn("ask_user", names)
                        self.assertNotIn("ask_question", names)
                        self.assertNotIn("temperature", request)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
