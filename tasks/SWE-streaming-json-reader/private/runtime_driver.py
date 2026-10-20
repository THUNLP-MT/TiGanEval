'Sandboxed candidate runner for the streaming JSON reader simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _build(protocol, wire, event: Mapping[str, Any], byte_stream_type, response_type):
    body = bytes.fromhex(str(event["body_hex"]))
    streaming = bool(event.get("streaming", True))
    stream = byte_stream_type(
        wire.chunked(body, int(event.get("chunk_size", 5))),
        rewindable=not streaming,
    )
    response = response_type(
        str(event["content_type"]), stream, streaming=streaming
    )
    audit = {
        "chunks_pulled": 0,
        "bytes_pulled": 0,
        "close_count": 0,
        "read_after_close": 0,
        "total_bytes": len(body),
        "closed": False,
    }


    raw_iter = response.iter_raw
    raw_close = stream.close

    def audited_iter_raw():
        source = iter(raw_iter())

        def generate():
            while True:
                if audit["closed"]:
                    audit["read_after_close"] += 1
                try:
                    chunk = next(source)
                except StopIteration:
                    return
                audit["chunks_pulled"] += 1
                audit["bytes_pulled"] += len(chunk)
                yield chunk

        return generate()

    def audited_close():
        audit["close_count"] += 1
        audit["closed"] = True
        return raw_close()

    response.iter_raw = audited_iter_raw
    stream.close = audited_close
    return stream, response, audit


def _error_kind(exc: BaseException, expected_errors) -> str:
    for name, expected_type in expected_errors:
        if isinstance(exc, expected_type):
            return name
    name = type(exc).__name__
    if name in {expected_name for expected_name, _ in expected_errors}:
        return f"{type(exc).__module__}.{type(exc).__qualname__}"
    return name


def _drain(reader, response, audit, mode: str, expected_errors) -> dict[str, Any]:
    values: list[Any] = []
    marks: list[int] = []
    record: dict[str, Any] = {}
    iterator = None
    try:
        iterator = iter(reader.iter_json(response))
        for value in iterator:
            values.append(value)
            marks.append(int(audit["bytes_pulled"]))
            if mode == "early_break":
                break
        record["error"] = None
    except BaseException as exc:
        record["error"] = _error_kind(exc, expected_errors)
        record["error_detail"] = _describe(exc)
    if mode == "early_break" and iterator is not None:
        close = getattr(iterator, "close", None)
        if callable(close):
            try:
                close()
            except BaseException as exc:
                record["close_error"] = _describe(exc)
    record["values"] = values
    record["bytes_pulled_at_value"] = marks
    return record


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from client import protocol, wire

    byte_stream_type = protocol.ByteStream
    response_type = protocol.Response
    expected_errors = (
        ("DecodingError", protocol.DecodingError),
        ("StreamConsumed", protocol.StreamConsumed),
    )
    records: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            if str(event.get("type", "")) != "read":
                records.append({"type": "driver_error", "index": index, "error": "unknown event"})
                continue
            reader = importlib.reload(importlib.import_module("client.reader"))
            mode = str(event.get("mode", "full"))
            record: dict[str, Any] = {
                "type": "read",
                "index": index,
                "label": str(event.get("label", f"case-{index}")),
                "scenario": str(event.get("scenario", "")),
                "content_type": str(event.get("content_type", "")),
                "chunk_size": int(event.get("chunk_size", 5)),
                "streaming": bool(event.get("streaming", True)),
                "mode": mode,
            }
            try:
                stream, response, audit = _build(
                    protocol, wire, event, byte_stream_type, response_type
                )
            except BaseException as exc:
                record["setup_error"] = _describe(exc)
                records.append(record)
                continue
            record["body_bytes"] = int(audit["total_bytes"])
            first = _drain(
                reader,
                response,
                audit,
                "early_break" if mode == "early_break" else "full",
                expected_errors,
            )
            record["first_pass"] = first
            if mode == "twice":
                second = _drain(reader, response, audit, "full", expected_errors)
                record["second_pass"] = second
            record["stream"] = {
                key: int(audit[key])
                for key in (
                    "chunks_pulled",
                    "bytes_pulled",
                    "close_count",
                    "read_after_close",
                    "total_bytes",
                )
            }
            record["is_stream_consumed"] = bool(response.is_stream_consumed)
            records.append(record)
    return {
        "ok": True,
        "records": records,
        "candidate_stdout": captured.getvalue()[-2000:],
    }


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
