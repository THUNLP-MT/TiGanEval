'Sandboxed runner for the schedule engine: drives one program, reports raw output.'

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _reading(value: Any, zone: str, protocol: Any) -> dict[str, Any]:
    'One returned reading, with its wall-clock rendering where that works.'

    if not isinstance(value, datetime):
        return {"instant": None, "returned": repr(value)[:120]}
    row: dict[str, Any] = {"instant": value.isoformat()}
    try:
        row["local"] = protocol.from_utc(value, zone).isoformat()
        row["offset"] = protocol.offset_in_force(value, zone)
    except BaseException as exc:
        row["local_error"] = _describe(exc)
    return row


def _readings(values: Any, zone: str, protocol: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return [{"instant": None, "returned": repr(values)[:120]}]
    return [_reading(item, zone, protocol) for item in values]


def _rule_record(spec: Any) -> dict[str, Any]:
    'Snapshot a rule without calling a method candidate code can replace.'

    return {
        "summary": str(spec.summary),
        "zone": str(spec.zone),
        "wall_start": spec.wall_start.isoformat(),
        "period": str(spec.period),
        "interval": int(spec.interval),
        "count": None if spec.count is None else int(spec.count),
        "until": None if spec.until is None else spec.until.isoformat(),
    }


def _window_record(window: Any) -> dict[str, str]:
    'Snapshot a window before candidate imports can touch its class.'

    return {"start": window.start.isoformat(), "end": window.end.isoformat()}


def _callable(value: Any) -> Any:
    'The stable function behind a classmethod or an ordinary callable.'

    return getattr(value, "__func__", value)


def _protocol_surface(protocol: Any) -> tuple[Any, ...]:
    'The protected runtime surface candidate modules must leave alone.'

    zones = tuple(
        (
            str(name),
            str(zone.name),
            int(zone.base_offset),
            tuple(zone.periods),
        )
        for name, zone in sorted(protocol.ZONES.items())
    )
    return (
        protocol.RuleSpec,
        protocol.Window,
        protocol.Zone,
        _callable(protocol.RuleSpec.from_mapping),
        _callable(protocol.RuleSpec.as_dict),
        _callable(protocol.Window.from_mapping),
        _callable(protocol.Window.as_dict),
        _callable(protocol.Window.contains),
        _callable(protocol.Zone.offset_at),
        _callable(protocol.local_offsets),
        _callable(protocol.to_utc),
        _callable(protocol.from_utc),
        _callable(protocol.offset_in_force),
        _callable(protocol.zone_for),
        _callable(protocol.slice_window),
        _callable(protocol.parse_rule_text),
        _callable(protocol.format_stamp),
        protocol.TABLE_FROM,
        protocol.TABLE_UNTIL,
        tuple(sorted(protocol.PERIOD_STEP.items())),
        zones,
    )


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from recur import protocol


    prepared: list[dict[str, Any]] = []
    for raw in payload.get("operations", ()):
        operation = dict(raw)
        kind = str(operation.get("type", ""))
        item: dict[str, Any] = {"operation": operation, "kind": kind}
        if kind in ("expand", "paging", "export"):
            spec = protocol.RuleSpec.from_mapping(operation["rule"])
            item.update({"spec": spec, "rule": _rule_record(spec)})
        if kind in ("expand", "paging", "merge"):
            window = protocol.Window.from_mapping(operation["window"])
            item.update({"window_object": window, "window": _window_record(window)})
        if kind == "paging":
            pieces = protocol.slice_window(window, int(operation["slice_seconds"]))
            item["pieces"] = tuple(pieces)
            item["piece_windows"] = tuple(_window_record(piece) for piece in pieces)
        if kind == "merge":
            specs = tuple(protocol.RuleSpec.from_mapping(rule) for rule in operation["rules"])
            item["specs"] = specs
            item["rules"] = tuple(_rule_record(spec) for spec in specs)
        prepared.append(item)

    protected_surface = _protocol_surface(protocol)
    parse_rule_text = protocol.parse_rule_text
    module = importlib.import_module("recur.schedule")
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, item in enumerate(prepared):
            operation = dict(item["operation"])
            kind = str(item["kind"])
            record: dict[str, Any] = {
                "type": kind,
                "index": index,
                "label": str(operation.get("label", f"{kind}-{index}")),
                "check": str(operation.get("check", "")),
                "profile": operation.get("profile"),
            }
            for carried in ("wall_kind", "affected_wall", "slice_seconds",
                            "outlives_table", "stretch_at_table_edge"):
                if carried in operation:
                    record[carried] = operation[carried]
            try:
                if kind == "expand" or kind == "paging":
                    spec = item["spec"]
                    window = item["window_object"]
                    record["rule"] = dict(item["rule"])
                    record["window"] = dict(item["window"])
                    whole = module.expand(spec, window)
                    record["occurrences"] = _readings(whole, spec.zone, protocol)
                    if kind == "paging":
                        record["slices"] = [
                            {
                                "window": dict(piece_window),
                                "occurrences": _readings(
                                    module.expand(spec, piece), spec.zone, protocol
                                ),
                            }
                            for piece, piece_window in zip(
                                item["pieces"], item["piece_windows"]
                            )
                        ]
                elif kind == "export":
                    spec = item["spec"]
                    record["rule"] = dict(item["rule"])
                    text = module.serialize(spec)
                    record["text"] = text if isinstance(text, str) else repr(text)[:200]
                    try:
                        read_back = parse_rule_text(record["text"])
                        record["read_back"] = _rule_record(read_back)
                        again = module.serialize(read_back)
                        record["text_again"] = again if isinstance(again, str) else repr(again)[:200]
                    except BaseException as exc:
                        record["read_error"] = _describe(exc)
                elif kind == "merge":
                    specs = item["specs"]
                    window = item["window_object"]
                    record["rules"] = [dict(rule) for rule in item["rules"]]
                    record["window"] = dict(item["window"])
                    record["feeds"] = [
                        {
                            "zone": spec.zone,
                            "occurrences": _readings(module.expand(spec, window), spec.zone, protocol),
                        }
                        for spec in specs
                    ]
                    merged = module.merge_feeds(specs, window)
                    record["merged"] = _readings(merged, specs[0].zone if specs else "UTC", protocol)
                else:
                    record["ok"] = False
                    record["error"] = f"unknown operation: {kind}"
                    records.append(record)
                    continue
                record["ok"] = True
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            records.append(record)

    if _protocol_surface(protocol) != protected_surface:
        return {
            "ok": False,
            "error": "the schedule engine changed the shared recurrence protocol",
        }
    return {"ok": True, "records": records, "engine_stdout": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = run(payload)
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
