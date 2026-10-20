"""Runtime contract for the level editor's scene graph.

Entity identity, the trait and relation registry, the comparison rule and the
two digests below are the fixed part of the editor: the viewport, the outliner,
the change panel and the level file loader are all built against them.
Everything here is deterministic and every payload is JSON-shaped, so two runs
over the same level produce the same ids and the same digests.

A *checkpoint* is a plain mapping the editor can write to disk::

    {"entities": [
        {"id": <entity id>,
         "traits": {<key>: True | {<payload>}},
         "relations": {<key>: [{"target": <entity id>, "data": {...} | None}]}},
        ...
    ]}

``relations`` may be left out entirely when a prop has no links, and an empty
``relations`` map means the same thing as no ``relations`` key at all. Tag
traits are written as ``True``; data traits carry their payload.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


#: An entity id packs a slot number and the generation of that slot.
INDEX_BITS = 16
INDEX_MASK = (1 << INDEX_BITS) - 1

#: Slot 0 belongs to the editor itself. It is not part of the level and never
#: appears in a checkpoint; the editor keeps the designer's own state on it.
SESSION_INDEX = 0

TRAIT_KINDS: tuple[str, ...] = ("tag", "data")

#: The three lists the change panel renders, in the order it renders them.
CHANGE_FIELDS: tuple[str, ...] = ("added", "removed", "changed")


class SceneError(RuntimeError):
    """Anything the scene graph refuses to do."""


class UnknownEntity(SceneError):
    """A prop that is not in the level, or was destroyed."""


class UnknownKey(SceneError):
    """A trait or relation key the prop is not carrying."""


class CheckpointError(SceneError):
    """A checkpoint the level cannot be put back to.

    The editor wraps every revert in ``except CheckpointError``, tells the
    designer that nothing happened and leaves her where she was, so raising
    this is how a revert refuses.
    """


def encode_entity(index: int, generation: int) -> int:
    """The entity id for one slot at one generation."""
    slot, age = int(index), int(generation)
    if slot < 0 or slot > INDEX_MASK or age < 0:
        raise SceneError(f"slot or generation out of range: {slot}, {age}")
    return (age << INDEX_BITS) | slot


def decode_entity(entity: int) -> tuple[int, int]:
    """The slot and the generation packed into one entity id."""
    value = int(entity)
    return value & INDEX_MASK, value >> INDEX_BITS


@dataclass(frozen=True, slots=True)
class TraitSpec:
    """``kind`` is ``"tag"`` when the prop only either carries it or does not."""

    key: str
    kind: str = "data"


@dataclass(frozen=True, slots=True)
class RelationSpec:
    """``carries_data`` is True when each link of this kind has its own store."""

    key: str
    carries_data: bool = False


class Registry:
    """The trait and relation keys this project declares."""

    def __init__(self, traits: Sequence[TraitSpec], relations: Sequence[RelationSpec]):
        self.traits: dict[str, TraitSpec] = {spec.key: spec for spec in traits}
        self.relations: dict[str, RelationSpec] = {spec.key: spec for spec in relations}
        clash = sorted(set(self.traits) & set(self.relations))
        if clash:
            raise SceneError(f"key declared twice: {clash[0]}")

    @classmethod
    def build(cls, entries: Sequence[Mapping[str, Any]]) -> "Registry":
        """Build a registry from ``{"key": ..., "kind": "tag"|"data"|"relation"}``."""
        traits: list[TraitSpec] = []
        relations: list[RelationSpec] = []
        declared: set[str] = set()
        for entry in entries:
            key, kind = str(entry["key"]), str(entry.get("kind", "data"))
            if key in declared:
                raise SceneError(f"key declared twice: {key}")
            declared.add(key)
            if kind == "relation":
                carries = bool(entry.get("carries_data", False))
                relations.append(RelationSpec(key=key, carries_data=carries))
            elif kind in TRAIT_KINDS:
                traits.append(TraitSpec(key=key, kind=kind))
            else:
                raise SceneError(f"unknown kind for {key}: {kind}")
        return cls(traits, relations)

    def knows(self, key: str) -> bool:
        return str(key) in self.traits or str(key) in self.relations

    def is_trait(self, key: str) -> bool:
        return str(key) in self.traits

    def is_relation(self, key: str) -> bool:
        return str(key) in self.relations

    def is_tag(self, key: str) -> bool:
        spec = self.traits.get(str(key))
        return spec is not None and spec.kind == "tag"

    def carries_data(self, key: str) -> bool:
        spec = self.relations.get(str(key))
        return spec is not None and spec.carries_data

    def keys(self) -> list[str]:
        return sorted(set(self.traits) | set(self.relations))


class World:
    """The live level.

    Ids are slots. Destroying a prop frees its slot and raises that slot's
    generation, so the next prop ``create`` hands out may sit in the same slot
    under a different id, and an id that has been destroyed can never come back
    out of ``create``.

    The values this class hands back are the live stores the editor's tools
    write into, not copies of them.
    """

    def __init__(self) -> None:
        self._generation: dict[int, int] = {}
        self._live: dict[int, int] = {}
        self._free: list[int] = []
        self._next_index = 0
        self._traits: dict[int, dict[str, Any]] = {}
        self._relations: dict[int, dict[str, list[dict[str, Any]]]] = {}
        self._session = self.create()

    # -- identity -----------------------------------------------------
    def _allocate(self, index: int | None = None, generation: int | None = None) -> int:
        if index is None:
            if self._free:
                slot = self._free.pop()
            else:
                slot, self._next_index = self._next_index, self._next_index + 1
            age = self._generation.get(slot, 0)
        else:
            slot = int(index)
            if slot in self._live:
                raise SceneError(f"slot {slot} is taken")
            if slot in self._free:
                self._free.remove(slot)
            age = self._generation.get(slot, 0) if generation is None else int(generation)
            self._next_index = max(self._next_index, slot + 1)
        self._generation[slot] = self._live[slot] = int(age)
        entity = encode_entity(slot, age)
        self._traits[entity], self._relations[entity] = {}, {}
        return entity

    def create(self) -> int:
        """A new prop in the next free slot, at that slot's current generation."""
        return self._allocate()

    def reserve(self, index: int, generation: int) -> int:
        """Put a prop into one exact slot at one exact generation."""
        return self._allocate(index, generation)

    def destroy(self, entity: int) -> None:
        """Remove a prop, every link pointing at it, and free its slot."""
        target = self._require(entity)
        for keyed in self._relations.values():
            for key, edges in list(keyed.items()):
                kept = [edge for edge in edges if int(edge["target"]) != target]
                if kept:
                    keyed[key] = kept
                else:
                    keyed.pop(key, None)
        self._traits.pop(target, None)
        self._relations.pop(target, None)
        slot, age = decode_entity(target)
        del self._live[slot]
        self._generation[slot] = age + 1
        self._free.append(slot)

    def alive(self, entity: int) -> bool:
        slot, age = decode_entity(entity)
        return self._live.get(slot) == age

    def entities(self) -> list[int]:
        """Every live id, the editor's own session entity included."""
        return sorted(encode_entity(slot, age) for slot, age in self._live.items())

    def session_entity(self) -> int:
        """The editor's own entity in slot 0. It is not part of the level."""
        return self._session

    def free_slots(self) -> tuple[int, ...]:
        """The freed slots, oldest first; ``create`` takes the last one."""
        return tuple(self._free)

    def generation_of(self, index: int) -> int:
        return int(self._generation.get(int(index), 0))

    def _require(self, entity: int) -> int:
        if not self.alive(entity):
            raise UnknownEntity(f"no prop with id {int(entity)} is in the level")
        return int(entity)

    # -- traits -------------------------------------------------------
    def trait_keys(self, entity: int) -> list[str]:
        return sorted(self._traits[self._require(entity)])

    def has_trait(self, entity: int, key: str) -> bool:
        return str(key) in self._traits[self._require(entity)]

    def trait(self, entity: int, key: str) -> Any:
        """``True`` for a tag, otherwise the live store the tools write into."""
        store = self._traits[self._require(entity)]
        if str(key) not in store:
            raise UnknownKey(f"prop {int(entity)} is not carrying {key}")
        return store[str(key)]

    def set_trait(self, entity: int, key: str, value: Any) -> None:
        """Put ``value`` on the prop. The object you pass in is the one stored."""
        self._traits[self._require(entity)][str(key)] = value

    def remove_trait(self, entity: int, key: str) -> None:
        store = self._traits[self._require(entity)]
        if str(key) not in store:
            raise UnknownKey(f"prop {int(entity)} is not carrying {key}")
        store.pop(str(key))

    # -- relations ----------------------------------------------------
    def relation_keys(self, entity: int) -> list[str]:
        return sorted(self._relations[self._require(entity)])

    def edges(self, entity: int, key: str) -> list[dict[str, Any]]:
        """The live links under ``key``, in the order they were added."""
        return self._relations[self._require(entity)].get(str(key), [])

    def add_edge(self, entity: int, key: str, target: int, data: Any = None) -> None:
        """Append one link. Nothing here removes an older link to the same prop."""
        self._require(entity)
        if not self.alive(target):
            raise UnknownEntity(f"link target {int(target)} is not in the level")
        keyed = self._relations[int(entity)].setdefault(str(key), [])
        keyed.append({"target": int(target), "data": data})

    def remove_edge(self, entity: int, key: str, target: int) -> None:
        """Drop the first link under ``key`` that points at ``target``."""
        keyed = self._relations[self._require(entity)]
        edges = keyed.get(str(key), [])
        for position, edge in enumerate(edges):
            if int(edge["target"]) == int(target):
                edges.pop(position)
                break
        else:
            raise UnknownKey(f"prop {int(entity)} has no {key} link to {int(target)}")
        if not edges:
            keyed.pop(str(key), None)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def values_equal(left: Any, right: Any) -> bool:
    """True when two recorded payloads mean the same thing."""
    return _json(left) == _json(right)


