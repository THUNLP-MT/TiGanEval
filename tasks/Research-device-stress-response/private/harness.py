'Read one delivered qualification notebook against the lot it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-device-stress-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

LOT = workload.CURRENT.lot
UNIT_SOURCES = ("batch_table", "receipt")

BUCKETS: Mapping[str, str] = {
    "crossing_within_tolerance": "crossing_failures",
    "range_covers_and_meets_floor": "range_failures",
    "crossing_invariant_to_bench_calibration": "stability_failures",
    "next_block_reaches_the_crossing": "plan_failures",
    "report_reconciles_receipts": "ledger_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "crossing_within_tolerance": (
        "crossing_in_console_bar",
        "crossing_uses_the_pinned_rows",
        "crossing_pools_the_short_hold",
        "crossing_disagrees",
        "crossing_wrong_on_another_lot",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_a_pair",
        "range_does_not_contain_reported_crossing",
        "range_not_centred_on_reported_crossing",
        "range_narrower_than_the_units_support",
        "range_wider_than_the_units_support",
        "range_wrong_on_another_lot",
        "candidate_execution_failed",
    ),
    "crossing_invariant_to_bench_calibration": (
        "crossing_missing_on_live_lot",
        "crossing_missing_on_redraw",
        "crossing_carried_over_from_this_lot",
        "crossing_tracks_the_bench_scale",
        "crossing_tracks_which_bench_a_batch_ran_on",
        "candidate_execution_failed",
    ),
    "next_block_reaches_the_crossing": (
        "charged_session_did_not_advance_the_crossing",
        "block_is_not_a_session_or_a_stop",
        "block_at_the_wrong_hold",
        "block_at_a_cartridge_the_gauge_cannot_read",
        "block_over_the_hours_or_ports",
        "block_books_a_bench_or_batch_it_cannot",
        "block_does_not_reach_the_crossing",
        "block_leaves_the_ports_empty",
        "stopped_with_hours_left",
        "block_wrong_on_another_lot",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "sessions_are_not_a_ledger",
        "hour_reported_twice",
        "session_not_on_the_receipts",
        "handed_back_session_left_out",
        "charged_hour_missing",
        "counted_units_carry_no_source",
        "block_check_counted_as_a_unit",
        "counted_units_disagree",
        "report_wrong_on_another_lot",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "crossing_failures": ("crossing_wrong_on_another_lot",),
    "range_failures": ("range_wrong_on_another_lot",),
    "plan_failures": ("block_wrong_on_another_lot",),
    "ledger_failures": ("report_wrong_on_another_lot",),
}


_NAMING_ORDER: tuple[str, ...] = tuple(
    world.lot
    for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME, workload.ENDPOINT)
)


def _naming_rank(lot: str) -> int:
    return _NAMING_ORDER.index(lot) if lot in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident Ruth can open the March table for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("lot") == LOT else 1,
    )


def _reported_plan(record: Mapping[str, Any]) -> str:
    'The candidate-side plan Ruth can have Sanne read back.'

    if str(record.get("kind")) == "stopped_with_hours_left":
        return "stop"
    if "reported" in record:
        return str(record["reported"])
    fields = ("bench", "batch", "cartridge", "dwell_min", "units")
    if all(field in record for field in fields):
        return (
            f"{record['units']} couplings of {record['batch']} at "
            f"{record['cartridge']} on {record['bench']} for "
            f"{record['dwell_min']} minutes"
        )
    return "an unreadable next step"


def _reported_accounting(record: Mapping[str, Any]) -> str:
    'One candidate or bill-side accounting detail, without the reference count.'

    if "issue" in record:
        return str(record["issue"])
    if "booking_id" in record:
        return f"session {record['booking_id']}"
    if "source" in record:
        return (
            f"{record['source']} with {record.get('reported_units')} units and "
            f"{record.get('reported_leaks')} leaks"
        )
    if "reported_units" in record:
        return f"{record['reported_units']} batch-table units"
    if "reported" in record:
        return str(record["reported"])
    return "an unreadable accounting line"


def _carry_over_measurement(
    bucket: str, record: Mapping[str, Any]
) -> dict[str, Any]:
    'Keep what the candidate returned while withholding the hidden reference.'

    if bucket == "crossing_failures":
        return {"reported_bar": record.get("reported_bar", "blank")}
    if bucket == "range_failures":
        return {
            "reported_range": record.get(
                "reported_range", record.get("reported", "unreadable")
            )
        }
    if bucket == "plan_failures":
        return {"reported_plan": _reported_plan(record)}
    if bucket == "ledger_failures":
        return {"reported_accounting": _reported_accounting(record)}
    return {}


