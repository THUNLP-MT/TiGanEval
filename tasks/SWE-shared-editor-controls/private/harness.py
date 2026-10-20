'One sandboxed workload, with five outcome projections of measured state.'

import json
from pathlib import Path

from tiganeval.taskkit import AnalysisCache, SandboxedProject, artifact_hash, failed_analysis

from .reference import expected_session
from .workload import RUBRICS, private_sessions


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("copydesk/shared_bar.py", "copydesk/support.py")
PROJECT = SandboxedProject(task_root=TASK_ROOT, driver=Path(__file__).with_name("runtime_driver.py"),
                           editable_files=EDITABLE_FILES, prefix="tiganeval-copydesk-")
BUCKETS = {rubric: rubric + "_failures" for rubric in RUBRICS}
_CACHE = AnalysisCache()


def _difference(actual, expected, fields):
    return next((field for field in fields if actual[field] != expected[field]), None)


def _analyse(result, sessions):
    buckets = {value: [] for value in BUCKETS.values()}
    for measured, session in zip(result["sheets"], sessions, strict=True):
        expected = expected_session(session)
        family = session["family"]
        owner = None
        previous_documents = None
        for op, row, ref in zip(session["operations"], measured["rows"], expected["rows"], strict=True):
            actual, wanted = row["state"], ref["state"]
            if op["op"] == "select":
                owner = op["editor"]
            elif op["op"] == "remove_editor" and op["editor"] == owner:
                owner = None
            fields = {"record": session["name"], "label": op["label"], "event": op["op"]}

            def fail(rubric, kind, **details):
                buckets[BUCKETS[rubric]].append({"kind": kind, **fields, **details})

            if family == "ordinary" and op["op"] == "command":
                difference = _difference(actual, wanted, ("documents", "receipts"))
                if difference:
                    fail(RUBRICS[0], "command_changed_another_document" if actual["receipts"] and
                         any(item["editor"] not in {entry["editor"] for entry in wanted["receipts"]}
                             for item in actual["receipts"]) else "command_effect_not_conserved",
                         field=difference, actual_actions=len(actual["receipts"]), expected_actions=len(wanted["receipts"]))
            elif family == "selection" and op["op"] == "command":
                difference = _difference(actual, wanted, ("documents", "selections", "focus"))
                if difference:
                    kind = "selected_text_changed_differently" if difference == "documents" else "toolbar_lost_the_edit_range"
                    fail(RUBRICS[1], kind, field=difference,
                         expected_focus=wanted["focus"], actual_focus=actual["focus"])
            elif family == "theme":
                if op["op"] == "file" and _difference(actual, wanted, ("documents", "receipts")):
                    count, required = len(actual["receipts"]), len(wanted["receipts"])
                    kind = "image_not_inserted" if count < required else "image_delivered_to_stale_context"
                    if count and not required:
                        kind = "unsupported_image_was_inserted"
                    fail(RUBRICS[2], kind, file=op["file"]["name"],
                         actual_actions=len(actual["receipts"]), expected_actions=len(wanted["receipts"]))
                elif op["op"] == "command" and op["control"] == "image" and actual["dialogs"] != wanted["dialogs"]:
                    kind = "image_chooser_unavailable" if not actual["dialogs"] else "image_chooser_kept_old_configuration"
                    fail(RUBRICS[2], kind, actual_dialogs=len(actual["dialogs"]),
                         expected_owner=wanted["dialogs"][0]["owner"] if wanted["dialogs"] else "none")
                elif op["op"] == "command" and op["control"] == "link" and actual["tooltips"] != wanted["tooltips"]:
                    kind = "link_input_unavailable" if not actual["tooltips"] else "link_dialog_opened_in_another_field"
                    fail(RUBRICS[2], kind, actual_dialogs=len(actual["tooltips"]),
                         expected_owner=wanted["tooltips"][0]["editor"] if wanted["tooltips"] else "none")
                if op["op"] in {"select", "background_format"}:

                    actual_view = {key: (item["active"], item["value"]) for key, item in actual["controls"].items()}
                    wanted_view = {key: (item["active"], item["value"]) for key, item in wanted["controls"].items()}
                    picker_values = [item["value"] for item in actual["pickers"]]
                    if actual_view != wanted_view or not picker_values or any(
                            value != wanted["pickers"][0]["value"] for value in picker_values):
                        fail(RUBRICS[2], "format_display_described_another_field", source=op.get("editor", "none"))
            elif family == "availability":
                difference = _difference(actual, wanted, ("documents", "receipts", "dialogs", "tooltips"))
                forbidden = all(item["disabled"] for item in wanted["controls"].values())
                if op["op"] == "command":
                    if forbidden:
                        if actual["receipts"] or actual["documents"] != previous_documents:
                            fail(RUBRICS[3], "unavailable_field_was_edited", field="documents", actual_actions=len(actual["receipts"]))
                        if actual["dialogs"] or actual["tooltips"]:
                            fail(RUBRICS[3], "unavailable_field_opened_a_dialog", field="dialogs" if actual["dialogs"] else "tooltips",
                                 actual_actions=len(actual["receipts"]))
                    elif difference:
                        fail(RUBRICS[3], "controls_did_not_recover", field=difference, actual_actions=len(actual["receipts"]))
                actual_enabled = {key: item["disabled"] for key, item in actual["controls"].items()}
                wanted_enabled = {key: item["disabled"] for key, item in wanted["controls"].items()}
                if actual_enabled != wanted_enabled or any(
                    item["aria_disabled"] != wanted["pickers"][0]["aria_disabled"] or
                    (wanted["pickers"][0]["aria_disabled"] and item["expanded"])
                    for item in actual["pickers"]
                ) or not actual["pickers"]:
                    fail(RUBRICS[3], "availability_display_was_stale", active_controls=sum(
                        not value for value in actual_enabled.values()))
                if owner is None and (any(item["active"] or item["value"] for item in actual["controls"].values()) or
                                      any(item["value"] for item in actual["pickers"])):
                    fail(RUBRICS[3], "unowned_toolbar_retained_style")
            elif family == "lifecycle":
                if actual["bar_count"] > 1 or actual["picker_count"] > wanted["picker_count"] or actual["image_input_count"] > 1:
                    fail(RUBRICS[4], "shared_surface_accumulated_widgets", bars=actual["bar_count"],
                         pickers=actual["picker_count"], image_inputs=actual["image_input_count"])
                elif actual["bar_count"] < 1 or actual["picker_count"] < wanted["picker_count"]:
                    fail(RUBRICS[4], "shared_surface_missing_component", bars=actual["bar_count"], pickers=actual["picker_count"])
                if op["op"] in {"command", "file"} and _difference(actual, wanted, ("documents", "receipts", "dialogs", "tooltips")):
                    count = sum(len(actual[key]) for key in ("receipts", "dialogs", "tooltips"))
                    required = sum(len(wanted[key]) for key in ("receipts", "dialogs", "tooltips"))
                    kind = "dynamic_control_did_not_act" if count < required else "dynamic_control_used_stale_context"
                    if count > required:
                        kind = "dynamic_control_repeated_action"
                    fail(RUBRICS[4], kind, actual_actions=len(actual["receipts"]),
                         expected_actions=len(wanted["receipts"]))
            previous_documents = actual["documents"]
    return buckets


