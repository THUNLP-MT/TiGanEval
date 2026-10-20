'Sandboxed exporter: runs one catalogue program against a delivered build.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _grid(value: Any, rows: int, columns: int) -> list[list[list[int]]]:
    'One flattened plate, checked into plain integers before it leaves here.'

    plate: list[list[list[int]]] = []
    for row in value:
        pixels: list[list[int]] = []
        for pixel in row:
            channels = [int(number) for number in pixel]
            if len(channels) != 3:
                raise ValueError(f"a published pixel holds three channels: {channels}")
            pixels.append(channels)
        if len(pixels) != columns:
            raise ValueError(
                f"a published plate row holds {columns} pixels, not {len(pixels)}"
            )
        plate.append(pixels)
    if len(plate) != rows:
        raise ValueError(f"a published plate holds {rows} rows, not {len(plate)}")
    return plate


def _block(value: Any) -> list[int] | None:
    if value is None:
        return None
    return [int(word) for word in value]


def _stopped_on(bands: Any, document: Any) -> str | None:
    "Which layer's stored block the build's own reader will not take."

    for layer in document.layers:
        try:
            bands.decode(layer.block)
        except BaseException:
            return str(layer.name)
    return None


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from plate import bands, compose, protocol

    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            record: dict[str, Any] = {
                "type": kind,
                "index": index,
                "label": str(event.get("label", f"{kind}-{index}")),
                "checks": str(event.get("checks", "")),
            }
            document = None
            try:
                document = protocol.read_document(dict(event["document"]))
                if kind == "render":
                    record["plate"] = _grid(
                        compose.flatten(document), document.rows, document.columns
                    )
                    record["ok"] = True
                elif kind == "resave":
                    written: list[dict[str, Any]] = []
                    for layer in document.layers:
                        model = bands.decode(layer.block)
                        written.append(
                            {"layer": layer.name, "block": _block(bands.encode(model))}
                        )
                    record["written"] = written
                    record["ok"] = True
                else:
                    record["ok"] = False
                    record["error"] = f"unknown export step: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
                if document is not None:
                    stopped = _stopped_on(bands, document)
                    if stopped is not None:
                        record["stopped_on_layer"] = stopped
            records.append(record)

    return {
        "ok": True,
        "records": records,
        "console": captured.getvalue()[-2000:],
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
