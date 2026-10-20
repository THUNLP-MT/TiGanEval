'Read one delivered apportionment notebook against the world it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w
from .world import SUPPLIES


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-source-apportionment-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

LOT = workload.CURRENT.lot

BUCKETS: Mapping[str, str] = {
    "supply_shares_within_tolerance": "share_failures",
    "band_covers_and_meets_floor": "band_failures",
    "shares_invariant_to_signature_shift": "stability_failures",
    "next_visit_identifies_mixture": "visit_failures",
    "report_reconciles_receipts": "account_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "supply_shares_within_tolerance": (
        "shares_are_not_three_numbers",
        "shares_do_not_add_to_one",
        "shares_use_sheet_signature",
        "shares_include_changeover_rows",
        "shares_unweighted_samples",
        "shares_spent_the_grant_before_reading_the_rate",
        "shares_disagree",
        "shares_elsewhere_lean_on_the_sheet",
        "shares_wrong_on_another_window",
        "candidate_execution_failed",
    ),
    "band_covers_and_meets_floor": (
        "band_is_not_a_range",
        "band_excludes_reported_share",
        "band_tighter_than_the_floor",
        "band_undercovers",
        "band_degenerately_wide",
        "band_same_width_whatever_was_collected",
        "band_widths_do_not_track_records",
        "band_wrong_on_another_window",
        "candidate_execution_failed",
    ),
    "shares_invariant_to_signature_shift": (
        "figure_carried_over",
        "shift_slope_from_header_rows",
        "shares_track_shift_size",
        "set_aside_rows_track_the_changeover",
        "candidate_execution_failed",
    ),
    "next_visit_identifies_mixture": (
        "visit_is_not_a_call_or_a_stop",
        "visit_infeasible",
        "visit_over_the_slots_left",
        "visit_adds_no_identification",
        "stopped_with_slots_still_left",
        "visit_wrong_on_another_window",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "ledger_unreadable",
        "visits_are_not_a_ledger",
        "visit_not_on_the_ledger",
        "visit_details_disagree",
        "visit_counted_twice",
        "refusal_uncounted",
        "receipt_missing",
        "sample_counted_twice",
        "sample_not_on_the_sheet",
        "sample_missing_from_the_account",
        "sample_in_wrong_part_of_account",
        "account_wrong_on_another_window",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "share_failures": (
        "shares_elsewhere_lean_on_the_sheet",
        "shares_wrong_on_another_window",
    ),
    "band_failures": ("band_wrong_on_another_window",),
    "visit_failures": ("visit_wrong_on_another_window",),
    "account_failures": ("account_wrong_on_another_window",),
}


CARRY_OVER_FAMILY: Mapping[str, Mapping[str, str]] = {
    "share_failures": {
        "shares_use_sheet_signature": "shares_elsewhere_lean_on_the_sheet",
    },
}


CARRY_OVER_FIELDS: Mapping[str, Mapping[str, str]] = {
    "shares_elsewhere_lean_on_the_sheet": {
        "supply": "supply",
        "sheet_day": "sheet_day",
        "sheet_outdoor_C": "sheet_outdoor_C",
        "coldest_C": "coldest_C",
    },
}


_NAMING_ORDER: tuple[str, ...] = tuple(
    lot.lot
    for lot in (*workload.LATER, *workload.BLOCKS, workload.OUT_OF_REGIME)
)


def _naming_rank(lot: str) -> int:
    return _NAMING_ORDER.index(lot) if lot in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident she can open the sample sheet for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("window") == LOT else 1,
    )


_RUBRIC_OF_BUCKET: Mapping[str, str] = {
    bucket: rubric_id for rubric_id, bucket in BUCKETS.items()
}


def _carried_family(bucket: str, rows: Sequence[Mapping[str, Any]]) -> str:
    'The misreading the analyst names when she reports the later window.'

    kinds = {str(record.get("kind")) for record in rows}
    for mode in FAILURE_MODES[_RUBRIC_OF_BUCKET[bucket]]:
        if mode in kinds:
            return mode
    return str(rows[0].get("kind"))


