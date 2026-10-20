'Read one delivered failure notebook against the world it is a reading of.'

from __future__ import annotations

from fractions import Fraction
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from . import oracle
from . import world as w
from .workload import CURRENT, LATER_REVIEWS, SPENT_IDS, SPENT_TRACES


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-queue-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

BUCKETS: Mapping[str, str] = {
    "window_failure_rate": "rate_failures",
    "reported_range": "range_failures",
    "next_trace_plan": "plan_failures",
    "receipt_accounting": "ledger_failures",
    "correction_invariant": "invariance_failures",
}


VARIATION_MODES: Mapping[str, str] = {
    "spill": "moves_with_spill_fraction",
    "cap": "moves_with_retry_cap",
    "rollout": "moves_with_rollout_day",
    "stalled": "moves_with_unfinished_rollout",
}


WEEK_LABELS: Mapping[str, str] = {
    "quote-api-september": "the September week",
    "quote-api-october": "the October week",
    "quote-api-november": "the November week",
    "quote-api-august": "the August week",
    "quote-api-december": "the December week",
}


OPERATIONS_SLACK = Fraction(1, 1000)


REPORT_COHERENCE_SLACK = Fraction(5, 10000)

RANGE_SLACK = Fraction(18, 10000)


def _is_report_number(value: Any) -> bool:
    'A finite JSON number that the review can use in its arithmetic.'

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _unreadable_report_field(answer: Mapping[str, Any]) -> tuple[str, Any] | None:
    "The first missing or non-numeric member of the report's one reading."

    for field in ("operations", "failed_operations", "failure_rate"):
        value = answer.get(field)
        if not _is_report_number(value):
            return field, value
    return None


def _near_count(reported: Any, wanted: int, total: int) -> bool:
    if not _is_report_number(reported):
        return False
    return abs(reported - wanted) <= float(OPERATIONS_SLACK * total)


