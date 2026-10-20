'Deterministic, sandboxed measurement of one hour of the summary relay.'

from __future__ import annotations

from itertools import permutations
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE,
    AnalysisCache,
    SandboxedProject,
)

from ..workspace.relay.protocol import (
    STATISTIC_FIELDS,
    USAGE_FIELDS,
    body_digest,
    reference_summary,
    summary_scope,
)
from .workload import (
    ARRIVAL_VARIANTS,
    PUBLIC_DIRECTORY,
    build_programme,
    variant_of,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("relay/dispatcher.py", "relay/sharing.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-relay-",
    timeout=60.0,
)


PRIVATE_PROFILE = "release"
BASE_VARIANT = ARRIVAL_VARIANTS[0]


PUBLIC_RECORDS: tuple[str, ...] = (
    "invoice-run-spike",
    "two-desks-one-contract",
    "backend-outage-window",
    "handover-drop",
)

BUCKETS: Mapping[str, str] = {
    "delivered_response_equivalence": "response_failures",
    "every_call_answered_once": "settlement_failures",
    "upstream_execution_conservation": "execution_failures",
    "usage_ledger_completeness": "ledger_failures",
    "outcome_independent_of_arrival_order": "order_failures",
}

_CACHE = AnalysisCache()


def _expectations(programme: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    directory = dict(programme["directory"])
    calls: dict[str, Any] = {}
    episodes: list[dict[str, Any]] = []
    open_index: dict[tuple[str, str], int] = {}
    last_close: dict[tuple[str, str], str] = {}

    for window in programme["windows"]:
        label = str(window["label"])
        for raw in window["events"]:
            event = dict(raw)
            kind = str(event["type"])
            if kind == "call":
                principal = str(event["principal"])
                document = str(event["document_id"])


                held = directory.get(principal)
                known = held is not None
                desk = dict(held) if known else {"tenant": "", "clearance": "", "documents": ()}
                scope = summary_scope(desk["tenant"], desk["clearance"]) if known else ""
                authorized = known and document in tuple(desk["documents"])
                record: dict[str, Any] = {
                    "call_id": str(event["call_id"]),
                    "window": label,
                    "principal": principal,
                    "document_id": document,
                    "request_id": str(event["request_id"]),
                    "tenant": str(desk["tenant"]),
                    "scope": scope,
                    "known_to_the_directory": known,
                    "authorized": authorized,
                    "hung_up": False,
                    "episode": None,
                }
                if authorized:
                    key = (document, scope)
                    if key not in open_index:
                        open_index[key] = len(episodes)
                        episodes.append(
                            {
                                "document_id": document,
                                "scope": scope,
                                "window": label,
                                "calls": [],
                                "closed_by": None,
                                "follows_a_failure": last_close.get(key) == "fail",
                            }
                        )
                    episodes[open_index[key]]["calls"].append(record["call_id"])
                    record["episode"] = open_index[key]
                calls[record["call_id"]] = record
            elif kind == "abandon":
                calls[str(event["call_id"])]["hung_up"] = True
            elif kind in ("finish", "fail", "drain"):
                closing = "fail" if kind == "fail" else "finish"
                for key, index in open_index.items():
                    episodes[index]["closed_by"] = closing
                    last_close[key] = closing
                open_index.clear()

    for record in calls.values():
        if not record["authorized"]:
            record["expected"] = {"kind": "refused"}
        elif record["episode"] is None:
            record["expected"] = {"kind": "none"}
        elif episodes[record["episode"]]["closed_by"] == "fail":
            record["expected"] = {"kind": "refused"}
        else:
            pieces = reference_summary(record["document_id"], record["scope"])
            record["expected"] = {
                "kind": "summary",
                "digest": body_digest(pieces),
                "pieces": len(pieces),
                "first_piece": pieces[0],
            }
    return calls, episodes


def _scope_digests(document_id: str, directory: Mapping[str, Any]) -> dict[str, str]:
    scopes = {
        summary_scope(desk["tenant"], desk["clearance"]) for desk in directory.values()
    }
    return {
        body_digest(reference_summary(document_id, scope)): scope for scope in sorted(scopes)
    }


def _answers(report: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {str(row["call_id"]): [dict(item) for item in row["answers"]] for row in report["calls"]}


def _outcome_key(answers: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    return tuple(
        (str(item.get("kind")), str(item.get("digest", "")), str(item.get("reason", "")))
        for item in answers
    )


def _response_failures(report, calls, directory) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    digests: dict[str, dict[str, str]] = {}
    for call_id, answers in _answers(report).items():
        record = calls.get(call_id)
        if record is None or not answers:
            continue
        answer = answers[0]
        expected = record["expected"]
        document = record["document_id"]
        common = {"call_id": call_id, "window": record["window"],
                  "principal": record["principal"], "document_id": document}
        if str(answer["kind"]) == "summary" and expected["kind"] == "refused":
            if not record["authorized"]:
                failures.append({"kind": "refusal_not_delivered_to_unauthorized_caller", **common})
            else:
                failures.append({
                    "kind": "summary_after_the_rendering_failed", **common,
                    "pieces_delivered": int(answer.get("pieces", 0)),
                })
            continue
        if expected["kind"] != "summary":
            continue
        if str(answer["kind"]) == "refused":
            failures.append({
                "kind": "refusal_instead_of_the_summary", **common,


                "reason": str(answer.get("reason") or "no reason given"),
            })
            continue
        if str(answer.get("digest")) == expected["digest"]:
            continue
        if document not in digests:
            digests[document] = _scope_digests(document, directory)
        other = digests[document].get(str(answer.get("digest")))
        if other is not None and other != record["scope"]:
            failures.append({
                "kind": "response_from_another_scope", **common,
                "scope_the_summary_came_from": other,
                "scope_the_caller_reads_in": record["scope"],
            })
            continue
        pieces = int(answer.get("pieces", 0))
        whole = reference_summary(document, record["scope"])
        opening = str(answer.get("first_piece"))
        suffix = whole[len(whole) - pieces:] if 0 < pieces < len(whole) else ()
        if (
            suffix
            and opening == suffix[0]
            and str(answer.get("digest")) == body_digest(suffix)
        ):
            failures.append({
                "kind": "response_missing_leading_chunks", **common,
                "pieces_delivered": pieces,
                "pieces_in_the_summary": len(whole),
            })
            continue
        if (
            pieces == len(whole)
            and opening in whole
            and opening != whole[0]
            and any(
                body_digest(order) == str(answer.get("digest"))
                for order in permutations(whole)
                if order != tuple(whole)
            )
        ):


            failures.append({
                "kind": "response_pieces_out_of_order", **common,
                "opening_piece_position": whole.index(opening) + 1,
                "pieces_in_the_summary": len(whole),
            })
            continue
        failures.append({
            "kind": "response_did_not_match_reference", **common,
            "pieces_delivered": pieces,
            "pieces_in_the_summary": len(whole),
        })
    return failures


def _settlement_failures(report, calls, episodes, directory) -> list[dict[str, Any]]:
    answers = _answers(report)
    hung_up_windows = {
        record["window"] for record in calls.values() if record["hung_up"]
    }
    failed_episodes: set[int] = set()
    for raw in report["executions"]:
        row = dict(raw)
        if str(row.get("state")) != "failed":
            continue
        record = calls.get(str(row.get("started_by")))
        index = record["episode"] if record is not None else None
        if index is None:
            continue
        episode = episodes[index]
        desk = directory.get(str(row.get("rendered_for")))
        rendered_scope = (
            summary_scope(desk["tenant"], desk["clearance"])
            if desk is not None else ""
        )
        if (
            str(row.get("document_id")) == episode["document_id"]
            and rendered_scope == episode["scope"]
        ):
            failed_episodes.add(index)
    unanswered: list[dict[str, Any]] = []
    doubled: list[dict[str, Any]] = []
    for call_id, record in calls.items():
        given = answers.get(call_id, [])
        if len(given) > 1:
            doubled.append({
                "kind": "call_answered_twice", "call_id": call_id,
                "window": record["window"], "document_id": record["document_id"],
                "answers": len(given),
            })
            continue
        if given or record["hung_up"]:
            continue
        if not record["known_to_the_directory"]:


            kind = "desk_the_directory_dropped_left_unanswered"
        elif record["episode"] in failed_episodes:
            kind = "waiters_unresolved_after_the_backend_failed"
        elif record["window"] in hung_up_windows:
            kind = "waiters_unresolved_after_the_first_caller_left"
        else:
            kind = "call_left_unanswered"
        unanswered.append({
            "kind": kind, "call_id": call_id, "window": record["window"],
            "document_id": record["document_id"], "principal": record["principal"],
        })
    total = len(unanswered)
    for failure in unanswered:
        failure["callers_left_waiting"] = total
    return unanswered + doubled


def _execution_failures(report, calls, episodes, directory) -> list[dict[str, Any]]:
    counts = [0] * len(episodes)
    strays: dict[tuple[str, str], int] = {}
    wrong_request: list[dict[str, Any]] = []
    for raw in report["executions"]:
        row = dict(raw)
        record = calls.get(str(row.get("started_by")))
        index = record["episode"] if record is not None else None
        if index is None:
            key = (str(row.get("document_id")), str(row.get("window")))
            strays[key] = strays.get(key, 0) + 1
        else:
            episode = episodes[index]
            rendered_for = str(row.get("rendered_for"))
            desk = directory.get(rendered_for)
            rendered_scope = (
                summary_scope(desk["tenant"], desk["clearance"])
                if desk is not None else ""
            )
            rendered_document = str(row.get("document_id"))
            if (
                rendered_document != episode["document_id"]
                or rendered_scope != episode["scope"]
            ):
                wrong_request.append({
                    "kind": "upstream_execution_for_the_wrong_request",
                    "window": episode["window"],
                    "started_by": str(row.get("started_by")),
                    "rendered_for": rendered_for,
                    "rendered_document_id": rendered_document,
                    "rendered_scope": rendered_scope,
                    "requested_document_id": episode["document_id"],
                    "requested_scope": episode["scope"],
                })
                continue
            counts[index] += 1
    failures: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes):
        common = {
            "document_id": episode["document_id"],
            "window": episode["window"],
            "callers_in_the_episode": len(episode["calls"]),
        }
        if counts[index] > 1:
            failures.append({"kind": "duplicate_upstream_executions", **common,
                             "executions": counts[index]})
        elif counts[index] == 0:
            kind = (
                "no_execution_after_the_backend_failed"
                if episode["follows_a_failure"]
                else "episode_ran_no_upstream_execution"
            )
            failures.append({"kind": kind, **common})
    for (document, window), count in sorted(strays.items()):


        failures.append({
            "kind": "upstream_execution_without_a_caller", "document_id": document,
            "window": window, "executions": count,
        })
    return wrong_request + failures


def _ledger_failures(report, calls) -> list[dict[str, Any]]:
    answers = _answers(report)
    entries: dict[str, list[Mapping[str, Any]]] = {}
    malformed: list[dict[str, Any]] = []
    for raw in report["usage_entries"]:
        entry = dict(dict(raw).get("entry", {}))
        if set(entry) != set(USAGE_FIELDS):
            malformed.append({
                "kind": "usage_entry_has_wrong_shape",
                "window": str(dict(raw).get("window", "")),
            })
            continue
        entries.setdefault(str(entry["call_id"]), []).append(entry)
    for failure in malformed:
        failure["malformed_entries"] = len(malformed)
    answered = [call_id for call_id, given in answers.items() if given]
    missing: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    wrong_identity: list[dict[str, Any]] = []
    wrong_call: list[dict[str, Any]] = []
    for call_id in sorted(answered):
        record = calls.get(call_id)


        if record is None or not record["known_to_the_directory"]:
            continue
        held = entries.get(call_id, [])
        if not held or any(field not in held[0] for field in USAGE_FIELDS):
            missing.append({
                "kind": "usage_entry_missing_for_an_answered_caller",
                "call_id": call_id, "window": record["window"],
                "principal": record["principal"], "document_id": record["document_id"],
            })
            continue
        if len(held) > 1:
            duplicates.append({
                "kind": "duplicate_usage_entries_for_an_answered_caller",
                "call_id": call_id, "window": record["window"],
                "principal": record["principal"], "document_id": record["document_id"],
                "entries": len(held),
            })
        entry = held[0]
        if (
            str(entry["principal"]) != record["principal"]
            or str(entry["tenant"]) != record["tenant"]
        ):
            wrong_identity.append({
                "kind": "usage_entry_attributed_to_another_caller",
                "call_id": call_id, "window": record["window"],
                "principal_in_the_ledger": str(entry["principal"]),
                "principal_that_was_answered": record["principal"],
                "tenant_in_the_ledger": str(entry["tenant"]),
                "tenant_that_was_answered": record["tenant"],
            })
        elif (
            str(entry["request_id"]) != record["request_id"]
            or str(entry["document_id"]) != record["document_id"]
        ):
            wrong_call.append({
                "kind": "usage_entry_does_not_match_the_call",
                "call_id": call_id, "window": record["window"],
                "principal": record["principal"],
                "request_id_in_the_ledger": str(entry["request_id"]),
                "request_id_that_was_answered": record["request_id"],
                "document_id_in_the_ledger": str(entry["document_id"]),
                "document_id_that_was_answered": record["document_id"],
            })
    for failure in missing:
        failure["callers_answered"] = len(answered)
        failure["ledger_entries"] = sum(len(item) for item in entries.values())


    unearned: list[dict[str, Any]] = []
    for call_id in sorted(entries):
        if answers.get(call_id):
            continue
        record = calls.get(call_id, {})
        entry = entries[call_id][0]
        unearned.append({
            "kind": "usage_entry_for_a_caller_that_was_never_answered",
            "call_id": call_id,
            "window": str(record.get("window", "")),
            "principal": str(record.get("principal") or entry.get("principal") or "unknown"),
            "document_id": str(record.get("document_id") or entry.get("document_id") or ""),
        })
    for failure in unearned:
        failure["entries_without_an_answer"] = len(unearned)


    written: dict[str, set[str]] = {"summary": set(), "refused": set()}
    for call_id in answered:
        record = calls.get(call_id)
        if record is None or not record["known_to_the_directory"]:
            continue
        held = entries.get(call_id, [])
        kind = str(answers[call_id][0].get("kind"))
        if held and kind in written:
            written[kind].add(str(held[0].get("outcome")))
    ambiguous = written["summary"] & written["refused"]
    conflated: list[dict[str, Any]] = []
    for call_id in sorted(answered):
        record = calls.get(call_id)
        held = entries.get(call_id, [])
        if record is None or not held or not record["known_to_the_directory"]:
            continue
        said = str(held[0].get("outcome"))
        if said in ambiguous:
            conflated.append({
                "kind": "usage_entry_does_not_record_the_outcome", "call_id": call_id,
                "window": record["window"], "principal": record["principal"],
                "document_id": record["document_id"], "outcome_in_the_ledger": said,
            })
    for failure in conflated:
        failure["callers_affected"] = len(conflated)
    measured = {
        "calls_accepted": len(report["calls"]),
        "upstream_executions": len(report["executions"]),
        "calls_answered": len(answered),
    }
    reported = dict(report.get("reported_statistics", {}) or {})
    statistics: list[dict[str, Any]] = []
    for field in STATISTIC_FIELDS:
        raw = reported.get(field)
        numeric = isinstance(raw, int) and not isinstance(raw, bool)
        value = int(raw) if numeric else 0
        if not numeric or value != measured[field]:
            statistics.append({
                "kind": "sharing_statistics_do_not_match", "counter": field,
                "reported": value, "measured": measured[field], "window": "",
            })
    return (
        malformed + missing + duplicates + wrong_identity + wrong_call
        + unearned + conflated + statistics
    )


def _order_failures(reports: Mapping[str, Mapping[str, Any]], calls) -> list[dict[str, Any]]:
    base = _answers(reports[BASE_VARIANT])
    failures: list[dict[str, Any]] = []
    for variant, report in sorted(reports.items()):
        if variant == BASE_VARIANT:
            continue
        kind = (
            "outcome_changed_with_the_piece_boundaries"
            if variant == "wider-pieces"
            else "outcome_changed_with_the_arrival_order"
        )
        other = _answers(report)
        for call_id in sorted(calls):
            if _outcome_key(base.get(call_id, [])) == _outcome_key(other.get(call_id, [])):
                continue
            record = calls.get(call_id, {})
            failures.append({
                "kind": kind, "call_id": call_id,
                "window": str(record.get("window", "")),
                "document_id": str(record.get("document_id", "")),
                "principal": str(record.get("principal", "")),
            })
    for failure in failures:
        failure["callers_that_changed"] = len(
            {item["call_id"] for item in failures if item["kind"] == failure["kind"]}
        )
    return failures


def _stub(error: str) -> dict[str, Any]:


    failure = {
        "kind": CANDIDATE_FAILURE,
        "window": "",
        "error": str(error)[:240],
    }
    analysis: dict[str, Any] = {"harness_error": str(error)}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _analyse(outcome: Mapping[str, Any], programme: Mapping[str, Any]) -> dict[str, Any]:
    reports = {str(item.get("variant")): dict(item) for item in outcome.get("reports", ())}
    broken = [item for item in reports.values() if not item.get("ok")]
    missing = [variant for variant in ARRIVAL_VARIANTS if variant not in reports]
    if missing or broken:
        error = str(broken[0].get("error")) if broken else "the relay produced no replay"
        return _stub(error)
    calls, episodes = _expectations(programme)
    base = reports[BASE_VARIANT]
    response_failures: list[dict[str, Any]] = []
    settlement_failures: list[dict[str, Any]] = []
    execution_failures: list[dict[str, Any]] = []
    ledger_failures: list[dict[str, Any]] = []
    relay_errors: list[dict[str, Any]] = []
    for variant in ARRIVAL_VARIANTS:
        variant_programme = variant_of(programme, variant)
        variant_calls, variant_episodes = _expectations(variant_programme)
        directory = dict(variant_programme["directory"])
        report = reports[variant]
        response_failures.extend(_response_failures(report, variant_calls, directory))
        settlement_failures.extend(
            _settlement_failures(report, variant_calls, variant_episodes, directory)
        )
        execution_failures.extend(
            _execution_failures(report, variant_calls, variant_episodes, directory)
        )
        ledger_failures.extend(_ledger_failures(report, variant_calls))
        relay_errors.extend(dict(item) for item in report.get("relay_errors", ()))
    return {
        "response_failures": response_failures,
        "settlement_failures": settlement_failures,
        "execution_failures": execution_failures,
        "ledger_failures": ledger_failures,
        "order_failures": _order_failures(reports, calls),
        "episodes": len(episodes),
        "relay_errors": relay_errors[:6],
    }


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Replay the private hour against this relay once and measure it.'

    def compute() -> Mapping[str, Any]:
        programme = build_programme(PRIVATE_PROFILE)
        payload = {
            "programmes": [variant_of(programme, variant) for variant in ARRIVAL_VARIANTS]
        }
        outcome = PROJECT.invoke(Path(artifact_dir), payload)
        if not outcome.get("ok"):
            analysis = _stub(str(outcome.get("error", "the relay could not be run")))
        else:
            analysis = _analyse(outcome, programme)
        return {
            **analysis,
            "case": {
                "profile": PRIVATE_PROFILE,
                "arrival_orders": len(ARRIVAL_VARIANTS),
                "windows": len(programme["windows"]),
            },
        }

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The relay workspace, the desks it serves, and the recorded windows.",
        "measurements": {


            "project_records": [f"project_records/{path.name}" for path in records],
            "desks_the_relay_serves": {
                principal: {
                    "tenant": desk["tenant"],
                    "clearance": desk["clearance"],
                    "documents_this_desk_may_read": list(desk["documents"]),
                }
                for principal, desk in sorted(PUBLIC_DIRECTORY.items())
            },
        },
        "observed": {},
    }


def _window_totals(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    labels: list[str] = []
    for row in report["calls"]:
        if str(row["window"]) not in labels:
            labels.append(str(row["window"]))
    totals = []
    for label in labels:
        rows = [dict(row) for row in report["calls"] if str(row["window"]) == label]
        entries = [item for item in report["usage_entries"] if str(item["window"]) == label]
        executions = [item for item in report["executions"] if str(item["window"]) == label]
        totals.append({
            "window": label,
            "arrival_order": [str(row["call_id"]) for row in rows],
            "calls_accepted": len(rows),
            "upstream_executions": len(executions),
            "calls_answered_with_a_summary": sum(
                1 for row in rows if any(a["kind"] == "summary" for a in row["answers"])
            ),
            "calls_answered_with_a_refusal": sum(
                1 for row in rows if any(a["kind"] == "refused" for a in row["answers"])
            ),
            "calls_never_answered": sum(1 for row in rows if not row["answers"]),
            "usage_ledger_entries": len(entries),
        })
    return totals


def _caller_row(row: Mapping[str, Any]) -> dict[str, Any]:
    'One caller as the replay reports it.'

    answer = [
        {key: value for key, value in dict(item).items() if key != "first_piece"}
        for item in row["answers"]
    ]
    return {**{key: value for key, value in dict(row).items() if key != "answers"},
            "answers": answer}


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    path = Path(specification)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    programme = build_programme(record_id)
    outcome = PROJECT.invoke(Path(artifact_dir), {"programmes": [programme]})
    if not outcome.get("ok"):
        return {
            "summary": "The recorded window could not be replayed against this relay.",
            "measurements": {"record_id": record_id},
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    report = dict(list(outcome.get("reports", ()))[0])
    if not report.get("ok"):
        return {
            "summary": "The recorded window could not be replayed against this relay.",
            "measurements": {"record_id": record_id},
            "observed": {"execution_error": report.get("error", "unknown failure")},
        }
    return {
        "summary": "The recorded window ran against this relay.",
        "measurements": {
            "record_id": record_id,
            "windows": _window_totals(report),
            "reported_statistics": dict(report.get("reported_statistics", {})),
        },
        "observed": {
            "callers": [_caller_row(row) for row in report["calls"]],
            "backend_executions": [dict(row) for row in report["executions"]],
            "usage_ledger": [dict(item) for item in report["usage_entries"]],
            "relay_errors": list(report.get("relay_errors", ()))[:8],
        },
    }
