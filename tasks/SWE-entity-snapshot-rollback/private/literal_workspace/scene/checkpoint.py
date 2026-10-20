"""Checkpoint and revert for the level editor.

The checkpoint holds each prop's traits and links; reverting writes them back
onto the props that are still there, and the panel lists what differs.
"""

from __future__ import annotations

from typing import Any, Mapping

from .protocol import Registry, World


def capture_entity(world: World, entity: int, registry: Registry) -> dict[str, Any]:
    """What one prop is carrying right now."""

    traits: dict[str, Any] = {}
    for key in world.trait_keys(entity):
        value = world.trait(entity, key)
        traits[key] = True if value is True else dict(value)
    relations: dict[str, list[dict[str, Any]]] = {}
    for key in world.relation_keys(entity):
        relations[key] = [dict(edge) for edge in world.edges(entity, key)]
    snapshot: dict[str, Any] = {"id": int(entity), "traits": traits}
    if relations:
        snapshot["relations"] = relations
    return snapshot


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
    """Write the recorded traits and links back onto the prop."""

    for key, value in dict(snapshot.get("traits") or {}).items():
        world.set_trait(entity, key, value)
    for key, edges in dict(snapshot.get("relations") or {}).items():
        present = {int(edge["target"]) for edge in world.edges(entity, key)}
        for edge in edges:
            target = int(edge["target"])
            if target in present or not world.alive(target):
                continue
            world.add_edge(entity, key, target, edge.get("data"))


def restore_scene(
    world: World, registry: Registry, checkpoint: Mapping[str, Any]
) -> None:
    """Write the checkpoint back over the level, prop by prop."""

    for snapshot in checkpoint.get("entities") or ():
        entity = int(snapshot["id"])
        if world.alive(entity):
            restore_entity(world, entity, registry, snapshot)


def _keyed(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keyed = dict(snapshot.get("traits") or {})
    keyed.update(dict(snapshot.get("relations") or {}))
    return keyed


def compare_entities(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[str]]:
    """What the change panel shows for one prop."""

    left, right = _keyed(before), _keyed(after)
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(
            key for key in set(left) & set(right) if left[key] != right[key]
        ),
    }


def compare_scenes(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[int]]:
    """What the change panel shows for the whole level."""

    left = {int(item["id"]): item for item in (before.get("entities") or ())}
    right = {int(item["id"]): item for item in (after.get("entities") or ())}
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(
            entity for entity in set(left) & set(right) if left[entity] != right[entity]
        ),
    }
