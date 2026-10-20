"""Mount the production sheet's toolbar adapters."""

from .legacy import FieldToolbar


def install(host):
    def mount(editor):
        FieldToolbar(host, editor, host.add_bar("field/" + editor.key))

    for editor in host.editors.values():
        mount(editor)

    def changed(event):
        if event["kind"] == "mount_editor":
            mount(event["editor"])

    host.subscribe(changed)
