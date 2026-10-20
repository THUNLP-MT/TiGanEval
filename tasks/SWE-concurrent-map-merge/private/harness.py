'Deterministic, sandboxed measurement of one whiteboard session.'

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tiganeval.taskkit import (
    CANDIDATE_FAILURE, AnalysisCache, SandboxedProject, artifact_hash)

from .workload import build_session, resolve


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("board/merge.py", "board/helpers.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES, prefix="tiganeval-board-merge-", timeout=60.0,
)


PRIVATE_SESSION = "weekly-session"


PUBLIC_RECORDS: tuple[str, ...] = (
    "whole-room-reconnect", "handover-after-signal-loss",
    "field-cleared-while-offline", "queue-retry-storm",
)

BUCKETS: Mapping[str, str] = {
    "convergent_board_state": "convergence_failures",
    "causal_edit_precedence": "precedence_failures",
    "clear_scope_preserves_unseen_edits": "clear_failures",
    "state_vector_matches_what_it_holds": "vector_failures",
    "merge_account_matches_card": "account_failures",
}

_MISSING = object()
_CACHE = AnalysisCache()


def _contract() -> Any:
    from ..workspace.board import contract

    return contract


def _person(client: Any) -> str:
    'How the owner names one of the people in the session.'

    return str(client).title()


QUOTED_LIMIT = 120


def _quoted(text: Any) -> str:
    'One line of what the owner is reading, bounded and stripped of newlines.'

    body = " ".join(str(text).split())
    return body if len(body) <= QUOTED_LIMIT else body[: QUOTED_LIMIT - 1] + "…"


def _readable_value(value: Any) -> str:
    'How the owner would say a stored value out loud.'

    if value is _MISSING or value is None:
        return "nothing at all"
    if isinstance(value, Mapping):
        return f"a link to {value.get('link')}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _failure(kind: str, laptop: str, **fields: Any) -> dict[str, Any]:
    record = {"kind": kind, "laptop": laptop, **fields}
    return {
        name: _quoted(value) if isinstance(value, str) else value
        for name, value in record.items()
    }


