'Read one delivered planning notebook against the network it is a sheet for.'

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import ledger as ledger_module
from . import oracle, workload
from . import world as w
from .world import AREAS, WINDOWS


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-dispatch-desk-",
    timeout=60.0,
)
_CACHE = AnalysisCache()

CURRENT = workload.CURRENT

BUCKETS: Mapping[str, str] = {
    "area_window_demand_within_tolerance": "demand_failures",
    "range_covers_and_meets_floor": "range_failures",
    "demand_invariant_to_lag_and_transfer": "move_failures",
    "booking_feasible_and_covers": "plan_failures",
    "report_reconciles_settlements": "ledger_failures",
}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "area_window_demand_within_tolerance": (
        "report_is_about_the_wrong_shift",
        "demand_is_not_a_sheet",
        "demand_reads_stale_shift",
        "demand_double_counts_zone",
        "demand_uses_the_smoothed_column",
        "demand_disagrees",
        "shift_total_disagrees",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "range_is_not_centered",
        "range_narrower_than_the_calendar_allows",
        "range_adds_the_areas_apart",
        "range_degenerately_wide",
        "range_misses_the_shift",
        "candidate_execution_failed",
    ),
    "demand_invariant_to_lag_and_transfer": (
        "demand_tracks_the_lagging_area",
        "demand_tracks_the_transfer_date",
        "candidate_execution_failed",
    ),
    "booking_feasible_and_covers": (
        "booked_order_was_harmful",
        "booking_is_not_a_van_sheet",
        "booking_leaves_a_window_empty",
        "booking_over_cap",
        "booking_over_allowance",
        "booking_under_the_carrier_minimum",
        "booking_books_the_middle",
        "booking_costs_more_than_it_saves",
        "stopped_with_allowance_left",
        "candidate_execution_failed",
    ),
    "report_reconciles_settlements": (
        "ledger_unreadable",
        "settlements_are_not_a_ledger",
        "shift_counted_twice",
        "settlement_not_on_the_ledger",
        "receipt_missing",
        "refusal_uncounted",
        "candidate_execution_failed",
    ),
}


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(world: w.World) -> dict[str, str]:
    'The campaign an incident happened on, and what is its own about it.'

    return {
        "campaign": world.campaign,
        "desk": world.label,
        "desk_note": (
            "the week on my own desk"
            if world.campaign == CURRENT.campaign
            else "its own zones on its own shifts against its own allowance"
        ),
    }


def _here(record: Mapping[str, Any]) -> bool:
    return (
        str(record.get("kind")) == CANDIDATE_FAILURE
        or record.get("campaign") == CURRENT.campaign
    )


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign") == CURRENT.campaign else 1,
    )


def first_failing_state(
    batches: Sequence[tuple[str, int, Sequence[Mapping[str, Any]]]],
) -> list[dict[str, Any]]:
    "Of one campaign's booking states, the first one that went wrong."

    first: dict[str, int] = {}
    for campaign, index, records in batches:
        if records and (campaign not in first or index < first[campaign]):
            first[campaign] = index
    kept: list[dict[str, Any]] = []
    for campaign, index, records in batches:
        if records and first.get(campaign) == index:
            kept.extend(dict(record) for record in records)
    return kept


