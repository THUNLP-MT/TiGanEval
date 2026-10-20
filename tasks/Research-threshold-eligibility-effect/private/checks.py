'The five checks the review makes of one delivered campaign readout.'

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import CANDIDATE_FAILURE

from . import desk, oracle, workload
from . import world as w
from .publish import MARKET


BUCKETS: Mapping[str, str] = {
    "offer_effect_within_tolerance": "effect_failures",
    "range_covers_and_meets_floor": "range_failures",
    "estimate_invariant_to_recompute_and_truncation": "stability_failures",
    "next_review_feasible_and_informative": "plan_failures",
    "report_reconciles_receipts": "receipt_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "offer_effect_within_tolerance": (
        "uses_whole_book",
        "includes_carried_accounts",
        "splits_on_register_score",
        "keeps_credited_band",
        "counts_orders_not_account_days",
        "effect_disagrees",
        "effect_wrong_on_another_market",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_absent",
        "effect_outside_range",
        "account_days_absent",
        "account_days_disagree",
        "range_below_floor",
        "range_wider_than_the_evidence",
        "range_undercovers",
        "range_wrong_on_another_market",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_recompute_and_truncation": (
        "hardcoded_history",
        "moves_with_recompute_batch",
        "moves_with_export_stop",
        "candidate_execution_failed",
    ),
    "next_review_feasible_and_informative": (
        "review_grant_misspent",
        "review_is_not_a_lot_or_a_stop",
        "review_over_cap",
        "review_one_side_of_the_cut",
        "review_band_empty",
        "review_over_grant",
        "review_below_the_smallest_lot",
        "review_outside_the_band",
        "review_adds_no_observation",
        "review_after_the_range_is_made",
        "stopped_with_files_in_hand",
        "review_wrong_on_another_market",
        "review_elsewhere_after_the_range_is_made",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "lots_are_not_a_ledger",
        "receipt_missing",
        "refusal_uncounted",
        "lot_not_on_the_receipts",
        "lot_counted_twice",
        "receipts_wrong_on_another_market",
        "candidate_execution_failed",
    ),
}


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _points(value: Any) -> str:
    return format(float(value), ".2f")


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


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_points(value[0])} to {_points(value[1])}"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    read = float(value)
    return read if isfinite(read) else None


def _whole_number(value: Any) -> bool:
    read = _number(value)
    return read is not None and read.is_integer()


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str, scope: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(
                0, _fail(CANDIDATE_FAILURE, error=error, scope=scope)
            )


_MISREADINGS = (
    ("uses_whole_book", ("whole_book_flags", "whole_book_days", "no_band")),
    ("includes_carried_accounts", ("carried_included",)),
    ("splits_on_register_score", ("register_side",)),
    ("keeps_credited_band", ("credited_band_kept",)),
    ("counts_orders_not_account_days", ("order_flags",)),
)


def explanation(
    readings: Mapping[str, float], markets: Mapping[str, w.Market]
) -> str | None:
    'The one misreading that accounts for this delivery on most markets.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = sum(
            1
            for name, value in readings.items()
            if name in markets
            and any(
                _near(value, oracle.misreadings(markets[name])[family], oracle.CLASSIFY_SLACK)
                for family in families
            )
        )
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _matches_explanation(value: Any, market: w.Market, mode: str) -> bool:
    'Whether this market, not merely the delivery as a whole, fits `mode`.'

    families = next(
        (candidates for candidate, candidates in _MISREADINGS if candidate == mode),
        (),
    )
    readings = oracle.misreadings(market)
    return any(
        family in readings
        and _near(value, readings[family], oracle.CLASSIFY_SLACK)
        for family in families
    )


def _disagreeing_rows(market: w.Market) -> int:
    cut = market.cut
    return sum(
        1
        for row in market.rows
        if row["run_status"] == "scored"
        and (float(row["register_score"]) >= cut) != bool(int(row["offer_flag"]))
    )


def _credited_rows(market: w.Market) -> int:
    'Accounts the register itself shows a filed credit carrying over the line.'

    cut = market.cut
    counted = 0
    for row in market.rows:
        credit, shown = float(row["credit"]), float(row["register_score"])
        if credit > 0 and shown >= cut > shown - credit:
            counted += 1
    return counted


def _carried_rows(market: w.Market) -> int:
    return sum(1 for row in market.rows if row["run_status"] == "carried")


