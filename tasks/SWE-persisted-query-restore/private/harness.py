'Deterministic, sandboxed review of one Kerbside handset workspace.'

from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import all_slots, build_program


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("handset/persister.py", "handset/adapters.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-handset-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}

BUCKETS: Mapping[str, str] = {
    "restored_screen_fidelity": "fidelity_failures",
    "restore_load_accounting": "accounting_failures",
    "restored_query_quiescence": "quiescence_failures",
    "restore_path_agreement": "agreement_failures",
    "rebuild_freshness_merge": "freshness_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `handset/protocol.py`, loaded from the project's own tree, so     the review reads the app's own rendering rather than a second opinion."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "handset" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_handset_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


_SCREEN_WORDS: Mapping[str, str] = {
    "data": "the list on the screen", "data_updated_at": "the last-updated line",
    "data_update_count": "the update count", "error": "the banner text",
    "error_updated_at": "the banner's own timestamp",
    "error_update_count": "the banner count", "failure_count": "the retry count",
    "failure_reason": "the retry reason", "is_error": "the red banner",
    "is_load_error": "the empty-screen banner",
    "is_refetch_error": "the banner over the list",
    "is_pending": "the still-loading state", "is_fetched": "the loaded-once mark",
    "is_invalidated": "the out-of-date mark",
    "page_cursors": "the Load more position",
    "status": "what the screen calls itself", "fetch_status": "the loading state",
    "spinner": "the spinner",
}


_REPORT_ORDER = (
    "error", "is_error", "failure_reason", "failure_count", "data_updated_at",
    "error_updated_at", "page_cursors", "data", "data_update_count",
    "error_update_count", "is_fetched", "is_invalidated", "is_refetch_error",
    "is_load_error", "is_pending", "status", "fetch_status", "spinner",
)

_SCREEN_ONLY_FIELDS = ("fetch_status", "spinner")


_DERIVED_FIELDS = ("status", "is_error", "is_load_error", "is_refetch_error",
                   "is_pending", "is_fetched")


APP_RAISED = "the_app_fell_over_on_a_screen"


def _plain(value: Any) -> Any:
    'The value as the console wrote it, so a reference compares equal to it.'
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _state_of(saved: Mapping[str, Any]) -> Any:
    return reference_protocol().QueryState(**dict(saved.get("state") or {}))


def _settled(state: Any) -> Any:
    'The saved state as a query a live process can hold.'
    protocol = reference_protocol()
    return replace(
        state,
        fetch_status=protocol.IDLE,
        status=protocol.status_for(state.data, state.error),
    )


def _screen(state: Any) -> dict[str, Any]:
    return _plain(reference_protocol().derive_result(state))


def _difference(
    shown: Mapping[str, Any] | None,
    expected: Mapping[str, Any],
    *,
    ignore: Sequence[str] = (),
    only: Sequence[str] | None = None,
) -> str | None:
    'The first field of the screen that is not what it should be.'

    if shown is None:
        return "data"
    for name in _REPORT_ORDER:
        if name in ignore or name not in expected:
            continue
        if only is not None and name not in only:
            continue
        if shown.get(name) != expected.get(name):
            return name
    return None


def _words(field: str | None) -> str:
    return _SCREEN_WORDS.get(str(field), "the screen")


class Review:
    'Everything the five checks read from one run of a session.'

    def __init__(self, session: Mapping[str, Any], program: Mapping[str, Any]):
        self.session, self.program = session, program
        self.ops = [dict(op) for op in session.get("operations", ())]
        self.totals = dict(session.get("totals", {}))
        self.slots = all_slots(program)

    def by_label(self, label: str) -> dict[str, Any]:
        for op in self.ops:
            if str(op.get("label")) == label:
                return op
        return {}

    def reads(self, phase: str, prefix: str = "") -> list[dict[str, Any]]:
        return [
            op
            for op in self.ops
            if str(op.get("op")) == "read"
            and str(op.get("phase")) == phase
            and str(op.get("label", "")).startswith(prefix)
        ]

    def screen(self, op: Mapping[str, Any]) -> dict[str, Any] | None:
        value = op.get("screen")
        return dict(value) if isinstance(value, Mapping) else None

    def saved(self, key: str) -> Any:
        return _state_of(self.slots[key])

    def depot_calls_for(self, key: str) -> int:
        return sum(1 for row in self.session.get("depot_log", ()) if str(row.get("key")) == key)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _fidelity_failures(review: Review) -> list[dict[str, Any]]:
    'A restored screen is the screen the crew left, into an empty cache.'

    protocol = reference_protocol()
    failures: list[dict[str, Any]] = []
    for op in review.reads("reopen"):
        key = str(op.get("key"))
        saved = review.saved(key)
        expected = _screen(_settled(saved))
        shown = review.screen(op)
        field = _difference(shown, expected, ignore=_SCREEN_ONLY_FIELDS)
        if field is None:
            continue
        shown = shown or {}


        plain = _difference(
            shown,
            expected,
            ignore=(*_SCREEN_ONLY_FIELDS, *_DERIVED_FIELDS, "data_updated_at"),
        )
        named = plain or field
        saved_cursors = expected["page_cursors"]
        record = {
            "key": key,
            "saved_reason": str(saved.failure_reason or saved.error or "none"),
            "saved_failure_count": int(saved.failure_count),
            "saved_at": int(expected["data_updated_at"]),
            "shown_at": int(shown.get("data_updated_at", 0)),
            "saved_pages": len(saved_cursors),
            "shown_pages": len(shown.get("page_cursors") or ()),
            "field": named,
            "field_name": _words(named),
        }
        should_show_banner = protocol.status_for(saved.data, saved.error) == protocol.ERROR
        shows_banner = bool(shown.get("is_error"))
        if saved.error is not None and shown.get("error") is None:
            kind = "restored_error_dropped"
        elif shows_banner and not should_show_banner:
            kind = "restored_status_contradicts_the_screen"
        elif should_show_banner and not shows_banner:
            kind = "restored_banner_is_missing"
        elif record["shown_pages"] != record["saved_pages"]:
            kind = "restored_pages_dropped"
        elif record["shown_at"] != record["saved_at"]:
            kind = "restored_screen_is_a_fresh_load"
        else:
            kind = "restored_screen_is_not_the_copy_the_crew_left"
        failures.append(_fail(kind, **record))


    before_op = review.by_label("roundtrip-before")
    after_op = review.by_label("roundtrip-after")
    before = review.screen(before_op)
    after = review.screen(after_op)
    if before_op or after_op:
        field = _difference(after, before or {})
        if field is not None:
            failures.append(
                _fail(
                    "saved_screen_did_not_survive_restart",
                    key=str(after_op.get("key") or before_op.get("key") or ""),
                    field=field,
                    field_name=_words(field),
                    before_at=int((before or {}).get("data_updated_at", 0)),
                    after_at=int((after or {}).get("data_updated_at", 0)),
                )
            )
    return failures


def _accounting_failures(review: Review) -> list[dict[str, Any]]:
    'One completed load per load that reached the depot, and none for a restore.'

    failures: list[dict[str, Any]] = []
    totals = {
        "loads_total": int(review.totals.get("loads_completed", 0)),
        "depot_total": int(review.totals.get("depot_calls", 0)),
        "restored_total": int(review.totals.get("restored", 0)),
    }
    for op in review.ops:
        loads = int(op.get("loads_completed_here", 0))
        calls = int(op.get("depot_calls_here", 0))
        if loads == calls:
            continue
        kind = "restore_counted_as_a_load" if loads > calls else "completed_load_went_missing"
        failures.append(
            _fail(
                kind,
                key=str(op.get("key", "")),
                op_label=str(op.get("label", "")),
                loads_here=loads,
                depot_here=calls,
                **totals,
            )
        )


    if not failures and totals["loads_total"] != totals["depot_total"]:
        kind = (
            "restore_counted_as_a_load"
            if totals["loads_total"] > totals["depot_total"]
            else "completed_load_went_missing"
        )
        failures.append(
            _fail(
                kind,
                key="",
                op_label="session total",
                loads_here=totals["loads_total"],
                depot_here=totals["depot_total"],
                **totals,
            )
        )
    return failures


def _quiescence_failures(review: Review) -> list[dict[str, Any]]:
    'Every restore path leaves nothing running, whatever the writer caught.'

    failures: list[dict[str, Any]] = []
    rows = [(str(op.get("key")), review.screen(op)) for op in review.reads("writer")]
    for key, shown in rows:
        saved = review.saved(key)
        record = {
            "key": key,
            "saved_fetch_state": str(saved.fetch_status),
            "shown_fetch_status": str((shown or {}).get("fetch_status", "missing")),
            "other_key": key,
            "other_fetch_state": str(saved.fetch_status),
            "field": "fetch_status",
            "field_name": _words("fetch_status"),
            "depot_calls_for_key": review.depot_calls_for(key),
        }
        if shown is None or bool(shown.get("spinner")):
            failures.append(_fail("restored_screen_shows_a_load_that_is_not_running", **record))
    if failures:
        return failures


    for op in review.ops:
        if str(op.get("op")) != "rebuild":
            continue
        after = op.get("queries_after")
        if not isinstance(after, Mapping):
            continue
        for key, raw_state in after.items():
            if str(key) not in review.slots or not isinstance(raw_state, Mapping):
                continue
            shown_fetch_status = str(raw_state.get("fetch_status", "missing"))
            if shown_fetch_status == reference_protocol().IDLE:
                continue
            failures.append(
                _fail(
                    "rebuild_left_a_finished_load_running",
                    key=str(key),
                    saved_fetch_state=str(review.saved(str(key)).fetch_status),
                    shown_fetch_status=shown_fetch_status,
                    other_key=str(key),
                    other_fetch_state=shown_fetch_status,
                    field="fetch_status",
                    field_name=_words("fetch_status"),
                    depot_calls_for_key=review.depot_calls_for(str(key)),
                )
            )
    if failures:
        return failures

    for index in range(1, len(rows)):
        first_key, first = rows[0]
        other_key, other = rows[index]
        field = _difference(other, first or {})
        if field is None:
            continue
        failures.append(
            _fail(
                "restored_screen_varies_with_what_the_writer_caught",
                key=first_key,
                saved_fetch_state=str(review.saved(first_key).fetch_status),
                shown_fetch_status=str((first or {}).get("fetch_status", "missing")),
                other_key=other_key,
                other_fetch_state=str(review.saved(other_key).fetch_status),
                field=field,
                field_name=_words(field),
                depot_calls_for_key=review.depot_calls_for(other_key),
            )
        )
    return failures


def _agreement_failures(review: Review) -> list[dict[str, Any]]:
    'The two ways into a screen put the same screen up.'

    failures: list[dict[str, Any]] = []
    cold = {str(op.get("key")): review.screen(op) for op in review.reads("twoways", "twoways-cold")}
    link = {str(op.get("key")): review.screen(op) for op in review.reads("twoways", "twoways-link")}
    for key in sorted(link):
        after_boot, after_link = cold.get(key), link[key]
        field = _difference(after_boot, after_link or {})
        if field is None:
            continue
        saved = review.saved(key)
        record = {
            "key": key,
            "saved_reason": str(saved.failure_reason or saved.error or "none"),
            "field": field,
            "field_name": _words(field),
            "boot_shows_banner": bool((after_boot or {}).get("is_error")),
            "link_shows_banner": bool((after_link or {}).get("is_error")),
        }


        if (
            after_boot is not None
            and after_boot.get("error") is None
            and (after_link or {}).get("error") is not None
        ):
            failures.append(_fail("rebuild_dropped_the_error", **record))
        else:
            failures.append(_fail("the_two_ways_in_disagree", **record))
    return failures


_DATA_FIELDS = ("data", "data_updated_at", "data_update_count", "is_invalidated")
_ERROR_FIELDS = (
    "error", "error_updated_at", "error_update_count", "failure_count", "failure_reason",
)


def _freshness_failures(review: Review) -> list[dict[str, Any]]:
    'A rebuild over a live query moves neither stamp backwards.'

    protocol = reference_protocol()
    rebuild = review.by_label("rebuild-race")
    live_states = dict(rebuild.get("queries_before") or {})
    failures: list[dict[str, Any]] = []
    for op in review.reads("race"):
        key = str(op.get("key"))
        saved = review.saved(key)
        live_raw = live_states.get(key)
        live = None if live_raw is None else protocol.QueryState(**dict(live_raw))
        rows = saved if live is None or int(saved.data_updated_at) > int(live.data_updated_at) else live
        trouble = (
            saved
            if live is None or int(saved.error_updated_at) > int(live.error_updated_at)
            else live
        )
        expected = _screen(
            _settled(
                protocol.QueryState(
                    data=rows.data,
                    data_updated_at=int(rows.data_updated_at),
                    data_update_count=int(rows.data_update_count),
                    is_invalidated=bool(rows.is_invalidated),
                    error=trouble.error,
                    error_updated_at=int(trouble.error_updated_at),
                    error_update_count=int(trouble.error_update_count),
                    failure_count=int(trouble.failure_count),
                    failure_reason=trouble.failure_reason,
                )
            )
        )
        shown = review.screen(op)
        field = _difference(shown, expected, ignore=_SCREEN_ONLY_FIELDS)
        if field is None:
            continue


        rows_field = _difference(shown, expected, only=_DATA_FIELDS)
        trouble_field = _difference(shown, expected, only=_ERROR_FIELDS)
        field = rows_field or trouble_field or field
        shown = shown or {}
        record = {
            "key": key,
            "live_at": 0 if live is None else int(live.data_updated_at),
            "saved_at": int(saved.data_updated_at),
            "shown_at": int(shown.get("data_updated_at", 0)),
            "saved_reason": str(trouble.failure_reason or trouble.error or "none"),
            "saved_error_at": int(saved.error_updated_at),
            "live_error_at": 0 if live is None else int(live.error_updated_at),
            "shown_error_at": int(shown.get("error_updated_at", 0)),
            "field": field,
            "field_name": _words(field),
        }
        went_backwards = live is not None and record["shown_at"] < record["live_at"]
        banner_gone = (
            trouble is saved
            and expected["error"] is not None
            and shown.get("error") is None
        )
        no_bar_over_the_message = (
            expected["error"] is not None and not bool(shown.get("is_error"))
        )
        if rows_field is not None and went_backwards:
            failures.append(_fail("rebuild_overwrote_newer_rows", **record))
        elif rows_field is None and trouble_field is not None and banner_gone:
            failures.append(_fail("rebuild_skipped_the_saved_error", **record))
        elif rows_field is None and trouble_field is None and no_bar_over_the_message:
            failures.append(_fail("rebuild_merged_without_the_banner", **record))
        else:
            failures.append(_fail("rebuild_left_the_screen_between_the_two", **record))
    return failures


def _raised_failures(review: Review) -> list[dict[str, Any]]:
    'Screens the app raised on instead of putting them up.'

    failures: list[dict[str, Any]] = []
    for op in review.ops:
        reported = str(op.get("error") or "").strip()
        if not reported:
            continue
        key = str(op.get("key") or "")
        failures.append(
            _fail(
                APP_RAISED,
                error=_clean_line(reported),
                key=key,
                where=key or "the rebuild the app runs when it starts",
                op_label=str(op.get("label", "")),
                phase=str(op.get("phase", "")),
            )
        )
    return failures


def _analyse(session: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(session, program)
    raised = _raised_failures(review)
    if raised:
        return {bucket: list(raised) for bucket in BUCKETS.values()}
    return {
        "fidelity_failures": _fidelity_failures(review),
        "accounting_failures": _accounting_failures(review),
        "quiescence_failures": _quiescence_failures(review),
        "agreement_failures": _agreement_failures(review),
        "freshness_failures": _freshness_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _clean_line(reported: str) -> str:
    'One console line as the owner reads it back: the throwaway directory the     bench handset ran the copy in stripped out, and a line carrying a word she     would not use replaced rather than quoted..'

    line = _DIRECTORY_PART.sub("", str(reported).strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the app ended without saying why"
    return line[:200] or "the app ended without saying why"


def _console_error(session: Mapping[str, Any]) -> str:
    'The one line the console shows when a session did not finish.'

    reported = str(session.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(session.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the app ended without saying why"
    return f"the app stopped part way through the session: {_clean_line(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private session against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        session = PROJECT.invoke(artifact_dir, dict(program))
        if not session.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(session), tuple(BUCKETS.values()))
            )
            diagnostic = session.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(session, program)
        analysis["case"] = {
            "session": "release",
            "operations": len(program["operations"]),
        }
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
