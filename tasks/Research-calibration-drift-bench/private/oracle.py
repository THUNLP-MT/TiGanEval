"What the bench says, computed from the world's own parameters."

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import world as w


RATIO_TOLERANCE = 0.04

INVARIANCE_TOLERANCE = 0.05


FLOOR_SHARE = 0.6
CEILING_MULTIPLE = 3.0


def truth(campaign: w.Campaign) -> float:
    'The wear-rate ratio the two suppliers actually have.'

    return float(campaign.spec["ratio"])


def _rows(campaign: w.Campaign) -> list[dict[str, Any]]:
    return [dict(entry) for entry in campaign.runs if entry["kind"] == w.PART_RUN]


def _log_depth(row: Mapping[str, Any]) -> float:
    return math.log(float(row["reading"]))


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return float(sum(items) / len(items)) if items else float("nan")


def gain_fit(campaign: w.Campaign) -> dict[int, tuple[float, float]]:
    "Intercept and slope of the reference block's readings against bench-hours."

    fits: dict[int, tuple[float, float]] = {}
    for rig in w.RIGS:
        hours, readings = [], []
        for entry in campaign.runs:
            if int(entry["rig"]) != rig or entry["reference_um"] is None:
                continue
            hours.append(float(entry["hours_since_calibration"]))
            readings.append(float(entry["reference_um"]))
        design = np.column_stack([np.ones(len(hours)), np.asarray(hours)])
        solved, *_ = np.linalg.lstsq(design, np.asarray(readings), rcond=None)
        fits[rig] = (float(solved[0]), float(solved[1]))
    return fits


def _corrected(campaign: w.Campaign, rows: Sequence[Mapping[str, Any]]) -> list[float]:
    "Each reading referred to its own rig's fresh calibration."

    fits = gain_fit(campaign)
    values = []
    for row in rows:
        intercept, slope = fits[int(row["rig"])]
        gain = (intercept + slope * float(row["hours_since_calibration"])) / intercept
        values.append(_log_depth(row) - math.log(gain))
    return values


def _lot_rig_means(
    rows: Sequence[Mapping[str, Any]], values: Sequence[float]
) -> dict[tuple[str, int], float]:
    grouped: dict[tuple[str, int], list[float]] = {}
    for row, value in zip(rows, values):
        grouped.setdefault((str(row["lot"]), int(row["rig"])), []).append(value)
    return {key: _mean(items) for key, items in grouped.items()}


def fixture_ratio(campaign: w.Campaign) -> float:
    'What rig 2 reads for the same part, from the lots that ran on both rigs.'

    rows = _rows(campaign)
    values = _corrected(campaign, rows)
    means = _lot_rig_means(rows, values)
    gaps = [
        means[(lot, 2)] - means[(lot, 1)]
        for lot in {str(row["lot"]) for row in rows}
        if (lot, 1) in means and (lot, 2) in means
    ]
    return float(math.exp(_mean(gaps)))


def _lot_means(campaign: w.Campaign, rows: Sequence[Mapping[str, Any]],
               values: Sequence[float], fixture: float) -> dict[str, float]:
    'One number per lot: its parts on one scale, averaged.'

    adjusted = [
        value - (math.log(fixture) if int(row["rig"]) == 2 else 0.0)
        for row, value in zip(rows, values)
    ]
    grouped: dict[str, list[float]] = {}
    for row, value in zip(rows, adjusted):
        grouped.setdefault(str(row["lot"]), []).append(value)
    return {lot: _mean(items) for lot, items in grouped.items()}


def _supplier_lots(campaign: w.Campaign) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"A": [], "B": []}
    for lot in campaign.lots:
        result[str(lot["supplier"])].append(str(lot["lot"]))
    return result


def bench_ratio(campaign: w.Campaign) -> float:
    'The ratio the published table gives once both mechanisms are removed.'

    rows = _rows(campaign)
    values = _corrected(campaign, rows)
    means = _lot_means(campaign, rows, values, fixture_ratio(campaign))
    by_supplier = _supplier_lots(campaign)
    return float(math.exp(
        _mean(means[lot] for lot in by_supplier["B"])
        - _mean(means[lot] for lot in by_supplier["A"])
    ))


def raw_ratio(campaign: w.Campaign) -> float:
    'Depth averaged by supplier, with nothing taken off it.'

    rows = _rows(campaign)
    by_supplier: dict[str, list[float]] = {"A": [], "B": []}
    for row in rows:
        by_supplier[str(row["supplier"])].append(float(row["reading"]))
    return float(_mean(by_supplier["B"]) / _mean(by_supplier["A"]))


def drift_only_ratio(campaign: w.Campaign) -> float:
    'Every reading referred to its own calibration, and nothing else.'

    rows = _rows(campaign)
    values = _corrected(campaign, rows)
    means = _lot_means(campaign, rows, values, 1.0)
    by_supplier = _supplier_lots(campaign)
    return float(math.exp(
        _mean(means[lot] for lot in by_supplier["B"])
        - _mean(means[lot] for lot in by_supplier["A"])
    ))


