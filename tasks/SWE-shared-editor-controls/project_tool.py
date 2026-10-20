'Raw project telemetry; no comparisons or outcome verdicts.'

import json
from pathlib import Path
from tiganeval.tools import TaskToolResult
from .private import harness


def run_project(arguments, context):
    workspace = Path(context.workspace).resolve()
    action = arguments.get("action", "status")
    if action == "status":
        data = harness.public_status(workspace)
    elif action == "replay":
        path = (workspace / str(arguments.get("record", ""))).resolve()
        if not path.is_relative_to(workspace / "project_records") or path.suffix != ".json" or not path.is_file():
            raise ValueError("record must name an existing JSON file under project_records/")
        data = harness.public_replay(workspace, path)
    else:
        raise ValueError("action must be status or replay")
    return TaskToolResult(content=json.dumps(data, ensure_ascii=False, indent=2), data={"action": action, **data})
