'Read one delivered campaign notebook against the markets it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import CANDIDATE_FAILURE, failed_analysis

from . import checks, desk, oracle, publish, workload
from . import world as w
from .checks import (
    BUCKETS,
    FAILURE_MODES,
    _fail,
    _number,
    _pair,
    _points,
    _published_width,
    _show,
)
from .publish import (
    CACHE as _CACHE,
    EDITABLE_FILES,
    MARKET,
    PROJECT,
    TASK_ROOT,
    live_receipts,
    public_replay,
    public_status,
    run_review,
    snapshot,
    starting_receipts,
)


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "effect_failures": ("effect_wrong_on_another_market",),
    "range_failures": ("range_wrong_on_another_market",),
    "plan_failures": (
        "review_wrong_on_another_market",
        "review_elsewhere_after_the_range_is_made",
    ),
    "receipt_failures": ("receipts_wrong_on_another_market",),
}


CARRY_OVER_BY_KIND: Mapping[str, str] = {
    "review_after_the_range_is_made": "review_elsewhere_after_the_range_is_made",
}


CARRIED_FIELDS: tuple[str, ...] = ("files_left", "range_bar_points")

_CASE_LABELS: Mapping[str, str] = {
    "northgate": "Northgate",
    "westmoor": "Westmoor",
    "fairholm": "Fairholm",
    "lindale": "Lindale",
    "easthaven": "Easthaven",
    "northgate-batch-redrawn": "the Northgate refresh-batch reissue",
    "northgate-stop-moved": "the Northgate earlier-export reissue",
}

_KIND_LABELS: Mapping[str, str] = {
    "uses_whole_book": "the effect was read from the whole book",
    "includes_carried_accounts": "carried accounts entered the effect",
    "splits_on_register_score": "today's standing score set the sides",
    "keeps_credited_band": "manager-credited accounts entered the effect",
    "counts_orders_not_account_days": "orders were counted without their watched time",
    "effect_disagrees": "the effect disagreed with the independent reconstruction",
    "range_absent": "the range was absent or unreadable",
    "effect_outside_range": "the printed effect sat outside its range",
    "account_days_absent": "the account-days were absent or unreadable",
    "account_days_disagree": "the account-days did not reconcile to the rows",
    "range_below_floor": "the range was tighter than its evidence supports",
    "range_wider_than_the_evidence": "the range was wider than its evidence supports",
    "range_undercovers": "the range did not hold across the validation cases",
    "review_is_not_a_lot_or_a_stop": "the answer was neither a usable lot nor stop",
    "review_over_cap": "the lot exceeded one booking",
    "review_one_side_of_the_cut": "the lot put too many files on one side",
    "review_band_empty": "the lot's band had no files on one side",
    "review_over_grant": "the lot exceeded the files left",
    "review_below_the_smallest_lot": "the lot was too small for the desk",
    "review_outside_the_band": "the lot returned files outside the reading",
    "review_adds_no_observation": "the lot added no observed account-days",
    "review_after_the_range_is_made": "the plan kept buying after the stopping point",
    "stopped_with_files_in_hand": "the plan stopped before the stopping point",
    "lots_are_not_a_ledger": "the receipt ledger was absent or unreadable",
    "receipt_missing": "a charged receipt was missing",
    "refusal_uncounted": "a charged refusal was missing",
    "lot_not_on_the_receipts": "a reported lot did not match the receipts",
    "lot_counted_twice": "one receipt was counted twice",
}


def _case_label(market: str) -> str:
    return _CASE_LABELS.get(str(market), str(market).replace("-", " ").title())


def _carried_detail(record: Mapping[str, Any]) -> str:
    'One human-facing failure category plus a delivered measurement.'

    kind = str(record.get("kind"))
    summary = _KIND_LABELS.get(kind, "the case did not reconcile")
    if "reported_points" in record:
        return f"{summary}; the notebook printed {record['reported_points']} points"
    if "reported_range" in record:
        return f"{summary}; the printed range was {record['reported_range']}"
    if "reported_account_days" in record:
        return f"{summary}; it printed {record['reported_account_days']} account-days"
    if "receipt_id" in record:
        return f"{summary}; the receipt involved was {record['receipt_id']}"
    if "files" in record and "week" in record:
        return f"{summary}; it asked for {record['files']} files from week {record['week']}"
    if "reported" in record:
        return f"{summary}; the notebook returned {_show(record['reported'])}"
    return summary


_NAMING_ORDER: tuple[str, ...] = tuple(
    market.market
    for market in (*workload.SIBLINGS, *workload.REISSUES, workload.OUT_OF_REGIME)
)


def _naming_rank(market: str) -> int:
    return _NAMING_ORDER.index(market) if market in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident the growth lead can open files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("market") == MARKET else 1,
    )


