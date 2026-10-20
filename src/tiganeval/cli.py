from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml

from .client import OpenAIChatCompletionsClient
from .config import OpenAIClientConfig, UserConfig
from .report import report
from .runner import AGENTS, MODES, Episode, copy_workspace, write_json
from .sandbox import require_backend
from .taskkit import artifact_hash, run_experiment
from .tasks import TASKS_ROOT, load_task, select_tasks
from .tools import ToolContext
from .user import UserSimulator


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="tiganeval")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("list", "validate", "run"):
        command = commands.add_parser(name)
        command.add_argument("--tasks-root", type=Path, default=TASKS_ROOT)
        command.add_argument("--tasks", nargs="+")
        command.add_argument("--domain", choices=("SWE", "Research"))
        if name == "run":
            command.add_argument("--config", type=Path)
            command.add_argument("--model")
            command.add_argument("--base-url")
            command.add_argument("--api-key-env")
            command.add_argument("--user-model")
            command.add_argument("--user-base-url")
            command.add_argument("--user-api-key-env")
            command.add_argument(
                "--modes", nargs="+", choices=MODES, default=["partial", "full"]
            )
            command.add_argument("--output", type=Path)
            command.add_argument("--resume", action="store_true")
    commands.add_parser("sandbox-check")
    command = commands.add_parser("report")
    command.add_argument("directory", type=Path)
    return root


def model_configs(args) -> tuple[OpenAIClientConfig, OpenAIClientConfig]:
    data = yaml.safe_load(args.config.read_text()) if args.config else {}
    if not isinstance(data, dict) or set(data) - {"agent", "user"}:
        raise ValueError("Configuration must contain only agent and user settings.")
    agent = dict(data.get("agent") or {})
    for key in ("model", "base_url", "api_key_env"):
        if getattr(args, key) is not None:
            agent[key] = getattr(args, key)
    user = {k: v for k, v in agent.items() if k in {"base_url", "api_key_env"}}
    user.update(model="gpt-5.6-terra")
    user.update(data.get("user") or {})
    for key in ("model", "base_url", "api_key_env"):
        if getattr(args, "user_" + key) is not None:
            user[key] = getattr(args, "user_" + key)
    return OpenAIClientConfig.from_mapping(agent), OpenAIClientConfig.from_mapping(user)


def sandbox_check() -> dict:
    backend = require_backend()
    with tempfile.TemporaryDirectory(prefix="tiganeval-check-") as directory:
        root = Path(directory)
        workspace = root / "workspace"
        workspace.mkdir()
        secret = root / "private.txt"
        secret.write_text("private")
        (workspace / "visible.txt").write_text("visible")
        script = """import json, os, socket
from pathlib import Path
checks = {'workspace_read': Path('visible.txt').read_text() == 'visible'}
Path('scratch.txt').write_text('scratch')
checks['workspace_write'] = Path('scratch.txt').is_file()
try:
    Path(PRIVATE).read_text()
    checks['private_read_denied'] = False
except (PermissionError, FileNotFoundError):
    checks['private_read_denied'] = True
try:
    Path(PRIVATE).write_text('changed')
    checks['outside_write_denied'] = False
except (PermissionError, FileNotFoundError):
    checks['outside_write_denied'] = True
try:
    with socket.socket() as sock:
        sock.settimeout(1)
        sock.connect(('1.1.1.1', 443))
    checks['network_denied'] = False
except OSError:
    checks['network_denied'] = True
try:
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    checks['process_creation_denied'] = False
except PermissionError:
    checks['process_creation_denied'] = True
print(json.dumps(checks))
""".replace("PRIVATE", repr(str(secret)))
        result = run_experiment(
            {"script": script}, ToolContext("sandbox-check", "check", workspace)
        )
        if result["exit_code"] != 0:
            raise RuntimeError(f"Sandbox probe failed: {result['stderr']}")
        checks = json.loads(result["stdout"])
        checks["scratch_discarded"] = not (workspace / "scratch.txt").exists()
        if not all(checks.values()):
            raise RuntimeError(f"Sandbox probe failed: {checks}")
        return {"backend": backend, "checks": checks}


