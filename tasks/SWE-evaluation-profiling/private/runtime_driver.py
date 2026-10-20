'Sandboxed runner for one decision-service drill.'

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import sys
from typing import Any, Mapping


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _stat_rows(mapping: Any) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for key, stat in dict(mapping).items():
        rows[str(key)] = {
            "evals": int(getattr(stat, "evals", 0)),
            "successes": int(getattr(stat, "successes", 0)),
            "reuse": int(getattr(stat, "reuse", 0)),
        }
    return rows


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    from policy import engine as engine_module
    from policy import profile as profile_module
    from policy import protocol

    def rows(profile: Any) -> Any:
        return None if profile is None else _stat_rows(profile_module.stats(profile))

    def decide(engine: Any, request: Mapping[str, Any], enabled: bool) -> dict[str, Any]:
        with protocol.trace_ops() as log:
            decision = engine.decide(request, enabled)
        return {
            "outcome": str(decision.outcome),
            "work": int(decision.work),
            "ops": list(log),
            "profile_is_none": decision.profile is None,
            "rows": rows(decision.profile),
            "profile": decision.profile,
        }

    engine: Any = None
    held: dict[str, Any] = {}
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
            }
            try:
                if kind == "load":
                    policy = protocol.load_policy(dict(event["bundle"]))
                    engine = engine_module.Engine(policy)
                    record["ok"] = True
                elif kind == "decide":
                    request = dict(event["request"])
                    plain = decide(engine, request, False)
                    profiled = decide(engine, request, True)
                    held[record["label"]] = profiled.pop("profile")
                    plain.pop("profile", None)
                    record["ok"] = True
                    record["plain"] = plain
                    record["profiled"] = profiled
                elif kind == "recheck":
                    record["ok"] = True
                    record["rows"] = rows(held.get(str(event["of"])))
                elif kind == "rollup":
                    profile = held.get(str(event["of"]))
                    record["ok"] = True
                    record["source"] = rows(profile)
                    totals = profile_module.package_totals(profile)
                    record["totals"] = _stat_rows(totals)
                    record["source_after_rollup"] = rows(profile)
                    for stat in dict(totals).values():
                        stat.evals += 1000
                        stat.successes += 1000
                        stat.reuse += 1000
                    record["source_after_probe"] = rows(profile)
                elif kind == "rate":
                    profile = held.get(str(event["of"]))
                    reported = []
                    for key, stat in dict(profile_module.stats(profile)).items():
                        reported.append(
                            {
                                "key": str(key),
                                "evals": int(getattr(stat, "evals", 0)),
                                "successes": int(getattr(stat, "successes", 0)),
                                "reported": float(profile_module.rate(stat)),
                            }
                        )
                    reported.append(
                        {
                            "key": "(a rule that has not run)",
                            "evals": 0,
                            "successes": 0,
                            "reported": float(profile_module.rate(protocol.RuleStat())),
                        }
                    )
                    record["ok"] = True
                    record["rates"] = reported
                elif kind == "merge":
                    left = held.get(str(event["left"]))
                    right = held.get(str(event["right"]))
                    record["left_before"] = rows(left)
                    record["right_before"] = rows(right)
                    merged = profile_module.merge(left, right)
                    record["merged"] = rows(merged)
                    held[str(event["into"])] = merged
                    if event.get("probe"):
                        for stat in dict(profile_module.stats(merged)).values():
                            stat.evals += 1000
                            stat.successes += 1000
                            stat.reuse += 1000
                        record["left_after"] = rows(left)
                        record["right_after"] = rows(right)
                        record["what_the_nightly_job_did"] = (
                            "wrote 1000 onto every row of the merged report, then read "
                            "the two shards it was built from back out"
                        )
                    record["ok"] = True
                else:
                    record["ok"] = False
                    record["error"] = f"unknown drill step: {kind}"
            except BaseException as exc:
                record["ok"] = False
                record["error"] = _describe(exc)
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