def _near_rate(reported: Any, wanted: Fraction, slack: Fraction) -> bool:
    if not _is_report_number(reported):
        return False
    return abs(Fraction(str(reported)) - wanted) <= slack


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _percent(value: Any) -> str:
    'One share of operations written the way the capacity record writes it.'

    try:
        return format(float(value) * 100, ".2f")
    except (TypeError, ValueError):
        return _show(value)


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_percent(value[0])} to {_percent(value[1])}"
    return _show(value)


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident Marisol can open the export for first.'

    return (0 if str(record.get("kind")) == "candidate_process_failure" else 1,
            0 if record.get("review") == CURRENT.review else 1)


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The trace units this delivery paid for, or why the ledger will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(world: w.World, entries: Sequence[Mapping[str, Any]],
                walk: int = 5) -> list[dict[str, Any]]:
    'Every collection state this review can be in, with what is left to pull.'

    granted = int(world.spec["units_granted"])
    cost = int(world.spec["unit_cost"])

    def state(label: str, stream: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        left = granted - w.units_spent(stream)
        allowed = oracle.allowed_traces(world, stream)
        return {
            "label": label,
            "receipts": [dict(item) for item in stream],
            "paid": {(str(item["minute"]), str(item["pool"])) for item in stream},
            "units_left": left,
            "allowed": allowed,
            "open_left": 0 if allowed == "stop" else len(allowed),
        }

    states = [state("now", entries)]
    stream = list(entries)
    steps = min(walk, max(0, (granted - w.units_spent(stream)) // cost))
    for minute_label, pool in oracle.open_traces(world, entries)[:steps]:
        stream = w.extend(world, stream, [(minute_label, pool)])
        states.append(state(f"after {minute_label} {pool}", stream))


    filler = list(entries)
    burnable = _burnable(world, entries)
    index = 0
    while burnable and w.units_spent(filler) + cost <= granted:
        filler = w.extend(world, filler, [burnable[index % len(burnable)]],
                          [f"burn-{index:02d}"])
        index += 1
    states.append(state("units spent", filler))
    return states


def _burnable(world: w.World, entries: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    'Retained pool-minutes a session can pull that leave the open ones open.'

    open_set = set(oracle.open_traces(world, entries))
    found = []
    for minute in world.minutes:
        if not world.retained(minute.label):
            continue
        for pool in sorted(minute.pools):
            if (minute.label, pool) not in open_set:
                found.append((minute.label, pool))
    return found


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The September review with what it paid for, then the weeks after it.'

    rows = [{"world": CURRENT, "receipts": [dict(item) for item in live],
             "plan_base": [dict(item) for item in live], "walk": 7}]
    for world in LATER_REVIEWS:
        opened = world.open_traces()
        held = opened[:4] + ([_quiet(world)] if _quiet(world) else [])
        rows.append({
            "world": world,
            "receipts": w.ledger_with(world, held)["entries"],
            "plan_base": [],
            "walk": 3,
        })
    return rows


def _quiet(world: w.World) -> tuple[str, str] | None:
    "One retained minute where no pool spilled, as every week's ledger has one."

    for minute in world.minutes:
        if world.retained(minute.label) and not minute.spilled:
            return (minute.label, str(world.spec["pools"][0]["name"]))
    return None


def _rate_failures(world: w.World, answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    label = world.review
    total = oracle.operations(world)
    truth = oracle.truth(world)
    dashboard = max(row["error_percent"] for row in world.dashboard())
    spilled = sum(minute.spilled for minute in world.minutes)
    shared = {"review": label, "week": WEEK_LABELS.get(label, label),
              "dashboard_percent": dashboard, "spilled": spilled}

    unreadable = _unreadable_report_field(answer)
    if unreadable is not None:
        field, value = unreadable
        return [_fail("report_field_missing_or_unreadable", **shared, field=field,
                      reported=_show(value))]

    reported_operations = answer.get("operations")
    if not _near_count(reported_operations, total, total):
        told = dict(shared, reported_operations=_show(reported_operations),
                    reported_rate=_percent(answer.get("failure_rate")))
        if _near_count(reported_operations, oracle.all_receipt_operations(world), total):
            return [_fail("attempts_counted_as_operations", **told)]
        if _near_count(reported_operations, oracle.observed_operation_receipts(world), total):
            return [_fail("edge_probes_retained", **told)]
        if any(_near_count(reported_operations, value, total)
               for value in oracle.date_keyed_counts(world)):
            return [_fail("correction_keyed_on_date", **told,
                          crossover_day=str(world.spec["releases"][-1]["day"]))]
        return [_fail("window_failure_rate_disagrees", **shared, field="operations",
                      reported=_show(reported_operations))]

    reported_rate = answer.get("failure_rate")
    if not _near_rate(reported_rate, truth, oracle.TOLERANCE):
        told = dict(shared, reported_operations=_show(reported_operations),
                    reported_rate=_percent(reported_rate))
        if _near_rate(reported_rate, oracle.probe_retained_rate(world), oracle.TOLERANCE / 2):
            return [_fail("edge_probes_retained", **told)]
        if _near_rate(reported_rate, oracle.attempt_rate(world), oracle.TOLERANCE) or\
                _near_rate(reported_rate, oracle.probe_removed_attempt_rate(world),
                           oracle.TOLERANCE):
            return [_fail("attempts_counted_as_operations", **told)]
        return [_fail("window_failure_rate_disagrees", **shared, field="failure_rate",
                      reported=_percent(reported_rate))]

    reported_failed = answer.get("failed_operations")
    wanted = oracle.failed_operations(world)
    room = float(oracle.TOLERANCE) * total
    if abs(reported_failed - wanted) > room:
        return [_fail("window_failure_rate_disagrees", **shared, field="failed_operations",
                      reported=_show(reported_failed))]
    implied = reported_operations * reported_rate
    if abs(reported_failed - implied) > float(REPORT_COHERENCE_SLACK * total):
        return [_fail("window_failure_rate_disagrees", **shared, field="failed_operations",
                      reported=_show(reported_failed))]
    return []


def _range_failures(world: w.World, answer: Mapping[str, Any],
                    receipts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    label = world.review
    low, high = oracle.feasible_range(world, receipts)
    truth = oracle.truth(world)
    unresolved = len(oracle.open_traces(world, receipts)) + _unretained_open(world, receipts)
    shared = {"review": label, "week": WEEK_LABELS.get(label, label),
              "unresolved_minutes": unresolved,
              "spilled": sum(minute.spilled for minute in world.minutes)}
    bounds = answer.get("failure_rate_range")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in bounds)
        or bounds[0] > bounds[1]
        or (bounds[0] == bounds[1] and high > low)
    ):
        return [_fail("range_absent_or_zero_width", **shared, reported=_pair(bounds))]
    told = dict(shared, reported_low=_percent(bounds[0]), reported_high=_percent(bounds[1]),
                reported_range=_pair(bounds))
    first = Fraction(str(bounds[0]))
    second = Fraction(str(bounds[1]))


    reported_rate = answer.get("failure_rate")
    outside_own = (
        isinstance(reported_rate, (int, float)) and not isinstance(reported_rate, bool)
        and not (first - RANGE_SLACK <= Fraction(str(reported_rate)) <= second + RANGE_SLACK)
    )
    if outside_own and (first > truth + RANGE_SLACK or second < truth - RANGE_SLACK):
        return [_fail("range_excludes_supported_value", **told)]
    if first > low + RANGE_SLACK or second < high - RANGE_SLACK:
        return [_fail("range_narrower_than_unresolved_minutes", **told)]
    if first < low - RANGE_SLACK or second > high + RANGE_SLACK:
        return [_fail("range_wider_than_the_counters_support", **told)]
    return []


def _unretained_open(world: w.World, receipts: Sequence[Mapping[str, Any]]) -> int:
    'Pool-minutes that spilled and can no longer be pulled at any price.'

    seen = set(oracle.resolved(receipts))
    count = 0
    for minute in world.minutes:
        if world.retained(minute.label):
            continue
        for pool in world.spilling_pools(minute.label):
            if (minute.label, pool) not in seen:
                count += 1
    return count


def _invariance_failures(world: w.World, answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The same reading, on a week whose one changed fact the notebook must carry.'

    label = world.review
    mode = VARIATION_MODES[str(world.spec["variation"])]
    total = oracle.operations(world)
    truth = oracle.truth(world)
    told = {
        "review": label,
        "week": WEEK_LABELS.get(label, label),
        "reported_rate": _percent(answer.get("failure_rate")),
        "reported_operations": _show(answer.get("operations")),
        "reported_failed": _show(answer.get("failed_operations")),
        "retry_cap": world.cap,
        "crossover_day": str(world.spec["releases"][-1]["day"]),
        "stalled_share": _stalled_share(world),
        "dashboard_percent": max(row["error_percent"] for row in world.dashboard()),
    }
    unreadable = _unreadable_report_field(answer)
    if unreadable is not None:
        field, value = unreadable
        return [_fail("report_field_missing_or_unreadable", **told, field=field,
                      reported=_show(value))]
    if not _near_count(answer.get("operations"), total, total):
        return [_fail(mode, **told)]
    if not _near_rate(answer.get("failure_rate"), truth, oracle.TOLERANCE):
        return [_fail(mode, **told)]
    reported_failed = answer.get("failed_operations")
    implied = answer["operations"] * answer["failure_rate"]
    if abs(reported_failed - implied) > float(REPORT_COHERENCE_SLACK * total):
        return [_fail("later_report_fields_disagree", **told)]
    return []


def _stalled_share(world: w.World) -> str:
    "The share of that window's traffic its fleets never moved off the old client."

    share = sum(Fraction(str(fleet["share"])) for fleet in world.spec["fleets"]
                if fleet.get("moved_on") is None)
    return format(float(100 * share), ".4g")


def _ledger_failures(world: w.World, answer: Mapping[str, Any],
                     receipts: Sequence[Mapping[str, Any]],
                     ledger_error: str | None) -> list[dict[str, Any]]:
    label = world.review
    shared = {"review": label, "week": WEEK_LABELS.get(label, label)}
    if ledger_error:
        return [_fail("receipt_ledger_unreadable", **shared, reason=str(ledger_error))]
    rows = answer.get("trace_units")
    if not isinstance(rows, list):
        return [_fail("trace_units_are_not_a_ledger", **shared,
                      reported=_show(rows), paid_for=len(receipts))]
    billed = {str(item["trace_id"]): item for item in receipts}
    seen: dict[str, int] = {}
    for row in rows:
        key = str(row.get("trace_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [_fail("unit_reported_twice", **shared, trace_id=key,
                          times_reported=seen[key])]
        entry = billed.get(key)
        if entry is None:
            return [_fail("resolved_minute_without_receipt", **shared, trace_id=key,
                          minute=_show(row.get("minute")), paid_for=len(receipts))]
        if str(row.get("minute")) != str(entry["minute"]) or\
                str(row.get("pool")) != str(entry["pool"]):
            return [_fail(
                "trace_line_disagrees_with_receipt", **shared, trace_id=key,
                reported_minute=_show(row.get("minute")),
                reported_pool=_show(row.get("pool")),
                reported_probe_receipts=_show(row.get("probe_receipts")),
                reported_probe_errors=_show(row.get("probe_errors")),
            )]
        for field in ("probe_receipts", "probe_errors"):
            if row.get(field) != entry["observed"][field]:
                return [_fail(
                    "trace_line_disagrees_with_receipt", **shared, trace_id=key,
                    reported_minute=_show(row.get("minute")),
                    reported_pool=_show(row.get("pool")),
                    reported_probe_receipts=_show(row.get("probe_receipts")),
                    reported_probe_errors=_show(row.get("probe_errors")),
                )]
    for key, entry in billed.items():
        if key not in seen:
            return [_fail("receipts_unaccounted", **shared, trace_id=key,
                          minute=str(entry["minute"]), pool=str(entry["pool"]),
                          paid_for=len(receipts))]
    return []


def _plan_failures(world: w.World, state: Mapping[str, Any],
                   answer: Any) -> list[dict[str, Any]]:
    label = world.review
    allowed = state["allowed"]
    left = int(state["units_left"])
    shared = {
        "review": label,
        "week": WEEK_LABELS.get(label, label),
        "units_left": left,
        "minutes_left": int(state["open_left"]),
        "retained_from": world.retained_from(),
        "granted": int(world.spec["units_granted"]),
    }
    if not isinstance(answer, list) or not answer:
        return [_fail("plan_did_not_name_a_minute_or_a_stop", **shared,
                      reported=_show(answer))]
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                return [_fail("plan_did_not_name_a_minute_or_a_stop", **shared,
                              reported=_show(choice))]
            if allowed != "stop":
                return [_fail("stopped_with_minutes_unresolved", **shared)]
            continue
        if not isinstance(choice, dict):
            return [_fail("plan_did_not_name_a_minute_or_a_stop", **shared,
                          reported=_show(choice))]
        minute_label, pool = str(choice.get("minute")), str(choice.get("pool"))
        if allowed != "stop" and (minute_label, pool) in allowed:
            continue
        named = {**shared, "minute": minute_label, "pool": pool}
        pools = [str(entry["name"]) for entry in world.spec["pools"]]
        if pool not in pools or world.minute(minute_label) is None:
            return [_fail("plan_did_not_name_a_minute_or_a_stop", **named,
                          reported=f"{minute_label} {pool}")]
        if not world.retained(minute_label):
            return [_fail("outside_retention", **named)]
        if left < int(world.spec["unit_cost"]):
            return [_fail("exceeds_units", **named)]
        if (minute_label, pool) in state["paid"]:
            return [_fail("repeats_a_paid_minute", **named)]
        return [_fail("less_informative_than_named_minutes", **named,
                      spilled_here=int(world.minute(minute_label).pools[pool][1]))]
    return []


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (f"it was still running after {reported[len(_TIMEOUT_PHRASE):].strip()} "
                "and the console stopped it")
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the failure notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every review and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, ledger_error = live_ledger(Path(artifact_dir))
        rows = cases(entries)
        contexts: dict[str, Any] = {}
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[w.World, dict[str, Any], int]] = []
        for row in rows:
            world = row["world"]
            contexts[world.review] = world.context()
            reports.append((row, len(requests)))
            requests.append({"kind": "report", "context": world.review,
                             "receipts": row["receipts"]})
            for state in plan_states(world, row["plan_base"], walk=int(row["walk"])):
                plans.append((world, state, len(requests)))
                requests.append({"kind": "plan", "context": world.review,
                                 "receipts": state["receipts"]})
        run = PROJECT.invoke(Path(artifact_dir),
                             {"contexts": contexts, "requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"review": CURRENT.review, "units_paid_for": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the weeks"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        broke = False
        for row, index in reports:
            world, receipts = row["world"], row["receipts"]
            value, error = answer(index)
            if error is not None:
                broke = True
                stopped = _fail(
                    "candidate_process_failure", error=error, review=world.review,
                    week=WEEK_LABELS.get(world.review, world.review),
                )


                buckets = ("rate_failures", "range_failures", "ledger_failures")\
                    if world is CURRENT else\
                    ("range_failures", "ledger_failures", "invariance_failures")
                for bucket in buckets:
                    failures[bucket].append(stopped)
                continue
            report = dict(value or {})
            if world is CURRENT:
                standing = _rate_failures(world, report)
                failures["rate_failures"].extend(standing)
            else:
                standing = _invariance_failures(world, report)
                failures["invariance_failures"].extend(standing)


            failures["range_failures"].extend(_range_failures(world, report, receipts))
            failures["ledger_failures"].extend(
                _ledger_failures(world, report, receipts,
                                 ledger_error if world is CURRENT else None))
        for world, state, index in plans:
            value, error = answer(index)
            if error is not None:
                broke = True
                failures["plan_failures"].append(_fail("candidate_process_failure", error=error))
                continue
            failures["plan_failures"].extend(_plan_failures(world, state, value))

        analysis: dict[str, Any] = {
            bucket: sorted(records, key=_report_order)
            for bucket, records in failures.items()
        }
        analysis["case"] = {
            "review": CURRENT.review,
            "units_paid_for": len(entries),
            "weeks_read": len(rows),
            "notebook_stopped": broke,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a session record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    'The review evidence as it stood at the end of one past session.'

    through = str(record["through_minute"])
    context = world.context()
    context["as_of"] = str(record["as_of"])
    context["archive"]["retained_from"] = str(record["retained_from"])
    context["window"]["last_day"] = through[:10]
    context["rollup"] = [row for row in context["rollup"] if row["minute"] <= through]
    context["pool_counters"] = [row for row in context["pool_counters"]
                                if row["minute"] <= through]
    context["dashboard"] = [row for row in context["dashboard"] if row["day"] <= through[:10]]
    return context


def _record_ledger(world: w.World, record: Mapping[str, Any]) -> list[dict[str, Any]]:
    traces = [(str(minute), str(pool)) for minute, pool in record.get("traces", ())]
    ids = list(record.get("trace_ids", SPENT_IDS))[: len(traces)]
    return w.extend(world, [], traces, ids or None)


def _evening_view(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    "The last evening on that session's export, minute by minute."

    minutes = sorted({row["minute"] for row in context["rollup"]})
    if not minutes:
        return []
    day = minutes[-1][:10]
    rows: list[dict[str, Any]] = []
    for minute in minutes:
        if not minute.startswith(day):
            continue
        entry: dict[str, Any] = {"minute": minute}
        for row in context["rollup"]:
            if row["minute"] != minute:
                continue
            attempt = "op" if row["attempt"] is None else f"a{row['attempt']}"
            if row["outcome"] == "ok":
                mark = "ok"
            elif row["retryable"] is False:
                mark = "final"
            elif row["retryable"] is True:
                mark = "retry"
            else:
                mark = "error"
            entry[f"{row['client_version']}_{attempt}_{mark}"] = row["receipts"]
        spilled = sum(row["probes_spilled"] for row in context["pool_counters"]
                      if row["minute"] == minute)
        entry["probes_spilled"] = spilled
        rows.append(entry)
    return rows[-30:]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = CURRENT.context()
    entries, error = live_ledger(root)
    granted = int(CURRENT.spec["units_granted"])
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session_id", "date", "operator", "through_minute")},
        })
    return {
        "summary": (f"The {context['review']} review, its archive terms and the "
                    "working sessions on record."),
        "measurements": {
            "review": context["review"],
            "route": context["route"],
            "window": context["window"],
            "as_of": context["as_of"],
            "archive": context["archive"],
            "pools": context["pools"],
            "fleets": context["fleets"],
            "dashboard": context["dashboard"],
            "trace_units_spent": w.units_spent(entries),
            "trace_units_left": granted - w.units_spent(entries),
            "traces_on_the_ledger": [
                {"trace_id": item["trace_id"], "minute": item["minute"],
                 "pool": item["pool"], "observed": item["observed"]}
                for item in entries
            ],
            "receipt_ledger": error or "reads back in order",
            "export_files": ["service_context.json", "request_rollup.json",
                             "edge_pool_counters.json"],
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's operator ran it."

    record = _record(record_path)
    context = snapshot(CURRENT, record)
    receipts = _record_ledger(CURRENT, record)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"contexts": {CURRENT.review: context},
         "requests": [
             {"kind": "report", "context": CURRENT.review, "receipts": receipts},
             {"kind": "plan", "context": CURRENT.review, "receipts": receipts},
         ]},
    )
    session = {
        "session_id": record.get("session_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_minute"),
        "archive_retained_from": record.get("retained_from"),
        "traces_on_the_ledger": [
            {"trace_id": item["trace_id"], "minute": item["minute"], "pool": item["pool"],
             "observed": item["observed"], "units": item["units"]}
            for item in receipts
        ],
        "dashboard": context["dashboard"],
        "last_evening_by_minute": _evening_view(context),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "review": context["review"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "review": context["review"],
            "window": context["window"],
            "as_of": context["as_of"],
            "trace_units_spent": w.units_spent(receipts),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_trace_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_trace(artifact_dir: Path, minute_label: Any, pool: Any,
              trace_id: Any) -> Mapping[str, Any]:
    outcome = w.collect(Path(artifact_dir), CURRENT, minute_label, pool, trace_id)
    receipt = dict(outcome["receipt"])
    return dict(outcome, rows=CURRENT.edge_rows(receipt["minute"], receipt["pool"]))


def starting_ledger() -> dict[str, Any]:
    'The ledger the review starts from: the five units earlier sessions bought.'

    return w.ledger_with(CURRENT, list(SPENT_TRACES), list(SPENT_IDS))
