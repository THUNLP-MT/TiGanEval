"What the campaign says, computed from the campaign's own parameters."

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from . import chamber
from . import world as w


TOLERANCE = 250.0


CLASSIFY_SLACK = 60.0


STANDS_FACTOR = 1.5


MIN_GROUP_ROWS = 8


NARROW_FACTOR = 0.95
WIDE_FACTOR = 4.0

COVERAGE = 0.8


CARRIED_OVER_GAP = 200.0

INVARIANCE_SLACK = 100.0

PARTING_SHARE = 0.5


def truth(world: w.World) -> float:
    'Hours at the field drive and the hold to a tenth of the output gone.'

    return world.hours_to_target()


def trace_rows(
    world: w.World,
    *,
    pinned_start: bool = False,
    elapsed_hours: bool = False,
    keep_full_scale: bool = False,
) -> list[dict[str, Any]]:
    "Every module row of the export, in wall-clock hours and the meter's mW."

    incoming = {
        str(module["module_id"]): float(module["incoming_mw"])
        for module in world.spec["modules"]
    }
    first: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for row in world.trace_rows():
        name = str(row["module_id"])
        if name == w.REFERENCE_MODULE:
            continue
        first.setdefault(name, float(row["output_mw"]))
        hours = (
            float(row["elapsed_h"])
            if elapsed_hours
            else float(row["elapsed_h"]) * world.cadence_min(str(row["rack"])) / 60.0
        )
        rows.append(
            {
                "module_id": name,
                "hours": hours,
                "drive_a": float(row["drive_a"]),
                "case_temp_c": world.hold_temp_c,
                "start_mw": first[name] if pinned_start else incoming[name],
                "output_mw": float(row["output_mw"]),
                "source": "trace_export",
            }
        )
    if not pinned_start and not keep_full_scale:
        span = world.full_scale_mw - 1e-9
        rows = [row for row in rows if float(row["output_mw"]) < span]
    return rows


