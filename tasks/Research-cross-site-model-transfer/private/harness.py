'Read one delivered triage report against the centres it is a report about.'

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, CANDIDATE_FAILURE, SandboxedProject, failed_analysis

from . import oracle, workload, world


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("analysis.py", "support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-transfer-",
    timeout=60.0,
)
_CACHE = AnalysisCache()

RUBRICS = (
    "served_stream_error",
    "published_error_range",
    "report_built_from_the_intake_counters",
    "next_review_request",
    "reviews_reconcile_with_the_ledger",
)
BUCKETS: Mapping[str, str] = {rubric: rubric for rubric in RUBRICS}

FAILURE_MODES: Mapping[str, tuple[str, ...]] = {
    "served_stream_error": (
        "error_taken_from_the_source_centre",
        "tickets_the_queue_never_showed_left_out",
        "groups_weighted_by_the_rows_reviewed",
        "served_error_disagrees",
        "candidate_execution_failed",
    ),
    "published_error_range": (
        "range_is_not_an_interval",
        "range_misses_the_error",
        "range_narrower_than_the_reviews_support",
        "range_wider_than_the_reviews_support",
        "candidate_execution_failed",
    ),
    "report_built_from_the_intake_counters": (
        "report_has_no_breakdown",
        "group_bands_do_not_match_the_intake",
        "group_shares_do_not_match_the_counters",
        "group_review_count_disagrees_with_the_ledger",
        "published_error_is_not_the_groups_combined",
        "group_error_disagrees_with_the_reviewed_rows",
        "candidate_execution_failed",
    ),
    "next_review_request": (
        "request_is_not_a_review_or_a_stop",
        "review_spend_missed_the_hidden_band",
        "request_buys_source_centre_labels",
        "request_uses_the_queue_for_tickets_it_never_shows",
        "request_over_the_per_request_cap",
        "request_over_the_quarter_units",
        "request_does_not_reach_the_whole_unreviewed_band",
        "request_leaves_the_unreviewed_tickets_thin",
        "request_buys_reviews_with_nothing_hidden",
        "request_after_quarter_units_spent",
        "candidate_execution_failed",
    ),
    "reviews_reconcile_with_the_ledger": (
        "ledger_unreadable",
        "reviews_are_not_a_list",
        "review_missing_from_the_report",
        "review_not_on_the_ledger",
        "review_reported_twice",
        "review_channel_disagrees_with_the_ledger",
        "review_rows_disagree_with_the_ledger",
        "review_units_disagree_with_the_ledger",
        "units_disagree_with_the_ledger",
        "candidate_execution_failed",
    ),
}

CURRENT_DEPLOYMENT = str(workload.CURRENT_SPEC["deployment"])


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, wanted: float | None, slack: float) -> bool:
    read = _number(value)
    return read is not None and wanted is not None and abs(read - float(wanted)) <= slack


def _points(value: Any) -> str:
    'One error rate written the way the centre managers write it.'

    read = _number(value)
    if read is None:
        return _show(value)
    return format(read * 100.0, ".1f")


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
        if not value:
            return "no entries at all"
        return "a list of " + str(len(value)) + " entries"
    if isinstance(value, dict):
        return "an entry for " + ", ".join(sorted(map(str, value)))
    if value is None:
        return "empty"
    return str(value)


def _window_label(low: Any, high: Any) -> str:
    if low is None and high is None:
        return "every ticket received"
    if low is None:
        return f"under {int(high) + 1} prior contacts"
    if high is None:
        return f"{int(low)} prior contacts and over"
    return f"{int(low)} to {int(high)} prior contacts"


def _canonical_window(low: Any, high: Any) -> tuple[Any, Any]:
    'Zero and an open lower bound cover the same non-negative counts.'

    return (None if low == 0 else low, high)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _where(stream: world.Stream) -> dict[str, str]:
    'The centre a failure happened at, in the words the owner uses for it.'

    return {"deployment": stream.deployment, "centre": stream.site.capitalize()}


def _report_order(record: Mapping[str, Any]) -> tuple[int, int]:
    'Put the incident the owner can open her own files for first.'

    return (
        0 if str(record.get("kind")) == CANDIDATE_FAILURE else 1,
        0 if record.get("deployment") == CURRENT_DEPLOYMENT else 1,
    )


