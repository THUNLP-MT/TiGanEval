"""Checkpoint and revert for the level editor.

The prototype behind the editor's "Checkpoint" and "Revert to checkpoint"
buttons and the change panel beside them. Capture writes down what each prop is
carrying; revert writes it back.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import Registry, World


def capture_entity(world: World, entity: int, registry: Registry) -> dict[str, Any]:
    """What one prop is carrying right now."""

    return {
        "id": int(entity),
        "traits": {key: world.trait(entity, key) for key in world.trait_keys(entity)},
    }


def capture_scene(world: World, registry: Registry) -> dict[str, Any]:
    """A checkpoint of the whole level."""

    session = world.session_entity()
    return {
        "entities": [
            capture_entity(world, entity, registry)
            for entity in world.entities()
            if entity != session
        ]
    }


def restore_entity(
    world: World, entity: int, registry: Registry, snapshot: Mapping[str, Any]
) -> None:
    """Put one prop back the way the checkpoint has it."""

    for key, value in dict(snapshot.get("traits") or {}).items():
        world.set_trait(entity, key, value)


def restore_scene(
    world: World, registry: Registry, checkpoint: Mapping[str, Any]
) -> None:
    """Put the level back the way the checkpoint has it."""

    for snapshot in checkpoint.get("entities") or ():
        entity = int(snapshot["id"])
        if world.alive(entity):
            restore_entity(world, entity, registry, snapshot)


def compare_entities(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[str]]:
    """What the change panel shows for one prop."""

    return {"added": [], "removed": [], "changed": [] if before == after else ["*"]}


def compare_scenes(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[int]]:
    """What the change panel shows for the whole level."""

    later = {int(item["id"]): item for item in (after.get("entities") or ())}
    changed = [
        int(item["id"])
        for item in (before.get("entities") or ())
        if later.get(int(item["id"])) != item
    ]
    return {"added": [], "removed": [], "changed": changed}
