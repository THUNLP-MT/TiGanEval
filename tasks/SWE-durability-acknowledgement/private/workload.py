'Deterministic commit timelines for the write path.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


DEVICE_FAULT = "the device refused the write"


NEVER_COMMITTED = 999


class _Script:
    'Builds one timeline, numbering commits and their correlation ids.'

    def __init__(self, seed: int):
        self.seed = int(seed)
        self.commits = 0
        self.steps: list[dict[str, Any]] = []

    def commit(self, tag: str, *, keys: int = 1, sync: bool = False) -> "_Script":
        self.commits += 1
        number = self.commits
        self.steps.append(
            {
                "op": "commit",
                "label": f"commit-{number}",
                "correlation_id": f"w-{self.seed:02d}-{number:03d}",
                "keys": [
                    [f"{tag}/{index}", f"{(self.seed * 37 + number * 11 + index) % 971:03d}"]
                    for index in range(1, int(keys) + 1)
                ],
                "sync": bool(sync),
            }
        )
        return self

    def wait(self, label: str, seq: int) -> "_Script":
        self.steps.append({"op": "wait", "label": label, "seq": int(seq)})
        return self

    def flush(self, label: str, upto_seq: int | None = None) -> "_Script":
        step: dict[str, Any] = {"op": "flush", "label": label}
        if upto_seq is not None:
            step["upto_seq"] = int(upto_seq)
        self.steps.append(step)
        return self

    def fault(self, label: str) -> "_Script":
        self.steps.append({"op": "fault", "label": label, "message": DEVICE_FAULT})
        return self

    def regroup(self, label: str, sync_grouping: int) -> "_Script":
        self.steps.append(
            {"op": "regroup", "label": label, "sync_grouping": int(sync_grouping)}
        )
        return self

    def probe(self, label: str) -> "_Script":
        self.steps.append({"op": "probe", "label": label})
        return self


def _release_traffic(seed: int) -> list[dict[str, Any]]:
    'Mixed sync and non-sync commits, a partial fsync, clients parked on     numbers that are already durable, on numbers that are not yet, and on one     that never arrives.'

    script = _Script(seed)
    script.commit("account", keys=2)
    script.commit("account", keys=1, sync=True)
    script.wait("client-early", 2)
    script.commit("ledger", keys=3)
    script.commit("ledger", keys=1, sync=True)
    script.wait("client-mid", 5)
    script.commit("ledger", keys=2, sync=True)
    script.probe("after-the-first-group")
    script.commit("index", keys=1)
    script.commit("index", keys=2, sync=True)
    script.flush("partial-fsync", upto_seq=6)
    script.wait("client-late", 7)
    script.commit("index", keys=1, sync=True)
    script.flush("full-fsync")
    script.wait("client-settled", 8)
    script.wait("client-parked", NEVER_COMMITTED)
    script.commit("account", keys=2, sync=True)
    script.probe("before-the-deploy")
    return script.steps


def _release_fault(seed: int) -> list[dict[str, Any]]:
    'One refused write, then a device that comes back and takes more bytes.'

    script = _Script(seed)
    script.commit("session", keys=1, sync=True)
    script.commit("session", keys=2, sync=True)
    script.wait("client-ahead", 4)
    script.commit("session", keys=1)
    script.commit("audit", keys=2, sync=True)
    script.fault("device-refused")
    script.commit("audit", keys=1, sync=True)
    script.probe("after-the-refusal")
    script.commit("audit", keys=1, sync=True)
    script.flush("retry-fsync")
    script.wait("client-after", 6)
    script.wait("client-behind", 1)
    script.probe("before-the-deploy")
    return script.steps


def private_sessions(seed: int) -> list[dict[str, Any]]:
    'The four sessions every delivery is measured on.'

    traffic = _release_traffic(seed)
    regrouped = list(traffic)
    regrouped.insert(7, {"op": "regroup", "label": "pipeline-deepened", "sync_grouping": 4})
    return [
        {"name": "primary", "listener": True, "sync_grouping": 3, "timeline": traffic},
        {"name": "replica", "listener": False, "sync_grouping": 3, "timeline": traffic},
        {"name": "regrouped", "listener": True, "sync_grouping": 7, "timeline": regrouped},
        {
            "name": "faulted",
            "listener": True,
            "sync_grouping": 2,
            "timeline": _release_fault(seed),
        },
    ]


