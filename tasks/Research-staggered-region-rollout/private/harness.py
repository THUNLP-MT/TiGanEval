'Read one delivered rollout notebook against the world it is a reading of.'

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, publish, receipts as rcp, workload
from . import world as w

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-region-rollout-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

NETWORK = workload.CURRENT.network

BUCKETS: Mapping[str, str] = {
    "rollout_effect_within_tolerance": "effect_failures",
    "report_reconciles_receipts": "receipt_failures",
    "range_covers_and_meets_floor": "range_failures",
    "next_week_feasible_and_informative": "plan_failures",
    "estimate_invariant_to_migration_and_rollback": "stability_failures",
}


FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "rollout_effect_within_tolerance": (
        "rate_read_across_stack_change",
        "compares_against_already_live",
        "rolled_back_metro_counted_live",
        "effect_disagrees",
        "effect_wrong_on_another_network",
        "effect_wrong_where_she_cannot_name_it",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "measurements_are_not_a_list",
        "receipt_missing",
        "refusal_uncounted",
        "region_week_counted_twice",
        "week_not_on_the_receipts",
        "receipts_wrong_on_another_network",
        "receipts_wrong_where_she_cannot_name_it",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_absent",
        "range_undercovers",
        "range_below_floor",
        "range_wider_than_the_evidence",
        "metro_days_not_reported",
        "range_wrong_on_another_network",
        "range_wrong_where_she_cannot_name_it",
        "candidate_execution_failed",
    ),
    "next_week_feasible_and_informative": (
        "booking_on_a_live_metro",
        "booking_single_arm",
        "booking_over_cap",
        "plan_is_not_a_booking_or_a_stop",
        "stopped_with_capacity_left",
        "booking_uninformative",
        "booking_wrong_on_another_network",
        "booking_wrong_where_she_cannot_name_it",
        "candidate_execution_failed",
    ),
    "estimate_invariant_to_migration_and_rollback": (
        "stability_reading_missing",
        "hardcoded_history",
        "moves_with_migration_offset",
        "moves_with_rollback_week",
        "candidate_execution_failed",
    ),
}


CARRY_OVER: Mapping[str, tuple[str, ...]] = {
    "effect_failures": ("effect_wrong_on_another_network",),
    "receipt_failures": ("receipts_wrong_on_another_network",),
    "range_failures": ("range_wrong_on_another_network",),
    "plan_failures": ("booking_wrong_on_another_network",),
}


CARRY_OVER_UNNAMED: Mapping[str, str] = {
    "effect_failures": "effect_wrong_where_she_cannot_name_it",
    "receipt_failures": "receipts_wrong_where_she_cannot_name_it",
    "range_failures": "range_wrong_where_she_cannot_name_it",
    "plan_failures": "booking_wrong_where_she_cannot_name_it",
}


_NAMING_ORDER: tuple[str, ...] = workload.NAMING_ORDER


def _naming_rank(network: str) -> int:
    return _NAMING_ORDER.index(network) if network in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Sort key that puts the incident she can open a register for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("network") == NETWORK else 1,
    )


