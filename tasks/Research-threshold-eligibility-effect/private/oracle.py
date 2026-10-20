"What a market says, computed from the market's own accounts and chances."

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Mapping, Sequence

from . import desk
from . import world as w


TOLERANCE = 1.5


CLASSIFY_SLACK = 0.35

INVARIANCE_SLACK = 0.7


CARRIED_OVER_GAP = 0.5


NARROW_FACTOR = 0.80
WIDE_FACTOR = 1.6

COVERAGE = 0.9


ACCOUNT_DAYS_RELATIVE_SLACK = 0.005

_NORMAL = NormalDist()


_MEMO: dict[tuple[str, str], Any] = {}


def _once(name: str, market: w.Market, make):
    key = (name, market.market)
    if key not in _MEMO:
        _MEMO[key] = make()
    return _MEMO[key]


def eligible(market: w.Market) -> list[Mapping[str, Any]]:
    "The rows the line decides: scored, near the line on the run's own score,     and not lifted over it by a credit."

    return _once("eligible", market, lambda: _eligible(market))


def _eligible(market: w.Market) -> list[Mapping[str, Any]]:
    band = float(market.spec["band_points"])
    return [
        row
        for row in market.rows
        if row["run_status"] == "scored"
        and abs(float(row["run_score"]) - market.cut) <= band
        and not row["credit_lifted"]
    ]


def truth(market: w.Market) -> float:
    'What the offer did, in points of sixty-day order rate, at the line.'

    return _once("truth", market, lambda: _truth(market))


def _truth(market: w.Market) -> float:
    window = int(market.spec["order_window_days"])
    sides: dict[int, list[float]] = {0: [0.0, 0.0], 1: [0.0, 0.0]}
    for row in eligible(market):
        hazard = 1.0 - (1.0 - float(row["true_chance"])) ** (1.0 / window)
        reach = 1.0 - (1.0 - hazard) ** window
        entry = sides[int(row["offer_flag"])]
        entry[0] += reach
        entry[1] += reach / hazard
    if not sides[0][1] or not sides[1][1]:
        return 0.0
    return 100.0 * (
        _rate(sides[1][0], sides[1][1], window) - _rate(sides[0][0], sides[0][1], window)
    )


def mean_chance_gap(market: w.Market) -> float:
    "The plain difference of the two sides' sixty-day chances."

    sides: dict[int, list[float]] = {0: [], 1: []}
    for row in eligible(market):
        sides[int(row["offer_flag"])].append(float(row["true_chance"]))
    if not sides[0] or not sides[1]:
        return 0.0
    return 100.0 * (
        sum(sides[1]) / len(sides[1]) - sum(sides[0]) / len(sides[0])
    )


def _counts(rows: Sequence[Mapping[str, Any]], side: str) -> dict[str, list[float]]:
    'Per side, the orders seen and the days the export watched for them.'

    tally = {"above": [0.0, 0.0], "below": [0.0, 0.0]}
    for row in rows:
        watched = int(row["watched_days"])
        if watched <= 0:
            continue
        offset = row["order_offset"]
        seen = offset is not None and int(offset) <= watched
        entry = tally[row[side]]
        entry[0] += 1.0 if seen else 0.0
        entry[1] += float(offset) if seen else float(watched)
    return tally


def _rate(events: float, days: float, window: int) -> float:
    if days <= 0:
        return 0.0
    return 1.0 - math.exp(-window * (events / days))


def _difference(tally: Mapping[str, Sequence[float]], window: int) -> float:
    above = _rate(tally["above"][0], tally["above"][1], window)
    below = _rate(tally["below"][0], tally["below"][1], window)
    return 100.0 * (above - below)


def _tagged(
    market: w.Market,
    rows: Sequence[Mapping[str, Any]],
    *,
    by_register: bool = False,
) -> list[dict[str, Any]]:
    'The rows with the side the reading puts them on.'

    cut = market.cut
    out = []
    for row in rows:
        score = float(row["register_score"] if by_register else row["run_score"])
        side = "above" if (score >= cut if by_register else int(row["offer_flag"])) else "below"
        out.append(dict(row, side=side))
    return out


def _select(
    market: w.Market,
    *,
    band: bool = True,
    scored_only: bool = True,
    drop_credited: bool = True,
    by_register: bool = False,
) -> list[dict[str, Any]]:
    cut = market.cut
    width = float(market.spec["band_points"])
    rows = []
    for row in market.rows:
        if scored_only and row["run_status"] != "scored":
            continue
        score = float(row["register_score"] if by_register else row["run_score"])
        if band and abs(score - cut) > width:
            continue
        credit = float(row["credit"])
        lifted = (
            (credit > 0 and score >= cut > score - credit)
            if by_register
            else bool(row["credit_lifted"])
        )
        if drop_credited and lifted:
            continue
        rows.append(row)
    return _tagged(market, rows, by_register=by_register)