def _written_off_the_live_lot(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the lot Ruth can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("lot") == LOT
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    mode = modes[0]
    named = min(
        (record for record in rows if record.get("lot")),
        key=lambda record: _naming_rank(str(record["lot"])),
        default=rows[0],
    )
    elsewhere = sorted({str(record["lot"]) for record in rows if record.get("lot")})
    carried = {
        "lot": LOT,
        "other_lot": str(named.get("lot")),
        "other_lots": len(elsewhere),
    }
    if "hours_left" in named:
        carried["hours_left"] = named["hours_left"]
    carried.update(_carry_over_measurement(bucket, named))
    return [_fail(mode, **carried)]


def _bar(value: Any) -> str:
    return format(float(value), ".1f")


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
        return f"{_bar(value[0])} to {_bar(value[1])} bar"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The sessions this delivery has paid for, or why the stream will not read.'

    try:
        return w.read_receipts(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def _extend(world: w.World, stream: Sequence[Mapping[str, Any]], bookings) -> list[dict[str, Any]]:
    return w.extend(world, stream, bookings)


def plan_states(
    world: w.World, stream: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every booking state this lot can be asked for a next session in.'

    states = [{"label": "as it stands", "receipts": [dict(item) for item in stream]}]
    if world.lot != LOT or oracle.stop_is_the_only_answer(world, stream):
        return states


    states.append(
        {"label": "hours and stores spent", "receipts": oracle.walk_to_exhaustion(world, stream)}
    )


    filler = []
    for index in range(3):
        session = oracle.best_session(world, _extend(world, stream, filler))
        if session is None:
            break
        filler.append(dict(session, booking_id=f"state-{index + 1:02d}"))
    handed_back = _extend(
        world,
        stream,
        [
            *filler,
            {
                "booking_id": "state-refused",
                "bench": "B-2",
                "batch": "B-05",
                "cartridge": "C-200",
                "dwell_min": 30,
                "units": 6,
            },
        ],
    )
    states.append({"label": "a sheet handed back", "receipts": handed_back})


    states.append(
        {
            "label": "an hour on the pinned cartridge",
            "receipts": _extend(
                world,
                stream,
                [
                    {
                        "booking_id": "state-pinned",
                        "bench": "B-1",
                        "batch": "B-05",
                        "cartridge": "C-300",
                        "dwell_min": 30,
                        "units": 6,
                    }
                ],
            ),
        }
    )


    short: list[dict[str, Any]] = []
    index = 0
    while world.hours_left(_extend(world, stream, short)) > 1.0 + 1e-9:
        index += 1
        short.append(
            {
                "booking_id": f"state-thin-{index:02d}",
                "bench": "B-1",
                "batch": "B-05",
                "cartridge": "C-200",
                "dwell_min": 30,
                "units": 1,
            }
        )
    short.append(
        {
            "booking_id": "state-thin-short",
            "bench": "B-1",
            "batch": "B-06",
            "cartridge": "C-200",
            "dwell_min": int(world.spec["short_hold_min"]),
            "units": 1,
        }
    )
    states.append({"label": "half an hour left", "receipts": _extend(world, stream, short)})
    return states


def instances(stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The lot on the desk, the ones the notebook is run over next, the redraws.'

    rows: list[dict[str, Any]] = [
        {
            "label": LOT,
            "world": workload.CURRENT,
            "receipts": [dict(item) for item in stream],
            "redraw": False,
        }
    ]
    for world in (*workload.SIBLINGS, workload.OUT_OF_REGIME, workload.ENDPOINT):
        rows.append(
            {"label": world.lot, "world": world, "receipts": w.opening_stream(world),
             "redraw": False}
        )
    for world in workload.PARTNERS:
        rows.append(
            {"label": world.lot, "world": world, "receipts": w.opening_stream(world),
             "redraw": True}
        )
    for row in rows:
        row["plans"] = [] if row["redraw"] else plan_states(row["world"], row["receipts"])
    return rows


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(self, buckets: Sequence[str], error: str) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(0, _fail(CANDIDATE_FAILURE, error=error))


_MISREADINGS = (
    ("crossing_in_console_bar", ("console_bar", "console_bar_and_pinned")),
    ("crossing_uses_the_pinned_rows", ("pinned_rows",)),
    ("crossing_pools_the_short_hold", ("short_hold", "pinned_and_short_hold")),
)


def explanation(
    readings: Mapping[str, float],
    worlds: Mapping[str, w.World],
    streams: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str | None:
    'The one misreading that accounts for this delivery on most of the lots.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = 0
        for lot, value in readings.items():
            if lot not in worlds:
                continue
            misread = oracle.misreadings(worlds[lot], streams.get(lot, ()))
            if any(
                _near(value, misread[family], oracle.CLASSIFY_SLACK)
                for family in families
                if family in misread
            ):
                hits += 1
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _matches_explanation(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    reported: Any,
    mode: str | None,
) -> bool:
    'Whether the named delivery itself exhibits the fleet-level diagnosis.'

    if mode is None or _number(reported) is None:
        return False
    families = dict(_MISREADINGS).get(mode, ())
    misread = oracle.misreadings(world, stream)
    return any(
        family in misread
        and _near(reported, misread[family], oracle.CLASSIFY_SLACK)
        for family in families
    )


def _pinned_units(world: w.World) -> tuple[int, str]:
    'How many rows came back on the sticker, and the lowest cartridge that did.'

    span = world.span_bar
    count = 0
    lowest: str | None = None
    for row in world.run_rows():
        if str(row["result"]) not in w.RESULTS:
            continue
        if float(row["reading_bar"]) >= span - 1e-9:
            count += 1
            name = str(row["cartridge"])
            if lowest is None or world.true_bar(name) < world.true_bar(lowest):
                lowest = name
    return count, str(lowest or "")


def _short_hold_units(world: w.World) -> tuple[int, str]:
    'How many rows ran at the short hold, and the batch that carries them.'

    hold = int(world.spec["plan_hold_min"])
    count = 0
    batch: str | None = None
    for row in world.run_rows():
        if str(row["result"]) not in w.RESULTS:
            continue
        if int(row["dwell_min"]) != hold:
            count += 1
            batch = batch or str(row["batch"])
    return count, str(batch or "")


def _furthest_bench(world: w.World) -> tuple[str, float, str]:
    "The bench whose block reading sits furthest from the block's own pressure."

    block = float(world.spec["block_bar"])
    best = max(
        world.spec["benches"],
        key=lambda bench: abs(world.scale_of(bench) - 1.0),
    )
    batch = next(
        (name for name in sorted(world.batches) if world.batches[name]["bench"] == best),
        sorted(world.batches)[0],
    )
    readings = world.block_readings(best, batch)
    return best, sum(readings) / len(readings), batch


def _check_crossing(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    mode: str | None,
) -> None:
    truth = oracle.truth(world)
    reported = report.get("crossing_bar")
    if _near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "lot": world.lot,
        "reported_bar": (
            _bar(reported) if _number(reported) is not None else _show(reported)
        ),
    }
    if not _matches_explanation(world, stream, reported, mode):


        review.add(
            "crossing_failures",
            "crossing_disagrees",
            **shared,
            plan_hold_min=int(world.spec["plan_hold_min"]),
            counted_units=sum(units for _bar_, units, _leaks in oracle.levels(world, stream)),
        )
        return
    if mode == "crossing_in_console_bar":
        bench, block_reading, batch = _furthest_bench(world)
        review.add(
            "crossing_failures",
            mode,
            **shared,
            bench=bench,
            batch=batch,
            block_bar=_bar(world.spec["block_bar"]),
            block_reading_bar=_bar(block_reading),
        )
        return
    if mode == "crossing_uses_the_pinned_rows":
        count, cartridge = _pinned_units(world)
        review.add(
            "crossing_failures",
            mode,
            **shared,
            pinned_units=count,
            cartridge=cartridge,
            span_bar=_bar(world.span_bar),
        )
        return
    count, batch = _short_hold_units(world)
    review.add(
        "crossing_failures",
        mode,
        **shared,
        short_hold_units=count,
        batch=batch,
        plan_hold_min=int(world.spec["plan_hold_min"]),
        short_hold_min=int(world.spec["short_hold_min"]),
    )


def _range_of(report: Mapping[str, Any]) -> tuple[float, float] | None:
    bounds = report.get("crossing_range_bar")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(_number(item) is None for item in bounds)
        or float(bounds[0]) > float(bounds[1])
    ):
        return None
    return float(bounds[0]), float(bounds[1])


def _check_range(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> None:
    'The authored two-standard-error construction, on each side of the point.'

    bounds = _range_of(report)
    if bounds is None:
        review.add(
            "range_failures",
            "range_is_not_a_pair",
            lot=world.lot,
            reported=_pair(report.get("crossing_range_bar")),
        )
        return
    reported = _number(report.get("crossing_bar"))
    if reported is not None and not bounds[0] <= reported <= bounds[1]:
        review.add(
            "range_failures",
            "range_does_not_contain_reported_crossing",
            lot=world.lot,
            reported_bar=_bar(reported),
            reported_range=_pair(list(bounds)),
        )
        return
    centre = reported if reported is not None else (bounds[0] + bounds[1]) / 2.0
    sides = (centre - bounds[0], bounds[1] - centre)
    supported = oracle.admitted_half_widths(world, stream)
    slack = oracle.RANGE_ROUNDING_BAR
    if reported is not None and abs(sides[0] - sides[1]) > 2.0 * slack:
        review.add(
            "range_failures",
            "range_not_centred_on_reported_crossing",
            lot=world.lot,
            reported_bar=_bar(reported),
            reported_range=_pair(list(bounds)),
        )
        return
    counted = sum(units for _bar_, units, _leaks in oracle.levels(world, stream))


    fields = {
        "lot": world.lot,
        "reported_range": _pair(list(bounds)),
        "counted_units": counted,
        "levels_counted": len(oracle.levels(world, stream)),
    }
    unsupported = [
        side
        for side in sides
        if not any(abs(side - width) <= slack for width in supported)
    ]
    if not unsupported:
        return
    if min(unsupported) < min(supported) - slack:
        review.add("range_failures", "range_narrower_than_the_units_support", **fields)
    else:
        review.add("range_failures", "range_wider_than_the_units_support", **fields)


def _check_stability(review: Review, readings: Mapping[str, float]) -> None:
    live = readings.get(LOT)
    if live is None:
        return
    carried = workload.SIBLINGS[0].lot
    other = readings.get(carried)
    if (
        other is not None
        and abs(live - other) < 1e-6
        and abs(oracle.truth(workload.CURRENT) - oracle.truth(workload.SIBLINGS[0]))
        > oracle.CARRIED_OVER_GAP
    ):
        review.add(
            "stability_failures",
            "crossing_carried_over_from_this_lot",
            lot=LOT,
            other_lot=carried,
            reported_bar=_bar(live),
        )
        return
    for mode, partner in (
        ("crossing_tracks_the_bench_scale", workload.SCALE_PARTNER),
        ("crossing_tracks_which_bench_a_batch_ran_on", workload.BENCH_PARTNER),
    ):
        value = readings.get(partner.lot)
        if value is None:
            continue
        if abs(live - value) > oracle.INVARIANCE_SLACK:
            review.add(
                "stability_failures",
                mode,
                lot=LOT,
                other_lot=partner.lot,
                reported_bar=_bar(live),
                other_bar=_bar(value),
                moved_by=_bar(abs(live - value)),
            )
            return


def _check_live_collection_history(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
) -> None:
    'Keep an Agent-booked bad hour from disappearing behind a later stop.'

    opening = w.opening_stream(world)
    prefix = [dict(item) for item in opening]
    for receipt in stream[len(opening):]:
        choice = {
            "bench": receipt.get("bench"),
            "batch": receipt.get("batch"),
            "cartridge": receipt.get("cartridge"),
            "dwell_min": receipt.get("dwell_min"),
            "units": receipt.get("units_asked"),
        }
        probe = Review()
        _check_plan(probe, world, prefix, [choice])
        if probe.failures["plan_failures"]:
            review.add(
                "plan_failures",
                "charged_session_did_not_advance_the_crossing",
                lot=world.lot,
                booking_id=str(receipt.get("booking_id")),
                cartridge=str(receipt.get("cartridge")),
                dwell_min=int(receipt.get("dwell_min")),
                units_returned=int(receipt.get("units_returned")),
                hours_charged=float(receipt.get("hours_charged")),
                issue=str(probe.failures["plan_failures"][0]["kind"]),
            )
            return
        prefix.append(dict(receipt))


def _check_plan(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    answer: Any,
) -> None:
    hold = int(world.spec["plan_hold_min"])
    ports = int(world.spec["ports"])
    hours = world.hours_left(stream)
    stock = world.stock_left(stream)
    day = world.served_on(stream)
    shared = {
        "lot": world.lot,
        "hours_left": hours,
        "ports": ports,
        "plan_hold_min": hold,
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "block_is_not_a_session_or_a_stop", **shared,
                   reported=_show(answer))
        return
    stop_only = oracle.stop_is_the_only_answer(world, stream)
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "block_is_not_a_session_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not stop_only:
                review.add("plan_failures", "stopped_with_hours_left", **shared,
                           stores_left=sum(stock.values()))
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "block_is_not_a_session_or_a_stop", **shared,
                       reported=_show(choice))
            return
        bench = choice.get("bench")
        batch = choice.get("batch")
        cartridge = choice.get("cartridge")
        dwell = _number(choice.get("dwell_min"))
        units = _number(choice.get("units"))
        if (
            not isinstance(bench, str)
            or not isinstance(batch, str)
            or not isinstance(cartridge, str)
            or dwell is None
            or units is None
            or dwell != int(dwell)
            or units != int(units)
            or units < 1
        ):
            review.add("plan_failures", "block_is_not_a_session_or_a_stop", **shared,
                       reported=_show(
                           f"{_show(cartridge)} on {_show(bench)} from {_show(batch)}, "
                           f"{_show(choice.get('units'))} units at "
                           f"{_show(choice.get('dwell_min'))} minutes"
                       ))
            return
        dwell, units = int(dwell), int(units)
        named = {**shared, "bench": bench, "batch": batch, "cartridge": cartridge,
                 "dwell_min": dwell, "units": units}
        if dwell != hold:
            review.add("plan_failures", "block_at_the_wrong_hold", **named)
            return
        if (
            cartridge in world.spec["cartridges"]
            and cartridge not in oracle.readable_cartridges(world)
        ):
            review.add("plan_failures", "block_at_a_cartridge_the_gauge_cannot_read", **named,
                       span_bar=_bar(world.span_bar))
            return
        if units > ports or world.hours_charged(dwell) > hours + 1e-9:
            review.add("plan_failures", "block_over_the_hours_or_ports", **named,
                       hours_charged=world.hours_charged(dwell))
            return
        if (
            bench not in world.spec["benches"]
            or world.bench_is_out(bench, str(day))
            or batch not in stock
            or stock.get(batch, 0) < units
            or cartridge not in world.spec["cartridges"]
            or day is None
        ):
            window = world.spec["bench_out"].get(bench) or ("", "")
            review.add("plan_failures", "block_books_a_bench_or_batch_it_cannot", **named,
                       served_on=str(day), stores_left=int(stock.get(batch, 0)),
                       out_from=str(window[0]), out_to=str(window[1]))
            return
        wanted = oracle.bracketing_cartridges(world, stream)
        if cartridge not in wanted:
            review.add("plan_failures", "block_does_not_reach_the_crossing", **named,
                       stores_left=int(stock.get(batch, 0)))
            return
        if units != min(ports, int(stock[batch])):
            review.add("plan_failures", "block_leaves_the_ports_empty", **named,
                       stores_left=int(stock.get(batch, 0)))
            return


def _trajectory_successors(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    answer: Any,
    depth: int,
) -> list[list[dict[str, Any]]]:
    'Serve each distinct valid alternative the notebook offered.'

    probe = Review()
    _check_plan(probe, world, stream, answer)
    if probe.failures["plan_failures"] or not isinstance(answer, list):
        return []
    successors: list[list[dict[str, Any]]] = []
    seen: set[str] = set()
    used_ids = {str(entry.get("booking_id")) for entry in stream}
    for index, choice in enumerate(answer):
        if not isinstance(choice, dict):
            continue
        marker = json.dumps(choice, sort_keys=True, separators=(",", ":"))
        if marker in seen:
            continue
        seen.add(marker)
        suffix = 0
        booking_id = f"review-path-{depth:02d}-{index:02d}"
        while booking_id in used_ids:
            suffix += 1
            booking_id = f"review-path-{depth:02d}-{index:02d}-{suffix}"
        booking = dict(choice, booking_id=booking_id)
        successors.append(w.extend(world, stream, [booking]))
    return successors


def _partner_stream(
    partner: w.World, stream: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "Replay March's post-opening choices onto one calibration redraw."

    current_opening = w.opening_stream(workload.CURRENT)
    bookings = [
        {
            "booking_id": str(entry["booking_id"]),
            "bench": str(entry["bench"]),
            "batch": str(entry["batch"]),
            "cartridge": str(entry["cartridge"]),
            "dwell_min": int(entry["dwell_min"]),
            "units": int(entry["units_asked"]),
        }
        for entry in stream[len(current_opening):]
    ]
    return w.extend(partner, w.opening_stream(partner), bookings)


def _counted_by_source(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    *,
    plan_hold_only: bool = True,
    drop_pinned: bool = True,
) -> dict[str, tuple[int, int]]:
    'The couplings the ladder counts, split by where each one came from.'

    span = world.span_bar
    hold = int(world.spec["plan_hold_min"])
    totals: dict[str, list[int]] = {}
    for row in oracle.all_rows(world, stream):
        if str(row["result"]) not in w.RESULTS:
            continue
        if plan_hold_only and int(row["dwell_min"]) != hold:
            continue
        if drop_pinned and float(row["reading_bar"]) >= span - 1e-9:
            continue
        entry = totals.setdefault(str(row["source"]), [0, 0])
        entry[0] += 1
        entry[1] += 1 if str(row["result"]) == "leak" else 0
    return {source: (units, leaks) for source, (units, leaks) in totals.items()}


def _counted_units_issue(value: Any) -> str | None:
    'A public-schema diagnosis for an unreadable provenance entry.'

    if not isinstance(value, list):
        return "the counted_units field is not a list"
    if not value:
        return "the counted_units list is empty"
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            return f"entry {index} is not a source-count object"
        source = item.get("source")
        if source not in UNIT_SOURCES:
            return f"entry {index} does not name a recognised source"
        units = _number(item.get("units"))
        leaks = _number(item.get("leaks"))
        if units is None or leaks is None:
            return f"entry {index} does not carry numeric units and leaks"
        if units < 0 or leaks < 0 or units != int(units) or leaks != int(leaks):
            return f"entry {index} does not carry non-negative whole counts"
        if leaks > units:
            return f"entry {index} claims more leaks than units"
    return None


def _block_checks(world: w.World) -> int:
    return sum(1 for row in world.run_rows() if str(row["result"]) == "block")


def _check_ledger(
    review: Review,
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    error: str | None,
) -> None:
    if error:
        review.add("ledger_failures", "receipts_unreadable", lot=world.lot, reason=str(error))
        return
    rows = report.get("sessions")
    if not isinstance(rows, list):
        review.add("ledger_failures", "sessions_are_not_a_ledger", lot=world.lot,
                   reported=_show(rows), charged=len(stream))
        return
    billed = {str(item["booking_id"]): item for item in stream}
    seen: dict[str, int] = {}
    for row in rows:
        booking_id = str(row.get("booking_id"))
        seen[booking_id] = seen.get(booking_id, 0) + 1
        if seen[booking_id] > 1:
            review.add("ledger_failures", "hour_reported_twice", lot=world.lot,
                       booking_id=booking_id, times_reported=seen[booking_id])
            return
        entry = billed.get(booking_id)
        if entry is None or row.get("bench") != entry["bench"] or not all(
            _near(row.get(field), float(entry[wanted]), 1e-9)
            for field, wanted in (
                ("dwell_min", "dwell_min"),
                ("units", "units_returned"),
                ("hours_charged", "hours_charged"),
            )
        ) or not _near(
            row.get("leaks"), float(list(entry.get("results") or ()).count("leak")), 1e-9
        ):
            review.add("ledger_failures", "session_not_on_the_receipts", lot=world.lot,
                       booking_id=booking_id, charged=len(stream))
            return
    for booking_id, entry in billed.items():
        if booking_id in seen:
            continue
        kind = (
            "handed_back_session_left_out"
            if str(entry.get("refusal") or "")
            else "charged_hour_missing"
        )
        review.add("ledger_failures", kind, lot=world.lot, booking_id=booking_id,
                   hours_charged=float(entry["hours_charged"]),
                   served_on=str(entry["served_on"]), charged=len(stream))
        return
    counted = report.get("counted_units")
    counted_issue = _counted_units_issue(counted)
    if counted_issue is not None:
        review.add("ledger_failures", "counted_units_carry_no_source", lot=world.lot,
                   reported=_show(counted), sources=", ".join(UNIT_SOURCES),
                   issue=counted_issue)
        return
    reported_units: dict[str, list[float]] = {}
    for item in counted:
        entry = reported_units.setdefault(str(item["source"]), [0.0, 0.0])
        entry[0] += float(item["units"])
        entry[1] += float(item["leaks"])
    wanted = _counted_by_source(world, stream)
    table_units = float(reported_units.get("batch_table", [0.0, 0.0])[0])
    ladder_units = float(wanted.get("batch_table", (0, 0))[0])
    blocks = _block_checks(world)
    if abs(table_units - (ladder_units + blocks)) < 1e-9 and blocks:
        review.add("ledger_failures", "block_check_counted_as_a_unit", lot=world.lot,
                   reported_units=int(table_units), block_checks=blocks,
                   counted_units=int(ladder_units))
        return
    got_table = reported_units.get("batch_table", [0.0, 0.0])

    def same_total(pair: Sequence[float], wanted_pair: Sequence[float]) -> bool:
        return (
            abs(float(pair[0]) - float(wanted_pair[0])) <= 1e-9
            and abs(float(pair[1]) - float(wanted_pair[1])) <= 1e-9
        )

    canonical_table = wanted.get("batch_table", (0, 0))
    table_matches_number = same_total(got_table, canonical_table)
    reported_crossing = _number(report.get("crossing_bar"))
    if not table_matches_number and reported_crossing is not None:


        for plan_hold_only in (True, False):
            for drop_pinned in (True, False):
                if plan_hold_only and drop_pinned:
                    continue
                alternative = _counted_by_source(
                    world,
                    stream,
                    plan_hold_only=plan_hold_only,
                    drop_pinned=drop_pinned,
                ).get("batch_table", (0, 0))
                if not same_total(got_table, alternative):
                    continue
                readings = []
                for correct_bench in (True, False):
                    try:
                        readings.append(
                            oracle.crossing(
                                oracle.levels(
                                    world,
                                    stream,
                                    correct_bench=correct_bench,
                                    plan_hold_only=plan_hold_only,
                                    drop_pinned=drop_pinned,
                                )
                            )
                        )
                    except (ValueError, ZeroDivisionError, OverflowError):
                        continue
                if any(
                    abs(reported_crossing - value) <= oracle.CLASSIFY_SLACK
                    for value in readings
                ):
                    table_matches_number = True
                    break
            if table_matches_number:
                break
    if not table_matches_number:
        review.add(
            "ledger_failures",
            "counted_units_disagree",
            lot=world.lot,
            source="batch_table",
            reported_units=_show(got_table[0]),
            reported_leaks=_show(got_table[1]),
            counted_units=int(ladder_units),
        )
        return


    got = reported_units.get("receipt", [0.0, 0.0])
    want = wanted.get("receipt", (0, 0))
    if abs(got[0] - want[0]) > 1e-9 or abs(got[1] - want[1]) > 1e-9:
        review.add("ledger_failures", "counted_units_disagree", lot=world.lot,
                   source="receipt", reported_units=_show(got[0]),
                   reported_leaks=_show(got[1]),
                   counted_units=int(want[0]))
        return


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
    return f"the qualification notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every lot and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        stream, stream_error = live_receipts(Path(artifact_dir))
        rows = instances(stream)
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(world: w.World) -> int:
            if id(world) not in seen:
                seen[id(world)] = len(contexts)
                contexts.append(world.context())
            return seen[id(world)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[w.World, list[dict[str, Any]], int, bool]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "receipts": row["receipts"]}
            )
            for state_index, state in enumerate(row["plans"]):
                plans.append(
                    (row["world"], list(state["receipts"]), len(requests), state_index == 0)
                )
                requests.append(
                    {"kind": "plan", "context": context_index(row["world"]),
                     "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"lot": LOT, "sessions_charged": len(stream)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the lots"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        readings: dict[str, float] = {}
        missing_readings: dict[str, str] = {}
        worlds: dict[str, w.World] = {}
        streams: dict[str, list[dict[str, Any]]] = {}
        for row, index in reports:
            value, _error = answer(index)
            reported = dict(value or {}).get("crossing_bar") if value else None
            read = _number(reported)
            if read is not None:
                readings[row["world"].lot] = read
                worlds[row["world"].lot] = row["world"]
                streams[row["world"].lot] = list(row["receipts"])
            elif _error is None:
                missing_readings[row["world"].lot] = _show(reported)
                if row["redraw"]:
                    review.add(
                        "stability_failures",
                        "crossing_missing_on_redraw",
                        lot=LOT,
                        other_lot=row["world"].lot,
                        reported=_show(reported),
                    )
        if LOT in missing_readings:
            partner = next(
                (world for world in workload.PARTNERS if world.lot in readings),
                None,
            )
            if partner is not None:
                review.add(
                    "stability_failures",
                    "crossing_missing_on_live_lot",
                    lot=LOT,
                    other_lot=partner.lot,
                    reported=missing_readings[LOT],
                    other_bar=_bar(readings[partner.lot]),
                )
        mode = explanation(readings, worlds, streams)
        stopped = False
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("crossing_failures", "range_failures", "ledger_failures",
                     "stability_failures"),
                    error,
                )
                continue
            if row["redraw"]:
                continue
            report = dict(value or {})
            _check_crossing(review, world, row["receipts"], report, mode)
            _check_range(review, world, row["receipts"], report)
            _check_ledger(
                review, world, row["receipts"], report,
                stream_error if world.lot == LOT else None,
            )
        frontier: list[tuple[w.World, list[dict[str, Any]]]] = []
        for world, receipts, index, is_start in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            _check_plan(review, world, receipts, value)
            if is_start:
                frontier.extend(
                    (world, successor)
                    for successor in _trajectory_successors(world, receipts, value, 1)
                )
        if stream_error is None:
            _check_live_collection_history(review, workload.CURRENT, stream)
        _check_stability(review, readings)


        max_rounds = max(
            int(float(row["world"].spec["hours_granted"])) + 2
            for row in rows
            if not row["redraw"]
        )
        for depth in range(1, max_rounds + 1):
            if not frontier:
                break
            unique: list[tuple[w.World, list[dict[str, Any]]]] = []
            state_keys: set[tuple[str, str]] = set()
            for world, receipts in frontier:
                key = (
                    world.lot,
                    json.dumps(receipts, sort_keys=True, separators=(",", ":")),
                )
                if key not in state_keys:
                    state_keys.add(key)
                    unique.append((world, receipts))
            frontier = []

            dynamic_contexts: list[dict[str, Any]] = []
            dynamic_seen: dict[int, int] = {}

            def dynamic_context_index(world: w.World) -> int:
                if id(world) not in dynamic_seen:
                    dynamic_seen[id(world)] = len(dynamic_contexts)
                    dynamic_contexts.append(world.context())
                return dynamic_seen[id(world)]

            dynamic_requests: list[dict[str, Any]] = []
            states: list[dict[str, Any]] = []
            for world, receipts in unique:
                report_index = len(dynamic_requests)
                dynamic_requests.append(
                    {"kind": "report", "context": dynamic_context_index(world),
                     "receipts": receipts}
                )
                plan_index = len(dynamic_requests)
                dynamic_requests.append(
                    {"kind": "plan", "context": dynamic_context_index(world),
                     "receipts": receipts}
                )
                partner_requests: list[tuple[w.World, list[dict[str, Any]], int]] = []
                if world.lot == LOT:
                    for partner in workload.PARTNERS:
                        partner_receipts = _partner_stream(partner, receipts)
                        partner_index = len(dynamic_requests)
                        dynamic_requests.append(
                            {"kind": "report", "context": dynamic_context_index(partner),
                             "receipts": partner_receipts}
                        )
                        partner_requests.append((partner, partner_receipts, partner_index))
                states.append(
                    {
                        "world": world,
                        "receipts": receipts,
                        "report": report_index,
                        "plan": plan_index,
                        "partners": partner_requests,
                    }
                )

            dynamic_run = PROJECT.invoke(
                Path(artifact_dir),
                {"contexts": dynamic_contexts, "requests": dynamic_requests},
            )
            if not dynamic_run.get("ok"):
                stopped = True
                review.stopped(tuple(BUCKETS.values()), _console_error(dynamic_run))
                break
            dynamic_results = list(dynamic_run.get("results", ()))

            def dynamic_answer(index: int) -> tuple[Any, str | None]:
                if index >= len(dynamic_results):
                    return None, "the notebook returned no answer after a chamber session"
                item = dict(dynamic_results[index])
                if not item.get("ok"):
                    return None, str(item.get("error") or "the notebook stopped")
                return item.get("answer"), None

            for state in states:
                world = state["world"]
                receipts = state["receipts"]
                report_value, report_error = dynamic_answer(state["report"])
                if report_error is not None:
                    stopped = True
                    review.stopped(
                        ("crossing_failures", "range_failures", "ledger_failures",
                         "stability_failures"),
                        report_error,
                    )
                else:
                    report = dict(report_value or {})
                    _check_crossing(review, world, receipts, report, mode)
                    _check_range(review, world, receipts, report)
                    _check_ledger(review, world, receipts, report, None)

                    if world.lot == LOT:
                        trajectory_readings: dict[str, float] = {}
                        live = _number(report.get("crossing_bar"))
                        if live is not None:
                            trajectory_readings[LOT] = live
                        for partner, _partner_receipts, partner_index in state["partners"]:
                            partner_value, partner_error = dynamic_answer(partner_index)
                            if partner_error is not None:
                                stopped = True
                                review.failures["stability_failures"].append(
                                    _fail(CANDIDATE_FAILURE, error=partner_error)
                                )
                                continue
                            partner_report = dict(partner_value or {})
                            partner_reading = _number(partner_report.get("crossing_bar"))
                            if partner_reading is None:
                                review.add(
                                    "stability_failures",
                                    "crossing_missing_on_redraw",
                                    lot=LOT,
                                    other_lot=partner.lot,
                                    reported=_show(partner_report.get("crossing_bar")),
                                )
                            else:
                                trajectory_readings[partner.lot] = partner_reading
                        if live is None:
                            partner = next(
                                (item for item in workload.PARTNERS
                                 if item.lot in trajectory_readings),
                                None,
                            )
                            if partner is not None:
                                review.add(
                                    "stability_failures",
                                    "crossing_missing_on_live_lot",
                                    lot=LOT,
                                    other_lot=partner.lot,
                                    reported=_show(report.get("crossing_bar")),
                                    other_bar=_bar(trajectory_readings[partner.lot]),
                                )
                        _check_stability(review, trajectory_readings)

                plan_value, plan_error = dynamic_answer(state["plan"])
                if plan_error is not None:
                    stopped = True
                    review.failures["plan_failures"].append(
                        _fail(CANDIDATE_FAILURE, error=plan_error)
                    )
                    continue
                _check_plan(review, world, receipts, plan_value)
                frontier.extend(
                    (world, successor)
                    for successor in _trajectory_successors(
                        world, receipts, plan_value, depth + 1
                    )
                )

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_lot(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "lot": LOT,
            "sessions_charged": len(stream),
            "lots_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def snapshot(world: w.World, record: Mapping[str, Any]) -> dict[str, Any]:
    "The lot's evidence as it stood at the end of one recorded working day."

    through = str(record["through_batch"])
    context = world.context()
    context["runs"] = [row for row in context["runs"] if str(row["batch"]) <= through]
    context["bench_sheet"] = [
        row for row in context["bench_sheet"] if str(row["batch"]) <= through
    ]
    return context


def _ladder_view(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Units and leaks by batch and cartridge, as the reporting job lays them out.'

    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in context["runs"]:
        if str(row["result"]) not in ("leak", "hold"):
            continue
        key = (str(row["batch"]), str(row["cartridge"]))
        entry = rows.setdefault(
            key,
            {
                "batch": key[0],
                "cartridge": key[1],
                "bench": row["bench"],
                "dwell_min": row["dwell_min"],
                "reading_bar": row["reading_bar"],
                "units": 0,
                "leaks": 0,
            },
        )
        entry["units"] += 1
        entry["leaks"] += 1 if str(row["result"]) == "leak" else 0
    return [rows[key] for key in sorted(rows)]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    stream, error = live_receipts(root)
    world = workload.CURRENT
    context = world.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("date", "operator", "record_id", "through_batch")},
        })
    return {
        "summary": (
            f"The {context['lot']} qualification, the plan's terms and the working days on record."
        ),
        "measurements": {
            "lot": context["lot"],
            "family": context["family"],
            "build_month": context["build_month"],
            "plan_hold_min": context["plan_hold_min"],
            "target_fraction": context["target_fraction"],
            "sticker_span_bar": context["sticker_span_bar"],
            "block_bar": context["block_bar"],
            "cartridges_on_the_shelf": context["cartridges_on_the_shelf"],
            "benches": context["benches"],
            "bench_out_of_service": context["bench_out_of_service"],
            "budget": context["budget"],
            "chamber_hours_spent": world.hours_spent(stream),
            "chamber_hours_left": world.hours_left(stream),
            "stores_left": world.stock_left(stream),
            "next_day_the_scheduler_holds": world.served_on(stream),
            "sessions_on_the_receipts": [
                {
                    "booking_id": item["booking_id"],
                    "bench": item["bench"],
                    "batch": item["batch"],
                    "cartridge": item["cartridge"],
                    "dwell_min": item["dwell_min"],
                    "units_asked": item["units_asked"],
                    "units_returned": item["units_returned"],
                    "hours_charged": item["hours_charged"],
                    "served_on": item["served_on"],
                    "refusal": item["refusal"],
                }
                for item in stream
            ],
            "receipt_stream": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that recorded working day ran it.'

    record = _record(record_path)
    world = workload.CURRENT
    context = snapshot(world, record)
    stream, _error = live_receipts(Path(artifact_dir))
    receipts = [
        item for item in stream if str(item["served_on"]) <= str(record.get("date", ""))
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": receipts},
            {"kind": "plan", "context": context, "receipts": receipts},
        ]},
    )
    day = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through_batch": record.get("through_batch"),
        "bench_sheet": [dict(row) for row in context["bench_sheet"]],
        "by_batch_and_cartridge": _ladder_view(context),
        "sessions_on_the_receipts": [
            {"booking_id": item["booking_id"], "cartridge": item["cartridge"],
             "dwell_min": item["dwell_min"], "units_returned": item["units_returned"],
             "hours_charged": item["hours_charged"], "refusal": item["refusal"]}
            for item in receipts
        ],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} working day could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "lot": context["lot"]},
            "public": {"day": day, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} working day ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "lot": context["lot"],
            "batches_through": record.get("through_batch"),
            "plan_hold_min": context["plan_hold_min"],
            "sticker_span_bar": context["sticker_span_bar"],
        },
        "public": {
            "day": day,
            "report_returned": results[0] if results else None,
            "next_block_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_session(
    artifact_dir: Path,
    bench: Any,
    batch: Any,
    cartridge: Any,
    dwell_min: Any,
    units: Any,
    booking_id: Any,
) -> Mapping[str, Any]:
    stream, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return w.collect(
        Path(artifact_dir), workload.CURRENT, bench, batch, cartridge, dwell_min,
        units, booking_id,
    )


def starting_receipts() -> dict[str, Any]:
    'The receipt stream the review starts from: the sheet the desk handed back.'

    return {
        "lot": workload.CURRENT.lot,
        "entries": w.opening_stream(workload.CURRENT),
    }
