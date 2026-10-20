'Deterministic editor sessions for the scene-checkpoint project.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


REGISTRY_ENTRIES: tuple[dict[str, Any], ...] = (
    {"key": "Transform", "kind": "data"},
    {"key": "Tint", "kind": "data"},
    {"key": "Label", "kind": "data"},
    {"key": "Frozen", "kind": "tag"},
    {"key": "Locked", "kind": "tag"},
    {"key": "Selection", "kind": "data"},
    {"key": "ChildOf", "kind": "relation"},
    {"key": "MountedOn", "kind": "relation", "carries_data": True},
)


PAINT_TAG = "Frozen"


SESSION_TRAIT = "Selection"


def _transform(x: float, y: float, z: float = 0.0) -> dict[str, Any]:
    return {"position": {"x": float(x), "y": float(y), "z": float(z)}, "scale": 1.0}


def _tint(red: int, green: int, blue: int) -> dict[str, Any]:
    return {"rgb": [int(red), int(green), int(blue)], "strength": 100}


def _label(text: str) -> dict[str, Any]:
    return {"text": str(text), "shown": True}


def _fillers(variant: int) -> tuple[str, ...]:
    return ("bin", "cable") if int(variant) > 4 else ()


def _add_fillers(variant: int, parent: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for position, prop in enumerate(_fillers(variant)):
        events.append({"type": "create", "label": f"add-{prop}", "prop": prop})
        events.append(
            {
                "type": "set_trait",
                "label": f"place-{prop}",
                "prop": prop,
                "key": "Transform",
                "value": _transform(9.0 + position, 4.0 + variant),
            }
        )
        events.append(
            {
                "type": "set_trait",
                "label": f"name-{prop}",
                "prop": prop,
                "key": "Label",
                "value": _label(prop),
            }
        )
        events.append(
            {
                "type": "link",
                "label": f"parent-{prop}",
                "prop": prop,
                "key": "ChildOf",
                "target": parent,
            }
        )
    return events


def _paint(variant: int) -> list[dict[str, Any]]:
    'A set-dressing session: checkpoint the set, batch paint it, revert.'
    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-crate-a", "prop": "crate-a"},
        {"type": "create", "label": "add-crate-b", "prop": "crate-b"},
        {"type": "create", "label": "add-lamp", "prop": "lamp"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-pallet", "prop": "pallet", "key": "Transform", "value": _transform(2, variant)},
        {"type": "set_trait", "label": "place-crate-a", "prop": "crate-a", "key": "Transform", "value": _transform(3, variant + 1)},
        {"type": "set_trait", "label": "place-crate-b", "prop": "crate-b", "key": "Transform", "value": _transform(4, variant + 2)},
        {"type": "set_trait", "label": "place-lamp", "prop": "lamp", "key": "Transform", "value": _transform(5, variant + 3)},
        {"type": "set_trait", "label": "paint-crate-a", "prop": "crate-a", "key": "Tint", "value": _tint(120 + variant, 90, 40)},
        {"type": "set_trait", "label": "paint-crate-b", "prop": "crate-b", "key": "Tint", "value": _tint(60, 130 + variant, 20)},
        {"type": "set_trait", "label": "name-lamp", "prop": "lamp", "key": "Label", "value": _label("key light")},
        {"type": "set_trait", "label": "lock-crate-b", "prop": "crate-b", "key": "Locked", "value": True},
        {"type": "link", "label": "parent-crate-a", "prop": "crate-a", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "parent-crate-b", "prop": "crate-b", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "mount-pallet", "prop": "pallet", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 2.0, "y": 0.0}}},
        *_add_fillers(variant, "stage"),
        {"type": "select", "label": "select-crate-a", "prop": "crate-a"},
        {"type": "capture", "label": "checkpoint-set", "name": "before-paint", "scope": "scene"},
        {"type": "capture", "label": "checkpoint-lamp", "name": "lamp-mark", "scope": "entity", "prop": "lamp"},
        {"type": "set_trait", "label": "repaint-crate-a", "prop": "crate-a", "key": "Tint", "value": _tint(10, 10, 10)},
        {"type": "set_trait", "label": "freeze-crate-a", "prop": "crate-a", "key": PAINT_TAG, "value": True},
        {"type": "set_trait", "label": "freeze-crate-b", "prop": "crate-b", "key": PAINT_TAG, "value": True},
        {"type": "set_trait", "label": "lock-pallet", "prop": "pallet", "key": "Locked", "value": True},
        {"type": "set_trait", "label": "freeze-lamp", "prop": "lamp", "key": PAINT_TAG, "value": True},
        {"type": "remove_trait", "label": "clear-lamp-name", "prop": "lamp", "key": "Label"},
        {"type": "remove_trait", "label": "unlock-crate-b", "prop": "crate-b", "key": "Locked"},
        {"type": "restore_entity", "label": "revert-lamp", "prop": "lamp", "name": "lamp-mark"},
        {"type": "restore", "label": "revert-set", "name": "before-paint"},
        {"type": "inspect", "label": "paint-final"},
    ]


