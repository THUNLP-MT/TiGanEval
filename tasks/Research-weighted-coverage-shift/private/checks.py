'The five readings of one delivered board, each against the depot it is about.'

from __future__ import annotations

from math import ceil
from typing import Any, Mapping, Sequence

from . import desk, oracle, world


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def near(value: Any, wanted: float | None, slack: float) -> bool:
    read = number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def points(value: Any) -> str:
    'One share written the way the dispatch desk writes it.'

    read = number(value)
    if read is None:
        return show(value)
    return format(read * 100.0, ".1f")


def minutes(pair: Any) -> str:
    if isinstance(pair, (list, tuple)) and len(pair) == 2 and all(
        number(item) is not None for item in pair
    ):
        return f"{int(round(float(pair[0])))} to {int(round(float(pair[1])))} minutes"
    return show(pair)


def show(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".6g")
    if isinstance(value, (list, tuple)):
        return "no entries at all" if not value else f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def where(depot: world.Depot) -> dict[str, str]:
    'The depot a failure happened at, in the words the owner uses for it.'

    name, month = depot.depot.rsplit("-", 2)[0], str(depot.spec["month"])
    return {"depot": depot.depot, "board": name.capitalize(), "month": month}


def fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def windows_of(report: Mapping[str, Any], depot: world.Depot) -> dict[str, tuple[float, float]] | None:
    'The windows a delivered board prints, or None when it prints no board.'

    rows = report.get("windows")
    if not isinstance(rows, list) or not rows:
        return None
    found: dict[str, tuple[float, float]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        name = row.get("job_class")
        pair = row.get("window")
        if not isinstance(name, str) or name not in depot.classes or name in found:
            return None
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return None
        low, high = number(pair[0]), number(pair[1])
        if low is None or high is None or low > high:
            return None
        found[name] = (low, high)
    return found


def rows_behind(
    depot: world.Depot, receipts: Sequence[Mapping[str, Any]], job_class: str
) -> int:
    return len(oracle.usable_diffs(depot, receipts, job_class))


def rate_failures(
    depot: world.Depot,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    windows: Mapping[str, tuple[float, float]] | None,
) -> list[dict[str, Any]]:


    if windows is None:
        return []
    truth = oracle.true_rate(depot, windows)
    reported = report.get("stream_rate")
    if near(reported, truth, oracle.TOLERANCE):
        read = number(reported)
        if read is not None and abs(read * 100.0 - round(read * 100.0)) > 1e-7:
            return [
                fail(
                    "stream_rate_not_to_nearest_point",
                    **where(depot),
                    reported=format(read * 100.0, ".4f").rstrip("0").rstrip("."),
                    rounded=format(round(read * 100.0), ".0f"),
                )
            ]
        return []

    filed = {name: len(oracle.sheet_diffs(depot, name)) for name in depot.classes}
    total_sheets = sum(filed.values())
    stopped = [name for name in depot.classes if oracle.stopped(depot, name)]
    unprinted = [name for name in depot.classes if windows is not None and name not in windows]
    unprinted_class = (
        max(unprinted, key=lambda name: (depot.share(name), name))
        if unprinted
        else "none"
    )
    shared = {
        **where(depot),
        "reported": points(reported),
        "expected": points(truth),
        "sheets_total": total_sheets,
        "jobs_total": len(depot.month),
        "stopped_class": stopped[0] if stopped else "none",
        "sheet_share": points(
            filed[stopped[0]] / total_sheets if stopped and total_sheets else 0.0
        ),
        "stream_share": points(depot.share(stopped[0]) if stopped else 0.0),
        "unprinted_class": unprinted_class,
        "unprinted_share": points(
            depot.share(unprinted_class) if unprinted_class != "none" else 0.0
        ),
    }
    if near(reported, oracle.read_off_the_sheets(depot, receipts, windows), oracle.DECOY_SLACK):
        return [fail("rate_read_off_the_sheets", **shared)]
    for reading in oracle.printed_classes_only(depot, receipts, windows):
        if near(reported, reading, oracle.WIDE_SLACK):
            return [fail("unprintable_class_left_out_of_denominator", **shared)]
    return [fail("stream_rate_disagrees", **shared)]


def window_failures(
    depot: world.Depot,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    windows: Mapping[str, tuple[float, float]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    'Everything about the printed windows, split into shape and holding.'

    limit = int(depot.spec["window_limit_minutes"])
    if windows is None:
        return [fail("windows_are_not_a_list", **where(depot),
                     reported=show(report.get("windows")),
                     classes=len(depot.classes))], []
    missing = [
        name
        for name in depot.classes
        if name not in windows and oracle.printable(depot, receipts, name)
    ]
    alike = len({pair for pair in windows.values()}) == 1 and len(windows) > 1
    entries = {
        str(row.get("job_class")): row
        for row in report.get("windows", ())
        if isinstance(row, Mapping)
    }
    shape: list[dict[str, Any]] = []
    holding: list[dict[str, Any]] = []
    for name in depot.classes:
        if name not in windows:
            continue
        low, high = windows[name]
        edge = oracle.floor_for(depot, receipts, name)
        loose = oracle.loose_floor(depot, receipts, name)
        half = (high - low) / 2.0
        held = oracle.class_hold(depot, name, low, high)
        expected_half = int(ceil(edge)) if edge is not None else 0
        expected_rows = rows_behind(depot, receipts, name)
        reported_rows = number(entries[name].get("sheets_used"))
        common = {
            **where(depot),
            "job_class": name,
            "reported_window": minutes([low, high]),
            "rows_behind": expected_rows,
            "floor": expected_half,
            "limit": limit,
            "held": points(held),
            "expected_window": minutes([-expected_half, expected_half]),
            "reported_sheets": show(entries[name].get("sheets_used")),
            "expected_sheets": expected_rows,
        }
        if not oracle.printable(depot, receipts, name):
            shape.append(fail("window_without_support", **common))
            if held < oracle.HOLD_FLOOR:
                holding.append(fail("window_does_not_hold_its_class", **common))
            continue
        if high - low > limit:
            shape.append(fail("window_over_the_limit", **common))
            continue
        if not low.is_integer() or not high.is_integer() or low != -high:
            shape.append(fail("window_not_symmetric_whole_minutes", **common))
            continue
        if alike and half != expected_half:
            shape.append(fail("one_window_for_all_classes", **common,
                              printed=len(windows)))
            continue
        if half < expected_half:
            if alike:
                shape.append(fail("one_window_for_all_classes", **common,
                                  printed=len(windows)))
            elif loose is not None and half == int(ceil(loose)):
                shape.append(fail("cut_ignores_printed_job", **common))
            else:
                shape.append(fail("window_under_the_sheet_floor", **common))
            continue
        if half > expected_half:
            shape.append(fail("window_not_tight", **common))
            continue
        if reported_rows is None or reported_rows != expected_rows:
            shape.append(fail("sheets_used_disagrees", **common))
            continue
        if held < oracle.HOLD_FLOOR:
            holding.append(fail("window_does_not_hold_its_class", **common))
    for name in missing:
        edge = oracle.floor_for(depot, receipts, name)
        shape.append(
            fail(
                "window_misses_the_class",
                **where(depot),
                job_class=name,
                reported_window="nothing at all",
                rows_behind=rows_behind(depot, receipts, name),
                floor=int(ceil(edge)) if edge is not None else 0,
                limit=limit,
                held=points(0.0),
            )
        )
    return shape, holding


def plan_failures(
    depot: world.Depot, state: Mapping[str, Any], answer: Any
) -> list[dict[str, Any]]:
    receipts = state["receipts"]
    context = depot.visit_terms()
    wanted = oracle.actionable_class(depot, receipts) or oracle.wanted_class(
        depot, receipts
    )
    shared = {
        **where(depot),
        "units_left": desk.units_left(depot, receipts),
        "units_granted": int(depot.spec["units_granted"]),
        "job_class": wanted or "none",
        "roster_weeks": ", ".join(
            str(week) for week in context["roster"].get(wanted or "", ())
        ) or "none",
        "jobs_per_visit": int(context["jobs_per_visit"]),
        "visits_per_week": int(context["visits_per_week"]),
    }
    choices = list(answer) if isinstance(answer, list) else [answer]
    if not choices:
        return [fail("visit_is_not_a_booking_or_a_stop", **shared,
                     reported=show(answer), week_asked="none", class_asked="none")]
    for choice in choices:
        problem = oracle.plan_is_allowed(depot, receipts, choice)
        if problem is None:
            continue
        asked = choice if isinstance(choice, Mapping) else {}
        asked_week = asked.get("week")
        week_visits = (
            desk.visits_in_week(receipts, asked_week)
            if isinstance(asked_week, int) and not isinstance(asked_week, bool)
            else "unknown"
        )
        reported = (
            f"{asked.get('jobs')} jobs on {asked.get('job_class')} in week {asked.get('week')}"
            if asked
            else show(choice)
        )
        return [
            fail(
                problem,
                **shared,
                reported=reported,
                week_asked=str(asked.get("week", "none")),
                class_asked=str(asked.get("job_class", "none")),
                week_visits=week_visits,
            )
        ]
    return []


def receipt_failures(
    depot: world.Depot,
    receipts: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    receipts_error: str | None,
) -> list[dict[str, Any]]:
    place = where(depot)
    if receipts_error:
        return [fail("receipts_unreadable", **place, reason=str(receipts_error))]
    rows = report.get("visits")
    paid_for = len(receipts)
    if not isinstance(rows, list):
        return [fail("visits_are_not_a_list", **place, reported=show(rows),
                     paid_for=paid_for)]
    billed = {str(entry["receipt_id"]): entry for entry in receipts}
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [fail("visits_are_not_a_list", **place, reported=show(row),
                         paid_for=paid_for)]
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [fail("visit_counted_twice", **place, receipt_id=key,
                         times_reported=seen[key], paid_for=paid_for)]
        entry = billed.get(key)
        if entry is None:
            return [fail("visit_not_on_the_receipts", **place, receipt_id=key,
                         paid_for=paid_for)]
        reported_class = row.get("job_class")
        if not isinstance(reported_class, str) or reported_class != str(entry["job_class"]):
            return [fail("class_disagrees_with_the_receipt", **place, receipt_id=key,
                         class_reported=show(reported_class),
                         receipt_class=str(entry["job_class"]), paid_for=paid_for)]
        reported_jobs = number(row.get("jobs_returned"))
        if reported_jobs is None or abs(reported_jobs - int(entry["jobs_returned"])) > 0.0:
            return [fail("jobs_disagree_with_the_receipt", **place, receipt_id=key,
                         jobs_reported=show(row.get("jobs_returned")),
                         receipt_jobs=int(entry["jobs_returned"]), paid_for=paid_for)]
        reported_units = number(row.get("units_charged"))
        if reported_units is None or abs(reported_units - int(entry["units_charged"])) > 0.0:
            return [fail("units_disagree_with_the_receipt", **place, receipt_id=key,
                         units_reported=show(row.get("units_charged")),
                         receipt_units=int(entry["units_charged"]), paid_for=paid_for)]
    for refusals_first in (True, False):
        for key, entry in billed.items():
            if key in seen or bool(entry.get("refusal")) is not refusals_first:
                continue
            kind = "refusal_uncounted" if refusals_first else "visit_missing_from_the_report"
            return [fail(kind, **place, receipt_id=key, paid_for=paid_for,
                         receipt_units=int(entry["units_charged"]))]
    left = int(depot.spec["units_granted"]) - desk.units_spent(receipts)
    reported_left = number(report.get("units_left"))
    if reported_left is None or abs(reported_left - left) > 0.0:
        return [fail("units_left_disagrees", **place,
                     reported_units=show(report.get("units_left")),
                     receipt_units=left, paid_for=paid_for)]
    return []