def _check_effect(
    review: Review, market: w.Market, report: Mapping[str, Any], mode: str | None
) -> None:
    truth = oracle.truth(market)
    reported = report.get("offer_effect_points")
    if _near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "market": market.market,
        "reported_points": (
            _points(reported) if _number(reported) is not None else _show(reported)
        ),
        "comparison_detail": (
            f"{_points(abs(float(reported) - truth))} points apart"
            if _number(reported) is not None
            else "not numerically comparable"
        ),
    }
    if (
        _number(reported) is None
        or mode is None
        or not _matches_explanation(reported, market, mode)
    ):
        review.add("effect_failures", "effect_disagrees", **shared, cut=_points(market.cut))
        return
    if mode == "uses_whole_book":


        review.add("effect_failures", mode, **shared, book_rows=len(market.rows))
    elif mode == "includes_carried_accounts":
        review.add("effect_failures", mode, **shared, carried_rows=_carried_rows(market),
                   book_rows=len(market.rows))
    elif mode == "splits_on_register_score":
        review.add("effect_failures", mode, **shared,
                   disagreeing_rows=_disagreeing_rows(market))
    elif mode == "keeps_credited_band":
        review.add("effect_failures", mode, **shared, credited_rows=_credited_rows(market),
                   credit_ceiling=_points(market.spec["credit_ceiling"]))
    else:
        review.add("effect_failures", mode, **shared,
                   export_stop_day=market.days[int(market.spec["export_stop_day"]) - 1],
                   order_window_days=int(market.spec["order_window_days"]))


def _published_width(report: Mapping[str, Any]) -> float | None:
    reported = report.get("effect_range_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or float(reported[0]) > float(reported[1])
    ):
        return None
    return (float(reported[1]) - float(reported[0])) / 2.0