def _slots(variant: int) -> list[dict[str, Any]]:
    'A cleanup session: a prop is deleted, a replacement is dropped in, revert.'
    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-crate", "prop": "crate"},
        {"type": "create", "label": "add-barrel", "prop": "barrel"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-pallet", "prop": "pallet", "key": "Transform", "value": _transform(1, variant)},
        {"type": "set_trait", "label": "place-crate", "prop": "crate", "key": "Transform", "value": _transform(2, variant + 1)},
        {"type": "set_trait", "label": "place-barrel", "prop": "barrel", "key": "Transform", "value": _transform(3, variant + 2)},
        {"type": "set_trait", "label": "name-pallet", "prop": "pallet", "key": "Label", "value": _label("pallet stack")},
        {"type": "link", "label": "parent-crate", "prop": "crate", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "parent-barrel", "prop": "barrel", "key": "ChildOf", "target": "stage"},
        {"type": "link", "label": "mount-pallet", "prop": "pallet", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 1.0, "y": 0.5}}},
        *_add_fillers(variant, "stage"),
        {"type": "select", "label": "select-pallet", "prop": "pallet"},
        {"type": "capture", "label": "checkpoint-set", "name": "before-cleanup", "scope": "scene"},
        {"type": "destroy", "label": "delete-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-standin", "prop": "standin"},
        {"type": "set_trait", "label": "place-standin", "prop": "standin", "key": "Transform", "value": _transform(1, variant + 6)},
        {"type": "set_trait", "label": "name-standin", "prop": "standin", "key": "Label", "value": _label("crate stand")},
        {"type": "link", "label": "parent-crate-again", "prop": "crate", "key": "ChildOf", "target": "standin"},
        {"type": "restore", "label": "revert-cleanup", "name": "before-cleanup"},
        {"type": "inspect", "label": "slots-final"},
    ]


def _drift(variant: int) -> list[dict[str, Any]]:
    'A nudging session: checkpoint once, then nudge and revert three times.'
    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-crate", "prop": "crate"},
        {"type": "create", "label": "add-lamp", "prop": "lamp"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-crate", "prop": "crate", "key": "Transform", "value": _transform(6, variant)},
        {"type": "set_trait", "label": "place-lamp", "prop": "lamp", "key": "Transform", "value": _transform(7, variant)},
        {"type": "set_trait", "label": "paint-crate", "prop": "crate", "key": "Tint", "value": _tint(200, 40 + variant, 40)},
        {"type": "link", "label": "parent-crate", "prop": "crate", "key": "ChildOf", "target": "stage"},
        {"type": "link", "label": "mount-crate", "prop": "crate", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 6.0, "y": float(variant)}}},
        *_add_fillers(variant, "stage"),
        {"type": "select", "label": "select-crate", "prop": "crate"},
        {"type": "capture", "label": "checkpoint-set", "name": "mark", "scope": "scene"},
        {"type": "brush", "label": "nudge-tint-1", "prop": "crate", "key": "Tint", "path": ["rgb", 1], "value": 11},
        {"type": "brush_edge", "label": "nudge-mount-1", "prop": "crate", "key": "MountedOn", "target": "stage", "path": ["offset", "x"], "value": 11.5},
        {"type": "restore", "label": "revert-1", "name": "mark"},
        {"type": "brush_edge", "label": "nudge-mount-2", "prop": "crate", "key": "MountedOn", "target": "stage", "path": ["offset", "y"], "value": 12.5},
        {"type": "restore", "label": "revert-2", "name": "mark"},
        {"type": "brush", "label": "nudge-3", "prop": "crate", "key": "Tint", "path": ["rgb", 0], "value": 5},
        {"type": "restore", "label": "revert-3", "name": "mark"},
        {"type": "inspect", "label": "drift-final"},
    ]


