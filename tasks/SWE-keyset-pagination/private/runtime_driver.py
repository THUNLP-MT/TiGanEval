'Sandboxed runner for the catalogue listing service.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _item(protocol: Any, row: Mapping[str, Any]) -> Any:
    values = dict(row)
    return protocol.Item(item_id=str(values.pop("item_id")), values=values)


def _poison_first_number(value: Any) -> bool:
    'Replace one numeric payload leaf without assuming a cursor schema.'

    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            if isinstance(child, (int, float)) and not isinstance(child, bool):
                value[key] = {}
                return True
            if isinstance(child, (dict, list)) and _poison_first_number(child):
                return True
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (int, float)) and not isinstance(child, bool):
                value[index] = {}
                return True
            if isinstance(child, (dict, list)) and _poison_first_number(child):
                return True
    return False


def _token(protocol: Any, op: Mapping[str, Any], minted: Mapping[str, str]) -> dict[str, Any]:
    'The token this request carries, in the shape the client holds it.'

    text = op.get("cursor_text")
    if text is None and op.get("cursor_from") is not None:
        text = minted.get(str(op["cursor_from"]))
        if text is None:
            return {"skip": "no token to send"}
    if text is None:
        return {"token": None}
    edit = str(op.get("edit") or "")
    if not edit:
        return {"token": str(text)}
    if edit == "truncate":
        return {"token": str(text)[:-6]}
    if edit == "empty":
        return {"token": protocol.encode_cursor({}), "fields_left": 0}
    try:
        payload = protocol.decode_cursor(str(text))
    except Exception as exc:
        return {"skip": f"the token cannot be edited: {_describe(exc)}"}
    if edit == "poison:first-number":
        if not _poison_first_number(payload):
            return {"skip": "the token has no numeric boundary value to change"}
        return {"token": protocol.encode_cursor(payload), "fields_left": len(payload)}
    keys = sorted(payload)
    index = int(edit.split(":", 1)[1])
    if index >= len(keys):
        return {"skip": "the token has no such field"}
    payload.pop(keys[index])
    return {"token": protocol.encode_cursor(payload), "fields_left": len(payload)}


def _read(protocol: Any, result: Any) -> dict[str, Any]:
    "What one listing result served, read through the release's own accessors."

    if protocol.is_refusal(result):
        return {"refused": True, "reason": str(result.get("reason", "")),
                "item_ids": [], "served": 0, "next_cursor": None}
    items = protocol.items_of(result)
    cursor = protocol.cursor_of(result)
    return {"refused": False, "reason": "", "item_ids": [str(item.item_id) for item in items],
            "served": len(items), "next_cursor": None if cursor is None else str(cursor)}


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from listing import protocol

    config = protocol.load_config()
    module = importlib.import_module("listing.pages")
    catalogues = {str(name): [_item(protocol, row) for row in rows]
                  for name, rows in dict(payload.get("catalogues", {})).items()}
    stores: dict[str, Any] = {}
    services: dict[str, Any] = {}
    minted: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            kind = str(op.get("op", ""))
            record: dict[str, Any] = {"index": index, "op": kind,
                                      "label": str(op.get("label", f"{kind}-{index}")),
                                      "phase": str(op.get("phase", ""))}
            try:
                if kind == "store":
                    store = protocol.Store(catalogues[str(op["catalogue"])])
                    stores[str(op["name"])] = store
                    record["ok"], record["rows"] = True, len(store)
                elif kind == "service":
                    if op.get("restart"):
                        module = importlib.reload(module)
                    services[str(op["name"])] = module.Catalogue(stores[str(op["store"])], config)
                    record["ok"] = True
                elif kind == "add":
                    stores[str(op["store"])].add(_item(protocol, op["row"]))
                    record["ok"], record["item_id"] = True, str(op["row"]["item_id"])
                elif kind == "remove":
                    stores[str(op["store"])].remove(str(op["item_id"]))
                    record["ok"], record["item_id"] = True, str(op["item_id"])
                elif kind == "reprice":
                    stores[str(op["store"])].reprice(str(op["item_id"]), **dict(op["values"]))
                    record["ok"], record["item_id"] = True, str(op["item_id"])
                elif kind == "find":
                    carried = _token(protocol, op, minted)
                    token = carried.get("token")
                    if "fields_left" in carried:
                        record["fields_left"] = int(carried["fields_left"])
                    if carried.get("skip"):
                        record["ok"] = True
                        record["skipped"] = True
                        record["note"] = str(carried["skip"])
                    else:
                        arguments: dict[str, Any] = {}
                        for name in ("order_by", "limit", "offset"):
                            if op.get(name) is not None:
                                arguments[name] = op[name]
                        if token is not None:
                            arguments["cursor"] = token
                        record["asked_for"] = int(arguments.get("limit", config.default_limit))
                        record["sent_cursor"] = token is not None
                        record.update(_read(protocol,
                                            services[str(op["service"])].find(**arguments)))
                        record["ok"] = True
                        if record.get("next_cursor"):
                            minted[record["label"]] = str(record["next_cursor"])
                else:
                    record["ok"], record["error"] = False, f"unknown operation: {kind}"
            except BaseException as exc:
                record["ok"], record["error"] = False, _describe(exc)
            records.append(record)

    return {"ok": True, "operations": records, "minted": minted,
            "stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
