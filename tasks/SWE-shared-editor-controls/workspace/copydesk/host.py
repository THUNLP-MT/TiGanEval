"""Synchronous component host for the copy desk's recorded interaction stream.

subscribe(callback) receives lifecycle/selection/change notifications. User
selection identifies the field the operator entered. Background format changes
emit source='api' and leave keyboard focus alone. A pointer command can blur an
editor into the toolbar before delivering the control callback; that blur has
selection=None and destination='toolbar'. restore() emits source='api'.

Controls and theme objects belong to their Bar. Detaching a control does not
erase its listeners; reattaching the same object retains them. Low-level write
also serves import jobs, so it is not a permission check for toolbar actions.
"""

from copy import deepcopy
from .protocol import new_document, document_effect, document_view, format_view


class Editor:
    def __init__(self, spec):
        self.key = str(spec["id"])
        self.document = new_document(spec)
        self.stamp = str(spec.get("stamp", ""))
        self.mimetypes = tuple(spec.get("mimetypes", ["image/png"]))
        self.enabled = not bool(spec.get("read_only", False))
        self.connected = True
        self.selection = None


class Control:
    def __init__(self, spec):
        self.key = str(spec["id"])
        self.command = str(spec["command"])
        self.kind = str(spec.get("kind", "button"))
        self.attached = True
        self.disabled = False
        self.active = False
        self.value = ""
        self.listeners = []

    def listen(self, callback):
        self.listeners.append(callback)

    def unlisten(self, callback):
        self.listeners = [item for item in self.listeners if item is not callback]


class Picker:
    def __init__(self, control):
        self.control = control
        self.value = ""
        self.aria_disabled = False
        self.expanded = False

    def press(self):
        if not self.aria_disabled:
            self.expanded = True


class ImageInput:
    def __init__(self, host, editor):
        self.owner = editor.key
        self.accept = tuple(editor.mimetypes)

        def upload(file):
            if file["type"] in editor.mimetypes:
                selection = editor.selection or [0, 0]
                result = host.write(editor, selection, "image", file)
                host.restore(editor, result)

        self.on_change = upload


class Bar:
    def __init__(self, name, controls):
        self.name = name
        self.controls = {spec["id"]: Control(spec) for spec in controls}
        self.pickers = []
        self.image_inputs = []

    def live_controls(self):
        return [control for control in self.controls.values() if control.attached]

    def add_picker(self, control):
        picker = Picker(control)
        self.pickers.append(picker)
        return picker

    def image_input(self, host, editor):
        if not self.image_inputs:
            self.image_inputs.append(ImageInput(host, editor))
        return self.image_inputs[0]