def _first_difference(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[str, str, Any, Any] | None:
    'The first card and field two boards disagree about.'

    for card in sorted(set(left).union(right)):
        one_card, other_card = dict(left.get(card, {})), dict(right.get(card, {}))
        for field in sorted(set(one_card).union(other_card)):
            one, other = one_card.get(field, _MISSING), other_card.get(field, _MISSING)
            if one != other:
                return card, field, one, other
    return None


def _stub_analysis(error: str) -> dict[str, Any]:
    'The measurement to report when the merge could not be run at all.'

    failure = _failure(CANDIDATE_FAILURE, "meera-desk", error=str(error).strip())
    analysis: dict[str, Any] = {"harness_error": str(error), "replicas": []}
    for bucket in BUCKETS.values():
        analysis[bucket] = [dict(failure)]
    return analysis


def _trusted_observation(raw: Any) -> dict[str, Any]:
    "Validate candidate output with the task's host-side contract copy."

    if not isinstance(raw, Mapping):
        raise TypeError("a replica observation must be a mapping")
    contract = _contract()
    snapshot = contract.require_snapshot(raw.get("snapshot"))
    return {
        "packet": [str(item) for item in raw.get("packet", ())],
        "repeat_of_held_ops": bool(raw.get("repeat_of_held_ops", False)),
        "snapshot": snapshot,
        "digest": contract.digest_of_board(snapshot),
        "state_vector": contract.require_vector(raw.get("state_vector")),
        "account": [dict(entry) for entry in contract.require_account(raw.get("account"))],
    }


def _trusted_outcome(outcome: Mapping[str, Any]) -> dict[str, Any]:
    'Move validation and board fingerprints outside candidate control.'

    clean: dict[str, Any] = {"ok": bool(outcome.get("ok")), "replicas": {}}
    for name, raw_record in dict(outcome.get("replicas", {})).items():
        record = dict(raw_record)
        checked = {
            "error": record.get("error"),
            "deliveries": [],
            "delivered": [str(item) for item in record.get("delivered", ())],
            "catch_up": record.get("catch_up"),
            "final": None,
        }
        try:
            checked["deliveries"] = [
                _trusted_observation(observation)
                for observation in record.get("deliveries", ())
            ]
            if checked["error"] is None and record.get("final") is not None:
                checked["final"] = _trusted_observation(record["final"])
        except (TypeError, ValueError, KeyError) as exc:
            checked["error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        clean["replicas"][str(name)] = checked
    return clean


def _analyse(candidate: Mapping[str, Any], session: Mapping[str, Any]) -> dict[str, Any]:
    contract = _contract()
    ops = {contract.op_id(op): dict(op) for op in session["ops"]}
    convergence: list[dict[str, Any]] = []
    precedence: list[dict[str, Any]] = []
    clears: list[dict[str, Any]] = []
    vectors: list[dict[str, Any]] = []
    accounts: list[dict[str, Any]] = []
    prefix_states: list[tuple[str, frozenset[str], dict[str, Any]]] = []

    records = {
        str(name): dict(record)
        for name, record in dict(candidate.get("replicas", {})).items()
    }
    healthy: dict[str, dict[str, Any]] = {}
    for name in sorted(records):
        record = records[name]
        error = record.get("error")
        if error or not record.get("final"):
            failure = _failure(
                "sync_stopped_with_an_error",
                name,
                error=str(error or "the copy returned nothing at the end of the session"),
                packets_taken=len(list(record.get("deliveries", ()))),
            )
            for bucket in (convergence, precedence, clears, vectors, accounts):
                bucket.append(dict(failure))
        else:
            healthy[name] = record

    for name, record in healthy.items():
        delivered = [str(item) for item in record.get("delivered", ())]
        final = dict(record["final"])
        snapshot = dict(final.get("snapshot", {}))
        account = [dict(entry) for entry in final.get("account", ())]
        prefix_delivered: list[str] = []
        for observation in record.get("deliveries", ()):
            observation = dict(observation)
            for item in observation.get("packet", ()):
                identifier = str(item)
                if identifier not in prefix_delivered:
                    prefix_delivered.append(identifier)
            prefix_snapshot = dict(observation.get("snapshot", {}))
            prefix_resolution = resolve([ops[item] for item in prefix_delivered])
            _judge_account(
                contract,
                name,
                prefix_snapshot,
                prefix_resolution,
                [dict(entry) for entry in observation.get("account", ())],
                ops,
                prefix_delivered,
                accounts,
            )
            if not _dependency_closed(contract, prefix_delivered, ops):
                continue
            _judge_fields(
                contract, name, prefix_snapshot, prefix_resolution, precedence, clears
            )
            prefix_states.append((name, frozenset(prefix_delivered), prefix_snapshot))
        resolution = resolve([ops[item] for item in delivered if item in ops])
        _judge_fields(contract, name, snapshot, resolution, precedence, clears)
        _judge_vector(contract, name, record, delivered, vectors)
        _judge_account(contract, name, snapshot, resolution, account, ops, delivered, accounts)
        _judge_repeats(name, record, convergence)
    _judge_prefix_convergence(prefix_states, convergence)
    _judge_convergence(healthy, convergence)

    return {
        "convergence_failures": convergence,
        "precedence_failures": precedence,
        "clear_failures": clears,
        "vector_failures": vectors,
        "account_failures": accounts,
        "replicas": sorted(records),
    }


def _dependency_closed(
    contract: Any,
    identifiers: Sequence[str],
    ops: Mapping[str, Mapping[str, Any]],
) -> bool:
    "Whether every delivered operation's declared dependencies were delivered."

    given = set(identifiers)
    return all(
        contract.covered_ids(ops[identifier]["deps"]).issubset(given)
        for identifier in identifiers
        if identifier in ops
    )


def _judge_fields(
    contract: Any,
    name: str,
    snapshot: Mapping[str, Any],
    resolution: Mapping[tuple[str, str], Mapping[str, Any]],
    precedence: list[dict[str, Any]],
    clears: list[dict[str, Any]],
) -> None:
    'What each card field shows, against what the session leaves in play.'

    op_id = contract.op_id
    for card, field in sorted(resolution):
        entry = resolution[(card, field)]
        shown = dict(snapshot.get(card, {})).get(field, _MISSING)
        maximal, live = list(entry["maximal"]), list(entry["live"])
        where = {"card_title": card, "card_field": field}
        if shown is _MISSING:
            if not maximal:
                continue
            best = maximal[0]
            if entry["clears"]:
                clears.append(_failure(
                    "clear_removed_an_edit_its_author_never_saw", name, **where,
                    lost_value=_readable_value(best.get("value")),
                    lost_editor=_person(best["client"]),
                    clearing_editor=_person(entry["clears"][0]["client"]),
                ))
            else:
                precedence.append(_failure(
                    "card_field_shows_no_value", name, **where,
                    value_that_should_show=_readable_value(best.get("value")),
                ))
            continue
        matches = [edit for edit in entry["edits"] if edit.get("value") == shown]
        if not matches:
            precedence.append(_failure(
                "card_field_shows_an_unknown_value", name, **where,
                value_shown=_readable_value(shown),
            ))
            continue
        shown_ids = {op_id(edit) for edit in matches}
        if shown_ids.intersection(op_id(edit) for edit in maximal):
            continue
        if shown_ids.intersection(op_id(edit) for edit in live):
            on_top = next(
                (edit for edit in maximal if contract.happens_before(matches[0], edit)),
                maximal[0] if maximal else matches[0],
            )
            precedence.append(_failure(
                "replaced_value_came_back", name, **where,
                value_shown=_readable_value(shown),
                value_written_on_top=_readable_value(on_top.get("value")),
            ))
        else:
            clears.append(_failure(
                "cleared_field_still_shows_a_value", name, **where,
                value_still_showing=_readable_value(shown),
            ))
    for card in sorted(snapshot):
        for field in sorted(dict(snapshot[card])):
            if (card, field) not in resolution:
                precedence.append(_failure(
                    "card_field_shows_an_unknown_value", name,
                    card_title=card, card_field=field,
                    value_shown=_readable_value(dict(snapshot[card])[field]),
                ))


def _judge_vector(
    contract: Any,
    name: str,
    record: Mapping[str, Any],
    delivered: Sequence[str],
    vectors: list[dict[str, Any]],
) -> None:
    'What the copy tells the service it holds, against what it was handed.'

    def overclaims(vector: Mapping[str, Any], held: Sequence[str], packet: int) -> bool:
        claimed = contract.covered_ids(vector)
        extra = sorted(claimed.difference(held))
        if not extra:
            return False
        vectors.append(_failure(
            "laptop_claims_edits_it_does_not_have", name,
            claimed_edit=extra[0],
            editor=_person(contract.split_id(extra[0])[0]),
            packet_number=packet,
            edits_it_claims=len(claimed),
            edits_it_was_given=len(held),
        ))
        return True

    def underclaims(vector: Mapping[str, Any], held: Sequence[str]) -> bool:
        honest = contract.contiguous_vector(held)
        short = sorted(
            client
            for client, seq in honest.items()
            if int(vector.get(client, 0)) < int(seq)
        )
        if not short:
            return False
        vectors.append(_failure(
            "laptop_asks_for_the_whole_session_again", name,
            editor=_person(short[0]),
            edits_held=len(held),
            edits_it_admits_to=len(contract.covered_ids(vector)),
        ))
        return True

    held: list[str] = []
    observations = list(record.get("deliveries", ()))
    for index, observation in enumerate(observations, start=1):
        for item in observation.get("packet", ()):
            if str(item) not in held:
                held.append(str(item))
        vector = dict(observation.get("state_vector", {}))
        if overclaims(vector, held, index) or underclaims(vector, held):
            return
    final_vector = dict(record["final"].get("state_vector", {}))
    if overclaims(final_vector, delivered, len(observations) + 1):
        return
    underclaims(final_vector, delivered)


def _judge_account(
    contract: Any,
    name: str,
    snapshot: Mapping[str, Any],
    resolution: Mapping[tuple[str, str], Mapping[str, Any]],
    account: Sequence[Mapping[str, Any]],
    ops: Mapping[str, Mapping[str, Any]],
    delivered: Sequence[str],
    problems: list[dict[str, Any]],
) -> None:
    'The account and the card have to be two views of the same merge.'

    settled_ops = {
        str(entry["op"]) for entry in account if str(entry["disposition"]) != "pending"
    }
    listed = {str(entry["op"]) for entry in account}
    for identifier in delivered:
        if identifier in listed:
            continue
        op = dict(ops.get(identifier, {}))
        problems.append(_failure(
            "operation_missing_from_the_account", name,
            missing_operation=identifier,
            editor=_person(op.get("client", "")),
            card_title=str(op.get("card", "")),
            card_field=str(op.get("field", "")),
            entries_listed=len(account),
            operations_handed=len(delivered),
        ))
        break

    given = set(delivered)
    for entry in account:
        identifier = str(entry["op"])
        if identifier in given:
            continue
        problems.append(_failure(
            "account_lists_an_operation_never_handed", name,
            unexpected_operation=identifier,
            listed_as=str(entry["disposition"]),
            entries_listed=len(account),
            operations_handed=len(delivered),
        ))
        break

    entries_by_id = {str(entry["op"]): entry for entry in account}
    for identifier in delivered:
        op = dict(ops.get(identifier, {}))
        missing = sorted(contract.covered_ids(op.get("deps", {})).difference(given))
        entry = entries_by_id.get(identifier)
        if not missing or entry is None:
            continue
        if str(entry["disposition"]) == "pending" and entry.get("by") is None:
            continue
        problems.append(_failure(
            "waiting_operation_not_pending", name,
            operation=identifier,
            missing_dependency=missing[0],
            card_title=str(op.get("card", "")),
            card_field=str(op.get("field", "")),
            listed_as=str(entry["disposition"]),
        ))
        break

    counts: dict[str, int] = {}
    for entry in account:
        counts[str(entry["op"])] = counts.get(str(entry["op"]), 0) + 1
    for identifier in sorted(counts):
        if counts[identifier] > 1:
            problems.append(_failure(
                "edit_listed_twice_in_the_account", name,
                repeated_edit=identifier,
                times_listed=counts[identifier],
                editor=_person(dict(ops.get(identifier, {})).get("client", "")),
            ))
            break

    for entry in account:
        identifier = str(entry["op"])
        if identifier not in given:
            continue
        op = dict(ops.get(identifier, {}))
        if (
            str(entry["card"]) == str(op.get("card", ""))
            and str(entry["field"]) == str(op.get("field", ""))
        ):
            continue
        problems.append(_failure(
            "account_places_operation_on_wrong_field", name,
            operation=identifier,
            listed_card=str(entry["card"]),
            listed_field=str(entry["field"]),
            actual_card=str(op.get("card", "")),
            actual_field=str(op.get("field", "")),
        ))
        break

    for entry in account:
        identifier = str(entry["op"])
        if identifier not in given or str(entry["disposition"]) != "pending":
            continue
        op = dict(ops.get(identifier, {}))
        if not contract.covered_ids(op.get("deps", {})).issubset(given):
            continue
        problems.append(_failure(
            "settled_operation_left_pending", name,
            operation=identifier,
            card_title=str(op.get("card", "")),
            card_field=str(op.get("field", "")),
        ))
        break

    def readable_for(card: str, field: str) -> list[Mapping[str, Any]]:
        return [
            entry
            for entry in account
            if str(entry["card"]) == card
            and str(entry["field"]) == field
            and str(entry["disposition"]) == "readable"
        ]

    fields = set(resolution).union(
        (card, field) for card in snapshot for field in dict(snapshot[card])
    )
    for card, field in sorted(fields):
        shown = dict(snapshot.get(card, {})).get(field, _MISSING)
        readable = readable_for(card, field)
        named = (
            dict(ops.get(str(readable[0]["op"]), {})).get("value", _MISSING)
            if len(readable) == 1
            else _MISSING
        )
        if len(readable) == 1 and shown is not _MISSING and named == shown:
            continue
        if not readable and shown is _MISSING:
            continue
        problems.append(_failure(
            "account_names_a_value_the_card_does_not_show", name,
            card_title=card, card_field=field,
            account_says=(
                _readable_value(named)
                if len(readable) == 1
                else ("nothing at all" if not readable else f"{len(readable)} different values")
            ),
            card_shows=_readable_value(shown),
        ))
        break

    for entry in account:
        identifier, disposition = str(entry["op"]), str(entry["disposition"])
        if disposition == "pending":
            if entry.get("by") is not None:
                problems.append(_failure(
                    "account_blames_an_edit_that_did_not_replace_it", name,
                    edit_named=identifier,
                    blamed_edit=str(entry["by"]),
                    card_title=str(entry["card"]),
                    card_field=str(entry["field"]),
                    listed_as=disposition,
                ))
                break
            continue
        op = dict(ops.get(identifier, {}))
        blamed = entry.get("by")
        other = dict(ops.get(str(blamed), {})) if blamed else {}
        same_field = (
            str(blamed) in given
            and str(other.get("card")) == str(entry["card"])
            and str(other.get("field")) == str(entry["field"])
        )
        if disposition == "applied":
            wrong = str(op.get("kind")) != "clear" or blamed is not None
        elif disposition == "readable":
            wrong = str(op.get("kind")) != "edit" or blamed is not None
        elif disposition == "removed":
            wrong = (
                str(op.get("kind")) != "edit"
                or str(other.get("kind")) != "clear"
                or not same_field
                or not contract.dominates(other.get("deps", {}), identifier)
            )
        else:
            winner = readable_for(str(entry["card"]), str(entry["field"]))


            key = (str(op.get("card", "")), str(op.get("field", "")))
            cleared_by = dict(dict(resolution.get(key, {})).get("removed", {})).get(
                identifier
            )
            wrong = (
                str(op.get("kind")) != "edit"
                or str(other.get("kind")) != "edit"
                or (cleared_by is not None and cleared_by in settled_ops)
                or not same_field
                or not (
                    (len(winner) == 1 and str(winner[0]["op"]) == str(blamed))
                    or contract.happens_before(op, other)
                )
            )
        if wrong:
            problems.append(_failure(
                "account_blames_an_edit_that_did_not_replace_it", name,
                edit_named=identifier,
                blamed_edit=str(blamed) if blamed else "nothing at all",
                card_title=str(entry["card"]),
                card_field=str(entry["field"]),
                listed_as=disposition,
            ))
            break


def _judge_repeats(
    name: str, record: Mapping[str, Any], convergence: list[dict[str, Any]]
) -> None:
    'A packet the copy already holds must not change what it shows.'

    observations = list(record.get("deliveries", ()))
    for index in range(1, len(observations)):
        current, previous = dict(observations[index]), dict(observations[index - 1])
        if not current.get("repeat_of_held_ops"):
            continue
        if str(current.get("digest")) == str(previous.get("digest")):
            continue
        difference = _first_difference(
            dict(previous.get("snapshot", {})), dict(current.get("snapshot", {}))
        )
        card, field, before, after = difference or ("", "", _MISSING, _MISSING)
        convergence.append(_failure(
            "redelivery_changed_the_card", name,
            card_title=card, card_field=field,
            value_before=_readable_value(before),
            value_after=_readable_value(after),
        ))
        break


def _judge_prefix_convergence(
    states: Sequence[tuple[str, frozenset[str], Mapping[str, Any]]],
    convergence: list[dict[str, Any]],
) -> None:
    'Copies observed with the same dependency-closed prefix must read alike.'

    groups: dict[frozenset[str], list[tuple[str, Mapping[str, Any]]]] = {}
    for name, identifiers, snapshot in states:
        groups.setdefault(identifiers, []).append((name, snapshot))
    for identifiers in sorted(groups, key=lambda item: sorted(item)):
        copies = sorted(groups[identifiers], key=lambda item: item[0])
        if len(copies) < 2:
            continue
        left_name, left = copies[0]
        for other_name, right in copies[1:]:
            difference = _first_difference(left, right)
            if difference is None:
                continue
            card, field, one, two = difference
            convergence.append(_failure(
                "laptops_show_different_cards", left_name,
                other_laptop=other_name, card_title=card, card_field=field,
                one_value=_readable_value(one),
                other_value=_readable_value(two),
            ))
            return


def _judge_convergence(
    healthy: Mapping[str, Mapping[str, Any]], convergence: list[dict[str, Any]]
) -> None:
    'Copies that ended the session holding the same operations must read alike.'

    groups: dict[frozenset[str], list[str]] = {}
    for name, record in healthy.items():
        key = frozenset(str(item) for item in record.get("delivered", ()))
        groups.setdefault(key, []).append(name)
    for key in sorted(groups, key=lambda item: sorted(item)):
        names = sorted(groups[key])
        if len(names) < 2:
            continue
        left = dict(dict(healthy[names[0]]["final"]).get("snapshot", {}))
        for other in names[1:]:
            right = dict(dict(healthy[other]["final"]).get("snapshot", {}))
            difference = _first_difference(left, right)
            if difference is None:
                continue
            card, field, one, two = difference
            convergence.append(_failure(
                "laptops_show_different_cards", names[0],
                other_laptop=other, card_title=card, card_field=field,
                one_value=_readable_value(one),
                other_value=_readable_value(two),
            ))
            return


_PROCESS_DEATH_PREFIXES = ("candidate process exited", "candidate returned")


def _reportable_error(error: str) -> str:
    'The failure text the owner reads off a replay that produced no session.'

    text = str(error).strip()
    if text.startswith(_PROCESS_DEATH_PREFIXES):
        return "the client stopped before it opened a single card"
    return text


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private session once against this workspace and measure it.'

    def compute() -> Mapping[str, Any]:
        session = build_session(PRIVATE_SESSION)
        outcome = PROJECT.invoke(artifact_dir, session)
        if not outcome.get("ok"):
            analysis = _stub_analysis(
                _reportable_error(str(outcome.get("error", "the merge could not be run")))
            )
        else:
            analysis = _analyse(_trusted_outcome(outcome), session)
        return {
            **analysis,
            "case": {
                "session": PRIVATE_SESSION,
                "operations": len(session["ops"]),
                "copies": len(session["replicas"]),
            },
        }

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    records = sorted((Path(artifact_dir) / "project_records").glob("*.json"))
    return {
        "summary": "The whiteboard workspace and the sessions support kept are available.",
        "measurements": {
            "workspace_hash": artifact_hash(artifact_dir),
            "project_records": [f"project_records/{path.name}" for path in records],
            "dispositions_the_account_may_use": list(_contract().DISPOSITIONS),
            "editable_files": list(EDITABLE_FILES),
        },
        "observed": {},
    }


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    record_path = Path(specification)
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    record_id = str(raw.get("record_id", record_path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    session = build_session(record_id)
    outcome = PROJECT.invoke(artifact_dir, session)
    measurements: dict[str, Any] = {
        "record_id": record_id,
        "support_note": str(raw.get("support_note", raw.get("scene", ""))),
        "operations_in_the_session": [dict(op) for op in session["ops"]],
        "delivery_programme": {
            name: list(plan["deliveries"]) for name, plan in session["replicas"].items()
        },
        "catch_up_pairs": list(session["catch_up"]),
    }
    if not outcome.get("ok"):
        return {
            "summary": "The recorded session could not be run against this workspace.",
            "measurements": measurements,
            "observed": {"execution_error": outcome.get("error", "unknown failure")},
        }
    outcome = _trusted_outcome(outcome)
    timeline: dict[str, Any] = {}
    for name, record in dict(outcome.get("replicas", {})).items():
        record = dict(record)
        final = dict(record.get("final") or {})
        timeline[str(name)] = {
            "error": record.get("error"),
            "packets": [
                {
                    "packet": list(observation.get("packet", ())),
                    "every_op_already_held": observation.get("repeat_of_held_ops"),
                    "state_vector_after": observation.get("state_vector"),
                    "board_digest_after": observation.get("digest"),
                    "account_entries": len(list(observation.get("account", ()))),
                    "pending_entries": sum(
                        1
                        for entry in observation.get("account", ())
                        if str(dict(entry).get("disposition")) == "pending"
                    ),
                }
                for observation in record.get("deliveries", ())
            ],
            "catch_up": record.get("catch_up"),
            "operations_it_ended_up_with": list(record.get("delivered", ())),
            "board_at_the_end": final.get("snapshot"),
            "board_digest_at_the_end": final.get("digest"),
            "state_vector_at_the_end": final.get("state_vector"),
            "merge_account_at_the_end": final.get("account"),
        }
    return {
        "summary": "The recorded session ran against this workspace.",
        "measurements": measurements,
        "observed": {"copies": timeline},
    }
