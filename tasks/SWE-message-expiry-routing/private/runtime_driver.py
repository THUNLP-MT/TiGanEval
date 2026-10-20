'Sandboxed candidate runner for the message broker simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from broker import protocol

    raw_snapshot = payload.get("snapshot")
    snapshot = dict(raw_snapshot) if isinstance(raw_snapshot, Mapping) else None
    clock = protocol.Clock(float(payload.get("start_time", 0.0)))
    state = protocol.BrokerState(snapshot)
    module = importlib.reload(importlib.import_module("broker.channel"))
    channel = module.Channel(state, clock)
    raw_tags = payload.get("tags")
    tags: dict[str, str] = (
        {str(label): str(tag) for label, tag in dict(raw_tags).items()}
        if isinstance(raw_tags, Mapping)
        else {}
    )
    index_offset = int(payload.get("index_offset", 0))
    records: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for position, raw_event in enumerate(payload.get("events", ())):
            index = index_offset + position
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            record: dict[str, Any] = {
                "type": kind,
                "index": index,
                "label": str(event.get("label", f"{kind}-{index}")),
                "now": clock.now(),
            }
            try:
                if kind == "reset":


                    state = protocol.BrokerState({"next_tag": state.next_tag})
                    channel = module.Channel(state, clock)
                    tags = {}
                    clock.set(float(event.get("now", 0.0)))
                    record["ok"] = True
                elif kind == "advance":
                    clock.set(clock.now() + float(event.get("seconds", 0.0)))
                    record["ok"] = True
                    record["now"] = clock.now()
                elif kind == "declare":
                    for raw_spec in event.get("specs", ()):
                        channel.declare(protocol.QueueSpec.from_mapping(dict(raw_spec)))
                    record["ok"] = True
                elif kind == "publish":
                    identifiers = channel.publish(
                        [str(queue) for queue in event.get("queues", ())],
                        event.get("body"),
                        dict(event.get("headers", {})) or None,
                        event.get("ttl"),
                    )
                    listed = [str(item) for item in (identifiers or ())]
                    record["ok"] = True
                    record["message_ids"] = listed
                    for queue, identifier in zip(event.get("queues", ()), listed):
                        published.append(
                            {
                                "message_id": identifier,
                                "queue": str(queue),
                                "label": record["label"],
                                "index": index,
                                "body": event.get("body"),
                            }
                        )
                elif kind == "get":
                    record["queue"] = str(event["queue"])
                    delivery = channel.get(str(event["queue"]))
                    record["ok"] = True
                    if delivery is None:
                        record["delivery"] = None
                    else:
                        tag = str(delivery["tag"])
                        message = delivery["message"]
                        tags[record["label"]] = tag
                        record["delivery"] = {
                            "tag": tag,
                            "message": message.as_dict()
                            if hasattr(message, "as_dict")
                            else dict(message),
                            "redelivery_count": channel.redelivery_count(tag),
                        }
                elif kind in ("ack", "reject"):


                    record["tag_of"] = str(event.get("tag_of", ""))
                    if kind == "reject":
                        record["requeue"] = bool(event.get("requeue", False))
                    tag = tags.get(str(event.get("tag_of", "")))
                    if tag is None:


                        record["ok"] = True
                        record["skipped"] = f"no delivery was recorded for {event.get('tag_of')!r}"
                    elif kind == "ack":
                        channel.ack(tag)
                        record["ok"] = True
                    else:
                        channel.reject(tag, bool(event.get("requeue", False)))
                        record["ok"] = True
                elif kind == "drain_expired":
                    record["queue"] = str(event["queue"])
                    record["ok"] = True
                    record["expired"] = int(channel.drain_expired(str(event["queue"])))
                elif kind == "restart":


                    record["ok"] = True
                elif kind == "inspect":
                    record["ok"] = True
                else:
                    record["ok"] = False
                    record["error"] = f"unknown event: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
            try:
                record["state"] = json.loads(json.dumps(state.snapshot()))
            except BaseException as exc:
                record["state_error"] = _describe(exc)
            records.append(record)

    return {
        "ok": True,
        "records": records,
        "published": published,
        "candidate_stdout": captured.getvalue()[-2000:],
        "snapshot": json.loads(json.dumps(state.snapshot())),
        "now": clock.now(),
        "tags": dict(tags),
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