def _ack_path_incident(seed: int) -> dict[str, Any]:
    script = _Script(seed)
    script.commit("order", keys=2, sync=True)
    script.commit("order", keys=1)
    script.wait("ack-1", 1)
    script.commit("order", keys=3, sync=True)
    script.commit("cart", keys=1)
    script.commit("cart", keys=2, sync=True)
    script.wait("ack-2", 5)
    script.commit("cart", keys=1, sync=True)
    script.probe("after-the-batch")
    script.commit("order", keys=2, sync=True)
    script.commit("order", keys=1)
    script.wait("ack-3", 7)
    script.commit("cart", keys=1, sync=True)
    script.probe("where-the-node-went-down")
    return {"listener": True, "sync_grouping": 4, "timeline": script.steps}


def _group_commit_trace(seed: int) -> dict[str, Any]:
    script = _Script(seed)
    for tag, keys, sync in (
        ("metric", 1, False),
        ("metric", 2, True),
        ("metric", 1, False),
        ("trace", 3, True),
        ("trace", 1, True),
        ("trace", 2, False),
        ("span", 1, True),
        ("span", 2, True),
    ):
        script.commit(tag, keys=keys, sync=sync)
    script.flush("one-fsync-for-the-lot")
    script.probe("after-one-fsync")
    script.commit("span", keys=1, sync=True)
    script.commit("span", keys=1)
    script.commit("metric", keys=2, sync=True)
    script.flush("half-an-fsync", upto_seq=10)
    script.probe("after-the-partial")
    script.flush("the-rest")
    script.probe("end-of-trace")
    return {"listener": True, "sync_grouping": 8, "timeline": script.steps}


def _fsync_fault_drill(seed: int) -> dict[str, Any]:
    script = _Script(seed)
    script.commit("row", keys=1, sync=True)
    script.commit("row", keys=2, sync=True)
    script.wait("writer-3", 3)
    script.commit("row", keys=1, sync=True)
    script.fault("device-refused")
    script.commit("row", keys=2, sync=True)
    script.probe("after-the-refusal")
    script.commit("row", keys=1, sync=True)
    script.commit("row", keys=1, sync=True)
    script.wait("writer-5", 5)
    script.probe("device-came-back")
    return {"listener": True, "sync_grouping": 2, "timeline": script.steps}


def _replica_node_trace(seed: int) -> dict[str, Any]:
    script = _Script(seed)
    script.commit("replica", keys=1, sync=True)
    script.commit("replica", keys=2)
    script.wait("feed-1", 1)
    script.commit("replica", keys=1, sync=True)
    script.regroup("pipeline-shallowed", 2)
    script.commit("replica", keys=2, sync=True)
    script.commit("replica", keys=1, sync=True)
    script.probe("mid-session")
    script.commit("replica", keys=1, sync=True)
    script.wait("feed-2", NEVER_COMMITTED)
    script.probe("before-the-deploy")
    return {"listener": False, "sync_grouping": 5, "timeline": script.steps}


PUBLIC_BUILDERS = {
    "ack-path-incident": (_ack_path_incident, 3),
    "group-commit-trace": (_group_commit_trace, 11),
    "fsync-fault-drill": (_fsync_fault_drill, 19),
    "replica-node-trace": (_replica_node_trace, 26),
}


def public_session(record_id: str) -> dict[str, Any]:
    'The session one recorded scenario replays.'

    if record_id not in PUBLIC_BUILDERS:
        raise ValueError(f"unknown project record: {record_id}")
    builder, seed = PUBLIC_BUILDERS[record_id]
    return {"name": record_id, **builder(seed)}


def sync_requests(timeline: Sequence[Mapping[str, Any]]) -> int:
    'How many commits in one timeline ask for an fsync.'

    return sum(
        1
        for step in timeline
        if str(step.get("op")) == "commit" and bool(step.get("sync"))
    )
