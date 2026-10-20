'Read one delivered readout against the campaign it is a readout about.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-checkpoint-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "shipped_gain_within_tolerance",
    "range_covers_and_meets_floor",
    "gain_invariant_to_lot_and_turn",
    "booking_reads_shortlist_on_one_lot",
    "report_reconciles_receipts",
)

BUCKETS: Mapping[str, str] = {
    "shipped_gain_within_tolerance": "gain_failures",
    "range_covers_and_meets_floor": "range_failures",
    "gain_invariant_to_lot_and_turn": "move_failures",
    "booking_reads_shortlist_on_one_lot": "plan_failures",
    "report_reconciles_receipts": "ledger_failures",
}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "shipped_gain_within_tolerance": (
        "report_names_no_shipped_checkpoint",
        "gain_uses_table_peak",
        "gain_uses_stored_release_score",
        "gain_ignores_lot_change",
        "shipped_checkpoint_never_measured",
        "shipped_gain_disagrees",
        "candidate_execution_failed",
    ),
    "range_covers_and_meets_floor": (
        "range_is_not_a_range",
        "range_misses_reported_gain",
        "promotion_range_reaches_zero",
        "range_exceeds_board_ask",
        "range_below_read_floor",
        "range_above_what_the_reads_leave",
        "range_undercovers",
        "candidate_execution_failed",
    ),
    "gain_invariant_to_lot_and_turn": (
        "gain_tracks_lot_amount",
        "hardcoded_run_exclusion",
        "candidate_execution_failed",
    ),
    "booking_reads_shortlist_on_one_lot": (
        "booking_is_not_a_job_or_a_stop",
        "booking_retrains_the_top_config",
        "booking_lot_the_desk_cannot_score_on",
        "booking_item_not_on_disk",
        "booking_asks_for_passes_the_lot_has_left",
        "booking_exceeds_remaining",
        "booking_breaks_the_reserve",
        "booking_over_the_job_cap",
        "booking_leaves_the_model_out",
        "booking_names_no_checkpoint",
        "stopped_with_units_still_granted",
        "candidate_execution_failed",
    ),
    "report_reconciles_receipts": (
        "receipts_unreadable",
        "jobs_are_not_a_list",
        "job_missing_from_the_report",
        "job_not_on_the_receipts",
        "job_counted_twice",
        "job_lot_disagrees_with_the_receipt",
        "reads_disagree_with_the_receipt",
        "job_units_disagree_with_the_receipt",
        "units_do_not_reconcile",
        "candidate_execution_failed",
    ),
}

CURRENT_CAMPAIGN = str(workload.CURRENT_SPEC["campaign"])


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float | None, slack: float) -> bool:
    read = _number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def _points(value: Any) -> str:
    read = _number(value)
    return _show(value) if read is None else format(read, ".2f")


def _score(value: Any) -> str:
    read = _number(value)
    return _show(value) if read is None else format(read, ".4f")


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
        return "nothing at all" if not value else f"a list of {len(value)} entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(campaign: w.Campaign) -> dict[str, str]:
    'The campaign a failure happened on, in the words the owner uses for it.'

    return {
        "campaign_id": campaign.campaign,
        "campaign": str(campaign.spec["owner_label"]),
    }


def _here(record: Mapping[str, Any]) -> bool:
    return (
        str(record.get("kind")) == CANDIDATE_FAILURE
        or record.get("campaign_id") == CURRENT_CAMPAIGN
    )


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign_id") == CURRENT_CAMPAIGN else 1,
    )