def no_gain_ratio(campaign: w.Campaign) -> float:
    'The two rigs told apart, and every reading left on the scale it came off.'

    rows = _rows(campaign)
    values = [_log_depth(row) for row in rows]
    means = _lot_rig_means(rows, values)
    gaps = [
        means[(lot, 2)] - means[(lot, 1)]
        for lot in {str(row["lot"]) for row in rows}
        if (lot, 1) in means and (lot, 2) in means
    ]
    fixture = math.exp(_mean(gaps))
    lot_means = _lot_means(campaign, rows, values, fixture)
    by_supplier = _supplier_lots(campaign)
    return float(math.exp(
        _mean(lot_means[lot] for lot in by_supplier["B"])
        - _mean(lot_means[lot] for lot in by_supplier["A"])
    ))


def zero_offset_ratio(campaign: w.Campaign) -> float:
    "The block's walk taken off as microns rather than as a share of the reading."

    rows = _rows(campaign)
    fits = gain_fit(campaign)
    values = []
    for row in rows:
        _intercept, slope = fits[int(row["rig"])]
        shifted = float(row["reading"]) - slope * float(row["hours_since_calibration"])
        values.append(math.log(max(1e-6, shifted)))
    means = _lot_rig_means(rows, values)
    gaps = [
        means[(lot, 2)] - means[(lot, 1)]
        for lot in {str(row["lot"]) for row in rows}
        if (lot, 1) in means and (lot, 2) in means
    ]
    fixture = math.exp(_mean(gaps))
    lot_means = _lot_means(campaign, rows, values, fixture)
    by_supplier = _supplier_lots(campaign)
    return float(math.exp(
        _mean(lot_means[lot] for lot in by_supplier["B"])
        - _mean(lot_means[lot] for lot in by_supplier["A"])
    ))


def rig_constant_ratio(campaign: w.Campaign) -> float:
    'One constant per rig fitted beside the suppliers, and no calibration term.'

    rows = _rows(campaign)
    lots = sorted({str(row["lot"]) for row in rows})
    design = np.zeros((len(rows), 3 + len(lots)))
    response = np.zeros(len(rows))
    for index, row in enumerate(rows):
        design[index, 0] = 1.0
        design[index, 1] = 1.0 if str(row["supplier"]) == "B" else 0.0
        design[index, 2] = 1.0 if int(row["rig"]) == 2 else 0.0
        response[index] = _log_depth(row)


    for offset, lot in enumerate(lots):
        for index, row in enumerate(rows):
            if str(row["lot"]) == lot:
                design[index, 3 + offset] = 1.0
    keep = [0, 1, 2] + [3 + offset for offset, lot in enumerate(lots)
                        if lot not in (_supplier_lots(campaign)["A"][0],
                                       _supplier_lots(campaign)["B"][0])]
    solved, *_ = np.linalg.lstsq(design[:, keep], response, rcond=None)
    return float(math.exp(solved[1]))


def decoy_ratios(campaign: w.Campaign) -> dict[str, float]:
    return {
        "raw": raw_ratio(campaign),
        "drift_only": drift_only_ratio(campaign),
        "no_gain": no_gain_ratio(campaign),
        "rig_constant": rig_constant_ratio(campaign),
        "zero_offset": zero_offset_ratio(campaign),
    }


def _variance_components(campaign: w.Campaign) -> tuple[float, float]:
    lot_var = float(campaign.spec["lot_sd"]) ** 2
    unit_var = (
        float(campaign.spec["part_sd"]) ** 2
        + (float(campaign.spec["noise_sd"]) / float(campaign.spec["mu_a"])) ** 2
    )
    return lot_var, unit_var


