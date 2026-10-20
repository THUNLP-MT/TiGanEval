'The five binary project checks, one delivered board pack at a time.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import desk, oracle, reading, world


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _points(value: Any) -> str:
    read = _number(value)
    if read is None:
        return _show(value)
    return format(read, ".1f")


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


def _as_written(value: Any) -> str:
    'A range line as the pack printed it, endpoint by endpoint.'

    if isinstance(value, (list, tuple)):
        if not value:
            return "no entries at all"
        return " then ".join(_points(item) for item in value)
    return _show(value)


def _bundle_list(value: Any) -> str:
    'The bundles the pack priced, with the points it put against each.'

    if not isinstance(value, (list, tuple)):
        return _show(value)
    if not value:
        return "no entries at all"
    written = []
    for item in value:
        if isinstance(item, Mapping):
            written.append(f"{_show(item.get('bundle'))} {_points(item.get('points'))}")
        else:
            written.append(_show(item))
    return ", ".join(written)


def _line(credits: Any, refused: Any) -> str:
    'One request line the way a bill reads it.'

    read = _number(credits)
    spent = f"{_show(credits)} credit" if read == 1.0 else f"{_show(credits)} credits"
    returned = "nothing returned" if refused else "work returned"
    return f"{spent} and {returned}"


def _near(value: Any, wanted: float | None, slack: float) -> bool:
    read = _number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def where(fleet: world.Fleet) -> dict[str, str]:
    return {"campaign": fleet.campaign, "depot": fleet.fleet.capitalize()}


def _named_bundle(fleet: world.Fleet, report: Mapping[str, Any]) -> str:
    'The bundle the pack ships, whenever it names one the vendor supplies.'

    named = report.get("bundle")
    return str(named) if named in reading.BUNDLES else oracle.ship(fleet)


def _shared(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], bundle: str
) -> dict[str, Any]:
    profile = oracle.worst_profile(fleet, bundle)
    raised = sum(
        1 for row in oracle.export_rows(fleet) if row["stage"] == "as_captured"
    )
    return {
        **where(fleet),
        "log_rows": len(oracle.export_rows(fleet)),
        "as_captured_rows": raised,
        "counter_share": _points(
            100.0
            * sum(1 for row in oracle.export_rows(fleet) if row["duty_profile"] == "counter")
            / max(1, len(oracle.export_rows(fleet)))
        ),
        "deciding_profile": profile,
        "deciding_rows": oracle.rows_in_profile(fleet, receipts, profile),
        "thin_profiles": "yard and night",
    }


