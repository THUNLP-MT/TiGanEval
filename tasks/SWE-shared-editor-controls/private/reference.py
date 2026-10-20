'Trusted replay of operator intent using frozen public document operations.'

import importlib
import importlib.util
from pathlib import Path
import sys


def host_module():
    name = "_shared_editor_public_reference"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / "workspace" / "copydesk" / "__init__.py"
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return importlib.import_module(name + ".host")


def expected_session(session):
    module = host_module()
    host = module.Host(session["page"])
    active, selection, pending = None, None, None
    rows = []

    def sync():
        available = active is not None and active.connected and active.enabled
        view = module.format_view(active.document, selection) if active else {"bold": False, "size": ""}
        live = host.shared.live_controls()
        host.shared.pickers = [item for item in host.shared.pickers if item.control in live]
        for control in live:
            control.active = view["bold"] if control.command == "bold" else False
            control.value = view["size"] if control.command == "size" else ""
            control.disabled = not available
            if control.kind == "select" and not any(item.control is control for item in host.shared.pickers):
                host.shared.add_picker(control)
        for item in host.shared.pickers:
            item.value = view["size"]
            item.aria_disabled = not available
            if not available:
                item.expanded = False

    sync()
    for op in session["operations"]:
        host.operate(op)
        if op["op"] == "select":
            active = host.editors[op["editor"]]
            selection = list(op["range"])
        elif op["op"] == "remove_editor" and active is host.editors[op["editor"]]:
            active, selection = None, None
        elif op["op"] == "command":
            control = host.shared.controls[op["control"]]
            if active is not None and active.connected and active.enabled and control.attached:
                host.restore(active, selection)
                if control.command == "image":
                    image_input = host.shared.image_input(host, active)
                    image_input.owner = active.key
                    image_input.accept = active.mimetypes
                    image_input.on_change = lambda file: None
                    host.open_image(image_input)
                    pending = active
                elif control.command == "link":
                    host.open_tooltip(active, "link")
                else:
                    selection = host.write(active, selection, control.command, op.get("value"))
                    host.restore(active, selection)
        elif op["op"] == "file":
            if pending is not None and pending is active and active.connected and active.enabled:
                if op["file"]["type"] in active.mimetypes:
                    selection = host.write(active, selection, "image", op["file"])
                    host.restore(active, selection)
            pending = None
        sync()
        rows.append({"label": op["label"], "state": module.snapshot(host)})
    return {"name": session["name"], "rows": rows}