def _carried_reading(bucket: str, record: Mapping[str, Any]) -> str:
    'What the delivered notebook printed on the window she is naming.'

    if bucket == "share_failures":
        if record.get("supply") and record.get("reported_share"):
            return f"the {record['supply']} share at {record['reported_share']}"
        return f"a shares line reading {record.get('reported', 'nothing at all')}"
    if bucket == "band_failures":
        if record.get("supply") and record.get("reported_band"):
            return f"a range against {record['supply']} of {record['reported_band']}"
        return f"a range line reading {record.get('reported', 'nothing at all')}"
    if bucket == "visit_failures":
        if record.get("kind") == "stopped_with_slots_still_left":
            return f"a stop with {record.get('slots_left')} slots still on the agreement"
        if record.get("point"):
            return (
                f"{record.get('samples_asked')} slots at {record['point']} at "
                f"{record.get('dwell_min')} minutes"
            )
        return f"a visit line reading {record.get('reported', 'nothing at all')}"
    if bucket == "account_failures":
        for field in ("call_id", "sample_id"):
            if record.get(field):
                return f"the line for {record[field]}"
        if record.get("reason"):
            return f"the line they stopped on, {record['reason']}"
        return f"a visit list reading {record.get('reported', 'nothing at all')}"
    return "figures its own team does not have"