def fleet_number(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    truth = oracle.fleet_points(fleet)
    wanted = oracle.ship(fleet)
    named = report.get("bundle")
    points = report.get("fleet_points")
    shared = {
        **_shared(fleet, receipts, _named_bundle(fleet, report)),
        "reported": _points(points),
        "reported_bundle": _show(named),
    }
    if named == wanted and _near(points, truth, oracle.TOLERANCE):
        return _every_bundles_number(fleet, report, shared)
    pooled = oracle.pooled_over_the_log(fleet, receipts)
    captured = oracle.worst_as_captured(fleet, receipts)
    averaged = oracle.profiles_averaged(fleet, receipts)
    if _near(points, pooled[1], oracle.DECOY_SLACK):
        return [_fail("pooled_over_the_log", **shared)]
    if _near(points, captured[1], oracle.DECOY_SLACK):
        return [_fail("rows_scored_as_captured", **shared)]
    if _near(points, averaged[1], oracle.DECOY_SLACK):
        return [_fail("profiles_averaged_not_worst", **shared)]
    if named != wanted:
        return [_fail("bundle_is_not_the_registers", **shared)]
    return [_fail("fleet_number_disagrees", **shared)]


def _every_bundles_number(
    fleet: world.Fleet, report: Mapping[str, Any], shared: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'The pack prices all three bundles, and the one it ships at its headline.'

    printed = report.get("bundle_points")
    listed: dict[str, float] = {}
    if isinstance(printed, (list, tuple)):
        for item in printed:
            if not isinstance(item, Mapping):
                continue
            value = _number(item.get("points"))
            if value is not None:
                listed[str(item.get("bundle"))] = value
    headline = _number(report.get("fleet_points"))
    shipped = str(report.get("bundle"))
    complete = (
        isinstance(printed, (list, tuple))
        and len(printed) == len(reading.BUNDLES)
        and set(listed) == set(reading.BUNDLES)
    )
    accurate = complete and all(
        _near(listed.get(bundle), oracle.bundle_points(fleet, bundle), oracle.TOLERANCE)
        for bundle in reading.BUNDLES
    )
    if accurate and _near(listed.get(shipped), headline, oracle.PRINTED_SLACK):
        if listed[shipped] == min(listed.values()):
            return []
        return [
            _fail(
                "bundle_not_lowest_printed",
                **shared,
                bundle_list=_bundle_list(printed),
            )
        ]
    return [_fail("bundle_numbers_missing", **shared, bundle_list=_bundle_list(printed))]


def published_range(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    "Everything about a published range except whether it holds the fleet's     own number, which `range_holds` reads across the fleets together."

    published = report.get("points_range")
    bundle = _named_bundle(fleet, report)
    profile = oracle.measured_profile(fleet, receipts, bundle)
    rows = oracle.rows_in_profile(fleet, receipts, profile)
    shared = {
        **where(fleet),
        "reported_range": _pair(published),
        "deciding_profile": profile,
        "deciding_rows": rows,
        "reported_profile": _show(report.get("worst_profile")),
        "reported_rows": _show(report.get("rows_used")),
    }
    centre = _number(report.get("fleet_points"))
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [
            _fail("range_is_not_an_interval", **shared, reported=_as_written(published))
        ]
    if centre is not None and not (float(published[0]) <= centre <= float(published[1])):


        return [_fail("number_outside_its_range", **shared, reported=_points(centre))]
    width = float(published[1]) - float(published[0])
    basis = (
        centre
        if centre is not None and 0.0 <= centre <= 100.0
        else oracle.measured_points(fleet, receipts, bundle)
    )
    honest = oracle.range_width(basis, rows)
    if width < honest * oracle.RANGE_FLOOR:
        return [_fail("range_below_floor", **shared, width=_points(width))]
    if width > honest * oracle.RANGE_CEILING:
        return [_fail("range_wider_than_the_rows_leave", **shared, width=_points(width))]
    bay_problem = _bay_behind_the_number(fleet, receipts, report, shared)
    if bay_problem:
        return bay_problem
    claimed = float(report["rows_used"])
    claimed_width = honest * (rows / claimed) ** 0.5
    if not (
        claimed_width * oracle.RANGE_FLOOR
        <= width
        <= claimed_width * oracle.RANGE_CEILING
    ):
        return [
            _fail(
                "range_rows_disagree",
                **shared,
                width=_points(width),
                held_rows=rows,
            )
        ]
    return []


def _bay_behind_the_number(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    shared: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'The pack says which bay the range stands on and how much is behind it.'

    named = report.get("worst_profile")
    claimed = _number(report.get("rows_used"))
    held = (
        oracle.rows_in_profile(fleet, receipts, str(named))
        if named in world.PROFILES
        else 0
    )
    if (
        named in world.PROFILES
        and named == shared.get("deciding_profile")
        and claimed is not None
        and claimed.is_integer()
        and 0 < claimed <= held
    ):
        return []
    return [
        _fail("deciding_bay_not_named", **shared, held_rows=held)
    ]


def range_holds(fleet: world.Fleet, report: Mapping[str, Any]) -> bool:
    published = report.get("points_range")
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
    ):
        return False
    truth = oracle.fleet_points(fleet)
    return float(published[0]) <= truth <= float(published[1])


def undercovers(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> dict[str, Any]:
    profile = oracle.measured_profile(fleet, receipts, _named_bundle(fleet, report))
    return _fail(
        "range_undercovers",
        **where(fleet),
        deciding_profile=profile,
        deciding_rows=oracle.rows_in_profile(fleet, receipts, profile),
        reported_range=_pair(report.get("points_range")),
        reported=_points(report.get("fleet_points")),
    )


def invariance(
    fleet: world.Fleet,
    kind: str,
    base: Mapping[str, Any],
    other: Mapping[str, Any],
    label: str,
) -> list[dict[str, Any]]:
    first, second = base.get("fleet_points"), other.get("fleet_points")
    moved = None
    if _number(first) is not None and _number(second) is not None:
        moved = abs(float(first) - float(second))
    shared = {
        **where(fleet),
        "reissue": label,
        "first_reading": _points(first),
        "second_reading": _points(second),
        "gap": _points(moved),
    }
    if base.get("bundle") != other.get("bundle"):
        return [_fail(kind, **shared)]
    if moved is None or moved > oracle.INVARIANCE:
        return [_fail(kind, **shared)]
    return []


def next_capture(
    fleet: world.Fleet, receipts: Sequence[Mapping[str, Any]], answer: Any
) -> list[dict[str, Any]]:
    settings = desk.terms(fleet)
    shared = {
        **where(fleet),
        "credits_left": oracle.credits_left(fleet, receipts),
        "credits_granted": int(fleet.spec["credits_granted"]),
        "minimum": int(settings["min_rows_per_request"]),
        "cap": int(settings["max_rows_per_request"]),
        "deciding_profile": oracle.deciding_profiles(fleet, receipts)[0],
    }
    choices = list(answer) if isinstance(answer, list) else [answer]
    if not choices:
        return [
            _fail(
                "capture_is_not_a_request_or_a_stop",
                **shared,
                reported=_show(answer),
                cell="no cell at all",
            )
        ]
    for choice in choices:
        problem = oracle.plan_is_allowed(fleet, receipts, choice)
        if problem is None:
            continue
        asked = choice if isinstance(choice, Mapping) else {}
        cell = (
            f"{asked.get('duty_profile')} on {asked.get('firmware')}, "
            f"{asked.get('condition')} captures"
            if asked
            else _show(choice)
        )
        return [
            _fail(
                problem,
                **shared,
                reported=(
                    f"{asked.get('rows')} rows of {cell}" if asked else _show(choice)
                ),
                cell=cell,
            )
        ]
    return []


def reconciliation(
    fleet: world.Fleet,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    receipts_error: str | None,
) -> list[dict[str, Any]]:
    shared = where(fleet)
    if receipts_error:
        return [_fail("receipts_unreadable", **shared, reason=str(receipts_error))]
    listed = report.get("requests")
    billed = {str(entry["receipt_id"]): entry for entry in receipts}
    charged_for = len(receipts)
    if not isinstance(listed, list):
        return [
            _fail(
                "requests_are_not_a_list",
                **shared,
                reported=_show(listed),
                charged_for=charged_for,
            )
        ]
    seen: dict[str, int] = {}
    for row in listed:
        if not isinstance(row, Mapping):
            return [
                _fail(
                    "requests_are_not_a_list",
                    **shared,
                    reported=_show(row),
                    charged_for=charged_for,
                )
            ]
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [
                _fail("request_counted_twice", **shared, receipt_id=key, times=seen[key])
            ]
        entry = billed.get(key)
        if entry is None:
            return [
                _fail(
                    "request_not_on_the_receipts",
                    **shared,
                    receipt_id=key,
                    charged_for=charged_for,
                )
            ]
        rows = _number(row.get("rows_returned"))
        if rows is None or abs(rows - int(entry["rows_returned"])) > 0.0:
            return [
                _fail(
                    "rows_above_the_receipt",
                    **shared,
                    receipt_id=key,
                    reported_rows=_show(row.get("rows_returned")),
                    desk_rows=int(entry["rows_returned"]),
                )
            ]
        charged = _number(row.get("credits_charged"))
        handed_back = entry.get("refusal") is not None
        if (
            charged is None
            or abs(charged - int(entry["credits_charged"])) > 0.0
            or bool(row.get("refused")) != handed_back
        ):
            return [
                _fail(
                    "line_disagrees_with_the_receipt",
                    **shared,
                    receipt_id=key,
                    reported_line=_line(row.get("credits_charged"), row.get("refused")),
                    desk_line=_line(int(entry["credits_charged"]), handed_back),
                )
            ]
    for key, entry in billed.items():
        if key in seen:
            continue
        kind = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        return [
            _fail(kind, **shared, receipt_id=key, charged_for=charged_for)
        ]
    spent = desk.credits_spent(receipts)
    reported = _number(report.get("credits_used"))
    if reported is None or abs(reported - spent) > 0.0:
        return [
            _fail(
                "credits_disagree_with_the_receipts",
                **shared,
                reported_credits=_show(report.get("credits_used")),
                desk_credits=spent,
            )
        ]
    return []
