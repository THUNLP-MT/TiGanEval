"""Checkpoint and revert for the level editor.

A checkpoint is a value: nothing the designer does to the level afterwards
reaches into it, and nothing it holds ends up inside the level. A revert puts
the level back to exactly what the checkpoint holds — props, slots, traits and
links — or it refuses and leaves the level alone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .protocol import (
    CheckpointError,
    Registry,
    World,
    canonical_checkpoint,
    canonical_snapshot,
    decode_entity,
    validate_checkpoint,
    values_equal,
)


def _check_keys(snapshot: Mapping[str, Any], registry: Registry) -> None:
    for key, value in dict(snapshot["traits"]).items():
        if not registry.is_trait(key):
            raise CheckpointError(f"the file names a trait this project has not declared: {key}")
        if registry.is_tag(key):
            if value is not True:
                raise CheckpointError(f"the tag {key} is carrying a payload")
        elif not isinstance(value, Mapping):
            raise CheckpointError(f"the trait {key} is carrying no payload")
    for key, edges in dict(snapshot["relations"]).items():
        if not registry.is_relation(key):
            raise CheckpointError(f"the file names a relation this project has not declared: {key}")
        for edge in edges:
            if edge["data"] is not None and not registry.carries_data(key):
                raise CheckpointError(f"the relation {key} has no store to fill")


def capture_entity(world: World, entity: int, registry: Registry) -> dict[str, Any]:
    """What one prop is carrying right now, as a value of its own."""
    if not world.alive(entity):
        raise CheckpointError(f"prop {int(entity)} is not in the level")
    traits: dict[str, Any] = {}
    for key in world.trait_keys(entity):
        if not registry.is_trait(key):
            raise CheckpointError(f"prop {int(entity)} carries an undeclared trait: {key}")
        traits[key] = True if registry.is_tag(key) else deepcopy(world.trait(entity, key))
    relations: dict[str, list[dict[str, Any]]] = {}
    for key in world.relation_keys(entity):
        if not registry.is_relation(key):
            raise CheckpointError(f"prop {int(entity)} carries an undeclared relation: {key}")
        edges = [
            {"target": int(edge["target"]), "data": deepcopy(edge.get("data"))}
            for edge in world.edges(entity, key)
        ]
        if edges:
            relations[key] = edges
    snapshot: dict[str, Any] = {"id": int(entity), "traits": traits}
    if relations:
        snapshot["relations"] = relations
    return snapshot


def capture_scene(world: World, registry: Registry) -> dict[str, Any]:
    """A checkpoint of the whole level, without the editor's session entity."""
    session = world.session_entity()
    return {
        "entities": [
            capture_entity(world, entity, registry)
            for entity in world.entities()
            if entity != session
        ]
    }


def _put_traits(world: World, entity: int, snapshot: Mapping[str, Any], registry: Registry) -> None:
    wanted = dict(snapshot["traits"])
    for key in list(world.trait_keys(entity)):
        if key not in wanted:
            world.remove_trait(entity, key)
    for key, value in wanted.items():
        world.set_trait(entity, key, True if registry.is_tag(key) else deepcopy(value))


def _clear_links(world: World, entity: int) -> None:
    for key in list(world.relation_keys(entity)):
        while world.edges(entity, key):
            world.remove_edge(entity, key, world.edges(entity, key)[0]["target"])


def _put_links(world: World, entity: int, snapshot: Mapping[str, Any]) -> None:
    for key, edges in dict(snapshot["relations"]).items():
        for edge in edges:
            world.add_edge(entity, key, edge["target"], deepcopy(edge["data"]))


def restore_entity(
    world: World, entity: int, registry: Registry, snapshot: Mapping[str, Any]
) -> None:
    """Put one prop back to exactly what the checkpoint holds, or refuse."""
    canon = canonical_snapshot(snapshot)
    _check_keys(canon, registry)
    if not world.alive(entity):
        raise CheckpointError(f"prop {int(entity)} is not in the level")
    for edges in canon["relations"].values():
        for edge in edges:
            if not world.alive(edge["target"]):
                raise CheckpointError("a link names a prop that is not in the level")
    _put_traits(world, entity, canon, registry)
    _clear_links(world, entity)
    _put_links(world, entity, canon)


def restore_scene(
    world: World, registry: Registry, checkpoint: Mapping[str, Any]
) -> None:
    """Put the level back to exactly what the checkpoint holds, or refuse."""
    validate_checkpoint(checkpoint, registry)
    canon = canonical_checkpoint(checkpoint)
    wanted = {entity["id"]: entity for entity in canon["entities"]}
    session = world.session_entity()
    for entity in list(world.entities()):
        if entity != session and entity not in wanted:
            world.destroy(entity)
    for entity in sorted(wanted):
        if not world.alive(entity):
            slot, generation = decode_entity(entity)
            world.reserve(slot, generation)
    for entity in sorted(wanted):
        _put_traits(world, entity, wanted[entity], registry)
        _clear_links(world, entity)
    for entity in sorted(wanted):
        _put_links(world, entity, wanted[entity])


def _keyed(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keyed = dict(snapshot["traits"])
    keyed.update(snapshot["relations"])
    return keyed


def compare_entities(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[str]]:
    """What the change panel shows for one prop."""
    left = _keyed(canonical_snapshot(before))
    right = _keyed(canonical_snapshot(after))
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(
            key for key in set(left) & set(right) if not values_equal(left[key], right[key])
        ),
    }


def compare_scenes(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, list[int]]:
    """What the change panel shows for the whole level."""
    left = {entity["id"]: entity for entity in canonical_checkpoint(before)["entities"]}
    right = {entity["id"]: entity for entity in canonical_checkpoint(after)["entities"]}
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(
            entity for entity in set(left) & set(right)
            if not values_equal(left[entity], right[entity])
        ),
    }
