'What the campaign tool prints, and the file desk call behind it.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import AnalysisCache, SandboxedProject

from . import desk, workload
from . import world as w


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-threshold-eligibility-",
    timeout=120.0,
)
CACHE = AnalysisCache()

MARKET = workload.CURRENT.market


def live_receipts(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    'The lots this delivery has been charged for, or why the file will not read.'

    try:
        return desk.read_receipts(Path(artifact_dir), workload.CURRENT), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def _record(path: Path) -> Mapping[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a working-session record must contain a JSON object")
    return raw


def snapshot(market: w.Market, record: Mapping[str, Any]) -> dict[str, Any]:
    "The campaign's evidence as it stood on the day of one working session."

    through = str(record["as_of"])
    context = market.context()
    context["window"]["last_day"] = through
    context["as_of"] = through
    register = []
    for row in context["register"]:
        if row["offer_date"] and row["offer_date"] > through:
            continue
        row = dict(row)
        if row["first_order_date"] and row["first_order_date"] > through:
            row["first_order_date"] = ""
        if row["last_observed_date"] and row["last_observed_date"] > through:
            row["last_observed_date"] = through
        register.append(row)
    context["register"] = register
    context["recompute"] = [
        row for row in context["recompute"] if row["refresh_date"] <= through
    ]
    return context


def _by_score(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Rows by quarter-point of standing score around the line, as the job counts them.'

    cut = float(context["cut"])
    rows: dict[float, dict[str, Any]] = {}
    for row in context["register"]:
        value = round(float(row["standing_score"]), 2)
        if abs(value - cut) > 3.0:
            continue
        entry = rows.setdefault(
            value, {"standing_score": value, "accounts": 0, "offered": 0, "credits_filed": 0}
        )
        entry["accounts"] += 1
        entry["offered"] += int(row["offer_flag"])
        entry["credits_filed"] += 1 if float(row["credits_filed"]) > 0 else 0
    return [rows[value] for value in sorted(rows)]


def _by_week(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Rows, offers and orders by run week, as the weekly job lays them out.'

    rows: dict[int, dict[str, Any]] = {}
    for row in context["register"]:
        week = int(row["run_week"])
        entry = rows.setdefault(
            week,
            {"run_week": week, "scored": 0, "carried": 0, "offered": 0,
             "orders_in_the_export": 0, "offer_date": row["offer_date"],
             "last_observed_date": row["last_observed_date"]},
        )
        entry["scored" if row["run_status"] == "scored" else "carried"] += 1
        entry["offered"] += int(row["offer_flag"])
        entry["orders_in_the_export"] += 1 if row["first_order_date"] else 0
        if row["offer_date"]:
            entry["offer_date"] = row["offer_date"]
        if row["last_observed_date"]:
            entry["last_observed_date"] = row["last_observed_date"]
    return [rows[week] for week in sorted(rows)]


def _receipt_view(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "receipt_id": item["receipt_id"],
            "week": item["week"],
            "band": item["band"],
            "above_share": item["above_share"],
            "files_charged": item["files_charged"],
            "files_remaining": item["files_remaining"],
            "rows_returned": item["rows_returned"],
            "refusal": item["refusal"],
        }
        for item in entries
    ]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    entries, error = live_receipts(root)
    market = workload.CURRENT
    context = market.context()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record(path)
        records.append({
            "record": f"project_records/{path.name}",
            **{key: raw.get(key) for key in ("session", "date", "analyst", "as_of")},
        })
    return {
        "summary": (
            f"The {context['market']} offer campaign, the council's terms and the "
            "working sessions on record."
        ),
        "measurements": {
            "market": context["market"],
            "window": context["window"],
            "as_of": context["as_of"],
            "cut": context["cut"],
            "credit_ceiling": context["credit_ceiling"],
            "order_window_days": context["order_window_days"],
            "export_stop_day": context["export_stop_day"],
            "publication_lag_days": context["publication_lag_days"],
            "review_grant": context["review_grant"],
            "council": context["council"],
            "accounts_in_the_register": len(context["register"]),
            "rows_in_the_recompute_log": len(context["recompute"]),
            "files_charged": market.files_spent(entries),
            "files_left": market.files_left(entries),
            "lots_on_the_receipts": _receipt_view(entries),
            "receipts": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    'Run the notebook the way that working session ran it.'

    record = _record(record_path)
    entries, _error = live_receipts(Path(artifact_dir))
    market = workload.CURRENT
    context = snapshot(market, record)
    receipts = [
        item for item in desk.opening_receipts(market)
        if str(item["receipt_id"]) in set(record.get("receipts_on_file", ()))
    ]
    run = PROJECT.invoke(
        Path(artifact_dir),
        {"requests": [
            {"kind": "report", "context": context, "receipts": receipts},
            {"kind": "plan", "context": context, "receipts": receipts},
        ]},
    )
    session = {
        "session": record.get("session"),
        "date": record.get("date"),
        "analyst": record.get("analyst"),
        "notes": list(record.get("notes", ())),
        "evidence_through": record.get("as_of"),
        "lots_on_the_receipts": _receipt_view(receipts),
        "by_standing_score": _by_score(context),
        "by_run_week": _by_week(context),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('session')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name, "market": context["market"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('session')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "market": context["market"],
            "as_of": context["as_of"],
            "cut": context["cut"],
            "rows_in_the_register": len(context["register"]),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_review_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_review(
    artifact_dir: Path, week: Any, band: Any, above_share: Any, files: Any, receipt_id: Any
) -> Mapping[str, Any]:
    entries, error = live_receipts(Path(artifact_dir))
    if error:
        raise ValueError(error)
    return desk.review(
        Path(artifact_dir), workload.CURRENT, week, band, above_share, files, receipt_id
    )


def starting_receipts() -> dict[str, Any]:
    'The receipts the campaign starts from: the two lots already charged.'

    return {
        "market": workload.CURRENT.market,
        "lots": desk.opening_receipts(workload.CURRENT),
    }
