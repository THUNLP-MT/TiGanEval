'What `run_project` prints: the campaign as it stands, a past working session run against this notebook, and one batch put through the desk.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import desk, workload, world
from .harness import EDITABLE_FILES, PROJECT, live_receipts


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working record must contain a JSON object")
    return raw


def _receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: entry[key]
        for key in (
            "batch_id", "day", "channel", "period", "listings_requested",
            "listings_returned", "violating_returned", "credits_charged",
            "credits_remaining", "refusal",
        )
    }


def _day_index(queue: world.Queue, day: str) -> int:
    return max(0, min(len(queue.days) - 1, queue.days.index(str(day))))


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    queue = workload.current()
    context = queue.context()
    entries, error = live_receipts(root)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append(
            {
                "record": f"project_records/{path.name}",
                **{key: raw.get(key) for key in ("record_id", "date", "author", "through_day")},
            }
        )
    return {
        "summary": (
            f"The {context['queue']} review queue, the terms the audit runs under and "
            "the working records on file."
        ),
        "measurements": {
            "queue": context["queue"],
            "desk": context["desk"],
            "window": context["window"],
            "as_of": context["as_of"],
            "review": context["review"],
            "audit": context["audit"],
            "intake_log_file": context["intake_log_file"],
            "channel_traffic": context["channel_traffic"],
            "credits_charged": desk.credits_charged(entries),
            "credits_left": desk.credits_left(queue, entries),
            "batches_on_the_receipts": [_receipt_summary(entry) for entry in entries],
            "receipts": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    queue = workload.current()
    through = _day_index(queue, str(record["through_day"]))
    context = queue.context(through)
    keep = {str(item) for item in record.get("batches", ())}
    entries = [
        dict(entry)
        for entry in json.loads(json.dumps(_opening()))["batches"]
        if str(entry["batch_id"]) in keep
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {
            "states": [
                {
                    "context": context,
                    "log_csv": queue.log_csv(through),
                    "requests": [
                        {"kind": "report", "receipts": entries},
                        {"kind": "plan", "receipts": entries},
                    ],
                }
            ]
        },
    )
    session = {
        "record_id": record.get("record_id"),
        "date": record.get("date"),
        "author": record.get("author"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("through_day"),
        "channel_traffic": context["channel_traffic"],
        "batches_on_the_receipts": [_receipt_summary(entry) for entry in entries],
        "credits_charged": desk.credits_charged(entries),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "queue": context["queue"]},
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
            "queue": context["queue"],
            "window": context["window"],
            "credits_charged": desk.credits_charged(entries),
        },
        "public": {
            "session": session,
            "readout_returned": results[0] if results else None,
            "next_batch_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def _opening() -> Mapping[str, Any]:
    from .harness import opening_receipts

    return opening_receipts()


def run_batch(
    artifact_dir: Path,
    channel: Any,
    period: Any,
    listings: Any,
    batch_id: Any,
) -> Mapping[str, Any]:
    return desk.collect(
        Path(artifact_dir), workload.current(), channel, period, listings, batch_id
    )
