'Deterministic, sandboxed analysis of one catalogue listing workspace.'

from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import (
    MIXED, NAME_DESC, PRICE_ASC, RESTOCK, build_program, build_restart_program,
    sorts_after)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("listing/pages.py", "listing/shelves.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-listing-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: tuple[str, ...] = (
    "catalogue-sweep", "restock-mid-scroll", "sort-menu-and-retries", "after-the-deploy")


STILL_SCROLLS: Mapping[str, str] = {
    "scroll-price": PRICE_ASC, "scroll-mixed": MIXED,
    "scroll-name": NAME_DESC, "counter": PRICE_ASC}

BUCKETS: Mapping[str, str] = {
    "page_order_matches_catalogue": "order_failures",
    "scroll_delivers_each_row_once": "scroll_failures",
    "cursor_refusal_contract": "refusal_failures",
    "page_boundary_honesty": "boundary_failures",
    "cursor_is_self_contained": "portability_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `listing/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "listing" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_listing_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def settings() -> Any:
    return reference_protocol().load_config(TASK_ROOT / "workspace" / "service.toml")

def _catalogue_order(rows: Sequence[Mapping[str, Any]], order_by: str) -> list[str]:
    'The catalogue in the order a client asked for, as the release orders it.'

    protocol = reference_protocol()
    store = protocol.Store(
        protocol.Item(item_id=str(row["item_id"]),
                      values={key: value for key, value in row.items() if key != "item_id"})
        for row in rows)
    return [item.item_id for item in protocol.list_all(store, order_by)]


class Review:
    'Everything the five checks read from one run of the listing traffic.'

    def __init__(self, runs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]):
        self.pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

        self.rows_at: dict[str, list[dict[str, Any]]] = {}

        self.index_of: dict[str, int] = {}
        self.edit_steps: list[int] = []


        self.portable: list[dict[str, Any]] = []
        for program, candidate in runs:
            catalogues = dict(program.get("catalogues", {}))
            stores: dict[str, list[dict[str, Any]]] = {}
            services: dict[str, str] = {}
            for op, record in zip(program.get("operations", ()),
                                  candidate.get("operations", ())):
                op, record = dict(op), dict(record)
                self.index_of[str(op.get("label"))] = len(self.pairs)
                self.pairs.append((op, record))
                kind = str(op.get("op"))
                store = str(op.get("store", ""))
                if kind in ("add", "remove", "reprice"):
                    self.edit_steps.append(len(self.pairs) - 1)
                if kind == "store":
                    stores[str(op["name"])] = [dict(row)
                                               for row in catalogues[str(op["catalogue"])]]
                elif kind == "service":
                    services[str(op["name"])] = store
                elif kind == "add":
                    stores[store].append(dict(op["row"]))
                elif kind == "remove":
                    stores[store] = [row for row in stores[store]
                                     if str(row["item_id"]) != str(op["item_id"])]
                elif kind == "reprice":
                    for row in stores[store]:
                        if str(row["item_id"]) == str(op["item_id"]):
                            row.update(dict(op["values"]))
                elif kind == "find":
                    self.rows_at[str(op["label"])] = [
                        dict(row) for row in stores[services[str(op["service"])]]]
        self.by_label = {str(record.get("label")): (op, record) for op, record in self.pairs}

    def finds(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        return [(op, record) for op, record in self.pairs if str(op.get("op")) == "find"]

    def served(self, op: Mapping[str, Any], record: Mapping[str, Any]) -> bool:
        'Whether this request came back with a page rather than a refusal.'

        return bool(record.get("ok")) and not record.get("skipped") and not record.get("refused")

    def scroll(self, name: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        rows = [(op, record) for op, record in self.finds() if str(op.get("scroll", "")) == name]
        return sorted(rows, key=lambda pair: int(pair[0].get("position", 0)))

    def delivered(self, name: str) -> list[str]:
        ids: list[str] = []
        for op, record in self.scroll(name):
            if self.served(op, record):
                ids.extend(str(value) for value in record.get("item_ids", ()))
        return ids


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _order_failures(review: Review) -> list[dict[str, Any]]:
    "The pages of one scroll, put end to end, against the catalogue's order."

    failures: list[dict[str, Any]] = []
    for name, order_by in STILL_SCROLLS.items():
        pages = review.scroll(name)
        if not pages:
            continue
        rows = review.rows_at[str(pages[0][0]["label"])]
        expected = _catalogue_order(rows, order_by)
        delivered = review.delivered(name)
        counted = Counter(delivered)
        repeated = [item for item, times in counted.items() if times > 1]
        absent = [item for item in expected if item not in counted]
        if repeated:
            failures.append(_fail(
                "products_repeated_in_the_list", sort=order_by, repeated_item=repeated[0],
                times_delivered=counted[repeated[0]], rows_delivered=len(delivered),
                catalogue_rows=len(expected)))
        elif absent:
            failures.append(_fail(
                "products_missing_from_the_list", sort=order_by, missing_item=absent[0],
                missing_count=len(absent), rows_delivered=len(delivered),
                catalogue_rows=len(expected)))
        elif delivered != expected:
            position = next(index for index in range(len(delivered))
                            if delivered[index] != expected[index])
            failures.append(_fail(
                "list_not_in_the_order_asked_for", sort=order_by, position=position + 1,
                expected_item=expected[position], delivered_item=delivered[position],
                catalogue_rows=len(expected)))
    failures.extend(_window_failures(review))
    failures.extend(_sortless_failures(review))
    return failures


def _sortless_failures(review: Review) -> list[dict[str, Any]]:
    'A request that names no sort has no ordering to be a page of.'

    failures: list[dict[str, Any]] = []
    for op, record in review.finds():
        if op.get("order_by") is not None or op.get("probe"):
            continue
        if record.get("skipped") or record.get("sent_cursor"):
            continue
        if record.get("ok") and record.get("refused"):
            continue
        served = [str(value) for value in record.get("item_ids", ())]
        failures.append(_fail(
            "request_without_a_sort_served", label=str(op["label"]),
            rows_served=int(record.get("served", 0)),
            first_product=served[0] if served else "nothing",
            what_came_back=_what_came_back(record),
            offset_shape=("carried no offset" if op.get("offset") is None
                          else f"carried offset {int(op['offset'])}"),
            catalogue_rows=len(review.rows_at[str(op["label"])])))
    return failures


def _window_failures(review: Review) -> list[dict[str, Any]]:
    'A page the storefront asks for by row count is that window of the list.'

    limit = int(settings().max_page_size)
    failures: list[dict[str, Any]] = []
    for op, record in review.finds():
        offset, order_by = op.get("offset"), op.get("order_by")
        if offset is None or order_by is None or op.get("probe") or op.get("cursor_from"):
            continue
        catalogue = _catalogue_order(review.rows_at[str(op["label"])], str(order_by))
        asked = min(int(record.get("asked_for", 0)), limit)
        window = catalogue[int(offset): int(offset) + asked]
        served = [str(value) for value in record.get("item_ids", ())]
        if review.served(op, record) and served == window:
            continue
        failures.append(_fail(
            "offset_page_served_the_wrong_products", label=str(op["label"]),
            offset_asked_for=int(offset), rows_expected=len(window), rows_served=len(served),
            first_product_expected=window[0] if window else "nothing",
            what_came_back=_what_came_back(record)))
    return failures


def _scroll_failures(review: Review) -> list[dict[str, Any]]:
    'One scroll through a catalogue merchandising is editing under it.'

    pages = review.scroll(RESTOCK)
    if not pages:
        return []
    first, last = str(pages[0][0]["label"]), str(pages[-1][0]["label"])
    opening = {str(row["item_id"]) for row in review.rows_at[first]}
    closing_rows = review.rows_at[last]
    closing = {str(row["item_id"]) for row in closing_rows}
    names: dict[str, str] = {}
    for op, _record in pages:
        for row in review.rows_at[str(op["label"])]:
            names.setdefault(str(row["item_id"]), str(row.get("name", row["item_id"])))
    delivered = review.delivered(RESTOCK)
    counted = Counter(delivered)
    failures: list[dict[str, Any]] = []
    repeated = [item for item, times in counted.items() if times > 1]
    if repeated:
        failures.append(_fail(
            "product_delivered_twice_in_one_scroll", item_id=repeated[0],
            product=names.get(repeated[0], repeated[0]), times_delivered=counted[repeated[0]],
            catalogue_rows=len(closing)))
    throughout = sorted(opening & closing)
    unreached = [item for item in throughout if item not in counted]
    if unreached:
        failures.append(_fail(
            "product_present_throughout_never_reached", item_id=unreached[0],
            product=names.get(unreached[0], unreached[0]), missing_count=len(unreached),
            catalogue_rows=len(closing)))
    for op, _record in review.pairs:
        if not op.get("must_reach"):
            continue
        item_id = str(op["row"]["item_id"])
        if item_id not in counted:
            failures.append(_fail(
                "restocked_product_never_reached", item_id=item_id,
                product=str(op["row"]["name"]), price_cents=int(op["row"]["price_cents"]),
                catalogue_rows=len(closing)))
    return failures


def _boundary_failures(review: Review) -> list[dict[str, Any]]:
    'What a page says about the rows that follow it, at whatever page size.'

    limit = int(settings().max_page_size)
    failures: list[dict[str, Any]] = []
    for op, record in review.finds():
        order_by = op.get("order_by")
        if order_by is None or op.get("probe") or record.get("skipped"):
            continue
        rows = review.rows_at[str(op["label"])]
        served = int(record.get("served", 0)) if review.served(op, record) else 0
        carried = record.get("next_cursor") is not None
        fields = {"label": str(op["label"]), "rows_served": served,
                  "rows_asked_for": int(record.get("asked_for", 0))}


        if not served:
            behind = (0 if record.get("sent_cursor")
                      else max(0, len(rows) - int(op.get("offset") or 0)))
            if behind:
                failures.append(_fail(
                    "list_ended_while_products_remained", rows_left=behind, **fields))
            elif carried and review.served(op, record):
                failures.append(_fail(
                    "continuation_offered_on_a_finished_list", rows_left=0, **fields))
            continue
        if served > limit:
            failures.append(_fail(
                "page_larger_than_the_service_serves", max_page_size=limit, **fields))
            continue
        last = next((row for row in rows
                     if str(row["item_id"]) == str(record["item_ids"][-1])), None)
        if last is None:
            continue
        left = sum(1 for row in rows if sorts_after(row, last, str(order_by)))
        if carried and left == 0:
            failures.append(_fail(
                "continuation_offered_on_a_finished_list", rows_left=0, **fields))
        elif not carried and left:
            failures.append(_fail(
                "list_ended_while_products_remained", rows_left=left, **fields))
        elif left and served < min(int(fields["rows_asked_for"]), limit):
            failures.append(_fail(
                "page_shorter_than_the_size_asked_for", rows_left=left,
                max_page_size=limit, **fields))
    return failures


def _what_came_back(record: Mapping[str, Any]) -> str:
    'What the service handed back, in the words the mobile team would use.'
    if record.get("skipped"):
        return "nothing at all, because the app was never handed a place to carry"
    if not record.get("ok"):
        return "an error out of the service"
    if record.get("refused"):
        return "a refusal that sends the app back to the top of the list"
    served = [str(value) for value in record.get("item_ids", ())]
    if not served:
        return "a page with nothing on it"
    return f"a page of {len(served)} products starting at {served[0]}"


def _refusal_failures(review: Review) -> list[dict[str, Any]]:
    'Tokens this service would not have minted -- and the ones it would.'

    failures: list[dict[str, Any]] = []
    for op, record in review.finds():
        if (not op.get("probe") and op.get("mirror") is None
                and record.get("sent_cursor") and not record.get("skipped")
                and not review.served(op, record)):
            failures.append(_fail(
                "own_cursor_not_honoured", label=str(op["label"]),
                rows_served=int(record.get("served", 0)),
                what_came_back=_what_came_back(record),
                sort_asked_for=str(op.get("order_by") or "no sort at all")))
            continue
        kind = str(op.get("probe", ""))
        if not kind or record.get("skipped"):
            continue
        if record.get("ok") and record.get("refused"):
            continue
        fields: dict[str, Any] = {
            "label": str(op["label"]),
            "rows_served": int(record.get("served", 0)),
            "what_came_back": _what_came_back(record),
            "sort_asked_for": str(op.get("order_by") or "no sort at all"),
        }
        if kind == "cursor_from_another_sort_honoured":
            fields["sort_the_cursor_was_made_under"] = str(op.get("minted_under", PRICE_ASC))
        if kind == "cursor_with_an_offset_served":
            fields["offset_asked_for"] = int(op.get("offset", 0))
        if kind == "edited_cursor_honoured":
            fields["fields_left"] = int(record.get("fields_left", 0))
        failures.append(_fail(kind, **fields))
    return failures


def _portability_failures(review: Review) -> list[dict[str, Any]]:
    'The same token asked of a service that has just been built.'

    failures: list[dict[str, Any]] = []
    asked: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for op, record in review.finds():
        mirror = op.get("mirror")
        if mirror is None:
            continue
        asked.append((op, record))
        pair = review.by_label.get(str(mirror))
        if pair is None or not review.served(*pair):
            continue
        expected = [str(value) for value in pair[1].get("item_ids", ())]
        if not expected:
            continue
        served = [str(value) for value in record.get("item_ids", ())]
        fields = {"label": str(op["label"]), "rows_expected": len(expected),
                  "rows_served": len(served)}
        if record.get("skipped") or not review.served(op, record) or not served:
            failures.append(_fail(
                "cursor_not_recognised_after_a_restart",
                what_came_back=_what_came_back(record),
                refusal_reason=str(record.get("reason") or ""), **fields))
        elif served != expected:
            failures.append(_fail(
                "second_instance_returned_a_different_page",
                first_item_expected=expected[0], first_item_served=served[0], **fields))
        else:
            fields["compared"] = True
            review.portable.append(fields)
    if asked and not review.portable and not failures:
        op, record = asked[0]
        failures.append(_fail(
            "cursor_not_recognised_after_a_restart", label=str(op["label"]),
            rows_expected=0, rows_served=int(record.get("served", 0)),
            what_came_back=_what_came_back(record),
            refusal_reason=str(record.get("reason") or "")))
    return failures


def _analyse(runs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> dict[str, Any]:
    review = Review(runs)
    return {
        "order_failures": _order_failures(review),
        "scroll_failures": _scroll_failures(review),
        "refusal_failures": _refusal_failures(review),
        "boundary_failures": _boundary_failures(review),
        "portability_failures": _portability_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a run of traffic did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE):].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the service ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the service ended without saying why"
    return f"the listing service stopped part way through the traffic: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private listing traffic against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        runs = [(program, candidate)]
        if candidate.get("ok"):
            after = build_restart_program(dict(candidate.get("minted", {})))
            if after["operations"]:
                second = PROJECT.invoke(artifact_dir, dict(after))
                if not second.get("ok"):
                    candidate = second
                else:
                    runs.append((after, second))
        if not candidate.get("ok"):
            analysis = dict(failed_analysis(_console_error(candidate), tuple(BUCKETS.values())))
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(runs)
        analysis["case"] = {"traffic": "release",
                            "requests": sum(1 for op in program["operations"]
                                            if str(op.get("op")) == "find")}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def _scenario_shape(program: Mapping[str, Any]) -> dict[str, Any]:
    finds = [op for op in program.get("operations", ()) if str(op.get("op")) == "find"]
    catalogues = {name: len(rows) for name, rows in program.get("catalogues", {}).items()}
    return {
        "catalogue_rows": catalogues,
        "sorts": sorted({str(op.get("order_by")) for op in finds if op.get("order_by")}),
        "page_sizes": sorted({int(op["limit"]) for op in finds if op.get("limit") is not None}),
        "requests": len(finds),
        "edits_between_requests": sum(
            1 for op in program.get("operations", ())
            if str(op.get("op")) in ("add", "remove", "reprice")),
    }


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    config = settings()
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        shape = _scenario_shape(build_program(record_id)) if record_id in PUBLIC_RECORDS else {}
        records.append({"record": f"project_records/{path.name}", "scene": raw.get("scene"), **shape})
    return {
        "summary": "The listing workspace and the recorded scenarios the team replays.",
        "measurements": {
            "listing_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "listing").glob("*.py")),
            "editable_files": list(EDITABLE_FILES),
            "service_toml": {"default_limit": config.default_limit,
                             "max_page_size": config.max_page_size},
        },
        "records": records,
    }


def _request_rows(review: Review, max_page_size: int) -> list[dict[str, Any]]:
    'Every request the console made and what came back.'

    rows = []
    for op, record in review.pairs:
        kind = str(op.get("op"))
        if kind != "find":
            row: dict[str, Any] = {"step": str(op.get("label")), "operation": kind,
                                   "completed": bool(record.get("ok"))}
            if op.get("item_id") or op.get("row"):
                row["item"] = str(op.get("item_id") or op["row"]["item_id"])
            if record.get("error"):
                row["error"] = record["error"]
            rows.append(row)
            continue
        row = {
            "request": str(op.get("label")),
            "sort": op.get("order_by"),
            "page_size_asked_for": record.get("asked_for", op.get("limit")),
            "offset": op.get("offset"),
            "sent_a_continuation": bool(record.get("sent_cursor")),
            "completed": bool(record.get("ok")),
        }
        if record.get("skipped"):
            row["not_sent"] = str(record.get("note", ""))
        elif record.get("ok"):
            served = list(record.get("item_ids", ()))
            row.update({
                "refused": bool(record.get("refused")),
                "refusal_reason": record.get("reason") or None,
                "rows_served": record.get("served"),
                "max_page_size": max_page_size,
                "carried_a_continuation": record.get("next_cursor") is not None,
                "first_product": served[0] if served else None,
                "last_product": served[-1] if served else None,
                "products": served,
            })
        else:
            row["error"] = record.get("error")
        rows.append(row)
    return rows


def _scroll_rows(review: Review, program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Per scroll, report request counts and raw delivery volume.'

    names: list[str] = []
    for op in program.get("operations", ()):
        name = str(op.get("scroll", ""))
        if name and name not in names:
            names.append(name)
    rows = []
    for name in names:
        pages = review.scroll(name)
        order_by = str(pages[0][0].get("order_by"))
        last = str(pages[-1][0]["label"])
        catalogue = review.rows_at[last]
        delivered = review.delivered(name)
        rows.append({
            "scroll": name,
            "sort": order_by,
            "requests_made": sum(1 for _op, record in pages if not record.get("skipped")),
            "requests_that_carried_a_continuation": sum(
                1 for _op, record in pages if record.get("next_cursor") is not None),
            "requests_that_served_nothing": sum(
                1 for op, record in pages
                if review.served(op, record) and int(record.get("served", 0)) == 0),
            "catalogue_rows_at_the_end": len(catalogue),
            "rows_delivered": len(delivered),
        })
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded scenario and report the request log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(record_id)
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} scenario could not run against this listing service.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {"execution_error": candidate.get("error", "unknown failure"),
                       "diagnostic": candidate.get("diagnostic")},
        }
    config = settings()
    review = Review([(program, candidate)])
    return {
        "summary": f"The {record_id} scenario ran against this listing service.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "default_limit": config.default_limit,
            "max_page_size": config.max_page_size,
            **_scenario_shape(program),
        },
        "public": {
            "what_the_service_did": _request_rows(review, int(config.max_page_size)),
            "how_each_scroll_went": _scroll_rows(review, program),
        },
    }
