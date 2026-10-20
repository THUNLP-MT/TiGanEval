'Sandboxed intake console: build one loader per partner and run the posts.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


_SETTINGS = (
    "rename", "name_style", "trim_trailing_underscore", "aliases", "alias_style",
    "extra_policy", "extra_in",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from intake import protocol

    module = importlib.reload(importlib.import_module("intake.mapper"))
    spec = dict(payload.get("shape", {}))
    shape = protocol.Shape(
        name=str(spec.get("name", "record")),
        fields=tuple(protocol.FieldSpec(**dict(field)) for field in spec.get("fields", ())),
    )
    layers = {
        str(name): [dict(layer) for layer in value]
        for name, value in dict(payload.get("configs", {})).items()
    }
    configs = {name: protocol.merge_configs(*value) for name, value in layers.items()}
    loaders: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    def loader(name: str) -> Any:
        if name not in loaders:
            loaders[name] = module.build_loader(shape, configs[name])
        return loaders[name]

    with redirect_stdout(captured):
        for index, raw in enumerate(payload.get("operations", ())):
            op = dict(raw)
            kind = str(op.get("op", ""))
            name = str(op.get("config", ""))
            record: dict[str, Any] = {
                "index": index, "op": kind, "config": name,
                "label": str(op.get("label", f"{kind}-{index}")),
                "ok": False, "error": None, "message": None, "trail": None,
                "result": None, "consumed": [],
            }
            protocol.reset_key_log()
            try:
                built = loader(name)
                if kind == "build":
                    record["result"] = None
                elif kind == "load":
                    record["result"] = _jsonable(built.load(dict(op.get("payload", {}))))
                elif kind == "dump":
                    record["result"] = _jsonable(built.dump(dict(op.get("record", {}))))
                elif kind == "schema":
                    record["result"] = _jsonable(built.input_schema())
                else:
                    raise ValueError(f"unknown operation: {kind}")
                record["ok"] = True
            except BaseException as exc:
                record["error"] = type(exc).__name__
                record["message"] = str(exc)[:300]
                trail = getattr(exc, "trail", None)
                if trail is not None:
                    record["trail"] = [str(item) for item in trail]
            record["consumed"] = [dict(entry) for entry in protocol.KEY_LOG]
            records.append(record)

    return {
        "ok": True,
        "operations": records,
        "configs": {
            name: {setting: _jsonable(getattr(config, setting)) for setting in _SETTINGS}
            for name, config in configs.items()
        },
        "stdout": captured.getvalue()[-2000:],
    }


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