def archived_ledger(stream: world.Stream, queue_rows: int, export_rows: int) -> list[dict[str, Any]]:
    'The reviews a centre had already paid for when its quarter was handed on.'

    entries: list[dict[str, Any]] = []
    entries = world.review(
        stream, entries, "queue", None, None, queue_rows,
        f"{stream.site[:2]}-q1", str(stream.days[7]),
    )
    unseen = oracle.unseen_window(stream)
    if unseen is not None and export_rows:
        entries = world.review(
            stream, entries, "export", None, int(unseen[1]), export_rows,
            f"{stream.site[:2]}-x1", str(stream.days[-2]),
        )
    return entries


ARCHIVED_ROWS: Mapping[str, tuple[int, int]] = {
    "ashcombe-q3": (200, 60),
    "delford-q3": (180, 60),
    "marren-q3": (240, 60),
    "pellwood-q3": (180, 60),
    "tarnbrook-q3": (240, 0),
}


def following_ledger(stream: world.Stream) -> list[dict[str, Any]]:
    queue_rows, export_rows = ARCHIVED_ROWS[stream.deployment]
    return archived_ledger(stream, queue_rows, export_rows)


def starting_ledger() -> dict[str, Any]:
    "The ledger Brookfield's quarter opens with: the first fortnight's reviews."

    stream = workload.current()
    entries: list[dict[str, Any]] = []
    for receipt_id, day, rows in (
        ("bf-w1-queue", "2026-08-14", 140),
        ("bf-w2-queue", "2026-08-24", 100),
    ):
        entries = world.review(
            stream, entries, "queue", None, None, rows, receipt_id, day, through=day
        )
    return world.ledger_document(stream, entries)


def live_ledger(artifact_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return world.read_ledger(Path(artifact_dir), workload.current()), None
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], str(exc)