class Host:
    def __init__(self, page):
        self.control_specs = deepcopy(page["controls"])
        self.shared = Bar("production-toolbar", self.control_specs)
        self.bars = [self.shared]
        self.editors = {spec["id"]: Editor(spec) for spec in page["editors"]}
        self.subscribers = []
        self.focus_target = "none"
        self.pending_input = None
        self.begin_step()

    def begin_step(self):
        self.receipts = []
        self.dialogs = []
        self.tooltips = []

    def subscribe(self, callback):
        self.subscribers.append(callback)

    def notify(self, **event):
        for callback in tuple(self.subscribers):
            callback(event)

    def add_bar(self, name):
        bar = Bar(name, self.control_specs)
        self.bars.append(bar)
        return bar

    def select(self, editor, selection, *, source="user"):
        for other in self.editors.values():
            other.selection = None
        editor.selection = list(selection)
        self.focus_target = editor.key
        self.notify(kind="selection", editor=editor, selection=list(selection), source=source,
                    destination="editor")

    def restore(self, editor, selection):
        self.select(editor, selection, source="api")

    def toolbar_focus(self):
        previous = self.editors.get(self.focus_target)
        self.focus_target = "toolbar"
        if previous is not None:
            previous.selection = None
            self.notify(kind="selection", editor=previous, selection=None, source="user",
                        destination="toolbar")

    def write(self, editor, selection, command, value=None):
        document, after = document_effect(editor.document, selection, command, value, stamp=editor.stamp)
        if selection is not None:
            editor.document = document
            self.receipts.append({"editor": editor.key, "command": command, "value": deepcopy(value),
                                  "range": list(selection), "after_range": after})
            self.notify(kind="change", editor=editor, source="api")
        return after

    def open_image(self, image_input):
        self.pending_input = image_input
        self.focus_target = "file-dialog"
        self.dialogs.append({"owner": image_input.owner, "accept": list(image_input.accept)})

    def open_tooltip(self, editor, command):
        self.focus_target = f"{editor.key}:{command}-input"
        self.tooltips.append({"editor": editor.key, "command": command})

    def operate(self, op):
        self.begin_step()
        kind = op["op"]
        if kind == "select":
            self.select(self.editors[op["editor"]], op["range"])
        elif kind == "command":
            control = self.shared.controls[op["control"]]
            if op.get("pointer", False):
                self.toolbar_focus()
            # A normal button click honours disabled. A dispatched change
            # notification (including native selects) still reaches listeners.
            if control.attached and not (control.disabled and control.kind == "button"
                                         and not op.get("dispatch", False)):
                control.value = op.get("value", "")
                for callback in tuple(control.listeners):
                    callback(op.get("value"))
        elif kind == "picker":
            for picker in self.shared.pickers:
                if picker.control.key == op["control"] and picker.control.attached:
                    picker.press()
                    break
        elif kind == "file":
            image_input, self.pending_input = self.pending_input, None
            if image_input is not None:
                image_input.on_change(dict(op["file"]))
        elif kind == "background_format":
            editor = self.editors[op["editor"]]
            editor.document, _ = document_effect(editor.document, op["range"], op["command"], op["value"])
            self.notify(kind="change", editor=editor, source="api")
        elif kind == "enabled":
            editor = self.editors[op["editor"]]
            editor.enabled = bool(op["value"])
            self.notify(kind="enabled", editor=editor)
        elif kind == "remove_editor":
            editor = self.editors[op["editor"]]
            editor.connected = False
            editor.selection = None
            if self.focus_target == editor.key:
                self.focus_target = "none"
            self.notify(kind="remove_editor", editor=editor)
        elif kind == "mount_editor":
            editor = Editor(op["editor"])
            self.editors[editor.key] = editor
            self.notify(kind="mount_editor", editor=editor)
        elif kind == "remove_control":
            control = self.shared.controls[op["control"]]
            control.attached = False
            self.notify(kind="controls")
        elif kind == "add_control":
            spec = op["control"]
            control = self.shared.controls.get(spec["id"])
            if control is None:
                control = self.shared.controls[spec["id"]] = Control(spec)
            control.attached = True
            self.notify(kind="controls")
        elif kind != "inspect":
            raise ValueError(f"unknown host operation: {kind}")


def snapshot(host):
    """Read component and document state; integration return values are unused."""
    return {
        "documents": {key: document_view(editor.document) for key, editor in host.editors.items()},
        "selections": {key: deepcopy(editor.selection) for key, editor in host.editors.items()},
        "focus": host.focus_target,
        "controls": {control.key: {"active": control.active, "value": control.value,
                                  "disabled": control.disabled}
                     for control in host.shared.live_controls()},
        "pickers": [{"control": item.control.key, "value": item.value,
                     "aria_disabled": item.aria_disabled, "expanded": item.expanded}
                    for item in host.shared.pickers],
        "bar_count": len(host.bars),
        "image_input_count": sum(len(bar.image_inputs) for bar in host.bars),
        "picker_count": sum(len(bar.pickers) for bar in host.bars),
        "receipts": deepcopy(host.receipts),
        "dialogs": deepcopy(host.dialogs),
        "tooltips": deepcopy(host.tooltips),
    }
