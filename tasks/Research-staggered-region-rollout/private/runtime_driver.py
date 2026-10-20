'Run one rollout notebook over a batch of networks inside the sandbox.'

from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
import sys


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _write_csv(name: str, columns: tuple[str, ...], rows) -> None:
    with open(name, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


def incident_log(context: dict) -> str:
    'The on-call log for the window, as the dispatch team keeps it.'

    lines = [
        f"# Dispatch on-call log — {context.get('network')} rollout",
        "",
        "One line per page or change, in the order the on-call engineer wrote it.",
        "`event` is the word the runbook asks for: paged, restarted, reloaded,",
        "degraded, disabled.",
        "",
        "| date | time | region | event | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in context.get("dispatch_incidents", ()):
        lines.append(
            f"| {row['date']} | {row['time']} | {row['region']} | {row['event']} "
            f"| {row['note']} |"
        )
    lines.append("")
    return "\n".join(lines)


def board_minute(context: dict, receipts: list) -> str:
    "The wave board's standing minute for the network this run is reading."

    network = str(context.get("network"))
    book = context.get("book", {})
    terms = context.get("capacity", {})
    low, high = (int(value) for value in terms["holdback_share_band"])
    charged = len(list(receipts))
    lines = [
        "# Wave board: standing minute",
        "",
        f"The standing minute as the wave board keeps it for the {network} rollout.",
        "",
        "## What the board decides",
        "",
        "Batching goes to the metros still waiting on the register, or the network",
        "stays on the one-drop dispatcher for the rest of the year. The board takes",
        "that decision from the rollout readout and from nothing else.",
        "",
        "## The book",
        "",
        f"The programme is judged on the region book cut on {book.get('counted_on')}.",
        "The book is the metros the board committed the half to, with the orders each",
        "of them was running on the day it was cut; `region_book.json` carries both.",
        f"The window the board reads closes on {book.get('window_closes_on')} and a metro",
        "that has not gone live by then has nothing in the readout.",
        "",
        f"The board reads a metro on its first {int(context['exposure_days'])} days on",
        f"batching, against the {int(context['baseline_days'])} days before it, because",
        "that is the comparison the depot managers were shown when they signed up to",
        "the schedule.",
        "",
        "For each exposure day, the comparison is the other metros in the same",
        "service band that had not gone live by that day. Read those same metros",
        "over the before-period. If the export starts inside that period, use every",
        "pre-live day it carries; do not drop the metro or its exposure days to make",
        "a complete pair.",
        "",
        "The book decides which live metros enter the number and weights them at",
        "the orders recorded on the cut day. Within a metro, each daily sampled rate",
        "is one day's reading; sampled-order counts determine the range, not its weight.",
        "",
        "## What earns the decision",
        "",
        "A move in on-time share, in on-time points, batching against no batching.",
        "`board_bar_points` in `rollout_context.json` carries the number the board acts",
        f"inside: {float(context['board_bar_points'])} points. The board will not take a",
        "decision from a readout whose range is wider than that.",
        "",
        "One sentence here is delivery finance's own and stands as they wrote it: at",
        "most one chance in twenty, across the whole set of networks this readout is",
        "produced for, of acting on a number that is not there. The same notebook",
        f"produces the readout for {int(context['networks_reviewed'])} networks.",
        "",
        "## Wave capacity",
        "",
        f"The board granted the programme {int(terms['region_weeks_granted'])} region-weeks",
        f"this half. {charged} are charged; `wave_receipts.json` carries the receipts and is",
        "the board's own record of what it charged.",
        "",
        "The terms the wave board serves on:",
        "",
        f"- at most {int(terms['region_weeks_per_week'])} region-weeks in any one calendar week;",
        f"- between {low} and {high} percent of the metro's orders held back from batching",
        "  for the week, so the depot keeps a control on its own ground;",
        "- only a metro that has not gone live, and only one running more than",
        f"  {int(terms['minimum_orders_per_day'])} orders a day, because the wave desk will",
        "  not staff a smaller one;",
        "- a week the board hands back is charged against the grant all the same. The",
        "  desk time goes whether or not the vans move.",
        "",
        "Until the current range is inside the board's bar, the next week must leave",
        "the next board's range at least as narrow as a full week on the largest metro",
        "the desk will still serve at the smallest held-back share allowed above. If",
        "no region-week can meet the desk's terms, there is nothing to book.",
        "",
    ]
    return "\n".join(lines)


def schema_note(context: dict) -> str:
    "The platform group's note on the two counters, for this network's export."

    return "\n".join(
        [
            "# On-time counters in the dispatch export",
            "",
            "The dispatch platform group's note on what is in `region_daily.csv` and",
            f"`order_sample.csv` for the {context.get('network')} network.",
            "",
            "## Where `ontime_orders` comes from",
            "",
            "Two services write it, and which one writes a metro's rows depends on which",
            "stack that metro is on.",
            "",
            "- The one-drop dispatcher, which every metro started on, counts an order on",
            "  time when it is delivered inside the promise measured from `placed_at` —",
            "  the moment the customer confirmed the order.",
            "- The batching stack, which a metro moves to on its `stack_migrated_on` date",
            "  in `rollout_register.csv`, counts an order on time when it is delivered",
            "  inside the promise measured from `assigned_at` — the moment the order is",
            "  attached to a van's run.",
            "",
            "The export writes one `ontime_orders` column and the metro's current stack",
            "fills it. There is no flag on the row saying which service wrote it; the",
            "migration date on the register is the only thing that says.",
            "",
            "`orders` is the same count on both stacks: every order the metro took that",
            "day.",
            "",
            "## `order_sample.csv`",
            "",
            "The sampling job takes a few percent of each metro's orders every day and",
            "keeps both raw stamps for them. `sampled_orders` is how many orders the",
            "sample holds for that metro-day, `ontime_by_placed_at` and",
            "`ontime_by_assigned_at` are the two counts over exactly those orders.",
            "",
            "The sample rate per metro is set in the sampling job's config and has not",
            "been changed this half. It is not the same for every metro.",
            "",
            "## Migration",
            "",
            "Moving a metro is a config flip and a drain of the old queue; it takes an",
            "hour and is scheduled by the platform group, not by the rollout programme.",
            "",
            "## `booked_weeks.csv`",
            "",
            "Rows the wave desk returns for a booked region-week, one per metro-day and",
            "arm. `arm` is `batched` or `held_back`. The columns are the same two counters",
            "over that arm's sampled orders.",
            "",
        ]
    )


def _publish(context: dict, receipts: list, home: str | None = None) -> None:
    'Lay the network out on disk the way the reporting pipeline leaves it.'

    Path("dispatch_incident_log.md").write_text(incident_log(context), encoding="utf-8")
    if home is not None and str(context.get("network")) != str(home):
        Path("wave_board_minute.md").write_text(
            board_minute(context, receipts), encoding="utf-8"
        )
        Path("pipeline_schema_note.md").write_text(schema_note(context), encoding="utf-8")
    Path("rollout_context.json").write_text(
        json.dumps(context, sort_keys=True), encoding="utf-8"
    )
    Path("wave_receipts.json").write_text(
        json.dumps(
            {"network": context.get("network"), "entries": receipts},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    Path("region_book.json").write_text(
        json.dumps(context.get("book", {}), indent=2, sort_keys=True), encoding="utf-8"
    )
    Path("dispatch_incident_log.json").write_text(
        json.dumps(
            {"network": context.get("network"),
             "entries": context.get("dispatch_incidents", [])},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_csv(
        "rollout_register.csv",
        ("region", "band", "readiness_score", "live_from", "stack_migrated_on",
         "orders_per_day"),
        context.get("register", ()),
    )
    _write_csv(
        "region_daily.csv",
        ("region", "date", "orders", "ontime_orders", "ontime_rate"),
        context.get("daily", ()),
    )
    _write_csv(
        "order_sample.csv",
        ("region", "date", "sampled_orders", "ontime_by_placed_at", "ontime_by_assigned_at"),
        context.get("order_sample", ()),
    )
    _write_csv(
        "booked_weeks.csv",
        ("region", "week", "date", "arm", "orders", "sampled_orders",
         "ontime_by_placed_at", "ontime_by_assigned_at"),
        context.get("booked_weeks", ()),
    )


def _home_network() -> str | None:
    'The network whose workspace this is, read before anything is republished.'

    try:
        raw = json.loads(Path("rollout_context.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return str(raw.get("network")) if isinstance(raw, dict) else None


def main() -> int:
    captured = io.StringIO()
    try:
        home = _home_network()
        payload = json.load(sys.stdin)
        contexts = list(payload.get("contexts") or ())
        results = []
        published = None
        with contextlib.redirect_stdout(captured):
            import analysis
            from protocol import plan_view, report_view

            for raw in payload.get("requests", ()):
                request = dict(raw)
                context = request.get("context")
                if isinstance(context, int):
                    context = contexts[context]
                context = context or {}
                receipts = list(request.get("receipts") or ())


                stamp = (id(context), json.dumps(receipts, sort_keys=True))
                if stamp != published:
                    _publish(context, receipts, home)
                    published = stamp
                try:
                    if request.get("kind") == "plan":
                        answer = plan_view(analysis.next_collection(context, receipts))
                    else:
                        answer = report_view(analysis.analyze(context, receipts))
                    json.dumps(answer, allow_nan=False)
                    results.append({"ok": True, "answer": answer})
                except BaseException as exc:
                    results.append({"ok": False, "error": _describe(exc)})
        result = {"ok": True, "results": results, "stdout": captured.getvalue()[-2000:]}
        json.dumps(result, allow_nan=False)
    except BaseException as exc:
        result = {"ok": False, "error": _describe(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