def _refusal(variant: int) -> list[dict[str, Any]]:
    'A session in which the checkpoint offered to the level does not fit it.'
    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-crate", "prop": "crate"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-pallet", "prop": "pallet", "key": "Transform", "value": _transform(1, variant)},
        {"type": "set_trait", "label": "place-crate", "prop": "crate", "key": "Transform", "value": _transform(2, variant + 1)},
        {"type": "set_trait", "label": "paint-crate", "prop": "crate", "key": "Tint", "value": _tint(80, 80, 80 + variant)},
        {"type": "link", "label": "parent-crate", "prop": "crate", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "mount-pallet", "prop": "pallet", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 0.5, "y": 0.5}}},
        *_add_fillers(variant, "stage"),
        {"type": "select", "label": "select-crate", "prop": "crate"},
        {"type": "record_reference", "label": "file-on-disk", "name": "yesterday"},
        {"type": "set_trait", "label": "move-crate", "prop": "crate", "key": "Transform", "value": _transform(8, variant + 4)},
        {"type": "set_trait", "label": "lock-pallet", "prop": "pallet", "key": "Locked", "value": True},
        {"type": "restore_broken", "label": "revert-missing-prop", "name": "yesterday", "fault": "dropped_target"},
        {"type": "restore_broken", "label": "revert-stray-key", "name": "yesterday", "fault": "unknown_key"},
        {"type": "restore", "label": "revert-yesterday", "name": "yesterday"},
        {"type": "inspect", "label": "refusal-final"},
    ]


def _handover(variant: int) -> list[dict[str, Any]]:
    "The next morning: yesterday's per-prop files opened on a level that moved."

    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-crate", "prop": "crate"},
        {"type": "create", "label": "add-lamp", "prop": "lamp"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-pallet", "prop": "pallet", "key": "Transform", "value": _transform(1, variant)},
        {"type": "set_trait", "label": "place-crate", "prop": "crate", "key": "Transform", "value": _transform(2, variant + 1)},
        {"type": "set_trait", "label": "place-lamp", "prop": "lamp", "key": "Transform", "value": _transform(3, variant + 2)},
        {"type": "set_trait", "label": "name-lamp", "prop": "lamp", "key": "Label", "value": _label("fill light")},
        {"type": "set_trait", "label": "freeze-lamp", "prop": "lamp", "key": PAINT_TAG, "value": True},
        {"type": "link", "label": "parent-crate", "prop": "crate", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "parent-crate-again", "prop": "crate", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "brace-crate", "prop": "crate", "key": "ChildOf", "target": "stage"},
        {"type": "link", "label": "mount-crate", "prop": "crate", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 2.0, "y": float(variant)}}},
        {"type": "link", "label": "mount-pallet", "prop": "pallet", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 0.0, "y": 1.5}}},
        *_add_fillers(variant, "stage"),
        {"type": "select", "label": "select-crate", "prop": "crate"},
        {"type": "capture", "label": "checkpoint-crate", "name": "crate-yesterday", "scope": "entity", "prop": "crate"},
        {"type": "capture", "label": "checkpoint-lamp", "name": "lamp-yesterday", "scope": "entity", "prop": "lamp"},
        {"type": "brush_edge", "label": "nudge-crate-mount-before-revert", "prop": "crate", "key": "MountedOn", "target": "stage", "path": ["offset", "x"], "value": 17.0},
        {"type": "set_trait", "label": "move-crate", "prop": "crate", "key": "Transform", "value": _transform(7, variant + 5)},
        {"type": "unlink", "label": "remove-crate-brace", "prop": "crate", "key": "ChildOf", "target": "stage"},
        {"type": "link", "label": "hang-crate-from-lamp", "prop": "crate", "key": "ChildOf", "target": "lamp"},
        {"type": "restore_entity", "label": "revert-crate", "prop": "crate", "name": "crate-yesterday"},
        {"type": "brush_edge", "label": "nudge-crate-mount-after-revert", "prop": "crate", "key": "MountedOn", "target": "stage", "path": ["offset", "y"], "value": 19.0},
        {"type": "destroy", "label": "delete-pallet", "prop": "pallet"},
        {"type": "set_trait", "label": "repaint-crate", "prop": "crate", "key": "Tint", "value": _tint(15, 15, 15)},
        {"type": "offer_entity", "label": "revert-crate-again", "prop": "crate", "name": "crate-yesterday", "fault": "stale_link"},
        {"type": "offer_entity", "label": "revert-lamp-tag-payload", "prop": "lamp", "name": "lamp-yesterday", "fault": "tag_payload"},
        {"type": "offer_entity", "label": "revert-lamp-stray-key", "prop": "lamp", "name": "lamp-yesterday", "fault": "unknown_key"},
        {"type": "destroy", "label": "delete-lamp", "prop": "lamp"},
        {"type": "offer_entity", "label": "revert-deleted-lamp", "prop": "lamp", "name": "lamp-yesterday", "fault": "missing_subject"},
        {"type": "inspect", "label": "handover-final"},
    ]


