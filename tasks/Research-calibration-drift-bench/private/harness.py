'Read one delivered qualification notebook against the bench it is a report of.'

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
    failed_analysis,
)

from . import oracle
from . import world as w
from .workload import (
    CURRENT,
    INVARIANCE,
    OUT_OF_REGIME,
    REPORT_PROBES,
    SIBLINGS,
    SPENT_IDS,
    SPENT_RUNS,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
CAMPAIGN = CURRENT.campaign
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-wearbench-",
    timeout=60.0,
)
_CACHE = AnalysisCache()

BUCKETS: Mapping[str, str] = {
    "wear_rate_ratio": "ratio_failures",
    "correction_survives_the_bench_schedule": "invariance_failures",
    "ratio_range_is_honest": "range_failures",
    "report_reconciles_with_the_receipts": "ledger_failures",
    "next_bench_booking": "plan_failures",
}


READING_SLACK = 5e-4


DECOY_SLACK = 0.012

COMPARISON_RESPONSE_SLACK = 1e-6


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(float(value)) else None


def _relative(left: float, right: float) -> float:
    return abs(left - right) / abs(right)


def _percent(value: float) -> str:
    return format(100.0 * float(value), ".1f")


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, (list, tuple)):
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{value[0]:.3f} to {value[1]:.3f}"
    return _show(value)


def starting_stream() -> dict[str, Any]:
    "The receipt stream the campaign starts from: the technician's two checks."

    return w.stream_with(CURRENT, SPENT_RUNS, SPENT_IDS)


