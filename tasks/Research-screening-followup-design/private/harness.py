'Read one delivered review notebook against the bench it is a review of.'

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import bench, oracle, workload
from . import world as w
from .world import INCUMBENT


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-plate-screen-",
    timeout=45.0,
)
_CACHE = AnalysisCache()

CURRENT = workload.CURRENT

BUCKETS: Mapping[str, str] = {
    "selected_effect_within_tolerance": "effect_failures",
    "range_covers_and_meets_floor": "range_failures",
    "estimate_invariant_to_day_shift": "move_failures",
    "report_reconciles_receipts": "ledger_failures",
    "next_booking_identifies_under_selection": "plan_failures",
}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "selected_effect_within_tolerance": (
        "report_is_not_about_the_selected_plate",
        "effect_is_the_screen_score",
        "effect_ignores_the_day_the_runs_sat_on",
        "effect_disagrees",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_an_interval",
        "range_does_not_contain_reported_effect",
        "range_changes_when_runs_are_relisted",
        "range_narrower_than_the_runs_support",
        "range_wider_than_the_runs_support",
        "range_exceeds_review_bar",
        "range_misses_the_effect",
        "range_does_not_follow_measurement_support",
        "range_does_not_follow_observed_variability",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_day_shift": (
        "estimate_tracks_the_rig_day",
        "estimate_tracks_which_day_the_plate_ran_on",
        "effect_missing_after_recheck",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipt_stream_unreadable",
        "measurements_are_not_a_ledger",
        "charged_day_missing_from_the_report",
        "day_not_on_the_receipt_stream",
        "day_reported_twice",
        "handed_back_day_left_out",
        "candidate_execution_failed",
    ),
    "next_booking_identifies_under_selection": (
        "plan_is_not_a_day_sheet",
        "booking_names_a_part_not_on_the_shelf",
        "booking_over_the_day_caps",
        "booking_leaves_the_plate_alone_on_the_day",
        "booking_falls_short_of_the_review_bar",
        "booking_with_no_rig_days_left",
        "booking_continues_after_review_bar",
        "stopped_with_rig_days_left",
        "candidate_execution_failed",
    ),
}


WIDTH_SLACK = 1e-6


RANGE_RESPONSE_MIN_K = 0.05


VARIABILITY_RESPONSE_MIN_K = 0.05


RELIST_TOLERANCE_K = 1e-9


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(world: w.World) -> dict[str, str]:
    'The screen a failure happened on, and what is its own about it.'

    return {
        "campaign": world.campaign,
        "screen": world.label,
        "screen_note": (
            "the sheets on my own desk"
            if world.campaign == CURRENT.campaign
            else "its own plates on its own rig days against its own review note"
        ),
    }


def _here(record: Mapping[str, Any]) -> bool:
    'Whether this incident happened on the screen Marta has sheets for.'

    return record.get("campaign") == CURRENT.campaign


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident Marta can open the July sheets for first.'

    return (0 if record.get("campaign") == CURRENT.campaign else 1, 0)


def _candidate_failure(
    world: w.World, error: str, request_kind: str
) -> dict[str, Any]:
    'A stopped request, with enough provenance to report the right screen.'

    return _fail(
        CANDIDATE_FAILURE,
        **_where(world),
        error=error,
        request_kind=request_kind,
    )


def reported(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The incidents a report is written from, visible screen first.'

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
        return format(value, ".4g")
    if isinstance(value, (list, tuple)):
        return f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def kelvin(value: Any) -> str:
    read = _number(value)
    return show(value) if read is None else format(float(read), ".2f")


def _pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        _number(item) is not None for item in value
    ):
        return f"{kelvin(value[0])} to {kelvin(value[1])}"
    return show(value)


def receipt_state(receipts: Sequence[Mapping[str, Any]]) -> str:
    'Name the exact receipt prefix one report was run against.'

    if not receipts:
        return "the receipt stream before a review day was charged"
    last = receipts[-1]
    return (
        f"the receipt stream through booking {last.get('receipt_id')} "
        f"on {last.get('day_id')}"
    )


