'Standard tools for the production sheet workspace.'

from tiganeval.taskkit import control_tools, experiment_tool, file_tools
from .project_tool import run_project

EDITABLE_PATHS = ("copydesk/shared_bar.py", "copydesk/support.py")


def get_actions():
    return (
        *file_tools(editable_paths=EDITABLE_PATHS, workspace_description="production sheet workspace"),
        {"name": "run_project", "handler": run_project,
         "description": "status lists the production sheet and available desk recordings. replay runs one recording and returns document contents, selections, focus, controls, native dialogs and command receipts beside the recorded sheet state.",
         "parameters": {"type": "object", "properties": {
             "action": {"type": "string", "enum": ["status", "replay"]},
             "record": {"type": "string", "description": "Path of a JSON recording under project_records/."}},
             "required": ["action"], "additionalProperties": False}},
        experiment_tool(timeout=30.0),
        *control_tools(),
    )