def reported(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "The incidents a report is written from, the desk's own campaign first."

    ordered = sorted(records, key=_report_order)
    here = [dict(record) for record in ordered if _here(record)]
    return here if here else [dict(record) for record in ordered]


def _number(value: Any) -> Fraction | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def drops(value: Any) -> str:
    read = _number(value)
    return show(value) if read is None else format(float(read), ".0f")


def _span(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        _number(item) is not None for item in value
    ):
        return f"{drops(value[0])} to {drops(value[1])}"
    return show(value)


def _order_text(order: Mapping[tuple[str, str], int]) -> str:
    return ", ".join(
        f"{area} {window} {order[(area, window)]}"
        for area in AREAS
        for window in WINDOWS
        if (area, window) in order
    )


def _demand_rows(report: Mapping[str, Any]) -> dict[tuple[str, str], Fraction] | None:
    rows = report.get("demand")
    if not isinstance(rows, list) or len(rows) != len(AREAS) * len(WINDOWS):
        return None
    read: dict[tuple[str, str], Fraction] = {}
    for row in rows:
        area, window = row.get("area"), row.get("window")
        value = _number(row.get("drops"))
        if area not in AREAS or window not in WINDOWS or value is None:
            return None
        if (area, window) in read:
            return None
        read[(str(area), str(window))] = value
    return read


def _demand_failures(
    world: w.World,
    shift: str,
    report: Mapping[str, Any],
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> list[dict[str, Any]]:
    where = _where(world)
    if str(report.get("shift_id")) != str(shift):
        return [
            _fail(
                "report_is_about_the_wrong_shift",
                **where,
                reported_shift=show(report.get("shift_id")),
                shift=str(shift),
            )
        ]
    read = _demand_rows(report)
    if read is None:
        return [
            _fail(
                "demand_is_not_a_sheet",
                **where,
                shift=str(shift),
                reported=show(report.get("demand")),
            )
        ]
    network = {
        (str(row["area"]), str(row["as_of_shift"])): int(row["drops_fcst_network"])
        for row in world.network_rows(arrangement, moved_to)
    }
    found: list[dict[str, Any]] = []
    for area in AREAS:
        for window in WINDOWS:
            value = read[(area, window)]
            right = oracle.truth(world, shift, area, window, arrangement, moved_to)
            if abs(value - right) <= oracle.TOLERANCE * right:
                continue
            told = {
                **where,
                "shift": str(shift),
                "area": area,
                "window": window,
                "reported": drops(float(value)),
                "network_line": network.get((area, str(shift)), 0),
                "moved_zone": str(world.moved_zone or "none"),
                "stamp_shift": world.stamp_for(area, shift, arrangement),
            }
            kind = "demand_disagrees"
            for name, decoy in oracle.misreadings(
                world, shift, area, window, arrangement, moved_to
            ):
                if abs(value - decoy) <= oracle.DECOY * right:
                    kind = name
                    break
            found.append(_fail(kind, **told))


    total = report.get("shift_total")
    total = total if isinstance(total, Mapping) else {}
    reported_total = _number(total.get("drops"))
    right_total = oracle.total_truth(world, shift, arrangement, moved_to)
    window_total = sum(read.values())
    if (
        reported_total is None
        or abs(reported_total - right_total) > oracle.TOLERANCE * right_total
        or abs(reported_total - window_total) > Fraction(1, 1_000_000)
    ):
        found.append(
            _fail(
                "shift_total_disagrees",
                **where,
                shift=str(shift),
                area="the network",
                window="the whole shift",
                reported=drops(total.get("drops")),
                window_total=drops(float(window_total)),
                network_line=sum(network.get((area, str(shift)), 0) for area in AREAS),
            )
        )
    return found


def _range_failures(
    world: w.World,
    shift: str,
    report: Mapping[str, Any],
    arrangement: str = "as issued",
    moved_to: int | None = None,
) -> list[dict[str, Any]]:
    where = _where(world)
    rows = report.get("demand")
    total = report.get("shift_total") or {}
    found: list[dict[str, Any]] = []
    read = _demand_rows(report) if isinstance(rows, list) else None
    def interval(span: Any, centre: Any) -> tuple[float, float] | None:
        if (
            not isinstance(span, list)
            or len(span) != 2
            or any(_number(item) is None for item in span)
            or _number(span[0]) > _number(span[1])
        ):
            return None
        middle = _number(centre)
        if middle is not None and not (
            _number(span[0]) <= middle <= _number(span[1])
        ):
            return None
        return float(span[0]), float(span[1])

    if read is None:
        return [
            _fail(
                "range_is_not_an_interval",
                **where,
                shift=str(shift),
                area=AREAS[0],
                window=WINDOWS[0],
                reported_range=show(rows),
                shift_total_range=_span(total.get("drops_range")),
            )
        ]
    by_key = {(str(row.get("area")), str(row.get("window"))): row for row in rows}
    for area in AREAS:
        for window in WINDOWS:
            row = by_key[(area, window)]
            told = {
                **where,
                "shift": str(shift),
                "area": area,
                "window": window,
                "reported_range": _span(row.get("drops_range")),
                "shift_total_range": _span(total.get("drops_range")),
            }
            span = interval(row.get("drops_range"), row.get("drops"))
            if span is None:
                found.append(_fail("range_is_not_an_interval", **told))
                continue
            middle = float(row["drops"])
            if abs((middle - span[0]) - (span[1] - middle)) > 1e-6 * max(
                1.0, span[1] - span[0]
            ):
                found.append(_fail("range_is_not_centered", **told))
                continue
            half = (span[1] - span[0]) / 2.0
            floor, ceiling = oracle.half_band(
                world, shift, area, window, arrangement=arrangement, moved_to=moved_to
            )
            if half < floor:
                found.append(_fail("range_narrower_than_the_calendar_allows", **told))
                continue
            if half > ceiling:
                found.append(_fail("range_degenerately_wide", **told))
                continue
    told_total = {
        **where,
        "shift": str(shift),
        "area": "the network",
        "window": "the whole shift",
        "reported_range": _span(total.get("drops_range")),
        "shift_total_range": _span(total.get("drops_range")),
    }
    span = interval(total.get("drops_range"), total.get("drops"))
    if span is None:
        found.append(_fail("range_is_not_an_interval", **told_total))
        return found
    middle = float(total["drops"])
    if abs((middle - span[0]) - (span[1] - middle)) > 1e-6 * max(
        1.0, span[1] - span[0]
    ):
        found.append(_fail("range_is_not_centered", **told_total))
        return found
    half = (span[1] - span[0]) / 2.0
    floor, ceiling = oracle.total_half_band(
        world, shift, arrangement=arrangement, moved_to=moved_to
    )
    if half < floor:
        found.append(_fail("range_adds_the_areas_apart", **told_total))
    elif half > ceiling:
        found.append(_fail("range_degenerately_wide", **told_total))
    return found


def _coverage_failures(
    world: w.World, shift: str, report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'Did the ranges the notebook gives for a settled shift hold that shift?'

    where = _where(world)
    rows = report.get("demand")
    read = _demand_rows(report) if isinstance(rows, list) else None
    if read is None or str(report.get("shift_id")) != str(shift):
        return []
    by_key = {(str(row.get("area")), str(row.get("window"))): row for row in rows}
    total = report.get("shift_total") or {}
    found: list[dict[str, Any]] = []
    for area in AREAS:
        for window in WINDOWS:
            row = by_key[(area, window)]
            span = row.get("drops_range")
            if not isinstance(span, list) or len(span) != 2 or any(
                _number(item) is None for item in span
            ):
                continue
            right = oracle.truth(world, shift, area, window)
            value = read[(area, window)]
            if abs(value - right) > oracle.TOLERANCE * right:
                continue
            settled = world.metered(area, shift, window)
            if not (float(span[0]) <= settled <= float(span[1])):
                found.append(
                    _fail(
                        "range_misses_the_shift",
                        **where,
                        shift=str(shift),
                        area=area,
                        window=window,
                        reported_range=_span(span),
                        shift_total_range=_span(total.get("drops_range")),
                        metered=settled,
                    )
                )
    span = total.get("drops_range")
    value = _number(total.get("drops"))
    right = oracle.total_truth(world, shift)
    if (
        isinstance(span, list)
        and len(span) == 2
        and all(_number(item) is not None for item in span)
        and value is not None
        and abs(value - right) <= oracle.TOLERANCE * right
    ):
        settled = sum(
            world.metered(area, shift, window) for area in AREAS for window in WINDOWS
        )
        if not (float(span[0]) <= settled <= float(span[1])):
            found.append(
                _fail(
                    "range_misses_the_shift",
                    **where,
                    shift=str(shift),
                    area="the network",
                    window="the whole shift",
                    reported_range=_span(span),
                    shift_total_range=_span(span),
                    metered=settled,
                )
            )
    return found


def _move_failures(
    world: w.World,
    shift: str,
    base: Mapping[str, Any],
    variants: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    where = _where(world)
    anchor = _demand_rows(base)
    if anchor is None:
        return []
    found: list[dict[str, Any]] = []
    for arrangement, kind in (
        ("lag", "demand_tracks_the_lagging_area"),
        ("move", "demand_tracks_the_transfer_date"),
    ):
        report = variants.get(arrangement)
        if report is None:
            continue
        again = _demand_rows(report)
        if again is None:
            continue
        for area in AREAS:
            for window in WINDOWS:
                right = oracle.truth(world, shift, area, window)
                gap = abs(again[(area, window)] - anchor[(area, window)])
                if gap <= oracle.MOVE_TOLERANCE * right:
                    continue
                found.append(
                    _fail(
                        kind,
                        **where,
                        shift=str(shift),
                        area=area,
                        window=window,
                        reported=drops(float(anchor[(area, window)])),
                        reported_again=drops(float(again[(area, window)])),
                        moved=drops(float(gap)),
                        what_changed=w.arrangement_note(arrangement),
                    )
                )
    return found


def _ledger_failures(
    world: w.World,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    ledger_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(world)
    if ledger_error:
        return [_fail("ledger_unreadable", **where, reason=str(ledger_error))]
    rows = report.get("settlements")
    charged = {str(entry["order_id"]): entry for entry in entries}
    if not isinstance(rows, list):
        return [
            _fail(
                "settlements_are_not_a_ledger",
                **where,
                reported=show(rows),
                settled_orders=len(entries),
            )
        ]
    seen: dict[str, int] = {}
    for row in rows:
        key = str(row.get("order_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [
                _fail(
                    "shift_counted_twice",
                    **where,
                    order_id=key,
                    times_reported=seen[key],
                    settled_orders=len(entries),
                )
            ]
        entry = charged.get(key)
        booked = _number(row.get("van_hours_charged"))
        if (
            entry is None
            or str(row.get("shift_id")) != str(entry["shift_id"])
            or booked is None
            or abs(float(booked) - float(entry["van_hours_charged"])) > 1e-6
        ):
            return [
                _fail(
                    "settlement_not_on_the_ledger",
                    **where,
                    order_id=key,
                    settled_orders=len(entries),
                )
            ]
    for key, entry in charged.items():
        if key in seen:
            continue
        kind = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        return [
            _fail(
                kind,
                **where,
                order_id=key,
                shift=str(entry["shift_id"]),
                van_hours_charged=float(entry["van_hours_charged"]),
                settled_orders=len(entries),
            )
        ]
    return []


def delivered_sheet(
    world: w.World, shift: str, report: Any
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    'The drops and the spread the pack itself published for one shift.'

    read = _demand_rows(report) if isinstance(report, Mapping) else None
    rows = report.get("demand") if isinstance(report, Mapping) else None
    if read is None or str(report.get("shift_id")) != str(shift):
        return (
            {
                (area, window): float(oracle.truth(world, shift, area, window))
                for area in AREAS
                for window in WINDOWS
            },
            {
                (area, window): oracle.area_spread(world, area)
                for area in AREAS
                for window in WINDOWS
            },
        )
    by_key = {(str(row.get("area")), str(row.get("window"))): row for row in rows}
    sheet: dict[tuple[str, str], float] = {}
    spread: dict[tuple[str, str], float] = {}
    for key, value in read.items():
        drops = max(float(value), 1.0)
        span = by_key[key].get("drops_range")
        share = 0.0
        if (
            isinstance(span, list)
            and len(span) == 2
            and all(_number(item) is not None for item in span)
            and float(span[1]) > float(span[0])
        ):
            share = min(
                (float(span[1]) - float(span[0])) / (4.0 * drops), oracle.MAX_SPREAD
            )
        sheet[key] = drops
        spread[key] = share
    return sheet, spread


def _plan_failures(
    world: w.World,
    entries: Sequence[Mapping[str, Any]],
    offered: Any,
    pack: Any = None,
    check_cost: bool = True,
) -> list[dict[str, Any]]:
    where = _where(world)
    left = oracle.allowance_left(world, entries)
    shift = oracle.next_shift(world, entries)
    stop_allowed = oracle.stop_is_right(world, entries)
    told = {
        **where,
        "shift": str(shift),
        "allowance_left": left,
        "van_cap": world.van_cap,
        "minimum_booking": world.minimum_booking,
        "drops_per_van": world.drops_per_van,


        "spill_multiple": (
            int(world.spill_multiple)
            if world.spill_multiple.denominator == 1
            else float(world.spill_multiple)
        ),
    }
    orders = offered if isinstance(offered, list) else [offered]
    if not orders:
        return [_fail("booking_is_not_a_van_sheet", **told, reported=show(offered))]
    for raw in orders:
        if isinstance(raw, str):
            if raw.strip().lower() != "stop":
                return [_fail("booking_is_not_a_van_sheet", **told, reported=show(raw))]
            if not stop_allowed:
                return [_fail("stopped_with_allowance_left", **told, reported="stop")]
            continue
        if not isinstance(raw, list) or not raw:
            return [_fail("booking_is_not_a_van_sheet", **told, reported=show(raw))]
        order: dict[tuple[str, str], int] = {}
        for line in raw:
            area, window = line.get("area"), line.get("window")
            vans = _number(line.get("vans"))
            if (
                area not in AREAS
                or window not in WINDOWS
                or vans is None
                or vans.denominator != 1
                or (area, window) in order
            ):
                return [_fail("booking_is_not_a_van_sheet", **told, reported=show(line))]
            order[(str(area), str(window))] = int(vans)
        if len(order) != len(AREAS) * len(WINDOWS):
            return [
                _fail(
                    "booking_is_not_a_van_sheet",
                    **told,
                    reported=", ".join(f"{area} {window}" for area, window in sorted(order)),
                )
            ]
        reported_order = _order_text(order)
        empty = [key for key, vans in sorted(order.items()) if vans <= 0]
        if empty:
            return [
                _fail(
                    "booking_leaves_a_window_empty",
                    **told,
                    area=empty[0][0],
                    window=empty[0][1],
                    reported=reported_order,
                )
            ]
        over = [key for key, vans in sorted(order.items()) if vans > world.van_cap]
        if over:
            return [
                _fail(
                    "booking_over_cap",
                    **told,
                    area=over[0][0],
                    window=over[0][1],
                    vans=order[over[0]],
                    reported=reported_order,
                )
            ]
        asked = sum(order.values())
        if asked > left:
            return [
                _fail("booking_over_allowance", **told, vans_asked_for=asked, reported=reported_order)
            ]
        if asked < world.minimum_booking:
            return [
                _fail(
                    "booking_under_the_carrier_minimum",
                    **told,
                    vans_asked_for=asked,
                    reported=reported_order,
                )
            ]
        if shift is None:
            return [
                _fail("booking_over_allowance", **told, vans_asked_for=asked, reported=reported_order)
            ]
        if not check_cost:
            continue
        sheet, spread = delivered_sheet(world, shift, pack)
        improvement = oracle.delivered_local_improvement(world, sheet, spread, order, left)
        if improvement > oracle.LOCAL_IMPROVEMENT_TOLERANCE:
            middle = oracle.delivered_middle(world, sheet)
            low = [key for key in order if order[key] <= middle[key]]
            kind = (
                "booking_books_the_middle" if low else "booking_costs_more_than_it_saves"
            )
            return [
                _fail(
                    kind,
                    **told,
                    vans_asked_for=asked,
                    reported=reported_order,
                    area=(sorted(low)[0][0] if low else AREAS[0]),
                    window=(sorted(low)[0][1] if low else WINDOWS[0]),
                )
            ]
    return []


_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(run: Mapping[str, Any]) -> str:
    'Describe a failed batch without echoing candidate-controlled output.'

    reported_line = str(run.get("error") or "no output").strip()
    if reported_line.startswith(_TIMEOUT_PHRASE):
        return "the planning notebook was still running when the console stopped it"
    if reported_line.startswith("candidate process exited"):
        return "the planning notebook process exited before returning the batch"
    if reported_line.startswith(
        ("candidate returned invalid JSON", "candidate returned non-object")
    ):
        return "the planning notebook ended without returning a readable batch"
    return "the planning notebook stopped before it returned a complete batch"


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The shifts this desk has been charged for, or why the ledger will not read.'

    try:
        return ledger_module.read_receipts(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def arrangements_of(world: w.World) -> tuple[str, ...]:
    "The arrangements this campaign's own sheets can actually reach."

    if world.spec.get("early_area") is None and world.moved_zone is None:
        return ("as issued",)
    return w.ARRANGEMENTS


def campaigns(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "The desk's own week with the ledger it holds, then the campaigns behind it."

    rows = [
        {
            "world": CURRENT,
            "entries": [dict(entry) for entry in live],
            "plan_limit": len(CURRENT.shifts),
        }
    ]
    for world in (*workload.LATER, workload.OUT_OF_REGIME):
        rows.append(
            {
                "world": world,
                "entries": workload.settled_stream(world),
                "plan_limit": len(world.shifts),
            }
        )
    return rows


def variant_entries(
    world: w.World,
    entries: Sequence[Mapping[str, Any]],
    arrangement: str,
    moved_to: int | None,
) -> list[dict[str, Any]]:
    'The same orders, settled against the same network under the arrangement.'

    return ledger_module.replay(world, ledger_module.orders_of(entries), arrangement, moved_to)


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every campaign and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        live, ledger_error = live_ledger(Path(artifact_dir))
        rows = campaigns(live)
        contexts: dict[str, Any] = {}
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], str, int | None, dict[str, int]]] = []
        looks: list[tuple[w.World, str, int]] = []
        plans: list[tuple[w.World, list[dict[str, Any]], int, int, int]] = []
        actual_orders: list[
            tuple[w.World, list[dict[str, Any]], dict[str, Any], int]
        ] = []
        for row in rows:
            world = row["world"]
            shift = oracle.next_shift(world, row["entries"])
            moved_to = None if shift is None else world.index_of(shift)
            index: dict[str, int] = {}
            for arrangement in arrangements_of(world):
                key = f"{world.campaign}|{arrangement}"
                contexts[key] = world.public_context(
                    arrangement, moved_to if arrangement == "move" else None
                )
                entries = (
                    row["entries"]
                    if arrangement == "as issued"
                    else variant_entries(
                        world,
                        row["entries"],
                        arrangement,
                        moved_to if arrangement == "move" else None,
                    )
                )
                index[arrangement] = len(requests)
                requests.append({"kind": "report", "context": key, "receipts": entries})
            reports.append((row, str(shift), moved_to, index))


            past = ledger_module.replay(world, workload.settled_orders(world)[:5])
            past_shift = oracle.next_shift(world, past)
            looks.append((world, str(past_shift), len(requests)))
            requests.append(
                {
                    "kind": "report",
                    "context": f"{world.campaign}|as issued",
                    "receipts": past,
                }
            )
            for step, state in enumerate(
                oracle.plan_states(world, row["entries"], row["plan_limit"])
            ):


                plans.append(
                    (world, list(state["entries"]), len(requests), len(requests) + 1, step)
                )
                requests.append(
                    {
                        "kind": "plan",
                        "context": f"{world.campaign}|as issued",
                        "receipts": state["entries"],
                    }
                )
                requests.append(
                    {
                        "kind": "report",
                        "context": f"{world.campaign}|as issued",
                        "receipts": state["entries"],
                    }
                )


        authored = workload.settled_stream(CURRENT)
        if ledger_error is None:
            for offset in range(len(authored), len(live)):
                prior = [dict(entry) for entry in live[:offset]]
                actual_orders.append((CURRENT, prior, dict(live[offset]), len(requests)))
                requests.append(
                    {
                        "kind": "report",
                        "context": f"{CURRENT.campaign}|as issued",
                        "receipts": prior,
                    }
                )

        run = PROJECT.invoke(Path(artifact_dir), {"contexts": contexts, "requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CURRENT.campaign, "shifts_settled": len(live)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(position: int) -> tuple[Any, str | None]:
            request_kind = (
                str(requests[position].get("kind"))
                if 0 <= position < len(requests)
                else "request"
            )
            answer_kind = "order" if request_kind == "plan" else "report"
            if position >= len(results):
                return None, f"the planning notebook returned no answer for one {answer_kind}"
            item = dict(results[position])
            if not item.get("ok"):
                return None, f"the planning notebook stopped while producing one {answer_kind}"
            return item.get("answer"), None

        stopped = False
        for row, shift, moved_to, index in reports:
            world, entries = row["world"], row["entries"]
            value, error = answer(index["as issued"])
            if error is not None:
                stopped = True
                for bucket in ("demand_failures", "range_failures", "ledger_failures",
                               "move_failures"):
                    failures[bucket].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            report = dict(value or {})
            failures["demand_failures"].extend(_demand_failures(world, shift, report))
            failures["range_failures"].extend(_range_failures(world, shift, report))
            failures["ledger_failures"].extend(
                _ledger_failures(
                    world, entries, report, ledger_error if world is CURRENT else None
                )
            )
            variants: dict[str, Mapping[str, Any]] = {}
            for arrangement in ("lag", "move"):
                if arrangement not in index:
                    continue
                other, other_error = answer(index[arrangement])
                if other_error is not None:
                    stopped = True
                    failures["move_failures"].append(_fail(CANDIDATE_FAILURE, error=other_error))
                else:
                    variants[arrangement] = dict(other or {})
            failures["move_failures"].extend(_move_failures(world, shift, report, variants))
        for world, past_shift, position in looks:
            value, error = answer(position)
            if error is not None:
                stopped = True
                failures["range_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            failures["range_failures"].extend(
                _coverage_failures(world, past_shift, dict(value or {}))
            )
        for world, entries, receipt, position in actual_orders:
            pack, error = answer(position)
            lines = [
                {
                    "area": line.get("area"),
                    "window": line.get("window"),
                    "vans": line.get("vans_booked"),
                }
                for line in receipt.get("lines", ())
            ]
            expected_shift = oracle.next_shift(world, entries)
            reasons = (
                [_fail(CANDIDATE_FAILURE, error=error)]
                if error is not None
                else _plan_failures(world, entries, [lines], pack)
            )
            if str(receipt.get("shift_id")) != str(expected_shift):
                reasons.insert(0, _fail("report_is_about_the_wrong_shift"))
            if reasons:
                failures["plan_failures"].append(
                    _fail(
                        "booked_order_was_harmful",
                        **_where(world),
                        order_id=str(receipt.get("order_id")),
                        shift=str(receipt.get("shift_id")),
                        van_hours_charged=float(receipt.get("van_hours_charged", 0)),
                        allowance_left_after=int(receipt.get("allowance_left_after", 0)),
                        vans_short=int(receipt.get("vans_short", 0)),
                        receipt_outcome=(
                            f"the carrier handed it back: {receipt.get('refusal')}"
                            if receipt.get("refusal")
                            else (
                                f"{int(receipt.get('vans_idle', 0))} vans idle and "
                                f"{int(receipt.get('vans_short', 0))} vans short"
                            )
                        ),
                        reason=str(reasons[0].get("kind")),
                    )
                )
        plan_batches: list[tuple[str, int, list[dict[str, Any]]]] = []
        continuation_batches: dict[
            str, list[tuple[str, int, list[dict[str, Any]]]]
        ] = {
            "demand_failures": [],
            "range_failures": [],
            "ledger_failures": [],
        }
        for world, entries, position, pack_position, step in plans:
            value, error = answer(position)
            pack, pack_error = answer(pack_position)
            if step > 0:
                if pack_error is not None:
                    stopped = True
                    for bucket in ("demand_failures", "range_failures", "ledger_failures"):
                        continuation_batches[bucket].append(
                            (
                                world.campaign,
                                step,
                                [_fail(CANDIDATE_FAILURE, **_where(world), error=pack_error)],
                            )
                        )
                else:
                    state_report = dict(pack or {})
                    state_shift = str(oracle.next_shift(world, entries))
                    continuation_batches["demand_failures"].append(
                        (
                            world.campaign,
                            step,
                            _demand_failures(world, state_shift, state_report),
                        )
                    )
                    continuation_batches["range_failures"].append(
                        (
                            world.campaign,
                            step,
                            _range_failures(world, state_shift, state_report),
                        )
                    )
                    continuation_batches["ledger_failures"].append(
                        (
                            world.campaign,
                            step,
                            _ledger_failures(world, entries, state_report, None),
                        )
                    )
            if error is not None:
                stopped = True
                plan_batches.append(
                    (world.campaign, step, [_fail(CANDIDATE_FAILURE, error=error)])
                )
                continue
            plan_batches.append(
                (
                    world.campaign,
                    step,
                    _plan_failures(
                        world,
                        entries,
                        value,
                        pack,
                        check_cost=pack_error is None,
                    ),
                )
            )
        for bucket, batches in continuation_batches.items():
            already_failed = {
                str(record.get("campaign"))
                for record in failures[bucket]
                if record.get("campaign") is not None
            }
            eligible = [row for row in batches if row[0] not in already_failed]
            failures[bucket].extend(first_failing_state(eligible))
        failures["plan_failures"].extend(first_failing_state(plan_batches))

        analysis: dict[str, Any] = {
            bucket: reported(records) for bucket, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT.campaign,
            "shifts_settled": len(live),
            "campaigns_read": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "order_id",
            "shift_id",
            "lines",
            "vans_idle",
            "windows_short",
            "vans_short",
            "spill_charge",
            "van_hours_charged",
            "allowance_left_after",
            "refusal",
        )
    }


def snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    "The desk's evidence as it stood at the end of one past working day."

    through = str(record["through_shift"])
    context = CURRENT.public_context()
    for key in ("harbour_rows", "ridge_rows", "network_rows"):
        context[key] = [row for row in context[key] if row["as_of_shift"] <= through]
    return context


def _record_ledger(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = list(record.get("orders_settled", ()))
    orders = [
        entry for entry in workload.settled_orders(CURRENT) if str(entry[0]) in set(held)
    ]
    return ledger_module.replay(CURRENT, orders) if orders else []


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = CURRENT.public_context()
    entries, error = live_ledger(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "operator", "through_shift")},
            }
        )
    return {
        "summary": (
            f"The {context['campaign']} calendar, the carrier terms and the working days on record."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "shifts": context["shifts"],
            "areas": context["areas"],
            "windows": context["windows"],
            "agreement": context["agreement"],
            "desk": context["desk"],
            "next_shift_without_an_order": ledger_module.next_open_shift(CURRENT, entries),
            "shifts_settled": len(ledger_module.booked_shifts(entries)),
            "allowance_left": ledger_module.allowance_left(CURRENT, entries),
            "settlement_ledger": error or "reads back in order",
            "orders_on_the_ledger": [_receipt_summary(entry) for entry in entries],
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that working day's planner ran it."

    record = _record(record_path)
    context = snapshot(record)
    entries = _record_ledger(record)
    held, _error = live_ledger(Path(artifact_dir))
    key = f"{CURRENT.campaign}|then"
    contexts = {key: context}
    requests = [
        {"kind": "report", "context": key, "receipts": entries},
        {"kind": "plan", "context": key, "receipts": entries},
    ]
    moved = [entry["order_id"] for entry in held] != [entry["order_id"] for entry in entries]
    if moved:
        now = f"{CURRENT.campaign}|now"
        contexts[now] = CURRENT.public_context()
        requests.extend(
            [
                {"kind": "report", "context": now, "receipts": held},
                {"kind": "plan", "context": now, "receipts": held},
            ]
        )
    run = PROJECT.invoke(Path(artifact_dir), {"contexts": contexts, "requests": requests})
    working_day = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_shift"),
        "harbour_rows": len(context["harbour_rows"]),
        "ridge_rows": len(context["ridge_rows"]),
        "network_line": [dict(row) for row in context["network_rows"]],
        "orders_on_the_ledger": [_receipt_summary(entry) for entry in entries],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} working day could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "campaign": context["campaign"]},
            "public": {
                "working_day": working_day,
                "console_error": run.get("error"),
                "diagnostic": run.get("diagnostic"),
            },
        }
    results = list(run.get("results", ()))
    public: dict[str, Any] = {
        "working_day": working_day,
        "report_returned": results[0] if results else None,
        "next_collection_returned": results[1] if len(results) > 1 else None,
        "stdout": run.get("stdout"),
    }
    if moved:
        public["desk_today"] = {
            "shifts_settled": len(ledger_module.booked_shifts(held)),
            "allowance_left": ledger_module.allowance_left(CURRENT, held),
            "orders_on_the_ledger": [_receipt_summary(entry) for entry in held],
            "report_returned": results[2] if len(results) > 2 else None,
            "next_collection_returned": results[3] if len(results) > 3 else None,
        }
    return {
        "summary": f"The {record.get('record_id')} working day ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "evidence_through": record.get("through_shift"),
            "orders_on_the_ledger": len(entries),
        },
        "public": public,
    }


def run_booking(artifact_dir: Path, shift: Any, order: Any, order_id: Any) -> Mapping[str, Any]:
    return ledger_module.collect(Path(artifact_dir), CURRENT, shift, order, order_id)
