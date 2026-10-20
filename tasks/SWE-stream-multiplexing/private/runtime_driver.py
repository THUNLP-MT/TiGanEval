'Sandboxed runner for one telemetry-uplink drill.'

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _payload(token: str, size: int) -> bytes:
    out = bytearray()
    while len(out) < size:
        out += hashlib.sha256(f"{token}:{len(out)}".encode()).digest()
    return bytes(out[:size])


class Drill:
    'One station session driven through a fixed sequence of steps.'

    def __init__(self, protocol: Any, sessions: Any):
        self.protocol, self.sessions = protocol, sessions

    def start(self, raw: Mapping[str, Any]) -> None:
        self.config = self.protocol.SessionConfig(**dict(raw))
        self.transport = self.protocol.Transport()
        self.peer = self.protocol.PeerEnd(self.config)
        self.session = self.sessions.Session(self.transport, self.config)
        self.streams: dict[str, Any] = {}
        self.ids: dict[str, int] = {}
        self.mine: dict[int, str] = {}
        self.theirs: dict[int, str] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self.handed: dict[str, bytearray] = {}
        self.pushed: dict[str, bytearray] = {}
        self.read_back: dict[str, bytearray] = {}
        self.emitted: dict[str, int] = {}
        self.taken: dict[str, int] = {}
        self.peak: dict[str, int] = {}
        self.tickets: list[tuple[str, Any]] = []
        self.opened = self.fed_frames = self.fed_payload = self.on_radio = 0


    def _off_the_radio(self) -> list[list[Any]]:
        'Hand the unit whatever the session has just put on the radio.'

        block = bytes(self.transport.taken[self.on_radio :])
        self.on_radio += len(block)
        frames, _rest = self.protocol.decode_frames(block)
        self.peer.feed(block)
        out = []
        for frame in frames:
            out.append([frame.name, int(frame.stream), len(frame.payload)])
            if frame.command == self.protocol.DATA:

                label = self.mine.get(frame.stream) or self.theirs.get(frame.stream) or "?"
                self.emitted[label] = self.emitted.get(label, 0) + len(frame.payload)
        for label, sent in self.emitted.items():
            self.peak[label] = max(self.peak.get(label, 0), sent - self.taken.get(label, 0))
        return out

    def _onto_the_radio(self) -> None:
        'Hand the session whatever the unit has queued for it.'

        block = self.peer.outbound()
        if not block:
            return
        frames, _rest = self.protocol.decode_frames(block)
        self.fed_frames += len(frames)
        self.fed_payload += sum(
            len(frame.payload) for frame in frames if frame.command == self.protocol.DATA
        )
        self.session.feed(block)


    def step(self, event: Mapping[str, Any], out: dict[str, Any]) -> None:
        kind, label = str(event.get("type")), str(event.get("stream", ""))
        out["stream"] = label
        if kind == "session":
            self.start(dict(event["config"]))
            out["config"] = dict(event["config"])
        elif kind == "open":
            stream = self.session.open_stream(int(event["priority"]))
            self.streams[label], self.ids[label] = stream, int(stream.id)
            self.mine.setdefault(int(stream.id), label)
            self.rows[label] = {"priority": int(event["priority"]), "drains": bool(event["drains"])}
            self.opened += 1
            out["id"] = int(stream.id)
        elif kind == "peer_open":
            stream_id = int(self.peer.open_stream())
            self.ids[label] = stream_id
            self.theirs.setdefault(stream_id, label)
            self.rows[label] = {"priority": 1, "drains": False}
            self.opened += 1
            self._onto_the_radio()
            out["id"] = stream_id
        elif kind == "accept":
            stream = self.session.accept_stream()
            if stream is not None:
                self.streams[label] = stream
            out["id"] = None if stream is None else int(stream.id)
        elif kind == "write":
            handed = self.handed.setdefault(label, bytearray())
            for index, size in enumerate(event["chunks"]):
                data = _payload(f"{event['token']}:{index}", int(size))
                self.tickets.append((label, self.streams[label].write(data)))
                handed += data
            out["handed_over"] = len(handed)
        elif kind == "peer_push":
            data = _payload(str(event["token"]), int(event["size"]))
            self.pushed.setdefault(label, bytearray())
            self.pushed[label] += data
            self.peer.push(self.ids[label], data)
            self._onto_the_radio()
            out["size"] = len(data)
        elif kind == "pump":
            before = dict(self.emitted)
            before_radio = len(self.transport.taken)
            out["budget"] = int(event["budget"])
            out["returned"] = int(self.session.pump(int(event["budget"])) or 0)
            out["wire_bytes"] = len(self.transport.taken) - before_radio
            out["frames"] = self._off_the_radio()
            out["delivered"] = {
                name: total - before.get(name, 0)
                for name, total in self.emitted.items()
                if total > before.get(name, 0)
            }
        elif kind == "drain":
            took = int(self.peer.drain(self.ids[label], int(event["size"])))
            self.taken[label] = self.taken.get(label, 0) + took
            self._onto_the_radio()
            self.peak[label] = max(
                self.peak.get(label, 0), self.emitted.get(label, 0) - self.taken[label]
            )
            out.update({"asked": int(event["size"]), "took": took})
        elif kind == "read":
            got = bytes(self.streams[label].read()) if label in self.streams else b""
            self.read_back.setdefault(label, bytearray())
            self.read_back[label] += got
            self._onto_the_radio()
            out.update({"read_bytes": len(got), "after_close": bool(event.get("after_close"))})
        elif kind == "close_stream":
            self.streams[label].close()
        elif kind == "peer_close":
            self.peer.close_stream(self.ids[label])
            self._onto_the_radio()
        elif kind == "present":
            unread = len(self.pushed.get(label, b"")) - len(self.read_back.get(label, b""))
            out.update({
                "present": int(self.ids[label]) in dict(self.session.streams),
                "unread_here": max(0, unread),
                "must_be_gone": bool(event.get("must_be_gone")),
                "must_be_listed": bool(event.get("must_be_listed")),
                "one_end_open": str(event.get("one_end_open", "")),
            })
        elif kind == "probe":
            out.update({"kind": str(event["kind"]), "raised": self._probe(str(event["kind"]), label)})
        elif kind == "close_session":
            self.transport.refusing = bool(event.get("refusing"))
            raised = "nothing"
            try:
                self.session.close()
            except BaseException as exc:
                raised = _describe(exc)
            self.transport.refusing = False
            out.update({"refusing": bool(event.get("refusing")), "raised": raised})
        elif kind == "report":
            out.update(self.report())
        else:
            raise ValueError(f"unknown drill step: {kind}")

    def _settled(self, ticket: Any) -> str:
        'What finished this write, as the console names it.'

        error = getattr(ticket, "error", None)
        if error is None:
            return "nothing"
        if isinstance(error, self.protocol.ClosedLink):
            return "ClosedLink"
        return type(error).__name__

    def _probe(self, kind: str, label: str) -> str:
        try:
            if kind == "open":
                self.session.open_stream(1)
                self.opened += 1
            else:
                self.streams[label].write(b"probe")
        except self.protocol.ClosedLink:
            return "ClosedLink"
        except BaseException as exc:
            return _describe(exc)
        return "nothing"


    def _row(self, label: str, row: Mapping[str, Any]) -> dict[str, Any]:
        stream_id = self.ids.get(label, -1)
        handed = bytes(self.handed.get(label, b""))
        pushed, read_back = bytes(self.pushed.get(label, b"")), bytes(self.read_back.get(label, b""))
        arrived = int(self.peer.arrived(stream_id))
        return {
            "stream": label, "id": stream_id, **dict(row),
            "handed_over": len(handed),
            "put_on_the_radio": self.emitted.get(label, 0),
            "arrived_at_the_unit": arrived,
            "arrived_in_order": self.protocol.digest_of(handed[:arrived]) == self.peer.digest(stream_id),
            "owed": len(handed) - self.emitted.get(label, 0),
            "sent_by_the_unit": len(pushed),
            "read_here": len(read_back),
            "read_in_order": pushed[: len(read_back)] == read_back,
            "taken_by_the_units_consumer": self.taken.get(label, 0),
            "peak_standing_at_the_unit": self.peak.get(label, 0),
        }

    def report(self) -> dict[str, Any]:
        frames, _rest = self.protocol.decode_frames(bytes(self.transport.taken))
        data = [frame for frame in frames if frame.command == self.protocol.DATA]
        return {
            "counters": self.session.counters.snapshot(),
            "measured": {
                "frames_sent": len(frames),
                "frames_received": self.fed_frames,
                "payload_bytes_sent": sum(len(frame.payload) for frame in data),
                "payload_bytes_received": self.fed_payload,
                "streams_opened": self.opened,
                "streams_closed": self.opened - len(dict(self.session.streams)),
            },
            "open_streams": sorted(int(key) for key in dict(self.session.streams)),
            "send_window": int(self.config.send_window),
            "max_frame_size": int(self.config.max_frame_size),
            "streams": [self._row(label, row) for label, row in sorted(self.rows.items())],
            "tickets": [
                {
                    "stream": label,
                    "handed_over": int(getattr(ticket, "total", -1)),
                    "delivered": int(getattr(ticket, "delivered", -1)),
                    "finished": bool(getattr(ticket, "done", False)),
                    "settled_as": self._settled(ticket),
                }
                for label, ticket in self.tickets
            ],
            "frames_the_unit_refused": [dict(item) for item in self.peer.rejected_frames],
            "streams_the_unit_opened": sorted(int(item) for item in self.peer.mine),
        }


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from link import protocol
    from link import session as sessions

    drill = Drill(protocol, sessions)
    records: list[dict[str, Any]] = []
    captured = io.StringIO()
    with redirect_stdout(captured):
        for index, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            record: dict[str, Any] = {
                "type": str(event.get("type", "")),
                "index": index,
                "label": str(event.get("label", f"step-{index}")),
                "phase": str(event.get("phase", "")),
            }
            try:
                drill.step(event, record)
                record["ok"] = True
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            records.append(record)
    return {"ok": True, "records": records, "console": captured.getvalue()[-2000:]}


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