def evaluate_project(artifact_dir):
    def compute():
        sessions = private_sessions()
        result = PROJECT.invoke(Path(artifact_dir), {"sessions": sessions})
        if not result.get("ok"):
            error = str(result.get("error", "sheet stopped"))
            diagnostic = str(result.get("diagnostic", "")).splitlines()
            if "candidate " in error:
                error = diagnostic[-1] if diagnostic else "the sheet stopped without output"
            analysis = failed_analysis(error[:200], tuple(BUCKETS.values()))
        else:
            analysis = _analyse(result, sessions)
        analysis["case"] = {"sheets": len(sessions), "operations": sum(len(item["operations"]) for item in sessions)}
        return analysis
    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(workspace):
    workspace = Path(workspace)
    return {"editable_files": list(EDITABLE_FILES), "workspace_hash": artifact_hash(workspace),
            "page": json.loads((workspace / "copydesk/page.json").read_text()),
            "records": [{"record": str(path.relative_to(workspace)), "scene": json.loads(path.read_text())["scene"]}
                        for path in sorted((workspace / "project_records").glob("*.json"))]}


def public_replay(workspace, path):
    raw = json.loads(Path(path).read_text())
    sessions = [raw, *raw.get("additional_sheets", [])]
    result = PROJECT.invoke(Path(workspace), {"sessions": sessions})
    return {"record": raw["name"], "scene": raw["scene"],
            "current_sheet": result.get("sheets", []),
            "recorded_sheet": raw["recorded_sheet"],
            **({"execution_error": result.get("error"), "diagnostic": result.get("diagnostic")} if not result.get("ok") else {})}
