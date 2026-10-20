'Sandboxed replay of one CI run against a candidate shard planner.'

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from typing import Any, Mapping, Sequence

HISTORY = "duration-history.json"
_WITH_ENTRIES = {"snapshot", "record", "record_group", "history_set", "history_publish"}
_PLAN_FIELDS = ("run_id", "attempt", "index", "shard_count", "history_generation", "files",
                "predicted_ms", "estimates")


def _jsonable(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth > 6:
        return repr(value)[:200]
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item, depth + 1) for item in value]
    return repr(value)[:200]


def _whole(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _history_document(path: Path) -> dict[str, Any] | None:
    'Read the shared file without trusting code in the candidate package.'

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            return None
        generation = _whole(raw.get("generation"), "generation")
        source = raw.get("entries")
        if not isinstance(source, Mapping):
            return None
        entries: dict[str, list[dict[str, Any]]] = {}
        for path_name, observations in source.items():
            if not isinstance(path_name, str) or isinstance(observations, (str, bytes)):
                return None
            if not isinstance(observations, Sequence) or not observations:
                return None
            parsed: list[dict[str, Any]] = []
            for item in observations:
                if not isinstance(item, Mapping):
                    return None
                duration = _whole(item.get("duration_ms"), "duration_ms")
                published = _whole(item.get("generation"), "generation")
                recorded_at = item.get("recorded_at")
                if isinstance(recorded_at, bool) or not isinstance(recorded_at, (int, float)):
                    return None
                parsed.append({"duration_ms": duration, "generation": published,
                               "recorded_at": float(recorded_at)})
            entries[path_name] = sorted(parsed, key=lambda row: (row["generation"], row["recorded_at"]))
        return {"generation": generation, "entries": dict(sorted(entries.items()))}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _write_history(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _hash_shard(files: Sequence[str], index: int, count: int) -> tuple[str, ...]:
    return tuple(path for path in sorted(set(str(item) for item in files))
                 if int(hashlib.md5(path.encode("utf-8")).hexdigest(), 16) % count + 1 == index)


def _require_plan(value: Any) -> dict[str, Any]:
    'Parse the runner-facing plan independently of candidate-mutable helpers.'

    if not isinstance(value, Mapping):
        raise ValueError("plan must be a mapping")
    missing = [name for name in _PLAN_FIELDS if name not in value]
    if missing:
        raise ValueError(f"plan is missing: {', '.join(missing)}")
    run_id = value.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must name the run")
    attempt = _whole(value.get("attempt"), "attempt", 1)
    index = _whole(value.get("index"), "index", 1)
    shard_count = _whole(value.get("shard_count"), "shard_count", 1)
    if index > shard_count:
        raise ValueError(f"shard index {index} is outside 1..{shard_count}")
    files = value.get("files")
    estimates = value.get("estimates")
    if isinstance(files, (str, bytes)) or not isinstance(files, Sequence):
        raise ValueError("files must be a sequence")
    listed: list[str] = []
    for item in files:
        if not isinstance(item, str) or not item:
            raise ValueError("files must hold paths")
        listed.append(item)
    if not isinstance(estimates, Mapping):
        raise ValueError("estimates must be a mapping")
    priced: dict[str, int] = {}
    for path, duration in estimates.items():
        if not isinstance(path, str) or not path:
            raise ValueError("estimates must hold paths")
        priced[path] = _whole(duration, "estimate")
    return {
        "run_id": run_id,
        "attempt": attempt,
        "index": index,
        "shard_count": shard_count,
        "history_generation": _whole(value.get("history_generation"), "history_generation"),
        "files": listed,
        "predicted_ms": _whole(value.get("predicted_ms"), "predicted_ms"),
        "estimates": priced,
    }


def _assigned(plan: Any) -> list[str] | None:
    'The files a plan names, read as leniently as the shard would read them.'

    listed = plan.get("files") if isinstance(plan, Mapping) else None
    if isinstance(listed, (str, bytes)) or not isinstance(listed, (list, tuple)):
        return None
    return [str(item) for item in listed]


def _ran(path: str, true_ms: Mapping[str, int], skipped: set[str], crashed: set[str]) -> dict[str, Any]:
    'What one machine reports back about one file it was handed.'

    if path in crashed:
        return {"file": path, "duration_ms": max(1, true_ms.get(path, 0) // 3), "status": "crashed"}
    if path in skipped:
        return {"file": path, "duration_ms": 0, "status": "skipped"}
    return {"file": path, "duration_ms": int(true_ms.get(path, 0)), "status": "completed"}


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from sharding import protocol


    RunContext, Checkout = protocol.RunContext, protocol.Checkout
    module = importlib.import_module("sharding.planner")
    history = Path(HISTORY)
    files: tuple[str, ...] = ()
    true_ms: dict[str, int] = {}
    assigned: dict[str, list[str] | None] = {}
    observed: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    captured = io.StringIO()

    with redirect_stdout(captured):
        for position, raw_event in enumerate(payload.get("events", ())):
            event = dict(raw_event)
            kind = str(event.get("type", ""))
            key = f"{event.get('group')}/{event.get('index')}"
            record: dict[str, Any] = {
                "type": kind, "index": position, "group": event.get("group"),
                "label": str(event.get("label", f"{kind}-{position}")), "phase": event.get("phase")}
            try:
                if kind == "checkout":
                    files = tuple(str(item) for item in event.get("files", ()))
                    true_ms = {str(k): int(v) for k, v in dict(event.get("durations", {})).items()}
                    record.update(ok=True, files=list(files), durations=dict(true_ms))
                elif kind == "history_set":
                    written = event.get("text")
                    if written is None:
                        history.unlink(missing_ok=True)
                    else:
                        history.write_text(str(written), encoding="utf-8")
                    record["ok"] = True
                elif kind == "history_publish":
                    current = _history_document(history)
                    entries = ({path: list(items) for path, items in current["entries"].items()}
                               if current is not None else {})
                    generation = int(event.get("generation", 1))
                    when = float(event.get("recorded_at", 0.0))
                    for path, value in dict(event.get("durations", {})).items():
                        entries.setdefault(str(path), []).append({
                            "duration_ms": int(value), "generation": generation, "recorded_at": when})
                    _write_history(history, {
                        "generation": max(generation, int(current["generation"]) if current else 0),
                        "entries": entries,
                    })
                    record["ok"] = True
                elif kind == "plan":
                    order = [str(item) for item in event.get("order", files)]
                    shard, count = int(event.get("index", 1)), int(event.get("count", 1))
                    raw_run = dict(event.get("run", {}))
                    context = RunContext(run_id=str(raw_run["run_id"]), attempt=int(raw_run["attempt"]),
                                         history_generation=int(raw_run["history_generation"]),
                                         now=float(raw_run["now"]))
                    record.update(
                        shard_index=shard, shard_count=count, run=dict(raw_run),
                        walk_order=order, discovered=sorted(set(order)),
                        reference_files=list(_hash_shard(order, shard, count)))
                    checkout = Checkout(root=str(Path.cwd()), files=tuple(order))
                    plan = module.plan_shards(checkout, context, str(history), shard, count)
                    assigned[key] = _assigned(plan)
                    record.update(ok=True, plan=_jsonable(plan), assigned=assigned[key])
                    try:
                        record["plan_read"] = _jsonable(_require_plan(plan))
                    except ValueError as exc:
                        record["plan_error"] = str(exc)
                elif kind == "shard_run":
                    listed = assigned.get(key)
                    skipped = {str(item) for item in event.get("skipped_files", ())}
                    crashed = {str(item) for item in event.get("crashed_files", ())}
                    rows = [_ran(path, true_ms, skipped, crashed) for path in listed or ()]
                    observed[key] = rows
                    record.update(ok=True, observations=rows,
                                  shard_index=int(event.get("index", 0)))
                elif kind == "record":
                    raw_run = dict(event.get("run", {}))
                    context = RunContext(run_id=str(raw_run["run_id"]), attempt=int(raw_run["attempt"]),
                                         history_generation=int(raw_run["history_generation"]),
                                         now=float(raw_run["now"]))
                    rows = observed.get(key, [])
                    record.update(ok=True, run=dict(raw_run), observations=rows,
                                  shard_index=int(event.get("index", 0)))
                    module.record_durations(str(history), context, [dict(r) for r in rows])
                elif kind == "record_group":
                    raw_run = dict(event.get("run", {}))
                    indices = [int(item) for item in event.get("indices", ())]
                    batches = {index: [dict(row) for row in observed.get(
                        f"{event.get('group')}/{index}", [])] for index in indices}
                    barrier = threading.Barrier(len(indices))
                    errors: dict[int, str] = {}

                    def publish(index: int) -> None:
                        context = RunContext(
                            run_id=str(raw_run["run_id"]), attempt=int(raw_run["attempt"]),
                            history_generation=int(raw_run["history_generation"]), now=float(raw_run["now"]))
                        try:
                            barrier.wait()
                            module.record_durations(str(history), context, batches[index])
                        except BaseException as exc:
                            errors[index] = f"{type(exc).__name__}: {str(exc)[:200]}"

                    threads = [threading.Thread(target=publish, args=(index,)) for index in indices]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join()
                    record.update(ok=not errors, run=dict(raw_run), shard_indices=indices,
                                  observations_by_shard={str(k): v for k, v in batches.items()},
                                  errors={str(k): v for k, v in errors.items()})
                    if errors:
                        record["error"] = "; ".join(f"shard {k}: {v}" for k, v in sorted(errors.items()))
                elif kind == "snapshot":
                    record["ok"] = True
                else:
                    record.update(ok=False, error=f"unknown event: {kind}")
            except BaseException as exc:
                record.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:200]}")
            document = _history_document(history)
            record.update(history_present=history.exists(), history_readable=document is not None,
                          history_generation=None if document is None else document["generation"])
            if kind in _WITH_ENTRIES:
                record["history_entries"] = None if document is None else document["entries"]
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
