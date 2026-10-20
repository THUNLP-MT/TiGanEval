'What the world says, computed from the checkpoints rather than from a report.'

from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence

from . import world as w


POINT = 0.01


TOLERANCE = 0.4


DECOY = 0.15


MOVE = 0.05


NARROWEST = 0.60
WIDEST = 2.2

COVER = 2.0


RANKING_READS = 3


_REPORT_NOT_GIVEN = object()


def production_quality(campaign: w.Campaign) -> float:
    return float(campaign.spec["production"]["quality"])


def gain_points(campaign: w.Campaign, item: str, arrangement: str = "as run") -> float | None:
    'What this item is really worth against the released model, in points.'

    worth = campaign.quality(item, arrangement)
    if worth is None:
        return None
    return (worth - production_quality(campaign)) / POINT


def best_on_disk(campaign: w.Campaign, arrangement: str = "as run") -> str:
    return max(
        (item for item in campaign.checkpoint_ids() if campaign.on_disk(item)),
        key=lambda item: campaign.quality(item, arrangement) or 0.0,
    )


def table_peak(campaign: w.Campaign, arrangement: str = "as run") -> Mapping[str, Any]:
    rows = campaign.ledger_rows(arrangement)
    return max(rows, key=lambda row: float(row["val_score"]))


def peak_gain(campaign: w.Campaign, arrangement: str = "as run") -> float:
    "The number the table's best row gives against the stored release figure."

    row = table_peak(campaign, arrangement)
    return (float(row["val_score"]) - campaign.release_score()) / POINT


def served(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in entries
        if not entry.get("refusal") and str(entry.get("kind")) == "reads"
    ]


def reads_of(entry: Mapping[str, Any], item: str) -> list[float]:
    return [
        float(row["val_score"])
        for row in entry.get("rows", ())
        if str(row["item"]) == str(item)
    ]