def live_stream(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The rig days this delivery was charged for, or why the stream will not read.'

    try:
        return bench.read_receipts(Path(artifact_dir), CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(world: w.World, base: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every booking state this screen can be asked for a next rig day in.'

    states = [{"label": "now", "receipts": [dict(entry) for entry in base]}]
    stream = [dict(entry) for entry in base]
    step = 0
    while not oracle.stop_is_right(world, stream) and step < len(world.open_days):
        sheet = oracle.best_sheet(world, stream)
        if not sheet:
            break
        step += 1
        stream = bench.extend(world, stream, [sheet], [f"walk-{step:02d}"])
        states.append(
            {"label": f"after {stream[-1]['day_id']}", "receipts": [dict(e) for e in stream]}
        )


    spent = [dict(entry) for entry in base]
    left = oracle.days_left(world, spent)
    if left > 0:
        sheets = [[{"part": world.selected, "runs": int(world.spec["runs_per_day"])}]] * left
        spent = bench.extend(
            world, spent, sheets, [f"spent-{index:02d}" for index in range(1, left + 1)]
        )
        states.append({"label": "rig days spent", "receipts": spent})
    return states


def range_comparison_base(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'An actual receipt prefix before the latest identifying evidence.'

    paired_positions: list[int] = []
    for position, entry in enumerate(receipts):
        returned = {
            str(part.get("part"))
            for part in entry.get("parts", ())
            if int(part.get("returned_runs", 0)) > 0
        }
        if world.selected in returned and INCUMBENT in returned:
            paired_positions.append(position)
    if not paired_positions:
        return [dict(entry) for entry in receipts]
    cutoff = paired_positions[0] + (1 if len(paired_positions) > 1 else 0)
    return [dict(entry) for entry in receipts[:cutoff]]


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The screen on the desk with the rig days it holds, then the ones behind it.'

    rows = [
        {
            "world": CURRENT,
            "receipts": [dict(entry) for entry in live],
            "plan_base": [dict(entry) for entry in live],
            "unpaired_base": workload.starting_stream()["entries"],
            "range_base": range_comparison_base(CURRENT, live),
        }
    ]
    for world in workload.LATER:
        settled = workload.settled_stream(world)["entries"]
        rows.append(
            {
                "world": world,
                "receipts": settled,
                "plan_base": [],
                "unpaired_base": [],
                "range_base": range_comparison_base(world, settled),
            }
        )
    return rows


def variant_receipts(
    world: w.World, receipts: Sequence[Mapping[str, Any]], arrangement: str
) -> list[dict[str, Any]]:
    'The same day sheets, run on the same rig under the other arrangement.'

    return bench.extend(
        world,
        [],
        bench.requests_of(receipts),
        [str(entry["receipt_id"]) for entry in receipts],
        arrangement,
    )


def variability_receipts(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Same day count and mean paired effect, with more mounting variation.'

    varied = json.loads(json.dumps(list(receipts)))
    paired: list[tuple[int, float]] = []
    for position, entry in enumerate(varied):
        plate = [float(value) for value in oracle.returned(entry, world.selected)]
        other = [float(value) for value in oracle.returned(entry, INCUMBENT)]
        if plate and other:
            paired.append(
                (position, sum(other) / len(other) - sum(plate) / len(plate))
            )
    if len(paired) < 2:
        return varied

    mean = sum(value for _position, value in paired) / len(paired)
    direction = 1.0 if paired[-1][1] >= mean else -1.0
    last_shift = 0.4 * direction
    shifts = [-last_shift / (len(paired) - 1)] * (len(paired) - 1) + [last_shift]
    for (position, _value), shift in zip(paired, shifts):
        for part in varied[position]["parts"]:
            if str(part.get("part")) != INCUMBENT or not part.get("returned_runs"):
                continue
            part["rise_K"] = [format(float(value) + shift, ".6g") for value in part["rise_K"]]


    sealed: list[dict[str, Any]] = []
    for sequence, entry in enumerate(varied, start=1):
        body = {
            key: value
            for key, value in entry.items()
            if key not in {"sequence", "previous", "seal"}
        }
        sealed.append(bench.sealed(body, sequence, sealed[-1]["seal"] if sealed else ""))
    return sealed


def _effect_failures(
    world: w.World, receipts: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    where = _where(world)
    truth = oracle.truth(world)
    plate = report.get("plate")
    if plate != world.selected:
        return [
            _fail(
                "report_is_not_about_the_selected_plate",
                **where,
                plate=show(plate),
                selected_plate=world.selected,
            )
        ]
    reported = _number(report.get("effect_K"))
    told = {
        **where,
        "plate": world.selected,
        "reported": kelvin(report.get("effect_K")),
        "reference_gap": kelvin(float(oracle.coupon_gap(world))),
    }
    if reported is None:
        return [_fail("effect_disagrees", **told)]
    if abs(reported - truth) <= oracle.TOLERANCE:
        return []
    for kind, value in oracle.misreadings(world, receipts):
        if abs(reported - value) <= oracle.DECOY_TOLERANCE:
            return [_fail(kind, **told)]
    return [_fail("effect_disagrees", **told)]


def _range_failures(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    *,
    terminal: bool = True,
) -> list[dict[str, Any]]:
    where = _where(world)
    state = receipt_state(receipts)
    bounds = report.get("effect_range_K")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(_number(item) is None for item in bounds)
        or bounds[0] > bounds[1]
    ):
        return [
            _fail(
                "range_is_not_an_interval",
                **where,
                plate=world.selected,
                reported=_pair(bounds),
                receipt_state=state,
            )
        ]
    low, high = float(bounds[0]), float(bounds[1])
    floor, ceiling = oracle.range_band(world, receipts)
    half = (high - low) / 2.0
    effect = _number(report.get("effect_K"))
    told = {
        **where,
        "plate": world.selected,
        "reported_range": _pair(bounds),
        "reported_effect": kelvin(report.get("effect_K")),
        "reported_width": kelvin(high - low),
        "range_width_wanted": kelvin(oracle.bar(world)),
        "runs_on_the_plate": sum(oracle.plate_days(world, receipts).values()),
        "reference_gap": kelvin(float(oracle.coupon_gap(world))),
        "receipt_state": state,
    }
    if effect is not None and not (low <= float(effect) <= high):
        return [_fail("range_does_not_contain_reported_effect", **told)]
    if half < floor - WIDTH_SLACK:
        return [_fail("range_narrower_than_the_runs_support", **told)]
    if half > ceiling + WIDTH_SLACK:
        return [_fail("range_wider_than_the_runs_support", **told)]
    if not terminal:
        return []
    if high - low > oracle.bar(world) + WIDTH_SLACK:
        return [_fail("range_exceeds_review_bar", **told)]
    truth = float(oracle.truth(world))
    if not (low <= truth <= high):
        return [_fail("range_misses_the_effect", **told)]
    return []


def _run_order_failures(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    relisted: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'The same block values cannot acquire a new range from list position.'

    original = report.get("effect_range_K")
    again = relisted.get("effect_range_K")

    def pair(value: Any) -> tuple[float, float] | None:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(_number(item) is None for item in value)
            or float(value[0]) > float(value[1])
        ):
            return None
        return float(value[0]), float(value[1])

    before, after = pair(original), pair(again)

    if before is None:
        return []
    if (
        after is not None
        and max(abs(a - b) for a, b in zip(before, after)) <= RELIST_TOLERANCE_K
    ):
        return []
    return [
        _fail(
            "range_changes_when_runs_are_relisted",
            **_where(world),
            plate=world.selected,
            reported_range=_pair(original),
            relisted_range=_pair(again),
            receipt_state=receipt_state(receipts),
        )
    ]


def _range_response_failures(
    world: w.World,
    before_receipts: Sequence[Mapping[str, Any]],
    before: Mapping[str, Any],
    after_receipts: Sequence[Mapping[str, Any]],
    after: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'The published range must change as paired evidence changes its support.'

    paired = len(oracle.paired_days(world, after_receipts))
    if paired == 0 or len(after_receipts) <= len(before_receipts):
        return []

    before_bounds = before.get("effect_range_K")
    after_bounds = after.get("effect_range_K")

    def width(value: Any) -> float | None:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(_number(item) is None for item in value)
            or float(value[0]) > float(value[1])
        ):
            return None
        return float(value[1]) - float(value[0])

    before_width = width(before_bounds)
    after_width = width(after_bounds)
    if (
        before_width is not None
        and after_width is not None
        and abs(before_width - after_width) >= RANGE_RESPONSE_MIN_K - WIDTH_SLACK
    ):
        return []
    return [
        _fail(
            "range_does_not_follow_measurement_support",
            **_where(world),
            plate=world.selected,
            before_range=_pair(before_bounds),
            after_range=_pair(after_bounds),
            before_width=kelvin(before_width),
            after_width=kelvin(after_width),
            paired_days=paired,
            before_receipt_state=receipt_state(before_receipts),
            after_receipt_state=receipt_state(after_receipts),
        )
    ]


def _range_width(report: Mapping[str, Any]) -> float | None:
    bounds = report.get("effect_range_K")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(_number(item) is None for item in bounds)
        or float(bounds[0]) > float(bounds[1])
    ):
        return None
    return float(bounds[1]) - float(bounds[0])


def _paired_contrasts(
    world: w.World, receipts: Sequence[Mapping[str, Any]]
) -> list[float]:
    found: list[float] = []
    for entry in receipts:
        plate = [float(value) for value in oracle.returned(entry, world.selected)]
        other = [float(value) for value in oracle.returned(entry, INCUMBENT)]
        if plate and other:
            found.append(sum(other) / len(other) - sum(plate) / len(plate))
    return found


def _sample_spread(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5


def _range_variability_failures(
    world: w.World,
    base_receipts: Sequence[Mapping[str, Any]],
    base: Mapping[str, Any],
    varied_receipts: Sequence[Mapping[str, Any]],
    varied: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'A range must react when observed mounting spread changes at fixed n.'

    base_days = _paired_contrasts(world, base_receipts)
    varied_days = _paired_contrasts(world, varied_receipts)
    if len(base_days) < 2 or len(base_days) != len(varied_days):
        return []
    before_width = _range_width(base)
    after_width = _range_width(varied)
    before_spread = _sample_spread(base_days)
    after_spread = _sample_spread(varied_days)
    if (
        before_width is not None
        and after_width is not None
        and after_width - before_width >= VARIABILITY_RESPONSE_MIN_K - WIDTH_SLACK
    ):
        return []
    return [
        _fail(
            "range_does_not_follow_observed_variability",
            **_where(world),
            plate=world.selected,
            before_range=_pair(base.get("effect_range_K")),
            after_range=_pair(varied.get("effect_range_K")),
            before_width=kelvin(before_width),
            after_width=kelvin(after_width),
            before_spread=kelvin(before_spread),
            after_spread=kelvin(after_spread),
            paired_days=len(base_days),
            receipt_state=receipt_state(base_receipts),
        )
    ]


def _ledger_failures(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    stream_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(world)
    if stream_error:
        return [_fail("receipt_stream_unreadable", **where, reason=str(stream_error))]
    rows = report.get("measurements")
    charged = {str(entry["receipt_id"]): entry for entry in receipts}
    if not isinstance(rows, list):
        return [
            _fail(
                "measurements_are_not_a_ledger",
                **where,
                reported=show(rows),
                charged_days=len(receipts),
            )
        ]
    seen: dict[str, int] = {}
    for row in rows:
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [
                _fail("day_reported_twice", **where, receipt_id=key, times_reported=seen[key])
            ]
        entry = charged.get(key)
        returned = sum(int(part["returned_runs"]) for part in entry["parts"]) if entry else None
        if (
            entry is None
            or str(row.get("day_id")) != str(entry["day_id"])
            or _number(row.get("runs_returned")) != Fraction(returned or 0)
        ):
            return [
                _fail(
                    "day_not_on_the_receipt_stream",
                    **where,
                    receipt_id=key,
                    charged_days=len(receipts),
                )
            ]
    for key, entry in charged.items():
        if key in seen:
            continue
        kind = (
            "handed_back_day_left_out"
            if entry.get("refusal")
            else "charged_day_missing_from_the_report"
        )
        return [
            _fail(
                kind,
                **where,
                receipt_id=key,
                day_id=str(entry["day_id"]),
                charged_days=len(receipts),
                rig_hours_charged=float(entry["rig_hours_charged"]),
            )
        ]
    return []


def _move_failures(
    world: w.World, base: Mapping[str, Any], variants: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    where = _where(world)
    anchor = _number(base.get("effect_K"))
    if anchor is None:
        return []
    found: list[dict[str, Any]] = []
    for arrangement, kind in (
        ("shift", "estimate_tracks_the_rig_day"),
        ("assign", "estimate_tracks_which_day_the_plate_ran_on"),
    ):
        if arrangement not in variants:


            continue
        report = variants[arrangement]
        again = _number(report.get("effect_K"))
        if again is None:
            found.append(
                _fail(
                    "effect_missing_after_recheck",
                    **where,
                    plate=world.selected,
                    reported=kelvin(float(anchor)),
                    reported_again=kelvin(report.get("effect_K")),
                    what_changed=w.arrangement_note(arrangement),
                )
            )
            continue
        if abs(again - anchor) <= oracle.MOVE_TOLERANCE:
            continue
        found.append(
            _fail(
                kind,
                **where,
                plate=world.selected,
                reported=kelvin(float(anchor)),
                reported_again=kelvin(float(again)),
                moved=kelvin(float(abs(again - anchor))),
                what_changed=w.arrangement_note(arrangement),
            )
        )
    return found


def _plan_failures(
    world: w.World,
    receipts: Sequence[Mapping[str, Any]],
    offered: Any,
    report: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    where = _where(world)
    left = oracle.days_left(world, receipts)
    reported_width = _range_width(report or {})
    paired_days = len(oracle.paired_days(world, receipts))
    range_inside = (
        reported_width is not None
        and reported_width <= oracle.bar(world) + WIDTH_SLACK
    )


    stop_allowed = left <= 0 or (paired_days >= 2 and range_inside) or report is None
    must_stop = (
        left > 0
        and paired_days >= 2
        and range_inside
    )
    told = {
        **where,
        "plate": world.selected,
        "incumbent_part": INCUMBENT,
        "rig_days_left": left,
        "range_width_wanted": kelvin(oracle.bar(world)),
        "range_width_in_hand": kelvin(reported_width),
        "paired_days": paired_days,
    }
    sheets = offered if isinstance(offered, list) else [offered]
    if not sheets:
        return [_fail("plan_is_not_a_day_sheet", **told, reported=show(offered))]
    stock = set(world.parts_in_stock())
    caps = world.day_capacity()
    for sheet in sheets:
        if isinstance(sheet, str):
            if sheet.strip().lower() != "stop":
                return [_fail("plan_is_not_a_day_sheet", **told, reported=show(sheet))]
            if not stop_allowed:
                return [_fail("stopped_with_rig_days_left", **told)]
            continue
        if not isinstance(sheet, list) or not sheet:
            return [_fail("plan_is_not_a_day_sheet", **told, reported=show(sheet))]
        counts: dict[str, int] = {}
        for item in sheet:
            if not isinstance(item, Mapping):
                return [_fail("plan_is_not_a_day_sheet", **told, reported=show(item))]
            part = item.get("part")
            runs = _number(item.get("runs"))
            if (
                not isinstance(part, str)
                or not part.strip()
                or runs is None
                or runs.denominator != 1
                or runs <= 0
            ):
                return [_fail("plan_is_not_a_day_sheet", **told, reported=show(item))]
            part = part.strip()
            if part in counts:
                return [_fail("plan_is_not_a_day_sheet", **told, reported=show(sheet))]
            counts[part] = int(runs)
        if must_stop:
            return [
                _fail(
                    "booking_continues_after_review_bar",
                    **told,
                    reported=", ".join(
                        f"{part} x{runs}" for part, runs in sorted(counts.items())
                    ),
                )
            ]
        if left <= 0:
            return [
                _fail(
                    "booking_with_no_rig_days_left",
                    **told,
                    reported=", ".join(f"{part} x{runs}" for part, runs in sorted(counts.items())),
                )
            ]
        outside = sorted(part for part in counts if part not in stock)
        if outside:
            return [_fail("booking_names_a_part_not_on_the_shelf", **told, part=outside[0])]
        total = sum(counts.values())
        if (
            total > caps["runs_per_day"]
            or len(counts) > caps["fixture_changes_per_day"]
            or any(runs <= 0 for runs in counts.values())
        ):
            return [
                _fail(
                    "booking_over_the_day_caps",
                    **told,
                    runs_asked_for=total,
                    parts_asked_for=len(counts),
                    runs_a_day_holds=caps["runs_per_day"],
                    fixture_changes_a_day_holds=caps["fixture_changes_per_day"],
                )
            ]
        if counts.get(world.selected, 0) <= 0 or counts.get(INCUMBENT, 0) <= 0:
            return [
                _fail(
                    "booking_leaves_the_plate_alone_on_the_day",
                    **told,
                    reported=", ".join(f"{part} x{runs}" for part, runs in sorted(counts.items())),
                )
            ]
        width = oracle.implied_width(
            world, receipts, [{"part": part, "runs": runs} for part, runs in counts.items()], left
        )
        if width > oracle.wanted_width(world, receipts) + 1e-9:


            return [
                _fail(
                    "booking_falls_short_of_the_review_bar",
                    **told,
                    reported=", ".join(f"{part} x{runs}" for part, runs in sorted(counts.items())),
                    plate_runs=counts.get(world.selected, 0),
                    incumbent_runs=counts.get(INCUMBENT, 0),
                    runs_a_day_holds=caps["runs_per_day"],
                )
            ]
    return []


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(run: Mapping[str, Any]) -> str:
    reported = str(run.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        line = (
            f"it was still running after {reported[len(_TIMEOUT_PHRASE):].strip()} "
            "and the console stopped it"
        )
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the review notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every screen and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, stream_error = live_stream(Path(artifact_dir))
        rows = cases(entries)
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], dict[str, int]]] = []
        plans: list[tuple[w.World, list[dict[str, Any]], int, int]] = []
        for row in rows:
            world = row["world"]
            index: dict[str, int] = {}
            for arrangement in w.ARRANGEMENTS:
                receipts = (
                    row["receipts"]
                    if arrangement == "as run"
                    else variant_receipts(world, row["receipts"], arrangement)
                )
                index[arrangement] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": world.public_context(arrangement),
                        "receipts": receipts,
                    }
                )
            if (
                not oracle.paired_days(world, row["unpaired_base"])
                and row["unpaired_base"] != row["receipts"]
            ):
                index["without paired days"] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": world.public_context(),
                        "receipts": row["unpaired_base"],
                    }
                )
            if len(row["range_base"]) < len(row["receipts"]):
                index["before paired days"] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": world.public_context(),
                        "receipts": row["range_base"],
                    }
                )
            varied = variability_receipts(world, row["receipts"])
            if len(oracle.paired_days(world, varied)) >= 2 and varied != row["receipts"]:
                row["variability_receipts"] = varied
                index["different variability"] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": world.public_context(),
                        "receipts": varied,
                    }
                )
            reports.append((row, index))
            for state in plan_states(world, row["plan_base"]):
                plan_position = len(requests)
                requests.append(
                    {
                        "kind": "plan",
                        "context": world.public_context(),
                        "receipts": state["receipts"],
                    }
                )
                report_position = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": world.public_context(),
                        "receipts": state["receipts"],
                    }
                )
                plans.append(
                    (world, list(state["receipts"]), plan_position, report_position)
                )
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            error = _console_error(run)
            analysis = dict(failed_analysis(error, tuple(BUCKETS.values())))
            for bucket in BUCKETS.values():
                analysis[bucket] = [
                    _candidate_failure(CURRENT, error, "notebook startup")
                ]
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CURRENT.campaign, "rig_days_charged": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(position: int) -> tuple[Any, str | None]:
            if position >= len(results):
                return None, "the notebook returned no answer for one of the screens"
            item = dict(results[position])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        for row, index in reports:
            world, receipts = row["world"], row["receipts"]
            value, error = answer(index["as run"])
            if error is not None:
                stopped = True
                for bucket in ("effect_failures", "range_failures", "ledger_failures",
                               "move_failures"):
                    failures[bucket].append(
                        _candidate_failure(world, error, "terminal report")
                    )
                continue
            report = dict(value or {})
            failures["effect_failures"].extend(_effect_failures(world, receipts, report))
            failures["range_failures"].extend(_range_failures(world, receipts, report))
            failures["ledger_failures"].extend(
                _ledger_failures(
                    world, receipts, report, stream_error if world is CURRENT else None
                )
            )
            variants: dict[str, Mapping[str, Any]] = {}
            for arrangement in ("shift", "assign"):
                other, other_error = answer(index[arrangement])
                if other_error is not None:
                    stopped = True
                    failures["move_failures"].append(
                        _candidate_failure(world, other_error, f"{arrangement} recheck")
                    )
                else:
                    variants[arrangement] = dict(other or {})
            failures["move_failures"].extend(_move_failures(world, report, variants))
            relisted, relisted_error = answer(index["relist"])
            if relisted_error is not None:
                stopped = True
                failures["range_failures"].append(
                    _candidate_failure(world, relisted_error, "relisted-run recheck")
                )
            else:
                failures["range_failures"].extend(
                    _run_order_failures(world, receipts, report, dict(relisted or {}))
                )
            if "without paired days" in index:
                unpaired, unpaired_error = answer(index["without paired days"])
                if unpaired_error is not None:
                    stopped = True
                    failures["range_failures"].append(
                        _candidate_failure(world, unpaired_error, "unpaired report")
                    )
                else:
                    failures["range_failures"].extend(
                        _range_failures(
                            world,
                            row["unpaired_base"],
                            dict(unpaired or {}),
                            terminal=False,
                        )
                    )
            if "before paired days" in index:
                before, before_error = answer(index["before paired days"])
                if before_error is not None:
                    stopped = True
                    failures["range_failures"].append(
                        _candidate_failure(world, before_error, "receipt-prefix report")
                    )
                else:
                    before_report = dict(before or {})
                    failures["range_failures"].extend(
                        _range_failures(
                            world,
                            row["range_base"],
                            before_report,
                            terminal=False,
                        )
                    )
                    failures["range_failures"].extend(
                        _range_response_failures(
                            world,
                            row["range_base"],
                            before_report,
                            receipts,
                            report,
                        )
                    )
            if "different variability" in index:
                varied, varied_error = answer(index["different variability"])
                if varied_error is not None:
                    stopped = True
                    for bucket in ("effect_failures", "range_failures"):
                        failures[bucket].append(
                            _candidate_failure(world, varied_error, "variability recheck")
                        )
                else:
                    varied_report = dict(varied or {})
                    failures["effect_failures"].extend(
                        _effect_failures(
                            world,
                            row["variability_receipts"],
                            varied_report,
                        )
                    )
                    failures["range_failures"].extend(
                        _range_variability_failures(
                            world,
                            receipts,
                            report,
                            row["variability_receipts"],
                            varied_report,
                        )
                    )
        for world, receipts, position, report_position in plans:
            value, error = answer(position)
            if error is not None:
                stopped = True
                failures["plan_failures"].append(
                    _candidate_failure(world, error, "booking decision")
                )
                continue
            plan_report, plan_report_error = answer(report_position)
            failures["plan_failures"].extend(
                _plan_failures(
                    world,
                    receipts,
                    value,
                    None if plan_report_error is not None else dict(plan_report or {}),
                )
            )

        analysis: dict[str, Any] = {
            bucket: reported(records) for bucket, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT.campaign,
            "rig_days_charged": len(entries),
            "screens_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a record must contain a JSON object")
    return raw


