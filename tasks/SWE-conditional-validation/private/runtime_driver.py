'Sandboxed runner for one order-platform replay program.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"

def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from orders import contract as contract_module
    from orders import policy as policy_module
    from orders import protocol
    from orders import retiring_guards

    def condition_of(spec: Any) -> Any:
        if not spec:
            return None
        return protocol.Equals(str(spec["path"]), spec.get("value"))

    def reviewed(schema: Any) -> dict[str, Any]:
        try:
            policy_module.check_schema(schema)
        except BaseException as exc:
            refused = isinstance(exc, protocol.SchemaError)
            return {"verdict": "refused" if refused else "error",
                    "error_kind": type(exc).__name__, "error": _describe(exc)}
        return {"verdict": "accepted"}

    def admitted(schema: Any, item: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return {"accepted": True, "item": policy_module.admit(schema, dict(item))}
        except protocol.ValidationError as exc:
            return {"accepted": False, "refusal": _describe(exc)}
        except BaseException as exc:
            return {"accepted": None, "error": _describe(exc)}

    def published(schema: Any, entries: Any) -> tuple[Any, list[dict[str, Any]]]:
        document = contract_module.to_contract(schema)
        def row(entry: Any) -> dict[str, Any]:
            item = protocol.apply_defaults(schema, dict(entry["payload"]))
            return {"payload": str(entry["label"]),
                    "complaints": list(protocol.validate_contract(document, item))}
        return document, [row(entry) for entry in entries]

    schemas: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            record: dict[str, Any] = {"type": kind, "index": index, "ok": True,
                                      "label": str(event.get("label", f"{kind}-{index}"))}
            try:
                schema = schemas.get(str(event.get("schema", "")))
                if kind in ("load", "review"):
                    document = event.get("document")
                    if document is None:
                        with open(str(event["document_path"]), encoding="utf-8") as handle:
                            document = json.load(handle)
                    built = protocol.load_schema(dict(document))
                    if kind == "load":
                        schemas[str(event["schema"])] = built
                    record["document"] = document
                    record.update(reviewed(built))
                elif kind == "admit":
                    record.update(admitted(schema, dict(event["payload"])))
                    guard = retiring_guards.GUARDS.get(str(event.get("schema", "")))
                    if guard is not None:
                        item = protocol.apply_defaults(schema, dict(event["payload"]))
                        record["hand_written_guard_says"] = list(guard(item))
                elif kind == "update":
                    key, stored = str(event["key"]), dict(event["stored"])
                    store = protocol.Store({key: stored})
                    caller = condition_of(event.get("condition"))
                    record["caller_condition"] = protocol.describe(caller)
                    try:
                        patch, condition = policy_module.build_update(
                            schema, dict(event["changes"]), caller)
                    except protocol.ValidationError as exc:
                        record.update(committed=False, refused_by="the write path",
                                      refusal=_describe(exc))
                    else:
                        record["patch"] = patch
                        record["condition_handed_to_the_store"] = protocol.describe(condition)
                        try:
                            store.update(key, patch, condition)
                            record["committed"] = True
                        except protocol.ConditionalCheckFailed as exc:
                            record.update(committed=False, refused_by="the store",
                                          refusal=_describe(exc))
                    record["item_afterwards"] = store.get(key)
                elif kind == "read":
                    key, projection = str(event["key"]), event.get("projection")
                    store = protocol.Store({key: dict(event["stored"])})
                    physical = list(protocol.stored_paths(schema, projection)) if projection else None
                    record.update(stored_item=store.get(key, physical), projection=projection)
                    try:
                        record["view"] = policy_module.read_view(
                            schema, record["stored_item"], projection)
                    except BaseException as exc:
                        record.update(view=None, error=_describe(exc))
                elif kind == "publish":
                    document, rows = published(schema, event["payloads"])
                    record.update(contract=document, contract_verdicts=rows)
                    record["write_path_verdicts"] = []
                    for entry in event["payloads"]:
                        outcome = admitted(schema, dict(entry["payload"]))
                        record["write_path_verdicts"].append(
                            {
                                "payload": str(entry["label"]),
                                **{
                                    name: outcome[name]
                                    for name in ("accepted", "refusal", "error")
                                    if name in outcome
                                },
                            }
                        )
                elif kind == "rebuild":
                    carried = contract_module.to_dto(schema)
                    rebuilt = contract_module.from_dto(carried)
                    record["carried_document"] = carried
                    _, here = published(schema, event["payloads"])
                    _, there = published(rebuilt, event["payloads"])
                    record["round_trip"] = [
                        {"payload": str(entry["label"]),
                         "here": admitted(schema, dict(entry["payload"]))["accepted"],
                         "after_rebuilding": admitted(rebuilt, dict(entry["payload"]))["accepted"],
                         "contract_here": here[position]["complaints"],
                         "contract_after_rebuilding": there[position]["complaints"]}
                        for position, entry in enumerate(event["payloads"])
                    ]
                else:
                    record.update(ok=False, error=f"unknown step in the program: {kind}")
            except BaseException as exc:
                record.update(ok=False, error=_describe(exc))
            records.append(record)

    return {"ok": True, "records": records, "console": captured.getvalue()[-2000:]}

def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
