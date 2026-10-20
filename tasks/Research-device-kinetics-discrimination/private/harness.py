'Read one delivered soak notebook against the campaign it is a reading of.'

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import chamber, desk_review, oracle, public_view, workload
from . import world as w
from .review import (
    BUCKETS,
    CARRY_OVER,
    FAILURE_MODES,
    Review,
    check_figure,
    check_range,
    check_stability,
    explanation,
    number,
    range_of,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-device-kinetics-",
    timeout=90.0,
)
_CACHE = AnalysisCache()

CAMPAIGN = workload.CURRENT.campaign


_NAMING_ORDER: tuple[str, ...] = tuple(world.campaign for world in workload.SIBLINGS)


def _naming_rank(campaign: str) -> int:
    return _NAMING_ORDER.index(campaign) if campaign in _NAMING_ORDER else len(_NAMING_ORDER)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("campaign") == CAMPAIGN else 1,
    )


def _written_off_the_live_campaign(
    bucket: str, records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "One check's records, reported off the campaign Anders can open."

    rows = [dict(record) for record in records]
    if not rows:
        return rows
    here = [
        record
        for record in rows
        if str(record.get("kind")) == CANDIDATE_FAILURE or record.get("campaign") == CAMPAIGN
    ]
    if here:
        return here
    modes = CARRY_OVER.get(bucket)
    if not modes:
        return rows
    mode = modes[0]
    same = rows
    named = min(
        (record for record in same if record.get("campaign")),
        key=lambda record: _naming_rank(str(record["campaign"])),
        default=same[0],
    )
    elsewhere = sorted({str(record["campaign"]) for record in same if record.get("campaign")})
    carried = {
        "campaign": CAMPAIGN,
        "other_campaign": str(named.get("campaign")),
        "other_campaigns": len(elsewhere),
    }
    if "days_left" in named:
        carried["days_left"] = named["days_left"]
    return [_fail(mode, **carried)]


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The blocks this delivery has paid for, or why the stream will not read.'

    try:
        return chamber.read_receipts(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    world: w.World, stream: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Every booking state this campaign can be asked for a next block in.'

    states = [{"label": "as it stands", "receipts": [dict(item) for item in stream]}]
    if world.campaign != CAMPAIGN:
        return states


    states.append(
        {"label": "the laws parted", "receipts": oracle.walk_to_exhaustion(world, stream)}
    )


    states.append(
        {
            "label": "a sheet handed back",
            "receipts": chamber.extend(
                world,
                stream,
                [
                    {
                        "block_id": "state-refused",
                        "drive_a": 1.8,
                        "case_temp_c": 95.0,
                        "ports": 8,
                        "chamber_days": 4,
                        "lot": "L-22",
                    }
                ],
            ),
        }
    )


    states.append(
        {
            "label": "days on the field-side drive",
            "receipts": chamber.extend(
                world,
                stream,
                [
                    {
                        "block_id": "state-soaked",
                        "drive_a": 1.7,
                        "case_temp_c": 85.0,
                        "ports": 7,
                        "chamber_days": 3,
                        "lot": "L-19",
                    }
                ],
            ),
        }
    )


    least = int(world.spec["smallest_block_days"])
    cap = int(world.spec["days_per_block_cap"])
    thin: list[dict[str, Any]] = []
    index = 0
    while True:
        left = world.days_left(chamber.extend(world, stream, thin))
        if left < least:
            break
        index += 1
        thin.append(
            {
                "block_id": f"state-thin-{index:02d}",
                "drive_a": 1.4,
                "case_temp_c": 85.0,
                "ports": 1,
                "chamber_days": min(least + (left - 1) % least, cap, left),
                "lot": "L-22" if index % 2 else "L-19",
            }
        )
    states.append({"label": "one day left", "receipts": chamber.extend(world, stream, thin)})
    return states


def instances(stream: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The campaign on the desk, the ones the notebook is run over next, the redraws.'

    rows: list[dict[str, Any]] = [
        {
            "label": CAMPAIGN,
            "world": workload.CURRENT,
            "receipts": [dict(item) for item in stream],
            "redraw": False,
        }
    ]
    for world in workload.SIBLINGS:
        rows.append(
            {"label": world.campaign, "world": world,
             "receipts": chamber.opening_stream(world), "redraw": False}
        )


    booked = [
        {
            "block_id": str(entry["block_id"]),
            "drive_a": float(entry["drive_a"]),
            "case_temp_c": float(entry["case_temp_c"]),
            "ports": int(entry["ports_asked"]),
            "chamber_days": int(entry["chamber_days_asked"]),
            "lot": str(entry["lot"]),
        }
        for entry in list(stream)[len(workload.CURRENT.spec["opening_blocks"]):]
    ]
    for world in workload.PARTNERS:
        rows.append(
            {"label": world.campaign, "world": world,
             "receipts": chamber.extend(world, chamber.opening_stream(world), booked),
             "redraw": True}
        )
    for row in rows:
        row["plans"] = [] if row["redraw"] else plan_states(row["world"], row["receipts"])
    return rows


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
    return f"the soak notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every campaign and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        stream, stream_error = live_receipts(Path(artifact_dir))
        rows = instances(stream)
        contexts: list[dict[str, Any]] = []
        seen: dict[int, int] = {}

        def context_index(world: w.World) -> int:
            if id(world) not in seen:
                seen[id(world)] = len(contexts)
                contexts.append(world.context())
            return seen[id(world)]

        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[w.World, list[dict[str, Any]], int]] = []
        for row in rows:
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": context_index(row["world"]),
                 "receipts": row["receipts"]}
            )
            for state in row["plans"]:
                plans.append(
                    (row["world"], list(state["receipts"]), len(requests))
                )
                requests.append(
                    {"kind": "plan", "context": context_index(row["world"]),
                     "receipts": state["receipts"]}
                )
        run = PROJECT.invoke(
            Path(artifact_dir), {"contexts": contexts, "requests": requests}
        )
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"campaign": CAMPAIGN, "blocks_charged": len(stream)}
            return analysis

        results = list(run.get("results", ()))

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the campaigns"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        review = Review()
        readings: dict[str, float] = {}
        worlds: dict[str, w.World] = {}
        streams: dict[str, list[dict[str, Any]]] = {}
        for row, index in reports:
            value, _error = answer(index)
            read = number(dict(value or {}).get("hours_to_loss")) if value else None
            if read is not None:
                readings[row["world"].campaign] = read
                worlds[row["world"].campaign] = row["world"]
                streams[row["world"].campaign] = list(row["receipts"])
        mode = explanation(readings, worlds, streams)
        held: list[bool] = []
        reasoning: list[tuple[w.World, list[dict[str, Any]], dict[str, Any]]] = []
        stopped = False
        for row, index in reports:
            world = row["world"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.stopped(
                    ("hours_failures", "range_failures", "ledger_failures",
                     "stability_failures"),
                    error,
                )
                continue
            if row["redraw"]:
                continue
            report = dict(value or {})
            check_figure(review, world, row["receipts"], report, mode)
            held.append(check_range(review, world, row["receipts"], report))


            reasoning.append((world, list(row["receipts"]), report))
            desk_review.check_ledger(
                review, world, row["receipts"], report,
                stream_error if world.campaign == CAMPAIGN else None,
            )
        for world, receipts, report in reasoning:
            desk_review.check_standing_laws(review, world, receipts, report)
        for world, receipts, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                review.failures["plan_failures"].append(_fail(CANDIDATE_FAILURE, error=error))
                continue
            desk_review.check_plan(
                review,
                world,
                receipts,
                value,
            )


        required_coverage = int(oracle.COVERAGE * len(held))
        if held and sum(held) < required_coverage:
            for row, index in reports:
                value, error = answer(index)
                if error is not None or row["redraw"]:
                    continue
                bounds = range_of(dict(value or {}))
                truth = oracle.truth(row["world"])
                if bounds is not None and not (bounds[0] <= truth <= bounds[1]):
                    review.add(
                        "range_failures",
                        "range_misses_the_hours",
                        campaign=row["world"].campaign,
                        reported_range=f"{bounds[0]:.0f} to {bounds[1]:.0f} hours",
                        campaigns_reviewed=len(held),
                        campaigns_held=sum(held),
                    )
        check_stability(review, readings, CAMPAIGN)

        analysis: dict[str, Any] = {
            bucket: _written_off_the_live_campaign(bucket, sorted(records, key=_report_order))
            for bucket, records in review.failures.items()
        }
        analysis["case"] = {
            "campaign": CAMPAIGN,
            "blocks_charged": len(stream),
            "campaigns_reviewed": len(rows),
            "notebook_stopped": stopped,
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    return public_view.status(Path(artifact_dir), live_receipts)


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    return public_view.replay(Path(artifact_dir), Path(record_path), PROJECT, live_receipts)


def run_block(
    artifact_dir: Path,
    drive_a: Any,
    case_temp_c: Any,
    ports: Any,
    chamber_days: Any,
    lot: Any,
    block_id: Any,
) -> Mapping[str, Any]:
    return public_view.run_block(
        Path(artifact_dir), live_receipts, drive_a, case_temp_c, ports, chamber_days,
        lot, block_id,
    )


def starting_receipts() -> dict[str, Any]:
    'The receipt stream the review starts from: the sheet the desk handed back.'

    return {
        "campaign": workload.CURRENT.campaign,
        "entries": chamber.opening_stream(workload.CURRENT),
    }
