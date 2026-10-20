"""Document operations shared by the production sheet and the single-field view.

Ranges are [start, length]. Formatting keeps the range; inserting a stamp or
image moves its caret past the inserted text. An empty range sets the typing
format. Mixed selected formats display the neutral value in the toolbar.
"""

from copy import deepcopy


def new_document(spec):
    text = str(spec.get("text", ""))
    document = {"text": text, "marks": [{} for _ in text], "typing": {}}
    for item in spec.get("formats", []):
        start, length = item["range"]
        for index in range(start, start + length):
            document["marks"][index].update(item["attributes"])
    return document


def format_view(document, selection):
    if selection is None:
        return {"bold": False, "size": ""}
    start, length = selection
    rows = document["marks"][start:start + length] if length else [document["typing"]]
    return {
        key: rows[0].get(key, default) if rows and all(
            row.get(key, default) == rows[0].get(key, default) for row in rows
        ) else default
        for key, default in (("bold", False), ("size", ""))
    }


def document_effect(document, selection, command, value=None, *, stamp=""):
    """The single-field operation, including its resulting edit range."""
    result = deepcopy(document)
    if selection is None:
        return result, None
    start, length = map(int, selection)
    if start < 0 or length < 0 or start + length > len(result["text"]):
        raise ValueError("selection lies outside the document")
    if command in {"bold", "size"}:
        if command == "bold" and value is None:
            value = not format_view(result, selection)["bold"]
        rows = result["marks"][start:start + length] if length else [result["typing"]]
        for row in rows:
            if value in (False, "", None):
                row.pop(command, None)
            else:
                row[command] = value
        return result, [start, length]
    if command == "stamp":
        inserted = stamp
    elif command == "image":
        inserted = "[" + str(value["name"]) + "]"
    else:
        raise ValueError(f"unknown document command: {command}")
    result["text"] = result["text"][:start] + inserted + result["text"][start + length:]
    result["marks"][start:start + length] = [{} for _ in inserted]
    return result, [start + len(inserted), 0]


def document_view(document):
    """Compact rendering of the document's text, styled spans and typing state."""
    spans = []
    for index, attributes in enumerate(document["marks"]):
        if not attributes:
            continue
        if spans and spans[-1][0] + spans[-1][1] == index and spans[-1][2] == attributes:
            spans[-1][1] += 1
        else:
            spans.append([index, 1, dict(attributes)])
    return {"text": document["text"], "spans": spans, "typing": dict(document["typing"])}