def _written_off_the_live_window(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the window the estates manager holds."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("window") == LOT
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    family = _carried_family(bucket, rows)
    mode = CARRY_OVER_FAMILY.get(bucket, {}).get(family, modes[-1])
    same = [record for record in rows if str(record.get("kind")) == family] or rows
    named = min(
        (record for record in same if record.get("window")),
        key=lambda record: _naming_rank(str(record["window"])),
        default=same[0],
    )
    elsewhere = sorted({str(record["window"]) for record in same if record.get("window")})
    carried = _fail(
        mode,
        window=LOT,
        other_window=str(named.get("window")),
        other_windows=len(elsewhere),
        other_reading=_carried_reading(bucket, named),
    )
    for field, source in CARRY_OVER_FIELDS.get(mode, {}).items():
        if named.get(source) is not None:
            carried[field] = named[source]
    return [carried]


def _share(value: Any) -> str:
    return format(float(value), ".3f")


def _measurement(value: Any) -> str:
    'Round-trip a measured boundary value so the failed comparison stays visible.'

    return repr(float(value))


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
        return f"{_share(value[0])} to {_share(value[1])}"
    return _show(value)


def _invalid_share(value: Any) -> str:
    'Name the first missing or unreadable share without supplying its answer.'

    if not isinstance(value, Mapping):
        return _show(value)
    for supply in SUPPLIES:
        if supply not in value:
            return f"{_supply(supply)} is missing"
        if _number(value.get(supply)) is None:
            return f"{_supply(supply)} reads {_show(value.get(supply))}"
    return _show(value)


def _invalid_band(value: Any, supply: str) -> str:
    'Name the first missing or unreadable endpoint on one reported band.'

    if not isinstance(value, Mapping):
        return _show(value)
    if supply not in value:
        return f"{_supply(supply)} is missing"
    pair = value.get(supply)
    if isinstance(pair, (list, tuple)) and len(pair) == 2:
        for label, endpoint in zip(("low end", "high end"), pair):
            if _number(endpoint) is None:
                return f"{label} reads {_show(endpoint)}"
    return _pair(pair)


def _measurement_pair(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return f"{_measurement(value[0])} to {_measurement(value[1])}"
    return _show(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _supply(name: str) -> str:
    return str(name).replace("_", " ")


def _shares_of(report: Mapping[str, Any]) -> tuple[float, float, float] | None:
    raw = report.get("shares")
    if not isinstance(raw, Mapping):
        return None
    values = [_number(raw.get(name)) for name in SUPPLIES]
    if any(value is None for value in values):
        return None
    return tuple(values)


def _band_of(report: Mapping[str, Any], supply: str) -> tuple[float, float] | None:
    raw = report.get("share_band")
    if not isinstance(raw, Mapping):
        return None
    pair = raw.get(supply)
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return None
    low, high = _number(pair[0]), _number(pair[1])
    if low is None or high is None or low > high:
        return None
    return low, high


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The visits this delivery has paid for, or why the ledger will not read.'

    try:
        return w.read_ledger(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def history_ledger(world: w.World) -> list[dict[str, Any]]:
    "A window's own rounds, as the analyser desk wrote them."

    return w.stream(world, workload.history_visits(world))


def _appended(
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    call_id: str,
    point: str,
    dwell_min: int,
    samples: int,
    channels: Sequence[str] = ("conductivity", "marker"),
) -> list[dict[str, Any]]:
    'The ledger this window would hold after one more visit the desk serves.'

    entries = [dict(entry) for entry in ledger]
    served = {str(entry["served_on"]) for entry in entries}
    free = [day for day in world.open_days() if day not in served]
    if not free:
        return entries
    cost = w.slot_cost(point, dwell_min, samples, channels, world.spec)
    if cost > world.slots_left(entries):
        return entries
    entries.append(
        w.receipt(
            world,
            call_id,
            point,
            dwell_min,
            samples,
            channels,
            free[0],
            len(entries) + 1,
            entries[-1]["seal"] if entries else "",
            world.slots_left(entries) - cost,
        )
    )
    return entries


def plan_states(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The states the window passes through, all of them bookable from the records.'

    frozen = w.stream(world, workload.history_visits(world))
    rated = _appended(world, frozen, "state-rate", "tie_in_plant_room", 5, 3)
    refused = _appended(world, frozen, "state-refused", "boiler_house", 5, 3)
    closed = _appended(world, rated, "state-riser", "east_riser", 30, 1, ("marker",))
    return [
        {"label": "as delivered", "ledger": [dict(item) for item in ledger]},
        {"label": "the whole grant in hand", "ledger": frozen},
        {"label": "after the plant room", "ledger": rated},
        {"label": "after a round the desk handed back", "ledger": refused},
        {"label": "after the riser", "ledger": closed},
    ]


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The window under study, then the ones the same notebook is used on next.'

    rows: list[dict[str, Any]] = [
        {
            "world": workload.CURRENT,
            "ledger": [dict(item) for item in entries],
            "plans": plan_states(workload.CURRENT, entries),
        }
    ]
    for world in (*workload.LATER, *workload.BLOCKS, workload.OUT_OF_REGIME):
        ledger = history_ledger(world)
        rows.append(
            {
                "world": world,
                "ledger": ledger,
                "plans": [{"label": "as delivered", "ledger": ledger}],
            }
        )
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
    ("shares_use_sheet_signature", ("sheet_signature", "header_slope",
                                    "sheet_and_unweighted", "sheet_and_floor",
                                    "everything_wrong")),
    ("shares_include_changeover_rows", ("changeover_kept",)),
    ("shares_unweighted_samples", ("unweighted",)),
)


def explanation(
    readings: Mapping[str, tuple[float, float, float]],
    worlds: Mapping[str, w.World],
    ledgers: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str | None:
    'The one misreading that accounts for this delivery on most of the windows.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = 0
        for lot, values in readings.items():
            if lot not in worlds:
                continue
            table = oracle.misreadings(worlds[lot], ledgers[lot])
            if any(
                all(
                    abs(values[index] - table[family][index]) <= oracle.CLASSIFY_SLACK
                    for index in range(3)
                )
                for family in families
                if family in table
            ):
                hits += 1
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def _check_shares(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    mode: str | None,
) -> None:
    truth = oracle.truth(world)
    values = _shares_of(report)
    if values is None:
        review.add(
            "share_failures",
            "shares_are_not_three_numbers",
            window=world.lot,
            reported=_invalid_share(report.get("shares")),
        )
        return
    total = sum(values)
    if abs(total - 1.0) > 1e-6:
        review.add(
            "share_failures", "shares_do_not_add_to_one", window=world.lot,
            reported_total=_measurement(total),
        )
        return
    gaps = [abs(values[index] - truth[index]) for index in range(3)]
    if max(gaps) <= oracle.TOLERANCE:
        return
    worst = max(range(3), key=lambda index: gaps[index])
    shared = {
        "window": world.lot,
        "supply": _supply(SUPPLIES[worst]),
        "reported_share": _share(values[worst]),
        "tolerance": _share(oracle.TOLERANCE),
    }
    if mode == "shares_use_sheet_signature":
        review.add(
            "share_failures",
            mode,
            **shared,
            sheet_day=str(world.sheet_day),
            sheet_outdoor_C=str(world.sheet_outdoor_C),
            coldest_C=str(round(min(world.temperature[day] for day in world.days), 1)),
        )
        return
    if mode == "shares_include_changeover_rows":
        aside = oracle.set_aside_ids(world, ledger)
        review.add(
            "share_failures",
            mode,
            **shared,
            samples_in_the_window=len(aside),
            first_sample=aside[0] if aside else "none",
        )
        return
    if mode == "shares_unweighted_samples":
        heaviest, lightest = _heaviest_lightest(world, ledger)
        review.add(
            "share_failures", mode, **shared, heaviest_day=heaviest, lightest_day=lightest
        )
        return
    if _nothing_left_to_buy(world, ledger) and not oracle.rate_is_measured(world, ledger):
        review.add(
            "share_failures",
            "shares_spent_the_grant_before_reading_the_rate",
            **shared,
            slots_left=world.slots_left(ledger),
            slots_on_the_header=_slots_on_the_header(ledger),
            visits_on_the_ledger=len(ledger),
        )
        return
    review.add("share_failures", "shares_disagree", **shared)


def _nothing_left_to_buy(world: w.World, ledger: Sequence[Mapping[str, Any]]) -> bool:
    'Whether the agreement can still serve this window anything at all.'

    served = {str(entry["served_on"]) for entry in ledger}
    if not [day for day in world.open_days() if day not in served]:
        return True
    return not oracle.affordable_plans(world, ledger)


def _slots_on_the_header(ledger: Sequence[Mapping[str, Any]]) -> int:
    "What the window spent on header rounds, which the desk's own bill shows."

    return sum(
        int(entry["slots_charged"])
        for entry in ledger
        if str(entry.get("point")) == "header"
    )


def _heaviest_lightest(
    world: w.World, ledger: Sequence[Mapping[str, Any]]
) -> tuple[str, str]:
    days = sorted({str(sample["taken_at"])[:10] for sample in oracle.header_samples(world, ledger)})
    if not days:
        return (str(world.days[0]), str(world.days[-1]))
    heaviest = max(days, key=lambda day: world.kwh.get(day, 0.0))
    lightest = min(days, key=lambda day: world.kwh.get(day, 0.0))
    return heaviest, lightest


def _check_band(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> bool:
    'The width the records support. Returns whether the recovery truth is held.'

    for supply in SUPPLIES:
        if _band_of(report, supply) is None:
            raw = report.get("share_band")
            review.add(
                "band_failures",
                "band_is_not_a_range",
                window=world.lot,
                supply=_supply(supply),
                reported=_invalid_band(raw, supply),
            )
            return True
    recovery = SUPPLIES[2]
    low, high = _band_of(report, recovery)
    shares = _shares_of(report)
    if shares is not None and not (low <= shares[2] <= high):
        review.add(
            "band_failures", "band_excludes_reported_share", window=world.lot,
            supply=_supply(recovery), reported_share=_measurement(shares[2]),
            reported_band=_measurement_pair([low, high]),
        )
    supported = oracle.supported_half(world, ledger)
    width = (high - low) / 2.0
    fields = {
        "window": world.lot,
        "supply": _supply(recovery),
        "reported_band": _pair([low, high]),
        "floor_muL": _share(world.spec["marker_floor_5"]),
    }
    if width < supported * oracle.NARROW_FACTOR:
        review.add("band_failures", "band_tighter_than_the_floor", **fields)
    elif width > supported * oracle.WIDE_FACTOR:
        review.add("band_failures", "band_degenerately_wide", **fields)
    truth = oracle.truth(world)[2]
    return low <= truth <= high


def _recovery_half(report: Mapping[str, Any] | None) -> float | None:
    'Half the recovery range the delivered report printed, where it printed one.'

    pair = _band_of(dict(report or {}), SUPPLIES[2]) if report is not None else None
    return None if pair is None else (pair[1] - pair[0]) / 2.0


def _check_band_moves(
    review: Review,
    world: w.World,
    before: Sequence[Mapping[str, Any]],
    before_report: Mapping[str, Any] | None,
    after: Sequence[Mapping[str, Any]],
    after_report: Mapping[str, Any] | None,
) -> None:
    "A published band is this state's, and not one width printed at every state."

    supported_before = oracle.supported_half(world, before)
    supported_after = oracle.supported_half(world, after)
    half_before = _recovery_half(before_report)
    half_after = _recovery_half(after_report)
    if half_before is None or half_after is None:
        return
    if supported_after <= 0.0 or half_after <= 0.0:
        return
    moved = supported_before / supported_after
    if moved < oracle.MOVEMENT_GAP:
        return
    if half_before / half_after >= moved**oracle.TRACKING_POWER:
        return
    review.add(
        "band_failures",
        "band_same_width_whatever_was_collected",
        window=world.lot,
        supply=_supply(SUPPLIES[2]),
        reported_band=_pair(list(_band_of(dict(after_report or {}), SUPPLIES[2]) or ())),
        band_before=_pair(list(_band_of(dict(before_report or {}), SUPPLIES[2]) or ())),
        rounds_between=len(list(after)) - len(list(before)),
    )


def _check_band_tracks_records(
    review: Review,
    rows: Sequence[Mapping[str, Any]],
    delivered: Mapping[str, Mapping[str, Any]],
) -> None:
    'Reject widths selected by collection state alone, not by each window.'

    measured: list[tuple[float, w.World, tuple[float, float]]] = []
    for row in rows:
        world = row["world"]
        pair = _band_of(dict(delivered.get(world.lot) or {}), SUPPLIES[2])
        if pair is None:
            return
        supported = oracle.supported_half(world, row["ledger"])
        half = (pair[1] - pair[0]) / 2.0
        if supported <= 0.0 or half <= 0.0:
            return
        measured.append((half / supported, world, pair))
    if len(measured) < 2:
        return
    narrow = min(measured, key=lambda item: item[0])
    wide = max(measured, key=lambda item: item[0])
    if wide[0] / narrow[0] <= oracle.WINDOW_TRACKING_SPREAD:
        return
    review.add(
        "band_failures", "band_widths_do_not_track_records", window=LOT,
        first_window=narrow[1].lot, other_window=wide[1].lot,
        reported_band=_pair(list(narrow[2])), other_band=_pair(list(wide[2])),
        windows_reviewed=len(measured),
    )


def _printed_recovery_width(report: Mapping[str, Any] | None) -> str:
    'The recovery range as the delivered report printed it, in her words.'

    pair = _band_of(dict(report or {}), SUPPLIES[2]) if report is not None else None
    if pair is None:
        return "a line finance cannot read a low and a high off"
    return f"{_share(pair[1] - pair[0])} wide"


def _check_visit(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    answer: Any,
    report: Mapping[str, Any] | None = None,
) -> None:
    state = oracle.plan_state(world, ledger)
    printed = _printed_recovery_width(report)
    shared = {
        "window": world.lot,
        "slots_left": state["slots_left"],
        "slots_per_visit": int(world.spec["slots_per_visit"]),
    }
    if not isinstance(answer, list) or not answer:
        review.add(
            "visit_failures", "visit_is_not_a_call_or_a_stop", **shared, reported=_show(answer)
        )
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add(
                    "visit_failures", "visit_is_not_a_call_or_a_stop", **shared,
                    reported=_show(choice),
                )
                return
            if not state["stop_only"]:
                review.add(
                    "visit_failures", "stopped_with_slots_still_left", **shared,
                    recovery_band=printed,
                    asked_for=_share(oracle.BAND_ASK * 2.0),
                    rate_status=(
                        "has an independent reading for the tie-in dosing rate"
                        if state["rate_measured"]
                        else "has no independent reading for the tie-in dosing rate"
                    ),
                )
                return
            continue
        if not isinstance(choice, dict):
            review.add(
                "visit_failures", "visit_is_not_a_call_or_a_stop", **shared,
                reported=_show(choice),
            )
            return
        point = choice.get("point")
        dwell = _number(choice.get("dwell_min"))
        samples = _number(choice.get("samples"))
        channels = choice.get("channels") or ("conductivity", "marker")
        if (
            not isinstance(point, str)
            or dwell is None or samples is None
            or dwell != int(dwell) or samples != int(samples)
            or samples < 1
            or not isinstance(channels, (list, tuple))
        ):
            review.add(
                "visit_failures", "visit_is_not_a_call_or_a_stop", **shared,
                reported=_show(
                    f"{_show(point)} for {_show(choice.get('samples'))} slots at "
                    f"{_show(choice.get('dwell_min'))} minutes"
                ),
            )
            return
        plan = {
            "point": point,
            "dwell_min": int(dwell),
            "samples": int(samples),
            "channels": tuple(channels),
        }
        named = {
            **shared,
            "point": _supply(point),
            "slots_asked": oracle.slot_cost(world, plan),
            "samples_asked": int(samples),
            "dwell_min": int(dwell),
        }
        refusal = oracle.plan_refusal(world, plan)
        if refusal is not None:
            review.add("visit_failures", "visit_infeasible", **named, reason=str(refusal))
            return
        if named["slots_asked"] > state["slots_left"]:
            review.add("visit_failures", "visit_over_the_slots_left", **named)
            return
        if state["stop_only"] or not oracle.plan_qualifies(world, ledger, plan):
            review.add(
                "visit_failures", "visit_adds_no_identification", **named,
                recovery_band=printed,
            )
            return


def _check_executed_visits(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
) -> None:
    'Reject Agent-added rounds the public agreement says the desk will refuse.'

    history = len(workload.history_visits(world))
    for entry in list(ledger)[history:]:
        reason = entry.get("refusal")
        if not reason:
            continue
        dwell = int(entry["dwell_min"])
        charged = int(entry["slots_requested"])
        if "ripple" in entry.get("channels", ()):
            charged -= int(world.spec["module_slots"])
        per_sample = int(world.spec["long_dwell_slots"]) if dwell >= 30 else 1
        review.add(
            "visit_failures",
            "visit_infeasible",
            window=world.lot,
            slots_left=world.slots_left(ledger),
            slots_per_visit=int(world.spec["slots_per_visit"]),
            point=_supply(str(entry["point"])),
            slots_asked=int(entry["slots_requested"]),
            samples_asked=max(1, charged // per_sample),
            dwell_min=dwell,
            reason=str(reason),
        )
        return


def _check_account(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    error: str | None,
) -> None:
    if error:
        review.add(
            "account_failures", "ledger_unreadable", window=world.lot, reason=str(error)
        )
        return
    rows = report.get("visits")
    if not isinstance(rows, list):
        review.add(
            "account_failures", "visits_are_not_a_ledger", window=world.lot,
            reported=_show(rows), on_the_ledger=len(ledger),
        )
        return
    billed = {str(entry["call_id"]): entry for entry in ledger}
    seen: dict[str, int] = {}
    for row in rows:
        call_id = str(row.get("call_id")) if isinstance(row, Mapping) else _show(row)
        seen[call_id] = seen.get(call_id, 0) + 1
        if seen[call_id] > 1:
            review.add(
                "account_failures", "visit_counted_twice", window=world.lot,
                call_id=call_id, times_reported=seen[call_id],
            )
            return
        entry = billed.get(call_id)
        if entry is None or not isinstance(row, Mapping) or _number(
            row.get("slots_charged")
        ) != float(entry["slots_charged"]):
            review.add(
                "account_failures", "visit_not_on_the_ledger", window=world.lot,
                call_id=call_id, on_the_ledger=len(ledger),
            )
            return
        if not isinstance(row.get("point"), str) or str(row["point"]) != str(entry["point"]):
            review.add(
                "account_failures", "visit_details_disagree", window=world.lot,
                call_id=call_id, reported_point=_supply(row.get("point")),
                ledger_point=_supply(entry["point"]),
            )
            return
    for call_id, entry in billed.items():
        if call_id in seen:
            continue
        kind = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        review.add(
            "account_failures", kind, window=world.lot, call_id=call_id,
            point=_supply(entry["point"]), slots_charged=int(entry["slots_charged"]),
            served_on=str(entry["served_on"]),
        )
        return
    _check_samples(review, world, ledger, report)


def _check_samples(
    review: Review,
    world: w.World,
    ledger: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> None:
    'Every slot on the sheet is either read or named as set aside, once.'

    window = {
        str(sample["sample_id"]): sample
        for sample in world.sample_rows(ledger)
        if world.days[0] <= str(sample["taken_at"])[:10] <= world.days[-1]
    }
    used = report.get("samples_used")
    aside = report.get("samples_set_aside")
    if not isinstance(used, list) or not isinstance(aside, list):
        review.add(
            "account_failures", "sample_missing_from_the_account", window=world.lot,
            sample_id=sorted(window)[0] if window else "none",
            on_the_sheet=len(window),
        )
        return
    counts: dict[str, int] = {}
    for value in [*used, *aside]:
        name = str(value)
        counts[name] = counts.get(name, 0) + 1
    for name, count in sorted(counts.items()):
        if count > 1:
            review.add(
                "account_failures", "sample_counted_twice", window=world.lot,
                sample_id=name, times_reported=count,
            )
            return
    extra = sorted(name for name in counts if name not in window)
    if extra:
        review.add(
            "account_failures", "sample_not_on_the_sheet", window=world.lot,
            sample_id=extra[0], on_the_sheet=len(window),
        )
        return
    missing = sorted(name for name in window if name not in counts)
    if missing:
        review.add(
            "account_failures", "sample_missing_from_the_account", window=world.lot,
            sample_id=missing[0], on_the_sheet=len(window),
        )
        return
    expected_aside = set(oracle.set_aside_ids(world, ledger))
    reported_aside = {str(value) for value in aside}
    for name in sorted(window):
        should_be_aside = name in expected_aside
        if (name in reported_aside) == should_be_aside:
            continue
        review.add(
            "account_failures", "sample_in_wrong_part_of_account", window=world.lot,
            sample_id=name,
            reported_part="set aside" if name in reported_aside else "behind the figures",
            expected_part="set aside" if should_be_aside else "behind the figures",
        )
        return


def _check_stability(
    review: Review,
    readings: Mapping[str, tuple[float, float, float]],
    worlds: Mapping[str, w.World],
    ledgers: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    here = readings.get(LOT)
    if here is None:
        return
    later = workload.LATER[0]
    other = readings.get(later.lot)
    if (
        other is not None
        and all(abs(here[index] - other[index]) < 1e-6 for index in range(3))
        and max(
            abs(a - b)
            for a, b in zip(oracle.truth(workload.CURRENT), oracle.truth(later))
        )
        > oracle.CARRIED_OVER_GAP
    ):
        review.add(
            "stability_failures", "figure_carried_over", window=LOT,
            other_window=later.lot, reported_share=_share(here[2]),
        )
        return
    for mode, block in (
        ("shares_track_shift_size", workload.SHIFT_BLOCK),
        ("set_aside_rows_track_the_changeover", workload.CHANGEOVER_BLOCK),
    ):
        values = readings.get(block.lot)
        if values is None:
            continue
        gaps = [abs(here[index] - values[index]) for index in range(3)]
        if max(gaps) <= oracle.INVARIANCE_SLACK:
            continue
        worst = max(range(3), key=lambda index: gaps[index])
        named = mode
        if mode == "shares_track_shift_size":
            table = oracle.misreadings(workload.CURRENT, ledgers.get(LOT, ()))
            if all(
                abs(here[index] - table["header_slope"][index]) <= oracle.CLASSIFY_SLACK
                for index in range(3)
            ):
                named = "shift_slope_from_header_rows"
        review.add(
            "stability_failures", named, window=LOT, other_window=block.lot,
            supply=_supply(SUPPLIES[worst]),
            reported_share=_share(here[worst]),
            other_share=_share(values[worst]),
            moved_by=_share(gaps[worst]),
        )
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
    return f"the apportionment notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every window and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, ledger_error = live_ledger(Path(artifact_dir))
        rows = instances(entries)
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[dict[str, Any], dict[str, Any], int]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {
                    "kind": "report",
                    "context": row["world"].context(row["ledger"]),
                    "ledger": row["ledger"],
                }
            )
            for state in row["plans"]:
                plans.append((row, state, len(requests)))
                requests.append(
                    {
                        "kind": "plan",
                        "context": row["world"].context(state["ledger"]),
                        "ledger": state["ledger"],
                    }
                )


        states = {state["label"]: state["ledger"] for state in rows[0]["plans"]}
        moves: list[tuple[list[dict[str, Any]], int]] = []
        for label in ("the whole grant in hand", "after the riser"):
            moves.append((states[label], len(requests)))
            requests.append(
                {
                    "kind": "report",
                    "context": workload.CURRENT.context(states[label]),
                    "ledger": states[label],
                }
            )
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"window": LOT, "visits_paid_for": len(entries)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the windows"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        _check_executed_visits(review, workload.CURRENT, entries)
        readings: dict[str, tuple[float, float, float]] = {}
        worlds: dict[str, w.World] = {}
        ledgers: dict[str, Sequence[Mapping[str, Any]]] = {}
        for row, index in reports:
            value, _error = answer(index)
            values = _shares_of(dict(value or {})) if value else None
            if values is not None:
                readings[row["world"].lot] = values
                worlds[row["world"].lot] = row["world"]
                ledgers[row["world"].lot] = row["ledger"]
        mode = explanation(readings, worlds, ledgers)
        held: list[bool] = []
        stopped = False
        delivered: dict[str, Mapping[str, Any]] = {}
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("share_failures", "band_failures", "account_failures",
                     "stability_failures"),
                    error,
                )
                continue
            report = dict(value or {})
            delivered[world.lot] = report
            _check_shares(review, world, row["ledger"], report, mode)
            held.append(_check_band(review, world, row["ledger"], report))
            _check_account(
                review, world, row["ledger"], report,
                ledger_error if world.lot == LOT else None,
            )
        for row, state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["visit_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            _check_visit(
                review, row["world"], state["ledger"], value,
                delivered.get(row["world"].lot),
            )
        misses_coverage = bool(held) and sum(held) < oracle.COVERAGE * len(held)
        misses_main_window = bool(held) and not held[0]
        if misses_main_window or misses_coverage:
            for position, (row, index) in enumerate(reports):
                value, error = answer(index)
                if error is not None:
                    continue
                pair = _band_of(dict(value or {}), SUPPLIES[2])
                truth = oracle.truth(row["world"])[2]
                if (
                    pair is not None
                    and not (pair[0] <= truth <= pair[1])
                    and (misses_coverage or position == 0)
                ):
                    review.add(
                        "band_failures", "band_undercovers", window=row["world"].lot,
                        supply=_supply(SUPPLIES[2]), reported_band=_pair(list(pair)),
                        windows_reviewed=len(held), windows_held=sum(held),
                    )
        if not review.failures["band_failures"]:
            _check_band_tracks_records(review, rows, delivered)
        (wide_ledger, wide_index), (tight_ledger, tight_index) = moves
        wide, wide_error = answer(wide_index)
        tight, tight_error = answer(tight_index)
        if wide_error is None and tight_error is None:
            _check_band_moves(
                review, workload.CURRENT,
                wide_ledger, dict(wide or {}), tight_ledger, dict(tight or {}),
            )
        _check_stability(review, readings, worlds, ledgers)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_window(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "window": LOT,
            "visits_paid_for": len(entries),
            "windows_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working session record must contain a JSON object")
    return raw


def snapshot(
    world: w.World, ledger: Sequence[Mapping[str, Any]], record: Mapping[str, Any]
) -> dict[str, Any]:
    "The window's evidence as it stood on the day of one working session."

    through = str(record["as_of"])
    context = world.context(
        [entry for entry in ledger if str(entry["served_on"]) <= through]
    )
    context["window"]["last_day"] = min(context["window"]["last_day"], through)
    context["weather"] = [row for row in context["weather"] if row["day"] <= through]
    context["heat_meter"] = [row for row in context["heat_meter"] if row["day"] <= through]
    context["samples"] = [
        row for row in context["samples"] if str(row["taken_at"])[:10] <= through
    ]
    context["operations"] = [row for row in context["operations"] if row["day"] <= through]
    return context


def _daily_view(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    "Each day's weather, heat and slots, as the estates office lays them out."

    rows: dict[str, dict[str, Any]] = {}
    for row in context["weather"]:
        rows.setdefault(row["day"], {"day": row["day"]})["outdoor_C"] = row["outdoor_C"]
    for row in context["heat_meter"]:
        rows.setdefault(row["day"], {"day": row["day"]})["delivered_kwh"] = row["delivered_kwh"]
    for row in context["samples"]:
        day = str(row["taken_at"])[:10]
        entry = rows.setdefault(day, {"day": day})
        entry["slots"] = entry.get("slots", 0) + 1
    return [rows[day] for day in sorted(rows)]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_ledger(root)
    world = workload.CURRENT
    context = world.context(entries if not error else history_ledger(world))
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session", "date", "author", "as_of")},
        })
    return {
        "summary": (
            f"The {context['block']} header, the {context['window']['first_day'][:7]} "
            "window, the agreement's terms and the working sessions on record."
        ),
        "measurements": {
            "window": context["window"],
            "block": context["block"],
            "supplies": context["supplies"],
            "signature_sheet_read_on": context["signature_sheet"]["read_on"],
            "signature_sheet_outdoor_C": context["signature_sheet"]["outdoor_C"],
            "marker_floor_muL": context["analyser"]["marker_floor_muL"],
            "report_request": context["report_request"],
            "collection": context["collection"],
            "slots_spent": world.slots_spent(entries),
            "slots_left": world.slots_left(entries),
            "visits_on_the_ledger": [
                {
                    "call_id": item["call_id"],
                    "point": item["point"],
                    "channels": item["channels"],
                    "dwell_min": item["dwell_min"],
                    "slots_charged": item["slots_charged"],
                    "served_on": item["served_on"],
                    "refusal": item["refusal"],
                }
                for item in entries
            ],
            "ledger": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that working session ran it.'

    record = _record(record_path)
    entries, _error = live_ledger(Path(artifact_dir))
    world = workload.CURRENT
    if _error:
        entries = history_ledger(world)
    context = snapshot(world, entries, record)
    ledger = [entry for entry in entries if str(entry["served_on"]) <= str(record["as_of"])]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "ledger": ledger},
            {"kind": "plan", "context": context, "ledger": ledger},
        ]},
    )
    session = {
        "session": record.get("session"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("as_of"),
        "visits_on_the_ledger": [
            {"call_id": item["call_id"], "point": item["point"],
             "slots_charged": item["slots_charged"], "served_on": item["served_on"],
             "refusal": item["refusal"]}
            for item in ledger
        ],
        "by_day": _daily_view(context),
        "operations": list(context["operations"]),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "block": context["block"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "block": context["block"],
            "evidence_through": context["window"]["last_day"],
            "slots_charged_by_then": sum(int(item["slots_charged"]) for item in ledger),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_visit(
    artifact_dir: Path,
    point: Any,
    channels: Any,
    dwell_min: Any,
    samples: Any,
    call_id: Any,
) -> Mapping[str, Any]:
    entries, error = live_ledger(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return w.sample_visit(
        Path(artifact_dir), workload.CURRENT, workload.HISTORY_VISITS,
        point, channels, dwell_min, samples, call_id,
    )


def starting_ledger() -> dict[str, Any]:
    'The ledger the window starts from: four rounds and the one handed back.'

    return {
        "lot": workload.CURRENT.lot,
        "entries": history_ledger(workload.CURRENT),
    }
