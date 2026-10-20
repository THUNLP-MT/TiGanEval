"The files the reporting pipeline leaves in the programme's workspace."

from __future__ import annotations

import csv
import io
import json
from typing import Any, Mapping, Sequence

from . import receipts as r
from . import runtime_driver
from . import workload
from . import world as w

CSV_FILES: Mapping[str, tuple[str, ...]] = {
    "rollout_register.csv": (
        "region", "band", "readiness_score", "live_from", "stack_migrated_on",
        "orders_per_day",
    ),
    "region_daily.csv": ("region", "date", "orders", "ontime_orders", "ontime_rate"),
    "order_sample.csv": (
        "region", "date", "sampled_orders", "ontime_by_placed_at", "ontime_by_assigned_at",
    ),
    "booked_weeks.csv": (
        "region", "week", "date", "arm", "orders", "sampled_orders",
        "ontime_by_placed_at", "ontime_by_assigned_at",
    ),
}


def _csv(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in columns})
    return buffer.getvalue()


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def incident_log(network: w.Network) -> str:
    'The on-call log for the window, as the dispatch team keeps it.'

    return runtime_driver.incident_log(network.context())


def starting_receipts() -> dict[str, Any]:
    'The region-weeks the wave board has already charged this campaign for.'

    return {
        "network": workload.CURRENT.network,
        "entries": r.history(workload.CURRENT, workload.HISTORY_BOOKINGS),
    }


def files() -> dict[str, str]:
    'Every generated file in the workspace, by its workspace-relative name.'

    network = workload.CURRENT
    context = network.context()
    out = {
        "rollout_context.json": _json(context),
        "wave_receipts.json": _json(starting_receipts()),
        "region_book.json": _json(context["book"]),
        "dispatch_incident_log.json": _json(
            {"network": network.network, "entries": context["dispatch_incidents"]}
        ),
        "dispatch_incident_log.md": incident_log(network),
    }
    for name, columns in CSV_FILES.items():
        key = {
            "rollout_register.csv": "register",
            "region_daily.csv": "daily",
            "order_sample.csv": "order_sample",
            "booked_weeks.csv": "booked_weeks",
        }[name]
        out[name] = _csv(columns, context[key])
    return out