def live_stream(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The sessions this delivery paid for, or the reason the stream will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def _same_sessions(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "Run the receipt stream's sessions unchanged on another bench schedule."

    bookings = [
        {
            "rig": entry["rig"],
            "part": entry.get("part"),
            "reference_block": entry.get("part") is None,
            "cycles": entry.get("cycles"),
        }
        for entry in entries
    ]
    return w.stream_with(
        campaign, bookings, [str(entry["run_id"]) for entry in entries]
    )["entries"]


def _store_split(campaign: w.Campaign) -> tuple[list[str], list[str]]:
    parts = [str(item["part"]) for item in campaign.spec["stores"]]
    return ([item for item in parts if item.startswith("A")],
            [item for item in parts if item.startswith("B")])


def _receipt_influence_pair(campaign: w.Campaign) -> dict[str, Any]:
    'Two sealed streams that differ only in one informative part reading.'

    entries = w.stream_with(campaign, SPENT_RUNS, SPENT_IDS)["entries"]
    choice = None
    for item in campaign.spec["stores"]:
        rigs = {
            int(row["rig"]) for row in campaign.sessions()
            if str(row["lot"]) == str(item["lot"])
        }
        if len(rigs) != 1:
            continue
        rig = 2 if 1 in rigs else 1
        if w.rig_hours_left(campaign, entries, rig) >= campaign.hours_for(w.PART_RUN):
            choice = (dict(item), rig)
            break
    if choice is None:
        raise ValueError("the receipt influence check needs one cross-rig spare")

    item, rig = choice
    run_id = "receipt-use-check"
    body = w.run_session(campaign, entries, rig, item["part"], None, None)
    changed = copy.deepcopy(body)
    reading_before = float(body["observed"]["reading_um"])
    reading_after = round(1.2 * reading_before, 3)
    changed["observed"]["reading_um"] = reading_after
    sequence = len(entries) + 1
    previous = str(entries[-1]["seal"]) if entries else ""
    return {
        "campaign": campaign,
        "run_id": run_id,
        "reading_before": reading_before,
        "reading_after": reading_after,
        "before": entries + [w.receipt(campaign, body, run_id, sequence, previous)],
        "after": entries + [w.receipt(campaign, changed, run_id, sequence, previous)],
    }


def _state(campaign: w.Campaign, label: str, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stop_is_right = (
        oracle.best_fixture_error(campaign, entries)
        >= oracle.standing_fixture_error(campaign, entries) - 1e-9
    )
    return {
        "label": label,
        "campaign": campaign,
        "receipts": [dict(entry) for entry in entries],
        "hours_left": w.hours_left(campaign, entries),
        "rig_hours_left": {rig: w.rig_hours_left(campaign, entries, rig) for rig in w.RIGS},
        "parts_left": [
            str(item["part"]) for item in campaign.spec["stores"]
            if str(item["part"]) not in {str(entry.get("part")) for entry in entries}
        ],
        "bar": oracle.plan_bar(campaign, entries),
        "standing": oracle.standing_fixture_error(campaign, entries),
        "stop_is_right": bool(stop_is_right),
    }


def plan_states(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every state the bench booking can be asked for in, on one campaign.'

    cost = campaign.hours_for(w.PART_RUN)
    used = {str(entry.get("part")) for entry in entries if entry.get("part")}
    stored_a, stored_b = (
        [part for part in side if part not in used] for side in _store_split(campaign)
    )

    def grown(bookings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        'The stream this campaign would hold after running those sessions.'

        stream = [dict(entry) for entry in entries]
        for booking in bookings:
            if w.hours_left(campaign, stream) < cost:
                break
            if w.rig_hours_left(campaign, stream, int(booking["rig"])) < cost:
                continue
            stream = w.extend(campaign, stream, [booking])
        return stream

    live = _state(campaign, "open", entries)
    initial = w.stream_with(campaign, SPENT_RUNS, SPENT_IDS)["entries"]


    live["bar"] = oracle.plan_bar(campaign, initial)
    states = [live]
    if stored_a and stored_b:
        states.append(_state(campaign, "two sessions in", grown([
            {"rig": 2, "part": stored_a[0]}, {"rig": 1, "part": stored_b[0]},
        ])))
    rig_two_cap = int(max(0.0, w.rig_hours_left(campaign, entries, 2)) // cost)
    filled = grown([{"rig": 2, "part": part} for part in stored_a[:rig_two_cap]])
    if w.rig_hours_left(campaign, filled, 2) < cost:
        states.append(_state(campaign, "second rig booked out", filled))
    spent = grown(
        [{"rig": 2, "part": part} for part in stored_a[:rig_two_cap]]
        + [{"rig": 1, "part": part} for part in stored_a[rig_two_cap:] + stored_b]
    )
    if w.hours_spent(spent) > w.hours_spent(entries):
        states.append(_state(campaign, "hours spent", spent))
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'Every campaign state the delivered notebook is read on.'

    reports = [{"campaign": CURRENT, "receipts": [dict(item) for item in live],
                "visible": True, "family": None}]
    for campaign in (*SIBLINGS, OUT_OF_REGIME, *REPORT_PROBES):
        reports.append({
            "campaign": campaign,
            "receipts": w.stream_with(campaign, SPENT_RUNS, SPENT_IDS)["entries"],
            "visible": False,
            "family": None,
        })
    family = []
    for reason, members in INVARIANCE.items():
        for campaign in members:
            family.append({
                "campaign": campaign,
                "receipts": _same_sessions(campaign, live),
                "visible": False,
                "family": reason,
            })
    plans = plan_states(CURRENT, live)
    for campaign in SIBLINGS:
        plans.append(_state(campaign, "open",
                            w.stream_with(campaign, SPENT_RUNS, SPENT_IDS)["entries"]))
    return {
        "reports": reports,
        "family": family,
        "receipt_probes": [_receipt_influence_pair(CURRENT)],
        "plans": plans,
    }


def _ratio_failures(campaign: w.Campaign, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    wanted = oracle.truth(campaign)
    reported = _number(report.get("wear_rate_ratio"))
    shared = {"campaign": campaign.campaign}


    if reported is None or reported <= 0:
        return [_fail("no_ratio_reported", **shared,
                      reported=_show(report.get("wear_rate_ratio")))]
    if _relative(reported, wanted) <= oracle.RATIO_TOLERANCE:
        return []
    told = {**shared, "reported_ratio": format(reported, ".3f"),
            "apart": _percent(reported - 1.0)}


    if campaign.campaign != CAMPAIGN:
        return [_fail("ratio_does_not_hold_on_the_other_qualifications", **told)]
    decoys = oracle.decoy_ratios(campaign)
    named = {
        "raw": "ratio_reported_in_raw_depth",
        "drift_only": "ratio_carries_the_fixture_difference",
        "no_gain": "ratio_carries_uncorrected_drift",
        "rig_constant": "ratio_carries_uncorrected_drift",
        "zero_offset": "ratio_takes_the_drift_off_as_a_fixed_amount",
    }


    matched = {mode for key, mode in named.items()
               if _relative(reported, decoys[key]) <= DECOY_SLACK}
    if len(matched) == 1:
        return [_fail(matched.pop(), **told)]
    return [_fail("ratio_disagrees_with_the_bench", **told,
                  reported=format(reported, ".3f"))]


def _range_failures(campaign: w.Campaign, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    floor = oracle.interval_floor(campaign)
    wanted = oracle.truth(campaign)
    shared = {"campaign": campaign.campaign, "lots": len(campaign.lots)}
    reported = report.get("ratio_range")
    if reported is None:
        return [_fail("no_range_reported", **shared, reported="empty")]
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None or _number(item) <= 0 for item in reported)
        or float(reported[0]) > float(reported[1])
    ):
        return [_fail("range_is_not_an_interval", **shared, reported=_pair(reported))]
    low, high = float(reported[0]), float(reported[1])
    width = math.log(high / low)
    told = {**shared, "reported_range": _pair([low, high]),
            "reported_width": _percent(high / low - 1.0)}
    point = _number(report.get("wear_rate_ratio"))
    if point is not None and point > 0 and not low <= point <= high:
        return [_fail("range_does_not_hold_the_reported_ratio", **told,
                      reported_ratio=format(point, ".3f"))]
    if width < oracle.FLOOR_SHARE * floor:
        return [_fail("range_narrower_than_the_lots_support", **told)]
    if width > oracle.CEILING_MULTIPLE * floor:
        return [_fail("range_wider_than_the_lots_support", **told)]
    if not low <= wanted <= high:
        missed_side = "below the lower end" if wanted < low else "above the upper end"
        return [_fail("range_misses_the_wear_rate", **told, missed_side=missed_side)]
    return []


def _ledger_failures(
    campaign: w.Campaign,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    stream_error: str | None,
) -> list[dict[str, Any]]:
    shared = {"campaign": campaign.campaign, "paid_for": len(receipts)}
    if stream_error:
        return [_fail("receipt_stream_unreadable", **shared, reason=str(stream_error))]
    rows = report.get("measurements")
    if not isinstance(rows, list):
        return [_fail("measurements_are_not_a_ledger", **shared,
                      reported=_show(rows))]
    billed = {str(item["run_id"]): item for item in receipts}
    seen: dict[str, int] = {}
    first_duplicate: dict[str, Any] | None = None
    first_unmatched: dict[str, Any] | None = None
    for row in rows:
        key = str(row.get("run_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1 and first_duplicate is None:
            first_duplicate = _fail(
                "session_reported_twice", **shared, run_id=key,
                times_reported=seen[key],
            )
        entry = billed.get(key)
        if entry is None:
            if first_unmatched is None:
                first_unmatched = _fail(
                    "session_not_on_the_receipt_stream", **shared, run_id=key)
            continue
        reading = _number(row.get("reading_um"))
        if (
            str(row.get("rig")) != str(entry["rig"])
            or str(row.get("kind")) != str(entry["observed"]["kind"])
            or reading is None
            or abs(reading - float(entry["observed"]["reading_um"])) > READING_SLACK
        ):
            if first_unmatched is None:
                first_unmatched = _fail(
                    "session_not_on_the_receipt_stream", **shared, run_id=key)
    for key, entry in billed.items():
        if key not in seen:
            return [_fail("paid_session_missing_from_the_report", **shared, run_id=key,
                          rig=int(entry["rig"]),
                          ran=str(entry["observed"]["kind"]))]
    if first_unmatched is not None:
        return [first_unmatched]
    if first_duplicate is not None:
        return [first_duplicate]
    return _count_failures(campaign, report, receipts, shared)


def _count_failures(
    campaign: w.Campaign,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    shared: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected = {
        supplier: sum(1 for row in campaign.sessions() if str(row["supplier"]) == supplier)
        + sum(1 for entry in receipts
              if entry["observed"]["kind"] == w.PART_RUN and str(entry["supplier"]) == supplier)
        for supplier in w.SUPPLIERS
    }
    references = sum(1 for entry in receipts if entry["observed"]["kind"] == w.REFERENCE_RUN)
    used = report.get("sessions_used")
    if not isinstance(used, dict) or any(
        not isinstance(used.get(supplier), int) for supplier in w.SUPPLIERS
    ):
        return [_fail("session_counts_disagree_with_the_table", **shared,
                      reported=_show(used), supplier="A", counted=expected["A"])]
    for supplier in w.SUPPLIERS:
        reported = int(used[supplier])
        if reported == expected[supplier]:
            continue
        told = {**shared, "supplier": supplier, "reported": reported,
                "counted": expected[supplier]}
        if references and reported == expected[supplier] + references:
            return [_fail("reference_run_counted_as_a_part_session", **told,
                          reference_runs=references)]
        return [_fail("session_counts_disagree_with_the_table", **told)]
    total = sum(int(used[supplier]) for supplier in w.SUPPLIERS)
    if references and total == sum(expected.values()) + references:
        return [_fail("reference_run_counted_as_a_part_session", **shared, supplier="A",
                      reported=total, counted=sum(expected.values()),
                      reference_runs=references)]
    return []


def _receipt_influence_failures(
    probe: Mapping[str, Any], before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'A valid bridge-part reading must reach the comparison it is counted behind.'

    first = _number(before.get("wear_rate_ratio"))
    second = _number(after.get("wear_rate_ratio"))
    if first is None or second is None:
        return []
    if not math.isclose(
        first, second, rel_tol=COMPARISON_RESPONSE_SLACK,
        abs_tol=COMPARISON_RESPONSE_SLACK,
    ):
        return []
    return [_fail(
        "part_receipts_do_not_reach_the_comparison",
        campaign=probe["campaign"].campaign,
        run_id=str(probe["run_id"]),
        reading_before=format(float(probe["reading_before"]), ".3f"),
        reading_after=format(float(probe["reading_after"]), ".3f"),
        reported_ratio=format(first, ".4g"),
    )]


def _invariance_failures(
    base: float | None, family: Sequence[tuple[str, float | None]]
) -> list[dict[str, Any]]:
    'The delivered ratio has to be the same number on every re-run of the bench.'

    named = {
        "drift_rate": "estimate_moves_with_drift_rate",
        "assignment": "estimate_moves_with_assignment_imbalance",
        "calibration_spacing": "correction_keyed_to_rig_identity",
    }


    ranked: list[tuple[float, dict[str, Any]]] = []
    for reason, mode in named.items():
        values = [base] + [value for label, value in family if label == reason]
        readable = [value for value in values if value is not None and value > 0]
        if len(readable) != len(values):
            ranked.append((float("inf"), _fail(mode, reported=_show(base),
                                               moved_to="empty", moved_by="100.0")))
            continue
        low, high = min(readable), max(readable)
        moved = (high - low) / low
        if moved > oracle.INVARIANCE_TOLERANCE:
            other = low if base is not None and abs(base - high) < abs(base - low) else high
            ranked.append((moved, _fail(mode, reported=format(base or high, ".3f"),
                                        moved_to=format(other, ".3f"),
                                        moved_by=_percent(moved))))
    if not ranked:
        return []
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [ranked[0][1]]


def _plan_failures(state: Mapping[str, Any], answer: Any) -> list[dict[str, Any]]:
    campaign: w.Campaign = state["campaign"]
    shared = {
        "campaign": campaign.campaign,


        "bench_state": str(state["label"]),
        "hours_left": format(float(state["hours_left"]), ".1f"),
        "second_rig_hours": format(float(state["rig_hours_left"][2]), ".1f"),
        "parts_left": len(state["parts_left"]),
    }
    if not isinstance(answer, list) or not answer:
        return [_fail("plan_is_not_a_bookable_session", **shared, reported=_show(answer))]
    if "stop" in answer and answer != ["stop"]:
        return [_fail("plan_is_not_a_bookable_session", **shared, reported=_show(answer))]
    part_cost = campaign.hours_for(w.PART_RUN)
    reference_cost = campaign.hours_for(w.REFERENCE_RUN)
    hours = 0.0
    rig_hours = {rig: 0.0 for rig in w.RIGS}
    booked: list[dict[str, Any]] = []
    taken: set[str] = set()
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                return [_fail("plan_is_not_a_bookable_session", **shared,
                              reported=_show(choice))]
            if not state["stop_is_right"]:
                return [_fail("stopped_with_hours_and_parts_in_hand", **shared)]
            continue
        if not isinstance(choice, dict):
            return [_fail("plan_is_not_a_bookable_session", **shared, reported=_show(choice))]
        rig = choice.get("rig")
        rig = int(rig) if str(rig) in {"1", "2"} else None
        part = choice.get("part")
        part = str(part) if isinstance(part, str) and part.strip() else None
        if rig is None or (part is None and not choice.get("reference_block")):
            return [_fail("plan_is_not_a_bookable_session", **shared, reported=_show(choice))]
        if part is not None:
            if part not in state["parts_left"] or part in taken:
                return [_fail("plan_books_a_part_stores_does_not_hold", **shared, part=part)]
            taken.add(part)
            booked.append({"rig": rig, "part": part})
            cost = part_cost
        else:
            cost = reference_cost
        hours += cost
        rig_hours[rig] += cost
    if hours > float(state["hours_left"]) + 1e-9:
        return [_fail("plan_exceeds_bench_hours", **shared,
                      booked_hours=format(hours, ".1f"))]
    for rig in w.RIGS:
        if rig_hours[rig] > float(state["rig_hours_left"][rig]) + 1e-9:
            return [_fail("plan_books_a_rig_that_is_not_open", **shared, rig=rig,
                          booked_hours=format(rig_hours[rig], ".1f"),
                          rig_hours=format(float(state["rig_hours_left"][rig]), ".1f"))]


    if not booked:
        if (
            answer == ["stop"]
            and state["stop_is_right"]
            and float(state["standing"]) <= float(state["bar"]) + 1e-9
        ):
            return []
        return [_fail("plan_leaves_the_two_rigs_uncompared", **shared, booked_sessions=0)]
    reached = oracle.plan_fixture_error(campaign, state["receipts"], booked)
    if reached > float(state["bar"]) + 1e-9:
        return [_fail("plan_leaves_the_two_rigs_uncompared", **shared,
                      booked_sessions=len(booked))]
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
    return f"the qualification notebook stopped part way through: {line[:200]}"


LIVE_STATE = "open"


def _report_order(record: Mapping[str, Any]) -> int:
    'How far the bench an incident was found on is from the one Dana holds.'

    if str(record.get("kind")) == CANDIDATE_FAILURE:
        return 0
    mine = record.get("campaign") in (None, CAMPAIGN)
    live = record.get("bench_state") in (None, LIVE_STATE)
    if mine and live:
        return 1
    return 2 if live else 3


def _reportable(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "One check's incidents, with only the nearest bench left to report from."

    ordered = [dict(record) for record in sorted(records, key=_report_order)]
    if not ordered:
        return ordered
    nearest = _report_order(ordered[0])
    return [record for record in ordered if _report_order(record) == nearest]


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every campaign and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, stream_error = live_stream(Path(artifact_dir))
        plan = cases(entries)
        requests: list[dict[str, Any]] = []
        report_index: list[tuple[Mapping[str, Any], int]] = []
        family_index: list[tuple[Mapping[str, Any], int]] = []
        receipt_probe_index: list[tuple[Mapping[str, Any], int, int]] = []
        plan_index: list[tuple[Mapping[str, Any], int]] = []
        for row in plan["reports"]:
            report_index.append((row, len(requests)))
            requests.append({"kind": "report", "context": row["campaign"].context(),
                             "receipts": row["receipts"]})
        for row in plan["family"]:
            family_index.append((row, len(requests)))
            requests.append({"kind": "report", "context": row["campaign"].context(),
                             "receipts": row["receipts"]})
        for row in plan["receipt_probes"]:
            before = len(requests)
            requests.append({"kind": "report", "context": row["campaign"].context(),
                             "receipts": row["before"]})
            after = len(requests)
            requests.append({"kind": "report", "context": row["campaign"].context(),
                             "receipts": row["after"]})
            receipt_probe_index.append((row, before, after))
        for state in plan["plans"]:
            plan_index.append((state, len(requests)))
            requests.append({"kind": "plan", "context": state["campaign"].context(),
                             "receipts": state["receipts"]})
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CAMPAIGN, "sessions_paid_for": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the campaigns"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        broke = False
        base_ratio: float | None = None
        for row, index in report_index:
            campaign = row["campaign"]
            value, error = answer(index)
            if error is not None:
                broke = True
                for bucket in ("ratio_failures", "range_failures", "ledger_failures"):
                    failures[bucket].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            if campaign is CURRENT:
                base_ratio = _number(report.get("wear_rate_ratio"))
            failures["ratio_failures"].extend(_ratio_failures(campaign, report))
            failures["range_failures"].extend(_range_failures(campaign, report))
            failures["ledger_failures"].extend(
                _ledger_failures(campaign, report, row["receipts"],
                                 stream_error if campaign is CURRENT else None))
        family: list[tuple[str, float | None]] = []
        for row, index in family_index:
            value, error = answer(index)
            if error is not None:
                broke = True
                for bucket in ("invariance_failures", "range_failures", "ledger_failures"):
                    failures[bucket].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            family.append((str(row["family"]), _number(report.get("wear_rate_ratio"))))
            failures["range_failures"].extend(_range_failures(row["campaign"], report))
            failures["ledger_failures"].extend(
                _ledger_failures(row["campaign"], report, row["receipts"], None))
        if family and not any(
            item["kind"] == CANDIDATE_FAILURE for item in failures["invariance_failures"]
        ):
            failures["invariance_failures"].extend(_invariance_failures(base_ratio, family))
        for row, before_index, after_index in receipt_probe_index:
            before, before_error = answer(before_index)
            after, after_error = answer(after_index)
            if before_error is not None or after_error is not None:
                broke = True
                failures["ledger_failures"].append(_fail(
                    CANDIDATE_FAILURE,
                    error=before_error or after_error or "the notebook stopped",
                ))
                continue
            failures["ledger_failures"].extend(_receipt_influence_failures(
                row, dict(before or {}), dict(after or {})))
        for state, index in plan_index:
            value, error = answer(index)
            if error is not None:
                broke = True
                failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            failures["plan_failures"].extend(_plan_failures(state, value))

        analysis: dict[str, Any] = {
            bucket: _reportable(records) for bucket, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CAMPAIGN,
            "sessions_paid_for": len(entries),
            "campaigns_read": (
                len(report_index) + len(family_index) + 2 * len(receipt_probe_index)
            ),
            "notebook_stopped": broke,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working-session record must contain a JSON object")
    return raw


def snapshot(campaign: w.Campaign, record: Mapping[str, Any]) -> dict[str, Any]:
    'The campaign evidence as it stood at the end of one past working session.'

    through = int(record["through_day"])
    context = campaign.context()
    context["sessions"] = [row for row in context["sessions"] if int(row["day"]) <= through]
    context["calibrations"] = [
        row for row in context["calibrations"] if int(row["signed_off_day"]) <= through
    ]
    context["lots"] = [
        row for row in context["lots"] if int(row["arrived_day"]) <= through
    ]
    arrived = {str(row["lot"]) for row in context["lots"]}
    context["stores"] = [
        row for row in context["stores"] if str(row["lot"]) in arrived
    ]
    context["rigs"] = [
        row for row in context["rigs"] if int(row["installed_day"]) <= through
    ]
    installed = {str(row["rig"]) for row in context["rigs"]}
    context["booking"]["rig_hours_available"] = {
        rig: hours if str(rig) in installed else 0.0
        for rig, hours in context["booking"]["rig_hours_available"].items()
    }
    context["review_day"] = int(record.get("review_day", context["review_day"]))
    return context


def _record_stream(campaign: w.Campaign, record: Mapping[str, Any]) -> list[dict[str, Any]]:
    bookings = [dict(item) for item in record.get("runs", ())]
    ids = list(record.get("run_ids", ()))[: len(bookings)]
    if not bookings:
        return []
    return w.extend(campaign, [], bookings, ids or None)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = CURRENT.context()
    entries, error = live_stream(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session_id", "date", "operator", "through_day")},
        })
    return {
        "summary": (
            f"The {context['campaign']} campaign, the bench terms and the working "
            "sessions on record."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "review_day": context["review_day"],
            "rigs": context["rigs"],
            "part_sessions_on_the_table": len(context["sessions"]),
            "booking": context["booking"],
            "bench_hours_spent": w.hours_spent(entries),
            "bench_hours_left": w.hours_left(CURRENT, entries),
            "sessions_on_the_receipt_stream": [
                {"run_id": item["run_id"], "rig": item["rig"], "part": item["part"],
                 "calibration": item["calibration"], "hours": item["hours"],
                 "observed": item["observed"]}
                for item in entries
            ],
            "receipt_stream": error or "reads back in order",
            "stores": context["stores"],
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past working session's operator ran it."

    record = _record(record_path)
    context = snapshot(CURRENT, record)
    receipts = _record_stream(CURRENT, record)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": receipts},
            {"kind": "plan", "context": context, "receipts": receipts},
        ]},
    )
    session = {
        "session_id": record.get("session_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through_day": record.get("through_day"),
        "sessions_on_the_receipt_stream": [
            {"run_id": item["run_id"], "rig": item["rig"], "part": item["part"],
             "hours": item["hours"], "observed": item["observed"]}
            for item in receipts
        ],
        "session_table": [dict(row) for row in context["sessions"]],
        "calibrations": context["calibrations"],
        "lots_in_by_then": context["lots"],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name,
                             "campaign": context["campaign"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "evidence_through_day": record.get("through_day"),
            "part_sessions_on_the_table": len(context["sessions"]),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_bench(
    artifact_dir: Path, rig: Any, part: Any, reference_block: Any, cycles: Any, run_id: Any
) -> Mapping[str, Any]:
    return w.collect(Path(artifact_dir), CURRENT, rig, part, reference_block, cycles, run_id)