def _check_range(
    review: Review,
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> bool:
    'Reconcile a range, its number and the account-days behind both.'

    width = _published_width(report)
    if width is None:
        review.add("range_failures", "range_absent", market=market.market,
                   reported=_pair(report.get("effect_range_points")))
        return True
    reported = report.get("effect_range_points")
    effect = _number(report.get("offer_effect_points"))
    if effect is None or not float(reported[0]) <= effect <= float(reported[1]):
        review.add(
            "range_failures",
            "effect_outside_range",
            market=market.market,
            reported_effect=_show(report.get("offer_effect_points")),
            reported_range=_pair(reported),
        )
    days = _number(report.get("account_days"))
    if days is None or days <= 0:
        review.add("range_failures", "account_days_absent", market=market.market,
                   reported=_show(report.get("account_days")),
                   reported_range=_pair(report.get("effect_range_points")))
        return True
    expected_days = oracle.account_days(market, receipts)
    days_slack = max(1.0, oracle.ACCOUNT_DAYS_RELATIVE_SLACK * expected_days)
    if not _near(days, expected_days, days_slack):
        review.add(
            "range_failures",
            "account_days_disagree",
            market=market.market,
            reported_account_days=_show(days),
            account_days_from_rows=int(expected_days),
            lots_charged=len(receipts),
        )
        truth = oracle.truth(market)
        return float(reported[0]) <= truth <= float(reported[1])
    supported = oracle.half_width_for_days(market, days, receipts)
    fields = {
        "market": market.market,
        "reported_range": _pair(report.get("effect_range_points")),
        "reported_account_days": _show(days),
        "markets_on_the_slide": int(market.spec["markets_on_the_slide"]),
    }
    if width < supported * oracle.NARROW_FACTOR:
        review.add("range_failures", "range_below_floor", **fields)
    elif width > supported * oracle.WIDE_FACTOR:
        review.add("range_failures", "range_wider_than_the_evidence", **fields)
    truth = oracle.truth(market)
    return float(reported[0]) <= truth <= float(reported[1])


def _check_review_history(
    review: Review,
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
) -> None:
    'Reject irreversible grant spend caused by this delivery, not opening history.'

    opening = desk.opening_receipts(market)
    for index, entry in enumerate(receipts[len(opening):], start=len(opening)):
        prior = receipts[:index]
        problem = str(entry.get("refusal") or "")
        if not problem:
            choice = {
                "week": entry.get("week"),
                "band": entry.get("band"),
                "above_share": entry.get("above_share"),
                "files": entry.get("files_charged"),
            }
            wrong = oracle.lot_ok(market, prior, choice)
            if wrong == "review_outside_the_band":
                problem = "the returned files sit outside the readout's line band"
            elif wrong == "review_adds_no_observation":
                problem = "the returned files add no observed account-days to the readout"
            elif wrong == "review_below_the_smallest_lot":
                problem = (
                    "the desk returned fewer than "
                    f"{int(market.spec['smallest_lot'])} files for the worked lot"
                )
            elif wrong is not None:
                problem = "the booking did not meet the campaign's written grant terms"
        if problem:
            review.add(
                "plan_failures",
                "review_grant_misspent",
                market=market.market,
                receipt_id=str(entry.get("receipt_id")),
                files_charged=int(entry.get("files_charged", 0)),
                rows_returned=int(entry.get("rows_returned", 0)),
                problem=problem,
            )
            return


def _check_receipts(
    review: Review,
    market: w.Market,
    report: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    error: str | None,
) -> None:
    if error:
        review.add("receipt_failures", "receipts_unreadable", market=market.market,
                   reason=str(error))
        return
    rows = report.get("lots")
    if not isinstance(rows, list):
        review.add("receipt_failures", "lots_are_not_a_ledger", market=market.market,
                   reported=_show(rows), charged=len(receipts))
        return
    charged = {str(item["receipt_id"]): item for item in receipts}
    seen: dict[str, int] = {}
    for row in rows:
        receipt_id = str(row.get("receipt_id"))
        seen[receipt_id] = seen.get(receipt_id, 0) + 1
        if seen[receipt_id] > 1:
            review.add("receipt_failures", "lot_counted_twice", market=market.market,
                       receipt_id=receipt_id, times_reported=seen[receipt_id])
            return
        entry = charged.get(receipt_id)
        if entry is None or not all(
            _near(row.get(field), float(entry[field]), 0.0)
            for field in ("files_charged", "rows_returned")
        ):
            review.add("receipt_failures", "lot_not_on_the_receipts", market=market.market,
                       receipt_id=receipt_id, charged=len(receipts))
            return
    for receipt_id, entry in charged.items():
        if receipt_id in seen:
            continue
        mode = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        review.add("receipt_failures", mode, market=market.market, receipt_id=receipt_id,
                   files_charged=int(entry["files_charged"]), charged=len(receipts))
        return


def _check_plan(
    review: Review,
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    answer: Any,
    width: float | None,
    plan_state: str = "the campaign's live grant",
) -> None:
    state = oracle.stop_only(market, receipts, width)
    shared = {
        "market": market.market,
        "files_left": state["files_left"],
        "files_per_booking": int(market.spec["files_per_booking"]),
        "plan_state": str(plan_state),
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "review_is_not_a_lot_or_a_stop", **shared,
                   reported=_show(answer))
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "review_is_not_a_lot_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not state["stop_only"]:
                review.add("plan_failures", "stopped_with_files_in_hand", **shared,
                           smallest_lot=int(market.spec["smallest_lot"]))
                return
            continue
        if not isinstance(choice, dict) or any(
            _number(choice.get(key)) is None for key in ("week", "band", "above_share", "files")
        ) or not _whole_number(choice.get("week")) or not _whole_number(choice.get("files")):
            review.add("plan_failures", "review_is_not_a_lot_or_a_stop", **shared,
                       reported=_show(choice))
            return
        lot = {
            "week": int(_number(choice["week"])),
            "band": float(_number(choice["band"])),
            "above_share": float(_number(choice["above_share"])),
            "files": int(_number(choice["files"])),
        }
        named = {**shared, "week": lot["week"], "band": _points(lot["band"]),
                 "above_share": _points(lot["above_share"]), "files": lot["files"]}
        wrong = oracle.lot_ok(market, receipts, lot)
        if wrong is None and state["range_made"]:


            review.add("plan_failures", "review_after_the_range_is_made", **named,
                       smallest_lot=int(market.spec["smallest_lot"]),
                       range_bar_points=_points(market.spec["range_bar_points"]))
            return
        if wrong is None:
            continue
        extra: dict[str, Any] = {"smallest_lot": int(market.spec["smallest_lot"])}
        if wrong == "review_one_side_of_the_cut":
            extra = {"above_share_low": _points(market.spec["above_share_low"]),
                     "above_share_high": _points(market.spec["above_share_high"])}
        elif wrong == "review_outside_the_band":


            extra = {
                "files_the_number_uses": oracle.files_the_reading_uses(
                    market, receipts, lot["week"], lot["band"], lot["above_share"],
                    lot["files"],
                )
            }
        elif wrong == "review_adds_no_observation":
            extra = {
                "observation_days_gained": _show(
                    oracle.observation_days_gained(
                        market, receipts, lot["week"], lot["band"],
                        lot["above_share"], lot["files"],
                    )
                )
            }
        review.add("plan_failures", wrong, **named, **extra)
        return


def _check_stability(review: Review, readings: Mapping[str, float]) -> None:
    live = readings.get(MARKET)
    if live is None:
        return
    for market in workload.SIBLINGS:
        value = readings.get(market.market)
        if (
            value is not None
            and abs(live - value) < 1e-6
            and abs(oracle.truth(workload.CURRENT) - oracle.truth(market))
            > oracle.CARRIED_OVER_GAP
        ):
            review.add("stability_failures", "hardcoded_history", market=MARKET,
                       other_market=market.market,
                       other_case=market.market.replace("-", " ").title(),
                       reported_points=_points(live))
            return
    for mode, other in (
        ("moves_with_recompute_batch", workload.BATCH_REISSUE),
        ("moves_with_export_stop", workload.STOP_REISSUE),
    ):
        value = readings.get(other.market)
        if value is None:
            continue
        if abs(live - value) > oracle.INVARIANCE_SLACK:
            extra: dict[str, Any] = {}
            if mode == "moves_with_recompute_batch":
                extra = {
                    "changed_offer_rows": sum(
                        int(left["offer_flag"]) != int(right["offer_flag"])
                        for left, right in zip(workload.CURRENT.rows, other.rows)
                    ),
                    "book_rows": len(workload.CURRENT.rows),
                }
            review.add(
                "stability_failures",
                mode,
                market=MARKET,
                other_market=other.market,
                other_case=(
                    "the Northgate refresh-batch reissue"
                    if mode == "moves_with_recompute_batch"
                    else "the Northgate earlier-export reissue"
                ),
                reported_points=_points(live),
                other_points=_points(value),
                moved_by=_points(abs(live - value)),
                **extra,
            )
            return