def canonical_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """One prop's recorded state in its comparable form.

    ``relations`` is always present, a link list is sorted by target and then
    by payload, an empty link list is dropped, and every link carries a
    ``data`` field. The payloads are the objects that were passed in:
    canonicalising reshapes, it does not copy.
    """

    if not isinstance(snapshot, Mapping) or "id" not in snapshot:
        raise CheckpointError("a recorded prop needs an id")
    raw_traits, raw_relations = snapshot.get("traits"), snapshot.get("relations")
    if raw_traits is not None and not isinstance(raw_traits, Mapping):
        raise CheckpointError("a recorded prop's traits must be a mapping")
    if raw_relations is not None and not isinstance(raw_relations, Mapping):
        raise CheckpointError("a recorded prop's relations must be a mapping")
    relations: dict[str, list[dict[str, Any]]] = {}
    for key, raw_edges in dict(raw_relations or {}).items():
        if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, (str, bytes)):
            raise CheckpointError(f"the links under {key} must be a list")
        rows = []
        for edge in raw_edges:
            if not isinstance(edge, Mapping) or "target" not in edge:
                raise CheckpointError(f"a link under {key} names no target")
            rows.append({"target": int(edge["target"]), "data": edge.get("data")})
        rows.sort(key=lambda row: (row["target"], _json(row["data"])))
        if rows:
            relations[str(key)] = rows
    traits = {str(key): value for key, value in dict(raw_traits or {}).items()}
    return {"id": int(snapshot["id"]), "traits": traits, "relations": relations}


