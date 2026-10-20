'Sandboxed runner for one recorded whiteboard session against a workspace.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def _op_id(op: Mapping[str, Any]) -> str:
    return f"{str(op['client'])}#{int(op['seq'])}"


def _pack(ops: list[Mapping[str, Any]]) -> str:
    'The private service owns the wire envelope, not candidate code.'

    return json.dumps({"ops": ops}, ensure_ascii=False, sort_keys=True)


def _covered_ids(vector: Any) -> frozenset[str]:
    'Interpret the advertised vector without calling candidate contract code.'

    if not isinstance(vector, Mapping):
        raise ValueError("a state vector must be a mapping")
    covered: set[str] = set()
    for client, raw_seq in vector.items():
        seq = int(raw_seq)
        if seq < 0:
            raise ValueError("a state vector cannot go backwards")
        covered.update(f"{str(client)}#{number}" for number in range(1, seq + 1))
    return frozenset(covered)


def _observe(replica: Any) -> dict[str, Any]:
    'Collect raw public API values; the host-side harness validates them.'

    return {
        "snapshot": replica.snapshot(),
        "state_vector": replica.state_vector(),
        "account": replica.account(),
    }


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from board import merge

    ops = {_op_id(op): dict(op) for op in payload["ops"]}
    plans = dict(payload["replicas"])
    copies: dict[str, Any] = {}
    records: dict[str, dict[str, Any]] = {}
    captured = io.StringIO()

    with redirect_stdout(captured):
        for name, plan in plans.items():
            record: dict[str, Any] = {
                "replica": name,
                "deliveries": [],
                "delivered": [],
                "catch_up": None,
                "final": None,
                "error": None,
            }
            records[name] = record
            delivered: list[str] = []
            try:
                copy = merge.Replica(str(plan.get("client", name)))
            except BaseException as exc:
                record["error"] = _describe(exc)
                continue
            copies[name] = copy
            for packet_ids in plan["deliveries"]:
                identifiers = [str(item) for item in packet_ids]
                repeat = all(item in delivered for item in identifiers)
                try:
                    copy.apply(_pack([ops[item] for item in identifiers]))
                    observation = _observe(copy)
                except BaseException as exc:
                    record["error"] = _describe(exc)
                    break
                for item in identifiers:
                    if item not in delivered:
                        delivered.append(item)
                record["deliveries"].append(
                    {"packet": identifiers, "repeat_of_held_ops": repeat, **observation}
                )
            record["delivered"] = list(delivered)

        for entry in payload.get("catch_up", ()):
            name = str(entry["replica"])
            peer = str(entry["peer"])
            record = records.get(name)
            if record is None or record["error"] is not None or name not in copies:
                continue
            copy = copies[name]
            held = _covered_ids(record["deliveries"][-1]["state_vector"]) if record["deliveries"] else frozenset()
            peer_record = records.get(peer) or {"delivered": []}
            resent = [item for item in peer_record["delivered"] if item not in held]
            try:
                if resent:
                    copy.apply(_pack([ops[item] for item in resent]))
                record["catch_up"] = {"peer": peer, "resent": resent}
                for item in resent:
                    if item not in record["delivered"]:
                        record["delivered"].append(item)
            except BaseException as exc:
                record["error"] = _describe(exc)

        for name, copy in copies.items():
            record = records[name]
            if record["error"] is not None:
                continue
            try:
                record["final"] = _observe(copy)
            except BaseException as exc:
                record["error"] = _describe(exc)

    return {
        "ok": True,
        "replicas": records,
        "client_stdout": captured.getvalue()[-2000:],
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