def plan_states(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    "Every state of this centre's quarter, with what it can still pay for."

    states = [{"label": "now", "ledger": [dict(item) for item in entries]}]
    held = [dict(item) for item in entries]
    for step in range(6):
        plan = oracle.one_allowed_plan(stream, held)
        if plan == "stop":
            break
        held = world.review(
            stream, held, str(plan["channel"]), plan["prior_contacts_min"],
            plan["prior_contacts_max"], int(plan["rows"]), f"walk-{step + 1}",
            str(stream.spec["as_of"]),
        )
        states.append({"label": f"after {len(held)} reviews", "ledger": [dict(item) for item in held]})


    burnt = [dict(item) for item in entries]
    for step in range(12):
        rows = oracle.affordable_rows(stream, burnt, "queue")
        if rows <= 0:
            break
        burnt = world.review(
            stream, burnt, "queue", None, None, rows, f"burn-{step + 1}",
            str(stream.spec["as_of"]),
        )
    states.append({"label": "units spent", "ledger": burnt})
    return states


def cases(live: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Live Brookfield, its public replay states, then the centres after it.'

    current = workload.current()
    rows = [
        {
            "stream": current,
            "ledger": [dict(item) for item in live],
            "plan_base": [dict(item) for item in live],
            "scored": True,
            "range_scored": True,
        }
    ]
    opening = list(starting_ledger()["entries"])
    live_key = tuple(str(item.get("seal")) for item in live)


    opening_key = tuple(str(item.get("seal")) for item in opening)
    if opening_key != live_key:
        rows.append(
            {
                "stream": current,
                "ledger": [dict(item) for item in opening],
                "plan_base": None,
                "scored": False,
                "range_scored": True,
            }
        )
    for stream in (*workload.following(), workload.lifted()):
        archived = following_ledger(stream)
        rows.append(
            {
                "stream": stream,
                "ledger": archived,
                "plan_base": archived,
                "scored": stream.threshold > 0,
                "range_scored": stream.threshold > 0,
            }
        )
    return rows


def _estimate_failures(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    truth = oracle.served_error(stream)
    reported = report.get("served_error")
    if _near(reported, truth, oracle.TOLERANCE):
        return []
    counters = stream.counters()
    skipped_total = sum(int(row["skipped_no_history_panel"]) for row in counters)
    received_total = sum(int(row["received"]) for row in counters)
    unseen = oracle.unseen_window(stream)
    shared = {
        **_where(stream),
        "reported": _points(reported),
        "skipped_total": skipped_total,
        "received_total": received_total,
        "counter_share": _points(skipped_total / received_total if received_total else 0.0),
        "reviewed_rows": len(oracle.ledger_rows(entries)),
    }
    if _near(reported, oracle.source_holdout_error(), oracle.DECOY_SLACK):
        return [_fail("error_taken_from_the_source_centre", **shared)]
    if unseen is not None and _near(
        reported, oracle.queue_only_error(stream, entries), oracle.DECOY_SLACK
    ):
        return [_fail("tickets_the_queue_never_showed_left_out", **shared)]
    if _near(reported, oracle.rows_weighted_error(stream, entries), oracle.DECOY_SLACK):
        return [_fail("groups_weighted_by_the_rows_reviewed", **shared)]
    return [_fail("served_error_disagrees", **shared)]


def _range_shape(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'Everything about a published range except whether it holds the error.'

    published = report.get("error_interval")
    shared = {
        **_where(stream),
        "reviewed_rows": len(oracle.ledger_rows(entries)),
        "reported_range": _pair(published),
    }
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
        or float(published[0]) > float(published[1])
        or float(published[0]) < 0.0
        or float(published[1]) > 1.0
    ):
        return [_fail("range_is_not_an_interval", **shared, reported=_pair(published))]
    centre = _number(report.get("served_error"))
    if centre is not None and not float(published[0]) <= centre <= float(published[1]):
        return [_fail("range_is_not_an_interval", **shared, reported=_pair(published))]
    supported_low, supported_high = oracle.supported_bounds(stream, entries)
    core_low, core_high = oracle.supported_bounds(
        stream, entries, spread_scale=oracle.TAIL_FLOOR
    )
    low, high = float(published[0]), float(published[1])


    if low > core_low + 1e-12 or high < core_high - 1e-12:
        return [_fail("range_narrower_than_the_reviews_support", **shared)]
    required = supported_high - supported_low
    width = float(published[1]) - float(published[0])
    if width < required * oracle.RANGE_FLOOR - 1e-12:
        return [_fail("range_narrower_than_the_reviews_support", **shared)]
    if width > required * oracle.RANGE_CEILING + 1e-12:
        return [_fail("range_wider_than_the_reviews_support", **shared)]
    return []


def _range_covers(stream: world.Stream, report: Mapping[str, Any]) -> bool:
    published = report.get("error_interval")
    if (
        not isinstance(published, list)
        or len(published) != 2
        or any(_number(value) is None for value in published)
    ):
        return False
    truth = oracle.served_error(stream)
    return float(published[0]) <= truth <= float(published[1])


def _counter_failures(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]], report: Mapping[str, Any]
) -> list[dict[str, Any]]:
    groups = report.get("groups")
    where = _where(stream)
    if not isinstance(groups, list) or not groups:
        return [_fail("report_has_no_breakdown", **where, reported=_show(groups))]

    def labels(windows: Sequence[tuple[Any, Any]]) -> str:
        return "; ".join(_window_label(*window) for window in windows)

    expected_windows = [_canonical_window(*window) for window in oracle.windows(stream)]
    reported_windows = []
    for entry in groups:
        if not isinstance(entry, Mapping):
            return [_fail("report_has_no_breakdown", **where, reported=_show(entry))]
        low, high = entry.get("prior_contacts_min"), entry.get("prior_contacts_max")
        reported_windows.append(
            _canonical_window(
                int(low) if isinstance(low, int) and not isinstance(low, bool) else None,
                int(high) if isinstance(high, int) and not isinstance(high, bool) else None,
            )
        )
    if Counter(reported_windows) != Counter(expected_windows):
        return [
            _fail(
                "group_bands_do_not_match_the_intake",
                **where,
                reported_groups=labels(reported_windows),
                expected_groups=labels(expected_windows),
                history_panel_from_contact=stream.threshold,
            )
        ]
    reported_shares = 0.0
    measured_total = 0.0
    unmeasured_share = 0.0
    for entry in groups:
        if not isinstance(entry, Mapping):
            return [_fail("report_has_no_breakdown", **where, reported=_show(entry))]
        low, high = entry.get("prior_contacts_min"), entry.get("prior_contacts_max")
        window = (
            int(low) if isinstance(low, int) and not isinstance(low, bool) else None,
            int(high) if isinstance(high, int) and not isinstance(high, bool) else None,
        )
        label = _window_label(*window)
        counter_share = oracle.window_share(stream, window)
        reported_share = _number(entry.get("share_of_received"))
        common = {
            **where,
            "group": label,
            "counter_share": _points(counter_share),
            "reported_share": _points(reported_share),
            "reported_error": _points(entry.get("error")),
        }
        if reported_share is None or abs(reported_share - counter_share) > oracle.SHARE_SLACK:
            return [_fail("group_shares_do_not_match_the_counters", **common)]
        reported_shares += reported_share
        reviewed_rows = len(oracle.rows_in_window(entries, window))
        reported_rows = _number(entry.get("rows_reviewed"))
        if reported_rows is None or abs(reported_rows - reviewed_rows) > 0.0:
            return [
                _fail(
                    "group_review_count_disagrees_with_the_ledger",
                    **common,
                    reported_rows=_show(entry.get("rows_reviewed")),
                    ledger_rows=reviewed_rows,
                )
            ]
        measured = oracle.reviewed_error(entries, window)
        rate = _number(entry.get("error"))
        if counter_share <= 0.0 and measured is None:


            continue
        if rate is None:


            if measured is None:
                unmeasured_share += counter_share
                continue
            return [_fail("group_error_disagrees_with_the_reviewed_rows", **common,
                          reviewed_error=_points(measured))]
        if measured is None or abs(rate - measured) > oracle.GROUP_SLACK:
            return [_fail("group_error_disagrees_with_the_reviewed_rows", **common,
                          reviewed_error=_points(measured))]
        measured_total += counter_share * measured
    if reported_shares <= 0.0 or abs(reported_shares - 1.0) > oracle.SHARE_SLACK:
        return [_fail("group_shares_do_not_match_the_counters", **where, group="every group",
                      counter_share=_points(1.0), reported_share=_points(reported_shares),
                      reported_error=_points(report.get("served_error")))]


    if unmeasured_share > 0.0:
        reported = _number(report.get("served_error"))
        if reported is None or (
            measured_total - 1e-12 <= reported <= measured_total + unmeasured_share + 1e-12
        ):
            return []
        return [_fail("published_error_is_not_the_groups_combined", **where,
                      reported=_points(reported), combined=_pair(
                          [measured_total, measured_total + unmeasured_share]
                      ), groups_counted=len(groups))]
    reported = _number(report.get("served_error"))
    if reported is None or abs(reported - measured_total) > oracle.COMBINATION_SLACK:
        return [_fail("published_error_is_not_the_groups_combined", **where,
                      reported=_points(reported), combined=_points(measured_total),
                      groups_counted=len(groups))]
    return []


def _collection_failures(
    stream: world.Stream, entries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'Reject irreversible hand-off spend outside the complete hidden route.'

    opening = list(starting_ledger()["entries"])
    if len(entries) < len(opening):
        return []
    unseen = oracle.unseen_window(stream)
    if unseen is None:
        return []
    expected = _canonical_window(*unseen)
    for entry in entries[len(opening):]:
        actual = _canonical_window(
            entry.get("prior_contacts_min"), entry.get("prior_contacts_max")
        )
        if entry.get("channel") == "export" and actual == expected:
            continue
        receipt_id = str(entry.get("receipt_id"))
        channel = str(entry.get("channel"))
        requested = _window_label(*actual)
        expected_label = _window_label(*expected)
        return [
            _fail(
                "review_spend_missed_the_hidden_band",
                **_where(stream),
                receipt_id=receipt_id,
                channel=channel,
                requested_band=requested,
                expected_band=expected_label,
                units_charged=int(entry.get("units_charged", 0)),
                reported=f"review {receipt_id} on the {channel} for {requested}",
            )
        ]
    return []


def _plan_failures(
    stream: world.Stream, state: Mapping[str, Any], answer: Any
) -> list[dict[str, Any]]:
    entries = state["ledger"]
    counters = stream.counters()
    context = stream.context()
    shared = {
        **_where(stream),
        "units_left": oracle.units_left(stream, entries),
        "units_granted": int(stream.spec["units_granted"]),
        "skipped_total": sum(int(row["skipped_no_history_panel"]) for row in counters),
    }
    if isinstance(answer, list):
        choices = list(answer)
    else:
        choices = [answer]
    if not choices:
        return [_fail("request_is_not_a_review_or_a_stop", **shared, reported=_show(answer),
                      invalid_reason="the notebook returned no instruction",
                      cap=int(context["review"]["max_rows_per_request"]["export"]),
                      site_asked="empty")]
    for choice in choices:
        problem = oracle.plan_is_allowed(stream, entries, choice)
        if problem is None:
            continue
        asked = choice if isinstance(choice, Mapping) else {}
        invalid_reason = "the record does not match the desk's request terms"
        if problem == "request_is_not_a_review_or_a_stop":
            if not isinstance(choice, Mapping):
                invalid_reason = "it is not a request record"
            elif choice.get("channel") not in world.CHANNELS:
                invalid_reason = "the channel is not one the desk accepts"
            elif not isinstance(choice.get("rows"), int) or isinstance(choice.get("rows"), bool):
                invalid_reason = "rows is not a whole number"
            elif int(choice["rows"]) <= 0:
                invalid_reason = "rows is not positive"
            else:
                low = choice.get("prior_contacts_min")
                high = choice.get("prior_contacts_max")
                invalid_bound = next(
                    (
                        name
                        for name, value in (
                            ("prior_contacts_min", low),
                            ("prior_contacts_max", high),
                        )
                        if value is not None
                        and (
                            not isinstance(value, int)
                            or isinstance(value, bool)
                            or int(value) < 0
                        )
                    ),
                    None,
                )
                if invalid_bound is not None:
                    invalid_reason = (
                        f"{invalid_bound} is not a non-negative whole number"
                    )
                elif low is not None and high is not None and int(low) > int(high):
                    invalid_reason = "the lower contact boundary is above the upper one"
                elif choice.get("site") is None:
                    invalid_reason = "the request does not name a site"
        site = asked.get("site")
        requested_band = "not a readable contact band"
        if problem == "request_does_not_reach_the_whole_unreviewed_band":
            requested_band = _window_label(
                asked.get("prior_contacts_min"), asked.get("prior_contacts_max")
            )
        unseen = oracle.unseen_window(stream)
        expected_band = _window_label(*unseen) if unseen is not None else "no hidden band"
        return [
            _fail(
                problem,
                **shared,
                reported=_show(choice if not isinstance(choice, Mapping) else
                               f"{asked.get('rows')} rows on the {asked.get('channel')}"),
                invalid_reason=invalid_reason,
                site_asked=str(site).capitalize() if site is not None else "empty",
                requested_band=requested_band,
                expected_band=expected_band,
                cap=int(
                    context["review"]["max_rows_per_request"].get(
                        str(asked.get("channel")),
                        context["review"]["max_rows_per_request"]["export"],
                    )
                ),
            )
        ]
    return []


def _ledger_failures(
    stream: world.Stream,
    entries: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    ledger_error: str | None,
) -> list[dict[str, Any]]:
    where = _where(stream)
    if ledger_error:
        return [_fail("ledger_unreadable", **where, reason=str(ledger_error))]
    rows = report.get("reviews")
    paid_for = len(entries)
    if not isinstance(rows, list):
        return [_fail("reviews_are_not_a_list", **where, reported=_show(rows),
                      paid_for=paid_for)]
    billed = {str(item["receipt_id"]): item for item in entries}
    seen: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return [_fail("reviews_are_not_a_list", **where, reported=_show(row),
                          paid_for=paid_for)]
        key = str(row.get("receipt_id"))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return [_fail("review_reported_twice", **where, receipt_id=key,
                          times_reported=seen[key])]
        entry = billed.get(key)
        if entry is None:
            return [_fail("review_not_on_the_ledger", **where, receipt_id=key,
                          paid_for=paid_for)]
        reported_channel = row.get("channel")
        if reported_channel != entry["channel"]:
            return [_fail("review_channel_disagrees_with_the_ledger", **where,
                          receipt_id=key, reported_channel=_show(reported_channel),
                          ledger_channel=str(entry["channel"]))]
        reported_rows = _number(row.get("rows_returned"))
        if reported_rows is None or reported_rows > int(entry["n_returned"]):
            return [_fail("review_rows_disagree_with_the_ledger", **where, receipt_id=key,
                          reported_rows=_show(row.get("rows_returned")),
                          ledger_rows=int(entry["n_returned"]))]
        if abs(reported_rows - int(entry["n_returned"])) > 0.0:
            return [_fail("review_rows_disagree_with_the_ledger", **where, receipt_id=key,
                          reported_rows=_show(row.get("rows_returned")),
                          ledger_rows=int(entry["n_returned"]))]
        reported_units = _number(row.get("units_charged"))
        if reported_units is None or abs(reported_units - int(entry["units_charged"])) > 0.0:
            return [_fail("review_units_disagree_with_the_ledger", **where,
                          receipt_id=key,
                          reported_units=_show(row.get("units_charged")),
                          ledger_units=int(entry["units_charged"]))]
    for key, entry in billed.items():
        if key not in seen:
            return [_fail("review_missing_from_the_report", **where, receipt_id=key,
                          paid_for=paid_for)]
    ledger_units = world.units_spent(entries)
    reported_units = _number(report.get("units_used"))
    if reported_units is None or abs(reported_units - ledger_units) > 0.0:
        return [_fail("units_disagree_with_the_ledger", **where,
                      reported_units=_show(report.get("units_used")),
                      ledger_units=ledger_units)]
    return []


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
    return f"the report notebook stopped part way through: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the delivered notebook over every centre and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        entries, ledger_error = live_ledger(Path(artifact_dir))
        rows = cases(entries)
        requests: list[dict[str, Any]] = []
        reports: list[tuple[dict[str, Any], int]] = []
        plans: list[tuple[world.Stream, dict[str, Any], int]] = []
        for row in rows:
            stream = row["stream"]
            reports.append((row, len(requests)))
            requests.append(
                {"kind": "report", "context": stream.context(), "ledger": row["ledger"]}
            )
            if row["plan_base"] is None:
                continue
            for state in plan_states(stream, row["plan_base"]):
                plans.append((stream, state, len(requests)))
                requests.append(
                    {"kind": "plan", "context": stream.context(), "ledger": state["ledger"]}
                )
        run = PROJECT.invoke(Path(artifact_dir), {"requests": requests})
        if not run.get("ok"):
            analysis = dict(failed_analysis(_console_error(run), tuple(BUCKETS.values())))
            for bucket in BUCKETS.values():
                for failure in analysis[bucket]:
                    failure["operation"] = "the notebook run before any centre returned an answer"
            if run.get("diagnostic"):
                analysis["diagnostic"] = str(run["diagnostic"])
            analysis["case"] = {"deployment": CURRENT_DEPLOYMENT, "reviews_paid_for": len(entries)}
            return analysis

        results = list(run.get("results", ()))
        failures: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKETS.values()}

        def answer(index: int) -> tuple[Any, str | None]:
            if index >= len(results):
                return None, "the notebook returned no answer for one of the centres"
            item = dict(results[index])
            if not item.get("ok"):
                return None, str(item.get("error") or "the notebook stopped")
            return item.get("answer"), None

        stopped = False
        uncovered: list[dict[str, Any]] = []
        for row, index in reports:
            stream, ledger = row["stream"], row["ledger"]
            value, error = answer(index)
            if error is not None:
                stopped = True
                for bucket in ("served_stream_error", "published_error_range",
                               "report_built_from_the_intake_counters",
                               "reviews_reconcile_with_the_ledger"):
                    failures[bucket].append(
                        _fail(
                            CANDIDATE_FAILURE,
                            **_where(stream),
                            operation=f"the {stream.site.capitalize()} report",
                            error=error,
                        )
                    )
                continue
            report = dict(value or {})
            if row["scored"]:
                failures["served_stream_error"].extend(
                    _estimate_failures(stream, ledger, report)
                )
            if row["range_scored"]:
                shape = _range_shape(stream, ledger, report)
                failures["published_error_range"].extend(shape)
                if not shape and not _range_covers(stream, report):
                    uncovered.append(
                        _fail(
                            "range_misses_the_error",
                            **_where(stream),
                            reported_range=_pair(report.get("error_interval")),
                            reviewed_rows=len(oracle.ledger_rows(ledger)),
                        )
                    )
            failures["report_built_from_the_intake_counters"].extend(
                _counter_failures(stream, ledger, report)
            )
            failures["reviews_reconcile_with_the_ledger"].extend(
                _ledger_failures(
                    stream, ledger, report,
                    ledger_error if stream.deployment == CURRENT_DEPLOYMENT else None,
                )
            )
        if ledger_error is None:
            failures["next_review_request"].extend(
                _collection_failures(workload.current(), entries)
            )


        here = [item for item in uncovered if item["deployment"] == CURRENT_DEPLOYMENT]
        if here or len(uncovered) > 1:
            failures["published_error_range"].extend(uncovered)

        for stream, state, index in plans:
            value, error = answer(index)
            if error is not None:
                stopped = True
                failures["next_review_request"].append(
                    _fail(
                        CANDIDATE_FAILURE,
                        **_where(stream),
                        operation=f"the {stream.site.capitalize()} next-review request",
                        error=error,
                    )
                )
                continue
            failures["next_review_request"].extend(_plan_failures(stream, state, value))

        analysis: dict[str, Any] = {
            rubric: sorted(records, key=_report_order)
            for rubric, records in failures.items()
        }
        analysis["case"] = {
            "deployment": CURRENT_DEPLOYMENT,
            "reviews_paid_for": len(entries),
            "centres_reviewed": len(
                {str(row["stream"].deployment) for row in rows}
            ),
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
            "receipt_id", "day", "site", "channel", "prior_contacts_min",
            "prior_contacts_max", "n_requested", "n_returned", "n_skipped",
            "units_charged", "snapshot_id",
        )
    }