def snapshot(record: Mapping[str, Any]) -> dict[str, Any]:
    'The July evidence as it stood at the end of one past working day.'

    through = str(record["through_day"])
    context = CURRENT.public_context()
    context["screen_runs"] = [
        row for row in context["screen_runs"] if row["day_id"] <= through
    ]
    context["rig_log"] = [row for row in context["rig_log"] if row["day_id"] <= through]
    return context


def _record_stream(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = list(record.get("rig_days_charged", ()))
    sheets = [list(sheet) for sheet in workload.STARTING_SHEETS][: len(held)]
    return bench.extend(CURRENT, [], sheets, list(held)) if sheets else []


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    context = CURRENT.public_context()
    entries, error = live_stream(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "operator", "through_day")},
            }
        )
    return {
        "summary": (
            f"The {context['campaign']} booking account and the working days on record."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "rig_days_allocated": context["booking"]["rig_days_on_the_sheet"],
            "rig_days_charged": len(entries),
            "rig_days_left": bench.days_left(CURRENT, entries),
            "rig_hours_charged": sum(entry["rig_hours_charged"] for entry in entries),
            "bookings": [
                {
                    "receipt_id": entry["receipt_id"],
                    "day_id": entry["day_id"],
                    "runs_returned": sum(part["returned_runs"] for part in entry["parts"]),
                    "refusal": entry["refusal"],
                }
                for entry in entries
            ],
            "receipt_stream": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "sources": {
            "booking_terms": "booking.md",
            "review_note": "design_review_note.md",
            "baseline_record": "baseline_characterisation.md",
            "bench_notes": "bench_notes.md",
            "screen_ledger": "screen_ledger.csv",
            "rig_log": "rig_log.md",
            "current_context": "screen_context.json",
            "current_receipts": "bench_receipts.json",
        },
        "records": records,
    }


def public_replay(
    artifact_dir: Path, record_path: Path, *, include_inputs: bool = False
) -> Mapping[str, Any]:
    "Run the notebook the way that working day's operator ran it."

    record = _record(record_path)
    context = snapshot(record)
    receipts = _record_stream(record)


    held, _error = live_stream(Path(artifact_dir))
    requests = [
        {"kind": "report", "context": context, "receipts": receipts},
        {"kind": "plan", "context": context, "receipts": receipts},
    ]
    moved = [entry["receipt_id"] for entry in held] != [
        entry["receipt_id"] for entry in receipts
    ]
    if moved:
        current = CURRENT.public_context()
        requests.extend(
            [
                {"kind": "report", "context": current, "receipts": held},
                {"kind": "plan", "context": current, "receipts": held},
            ]
        )
    run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
    working_day = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "operator": record.get("operator"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_day"),
        "receipt_ids": [entry["receipt_id"] for entry in receipts],
        "input_sources": {
            "screen_ledger": "screen_ledger.csv",
            "rig_log": "rig_log.md",
            "current_context": "screen_context.json",
            "current_receipts": "bench_receipts.json",
        },
    }
    public: dict[str, Any] = {"working_day": working_day}
    if include_inputs:
        public["inputs"] = {"working_day": {"context": context, "receipts": receipts}}
        if moved:
            public["inputs"]["bench_today"] = {"context": current, "receipts": held}
    if not run.get("ok"):
        public.update(
            console_error=run.get("error"), diagnostic=run.get("diagnostic")
        )
        return {
            "summary": f"The {record.get('record_id')} working day could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "campaign": context["campaign"]},
            "public": public,
        }
    results = list(run.get("results", ()))
    public.update(
        report_returned=results[0] if results else None,
        next_collection_returned=results[1] if len(results) > 1 else None,
        stdout=run.get("stdout"),
    )
    if moved:
        public["bench_today"] = {
            "rig_days_charged": len(held),
            "rig_days_left": bench.days_left(CURRENT, held),
            "receipt_ids": [entry["receipt_id"] for entry in held],
            "report_returned": results[2] if len(results) > 2 else None,
            "next_collection_returned": results[3] if len(results) > 3 else None,
        }
    return {
        "summary": f"The {record.get('record_id')} working day ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "evidence_through": record.get("through_day"),
            "rig_days_charged": len(receipts),
        },
        "public": public,
    }


def run_booking(artifact_dir: Path, sheet: Any, booking_id: Any) -> Mapping[str, Any]:
    return bench.collect(Path(artifact_dir), CURRENT, sheet, booking_id)


def starting_stream() -> dict[str, Any]:
    return workload.starting_stream()