def reading(market: w.Market) -> float:
    'What the register gives when it is read the way the market works.'

    return _once("reading", market, lambda: _difference(
        _counts(live_rows(market), "side"), int(market.spec["order_window_days"])
    ))


def live_rows(market: w.Market) -> list[dict[str, Any]]:
    'The rows the reading stands on, worked out once for this market.'

    return _once("live_rows", market, lambda: _select(market))


def _flag_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    'The share of a side that reached the export with an order on it.'

    tally = {"above": [0, 0], "below": [0, 0]}
    for row in rows:
        offset = row["order_offset"]
        watched = int(row["watched_days"])
        entry = tally[row["side"]]
        entry[0] += 1
        entry[1] += 1 if (offset is not None and int(offset) <= watched) else 0
    above = tally["above"][1] / tally["above"][0] if tally["above"][0] else 0.0
    below = tally["below"][1] / tally["below"][0] if tally["below"][0] else 0.0
    return 100.0 * (above - below)


def misreadings(market: w.Market) -> dict[str, float]:
    'The readings the wrong scope, the wrong side, the kept credits and the     counted flags produce on this market.'

    return _once("misreadings", market, lambda: _misreadings(market))


def _misreadings(market: w.Market) -> dict[str, float]:
    window = int(market.spec["order_window_days"])

    def days(**changes: Any) -> float:
        return _difference(_counts(_select(market, **changes), "side"), window)

    return {
        "whole_book_days": days(
            band=False, scored_only=False, drop_credited=False, by_register=True
        ),
        "whole_book_flags": _flag_rate(
            _select(market, band=False, scored_only=False, drop_credited=False, by_register=True)
        ),
        "no_band": days(band=False),
        "register_side": days(by_register=True),
        "credited_band_kept": days(drop_credited=False),
        "carried_included": days(scored_only=False),
        "order_flags": _flag_rate(_select(market)),
        "credited_band_dropped_flat": _difference(
            _counts(_flat_band(market), "side"), window
        ),
        "recompute_keyed": _difference(_counts(_recompute_keyed(market), "side"), window),
    }


def _flat_band(market: w.Market) -> list[dict[str, Any]]:
    'Every row inside the first point above the line dropped, credit or not.'

    cut = market.cut
    ceiling = max(1.0, float(market.spec["credit_ceiling"]))
    rows = [
        row
        for row in market.rows
        if row["run_status"] == "scored"
        and abs(float(row["run_score"]) - cut) <= float(market.spec["band_points"])
        and not (cut <= float(row["run_score"]) < cut + ceiling)
    ]
    return _tagged(market, rows)


def _recompute_keyed(market: w.Market) -> list[dict[str, Any]]:
    'The side taken from the pre-refresh score wherever the log carries one.'

    cut = market.cut
    width = float(market.spec["band_points"])
    before = {item["account_id"]: float(item["score_before"]) for item in market.refreshes}
    rows = []
    for row in market.rows:
        if row["run_status"] != "scored" or row["credit_lifted"]:
            continue
        score = before.get(row["account_id"], float(row["run_score"]))
        if abs(score - cut) > width:
            continue
        rows.append(dict(row, side="above" if score >= cut else "below"))
    return rows


def z_score(market: w.Market) -> float:
    'The multiplier a range needs to hold on every market the slide counts.'

    markets = max(1, int(market.spec["markets_on_the_slide"]))
    return _NORMAL.inv_cdf(1.0 - 0.05 / (2.0 * markets))


def _half_width_of(tally: Mapping[str, Sequence[float]], market: w.Market) -> float:
    window = int(market.spec["order_window_days"])
    variance = 0.0
    for side in ("above", "below"):
        events, days = tally[side][0], tally[side][1]
        if events <= 0 or days <= 0:
            return float("inf")
        hazard = events / days
        variance += ((1.0 - _rate(events, days, window)) * window * hazard) ** 2 / events
    return z_score(market) * math.sqrt(variance) * 100.0


def observed_rows(
    market: w.Market, receipts: Sequence[Mapping[str, Any]] = ()
) -> list[dict[str, Any]]:
    "The reading's rows with each reviewed file watched through its receipt."

    reviewed = {
        str(row["account_id"]): int(row.get("days_watched", 0))
        for entry in receipts
        for row in entry.get("files", ())
    }
    if not reviewed:
        return live_rows(market)
    return [
        dict(row, watched_days=max(int(row["watched_days"]), reviewed[str(row["account_id"])]))
        if str(row["account_id"]) in reviewed
        else dict(row)
        for row in live_rows(market)
    ]


