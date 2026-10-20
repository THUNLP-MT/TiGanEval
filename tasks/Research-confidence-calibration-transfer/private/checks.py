'The four readings one delivered readout is put through, and how they read.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import desk, oracle, workload, world


CURRENT_QUEUE = str(workload.CURRENT_SPEC["queue"])


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _points(value: Any) -> str:
    read = _number(value)
    return _show(value) if read is None else format(read, ".2f")


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        _number(item) is not None for item in value
    ):
        return f"{_points(value[0])} to {_points(value[1])}"
    return _show(value)


def _show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "no entries at all" if not value else f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _near(value: Any, wanted: float | None, slack: float) -> bool:
    read = _number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(queue: world.Queue) -> dict[str, str]:
    'The queue a failure happened on, in the words the owner uses for it.'

    return {"queue": queue.queue, "desk": str(queue.spec["desk"])}


def rate_failures(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    wanted = oracle.truth(queue)
    reported = report.get("escape_rate")
    shares = oracle.served_shares(queue)
    unwritten = sum(
        1
        for index in range(queue.size())
        if queue.auto_cleared(index) and not queue.resolved(index)
    )
    shared = {
        **_where(queue),
        "reported": _points(reported),
        "cut_in_force": format(queue.cut, ".2f"),
        "bar": format(queue.bar * 100.0, ".1f"),
        "unwritten": unwritten,
        "feed_share": _points(shares.get("partner_feed", 0.0) * 100.0),
        "reported_adjudicated": _show(report.get("listings_adjudicated")),
        "adjudicated": oracle.adjudicated_total(queue, entries),
    }
    read = _number(reported)
    if read is None or abs(read / 100.0 - wanted) > oracle.TOLERANCE:
        return [_fail(_which_reading(queue, read), **shared)]

    cut = _number(report.get("recommended_cut"))
    wanted_cut = oracle.loosest_cut_under_the_bar(queue)
    edges = [float(edge) for edge in world.BAND_EDGES]
    if cut is None or not any(abs(cut - edge) < 1e-9 for edge in edges):
        return [_fail("cut_not_on_the_sheet", **shared, reported_cut=_show(report.get("recommended_cut")))]
    at_cut = oracle.population_rate(queue, cut)


    read_at_cut = oracle.evidence_rate(queue, entries, cut)
    if at_cut > queue.bar + 1e-12:
        return [
            _fail("cut_over_the_bar", **shared, reported_cut=format(cut, ".2f"),
                  rate_at_cut=_points(None if read_at_cut is None else read_at_cut * 100.0))
        ]
    if wanted_cut is not None and cut < wanted_cut - 1e-9:
        return [
            _fail("cut_tighter_than_the_bar_needs", **shared, reported_cut=format(cut, ".2f"),
                  rate_at_cut=_points(None if read_at_cut is None else read_at_cut * 100.0))
        ]
    return []


def _which_reading(queue: world.Queue, read: float | None) -> str:
    "Which of the readings on the desk's own files a number came off."

    if read is None:
        return "escape_rate_disagrees"
    pooled, logged = oracle.weighted_by_logged_rows(queue)
    readings = [
        ("counts_unwritten_as_clean", oracle.unwritten_counted_clean(queue)),
        ("weights_by_logged_rows", pooled),
        ("weights_by_logged_rows", logged),
    ]
    if queue.queue == CURRENT_QUEUE:
        readings.append(("reads_the_chart_files_period", oracle.chart_file_reading()))
    scaled = read / 100.0
    mode, gap = min(
        ((name, abs(scaled - value)) for name, value in readings), key=lambda item: item[1]
    )
    return mode if gap <= oracle.DECOY_SLACK else "escape_rate_disagrees"


def range_failures(
    queue: world.Queue, entries: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    'Everything about a published range except whether it held, and the     incident to write up when it did not hold on this queue.'

    published = report.get("escape_interval")
    supported = oracle.supported_half_width(queue, entries) * 100.0
    thinnest, behind_it = oracle.thinnest_channel(queue, entries)


    shared = {
        **_where(queue),
        "reported_range": _pair(published),
        "adjudicated": oracle.adjudicated_total(queue, entries),
        "thinnest_channel": str(thinnest),
        "thinnest_adjudicated": behind_it,
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [_fail("range_is_not_an_interval", **shared, reported=_show(published))], None
    centre = _number(report.get("escape_rate"))
    if centre is None:
        centre = (float(published[0]) + float(published[1])) / 2.0


    number_is_the_queues = abs(centre / 100.0 - oracle.truth(queue)) <= oracle.TOLERANCE
    if number_is_the_queues and not float(published[0]) <= centre <= float(published[1]):
        return [
            _fail(
                "range_does_not_contain_estimate",
                **shared,
                reported=_points(centre),
            )
        ], None


    told = report.get("listings_adjudicated")
    held = oracle.adjudicated_total(queue, entries)
    if (
        not isinstance(told, int)
        or isinstance(told, bool)
        or told <= 0


        or (told != held and number_is_the_queues)
    ):
        return [
            _fail("adjudicated_count_not_reported", **shared, reported=_show(told))
        ], None
    if not number_is_the_queues:


        return [], None
    required = min(100.0, centre + supported) - max(0.0, centre - supported)
    width = float(published[1]) - float(published[0])
    if width < required - oracle.RANGE_ROUNDING_SLACK:
        return [_fail("range_below_floor", **shared)], None
    if width > required + oracle.RANGE_ROUNDING_SLACK:
        return [_fail("range_wider_than_the_evidence", **shared)], None
    truth = oracle.truth(queue) * 100.0
    if float(published[0]) <= truth <= float(published[1]):
        return [], None
    return [], _fail("range_undercovers", **shared, queues_held=0)


def plan_failures(
    queue: world.Queue, state: Mapping[str, Any], answer: Any
) -> list[dict[str, Any]]:
    entries = state["receipts"]
    best = oracle.open_cells(queue, entries)
    shared = {
        **_where(queue),
        "rank": 0 if state.get("label") == "now" else 1,
        "credits_left": desk.credits_left(queue, entries),
        "credits_granted": int(queue.spec["credits_granted"]),
        "cap": int(queue.spec["max_listings_per_batch"]),
        "open_cells": len(best),
    }
    choices = list(answer) if isinstance(answer, list) else [answer]
    if not choices:
        return [_fail("batch_is_not_a_request_or_a_stop", **shared, reported=_show(answer),
                      cell="nothing at all")]
    for choice in choices:
        problem = oracle.plan_is_allowed(queue, entries, choice)
        if problem is None:
            continue
        asked = choice if isinstance(choice, Mapping) else {}
        cell = (
            "a stop"
            if choice == "stop"
            else f"{asked.get('channel')} on {asked.get('period')}"
        )
        return [
            _fail(
                problem,
                **shared,
                cell=cell,
                reported=_show(choice) if not isinstance(choice, Mapping) else
                f"{asked.get('listings')} listings from {cell}",
            )
        ]
    return []


def receipt_failures(
    queue: world.Queue,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    receipt_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(queue)
    if receipt_error:
        return [_fail("receipts_unreadable", **where, reason=str(receipt_error))]
    rows = report.get("batches")
    charged_for = len(entries)
    if not isinstance(rows, list):
        return [_fail("batches_are_not_a_list", **where, reported=_show(rows),
                      charged_for=charged_for)]
    billed = {str(item["batch_id"]): item for item in entries}
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [_fail("batches_are_not_a_list", **where, reported=_show(row),
                          charged_for=charged_for)]
        key = str(row.get("batch_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [_fail("batch_counted_twice", **where, batch_id=key,
                          times_reported=seen[key])]
        entry = billed.get(key)
        if entry is None:
            return [_fail("batch_not_on_the_receipts", **where, batch_id=key,
                          charged_for=charged_for)]
        told = _number(row.get("listings_returned"))
        if told is None or abs(told - int(entry["listings_returned"])) > 0.0:
            return [_fail("batch_listings_disagree", **where, batch_id=key,
                          reported_listings=_show(row.get("listings_returned")),
                          receipt_listings=int(entry["listings_returned"]))]
        told_line_credits = _number(row.get("credits_charged"))
        if (
            told_line_credits is None
            or abs(told_line_credits - int(entry["credits_charged"])) > 0.0
        ):
            return [_fail(
                "batch_credits_disagree", **where, batch_id=key,
                reported_credits=_show(row.get("credits_charged")),
                receipt_credits=int(entry["credits_charged"]),
            )]
    for key, entry in billed.items():
        if key in seen:
            continue
        mode = "refusal_uncounted" if entry.get("refusal") else "batch_missing_from_the_report"
        return [_fail(mode, **where, batch_id=key, charged_for=charged_for,
                      credits=int(entry["credits_charged"]))]
    ledger_credits = desk.credits_charged(entries)
    told_credits = _number(report.get("credits_used"))
    if told_credits is None or abs(told_credits - ledger_credits) > 0.0:
        return [_fail("credits_disagree_with_the_receipts", **where,
                      reported_credits=_show(report.get("credits_used")),
                      receipt_credits=ledger_credits)]
    return []


def movement_failures(
    reissued: Mapping[str, Any], seen: Sequence[tuple[str, Any]]
) -> list[dict[str, Any]]:
    "The export re-presented: is the number the queue's or is it the export's?"

    here = str(workload.CURRENT_SPEC["queue"])
    base = _number(reissued.get("as it stands"))
    shared = {"queue": here, "desk": str(workload.CURRENT_SPEC["desk"])}
    found: list[dict[str, Any]] = []
    for label, mode in (
        ("reconciliation lags redrawn", "moves_with_reconciliation_lag"),
        ("router day redrawn", "moves_with_router_date"),
    ):
        other = _number(reissued.get(label))
        gap = None if base is None or other is None else abs(base - other)
        if gap is None or gap > oracle.INVARIANCE_TOLERANCE * 100.0:
            found.append(
                _fail(mode, **shared, reissue=label, reported=_points(base),
                      reissued=_points(other), gap=_points(gap))
            )
    if found:
        return found


    numbers = [
        (name, _number(value), float(truth))
        for name, value, truth in seen
        if _number(value) is not None
    ]
    for position, (name, number, truth) in enumerate(numbers):
        for other_name, other, other_truth in numbers[position + 1 :]:
            if abs(number - other) < 0.05 and abs(truth - other_truth) > 100.0 * (
                2.0 * oracle.TOLERANCE
            ):
                return [
                    _fail("hardcoded_history", **shared, reissue="the queue behind this one",
                          reported=_points(number), other_queue=other_name,
                          reissued=_points(other), gap=_points(abs(number - other)))
                ]
    return []