def _written_off_the_live_network(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the network the programme manager holds."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [record for record in rows if record.get("network") == NETWORK]
    if here:
        return here


    stopped = [
        record for record in rows if str(record.get("kind")) == CANDIDATE_FAILURE
    ]
    if stopped:
        return stopped
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    nameable = [
        record for record in rows if str(record.get("network", "")) in _NAMING_ORDER
    ]
    if not nameable:
        elsewhere = sorted({str(record["network"]) for record in rows if record.get("network")})
        return [
            _fail(
                CARRY_OVER_UNNAMED[bucket],
                network=NETWORK,
                other_readouts=len(elsewhere) or len(rows),
            )
        ]
    mode = modes[0]
    named = min(
        nameable,
        key=lambda record: _naming_rank(str(record["network"])),
    )
    elsewhere = sorted({str(record["network"]) for record in nameable})
    carried = {
        "network": NETWORK,
        "other_network": str(named.get("network")),
        "other_networks": len(elsewhere),
    }
    for key in ("region", "region_weeks_left"):
        if key in named:
            carried[key] = named[key]
    return [_fail(mode, **carried)]


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
    return float(value)


def _near(value: Any, wanted: float, slack: float) -> bool:
    read = _number(value)
    return read is not None and abs(read - wanted) <= slack


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The region-weeks this delivery has paid for, or why they will not read.'

    try:
        return rcp.read_ledger(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def live_network(entries: Sequence[Mapping[str, Any]]) -> w.Network:
    'Halcombe as it stands once every week on the receipts has been served.'

    extra = [
        entry for entry in list(entries)[len(workload.HISTORY_BOOKINGS):]
        if not entry.get("refusal")
    ]
    return w.with_bookings(workload.CURRENT_SPEC, extra) if extra else workload.CURRENT


def spent_receipts(
    network: w.Network, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The receipts after the grant has been charged down to nothing.'

    grown = [dict(entry) for entry in entries]
    names = [item.name for item in network.regions]
    for week in network.spec["bookable_weeks"]:
        for name in names:
            if rcp.weeks_left(network, grown) < 1:
                return grown
            if any(entry["receipt_id"] == rcp.receipt_id(name, week) for entry in grown):
                continue
            grown.append(rcp.make_receipt(network, grown, name, str(week), 30))
    return grown


def refused_receipts(
    network: w.Network, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'The receipts after one week the wave board handed back.'

    grown = [dict(entry) for entry in entries]
    week = str(network.spec["bookable_weeks"][0])
    for item in network.regions:
        if item.live_from is not None and str(item.live_from) <= w.shift(week, 6):
            grown.append(rcp.make_receipt(network, grown, item.name, week, 30))
            return grown
    return grown


def instances(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Halcombe, then the networks the same notebook is used on next.'

    live = live_network(entries)
    floor = int(live.spec["minimum_orders_per_day"])
    floor_boundary = replace(
        live,
        regions=tuple(
            replace(item, orders_per_day=floor)
            if item.name == "Fennhaven"
            else item
            for item in live.regions
        ),
    )
    here = [dict(item) for item in entries]
    rows: list[dict[str, Any]] = [
        {
            "label": NETWORK,
            "network": live,
            "receipts": here,
            "plans": [
                {"base": workload.CURRENT, "receipts": here},
                {"base": workload.CURRENT,
                 "receipts": refused_receipts(workload.CURRENT, here)},
                {"base": workload.CURRENT,
                 "receipts": spent_receipts(workload.CURRENT, here)},


                {"base": floor_boundary, "receipts": here},
            ],
        }
    ]
    for network in (
        *workload.SIBLINGS,
        *workload.PARTNERS,
        workload.OUT_OF_REGIME,
    ):
        ledger = rcp.history(network, ())
        rows.append(
            {
                "label": network.network,
                "network": network,
                "receipts": ledger,
                "plans": [{"base": network, "receipts": ledger}],
            }
        )
    return rows


class Review:
    def __init__(self) -> None:
        self.failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

    def add(self, bucket: str, kind: str, **fields: Any) -> None:
        self.failures[bucket].append(_fail(kind, **fields))

    def stopped(
        self, buckets: Sequence[str], error: str, *, network: str, request: str
    ) -> None:
        for bucket in buckets:
            self.failures[bucket].insert(
                0,
                _fail(
                    CANDIDATE_FAILURE,
                    error=error,
                    network=network,
                    request=request,
                ),
            )


_MISREADINGS = (
    ("rate_read_across_stack_change",
     ("printed", "printed_live", "printed_rollback", "printed_live_rollback",
      "two_way_fit")),
    ("compares_against_already_live",
     ("live_controls", "live_controls_rollback", "two_way_fit_sampled")),
    ("rolled_back_metro_counted_live", ("rollback",)),
)


def explanation(
    readings: Mapping[str, float], networks: Mapping[str, w.Network]
) -> str | None:
    'The one misreading that accounts for this delivery on most of the networks.'

    best: tuple[int, str | None] = (0, None)
    for mode, families in _MISREADINGS:
        hits = 0
        for label, value in readings.items():
            if label not in networks:
                continue
            spread = oracle.misreadings(networks[label])
            truth = oracle.truth(networks[label])
            if any(
                _near(value, spread[family], oracle.CLASSIFY_SLACK)
                and abs(spread[family] - truth) > oracle.TOLERANCE
                for family in families
            ):
                hits += 1
        if hits > best[0]:
            best = (hits, mode)
    return best[1] if readings and best[0] * 2 >= len(readings) else None


def wave_metro(network: w.Network) -> tuple[str, int]:
    'The metro whose stack moved furthest ahead of its own go-live date.'

    pairs = [
        (item.name, w.between(item.stack_migrated_on, str(item.live_from)))
        for item in network.regions
        if item.live_from and item.stack_migrated_on
    ]
    name, gap = max(pairs, key=lambda pair: (pair[1], pair[0]))
    return name, int(gap)


def metro_days_across_the_move(network: w.Network) -> int:
    "Metro-days in the reading that sit the far side of that metro's stack move."

    total = 0
    for name in network.measured_regions():
        item = network.region(name)
        days = sorted({*network.baseline_days(name), *network.exposure_days(name)})
        if not item.stack_migrated_on or not days:
            continue
        if not days[0] < item.stack_migrated_on <= days[-1]:
            continue
        total += sum(1 for day in days if day >= item.stack_migrated_on)
    return total


def live_comparisons(network: w.Network) -> tuple[str, int]:
    'The band with the most comparison metro-days that were already live, and how many.'

    counts: dict[str, int] = {}
    for name in network.measured_regions():
        band = network.region(name).band
        for day in network.exposure_days(name):
            waiting = set(network.controls_for(name, day))
            for other in oracle.controls_of(network, name, day, only_waiting=False):
                if other not in waiting:
                    counts[band] = counts.get(band, 0) + 1
    if not counts:
        return "", 0
    band = max(sorted(counts), key=lambda key: counts[key])
    return band, counts[band]


def rolled_back(network: w.Network) -> tuple[str, str, int]:
    'The metro sent back to the old flow, the morning it was, and the days after.'

    for item in network.regions:
        if item.disabled_on and item.live_from:
            ran = len(network.exposure_days(item.name))
            return item.name, str(item.disabled_on), int(network.spec["exposure_days"]) - ran
    return "", "", 0


def _check_effect(
    review: Review, network: w.Network, report: Mapping[str, Any], mode: str | None
) -> None:
    truth = oracle.truth(network)
    reported = report.get("effect_points")
    if _near(reported, truth, oracle.TOLERANCE):
        return
    shared = {
        "network": network.network,
        "reported_points": (
            _points(reported) if _number(reported) is not None else _show(reported)
        ),
    }
    if _number(reported) is None or mode is None:


        review.add(
            "effect_failures", "effect_disagrees", **shared,
            bar_points=_points(network.spec["board_bar_points"]),
        )
        return
    if mode == "rate_read_across_stack_change":
        name, gap = wave_metro(network)
        review.add(
            "effect_failures", mode, **shared, region=name, migrated_ahead_days=gap,
            metro_days_across_the_move=metro_days_across_the_move(network),
        )
        return
    if mode == "compares_against_already_live":
        band, count = live_comparisons(network)
        review.add("effect_failures", mode, **shared, band=band, live_comparisons=count)
        return
    name, disabled_on, days_after = rolled_back(network)
    review.add(
        "effect_failures", mode, **shared, region=name, disabled_on=disabled_on,
        days_after=days_after,
    )


def _check_range(
    review: Review, network: w.Network, report: Mapping[str, Any], reading_ok: bool
) -> bool:
    'The width the sampled orders support. Returns whether the truth is held.'

    reported = report.get("effect_range_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or reported[0] > reported[1]
    ):
        review.add("range_failures", "range_absent", network=network.network,
                   reported=_pair(reported))
        return False
    point = _number(report.get("effect_points"))
    if point is None or not float(reported[0]) <= point <= float(reported[1]):
        review.add("range_failures", "range_absent", network=network.network,
                   reported=_pair(reported))
    supported = oracle.half_width(network)
    width = (float(reported[1]) - float(reported[0])) / 2.0
    fields = {
        "network": network.network,
        "reported_range": _pair(reported),
        "networks_reviewed": int(network.spec["networks_reviewed"]),
    }
    days = _number(report.get("metro_days"))
    expected_days = oracle.region_days(network)
    if days is None or days <= 0 or days != int(days):
        review.add("range_failures", "metro_days_not_reported", **fields,
                   reported_metro_days=_show(report.get("metro_days")),
                   expected_metro_days=expected_days)
    elif not reading_ok:
        pass
    elif days != expected_days:
        review.add("range_failures", "metro_days_not_reported", **fields,
                   reported_metro_days=_show(report.get("metro_days")),
                   expected_metro_days=expected_days)
    elif width < supported * oracle.NARROW_FACTOR:
        review.add("range_failures", "range_below_floor", **fields,
                   sampled_orders=oracle.sampled_orders(network))
    elif width > supported * oracle.WIDE_FACTOR:


        review.add("range_failures", "range_wider_than_the_evidence", **fields,
                   metro_days=int(days))
    truth = oracle.truth(network)
    return float(reported[0]) <= truth <= float(reported[1])


def published_width(report: Mapping[str, Any]) -> float | None:
    'The width of the range this readout printed, when it printed one.'

    reported = report.get("effect_range_points")
    if (
        not isinstance(reported, list)
        or len(reported) != 2
        or any(_number(item) is None for item in reported)
        or float(reported[0]) > float(reported[1])
    ):
        return None
    return float(reported[1]) - float(reported[0])


def _check_receipts(
    review: Review,
    network: w.Network,
    report: Mapping[str, Any],
    ledger: Sequence[Mapping[str, Any]],
    error: str | None,
) -> None:
    if error:
        review.add("receipt_failures", "receipts_unreadable", network=network.network,
                   reason=str(error))
        return
    rows = report.get("measurements")
    if not isinstance(rows, list):
        review.add("receipt_failures", "measurements_are_not_a_list",
                   network=network.network, reported=_show(rows), charged=len(ledger))
        return
    billed = {str(item["receipt_id"]): item for item in ledger}
    seen: dict[str, int] = {}
    for row in rows:
        identifier = str(row.get("receipt_id"))
        seen[identifier] = seen.get(identifier, 0) + 1
        if seen[identifier] > 1:
            review.add("receipt_failures", "region_week_counted_twice",
                       network=network.network, receipt_id=identifier,
                       times_reported=seen[identifier])
            return
        entry = billed.get(identifier)
        if (
            entry is None
            or str(row.get("region")) != str(entry["region"])
            or str(row.get("week")) != str(entry["week"])
            or not _near(row.get("region_weeks_charged"),
                         float(entry["region_weeks_charged"]), 0.0)
            or not _near(row.get("days_returned"), float(entry["days_returned"]), 0.0)
        ):
            review.add("receipt_failures", "week_not_on_the_receipts",
                       network=network.network, receipt_id=identifier, charged=len(ledger))
            return
    for identifier, entry in billed.items():
        if identifier in seen:
            continue
        mode = "refusal_uncounted" if entry.get("refusal") else "receipt_missing"
        review.add(
            "receipt_failures", mode, network=network.network, receipt_id=identifier,
            region=str(entry["region"]), week=str(entry["week"]), charged=len(ledger),
            refusal=str(entry.get("refusal") or ""),
        )
        return


def _check_plan(
    review: Review,
    base: w.Network,
    ledger: Sequence[Mapping[str, Any]],
    width: float | None,
    answer: Any,
) -> None:
    'The next week has to be one the wave board will serve and learn from.'

    state = oracle.plan_state(base, ledger)
    left = rcp.weeks_left(base, ledger)
    bar = float(base.spec["board_bar_points"])
    inside = width is not None and width <= bar
    shared = {
        "network": base.network,
        "region_weeks_left": left,
        "bar_points": _points(bar),
    }
    if not isinstance(answer, list) or not answer:
        review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                   reported=_show(answer))
        return
    for choice in answer:
        if isinstance(choice, str):
            if choice != "stop":
                review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                           reported=_show(choice))
                return
            if not (inside or state["nothing_to_buy"] or left < 1):
                review.add("plan_failures", "stopped_with_capacity_left", **shared,
                           reported_range_width=_points(width) if width is not None
                           else "empty")
                return
            continue
        if not isinstance(choice, dict):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(choice))
            return
        region = choice.get("region")
        week = choice.get("week")
        share = _number(choice.get("holdback_share"))
        names = {item.name for item in base.regions}
        if (
            not isinstance(region, str) or region not in names
            or not isinstance(week, str) or share is None or share != int(share)
        ):
            review.add("plan_failures", "plan_is_not_a_booking_or_a_stop", **shared,
                       reported=_show(
                           f"{_show(region)} in {_show(week)} at "
                           f"{_show(choice.get('holdback_share'))} percent"
                       ))
            return
        share = int(share)
        item = base.region(region)
        named = {**shared, "region": region, "week": week, "holdback_share": share}
        if item.live_from is not None and str(item.live_from) <= w.shift(week, 6):
            review.add("plan_failures", "booking_on_a_live_metro", **named,
                       live_from=str(item.live_from))
            return
        if share == 0:
            low, high = (int(value) for value in base.spec["holdback_share_band"])
            review.add("plan_failures", "booking_single_arm", **named,
                       holdback_band=f"{low} to {high}")
            return
        if week not in set(base.spec["bookable_weeks"]):
            review.add("plan_failures", "booking_over_cap", **named,
                       refusal="the wave board is not selling that week")
            return
        if left < 1:
            review.add("plan_failures", "booking_over_cap", **named,
                       refusal="every region-week on the grant is charged")
            return
        if rcp.receipt_id(region, week) in {
            str(entry["receipt_id"]) for entry in ledger
        }:
            review.add("plan_failures", "booking_over_cap", **named,
                       refusal="that region-week is already on the receipts")
            return
        refusal = rcp.refusal_for(base, ledger, region, week, share)
        if refusal:
            review.add("plan_failures", "booking_over_cap", **named, refusal=refusal)
            return
        if state["bar"] is None:
            continue
        after = oracle.half_width_after(base, region, week, share)
        if after > state["bar"] * 1.005:


            beat = state["owner_week"] or {}
            review.add("plan_failures", "booking_uninformative", **named,
                       book_orders=int(base.book_orders().get(region, 0)),
                       largest_region=str(beat.get("region", "")))
            return


def _check_stability(review: Review, readings: Mapping[str, float]) -> None:


    if review.failures["stability_failures"]:
        return
    expected = {workload.CURRENT.network, workload.SIBLINGS[2].network}
    for base, partner, _ in workload.STABILITY_PAIRS:
        expected.update((base.network, partner.network))
    missing = expected - set(readings)
    if missing:
        review.add(
            "stability_failures", "stability_reading_missing", network=NETWORK,
            readouts_missing=len(missing),
        )
        return
    live = readings.get(NETWORK)
    if live is not None:
        carried = workload.SIBLINGS[2].network
        other = readings.get(carried)
        if (
            other is not None
            and abs(live - other) < 1e-6
            and abs(oracle.truth(workload.CURRENT) - oracle.truth(workload.SIBLINGS[2]))
            > oracle.CARRIED_OVER_GAP
        ):
            review.add("stability_failures", "hardcoded_history", network=NETWORK,
                       other_network=carried, reported_points=_points(live))
            return
    for base, partner, mode in workload.STABILITY_PAIRS:
        first = readings.get(base.network)
        second = readings.get(partner.network)
        if first is None or second is None:
            continue
        if abs(first - second) > oracle.INVARIANCE_SLACK:
            review.add(
                "stability_failures",
                mode,
                network=base.network,
                other_network=partner.network,
                region=rolled_back(base)[0] if "rollback" in mode else wave_metro(base)[0],
                reported_points=_points(first),
                other_points=_points(second),
                moved_by=_points(abs(first - second)),
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
    return f"the rollout notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every network and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, receipt_error = live_receipts(Path(artifact_dir))
        rows = instances(entries)
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(network: w.Network) -> int:
            if id(network) not in seen:
                seen[id(network)] = len(contexts)
                contexts.append(network.context())
            return seen[id(network)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[Mapping[str, Any], int]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["network"]),
                 "receipts": row["receipts"]}
            )
            for state in row["plans"]:
                plans.append((state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": context_index(state["base"]),
                     "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"network": NETWORK, "region_weeks_charged": len(entries)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the networks"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        readings: dict[str, float] = {}
        networks: dict[str, w.Network] = {}
        widths: dict[str, float | None] = {}
        for row, index in reports:
            value, _error = answer(index)
            report = dict(value or {}) if value else {}
            reading = _number(report.get("effect_points")) if report else None
            widths[row["network"].network] = published_width(report)
            if reading is not None:
                readings[row["network"].network] = reading
                networks[row["network"].network] = row["network"]
        mode = explanation(readings, networks)
        held: list[bool] = []
        covered: dict[str, bool] = {}
        stopped = False
        for row, index in reports:
            network = row["network"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("effect_failures", "range_failures", "receipt_failures",
                     "stability_failures"),
                    error,
                    network=network.network,
                    request="report",
                )
                continue
            report = dict(value or {})
            _check_effect(review, network, report, mode)
            reading_ok = _near(
                report.get("effect_points"), oracle.truth(network), oracle.TOLERANCE
            )
            range_held = _check_range(review, network, report, reading_ok)
            held.append(range_held)
            covered[network.network] = range_held
            _check_receipts(
                review, network, report, row["receipts"],
                receipt_error if network.network == NETWORK else None,
            )
        for state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        error=error,
                        network=state["base"].network,
                        request="plan",
                    )
                )
                continue
            _check_plan(
                review, state["base"], state["receipts"],
                widths.get(state["base"].network), value,
            )


        contract_held = sum(
            1 for item in (workload.CURRENT, *workload.SIBLINGS)
            if covered.get(item.network)
        )
        if held and not all(held):
            for row, index in reports:
                value, error = answer(index)
                if error is not None:
                    continue
                reported = dict(value or {}).get("effect_range_points")
                truth = oracle.truth(row["network"])
                if (
                    isinstance(reported, list)
                    and len(reported) == 2
                    and all(_number(item) is not None for item in reported)
                    and not (float(reported[0]) <= truth <= float(reported[1]))
                ):
                    review.add(
                        "range_failures",
                        "range_undercovers",
                        network=row["network"].network,
                        reported_range=_pair(reported),
                        networks_reviewed=int(row["network"].spec["networks_reviewed"]),
                        networks_held=contract_held,
                    )
        _check_stability(review, readings)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_network(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "network": NETWORK,
            "region_weeks_charged": len(entries),
            "networks_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working-session record must contain a JSON object")
    return raw


def snapshot(network: w.Network, record: Mapping[str, Any]) -> dict[str, Any]:
    "The network's evidence as it stood on the day of one working session."

    through = str(record["as_of"])
    context = network.context()
    context["window"]["last_day"] = through
    context["as_of"] = through
    context["daily"] = [row for row in context["daily"] if row["date"] <= through]
    context["order_sample"] = [
        row for row in context["order_sample"] if row["date"] <= through
    ]
    context["dispatch_incidents"] = [
        row for row in context["dispatch_incidents"] if row["date"] <= through
    ]
    context["booked_weeks"] = [
        row for row in context["booked_weeks"] if row["date"] <= through
    ]
    return context


def _by_day(context: Mapping[str, Any], region: str) -> list[dict[str, Any]]:
    "One metro's printed rows and its sampled rows, side by side and unjoined."

    sample = {
        (str(row["region"]), str(row["date"])): row for row in context["order_sample"]
    }
    rows = []
    for row in context["daily"]:
        if str(row["region"]) != region:
            continue
        seen = sample.get((region, str(row["date"])), {})
        rows.append(
            {
                "date": row["date"],
                "orders": row["orders"],
                "ontime_orders": row["ontime_orders"],
                "ontime_rate": row["ontime_rate"],
                "sampled_orders": seen.get("sampled_orders"),
                "ontime_by_placed_at": seen.get("ontime_by_placed_at"),
                "ontime_by_assigned_at": seen.get("ontime_by_assigned_at"),
            }
        )
    return rows


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_receipts(root)
    network = live_network(entries) if not error else workload.CURRENT
    context = network.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session", "date", "analyst", "as_of")},
        })
    return {
        "summary": (
            f"The {context['network']} batching rollout, the wave board's terms and "
            "the working sessions on record."
        ),
        "measurements": {
            "network": context["network"],
            "window": context["window"],
            "as_of": context["as_of"],
            "exposure_days": context["exposure_days"],
            "baseline_days": context["baseline_days"],
            "board_bar_points": context["board_bar_points"],
            "networks_reviewed": context["networks_reviewed"],
            "book": {
                "counted_on": context["book"]["counted_on"],
                "window_closes_on": context["book"]["window_closes_on"],
                "regions": sorted(context["book"]["orders_on_the_count_day"]),
            },
            "capacity": context["capacity"],
            "region_weeks_charged": len(entries),
            "region_weeks_left": rcp.weeks_left(workload.CURRENT, entries),
            "receipts_on_the_ledger": [
                {
                    "receipt_id": item["receipt_id"],
                    "region": item["region"],
                    "week": item["week"],
                    "holdback_share": item["holdback_share"],
                    "days_returned": item["days_returned"],
                    "refusal": item["refusal"],
                }
                for item in entries
            ],
            "receipts": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that working session ran it.'

    record = _record(record_path)
    entries, _error = live_receipts(Path(artifact_dir))
    network = live_network(entries)
    context = snapshot(network, record)
    ledger = [
        item for item in rcp.history(workload.CURRENT, workload.HISTORY_BOOKINGS)
        if str(item["week"]) <= str(record["as_of"])
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": ledger},
            {"kind": "plan", "context": context, "receipts": ledger},
        ]},
    )
    session = {
        "session": record.get("session"),
        "date": record.get("date"),
        "analyst": record.get("analyst"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("as_of"),
        "regions_walked": list(record.get("regions", ())),
        "receipts_charged_by_then": [
            {"receipt_id": item["receipt_id"], "region": item["region"],
             "week": item["week"], "refusal": item["refusal"]}
            for item in ledger
        ],
        "by_day": {
            region: _by_day(context, region) for region in record.get("regions", ())
        },
        "dispatch_incidents": [dict(row) for row in context["dispatch_incidents"]],
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name,
                             "network": context["network"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "network": context["network"],
            "as_of": context["as_of"],
            "board_bar_points": context["board_bar_points"],
            "region_weeks_charged": len(ledger),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_booking(
    artifact_dir: Path, region: Any, week: Any, holdback_share: Any
) -> Mapping[str, Any]:
    entries, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return rcp.collect(Path(artifact_dir), workload.CURRENT, region, week, holdback_share)


def starting_receipts() -> dict[str, Any]:
    'The receipts the campaign starts from: the two region-weeks already charged.'

    return publish.starting_receipts()