def account_days(
    market: w.Market, receipts: Sequence[Mapping[str, Any]] = ()
) -> float:
    tally = _counts(observed_rows(market, receipts), "side")
    return tally["above"][1] + tally["below"][1]


def half_width(
    market: w.Market, receipts: Sequence[Mapping[str, Any]] = ()
) -> float:
    'The range the near-cut rows and any reviewed files support, in points.'

    if receipts:
        return _half_width_of(
            _counts(observed_rows(market, receipts), "side"), market
        )
    return _once(
        "half_width", market, lambda: _half_width_of(_counts(live_rows(market), "side"), market)
    )


def half_width_for_days(
    market: w.Market,
    reported_days: float,
    receipts: Sequence[Mapping[str, Any]] = (),
) -> float:
    'The range a readout standing on `reported_days` account-days supports.'

    days = float(reported_days)
    reference = account_days(market, receipts)
    if days <= 0 or reference <= 0:
        return half_width(market, receipts)
    return half_width(market, receipts) * math.sqrt(reference / days)


def interval(market: w.Market) -> tuple[float, float]:
    value = reading(market)
    spread = half_width(market)
    return value - spread, value + spread


def files_left(market: w.Market, receipts: Sequence[Mapping[str, Any]]) -> int:
    return market.files_left(receipts)


def _lot_rows(
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    week: int,
    band: float,
    above_share: float,
    files: int,
) -> list[Mapping[str, Any]]:
    seen = sorted(
        {str(item["account_id"]) for entry in receipts for item in entry.get("files", ())}
    )
    return desk.lot_rows(
        market, int(week), float(band), float(above_share), int(files), seen
    )


def files_the_reading_uses(
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    week: int,
    band: float,
    above_share: float,
    files: int,
) -> int:
    'How many of the files this lot would return are rows the reading is made of.'

    rows = _lot_rows(market, receipts, week, band, above_share, files)
    width = float(market.spec["band_points"])
    cut = market.cut
    return sum(1 for row in rows if abs(float(row["run_score"]) - cut) <= width)


def files_outside_the_band(
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    week: int,
    band: float,
    above_share: float,
    files: int,
) -> int | None:
    'How many of the files this lot would return come from outside the band     the reading uses, or None when the lot would return no files at all.'

    rows = _lot_rows(market, receipts, week, band, above_share, files)
    if not rows:
        return None
    width = float(market.spec["band_points"])
    cut = market.cut
    return sum(1 for row in rows if abs(float(row["run_score"]) - cut) > width)


def observation_days_gained(
    market: w.Market,
    receipts: Sequence[Mapping[str, Any]],
    week: int,
    band: float,
    above_share: float,
    files: int,
) -> float:
    'The usable account-days a proposed lot adds to the current reading.'

    rows = _lot_rows(market, receipts, week, band, above_share, files)
    if not rows:
        return 0.0
    after = [*receipts, {"files": rows}]
    return max(0.0, account_days(market, after) - account_days(market, receipts))


def stop_only(
    market: w.Market, receipts: Sequence[Mapping[str, Any]], published_width: float | None
) -> dict[str, Any]:
    'Whether the campaign has anything left worth pulling, and why not.'

    left = files_left(market, receipts)
    smallest = int(market.spec["smallest_lot"])
    made = (
        published_width is not None
        and 2.0 * float(published_width) <= float(market.spec["range_bar_points"])
    )
    return {
        "files_left": left,
        "range_made": bool(made),
        "stop_only": bool(made or left < smallest),
    }


def lot_ok(
    market: w.Market, receipts: Sequence[Mapping[str, Any]], choice: Mapping[str, Any]
) -> str | None:
    'The first thing wrong with this lot, as the desk would find it.'

    spec = market.spec
    week, band = int(choice["week"]), float(choice["band"])
    share, files = float(choice["above_share"]), int(choice["files"])
    if not 1 <= week <= int(spec["run_weeks"]) or band <= 0:
        return "review_is_not_a_lot_or_a_stop"
    if files > int(spec["files_per_booking"]):
        return "review_over_cap"
    if not float(spec["above_share_low"]) <= share <= float(spec["above_share_high"]):
        return "review_one_side_of_the_cut"
    sides = desk.eligible_rows(market, week, band)
    if not sides["above"] or not sides["below"]:
        return "review_band_empty"
    if files > files_left(market, receipts):
        return "review_over_grant"
    if files < int(spec["smallest_lot"]):
        return "review_below_the_smallest_lot"
    outside = files_outside_the_band(market, receipts, week, band, share, files)
    if outside is None or outside > 0:
        return "review_outside_the_band"
    if observation_days_gained(market, receipts, week, band, share, files) <= 0:
        return "review_adds_no_observation"
    return None
