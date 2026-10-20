"""One control strip for the production sheet."""

from copydesk.protocol import format_view


class SharedBar:
    def __init__(self, host):
        self.host = host
        self.bar = host.shared
        self.active = None
        self.ranges = {}
        self.bindings = {}
        self.pickers = {}
        host.subscribe(self.changed)
        self.reconcile()
        self.refresh()

    def usable(self):
        return self.active is not None and self.active.connected and self.active.enabled

    def reconcile(self):
        live = set(self.bar.live_controls())
        for control, callback in list(self.bindings.items()):
            if control not in live:
                control.unlisten(callback)
                del self.bindings[control]
                picker = self.pickers.pop(control, None)
                if picker is not None:
                    self.bar.pickers.remove(picker)
        for control in self.bar.live_controls():
            if control not in self.bindings:
                callback = lambda value, control=control: self.command(control, value)
                self.bindings[control] = callback
                control.listen(callback)
                if control.kind == "select":
                    self.pickers[control] = self.bar.add_picker(control)

    def changed(self, event):
        if event["kind"] == "selection" and event.get("source") == "user":
            if event.get("selection") is not None:
                self.active = event["editor"]
                self.ranges[self.active] = list(event["selection"])
        elif event["kind"] == "remove_editor":
            self.ranges.pop(event["editor"], None)
            if event["editor"] is self.active:
                self.active = None
        elif event["kind"] == "controls":
            self.reconcile()
        self.refresh()

    def refresh(self):
        usable = self.usable()
        view = format_view(self.active.document, self.ranges.get(self.active)) if self.active else {"bold": False, "size": ""}
        for control in self.bar.live_controls():
            control.disabled = not usable
            control.active = view["bold"] if control.command == "bold" else False
            control.value = view["size"] if control.command == "size" else ""
        for control, picker in self.pickers.items():
            picker.value = view["size"]
            picker.aria_disabled = not usable
            if not usable:
                picker.expanded = False

    def command(self, control, value):
        if not self.usable() or not control.attached:
            self.refresh()
            return
        editor = self.active
        selection = self.ranges.get(editor)
        self.host.restore(editor, selection)
        if control.command == "image":
            image_input = self.bar.image_input(self.host, editor)
            image_input.owner = editor.key
            image_input.accept = tuple(editor.mimetypes)

            def upload(file):
                if self.usable() and self.active is editor and file["type"] in editor.mimetypes:
                    after = self.host.write(editor, selection, "image", file)
                    self.ranges[editor] = after
                    self.host.restore(editor, after)
                    self.refresh()

            image_input.on_change = upload
            self.host.open_image(image_input)
        elif control.command == "link":
            self.host.open_tooltip(editor, "link")
        else:
            after = self.host.write(editor, selection, control.command, value)
            self.ranges[editor] = after
            self.host.restore(editor, after)
        self.refresh()


def install(host):
    SharedBar(host)
