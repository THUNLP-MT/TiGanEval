'Sandboxed runner for the nightly archive job.'

from __future__ import annotations

import base64
from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _seed(protocol: Any, destination: Any, item: Mapping[str, Any], job: str) -> None:
    'One object that was in the vault before the stretch began.'

    payload = protocol.compress(protocol.dump_bytes(job, str(item["night"]), int(item["rows"])))
    name = str(item["object"])
    if not item.get("key"):
        destination.begin(name)
        destination.write(name, payload)
        destination.finalize(name)
        destination.close(name)
        return
    key = protocol.decode_key(str(item["key"]))
    stream = protocol.stream_id(job, str(item["night"]), destination.name)
    chunk = protocol.CHUNK_BYTES
    body = b"".join(
        protocol.frame(protocol.seal(key, protocol.chunk_nonce(stream, index),
                                     payload[start : start + chunk]))
        for index, start in enumerate(range(0, len(payload), chunk)))
    data = (protocol.write_header(protocol.key_id(key), stream) + body
            + protocol.SENTINEL + protocol.seal_trailer(key, body))
    destination.begin(name)
    destination.write(name, data)
    destination.finalize(name)
    destination.close(name)


class _DestinationView:
    'The job-facing destination API plus an evaluator-owned event clock.'

    __slots__ = ("name", "_begin", "_write", "_finalize", "_close", "_delete",
                 "_listing", "_read", "_events", "_timeline")

    def __init__(self, destination: Any, timeline: list[dict[str, Any]]):
        self.name = str(destination.name)
        self._begin = destination.begin
        self._write = destination.write
        self._finalize = destination.finalize
        self._close = destination.close
        self._delete = destination.delete
        self._listing = destination.listing
        self._read = destination.read_object
        self._events = destination.events
        self._timeline = timeline

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def _record(self, event: str, name: str, **fields: Any) -> None:
        self._timeline.append(
            {"event": event, "destination": self.name, "object": str(name), **fields}
        )

    def begin(self, name: str) -> str:
        result = self._begin(name)
        self._record("opened", name)
        return result

    def write(self, name: str, data: bytes) -> int:
        result = self._write(name, data)
        self._record("wrote", name, bytes=len(bytes(data)))
        return result

    def read_object(self, name: str) -> bytes:
        data = self._read(name)
        event = {"event": "read", "object": str(name), "bytes": len(data)}
        self._events.append(event)
        self._record("read", name, bytes=len(data))
        return data

    def finalize(self, name: str) -> None:
        self._finalize(name)
        self._record("finalized", name)

    def close(self, name: str) -> None:
        self._close(name)
        self._record("closed", name)

    def delete(self, name: str) -> None:
        self._delete(name)
        self._record("deleted", name)

    def listing(self) -> tuple[dict[str, Any], ...]:
        return self._listing()


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from nightly import protocol

    job = str(payload.get("job", "orders"))
    destinations = {name: protocol.Destination(name) for name in payload.get("destinations", ())}
    for item in payload.get("seeded", ()):
        _seed(protocol, destinations[str(item["destination"])], item, job)
    for destination in destinations.values():
        destination.events.clear()
    timeline: list[dict[str, Any]] = []
    job_destinations = {
        name: _DestinationView(destination, timeline)
        for name, destination in destinations.items()
    }
    pipeline = importlib.reload(importlib.import_module("nightly.pipeline"))
    restore = importlib.reload(importlib.import_module("nightly.restore"))

    nights: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for spec in payload.get("nights", ()):
            marks = {name: len(dest.events) for name, dest in destinations.items()}
            timeline_mark = len(timeline)
            for name, dest in destinations.items():
                dest.script(**{str(k): v for k, v in dict(spec.get("script", {})).get(name, {}).items()})
            run_spec = protocol.NightRun(
                job=job,
                night=str(spec["night"]),
                dump=protocol.DumpSource(job, str(spec["night"]), int(spec["rows"])),
                destinations=job_destinations,
                key_config=protocol.KeyConfig(**dict(spec.get("key_config", {}))),
                env=dict(spec.get("env", {})),
                files=dict(spec.get("files", {})),
            )
            record: dict[str, Any] = {"night": str(spec["night"])}
            try:
                report = pipeline.run_night(run_spec)
            except BaseException as exc:
                record["raised"] = _describe(exc)
            else:
                record["report"] = report if isinstance(report, Mapping) else {"returned": repr(report)}
            record["events"] = {
                name: list(dest.events[marks[name] :]) for name, dest in destinations.items()
            }
            record["timeline"] = list(timeline[timeline_mark:])
            record["handed"] = {
                name: {
                    entry["object"]: base64.b64encode(dest.bytes_handed_over(entry["object"])).decode()
                    for entry in dest.events[marks[name] :]
                    if entry.get("event") == "opened"
                }
                for name, dest in destinations.items()
            }
            nights.append(record)
        for dest in destinations.values():
            dest.script()
        keyring = {}
        for value in payload.get("keyring", ()):
            key = protocol.decode_key(str(value))
            keyring[protocol.key_id(key)] = key
        drill: list[dict[str, Any]] = []
        if payload.get("drill"):
            for dest in destinations.values():
                for entry in dest.listing():
                    if not entry["finalized"]:
                        continue
                    name = str(entry["object"])
                    row = {"destination": dest.name, "object": name}
                    try:
                        opened = restore.open_archive(name, dest.read_object(name), dict(keyring))
                    except BaseException as exc:
                        row["error"] = _describe(exc)
                    else:
                        data = bytes(opened) if isinstance(opened, (bytes, bytearray)) else b""
                        row["opened_bytes"] = len(data)
                        row["digest"] = hashlib.sha256(data).hexdigest()[:16]
                        if not isinstance(opened, (bytes, bytearray)):
                            row["returned"] = type(opened).__name__
                    drill.append(row)

    return {
        "ok": True,
        "nights": nights,
        "listings": {name: list(dest.listing()) for name, dest in destinations.items()},
        "stored": {
            name: {
                str(entry["object"]): base64.b64encode(dest.read_object(str(entry["object"]))).decode()
                for entry in dest.listing()
            }
            for name, dest in destinations.items()
        },
        "drill": drill,
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
