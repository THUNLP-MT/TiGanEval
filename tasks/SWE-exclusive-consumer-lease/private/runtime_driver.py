'Sandboxed runner for the fleet job scheduler simulator.'

from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import io
import json
import sys
from typing import Any, Mapping


MINUTE_MS = 60_000.0


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class Recorder:
    'One worker process, as the fleet sees it from the outside.'

    __slots__ = ("process", "name", "job_class", "link", "rank", "raises")

    def __init__(self, process, name, job_class, link, rank, raises):
        self.process = process
        self.name, self.job_class, self.link = name, job_class, link
        self.rank, self.raises = int(rank), bool(raises)

    def on_job(self, job: Any) -> None:
        return None

    def on_revoked(self, claim_id: Any = "") -> None:
        if self.raises:
            raise RuntimeError(f"shutdown hook for {self.name} failed")


def _callback_profiler(cursor: Mapping[str, Any], ledger: dict[str, Any]):
    'Record actual entries into the worker callbacks.'

    job_code = Recorder.on_job.__code__
    revoked_code = Recorder.on_revoked.__code__

    def profile(frame, event, _arg):
        if event != "call" or frame.f_code not in (job_code, revoked_code):
            return
        worker = frame.f_locals.get("self")
        if not isinstance(worker, Recorder):
            return
        if frame.f_code is job_code:
            job = frame.f_locals.get("job")
            ledger["deliveries"].append({
                "op_index": int(cursor["index"]), "process": worker.process,
                "worker": worker.name, "job": str(getattr(job, "job_id", job)),
                "job_class": str(getattr(job, "job_class", worker.job_class)),
                "account": str(getattr(job, "account", "")),
                "claimed_class": worker.job_class, "link": worker.link,
                "rank": worker.rank,
            })
        else:
            ledger["notices"].append({
                "op_index": int(cursor["index"]), "process": worker.process,
                "worker": worker.name, "job_class": worker.job_class,
                "link": worker.link,
                "claim_id": str(frame.f_locals.get("claim_id", "")),
            })

    return profile


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from dispatch import protocol

    module = importlib.reload(importlib.import_module("dispatch.assignment"))
    clock = protocol.Clock(0.0)
    cursor = {"index": -1}
    ledger: dict[str, Any] = {"deliveries": [], "notices": [], "ops": [], "consoles": {}}
    workers: dict[str, Recorder] = {}
    index = 0
    captured = io.StringIO()

    previous_profile = sys.getprofile()
    sys.setprofile(_callback_profiler(cursor, ledger))
    try:
        with redirect_stdout(captured):
            for process in payload.get("processes", ()):
                label = str(process.get("label", "process"))
                state = protocol.FleetState(clock)
                links: dict[str, Any] = {}
                claims: dict[str, str] = {}
                for raw in process.get("ops", ()):
                    op = dict(raw)
                    kind = str(op.get("op", ""))
                    cursor["index"] = index
                    record: dict[str, Any] = {
                        "index": index, "process": label, "op": kind,
                        "link": op.get("link"), "worker": op.get("worker"),
                        "class": op.get("class"), "job": op.get("job"),
                        "at_ms": clock.now_ms(),
                    }
                    try:
                        if kind == "link":
                            links[str(op["link"])] = module.Assigner(
                                state, clock, str(op["link"])
                            )
                        elif kind == "register":
                            links[str(op["link"])].register_class(protocol.JobClassSpec(
                                name=str(op["class"]),
                                exclusive=bool(op.get("exclusive", False)),
                                max_in_flight=int(op.get("max_in_flight", 1)),
                            ))
                        elif kind == "claim":
                            worker = Recorder(
                                label, str(op["worker"]), str(op["class"]),
                                str(op["link"]), int(op.get("rank", 0)),
                                bool(op.get("revoke_raises", False)),
                            )
                            workers[f"{label}/{op['worker']}"] = worker


                            claims.setdefault(str(op["worker"]), "")
                            claims[str(op["worker"])] = str(
                                links[str(op["link"])].claim(
                                    str(op["worker"]),
                                    str(op["class"]),
                                    rank=int(op.get("rank", 0)),
                                    on_job=worker.on_job,
                                    on_revoked=worker.on_revoked,
                                )
                            )
                            record["claim_id"] = claims[str(op["worker"])]
                        elif kind == "release":
                            name = str(op["worker"])
                            links[workers[f"{label}/{name}"].link].release(claims[name])
                        elif kind == "drop_link":
                            links[str(op["link"])].disconnect()
                        elif kind == "retire":
                            links[str(op["link"])].retire_class(str(op["class"]))
                        elif kind == "submit":
                            links[str(op["link"])].submit(protocol.Job(
                                job_id=str(op["job"]), job_class=str(op["class"]),
                                account=str(op.get("account", "")),
                            ))
                        elif kind == "finish":
                            links[str(op["link"])].finish(str(op["job"]))
                        else:
                            raise ValueError(f"unknown fleet operation: {kind}")
                        record["ok"] = True
                    except BaseException as exc:
                        record["ok"] = False
                        record["error"] = _describe(exc)
                    clock.advance(MINUTE_MS)
                    ledger["ops"].append(record)
                    index += 1
                try:
                    ledger["consoles"][label] = state.snapshot()
                except BaseException as exc:
                    ledger["consoles"][label] = {"error": _describe(exc)}
    finally:
        sys.setprofile(previous_profile)

    ledger["ok"] = True
    ledger["stdout"] = captured.getvalue()[-2000:]
    return ledger


def main() -> int:
    try:
        result = run(json.load(sys.stdin))
    except BaseException as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