def snapshot(stream: world.Stream, record: Mapping[str, Any]) -> dict[str, Any]:
    'The evidence as it stood at the end of one past working session.'

    through = str(record["through_day"])
    context = stream.context()
    context["as_of"] = str(record["date"])
    context["window"]["last_day"] = through
    context["intake_counters"] = [
        row for row in context["intake_counters"] if row["day"] <= through
    ]
    return context


def _record_ledger(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = starting_ledger()["entries"]
    keep = {str(item) for item in record.get("receipts", ())}
    return [dict(entry) for entry in held if str(entry["receipt_id"]) in keep]


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    stream = workload.current()
    context = stream.context()
    entries, error = live_ledger(root)
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
            f"The {context['deployment']} triage deployment, its review terms and the "
            "working records on file."
        ),
        "measurements": {
            "deployment": context["deployment"],
            "site": context["site"],
            "window": context["window"],
            "as_of": context["as_of"],
            "intake": context["intake"],
            "review": context["review"],
            "model": {
                "model_id": context["model"]["model_id"],
                "features": context["model"]["features"],
                "threshold": context["model"]["threshold"],
                "fit_manifest": context["model"]["fit_manifest"],
            },
            "units_spent": world.units_spent(entries),
            "units_left": world.units_left(stream, entries),
            "reviews_on_the_ledger": [_receipt_summary(entry) for entry in entries],
            "ledger": error or "reads back in order",
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def public_replay(artifact_dir: Path, record_path: Path) -> Mapping[str, Any]:
    "Run the notebook the way that past session's author ran it."

    record = _record(record_path)
    stream = workload.current()
    context = snapshot(stream, record)
    entries = _record_ledger(record)
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
        "evidence_through": record.get("through_day"),
        "intake_counters": context["intake_counters"],
        "reviews_on_the_ledger": [_receipt_summary(entry) for entry in entries],
        "units_spent": world.units_spent(entries),
    }
    if not run.get("ok"):
        return {
            "summary": f"The {record.get('record_id')} session could not run this notebook.",
            "measurements": {"record": Path(record_path).name,
                             "deployment": context["deployment"]},
            "public": {"session": session, "console_error": run.get("error"),
                       "diagnostic": run.get("diagnostic")},
        }
    results = list(run.get("results", ()))
    return {
        "summary": f"The {record.get('record_id')} session ran against this notebook.",
        "measurements": {
            "record": Path(record_path).name,
            "deployment": context["deployment"],
            "window": context["window"],
            "units_spent": world.units_spent(entries),
        },
        "public": {
            "session": session,
            "report_returned": results[0] if results else None,
            "next_collection_returned": results[1] if len(results) > 1 else None,
            "stdout": run.get("stdout"),
        },
    }


def run_review(
    artifact_dir: Path,
    site: Any,
    channel: Any,
    rows: Any,
    receipt_id: Any,
    low: Any = None,
    high: Any = None,
) -> Mapping[str, Any]:
    return world.collect(
        Path(artifact_dir), workload.current(), site, channel, rows, receipt_id, low, high
    )
