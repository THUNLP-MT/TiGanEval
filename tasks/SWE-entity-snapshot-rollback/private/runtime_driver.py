'Sandboxed candidate runner for the scene editor simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import builtins
import copy
import importlib
import io
import json
import sys
import _thread
import threading
from typing import Any, Mapping


_PROTOCOL_FUNCTIONS = (
    "_digest", "_entity_text", "_json", "encode_entity", "decode_entity",
    "values_equal", "canonical_snapshot", "canonical_checkpoint", "world_digest",
    "digest_of_checkpoint", "validate_checkpoint",
)
_REGISTRY_METHODS = (
    "__init__", "build", "knows", "is_trait", "is_tag", "is_relation",
    "carries_data", "keys",
)
_WORLD_METHODS = (
    "_allocate", "_require", "create", "reserve", "destroy", "alive", "entities", "session_entity",
    "free_slots", "generation_of", "trait_keys", "has_trait", "trait",
    "set_trait", "remove_trait", "relation_keys", "edges", "add_edge",
    "remove_edge",
)
_PROTOCOL_OBJECTS = (
    "CHANGE_FIELDS", "CheckpointError", "INDEX_BITS", "INDEX_MASK", "Registry",
    "RelationSpec", "SceneError", "SESSION_INDEX", "TRAIT_KINDS", "TraitSpec",
    "UnknownEntity", "UnknownKey", "World", "hashlib", "json",
)

_BLOCKED_AUDIT_EVENTS = {
    "ctypes.call_function", "ctypes.dlopen", "ctypes.dlsym", "ctypes.dlsym/handle",
    "gc.get_objects", "gc.get_referents", "gc.get_referrers",
    "sys._current_exceptions", "sys._current_frames", "sys._getframe",
    "sys._getframemodulename", "sys.setprofile", "sys.settrace",
}


class _CandidateRaised(Exception):
    'A safe description of an exception raised on the candidate thread.'

    def __init__(self, name: str, message: str, is_checkpoint: bool):
        super().__init__(f"{name}: {message}")
        self.name = str(name)
        self.message = str(message)
        self.is_checkpoint = bool(is_checkpoint)


def _call_isolated(
    function: Any,
    args: tuple[Any, ...],
    checkpoint_error: type[BaseException],
    ensure_integrity: Any,
    candidate_error: type[_CandidateRaised],
    worker_type: type[threading.Thread],
) -> Any:
    'Call candidate code on a stack that has no trusted driver frames.'
    outcome: list[tuple[Any, ...]] = []
    put = outcome.append
    exception_type = BaseException

    def invoke() -> None:
        try:
            put(("return", function(*args)))
        except exception_type as exc:
            try:
                name, message = type(exc).__name__, str(exc)[:200]
            except exception_type:
                name, message = "Exception", "the candidate raised an unreadable exception"
            put(("raise", str(name), str(message), isinstance(exc, checkpoint_error)))

    worker = worker_type(target=invoke, name="scene-candidate-call", daemon=True)
    start, join = worker.start, worker.join
    start()
    join()
    ensure_integrity()
    if len(outcome) != 1:
        raise RuntimeError("the candidate call did not return one result")
    if outcome[0][0] == "raise":
        raise candidate_error(outcome[0][1], outcome[0][2], outcome[0][3])
    return outcome[0][1]


def _object_mark(value: Any) -> tuple[Any, ...]:
    value = getattr(value, "__func__", value)
    code = getattr(value, "__code__", None)
    return (
        id(value), id(code), getattr(code, "co_code", None),
        repr(getattr(value, "__defaults__", None)),
    )


def _protocol_mark(protocol: Any) -> tuple[tuple[Any, ...], ...]:
    'Identity of the fixed editor contract used to measure candidate behavior.'
    marked = [
        ("protocol", name, *_object_mark(getattr(protocol, name)))
        for name in _PROTOCOL_FUNCTIONS
    ]
    marked.extend(
        ("Registry", name, *_object_mark(getattr(protocol.Registry, name)))
        for name in _REGISTRY_METHODS
    )
    marked.extend(
        ("World", name, *_object_mark(getattr(protocol.World, name)))
        for name in _WORLD_METHODS
    )
    return tuple(marked)