def _cell_counts(cells: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, int], int]:
    counts: dict[tuple[str, str, int], int] = {}
    for cell in cells:
        key = (str(cell["lot"]), str(cell["supplier"]), int(cell["rig"]))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _errors(campaign: w.Campaign, cells: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    'Standard errors of the supplier contrast and of the fixture ratio.'

    counts = _cell_counts(cells)
    if not counts:
        return float("inf"), float("inf")
    keys = sorted(counts)
    lots = sorted({key[0] for key in keys})
    index = {lot: offset for offset, lot in enumerate(lots)}
    lot_var, unit_var = _variance_components(campaign)
    size = len(keys)
    design = np.zeros((size, 3))
    membership = np.zeros((size, len(lots)))
    diagonal = np.zeros(size)
    for row, key in enumerate(keys):
        lot, supplier, rig = key
        design[row, 0] = 1.0
        design[row, 1] = 1.0 if supplier == "B" else 0.0
        design[row, 2] = 1.0 if rig == 2 else 0.0
        membership[row, index[lot]] = 1.0
        diagonal[row] = unit_var / counts[key]
    covariance = lot_var * membership @ membership.T + np.diag(diagonal)
    information = design.T @ np.linalg.solve(covariance, design)
    try:
        spread = np.linalg.inv(information)
    except np.linalg.LinAlgError:
        return float("inf"), float("inf")
    if spread[1, 1] <= 0 or spread[2, 2] <= 0:
        return float("inf"), float("inf")
    return float(math.sqrt(spread[1, 1])), float(math.sqrt(spread[2, 2]))


def campaign_cells(campaign: w.Campaign) -> list[dict[str, Any]]:
    return [
        {"lot": str(row["lot"]), "supplier": str(row["supplier"]), "rig": int(row["rig"])}
        for row in _rows(campaign)
    ]


def contrast_standard_error(
    campaign: w.Campaign, extra: Sequence[Mapping[str, Any]] = ()
) -> float:
    return _errors(campaign, campaign_cells(campaign) + list(extra))[0]


def fixture_standard_error(
    campaign: w.Campaign, extra: Sequence[Mapping[str, Any]] = ()
) -> float:
    return _errors(campaign, campaign_cells(campaign) + list(extra))[1]


def interval_floor(campaign: w.Campaign) -> float:
    'The width, in log wear rate, that the lots on the bench support.'

    return float(2.0 * 1.96 * contrast_standard_error(campaign))


def supported_range(campaign: w.Campaign) -> tuple[float, float]:
    "A range of that width around the world's ratio, for the author's notes."

    half = interval_floor(campaign) / 2.0
    return (truth(campaign) * math.exp(-half), truth(campaign) * math.exp(half))


def planned_cells(campaign: w.Campaign, bookings: Sequence[Mapping[str, Any]]) -> list[dict]:
    cells = []
    for booking in bookings:
        part = booking.get("part")
        stored = campaign.store_part(str(part)) if part else None
        if stored is None:
            continue
        cells.append({
            "lot": str(stored["lot"]),
            "supplier": str(stored["supplier"]),
            "rig": int(booking["rig"]),
        })
    return cells


def receipt_cells(campaign: w.Campaign, receipts: Sequence[Mapping[str, Any]]) -> list[dict]:
    cells = []
    for entry in receipts:
        if entry.get("observed", {}).get("kind") != w.PART_RUN:
            continue
        cells.append({
            "lot": str(entry["lot"]),
            "supplier": str(entry["supplier"]),
            "rig": int(entry["rig"]),
        })
    return cells


def standing_fixture_error(
    campaign: w.Campaign, receipts: Sequence[Mapping[str, Any]]
) -> float:
    'How sharply the fixture ratio is known with what has been run so far.'

    return fixture_standard_error(campaign, receipt_cells(campaign, receipts))


def _remaining(campaign: w.Campaign, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    used = {str(entry["part"]) for entry in receipts if entry.get("part")}
    spent = w.hours_spent(receipts)
    return {
        "parts": [item for item in campaign.spec["stores"] if str(item["part"]) not in used],
        "hours": float(campaign.spec["bench_hours_left"]) - spent,
        "rig_hours": {
            rig: w.rig_hours_left(campaign, receipts, rig) for rig in w.RIGS
        },
    }


def best_fixture_error(
    campaign: w.Campaign, receipts: Sequence[Mapping[str, Any]]
) -> float:
    'The sharpest the fixture ratio can be made with the hours that are left.'

    state = _remaining(campaign, receipts)
    cells = receipt_cells(campaign, receipts)
    parts = {str(item["part"]): item for item in state["parts"]}
    hours = state["hours"]
    rig_hours = dict(state["rig_hours"])
    cost = campaign.hours_for(w.PART_RUN)
    best = fixture_standard_error(campaign, cells)
    while parts and hours >= cost:
        choice = None
        for part_id, item in parts.items():
            for rig in w.RIGS:
                if rig_hours[rig] < cost:
                    continue
                trial = cells + [{"lot": str(item["lot"]),
                                  "supplier": str(item["supplier"]), "rig": rig}]
                value = fixture_standard_error(campaign, trial)
                if choice is None or value < choice[0]:
                    choice = (value, part_id, rig)
        if choice is None or choice[0] >= best - 1e-9:
            break
        best, part_id, rig = choice
        item = parts.pop(part_id)
        cells.append({"lot": str(item["lot"]), "supplier": str(item["supplier"]), "rig": rig})
        hours -= cost
        rig_hours[rig] -= cost
    return float(best)


PLAN_SHORTFALL_SHARE = 0.25


def plan_bar(campaign: w.Campaign, receipts: Sequence[Mapping[str, Any]]) -> float:
    'How sharp the fixture ratio has to be once the booked sessions have run.'

    now = standing_fixture_error(campaign, receipts)
    best = best_fixture_error(campaign, receipts)
    return float(best + PLAN_SHORTFALL_SHARE * (now - best))


def plan_fixture_error(
    campaign: w.Campaign,
    receipts: Sequence[Mapping[str, Any]],
    bookings: Sequence[Mapping[str, Any]],
) -> float:
    'How sharply the fixture ratio would be known once the plan has run.'

    cells = receipt_cells(campaign, receipts) + planned_cells(campaign, bookings)
    return fixture_standard_error(campaign, cells)