def reported(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The incidents a report is written from, the visible campaign first.'

    ordered = sorted(records, key=_report_order)
    here = [dict(record) for record in ordered if _here(record)]
    return here if here else [dict(record) for record in ordered]


def live_stream(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return w.read_receipts(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def paired_walk(
    campaign: w.Campaign,
    base: Sequence[Mapping[str, Any]],
    tags: tuple[str, str] = ("walk-1", "walk-2"),
) -> list[list[dict[str, Any]]]:
    'The two jobs a release runs, as the streams they leave behind.'

    price = int(campaign.spec["read_price"])
    cap = int(campaign.spec["job_cap"])
    steps: list[list[dict[str, Any]]] = []
    held = [dict(entry) for entry in base]

    lot = oracle.quietest_lot(campaign, held)
    items = [*oracle.shortlist(campaign), campaign.production_id]
    room = min(
        campaign.slices - w.slices_used(held, lot),
        oracle.usable(campaign, held) // (price * len(items)),
        cap // (price * len(items)),
        oracle.RANKING_READS,
    )
    if room >= 1:
        held = w.extend(campaign, held, tags[0], "reads", lot, items, int(room))
        steps.append([dict(entry) for entry in held])

    already = [
        item
        for item in sorted(oracle.items_read(held))
        if item != campaign.production_id and oracle.paired_reads(campaign, held, item)
    ]
    if already:
        best = oracle.settled_on(campaign, held, already)
        settled = oracle.pairing_lot(campaign, held, best) or lot
        pair = [best, campaign.production_id]
        room = min(
            campaign.slices - w.slices_used(held, settled),
            oracle.usable(campaign, held) // (price * len(pair)),
            cap // (price * len(pair)),
        )
        if room >= 1:
            held = w.extend(
                campaign, held, tags[1], "reads", settled, pair, int(room)
            )
            steps.append([dict(entry) for entry in held])
    return steps


def settled_stream(campaign: w.Campaign) -> list[dict[str, Any]]:
    'The jobs a campaign behind this one had already been charged for.'

    prefix = campaign.campaign.split("-")[0][:6]
    steps = paired_walk(campaign, [], tags=(f"{prefix}-a", f"{prefix}-b"))
    return steps[-1] if steps else []


def plan_states(campaign: w.Campaign, base: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "Every state of this campaign's grant the desk can be asked for a job in."

    states = [{"label": "nothing collected", "stream": []}]
    held = [dict(entry) for entry in base]
    if held:
        states.append({"label": "as it stands", "stream": held})
    for index, step in enumerate(paired_walk(campaign, held), start=1):
        states.append({"label": f"after job {index}", "stream": step})


    burnt = [dict(entry) for entry in base]
    price = int(campaign.spec["read_price"])
    head = oracle.shortlist(campaign)[:1] or [oracle.best_on_disk(campaign)]
    for step in range(8):
        lot = oracle.quietest_lot(campaign, burnt)
        room = min(
            campaign.slices - w.slices_used(burnt, lot),
            oracle.usable(campaign, burnt) // (2 * price),
            int(campaign.spec["job_cap"]) // (2 * price),
        )
        if room < 1:
            break
        burnt = w.extend(
            campaign, burnt, f"spend-{step + 1}", "reads", lot,
            [head[0], campaign.production_id], int(room),
        )
    states.append({"label": "grant at the reserve", "stream": burnt})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The campaign on the desk with the jobs it holds, then the ones behind it.'

    rows = [
        {
            "campaign": workload.current(),
            "stream": [dict(entry) for entry in live],
            "plan_base": [dict(entry) for entry in live],
        }
    ]
    for campaign in (*workload.later(), workload.quiet()):
        rows.append(
            {
                "campaign": campaign,
                "stream": settled_stream(campaign),
                "plan_base": [],
            }
        )
    return rows


def _resolve(campaign: w.Campaign, report: Mapping[str, Any]) -> str | None:
    item = report.get("shipped_checkpoint")
    if not isinstance(item, str) or not item.strip():
        return None
    item = item.strip()
    if campaign.quality(item) is None or item == campaign.production_id:
        return None
    if not campaign.on_disk(item):
        return None
    return item


def _measured_items(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> list[str]:
    'The checkpoints this stream put on one lot with the released model.'

    return [
        item
        for item in sorted(oracle.items_read(entries))
        if item != campaign.production_id and oracle.paired_reads(campaign, entries, item)
    ]


def _gain_failures(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    where = _where(campaign)
    peak = oracle.table_peak(campaign)
    peak_item = f"{peak['run_id']}@{peak['checkpoint_step']}"
    shipped = _resolve(campaign, report)
    common = {
        **where,
        "reported": _points(report.get("gain_points")),
        "peak_row": peak_item,
        "peak_read": _score(peak["val_score"]),
        "stored_score": _score(campaign.release_score()),
    }
    if shipped is None:
        return [
            _fail(
                "report_names_no_shipped_checkpoint",
                **common,
                named=_show(report.get("shipped_checkpoint")),
            )
        ]
    truth = oracle.gain_points(campaign, shipped)
    common["shipped"] = shipped
    common["paired_reads"] = oracle.paired_reads(campaign, entries, shipped)
    if _near(report.get("gain_points"), truth, oracle.TOLERANCE):


        measured = _measured_items(campaign, entries)
        if measured and shipped not in measured:
            return [
                _fail(
                    "shipped_checkpoint_never_measured",
                    **common,
                    measured_items=len(measured),
                )
            ]
        return []
    if _near(report.get("gain_points"), oracle.peak_gain(campaign), oracle.DECOY):
        return [_fail("gain_uses_table_peak", **common)]
    if _near(
        report.get("gain_points"),
        oracle.stored_figure_gain(campaign, entries, shipped),
        oracle.DECOY,
    ):
        return [_fail("gain_uses_stored_release_score", **common)]
    for reading in (
        oracle.table_row_gain(campaign, entries, shipped),
        oracle.cross_lot_gain(campaign, entries, shipped),
    ):
        if _near(report.get("gain_points"), reading, oracle.DECOY):
            return [_fail("gain_ignores_lot_change", **common)]
    return [_fail("shipped_gain_disagrees", **common)]


def _best_measured(
    campaign: w.Campaign, entries: Sequence[Mapping[str, Any]]
) -> str:
    'The row the stream itself settled on, for a readout that names none.'

    measured = _measured_items(campaign, entries)
    if measured:
        return oracle.settled_on(campaign, entries, measured)
    return oracle.best_on_disk(campaign)


def _range_shape(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    'Everything about a published range except whether it holds the truth.'

    published = report.get("gain_range")
    shipped = _resolve(campaign, report)
    item = shipped or _best_measured(campaign, entries)
    common = {
        **_where(campaign),
        "reported_range": _pair(published),
        "paired_reads": oracle.paired_reads(campaign, entries, item),
        "reported_gain": _points(report.get("gain_points")),
        "board_ask": _points(campaign.spec["range_ask_points"]),
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
    ):
        return [_fail("range_is_not_a_range", **common, reported=_show(published))]
    low = float(published[0])
    high = float(published[1])
    gain = _number(report.get("gain_points"))
    width = high - low
    floor = oracle.narrowest_width(campaign, entries, item)
    ceiling = oracle.widest_width(campaign, entries, item)
    common["reported_width"] = _points(width)
    common["lower_end"] = _points(low)
    if gain is not None and not low <= gain <= high:
        return [_fail("range_misses_reported_gain", **common)]
    if low <= 0.0:
        return [_fail("promotion_range_reaches_zero", **common)]
    if width > float(campaign.spec["range_ask_points"]) + 1e-9:
        return [_fail("range_exceeds_board_ask", **common)]
    if width < floor:
        return [_fail("range_below_read_floor", **common)]
    if width > ceiling:
        return [_fail("range_above_what_the_reads_leave", **common)]
    return []


def _range_covers(campaign: w.Campaign, report: Mapping[str, Any]) -> bool:
    published = report.get("gain_range")
    shipped = _resolve(campaign, report)
    if shipped is None:
        return True
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
    ):
        return False
    truth = oracle.gain_points(campaign, shipped) or 0.0
    return float(published[0]) <= truth <= float(published[1])


def _move_failures(
    campaign: w.Campaign, reports: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "How far the delivery's own error moves when one thing is redrawn."

    def error(arrangement: str) -> float | None:
        report = reports.get(arrangement)
        if not report:
            return None
        item = _resolve(campaign, report)
        value = _number(report.get("gain_points"))
        if item is None or value is None:
            return None
        truth = oracle.gain_points(campaign, item, arrangement)
        return None if truth is None else value - truth

    here = error("as run")
    if here is None:
        return []
    found: list[dict[str, Any]] = []
    for arrangement, mode in (
        ("assignment", "gain_tracks_lot_amount"),
        ("turn", "hardcoded_run_exclusion"),
    ):
        other = error(arrangement)
        if other is None or abs(other - here) <= oracle.MOVE:
            continue
        found.append(
            _fail(
                mode,
                **_where(campaign),
                arrangement_note=w.arrangement_note(arrangement),
                reported=_points(reports["as run"].get("gain_points")),
                other_reported=_points(reports[arrangement].get("gain_points")),
                moved_by=_points(abs(other - here)),
            )
        )
    return found


def _plan_failures(
    campaign: w.Campaign,
    state: Mapping[str, Any],
    answer: Any,
    stop_report: Any = None,
    stop_report_error: str | None = None,
) -> list[dict[str, Any]]:
    entries = state["stream"]
    price = int(campaign.spec["read_price"])
    common = {
        **_where(campaign),
        "units_left": w.units_left(campaign, entries),
        "units_free": oracle.usable(campaign, entries),
        "reserved": int(campaign.spec["reserve"]),
        "job_cap": int(campaign.spec["job_cap"]),
        "price_per_read": price,
    }
    choices = list(answer) if isinstance(answer, list) else [answer]
    if not choices:
        return [
            _fail("booking_is_not_a_job_or_a_stop", **common, reported=_show(answer),
                  lot_asked="none", item_asked="none", passes_asked=0,
                  passes_left=campaign.slices)
        ]
    found: list[dict[str, Any]] = []
    for choice in choices:
        if choice == "stop" and stop_report_error is not None:


            problem = (
                None
                if oracle.usable(campaign, entries) < oracle.cheapest_job(campaign)
                else CANDIDATE_FAILURE
            )
        else:
            problem = oracle.plan_is_allowed(campaign, entries, choice, stop_report)
        if problem is None:


            return []
        asked = choice if isinstance(choice, Mapping) else {}
        items = asked.get("items") if isinstance(asked.get("items"), list) else []
        off_disk = [
            str(item) for item in items if not campaign.on_disk(str(item))
        ]
        wanted = asked.get("repeats") if isinstance(asked, Mapping) else None
        passes_asked = (
            int(wanted) if isinstance(wanted, int) and not isinstance(wanted, bool) else 0
        )
        lot_asked = str(asked.get("lot")) if isinstance(asked, Mapping) else ""
        passes_left = campaign.slices - w.slices_used(entries, lot_asked)
        if isinstance(asked, Mapping) and str(asked.get("kind")) == "train":
            shown = f"{_show(asked.get('runs'))} more training runs of {_show(asked.get('config'))}"
        elif items:
            shown = (
                f"{len(items)} items at {_show(asked.get('repeats'))} reads each on "
                f"{_show(asked.get('lot'))}"
            )
        else:
            shown = _show(choice)
        detail = _fail(
            problem,
            **common,
            reported=shown,
            lot_asked=_show(asked.get("lot")) if isinstance(asked, Mapping) else "none",
            item_asked=off_disk[0] if off_disk else (str(items[0]) if items else "none"),
            passes_asked=passes_asked,
            passes_left=passes_left,
            cost=price * len(items) * (passes_asked or 1) if items else 0,
        )
        if problem == CANDIDATE_FAILURE:
            detail["error"] = str(stop_report_error)
        found.append(detail)
    return found


def _ledger_failures(
    campaign: w.Campaign,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    stream_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(campaign)
    if stream_error:
        return [_fail("receipts_unreadable", **where, reason=str(stream_error))]
    lines = report.get("jobs")
    billed = {str(entry["job_id"]): entry for entry in entries}
    common = {**where, "jobs_on_the_stream": len(entries)}
    if not isinstance(lines, list):
        return [_fail("jobs_are_not_a_list", **common, reported=_show(lines))]
    invalid_lines = [line for line in lines if not isinstance(line, Mapping)]
    if invalid_lines:
        invalid = invalid_lines[0]
        return [_fail("jobs_are_not_a_list", **common, reported=_show(invalid))]
    typed_lines = [line for line in lines if isinstance(line, Mapping)]
    keys = [str(line.get("job_id")) for line in typed_lines]
    missing = next((key for key in billed if key not in set(keys)), None)
    if missing is not None:
        return [_fail("job_missing_from_the_report", **common, job_id=missing)]
    extra = next((key for key in keys if key not in billed), None)
    if extra is not None:
        return [_fail("job_not_on_the_receipts", **common, job_id=extra)]
    seen: dict[str, int] = {}
    for key in keys:
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [
                _fail(
                    "job_counted_twice",
                    **common,
                    job_id=key,
                    times_reported=seen[key],
                )
            ]
    for line in typed_lines:
        key = str(line.get("job_id"))
        entry = billed[key]
        reported_lot = line.get("lot")
        receipt_lot = entry.get("lot")
        if reported_lot != receipt_lot:
            return [
                _fail(
                    "job_lot_disagrees_with_the_receipt",
                    **common,
                    job_id=key,
                    reported_lot=_show(reported_lot),
                    receipt_lot=_show(receipt_lot),
                )
            ]
        reads = _number(line.get("reads"))
        if (
            reads is None
            or not reads.is_integer()
            or int(reads) != int(entry["reads_returned"])
        ):
            return [
                _fail(
                    "reads_disagree_with_the_receipt",
                    **common,
                    job_id=key,
                    reported_reads=_show(line.get("reads")),
                    receipt_reads=int(entry["reads_returned"]),
                )
            ]
        units = _number(line.get("units_charged"))
        if (
            units is None
            or not units.is_integer()
            or int(units) != int(entry["units_charged"])
        ):
            return [
                _fail(
                    "job_units_disagree_with_the_receipt",
                    **common,
                    job_id=key,
                    reported_units=_show(line.get("units_charged")),
                    receipt_units=int(entry["units_charged"]),
                )
            ]
    left = int(campaign.spec["units_granted"]) - w.units_spent(entries)
    reported_left = _number(report.get("units_left"))
    if (
        reported_left is None
        or not reported_left.is_integer()
        or int(reported_left) != left
    ):
        return [
            _fail(
                "units_do_not_reconcile",
                **common,
                reported_units=_show(report.get("units_left")),
                stream_units=left,
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
    text = str(run.get("error") or "no output").strip()
    line = text
    if text.startswith(_TIMEOUT_PHRASE):
        line = (
            "it was still running after "
            f"{text[len(_TIMEOUT_PHRASE):].strip()} and the console stopped it"
        )
    elif any(text.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(run.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the notebook ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the notebook ended without saying why"
    return f"the readout notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every campaign and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, stream_error = live_stream(Path(artifact_dir))
        rows = cases(entries)
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], dict[str, int]]] = []
        plans: list[tuple[w.Campaign, dict[str, Any], int]] = []
        for row in rows:
            campaign = row["campaign"]
            index: dict[str, int] = {}
            for arrangement in w.ARRANGEMENTS:
                stream = (
                    row["stream"]
                    if arrangement == "as run"
                    else w.replay_stream(campaign, row["stream"], arrangement)
                )
                index[arrangement] = len(requests)
                requests.append(
                    {
                        "kind": "report",
                        "context": campaign.context(arrangement),
                        "ledger": stream,
                    }
                )
            reports.append((row, index))
            for state in plan_states(campaign, row["plan_base"]):
                plans.append((campaign, state, len(requests)))
                requests.append(
                    {
                        "kind": "plan_review",
                        "context": campaign.context(),
                        "ledger": state["stream"],
                        "stop_report_required": (
                            oracle.usable(campaign, state["stream"])
                            >= oracle.cheapest_job(campaign)
                        ),
                    }
                )
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CURRENT_CAMPAIGN, "jobs_charged": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(position: int) -> tuple[Any, str | None]:
            if position >= len(results):
                return None, "the notebook returned no answer for one of the campaigns"
            item = dict(results[position])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        uncovered: list[dict[str, Any]] = []
        for row, index in reports:
            campaign, stream = row["campaign"], row["stream"]
            held: dict[str, Mapping[str, Any]] = {}
            broke: str | None = None
            for arrangement in w.ARRANGEMENTS:
                value, error = answer(index[arrangement])
                if error is not None:
                    broke = broke or error
                    continue
                held[arrangement] = dict(value or {})
            if broke is not None:
                stopped = True
                for bucket in BUCKETS.values():
                    if bucket != "plan_failures":
                        failures[bucket].append(_fail(CANDIDATE_FAILURE, error=broke))
                continue
            report = held["as run"]
            failures["gain_failures"].extend(_gain_failures(campaign, stream, report))
            shape = _range_shape(campaign, stream, report)
            failures["range_failures"].extend(shape)
            if not shape and not _range_covers(campaign, report):
                uncovered.append(
                    _fail(
                        "range_undercovers",
                        **_where(campaign),
                        reported_range=_pair(report.get("gain_range")),
                        reported_width=_points(
                            float(report["gain_range"][1]) - float(report["gain_range"][0])
                        ),
                        paired_reads=oracle.paired_reads(
                            campaign, stream, _resolve(campaign, report) or ""
                        ),
                    )
                )
            failures["move_failures"].extend(_move_failures(campaign, held))
            failures["ledger_failures"].extend(
                _ledger_failures(
                    campaign,
                    stream,
                    report,
                    stream_error if campaign.campaign == CURRENT_CAMPAIGN else None,
                )
            )


        here = [
            item for item in uncovered if item["campaign_id"] == CURRENT_CAMPAIGN
        ]
        if here or len(uncovered) > 1:
            failures["range_failures"].extend(uncovered)

        for campaign, state, position in plans:
            value, error = answer(position)
            if error is not None:
                stopped = True
                failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            payload = dict(value) if isinstance(value, Mapping) else {}
            failures["plan_failures"].extend(
                _plan_failures(
                    campaign,
                    state,
                    payload.get("choice"),
                    payload.get("stop_report"),
                    str(payload["stop_report_error"])
                    if payload.get("stop_report_error") is not None
                    else None,
                )
            )

        analysis: dict[str, Any] = {
            bucket: reported(records) for bucket, records in failures.items()
        }
        analysis["case"] = {
            "campaign": CURRENT_CAMPAIGN,
            "jobs_charged": len(entries),
            "campaigns_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "job_id", "kind", "lot", "items", "repeats", "reads_returned",
            "units_charged", "units_left_after", "refusal",
        )
    }


def snapshot(campaign: w.Campaign, record: Mapping[str, Any]) -> dict[str, Any]:
    'The evidence as it stood at the end of one past working session.'

    context = campaign.context()
    finished = [str(run_id) for run_id in record["runs_finished"]]
    context["as_of"] = str(record["date"])
    context["run_ledger"] = [
        row for row in context["run_ledger"] if str(row["run_id"]) in finished
    ]
    context["checkpoint_registry"] = [
        row for row in context["checkpoint_registry"] if str(row["run_id"]) in finished
    ]
    context["curves"] = {
        run_id: rows for run_id, rows in context["curves"].items() if run_id in finished
    }
    return context


def _record_stream(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = workload.starting_stream()
    keep = {str(item) for item in record.get("jobs", ())}
    return [dict(entry) for entry in held if str(entry["job_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    campaign = workload.current()
    context = campaign.context()
    entries, error = live_stream(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author")},
                "runs_finished": list(raw.get("runs_finished", ())),
            }
        )
    return {
        "summary": (
            f"The {context['campaign']} campaign, the release it is measured against, "
            "the desk's terms and the working records on file."
        ),
        "measurements": {
            "campaign": context["campaign"],
            "label": context["label"],
            "as_of": context["as_of"],
            "release": context["release"],
            "lots": context["lots"],
            "compute": context["compute"],
            "review": context["review"],
            "runs": [
                {
                    "run_id": entry["run_id"],
                    "init_id": entry["init_id"],
                    "warmup": entry["warmup"],
                    "trainer_version": entry["trainer_version"],
                    "val_lot": campaign.lot_of(str(entry["run_id"])),
                    "checkpoints": len(campaign.steps()),
                }
                for entry in campaign.runs()
            ],
            "checkpoints_on_disk": sum(
                1 for row in context["checkpoint_registry"] if row["on_disk"] == "yes"
            ),
            "units_spent": w.units_spent(entries),
            "units_left": w.units_left(campaign, entries),
            "jobs_on_the_stream": [_receipt_summary(entry) for entry in entries],
            "receipt_stream": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    campaign = workload.current()
    context = snapshot(campaign, record)
    entries = _record_stream(record)
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "requests": [
                {"kind": "report", "context": context, "ledger": entries},
                {"kind": "plan", "context": context, "ledger": entries},
            ]
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "runs_finished": list(record.get("runs_finished", ())),
        "rows_in_the_table": len(context["run_ledger"]),
        "jobs_on_the_stream": [_receipt_summary(entry) for entry in entries],
        "units_spent": w.units_spent(entries),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "campaign": context["campaign"]},
            "public": {
                "session": session,
                "console_error": run.get("error"),
                "diagnostic": run.get("diagnostic"),
            },
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "campaign": context["campaign"],
            "as_of": context["as_of"],
            "units_spent": w.units_spent(entries),
        },
        "public": {
            "session": session,
            "readout_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_job(
    artifact_dir: Path,
    job_id: Any,
    kind: Any,
    lot: Any,
    items: Any,
    repeats: Any,
) -> Mapping[str, Any]:
    return w.collect(
        Path(artifact_dir), workload.current(), job_id, kind, lot, items, repeats
    )