def paired_jobs(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> list[Mapping[str, Any]]:
    'The jobs that put this item and the released model on one lot together.'

    return [
        entry
        for entry in served(entries)
        if reads_of(entry, item) and reads_of(entry, campaign.production_id)
    ]


def paired_reads(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> int:
    'How many slices carry both this item and the released model.'

    total = 0
    for entry in paired_jobs(campaign, entries, item):
        total += min(
            len(reads_of(entry, item)), len(reads_of(entry, campaign.production_id))
        )
    return total


def paired_gain(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float | None:
    "The gain the stream's paired jobs give for this item, in points."

    differences = []
    for entry in paired_jobs(campaign, entries, item):
        mine = reads_of(entry, item)
        theirs = reads_of(entry, campaign.production_id)
        width = min(len(mine), len(theirs))
        differences.extend(
            (mine[index] - theirs[index]) / POINT for index in range(width)
        )
    if not differences:
        return None
    return sum(differences) / len(differences)


def items_read(entries: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(row["item"]) for entry in served(entries) for row in entry.get("rows", ())}


def supported_half_width(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float:
    'Half the tightest honest range for the reads this stream holds, in points.'

    read_sd = float(campaign.spec["read_sd"])
    paired = paired_reads(campaign, entries, item)
    if paired:
        return COVER * read_sd * sqrt(2.0 / paired) / POINT
    slice_sd = float(campaign.spec["slice_sd"])
    lot_sd = float(campaign.spec["lot_sd"])
    held = max(
        1,
        sum(len(reads_of(entry, item)) for entry in served(entries)),
    )
    spread = sqrt(
        2.0 * lot_sd * lot_sd
        + slice_sd * slice_sd
        + read_sd * read_sd * (1.0 + 1.0 / held)
    )
    return COVER * spread / POINT


def narrowest_width(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float:
    return NARROWEST * 2.0 * supported_half_width(campaign, entries, item)


def widest_width(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float:
    return WIDEST * 2.0 * supported_half_width(campaign, entries, item)


def stored_figure_gain(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float | None:
    'Fresh reads of the item, taken against the number in the release note.'

    reads = [
        value for entry in served(entries) for value in reads_of(entry, item)
    ]
    if not reads:
        return None
    return (sum(reads) / len(reads) - campaign.release_score()) / POINT


def table_row_gain(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    item: str,
    arrangement: str = "as run",
) -> float | None:
    "The item's own row in the table, against a fresh read of the model."

    row = next(
        (
            entry
            for entry in campaign.ledger_rows(arrangement)
            if f"{entry['run_id']}@{entry['checkpoint_step']}" == str(item)
        ),
        None,
    )
    model = [
        value
        for entry in served(entries)
        for value in reads_of(entry, campaign.production_id)
    ]
    if row is None or not model:
        return None
    return (float(row["val_score"]) - sum(model) / len(model)) / POINT


def cross_lot_gain(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> float | None:
    'Fresh reads of both, averaged without keeping them on one lot.'

    mine = [value for entry in served(entries) for value in reads_of(entry, item)]
    theirs = [
        value
        for entry in served(entries)
        for value in reads_of(entry, campaign.production_id)
    ]
    if not mine or not theirs:
        return None
    return (sum(mine) / len(mine) - sum(theirs) / len(theirs)) / POINT


def shortlist(campaign: w.Campaign, arrangement: str = "as run", per_group: int = 2) -> list[str]:
    'The best on-disk checkpoints of each run group, by what the table says.'

    rows = [
        row
        for row in campaign.ledger_rows(arrangement)
        if campaign.on_disk(f"{row['run_id']}@{row['checkpoint_step']}")
    ]
    chosen: list[str] = []
    for group in sorted({int(entry["group"]) for entry in campaign.runs()}):
        members = {
            str(entry["run_id"])
            for entry in campaign.runs()
            if int(entry["group"]) == group
        }
        ranked = sorted(
            (row for row in rows if str(row["run_id"]) in members),
            key=lambda row: -float(row["val_score"]),
        )
        for row in ranked[:per_group]:
            chosen.append(f"{row['run_id']}@{row['checkpoint_step']}")
    return chosen


def usable(campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]) -> int:
    return w.usable_units(campaign, entries)


def cheapest_job(campaign: w.Campaign) -> int:
    'One checkpoint and the released model, read once each.'

    return 2 * int(campaign.spec["read_price"])


def best_supported_width(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> float:
    'The tightest range any item on this stream already stands behind.'

    widths = [
        2.0 * supported_half_width(campaign, entries, item)
        for item in items_read(entries)
        if item != campaign.production_id and paired_reads(campaign, entries, item)
    ]
    return min(widths) if widths else float("inf")


def stop_is_right(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    report: Any = _REPORT_NOT_GIVEN,
) -> bool:
    'The two stops the contract names, and no third one.'

    if usable(campaign, entries) < cheapest_job(campaign):
        return True
    measured = [
        item
        for item in sorted(items_read(entries))
        if item != campaign.production_id and paired_reads(campaign, entries, item)
    ]
    if not measured:
        return False
    if report is _REPORT_NOT_GIVEN:


        lot = pairing_lot(campaign, entries, settled_on(campaign, entries, measured))
        if lot is None or w.slices_used(entries, lot) < campaign.slices:
            return False
        width = best_supported_width(campaign, entries)
    else:
        if not isinstance(report, Mapping):
            return False
        item = report.get("shipped_checkpoint")
        published = report.get("gain_range")
        if (
            not isinstance(item, str)
            or not isinstance(published, list)
            or len(published) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in published
            )
        ):
            return False
        lot = pairing_lot(campaign, entries, item)
        if lot is None or w.slices_used(entries, lot) < campaign.slices:
            return False
        low, high = float(published[0]), float(published[1])
        if low > high:
            return False
        width = high - low
    return width <= float(campaign.spec["range_ask_points"]) + 1e-9


def plan_is_allowed(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    choice: Any,
    report: Any = _REPORT_NOT_GIVEN,
) -> str | None:
    'None when the job is one this release can act on now, else the incident.'

    if choice == "stop":
        return (
            None
            if stop_is_right(campaign, entries, report)
            else "stopped_with_units_still_granted"
        )
    if not isinstance(choice, Mapping):
        return "booking_is_not_a_job_or_a_stop"
    kind = str(choice.get("kind") or "reads")
    if kind == "train":
        return "booking_retrains_the_top_config"
    if kind != "reads":
        return "booking_is_not_a_job_or_a_stop"
    items = choice.get("items")
    repeats = choice.get("repeats")
    lot = choice.get("lot")
    if not isinstance(items, (list, tuple)) or not items:
        return "booking_is_not_a_job_or_a_stop"
    if any(not isinstance(item, str) or not item.strip() for item in items):
        return "booking_is_not_a_job_or_a_stop"
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats <= 0:
        return "booking_is_not_a_job_or_a_stop"
    if len(set(items)) != len(items):
        return "booking_is_not_a_job_or_a_stop"
    if not isinstance(lot, str) or lot not in campaign.lots():
        return "booking_lot_the_desk_cannot_score_on"
    if repeats > campaign.slices:
        return "booking_is_not_a_job_or_a_stop"
    if any(not campaign.on_disk(item) for item in items):
        return "booking_item_not_on_disk"
    if w.slices_used(entries, lot) + int(repeats) > campaign.slices:
        return "booking_asks_for_passes_the_lot_has_left"
    read_price = int(campaign.spec["read_price"])
    cost = read_price * len(items) * int(repeats)
    if cost > w.units_left(campaign, entries):
        return "booking_exceeds_remaining"
    if cost > usable(campaign, entries):
        return "booking_breaks_the_reserve"
    if cost > int(campaign.spec["job_cap"]):
        return "booking_over_the_job_cap"
    if campaign.production_id not in set(items):
        return "booking_leaves_the_model_out"
    if not [item for item in items if item != campaign.production_id]:
        return "booking_names_no_checkpoint"
    return None


def one_allowed_plan(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> Any:
    'A job this release can act on now, or a stop when nothing is left.'

    if stop_is_right(campaign, entries):
        return "stop"
    read_price = int(campaign.spec["read_price"])
    lot = quietest_lot(campaign, entries)
    already = [
        item
        for item in sorted(items_read(entries))
        if item != campaign.production_id and paired_reads(campaign, entries, item)
    ]
    if already:
        best = settled_on(campaign, entries, already)
        items = [best, campaign.production_id]
        first = False
        lot = pairing_lot(campaign, entries, best) or lot
    else:
        items = [*shortlist(campaign), campaign.production_id]
        first = True
    while items:
        room = min(
            campaign.slices - w.slices_used(entries, lot),
            usable(campaign, entries) // (read_price * len(items)),
            int(campaign.spec["job_cap"]) // (read_price * len(items)),
        )
        if first:
            room = min(room, RANKING_READS)
        if room >= 1:
            return {
                "kind": "reads",
                "lot": lot,
                "items": items,
                "repeats": int(room),
            }
        if len(items) <= 2:
            break
        items = [items[0], items[-1]]
    return "stop"


def settled_on(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    items: Sequence[str],
) -> str:
    'The row the campaign has settled on: the best of the best measured.'

    return max(
        sorted(items),
        key=lambda item: (
            paired_reads(campaign, entries, item),
            paired_gain(campaign, entries, item) or 0.0,
        ),
    )


def pairing_lot(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]], item: str
) -> str | None:
    'The lot this item and the released model already share reads on.'

    counted: dict[str, int] = {}
    for entry in paired_jobs(campaign, entries, item):
        lot = str(entry.get("lot"))
        counted[lot] = counted.get(lot, 0) + int(entry.get("repeats") or 0)
    if not counted:
        return None
    return max(sorted(counted), key=lambda lot: counted[lot])


def quietest_lot(campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]) -> str:
    'The open lot with the most slices the desk has not handed out yet.'

    return min(
        campaign.lots(),
        key=lambda lot: (w.slices_used(entries, lot), lot),
    )
