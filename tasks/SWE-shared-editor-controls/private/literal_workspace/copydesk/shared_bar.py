"""Reuse the strip while retaining the existing per-field adapters."""

from copydesk.legacy import FieldToolbar


def install(host):
    def mount(editor):
        FieldToolbar(host, editor, host.shared)

    for editor in host.editors.values():
        mount(editor)

    def changed(event):
        if event["kind"] == "mount_editor":
            mount(event["editor"])

    host.subscribe(changed)