def canonical_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    """A whole checkpoint in its comparable form, props sorted by id."""
    if not isinstance(checkpoint, Mapping):
        raise CheckpointError("a checkpoint must be a mapping")
    raw = checkpoint.get("entities")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise CheckpointError("a checkpoint needs a list of entities")
    entities = sorted(
        (canonical_snapshot(item) for item in raw), key=lambda item: item["id"]
    )
    return {"entities": entities}


def _entity_text(entity: Mapping[str, Any]) -> str:
    parts = [f"E {int(entity['id'])}"]
    traits = dict(entity["traits"])
    parts.extend(f"T {key} {_json(traits[key])}" for key in sorted(traits))
    relations = dict(entity["relations"])
    for key in sorted(relations):
        rows = [[int(edge["target"]), edge["data"]] for edge in relations[key]]
        parts.append(f"R {key} {_json(rows)}")
    return "\n".join(parts)


def _digest(entities: Sequence[Mapping[str, Any]]) -> str:
    text = "\n".join(_entity_text(entity) for entity in entities)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _live_view(world: World, entity: int) -> dict[str, Any]:
    return {
        "id": int(entity),
        "traits": {key: world.trait(entity, key) for key in world.trait_keys(entity)},
        "relations": {
            key: [dict(edge) for edge in world.edges(entity, key)]
            for key in world.relation_keys(entity)
        },
    }