def _panel(variant: int) -> list[dict[str, Any]]:
    'A session in which the change panel is asked what differs.'
    wide = int(variant) > 4
    return [
        {"type": "define", "label": "open-level"},
        {"type": "create", "label": "add-stage", "prop": "stage"},
        {"type": "create", "label": "add-pallet", "prop": "pallet"},
        {"type": "create", "label": "add-crate-a", "prop": "crate-a"},
        {"type": "create", "label": "add-crate-b", "prop": "crate-b"},
        {"type": "set_trait", "label": "place-stage", "prop": "stage", "key": "Transform", "value": _transform(0, 0)},
        {"type": "set_trait", "label": "place-pallet", "prop": "pallet", "key": "Transform", "value": _transform(1, variant)},
        {"type": "set_trait", "label": "place-crate-a", "prop": "crate-a", "key": "Transform", "value": _transform(2, variant + 1)},
        {"type": "set_trait", "label": "place-crate-b", "prop": "crate-b", "key": "Transform", "value": _transform(3, variant + 2)},
        {"type": "set_trait", "label": "paint-crate-a", "prop": "crate-a", "key": "Tint", "value": _tint(30, 140, 200)},
        {"type": "set_trait", "label": "name-pallet", "prop": "pallet", "key": "Label", "value": _label("pallet stack")},
        {"type": "link", "label": "parent-crate-a", "prop": "crate-a", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "shadow-crate-a", "prop": "crate-a", "key": "ChildOf", "target": "stage"},
        {"type": "link", "label": "parent-crate-b", "prop": "crate-b", "key": "ChildOf", "target": "pallet"},
        {"type": "link", "label": "mount-pallet", "prop": "pallet", "key": "MountedOn", "target": "stage", "data": {"offset": {"x": 1.0, "y": 2.0}}},
        *_add_fillers(variant, "stage"),
        {"type": "record_reference", "label": "file-on-disk", "name": "saved"},
        {
            "type": "panel",
            "label": "panel-unchanged",
            "scope": "scene",
            "left": "saved",
            "right": "saved",
            "left_transform": ["explicit_empty_relations"] if wide else [],
            "right_transform": ["reorder_edges", "drop_empty_relations"] if wide else ["reorder_edges"],
        },
        {
            "type": "panel",
            "label": "panel-prop-unchanged",
            "scope": "entity",
            "prop": "crate-a",
            "left": "saved",
            "right": "saved",
            "left_transform": ["explicit_empty_relations"] if wide else [],
            "right_transform": ["reorder_edges", "drop_empty_relations"] if wide else ["reorder_edges"],
        },
        {"type": "set_trait", "label": "repaint-crate-a", "prop": "crate-a", "key": "Tint", "value": _tint(210, 20, 20)},
        {"type": "set_trait", "label": "freeze-crate-a", "prop": "crate-a", "key": PAINT_TAG, "value": True},
        {"type": "remove_trait", "label": "clear-pallet-name", "prop": "pallet", "key": "Label"},
        {"type": "unlink", "label": "unparent-crate-a", "prop": "crate-a", "key": "ChildOf", "target": "stage"},
        {"type": "record_reference", "label": "file-now", "name": "now"},
        {
            "type": "panel",
            "label": "panel-changed",
            "scope": "scene",
            "left": "saved",
            "right": "now",
            "left_transform": [],
            "right_transform": ["reorder_edges"],
        },
        {
            "type": "panel",
            "label": "panel-prop-changed",
            "scope": "entity",
            "prop": "crate-a",
            "left": "saved",
            "right": "now",
            "left_transform": [],
            "right_transform": ["reorder_edges"],
        },
        {"type": "inspect", "label": "panel-final"},
    ]


PHASE_BUILDERS = {
    "paint": _paint,
    "slots": _slots,
    "drift": _drift,
    "refusal": _refusal,
    "handover": _handover,
    "panel": _panel,
}

REVIEW_PHASES: tuple[str, ...] = (
    "paint", "slots", "drift", "refusal", "handover", "panel",
)


def build_program(profile: str, variant: int) -> list[dict[str, Any]]:
    'The event list for one profile: a single phase, or the whole review.'
    if profile == "review":
        program: list[dict[str, Any]] = []
        for phase in REVIEW_PHASES:
            for event in PHASE_BUILDERS[phase](variant):
                program.append({**event, "phase": phase})
        return program
    builder = PHASE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown editor session profile: {profile}")
    return [{**event, "phase": profile} for event in builder(variant)]


def registry_entries() -> list[dict[str, Any]]:
    return [dict(entry) for entry in REGISTRY_ENTRIES]


def phase_of(program: Sequence[Mapping[str, Any]], index: int) -> str:
    if 0 <= int(index) < len(program):
        return str(program[int(index)].get("phase", ""))
    return ""