def _written_off_the_live_market(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the campaign the growth lead can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("market") == MARKET
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    named = min(
        (record for record in rows if record.get("market")),
        key=lambda record: _naming_rank(str(record["market"])),
        default=rows[0],
    )
    elsewhere = sorted({str(record["market"]) for record in rows if record.get("market")})
    carried = {
        "market": MARKET,
        "other_market": str(named.get("market")),
        "other_case": _case_label(str(named.get("market"))),
        "other_markets": len(elsewhere),
        "source_kind": str(named.get("kind")),
        "case_detail": _carried_detail(named),
    }
    for field in CARRIED_FIELDS:
        if field in named:
            carried[field] = named[field]
    mode = CARRY_OVER_BY_KIND.get(str(named.get("kind")), modes[0])
    return [_fail(mode if mode in modes else modes[0], **carried)]


def _extra_lot(market: w.Market, entries: Sequence[Mapping[str, Any]], call: Mapping[str, Any]):
    grown = [dict(item) for item in entries]
    grown.append(desk._charge(market, grown, call))
    return grown


def spent_receipts(market: w.Market) -> list[dict[str, Any]]:
    'The grant run down until the files left cannot buy the smallest lot.'

    entries = desk.opening_receipts(market)
    week = max(1, int(market.spec["run_weeks"]) // 2)
    band = float(market.spec["band_points"])
    number = 0
    while market.files_left(entries) >= int(market.spec["smallest_lot"]):
        number += 1
        entries = _extra_lot(
            market,
            entries,
            {
                "receipt_id": f"{market.spec['account_prefix']}-fill-{number:02d}",
                "week": week,
                "band": band,
                "above_share": 0.5,
                "files": min(
                    int(market.spec["files_per_booking"]), market.files_left(entries)
                ),
            },
        )
    return entries


def refused_receipts(market: w.Market) -> list[dict[str, Any]]:
    'The grant with one refused lot charged against it, receipt and all.'

    entries = desk.opening_receipts(market)
    return _extra_lot(
        market,
        entries,
        {
            "receipt_id": f"{market.spec['account_prefix']}-refused",
            "week": 1,
            "band": 2.0,
            "above_share": 0.85,
            "files": 60,
        },
    )


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Northgate as this delivery left it, then the markets that follow it.'

    live = workload.CURRENT
    rows: list[dict[str, Any]] = [
        {
            "market": live,
            "receipts": [dict(item) for item in entries],
            "plans": [
                {"market": live, "receipts": [dict(item) for item in entries],
                 "plan_state": "the campaign as delivered"},
                {"market": live, "receipts": refused_receipts(live),
                 "plan_state": "the refusal contingency"},
                {"market": live, "receipts": spent_receipts(live),
                 "plan_state": "the spent-grant contingency"},
            ],
        }
    ]
    for market in (*workload.SIBLINGS, *workload.REISSUES, workload.OUT_OF_REGIME):
        opening = desk.opening_receipts(market)
        rows.append(
            {
                "market": market,
                "receipts": opening,
                "plans": [{"market": market, "receipts": opening,
                           "plan_state": "that market's opening grant"}],
            }
        )
    return rows


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (
            "it was still running after "
            f"{reported[len(_TIMEOUT_PHRASE):].strip()} and the console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the campaign notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every market and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipt_error = live_receipts(Path(artifact_dir))
        rows = instances(entries)
        contexts: list[dict[str, Any]] = []
        seen: dict[str, int] = {}

        def context_index(market: w.Market) -> int:
            if market.market not in seen:
                seen[market.market] = len(contexts)
                contexts.append(market.context())
            return seen[market.market]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[Mapping[str, Any], int, bool]] = []
        plans: list[tuple[Mapping[str, Any], int, int]] = []
        for row in rows:
            for state_index, state in enumerate(row["plans"]):
                report_index = len(requests)
                reports.append((state, report_index, state_index == 0))
                requests.append(
                    {"kind": "report", "context": context_index(state["market"]),
                     "receipts": state["receipts"]}
                )
                plans.append((state, len(requests), report_index))
                requests.append(
                    {"kind": "plan", "context": context_index(state["market"]),
                     "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            for bucket in BUCKETS.values():
                for record in analysis.get(bucket, ()):
                    record["scope"] = "the whole council batch"
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"market": MARKET, "lots_charged": len(entries)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the markets"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = checks.Review()
        readings: dict[str, float] = {}
        markets: dict[str, w.Market] = {}
        widths: dict[int, float | None] = {}
        for row, index, primary in reports:
            value, _error = answer(index)
            report = dict(value or {}) if value else {}
            reading = _number(report.get("offer_effect_points")) if report else None
            if primary and reading is not None:
                readings[row["market"].market] = reading
                markets[row["market"].market] = row["market"]
            widths[index] = _published_width(report) if report else None
        mode = checks.explanation(readings, markets)
        held: list[bool] = []
        stopped = False
        for row, index, primary in reports:
            market = row["market"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("effect_failures", "range_failures", "receipt_failures",
                    "stability_failures"),
                    error,
                    market.market,
                )
                continue
            report = dict(value or {})
            checks._check_effect(review, market, report, mode)
            range_held = checks._check_range(
                review, market, row["receipts"], report
            )
            if primary:
                held.append(range_held)
            checks._check_receipts(
                review, market, report, row["receipts"],
                receipt_error if market.market == MARKET else None,
            )
        if receipt_error is None:
            checks._check_review_history(review, workload.CURRENT, entries)
        for state, index, report_index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        error=error,
                        scope=(
                            f"{_case_label(state['market'].market)} in "
                            f"{state['plan_state']}"
                        ),
                    )
                )
                continue
            checks._check_plan(
                review, state["market"], state["receipts"], value,
                widths.get(report_index),
                plan_state=str(state["plan_state"]),
            )
        if held and sum(held) < oracle.COVERAGE * len(held):
            for row, index, primary in reports:
                if not primary:
                    continue
                value, error = answer(index)
                if error is not None:
                    continue
                window = dict(value or {}).get("effect_range_points")
                truth = oracle.truth(row["market"])
                if (
                    isinstance(window, list)
                    and len(window) == 2
                    and all(_number(item) is not None for item in window)
                    and not (float(window[0]) <= truth <= float(window[1]))
                ):
                    review.add(
                        "range_failures",
                        "range_undercovers",
                        market=row["market"].market,
                        reported_range=_pair(window),
                        markets_reviewed=len(held),
                        markets_held=sum(held),
                    )
        checks._check_stability(review, readings)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_market(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "market": MARKET,
            "lots_charged": len(entries),
            "markets_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