def world_digest(world: World) -> str:
    """A short string standing for the level as it is now.

    The editor prints it in the status bar. The session entity is not part of
    the level, so it is left out; everything else in the world goes in.
    """

    session = world.session_entity()
    entities = sorted(
        (
            canonical_snapshot(_live_view(world, entity))
            for entity in world.entities()
            if entity != session
        ),
        key=lambda item: item["id"],
    )
    return _digest(entities)


def digest_of_checkpoint(checkpoint: Mapping[str, Any]) -> str:
    """The same string ``world_digest`` gives for a level matching this file."""
    return _digest(canonical_checkpoint(checkpoint)["entities"])


def validate_checkpoint(checkpoint: Mapping[str, Any], registry: Registry) -> None:
    """Raise ``CheckpointError`` when this file cannot be put back on a level.

    It refuses a file that is not shaped like a checkpoint, one that names a
    trait or relation key the project does not declare, a tag carrying a
    payload or a data trait carrying none, a link on a relation that has no
    store, the same prop listed twice, two props in one slot, the editor's
    session entity, and a link naming a prop the file itself does not contain.
    """

    canon = canonical_checkpoint(checkpoint)
    ids = [entity["id"] for entity in canon["entities"]]
    slots = [decode_entity(entity)[0] for entity in ids]
    if len(set(ids)) != len(ids):
        raise CheckpointError("the file lists one prop twice")
    if len(set(slots)) != len(slots):
        raise CheckpointError("the file puts two props in one slot")
    listed = set(ids)
    for entity in canon["entities"]:
        if decode_entity(entity["id"])[0] == SESSION_INDEX:
            raise CheckpointError("the file contains the editor's own session entity")
        for key, value in entity["traits"].items():
            if not registry.is_trait(key):
                raise CheckpointError(f"the file names an undeclared trait: {key}")
            if registry.is_tag(key) and value is not True:
                raise CheckpointError(f"the tag {key} is carrying a payload")
            if not registry.is_tag(key) and not isinstance(value, Mapping):
                raise CheckpointError(f"the trait {key} is carrying no payload")
        for key, edges in entity["relations"].items():
            if not registry.is_relation(key):
                raise CheckpointError(f"the file names an undeclared relation: {key}")
            for edge in edges:
                if edge["target"] not in listed:
                    raise CheckpointError(f"a {key} link names a prop the file does not contain")
                if edge["data"] is not None and not registry.carries_data(key):
                    raise CheckpointError(f"the relation {key} has no store to fill")