def _plain(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _scene(world: Any, protocol: Any) -> list[dict[str, Any]]:
    session = world.session_entity()
    rows = []
    for entity in world.entities():
        slot, generation = protocol.decode_entity(entity)
        traits = {}
        for key in world.trait_keys(entity):
            value = world.trait(entity, key)
            traits[key] = True if value is True else _plain(value)
        rows.append({
            "id": int(entity), "slot": int(slot), "generation": int(generation),
            "session": entity == session, "traits": traits,
            "relations": {
                key: [{"target": int(e["target"]), "data": _plain(e.get("data"))}
                      for e in world.edges(entity, key)]
                for key in world.relation_keys(entity)
            },
        })
    return rows


def _reference(world: Any, protocol: Any) -> dict[str, Any]:
    'A checkpoint of the live level, written by the operator rather than the editor.'
    entities = []
    for row in _scene(world, protocol):
        if row["session"]:
            continue
        snapshot: dict[str, Any] = {"id": row["id"], "traits": row["traits"]}
        if row["relations"]:
            snapshot["relations"] = row["relations"]
        entities.append(snapshot)
    return {"entities": entities}


def _reshape(checkpoint: Mapping[str, Any], names: Any) -> dict[str, Any]:
    'Write the same checkpoint down a different way.'
    result = copy.deepcopy(dict(checkpoint))
    for entity in result["entities"]:
        for name in names:
            if name == "reorder_edges":
                for key, edges in dict(entity.get("relations") or {}).items():
                    entity["relations"][key] = list(reversed(edges))
            elif name == "explicit_empty_relations":
                entity.setdefault("relations", {})
            elif name == "drop_empty_relations" and not entity.get("relations"):
                entity.pop("relations", None)
    return result


def _damage(checkpoint: Mapping[str, Any], fault: str) -> tuple[dict[str, Any], str]:
    'A checkpoint the level cannot be put back to, and how to say why.'
    result = copy.deepcopy(dict(checkpoint))
    if fault == "dropped_target":
        targets = {int(edge["target"]) for entity in result["entities"]
                   for edges in dict(entity.get("relations") or {}).values() for edge in edges}
        for position, entity in enumerate(result["entities"]):
            if int(entity["id"]) in targets:
                result["entities"].pop(position)
                return result, "it has a link to a prop the file does not contain"
    if fault == "unknown_key":
        result["entities"][0].setdefault("traits", {})["Ghost"] = {"value": 1}
        return result, "it names a key this project has never declared"
    raise ValueError(f"unknown fault: {fault}")


def _damage_entity(snapshot: Mapping[str, Any], fault: str) -> tuple[dict[str, Any], str]:
    "One prop's recorded state that this level cannot be put back to."

    if fault == "stale_link":
        return copy.deepcopy(dict(snapshot)), "it puts a link back onto a prop that is no longer in the level"
    if fault == "tag_payload":
        result = copy.deepcopy(dict(snapshot))
        result.setdefault("traits", {})["Frozen"] = {"value": True}
        return result, "a tag in the file is carrying a payload"
    if fault == "missing_subject":
        return copy.deepcopy(dict(snapshot)), "the prop named by the file is no longer in the level"
    wrapped, why = _damage({"entities": [copy.deepcopy(dict(snapshot))]}, fault)
    return wrapped["entities"][0], why


def _checkpoint_digest(protocol: Any, checkpoint: Any) -> str:
    'The digest of a saved file, whether it holds the level or one prop.'
    try:
        if isinstance(checkpoint, Mapping) and "entities" not in checkpoint:
            return str(protocol.digest_of_checkpoint({"entities": [checkpoint]}))
        return str(protocol.digest_of_checkpoint(checkpoint))
    except BaseException:
        return "unreadable"


def _step(
    event: Mapping[str, Any],
    record: dict[str, Any],
    state: dict[str, Any],
    protocol: Any,
    module: Any,
    call_candidate: Any,
) -> None:
    kind, world, props, saved = str(event["type"]), state["world"], state["props"], state["saved"]
    name = str(event.get("name", ""))
    if kind == "define":
        state["registry"] = protocol.Registry.build(state["entries"])
        state["world"], state["props"], state["saved"] = protocol.World(), {}, {}
    elif kind == "create":
        props[str(event["prop"])] = world.create()
    elif kind == "set_trait":
        world.set_trait(props[str(event["prop"])], str(event["key"]), copy.deepcopy(event.get("value")))
    elif kind == "remove_trait":
        world.remove_trait(props[str(event["prop"])], str(event["key"]))
    elif kind == "select":
        world.set_trait(world.session_entity(), "Selection", {"prop": str(event["prop"])})
    elif kind == "link":
        world.add_edge(props[str(event["prop"])], str(event["key"]),
                       props[str(event["target"])], copy.deepcopy(event.get("data")))
    elif kind == "unlink":
        world.remove_edge(props[str(event["prop"])], str(event["key"]), props[str(event["target"])])
    elif kind == "destroy":
        world.destroy(props[str(event["prop"])])
    elif kind == "brush":
        record["prop"], record["key"] = str(event["prop"]), str(event["key"])
        node = world.trait(props[str(event["prop"])], str(event["key"]))
        path = list(event.get("path", ()))
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = copy.deepcopy(event.get("value"))
    elif kind == "brush_edge":
        record["prop"], record["key"] = str(event["prop"]), str(event["key"])
        record["target"] = str(event["target"])
        edge = next(
            item for item in world.edges(props[record["prop"]], record["key"])
            if int(item["target"]) == int(props[record["target"]])
        )
        node = edge["data"]
        path = list(event.get("path", ()))
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = copy.deepcopy(event.get("value"))
    elif kind == "capture":
        record["checkpoint"] = name
        if str(event.get("scope", "scene")) == "entity":
            record["prop"] = str(event["prop"])
            saved[name] = call_candidate(
                module.capture_entity, world, props[str(event["prop"])], state["registry"]
            )
        else:
            saved[name] = call_candidate(module.capture_scene, world, state["registry"])
    elif kind == "record_reference":
        record["checkpoint"] = name
        saved[name] = _reference(world, protocol)
    elif kind == "restore":
        record["checkpoint"] = name
        call_candidate(module.restore_scene, world, state["registry"], saved[name])
    elif kind == "restore_entity":
        record["checkpoint"], record["prop"] = name, str(event["prop"])
        call_candidate(
            module.restore_entity, world, props[str(event["prop"])],
            state["registry"], saved[name]
        )
    elif kind in ("restore_broken", "offer_entity"):
        if kind == "restore_broken":
            broken, fault = _damage(saved[name], str(event["fault"]))
        else:
            broken, fault = _damage_entity(saved[name], str(event["fault"]))
            record["prop"] = str(event["prop"])
        record["checkpoint"], record["fault"], record["raised"] = name, fault, None
        try:
            if kind == "restore_broken":
                call_candidate(module.restore_scene, world, state["registry"], broken)
            else:
                call_candidate(
                    module.restore_entity, world, props[str(event["prop"])],
                    state["registry"], broken
                )
        except BaseException as exc:
            if isinstance(exc, _CandidateRaised):
                kind_name = "CheckpointError" if exc.is_checkpoint else exc.name
                message = exc.message
            else:
                kind_name = "CheckpointError" if isinstance(exc, protocol.CheckpointError) else type(exc).__name__
                message = str(exc)[:200]
            record["raised"], record["raised_text"] = kind_name, message
    elif kind == "panel":
        left = _reshape(saved[str(event["left"])], event.get("left_transform", ()))
        right = _reshape(saved[str(event["right"])], event.get("right_transform", ()))
        record["scope"] = str(event.get("scope", "scene"))
        if record["scope"] == "entity":
            wanted = props[str(event["prop"])]
            record["prop"] = str(event["prop"])
            left = next(item for item in left["entities"] if int(item["id"]) == wanted)
            right = next(item for item in right["entities"] if int(item["id"]) == wanted)
            record["left_canonical"] = _plain(protocol.canonical_snapshot(left))
            record["right_canonical"] = _plain(protocol.canonical_snapshot(right))
            record["reported"] = _plain(call_candidate(module.compare_entities, left, right))
        else:
            record["left_canonical"] = _plain(protocol.canonical_checkpoint(left))
            record["right_canonical"] = _plain(protocol.canonical_checkpoint(right))
            record["reported"] = _plain(call_candidate(module.compare_scenes, left, right))
    elif kind != "inspect":
        raise ValueError(f"unknown event: {kind}")


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from scene import protocol

    entries = list(payload.get("registry", ()))
    state: dict[str, Any] = {
        "entries": entries, "registry": protocol.Registry.build(entries),
        "world": protocol.World(), "props": {}, "saved": {},
    }
    records: list[dict[str, Any]] = []
    captured = io.StringIO()


    main_thread = _thread.get_ident()
    trusted_get_ident = _thread.get_ident

    def audit(event: str, _args: tuple[Any, ...]) -> None:
        if event in _BLOCKED_AUDIT_EVENTS:
            raise RuntimeError("editor extensions cannot inspect the session runner")
        if event == "_thread.start_new_thread" and trusted_get_ident() != main_thread:
            raise RuntimeError("editor extensions cannot start background threads")

    sys.addaudithook(audit)

    driver_globals = globals()
    guarded_globals = {
        name: driver_globals[name]
        for name in (
            "_CandidateRaised", "_call_isolated", "_checkpoint_digest", "_damage",
            "_damage_entity", "_plain", "_protocol_mark", "_reference", "_reshape",
            "_scene", "_step",
        )
    }
    guarded_dependencies = (
        (builtins, "any", builtins.any),
        (builtins, "getattr", builtins.getattr),
        (builtins, "id", builtins.id),
        (builtins, "isinstance", builtins.isinstance),
        (builtins, "len", builtins.len),
        (builtins, "repr", builtins.repr),
        (builtins, "set", builtins.set),
        (builtins, "str", builtins.str),
        (builtins, "type", builtins.type),
        (builtins, "vars", builtins.vars),
        (copy, "deepcopy", copy.deepcopy),
        (json, "dumps", json.dumps),
        (json, "loads", json.loads),
        (protocol.hashlib, "sha256", protocol.hashlib.sha256),
        (protocol.json, "dumps", protocol.json.dumps),
        (_thread, "get_ident", _thread.get_ident),
        (_thread, "start_new_thread", _thread.start_new_thread),
        (threading, "Thread", threading.Thread),
        (threading.Thread, "__init__", threading.Thread.__init__),
        (threading.Thread, "join", threading.Thread.join),
        (threading.Thread, "run", threading.Thread.run),
        (threading.Thread, "start", threading.Thread.start),
    )
    fixed_protocol_objects = {
        name: getattr(protocol, name) for name in _PROTOCOL_OBJECTS
    }
    trusted_any = any
    trusted_getattr = getattr
    trusted_id = id
    trusted_set = set
    trusted_type = type
    trusted_vars = vars
    fixed_protocol = _protocol_mark(protocol)
    world_fields = {
        "_generation", "_live", "_free", "_next_index", "_traits",
        "_relations", "_session",
    }

    def require_plain(value: Any, active: set[int] | None = None) -> None:
        active = trusted_set() if active is None else active
        value_type = trusted_type(value)
        if value is None or value_type in (bool, int, float, str):
            return
        if value_type not in (dict, list, tuple):
            raise TypeError("candidate values must use plain JSON-shaped containers")
        marker = trusted_id(value)
        if marker in active:
            raise TypeError("candidate values cannot contain a reference cycle")
        active.add(marker)
        if value_type is dict:
            for key, item in value.items():
                if trusted_type(key) not in (str, int):
                    raise TypeError("candidate mappings must use plain string or integer keys")
                require_plain(item, active)
        else:
            for item in value:
                require_plain(item, active)
        active.remove(marker)

    def ensure_integrity() -> None:
        if trusted_any(
            trusted_getattr(owner, name, None) is not value
            for owner, name, value in guarded_dependencies
        ):
            raise RuntimeError("a fixed runtime dependency changed while candidate code was running")
        if _protocol_mark(protocol) != fixed_protocol:
            raise RuntimeError("the fixed editor contract changed while the session was running")
        if trusted_any(
            trusted_getattr(protocol, name, None) is not value
            for name, value in fixed_protocol_objects.items()
        ):
            raise RuntimeError("a fixed editor contract object changed while candidate code was running")
        if trusted_any(
            driver_globals.get(name) is not value for name, value in guarded_globals.items()
        ):
            raise RuntimeError("the session runner changed while candidate code was running")
        world = state["world"]
        if trusted_type(world) is not protocol.World or trusted_set(trusted_vars(world)) != world_fields:
            raise RuntimeError("the candidate changed the shape of the live level")
        if trusted_any(name in trusted_vars(world) for name in _WORLD_METHODS):
            raise RuntimeError("the candidate replaced a live-level operation")
        require_plain({name: trusted_vars(world)[name] for name in world_fields})
        require_plain(state["props"])
        require_plain(state["saved"])
        if sys.modules.get("scene.protocol") is not protocol or sys.stdout is not captured:
            raise RuntimeError("the candidate replaced a fixed runtime object")

    trusted_call = _call_isolated
    candidate_error = _CandidateRaised
    worker_type = threading.Thread

    def call_candidate(function: Any, *args: Any, plain_result: bool = True) -> Any:
        result = trusted_call(
            function, tuple(args), protocol.CheckpointError, ensure_integrity,
            candidate_error, worker_type
        )
        if plain_result:
            require_plain(result)
        return result

    with redirect_stdout(captured):
        module = call_candidate(importlib.import_module, "scene.checkpoint", plain_result=False)
        ensure_integrity()
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            record: dict[str, Any] = {
                "type": kind, "index": index,
                "label": str(event.get("label", f"{kind}-{index}")),
            }
            try:
                _step(event, record, state, protocol, module, call_candidate)
                record["ok"] = True
            except BaseException as exc:
                record["ok"] = False
                if isinstance(exc, _CandidateRaised):
                    record["error"] = f"{exc.name}: {exc.message}"
                else:
                    record["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            ensure_integrity()
            try:
                record["props"] = dict(state["props"])
                record["scene"] = _scene(state["world"], protocol)
                record["digest"] = protocol.world_digest(state["world"])
                record["checkpoint_digests"] = {
                    name: _checkpoint_digest(protocol, value)
                    for name, value in state["saved"].items()
                }
            except BaseException as exc:
                record["state_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            records.append(record)

    return {"ok": True, "records": records, "candidate_stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
