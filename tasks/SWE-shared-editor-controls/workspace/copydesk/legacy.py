"""The production sheet's adapter from the previous single-field layout."""

from .protocol import format_view


class FieldToolbar:
    def __init__(self, host, editor, bar):
        self.host, self.editor, self.bar = host, editor, bar
        self.range = [0, 0]
        for control in bar.live_controls():
            control.listen(lambda value, c=control: self.command(c, value))
            if control.kind == "select":
                bar.add_picker(control)
        host.subscribe(self.changed)

    def changed(self, event):
        if event.get("editor") is not self.editor:
            return
        if event["kind"] == "selection" and event.get("selection") is not None:
            self.range = list(event["selection"])
        self.refresh()

    def refresh(self):
        view = format_view(self.editor.document, self.range)
        for control in self.bar.live_controls():
            if control.command == "bold":
                control.active = view["bold"]
            if control.command == "size":
                control.value = view["size"]
        for picker in self.bar.pickers:
            picker.value = view["size"]

    def command(self, control, value):
        self.host.restore(self.editor, self.range)
        if control.command == "image":
            self.host.open_image(self.bar.image_input(self.host, self.editor))
        elif control.command == "link":
            self.host.open_tooltip(self.editor, "link")
        else:
            self.range = self.host.write(self.editor, self.range, control.command, value)
            self.host.restore(self.editor, self.range)
        self.refresh()