def receipt_rows(world: w.World, stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Every module row a chamber block returned.'

    rows: list[dict[str, Any]] = []
    span = world.full_scale_mw - 1e-9
    for entry in stream:
        incoming = {
            str(item["module_id"]): float(item["incoming_mw"])
            for item in entry.get("modules") or ()
        }
        for reading in entry.get("readings") or ():
            if float(reading["output_mw"]) >= span:
                continue
            rows.append(
                {
                    "module_id": str(reading["module_id"]),
                    "hours": float(reading["soak_h"]),
                    "drive_a": float(entry["drive_a"]),
                    "case_temp_c": float(entry["case_temp_c"]),
                    "start_mw": incoming[str(reading["module_id"])],
                    "output_mw": float(reading["output_mw"]),
                    "source": "receipt",
                }
            )
    return rows


def counted_rows(
    world: w.World,
    stream: Sequence[Mapping[str, Any]] = (),
    *,
    pinned_start: bool = False,
    elapsed_hours: bool = False,
    keep_full_scale: bool = False,
) -> list[dict[str, Any]]:
    return [
        *trace_rows(
            world,
            pinned_start=pinned_start,
            elapsed_hours=elapsed_hours,
            keep_full_scale=keep_full_scale,
        ),
        *receipt_rows(world, stream),
    ]


def soak_hours(entry: Mapping[str, Any], row: Mapping[str, Any], world: w.World) -> float:
    'Accumulated soak one law reads into a row held at that drive and case.'

    return (
        float(row["hours"])
        * w.drive_factor(
            str(entry["drive_form"]),
            float(entry["drive_constant"]),
            float(row["drive_a"]),
            world.field_drive_a,
        )
        * w.temperature_factor(
            float(entry["ten_degree_factor"]), float(row["case_temp_c"]), world.hold_temp_c
        )
    )


def _shape_of(entry: Mapping[str, Any], hours: float) -> float:
    return w.shape(str(entry["time_shape"]), float(entry["shape_constant"]), hours)


def fit(world: w.World, law: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    "One law's amplitude and how far it sits from the rows, setting by setting."

    entry = world.spec["catalogue"][law]
    top = bottom = 0.0
    prepared = []
    for row in rows:
        design = float(row["start_mw"]) * _shape_of(entry, soak_hours(entry, row, world))
        lost = float(row["start_mw"]) - float(row["output_mw"])
        top += design * lost
        bottom += design * design
        prepared.append((row, design, lost))
    amplitude = top / bottom if bottom > 0 else 0.0
    groups: dict[tuple[float, float], list[float]] = {}
    for row, design, lost in prepared:
        key = (round(float(row["drive_a"]), 3), round(float(row["case_temp_c"]), 2))
        groups.setdefault(key, []).append(lost - amplitude * design)
    spread = {
        key: math.sqrt(sum(value * value for value in values) / len(values))
        for key, values in groups.items()
    }
    counted = {key: len(values) for key, values in groups.items()}
    return {
        "law": law,
        "amplitude": amplitude,
        "design_sum": bottom,
        "group_spread_mw": spread,
        "group_rows": counted,
        "worst_spread_mw": max(
            (value for key, value in spread.items() if counted[key] >= MIN_GROUP_ROWS),
            default=0.0,
        ),
    }


def fits(world: w.World, rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {law: fit(world, law, rows) for law in sorted(world.spec["catalogue"])}


def crossing_of(world: w.World, law: str, amplitude: float) -> float:
    'Hours at the field drive and the hold at which that law reaches the target.'

    entry = world.spec["catalogue"][law]
    target = float(world.spec["target_loss"])
    if amplitude <= 0:
        return float("inf")
    value = target / amplitude
    kind = str(entry["time_shape"])
    constant = float(entry["shape_constant"])
    if kind == "power":
        return value ** (1.0 / constant)
    if kind == "logarithmic":
        return constant * math.expm1(min(value, 700.0))
    if kind == "saturating":
        if value >= 1.0:
            return float("inf")
        return -constant * math.log(1.0 - value)
    return value * constant


def standing(world: w.World, table: Mapping[str, Mapping[str, Any]]) -> list[str]:
    "The catalogue laws whose curves sit inside the meter's repeat spread."

    bar = STANDS_FACTOR * world.read_noise_mw
    kept = [law for law, item in table.items() if float(item["worst_spread_mw"]) <= bar]
    reaches = [
        law
        for law in kept
        if math.isfinite(crossing_of(world, law, float(table[law]["amplitude"])))
    ]
    kept = reaches or kept
    if kept:
        return sorted(kept)


    reaching = [
        law
        for law in table
        if math.isfinite(crossing_of(world, law, float(table[law]["amplitude"])))
    ]
    best = min(reaching or list(table), key=lambda law: float(table[law]["worst_spread_mw"]))
    return [best]


def _standard_error(world: w.World, table: Mapping[str, Any], law: str) -> float:
    "Three standard errors of one law's own figure, off the rows it was fitted to."

    item = table[law]
    spread = max(float(item["worst_spread_mw"]), world.read_noise_mw)
    design = float(item["design_sum"])
    if design <= 0:
        return float("inf")
    error = spread / math.sqrt(design)
    amplitude = float(item["amplitude"])
    low = crossing_of(world, law, amplitude + 3.0 * error)
    high = crossing_of(world, law, max(amplitude - 3.0 * error, 1e-12))
    return abs(high - low) / 2.0


def reading_of(
    world: w.World,
    stream: Sequence[Mapping[str, Any]] = (),
    *,
    pinned_start: bool = False,
    elapsed_hours: bool = False,
    keep_full_scale: bool = False,
) -> dict[str, Any]:
    'What the export gives: the standing laws, their figures and the floor.'


    entries = list(stream)
    cache = getattr(world, "_readings", None)
    if cache is None:
        cache = {}
        object.__setattr__(world, "_readings", cache)
    key = (
        len(entries),
        str(entries[-1]["seal"]) if entries else "",
        pinned_start,
        elapsed_hours,
        keep_full_scale,
    )
    if key not in cache:
        cache[key] = _compute_reading(
            world,
            entries,
            pinned_start=pinned_start,
            elapsed_hours=elapsed_hours,
            keep_full_scale=keep_full_scale,
        )
    return cache[key]


def _compute_reading(
    world: w.World,
    stream: Sequence[Mapping[str, Any]] = (),
    *,
    pinned_start: bool = False,
    elapsed_hours: bool = False,
    keep_full_scale: bool = False,
) -> dict[str, Any]:
    rows = counted_rows(
        world,
        stream,
        pinned_start=pinned_start,
        elapsed_hours=elapsed_hours,
        keep_full_scale=keep_full_scale,
    )
    table = fits(world, rows)
    stands = standing(world, table)
    crossings = {law: crossing_of(world, law, table[law]["amplitude"]) for law in stands}
    figures = sorted(crossings.values())
    spread = figures[-1] - figures[0]
    error = max(_standard_error(world, table, law) for law in stands)
    return {
        "standing": stands,
        "crossings": crossings,
        "hours": sum(figures) / len(figures),
        "law_spread_h": spread,
        "sampling_half_h": error,
        "floor_half_h": max(spread, error),
        "rows": len(rows),
        "fits": table,
    }


def reading(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    return float(reading_of(world, stream)["hours"])


def supported_half_width(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> float:
    return float(reading_of(world, stream)["floor_half_h"])


def interval(world: w.World, stream: Sequence[Mapping[str, Any]] = ()) -> tuple[float, float]:
    read = reading_of(world, stream)
    return (
        read["hours"] - read["floor_half_h"],
        read["hours"] + read["floor_half_h"],
    )


def misreadings(
    world: w.World, stream: Sequence[Mapping[str, Any]] = ()
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, kwargs in (
        ("pinned_start", {"pinned_start": True}),
        ("elapsed_hours", {"elapsed_hours": True}),
        ("both", {"pinned_start": True, "elapsed_hours": True}),


        ("sticker_rows_kept", {"keep_full_scale": True}),
    ):
        try:
            out[name] = float(reading_of(world, stream, **kwargs)["hours"])
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
    return out


def candidate_blocks(world: w.World, stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "Every block the plan's own terms still allow."

    budget = world.spec
    left = world.spares_left(stream)
    out: list[dict[str, Any]] = []
    drives = sorted(
        {
            float(budget["drive_floor_a"]),
            world.field_drive_a,
            float(budget["drive_cap_a"]),
            round((float(budget["drive_floor_a"]) + world.field_drive_a) / 2.0, 2),
            round((world.field_drive_a + float(budget["drive_cap_a"])) / 2.0, 2),
        }
    )
    temps = sorted({world.hold_temp_c, float(budget["temp_cap_c"]),
                    round((world.hold_temp_c + float(budget["temp_cap_c"])) / 2.0, 1)})
    for lot in sorted(left):
        for days in range(1, int(budget["days_per_block_cap"]) + 1):
            ports = min(int(budget["ports_cap"]), left[lot])
            if ports < 1:
                continue
            for drive in drives:
                for temp in temps:
                    booking = {
                        "drive_a": drive,
                        "case_temp_c": temp,
                        "ports": ports,
                        "chamber_days": days,
                        "lot": lot,
                    }
                    if chamber.refusal_for(
                        world, stream, charged=world.days_charged(days), **booking
                    ):
                        continue
                    out.append(booking)
    return out


def separation(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    booking: Mapping[str, Any],
    read: Mapping[str, Any] | None = None,
) -> float:
    'How far apart one block would drive the two best-fitting laws, in spreads.'

    read = read if read is not None else reading_of(world, stream)
    table = read["fits"]
    pair = sorted(table, key=lambda law: float(table[law]["worst_spread_mw"]))[:2]
    if len(pair) < 2:
        return 0.0
    step = float(world.spec["block_read_interval_h"])
    span = world.full_scale_mw
    lot = str(booking.get("lot"))
    taken = sum(
        int(item["modules_returned"]) for item in stream if str(item.get("lot")) == lot
    )
    modules = chamber.spare_modules(world, lot, taken, int(booking["ports"]))
    total = 0.0
    hours = step
    while hours <= float(booking["chamber_days"]) * 24.0 + 1e-9:
        row = {
            "hours": hours,
            "drive_a": float(booking["drive_a"]),
            "case_temp_c": float(booking["case_temp_c"]),
        }
        losses = [
            float(table[law]["amplitude"])
            * _shape_of(world.spec["catalogue"][law], soak_hours(world.spec["catalogue"][law], row, world))
            for law in pair
        ]
        for module in modules:
            base = float(module["incoming_mw"])
            seen = [min(base * (1.0 - value), span) for value in losses]
            total += (seen[0] - seen[1]) ** 2
        hours += step
    return math.sqrt(total) / world.read_noise_mw


def best_separation(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    read: Mapping[str, Any] | None = None,
) -> float:
    read = read if read is not None else reading_of(world, stream)
    return max(
        (
            separation(world, stream, booking, read)
            for booking in candidate_blocks(world, stream)
        ),
        default=0.0,
    )


def range_is_closed(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    read: Mapping[str, Any] | None = None,
) -> bool:
    read = read if read is not None else reading_of(world, stream)
    return 2.0 * float(read["floor_half_h"]) <= float(world.spec["review_acts_within_h"])


def nothing_left_to_book(world: w.World, stream: Sequence[Mapping[str, Any]]) -> bool:
    'Whether the days, the spares or the schedule leave nothing to book at all.'

    if world.days_left(stream) < int(world.spec["smallest_block_days"]):
        return True
    if max(world.spares_left(stream).values(), default=0) < 1:
        return True
    if world.served_on(stream) is None:
        return True
    return not candidate_blocks(world, stream)


def stop_is_the_only_answer(
    world: w.World,
    stream: Sequence[Mapping[str, Any]],
    read: Mapping[str, Any] | None = None,
) -> bool:
    'Whether the days, the spares or the range leave nothing worth booking.'

    return nothing_left_to_book(world, stream) or range_is_closed(world, stream, read)


def best_block(
    world: w.World, stream: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    'The block this campaign would book next if it were booking soundly.'

    read = reading_of(world, stream)
    if stop_is_the_only_answer(world, stream, read):
        return None
    scored = [
        (separation(world, stream, booking, read), booking)
        for booking in candidate_blocks(world, stream)
    ]
    if not scored:
        return None
    best = max(value for value, _booking in scored)
    return max(
        (booking for value, booking in scored if value >= best - 1e-9),
        key=lambda booking: (int(booking["ports"]), -int(booking["chamber_days"])),
    )


def walk_to_exhaustion(
    world: w.World, stream: Sequence[Mapping[str, Any]], limit: int = 8
) -> list[dict[str, Any]]:
    'The stream this campaign reaches by booking soundly until nothing is left.'

    grown = [dict(item) for item in stream]
    for _step in range(limit):
        booking = best_block(world, grown)
        if booking is None:
            break
        grown = chamber.extend(
            world, grown, [dict(booking, block_id=f"walk-{len(grown) + 1:02d}")]
        )
    return grown