def validate(paths) -> None:
    require_backend()
    for path in paths:
        task = load_task(path)
        with tempfile.TemporaryDirectory(prefix="tiganeval-validate-") as directory:
            workspace = Path(directory) / "workspace"
            copy_workspace(task.root / "workspace", workspace)
            gold = task.root / "private" / "gold_workspace"
            for item in gold.rglob("*"):
                if item.is_file() and "__pycache__" not in item.parts:
                    target = workspace / item.relative_to(gold)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(item.read_bytes())
            results = task.evaluate(workspace)
            failed = [r.rubric_id for r in results if not r.passed]
            if failed:
                raise RuntimeError(
                    f"{task.task_id}: reference solution failed {failed}"
                )
        print(f"{task.task_id}: 5/5", flush=True)


def run(args, paths) -> None:
    require_backend()
    agent_config, user_config = model_configs(args)
    secrets = (agent_config.api_key(), user_config.api_key())
    output = (
        args.output or Path("runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    ).resolve()
    if args.resume and args.output is None:
        raise ValueError("--resume requires --output pointing to an existing run.")
    tasks = [load_task(path) for path in paths]
    modes = list(dict.fromkeys(args.modes))

    def settings(config):
        url = urlsplit(config.base_url or "https://api.openai.com/v1")
        return {
            "model": config.model,
            "parameters": dict(config.parameters),
            "base_url": urlunsplit(
                (url.scheme, url.netloc.rsplit("@", 1)[-1], url.path, "", "")
            ),
        }

    manifest = {
        "tasks": {t.task_id: artifact_hash(t.root) for t in tasks},
        "modes": modes,
        "agent": settings(agent_config),
        "user": settings(user_config),
        "runtime": artifact_hash(Path(__file__).parent),
    }
    manifest_path = output / "run.json"
    if args.resume:
        if (
            not manifest_path.is_file()
            or json.loads(manifest_path.read_text()) != manifest
        ):
            raise ValueError(
                "Resume requires the same tasks, runtime, modes, models, endpoints, and request parameters."
            )
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(manifest_path, manifest)
    for task in tasks:
        for mode in modes:
            directory = output / task.task_id / mode
            result_path = directory / "result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if result["status"] == "completed":
                    print(f"{task.task_id} {mode}: existing completed", flush=True)
                    continue
            if directory.exists():
                previous = (
                    output
                    / "attempts"
                    / task.task_id
                    / mode
                    / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                )
                previous.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(directory), previous)
            client = OpenAIChatCompletionsClient(agent_config)
            user = UserSimulator(task.registry, UserConfig(user_config))
            try:
                result = Episode(
                    task, mode, AGENTS[mode](client), user, directory, secrets=secrets
                ).run()
            finally:
                client.client.close()
                user.client.client.close()
            if result["status"] == "error":
                print(
                    f"{task.task_id} {mode}: ERROR {result['error']['type']}",
                    flush=True,
                )
            else:
                scores = ", ".join(f"{s['score']:.1f}" for s in result["submissions"])
                print(f"{task.task_id} {mode}: {scores}", flush=True)
            write_json(output / "summary.json", report(output))
    summary = report(output)
    write_json(output / "summary.json", summary)
    print(f"Results: {output}")
    if summary["errors"]:
        raise RuntimeError(
            f"{len(summary['errors'])} episodes ended with an infrastructure or API error."
        )


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "report":
            print(json.dumps(report(args.directory), indent=2))
        elif args.command == "sandbox-check":
            print(json.dumps(sandbox_check(), indent=2))
        else:
            paths = select_tasks(args.tasks_root, names=args.tasks, domain=args.domain)
            if args.command == "list":
                for path in paths:
                    data = yaml.safe_load((path / "task.yaml").read_text())
                    print(f"{data['id']}\t{data['title']}")
            elif args.command == "validate":
                validate(paths)
            else:
                run(args, paths)
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
