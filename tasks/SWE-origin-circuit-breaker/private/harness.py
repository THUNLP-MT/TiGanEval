'Deterministic, sandboxed analysis of one gateway workspace.'

from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import (
    AnalysisCache,
    SandboxedProject,
    artifact_hash,
    failed_analysis,
)

from .workload import (
    BILLING, CATALOG, FEED, HEALTHY_ORIGINS, LEDGER, LOOKUP, MESH, NOTIFY,
    PAIR_HUB, PARCEL_HUB, PICK_HUB, PRICING, SCHEME_CLEAR, TRACKING, WAREHOUSE,
    build_program, client_configs, origin_key,
)


TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("gateway/breaker.py", "gateway/support.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT,
    driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES,
    prefix="tiganeval-gateway-",
)


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release"}


PUBLIC_RECORDS: Mapping[str, str] = {
    "checkout-outage": "checkout",
    "fleet-audit": "fleet",
    "ledger-retry-window": "ledger",
    "recovery-morning": "recovery",
    "overnight-reroute": "reroute",
}

BUCKETS: Mapping[str, str] = {
    "shared_origin_isolation": "isolation_failures",
    "logical_call_accounting": "accounting_failures",
    "half_open_admission": "admission_failures",
    "outcome_classification": "classification_failures",
    "blocked_call_inertness": "inertness_failures",
}

_CACHE = AnalysisCache()
_PROTOCOL: Any = None


def reference_protocol() -> Any:
    "The frozen `gateway/protocol.py`, loaded from the project's own tree."

    global _PROTOCOL
    if _PROTOCOL is None:
        path = TASK_ROOT / "workspace" / "gateway" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_gateway_protocol_reference", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the project contract at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PROTOCOL = module
    return _PROTOCOL


def _phases(program: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(op["label"]): str(op.get("phase", ""))
        for op in program.get("operations", ())
        if str(op.get("op")) == "start"
    }


def _origins(program: Mapping[str, Any]) -> dict[str, str]:
    "The origin each call reaches, from the contract's own resolver."

    protocol = reference_protocol()
    configs = client_configs(program)
    origins: dict[str, str] = {}
    for op in program.get("operations", ()):
        if str(op.get("op")) != "start":
            continue
        base = configs.get(str(op["client"]), {}).get("base_url")
        request = protocol.Request(target=str(op["target"]), base_url=base)
        origins[str(op["label"])] = protocol.resolve_origin(request)
    return origins


def _clients(program: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(op["label"]): str(op["client"])
        for op in program.get("operations", ())
        if str(op.get("op")) == "start"
    }


