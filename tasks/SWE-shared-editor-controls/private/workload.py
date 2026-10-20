'Inputs for desk recordings and the separately composed release workload.'

from copy import deepcopy
import random


CONTROLS = [
    {"id": "bold", "command": "bold", "kind": "button"},
    {"id": "size", "command": "size", "kind": "select"},
    {"id": "stamp", "command": "stamp", "kind": "button"},
    {"id": "image", "command": "image", "kind": "button"},
    {"id": "link", "command": "link", "kind": "button"},
]
RUBRICS = (
    "active_document_commands", "selection_survives_toolbar_focus",
    "theme_tracks_editor_context", "unavailable_context_is_inert",
    "shared_control_lifecycle",
)
PUBLIC = (
    "copy-desk-switch", "toolbar-focus-transfer", "image-desk-review", "layout-remount",
)


def editor(key, text, stamp, mimetype, *, styled=False):
    return {"id": key, "text": text, "stamp": stamp, "mimetypes": [mimetype],
            "formats": [{"range": [1, 3], "attributes": {"bold": True, "size": "large"}}] if styled else []}


def session(name, family, number=11, count=2):
    rng = random.Random(number)
    words = ["Headline for the morning edition", "Body copy for the production sheet",
             "Caption beside the lead photograph"]
    keys = ["headline", "body", "caption"][:count]
    if number > 100:
        keys = [f"{key}-release" for key in keys]
    editors = [editor(key, words[index] + " " + str(rng.randrange(100, 999)),
                      f"<{key} approved>", ("image/gif", "image/webp", "image/avif")[index],
                      styled=index == 0)
               for index, key in enumerate(keys)]
    page = {"controls": deepcopy(CONTROLS), "editors": editors}
    a, b = keys[0], keys[-1]
    operations = []

    def add(op, label, **fields):
        operations.append({"op": op, "label": label, **fields})

    def select(key, start=1, length=3):
        add("select", f"select {key} at {start} for {length}", editor=key, range=[start, length])

    def command(control, **fields):
        add("command", f"press {control} at step {len(operations) + 1}", control=control, **fields)

    def image_for(key, mime, filename):
        select(key, 2, 0)
        command("image", pointer=True)
        add("file", f"choose {filename}", file={"name": filename, "type": mime})

    add("inspect", "open production sheet")
    if family == "ordinary":
        for key in reversed(keys):
            select(key, 2, 4)
            command("bold")
            command("size", value="small")
        for key in keys:
            select(key, 3, 0)
            command("stamp")
    elif family == "selection":
        select(b, 5, 2)
        select(a, 2, 6)
        command("bold", pointer=True)
        command("size", value="small", pointer=True)
        select(b, 7, 3)
        command("size", value="large", pointer=True)
        command("bold", pointer=True)
    elif family == "theme":
        select(a)
        select(b)
        add("background_format", f"import styling into {a}", editor=a, range=[1, 3], command="size", value="small")
        image_for(a, editors[0]["mimetypes"][0], "headline-photo.gif")
        image_for(b, editors[-1]["mimetypes"][0], "body-photo.webp")
        select(a, 1, 2)
        command("link")
        select(b, 0, 2)
        command("link")

        command("image")
        add("file", "choose unsupported attachment", file={"name": "notes.txt", "type": "text/plain"})
    elif family == "availability":
        select(a)
        add("enabled", f"lock {a} for review", editor=a, value=False)
        command("bold", dispatch=True)
        command("size", value="small", dispatch=True)
        add("picker", "open size menu during review", control="size")
        command("image", dispatch=True)
        command("link", dispatch=True)
        select(b, 3, 4)
        command("bold")
        add("remove_editor", f"close {b}", editor=b)
        command("stamp", dispatch=True)
        command("image", dispatch=True)
        add("enabled", f"release {a} from review", editor=a, value=True)
        command("bold", dispatch=True)
        select(a, 2, 2)
        command("size", value="small", pointer=True)
    elif family == "lifecycle":
        image_for(a, editors[0]["mimetypes"][0], "opening-image.gif")
        add("add_control", "insert approval button", control={"id": "approval", "command": "stamp"})
        select(b, 4, 0)
        command("approval")
        add("remove_control", "remove approval button", control="approval")
        add("add_control", "reattach approval button", control={"id": "approval", "command": "stamp"})
        select(a, 1, 0)
        command("approval")
        add("remove_control", "unmount size select", control="size")
        add("add_control", "remount size select", control={"id": "size", "command": "size", "kind": "select"})
        command("size", value="small", pointer=True)
        add("remove_editor", f"unmount {a}", editor=a)
        command("approval", dispatch=True)
        replacement = editor(a, "Replacement field mounted during layout", "<replacement approved>", "image/avif")
        add("mount_editor", f"recreate {a}", editor=replacement)
        command("approval", dispatch=True)
        image_for(a, "image/avif", "replacement-photo.avif")
        command("approval")
        select(b, 1, 3)
        command("size", value="large")
    else:
        raise ValueError(family)
    return {"name": name, "family": family, "page": page, "operations": operations}


def public_sessions():
    normal = session(PUBLIC[0], "ordinary", 11)
    transfer = session(PUBLIC[1], "selection", 22)
    images = session(PUBLIC[2], "theme", 33)
    availability = session("review-lock", "availability", 34)

    images["operations"].extend(availability["operations"][1:])
    remount = session(PUBLIC[3], "lifecycle", 44)
    return [normal, transfer, images, remount]


def private_sessions():
    sessions = [session("release-" + family, family, 90253 + index, 3)
                for index, family in enumerate(("ordinary", "selection", "theme", "availability", "lifecycle"))]


    sessions[-1]["page"]["editors"].reverse()
    sessions.append(session("single-field-compatibility", "ordinary", 91253, 1))
    sessions.append(session("second-layout-order", "lifecycle", 93253, 2))
    sessions[-1]["page"]["editors"].reverse()
    return sessions