def _calls(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    phases, origins, clients = _phases(program), _origins(program), _clients(program)
    rows: dict[str, dict[str, Any]] = {}
    for entry in dict(candidate.get("calls", {})).values():
        label = str(entry.get("label"))
        rows[label] = {
            **dict(entry),
            "phase": phases.get(label, ""),
            "origin": origins.get(label, ""),
            "client": clients.get(label, ""),
        }
    return rows


def _attempts(candidate: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in candidate.get("transport", ()):
        if isinstance(entry, Mapping):
            rows[str(entry.get("label"))].append(dict(entry))
    return rows


def _started_at(candidate: Mapping[str, Any], label: str) -> float:
    for record in candidate.get("operations", ()):
        if str(record.get("op")) == "start" and str(record.get("label")) == label:
            return float(record.get("clock_ms", 0.0))
    return 0.0


def _last_answer_before(
    candidate: Mapping[str, Any], origin: str, moment: float
) -> float | None:
    latest: float | None = None
    for entry in candidate.get("transport", ()):
        if str(entry.get("origin")) != origin:
            continue
        finished = float(entry.get("finished_at_ms", 0.0))
        if finished <= moment and (latest is None or finished > latest):
            latest = finished
    return latest


def _ms(value: Any) -> float | int:
    'A clock reading as the console prints it: whole milliseconds where it can.'

    number = round(float(value), 3)
    return int(number) if number == int(number) else number


class Review:
    'Everything the five checks read from one run of the traffic.'

    def __init__(self, candidate: Mapping[str, Any], program: Mapping[str, Any]):
        self.candidate, self.program = candidate, program
        self.calls = _calls(candidate, program)
        self.attempts = _attempts(candidate)

    def blocked(self, label: str) -> bool:
        return str(dict(self.calls.get(label, {})).get("outcome")) == "blocked"

    def sent(self, label: str) -> int:
        return len(self.attempts.get(label, ()))

    def wave(self, prefix: str) -> int:
        'How many attempts the calls whose label starts with `prefix` made.'

        return sum(len(rows) for label, rows in self.attempts.items()
                   if label.startswith(prefix))

    def setting(self, client: str, field: str, default: Any) -> Any:
        return client_configs(self.program).get(client, {}).get(field, default)

    def in_phase(self, phase: str) -> list[tuple[str, dict[str, Any]]]:
        return [item for item in sorted(self.calls.items()) if item[1]["phase"] == phase]

    def waited(self, label: str, origin: str) -> float | int:
        "The gap between that origin's last answer and this call being made."

        started = _started_at(self.candidate, label)
        last = _last_answer_before(self.candidate, origin, started)
        return _ms(started - float(last)) if last is not None else 0

    def calls_to(self, phase: str, origin: str, besides: str) -> int:
        return sum(1 for label, row in self.calls.items()
                   if row["phase"] == phase and row["origin"] == origin and label != besides)


def _fail(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _isolation_failures(review: Review) -> list[dict[str, Any]]:
    'One health map, keyed by the origin a request actually reaches.'

    failures = [
        _fail("healthy_origin_refused", origin=str(row["origin"]), label=label,
              client=str(row["client"]))
        for label, row in review.in_phase("topology")
        if row["origin"] in HEALTHY_ORIGINS and str(row.get("outcome")) == "blocked"
    ]
    threshold = int(review.setting("edge", "threshold", 5))
    billing, warehouse = origin_key(BILLING), origin_key(WAREHOUSE)
    if not review.blocked("charge-after-five"):
        failures.append(_fail(
            "failed_origin_still_called", origin=billing, label="charge-after-five",
            failures_before=review.calls_to("topology", billing, "charge-after-five"),
            threshold=threshold))
    if not review.blocked("stock-after-five"):
        callers = {str(row["client"]) for label, row in review.in_phase("topology")
                   if row["origin"] == warehouse and label != "stock-after-five"}
        failures.append(_fail(
            "origin_state_split_across_callers", origin=warehouse, label="stock-after-five",
            callers=len(callers), threshold=threshold,
            failures_before=review.calls_to("topology", warehouse, "stock-after-five")))
    if not review.sent("scheme-clear-after-five"):
        failures.append(_fail(
            "scheme_origin_collapsed", origin=origin_key(SCHEME_CLEAR),
            label="scheme-clear-after-five", failing_scheme="https",
            healthy_scheme="http"))
    return failures


def _accounting_failures(review: Review) -> list[dict[str, Any]]:
    "One settlement per logical call, dated at that call's last attempt."

    failures: list[dict[str, Any]] = []
    ledger = origin_key(LEDGER)
    threshold = int(review.setting("batch", "threshold", 5))
    cooldown = _ms(review.setting("batch", "cooldown_ms", 30000.0))
    if review.blocked("post-after-two"):
        failures.append(_fail(
            "retries_counted_as_failures", origin=ledger, label="post-after-two",
            logical_failures=2, threshold=threshold,
            attempts_so_far=sum(review.sent(f"post-{index}") for index in (1, 2))))
    if not review.blocked("post-after-five"):
        failures.append(_fail(
            "logical_failures_not_counted", origin=ledger, label="post-after-five",
            logical_failures=5, threshold=threshold))
    if not review.blocked("post-just-inside"):
        failures.append(_fail(
            "probe_left_before_cooldown", origin=ledger, label="post-just-inside",
            waited_ms=review.waited("post-just-inside", ledger), cooldown_ms=cooldown))
    return failures


def _admission_failures(review: Review) -> list[dict[str, Any]]:
    'How many calls are let through while an origin is being tried.'

    failures: list[dict[str, Any]] = []
    limit = int(review.setting("pickers", "half_open_max", 1))
    burst = review.wave("pick-wave-")
    if burst > limit:
        failures.append(_fail(
            "probe_flood", origin=origin_key(PICK_HUB), label="pick-wave-1",
            probes_sent=burst, half_open_max=limit))
    failures.extend(
        _fail("retry_took_a_second_slot", origin=str(row["origin"]), label=label,
              half_open_max=int(review.setting(str(row["client"]), "half_open_max", 1)),
              attempts_made=review.sent(label))
        for label, row in review.in_phase("recovery")
        if str(row.get("outcome")) == "blocked" and review.sent(label)
    )
    parcel = origin_key(PARCEL_HUB)
    if not review.sent("parcel-after-wait"):
        failures.append(_fail(
            "probe_slot_leaked", origin=parcel, label="parcel-after-wait",
            waited_ms=review.waited("parcel-after-wait", parcel),
            cooldown_ms=_ms(review.setting("parcels", "cooldown_ms", 10000.0))))
    pair_labels = ("pair-wave-1", "pair-wave-2")
    admitted = sum(bool(review.sent(label)) for label in pair_labels)
    pair_limit = int(review.setting("pairs", "half_open_max", 2))
    if admitted < pair_limit:
        failures.append(_fail(
            "available_probe_slot_refused", origin=origin_key(PAIR_HUB),
            label=next(label for label in pair_labels if not review.sent(label)),
            probes_sent=admitted, half_open_max=pair_limit))
    if not review.blocked("pair-wave-3"):
        failures.append(_fail(
            "retry_released_slot_early", origin=origin_key(PAIR_HUB),
            label="pair-wave-3", retrying_call="pair-wave-1",
            half_open_max=pair_limit))
    if not review.sent("feed-after-probe"):
        failures.append(_fail(
            "rejected_probe_slot_leaked", origin=origin_key(FEED),
            label="feed-after-probe", status=404,
            half_open_max=int(review.setting("feed", "half_open_max", 1))))
    return failures


def _classification_failures(review: Review) -> list[dict[str, Any]]:
    'Failures, rejections and successes told apart.'

    failures: list[dict[str, Any]] = []
    if not review.blocked("catalog-after-three"):
        failures.append(_fail(
            "rejection_treated_as_success", origin=origin_key(CATALOG), status=404,
            label="catalog-after-three", failing_calls=3,
            threshold=int(review.setting("catalog", "threshold", 3))))
    if not review.blocked("pricing-after-three"):
        failures.append(_fail(
            "suppressed_error_not_counted", origin=origin_key(PRICING), status=503,
            label="pricing-after-three", failing_calls=3,
            threshold=int(review.setting("pricing", "threshold", 3))))
    if review.blocked("lookup-after-four"):
        failures.append(_fail(
            "rejection_counted_as_failure", origin=origin_key(LOOKUP), status=404,
            label="lookup-after-four", rejections=4))


    if not review.blocked("feed-after-that"):
        failures.append(_fail(
            "rejected_probe_closed_the_circuit", origin=origin_key(FEED), status=404,
            label="feed-probe", threshold=int(review.setting("feed", "threshold", 2)),
            sent_after_probe=review.sent("feed-after-probe") + review.sent("feed-after-that")))
    if not review.blocked("tracking-after-two"):
        failures.append(_fail(
            "transport_error_not_counted", origin=origin_key(TRACKING),
            label="tracking-after-two", failing_calls=2,
            threshold=int(review.setting("tracking", "threshold", 2))))
    if not review.blocked("parcel-inside-new-wait"):
        failures.append(_fail(
            "transform_error_not_counted", origin=origin_key(PARCEL_HUB),
            label="parcel-inside-new-wait",
            waited_ms=review.waited("parcel-inside-new-wait", origin_key(PARCEL_HUB)),
            cooldown_ms=_ms(review.setting("parcels", "cooldown_ms", 10000.0))))
    normal = ("pick-normal-1", "pick-normal-2")
    sent_after_success = sum(bool(review.sent(label)) for label in normal)
    if sent_after_success < len(normal):
        failures.append(_fail(
            "successful_probe_left_half_open", origin=origin_key(PICK_HUB),
            label=next(label for label in normal if not review.sent(label)),
            sent_after_success=sent_after_success, expected_calls=len(normal),
            half_open_max=int(review.setting("pickers", "half_open_max", 1))))
    if not review.sent("pick-after-new-failure"):
        failures.append(_fail(
            "successful_call_did_not_reset_streak", origin=origin_key(PICK_HUB),
            label="pick-after-new-failure", failures_before_success=3,
            threshold=int(review.setting("pickers", "threshold", 3))))
    return failures


def _inertness_failures(review: Review) -> list[dict[str, Any]]:
    'A refused call writes nothing; an unguarded call is left alone.'

    failures: list[dict[str, Any]] = []
    notify = origin_key(NOTIFY)
    cooldown = _ms(review.setting("notify", "cooldown_ms", 20000.0))
    inside = sorted((label for label in review.attempts if label.startswith("notify-inside-")),
                    key=lambda label: int(label.rsplit("-", 1)[1]))
    if inside:
        failures.append(_fail(
            "blocked_call_reached_the_transport", origin=notify, label=inside[0],
            sent_in_window=sum(review.sent(label) for label in inside), cooldown_ms=cooldown))
    if not review.sent("notify-just-outside"):
        failures.append(_fail(
            "blocked_call_refreshed_the_block", origin=notify, label="notify-just-outside",
            waited_ms=review.waited("notify-just-outside", notify), cooldown_ms=cooldown))
    failures.extend(
        _fail("unguarded_call_blocked", origin=str(row["origin"]), label=label,
              client=str(row["client"]))
        for label, row in review.in_phase("block")
        if not row.get("guarded", True) and str(row.get("outcome")) == "blocked"
    )
    if review.blocked("mesh-guarded-1"):
        failures.append(_fail(
            "unguarded_call_counted", origin=origin_key(MESH), label="mesh-guarded-1",
            unguarded_failures=3, threshold=int(review.setting("mesh", "threshold", 2))))
    return failures


def _analyse(candidate: Mapping[str, Any], program: Mapping[str, Any]) -> dict[str, Any]:
    review = Review(candidate, program)
    return {
        "isolation_failures": _isolation_failures(review),
        "accounting_failures": _accounting_failures(review),
        "admission_failures": _admission_failures(review),
        "classification_failures": _classification_failures(review),
        "inertness_failures": _inertness_failures(review),
    }


_RUNNER_PHRASES = (
    "candidate process exited",
    "candidate returned invalid JSON",
    "candidate returned non-object",
)
_TIMEOUT_PHRASE = "project rehearsal exceeded"
_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the console shows when a stretch of traffic did not finish.'

    reported = str(candidate.get("error") or "no output").strip()
    line = reported
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still running after {limit} and the console stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip()
        tail = diagnostic.splitlines()[-1].strip() if diagnostic else ""
        line = tail or "the gateway ended without saying why"
    line = _DIRECTORY_PART.sub("", line)
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        line = "the gateway ended without saying why"
    return f"the gateway stopped part way through the traffic: {line[:200]}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the private traffic against this workspace and bucket what went wrong.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]))
        candidate = PROJECT.invoke(artifact_dir, dict(program))
        if not candidate.get("ok"):
            analysis = dict(
                failed_analysis(_console_error(candidate), tuple(BUCKETS.values()))
            )
            diagnostic = candidate.get("diagnostic")
            if diagnostic:
                analysis["diagnostic"] = str(diagnostic)
        else:
            analysis = _analyse(candidate, program)
        analysis["case"] = {"traffic": "release", "operations": len(program["operations"])}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)


def _record_scene(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("a project record must contain a JSON object")
    return raw


def public_status(artifact_dir: Path) -> Mapping[str, Any]:
    root = Path(artifact_dir)
    records = []
    for path in sorted((root / "project_records").glob("*.json")):
        raw = _record_scene(path)
        record_id = str(raw.get("record_id", path.stem))
        program = build_program(PUBLIC_RECORDS[record_id]) if record_id in PUBLIC_RECORDS else {}
        records.append(
            {
                "record": f"project_records/{path.name}",
                "scene": raw.get("scene"),
                "clients": client_configs(program) if program else {},
                "origins": sorted(dict(program.get("upstreams", {}))),
            }
        )
    return {
        "summary": "The gateway workspace and the stretches of traffic the team replays.",
        "measurements": {
            "workspace_hash": artifact_hash(root),
            "gateway_files": sorted(
                path.relative_to(root).as_posix() for path in (root / "gateway").glob("*.py")
            ),
            "editable_files": list(EDITABLE_FILES),
        },
        "records": records,
    }


def _origin_summary(
    candidate: Mapping[str, Any], calls: Mapping[str, Mapping[str, Any]], program: Mapping[str, Any]
) -> list[dict[str, Any]]:
    'What each origin received, and the wait before the next call reached it.'

    configs = client_configs(program)
    received: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in candidate.get("transport", ()):
        received[str(entry.get("origin"))].append(dict(entry))
    rows = []
    for origin in sorted(set(received) | {row["origin"] for row in calls.values()}):
        entries = sorted(received.get(origin, ()), key=lambda item: float(item["sent_at_ms"]))
        blocked = [
            (label, row)
            for label, row in calls.items()
            if row["origin"] == origin and str(row.get("outcome")) == "blocked"
        ]
        answers: dict[str, int] = defaultdict(int)
        for entry in entries:
            answers["no answer" if entry.get("status") is None else str(entry["status"])] += 1
        row: dict[str, Any] = {
            "origin": origin,
            "attempts_received": len(entries),
            "answers": dict(sorted(answers.items())),
            "calls_the_gateway_refused": len(blocked),
        }
        if blocked:
            first_block = min(_started_at(candidate, label) for label, _ in blocked)
            answered = _last_answer_before(candidate, origin, first_block)
            after = [
                item for item in entries
                if float(item["sent_at_ms"]) >= first_block
                and calls.get(str(item.get("label")), {}).get("guarded", True)
            ]


            refused_by = sorted({str(entry["client"]) for _, entry in blocked})
            waits = sorted(
                {configs.get(name, {}).get("cooldown_ms") for name in refused_by},
                key=lambda value: (value is None, float(value or 0.0)),
            )
            row["refused_by_clients"] = refused_by
            row["cooldown_ms"] = waits[0]
            row["last_answered_at_ms"] = None if answered is None else _ms(answered)
            row["waited_ms_before_a_guarded_call_reached_it"] = (
                _ms(float(after[0]["sent_at_ms"]) - float(answered))
                if after and answered is not None
                else None
            )
        rows.append(row)
    return rows


def _operation_rows(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Every operation the console drove, and what the call it drove ended as.'

    rows: list[dict[str, Any]] = []
    for record in candidate.get("operations", ()):
        row = {
            "label": record.get("label"),
            "operation": record.get("op"),
            "clock_ms": record.get("clock_ms"),
            "completed": bool(record.get("ok")),
            "error": record.get("error"),
        }
        if record.get("client"):
            row["client"] = record["client"]
            row["guarded"] = record.get("guarded")
        state = record.get("state")
        if isinstance(state, Mapping):
            row["call"] = {
                "outcome": state.get("outcome"),
                "status": state.get("status"),
                "attempts_made": state.get("attempts"),
                "finished": state.get("done"),
                "error": state.get("error"),
            }
        rows.append(row)
    return rows


def run_public_rehearsal(artifact_dir: Path, specification: Path) -> Mapping[str, Any]:
    'Replay one recorded stretch of traffic and report the access log.'

    path = Path(specification)
    raw = _record_scene(path)
    record_id = str(raw.get("record_id", path.stem))
    if record_id not in PUBLIC_RECORDS:
        raise ValueError(f"unknown project record: {record_id}")
    program = build_program(PUBLIC_RECORDS[record_id])
    candidate = PROJECT.invoke(Path(artifact_dir), dict(program))
    if not candidate.get("ok"):
        return {
            "summary": f"The {record_id} traffic could not run against this gateway.",
            "measurements": {"record_id": record_id, "scene": raw.get("scene")},
            "public": {
                "execution_error": candidate.get("error", "unknown failure"),
                "diagnostic": candidate.get("diagnostic"),
            },
        }
    calls = _calls(candidate, program)
    return {
        "summary": f"The {record_id} traffic ran against this gateway.",
        "measurements": {
            "record_id": record_id,
            "scene": raw.get("scene"),
            "clients": client_configs(program),
            "operation_count": len(candidate.get("operations", ())),
        },
        "public": {
            "what_the_gateway_did": _operation_rows(candidate),
            "what_left_the_process": list(candidate.get("transport", ())),
            "what_each_origin_received": _origin_summary(candidate, calls, program),
        },
    }
