'Deterministic, sandboxed review of one ingress control-plane workspace.'

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from tiganeval.registry import FORBIDDEN_VOCABULARY
from tiganeval.taskkit import AnalysisCache, SandboxedProject, failed_analysis

from .workload import PODS, build_program

TASK_ROOT = Path(__file__).resolve().parents[1]
EDITABLE_FILES = ("edge/compile.py", "edge/pin.py")
PROJECT = SandboxedProject(
    task_root=TASK_ROOT, driver=Path(__file__).resolve().with_name("runtime_driver.py"),
    editable_files=EDITABLE_FILES, prefix="tiganeval-edge-")


PRIVATE_CASE: Mapping[str, Any] = {"profile": "release", "scale": 1}


PUBLIC_RECORDS: Mapping[str, Mapping[str, Any]] = {
    "checkout-session-drops": {"profile": "checkout", "scale": 1},
    "controller-restart-resync": {"profile": "resync", "scale": 1},
    "guest-checkout-surge": {"profile": "guest", "scale": 1},
    "reporting-export-window": {"profile": "reporting", "scale": 1}}

BUCKETS: Mapping[str, str] = {
    "merged_plan_matches_the_policies": "merge_failures",
    "each_key_pins_once": "duplicate_failures",
    "pinning_survives_a_repush": "repush_failures",
    "opt_out_clears_inherited_pinning": "opt_out_failures",
    "pin_key_matches_the_reference": "pin_failures"}

_CACHE = AnalysisCache()
_FROZEN: Any = None


def frozen_protocol() -> Any:
    'The edge contract as it ships, loaded from the pristine workspace.'

    global _FROZEN
    if _FROZEN is None:
        path = TASK_ROOT / "workspace" / "edge" / "protocol.py"
        spec = importlib.util.spec_from_file_location("_frozen_edge_protocol", path)
        sys.modules[spec.name] = module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _FROZEN = module
    return _FROZEN


def _entry_key(kind: str, entry: Mapping[str, Any]) -> str:
    protocol = frozen_protocol()
    return protocol.normalise_key(kind, dict(entry).get("name", ""))


def _step_of(kind: str, entry: Mapping[str, Any]) -> Any:
    'One authored entry as the step the proxy should be given.'
    protocol, body = frozen_protocol(), dict(entry)
    common = {"key": str(body.get("name", "")), "stop": bool(body.get("stop", False))}
    if kind == "header":
        common["key"] = protocol.normalise_key("header", body["name"])
        return protocol.Step(kind="header", rewrite=protocol.read_rewrite(body), **common)
    if kind == "cookie":
        return protocol.Step(
            kind="cookie", path=str(body.get("path", "/")),
            ttl=protocol.ttl_seconds(body.get("ttl", 0)),
            flags=tuple(str(flag) for flag in body.get("flags", ()) or ()), **common)
    return protocol.Step(kind=kind, **common)


def reference_plan(documents: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    'The plan these documents compose to, or a refusal.'

    protocol = frozen_protocol()
    policies = [protocol.admit(document) for document in documents]
    if any(policy.disabled for policy in policies):
        return ()
    ordered = sorted(
        ((protocol.CANONICAL_KINDS.index(kind), protocol.rank(policy),
          _entry_key(kind, entry), index, kind, entry)
         for policy in policies for kind, index, entry in policy.entries),
        key=lambda item: item[:4])
    steps: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for *_place, kind, entry in ordered:
        identity = (kind, _entry_key(kind, entry))
        if identity not in seen:
            seen.add(identity)
            steps.append(_step_of(kind, entry))
    plan = tuple(steps)
    protocol.check_plan(plan)
    return plan


def reference_definitions(
    documents: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str], list[tuple[Any, str, Mapping[str, Any]]]]:
    'Every authored definition of each key, best precedence first.'

    protocol = frozen_protocol()
    table: dict[tuple[str, str], list[tuple[Any, str, Mapping[str, Any]]]] = {}
    for document in documents:
        try:
            policy = protocol.admit(document)
        except protocol.EdgeError:
            continue
        for kind, _index, entry in policy.entries:
            table.setdefault((kind, _entry_key(kind, entry)), []).append(
                (protocol.rank(policy), policy.name, entry))
    return {key: sorted(value, key=lambda item: item[0]) for key, value in table.items()}


def reference_parts(request: Any, steps: Sequence[Any], rewrites: Mapping) -> tuple[str, ...]:
    'What this request contributes, walking the plan the build emitted.'

    protocol = frozen_protocol()
    parts: list[str] = []
    for step in steps:
        value = protocol.read_value(request, step)
        if value is None:
            continue
        identity = _identity(step)
        rewrite = rewrites[identity] if identity in rewrites else step.rewrite
        parts.append(protocol.part(step, protocol.apply_rewrite(rewrite, value)))
        if step.stop:
            break
    return tuple(parts)


_DIRECTORY_PART = re.compile(r"/(?:[\w.\-]+/)+")


def _safe_error(text: Any) -> str:
    'One raised line as the push log would show it.'
    line = _DIRECTORY_PART.sub("", str(text or "no message").strip())
    if any(word in line.lower() for word in FORBIDDEN_VOCABULARY):
        return "the push ended without saying why"
    return line[:200]


def _failure(mode: str, **fields: Any) -> dict[str, Any]:
    return {"kind": mode, **fields}


def _rows(step: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    return [dict(item) for item in step.get(field) or ()]


def _step_from_row(row: Mapping[str, Any]) -> Any:
    "One step of a build's plan, back from the JSON the drill box returned."
    protocol, body = frozen_protocol(), dict(row)
    spec = body.get("rewrite")
    return protocol.Step(
        kind=str(body.get("kind", "?")), key=str(body.get("key", "")), ttl=body.get("ttl"),
        rewrite=None if not isinstance(spec, Mapping) else protocol.Rewrite(
            str(spec.get("pattern", "")), str(spec.get("substitution", ""))),
        path=str(body.get("path", "/")), stop=bool(body.get("stop", False)),
        flags=tuple(str(flag) for flag in body.get("flags", ()) or ()))


def plan_view(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    'One readable line per step, for the drill timeline.'
    protocol, view = frozen_protocol(), []
    for body in (dict(row) for row in rows):
        kind = str(body.get("kind", "?"))
        text = f"{kind} {protocol.normalise_key(kind, body.get('key', ''))}".strip()
        if body.get("rewrite"):
            text += f" rewrite={dict(body['rewrite']).get('pattern')}"
        if kind == "cookie":
            text += f" ttl={body.get('ttl')!r} path={body.get('path')}"
            text += (" " + ",".join(str(f) for f in body["flags"])) if body.get("flags") else ""
        view.append(text + (" stop" if body.get("stop") else ""))
    return view


def _rewrite_or_none(entry: Mapping[str, Any]) -> Any:
    protocol = frozen_protocol()
    try:
        return protocol.read_rewrite(entry)
    except protocol.EdgeError:
        return None


def read_steps(
    candidate: Mapping[str, Any], program: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    'One row per drill step, with what the policies say beside each push.'

    protocol = frozen_protocol()
    steps: list[dict[str, Any]] = []
    serving: dict[str, list[dict[str, Any]]] = {}
    rewrites: dict[str, dict[Any, Any]] = {}
    for event, record in zip(program, candidate.get("records", ())):
        step = {**dict(record), "event": dict(event)}
        kind = str(record.get("type"))
        if kind == "push":
            route = str(event["route"]["name"])
            documents = list(event["documents"])
            try:
                step["expected_plan"], step["expected_refusal"] = reference_plan(documents), None
            except protocol.EdgeError as exc:
                step["expected_plan"], step["expected_refusal"] = None, _safe_error(exc)
            step["definitions"] = reference_definitions(documents)
            step["opt_out"] = bool(step["expected_plan"] == () or step["expected_refusal"])
            step["serving_before"] = list(serving.get(route, ()))
            serving[route] = _rows(record, "serving")
            rewrites[route] = {identity: _rewrite_or_none(defined[0][2])
                               for identity, defined in step["definitions"].items()}
        elif kind in {"traffic", "cookies"}:
            route = str(record.get("route", event.get("route", "")))
            step["serving_rows"] = list(serving.get(route, ()))
            step["rewrites"] = dict(rewrites.get(route, {}))
        steps.append(step)
    return steps


def _pushes(steps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in steps if str(step.get("type")) == "push" and step.get("ok")]


def _broken(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'Any drill step the build could not carry out at all.'
    return [_failure("edge_operation_failed", label=str(step.get("label")),
                     route=str(step.get("route", "")), error=_safe_error(step.get("error")))
            for step in steps if not step.get("ok")]


def _collapsed(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    'The emitted plan with repeated keys folded away: what rubric 1 compares.'
    out: list[tuple[str, str]] = []
    for identity in (_identity(_step_from_row(row)) for row in rows):
        if identity not in out:
            out.append(identity)
    return out


def _at(step: Mapping[str, Any]) -> dict[str, str]:
    'Where in the drill a failure was measured.'
    return {"label": str(step.get("label")), "route": str(step.get("route"))}


def _named(identity: tuple[str, str]) -> dict[str, str]:
    "One pin step's kind and key, as the owner would name them."
    return {"pin_kind": identity[0], "key": identity[1] or "the client address"}


def _defined(step: Mapping[str, Any], identity: tuple[str, str]) -> tuple[Any, ...]:
    'Every authored definition of one key on this push, best precedence first.'
    return tuple(dict(step.get("definitions") or {}).get(identity) or ())


def _owner_of(step: Mapping[str, Any], identity: tuple[str, str]) -> str:
    'The policy whose definition of this key should have survived.'
    defined = _defined(step, identity)
    return str(defined[0][1]) if defined else "the attached policies"


def _identity(step: Any) -> tuple[str, str]:
    'The kind and normalised key one step pins on.'
    return (str(step.kind), frozen_protocol().normalise_key(step.kind, step.key))


def _merge_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _pushes(steps):
        if step.get("opt_out"):
            continue
        at = _at(step)
        if not step.get("accepted"):
            failures.append(_failure(
                "plan_refused_by_proxy", **at, refusal=_safe_error(step.get("refusal")),
                still_serving=len(_rows(step, "serving"))))
            continue
        emitted = _collapsed(_rows(step, "plan"))
        wanted = [_identity(item) for item in step["expected_plan"]]
        for identity in wanted:
            if identity not in emitted:
                failures.append(_failure(
                    "inherited_entry_dropped", **at, **_named(identity),
                    policy=_owner_of(step, identity)))
        for identity in emitted:
            if identity not in wanted:
                failures.append(_failure("entry_not_in_any_policy", **at, **_named(identity)))

        shared = [item for item in emitted if item in wanted]
        ordered = [item for item in wanted if item in emitted]
        blocks = [(item[0], _owner_of(step, item)) for item in ordered]
        for position, identity in enumerate(shared):
            if (identity[0], _owner_of(step, identity)) == blocks[position]:
                continue
            failures.append(_failure(
                "entries_out_of_precedence_order", **at, **_named(identity),
                should_follow=ordered[position][1] or "the client address",
                policy=_owner_of(step, identity)))
            break
    return failures


def _ttl_value(value: Any) -> Any:
    'One cookie lifetime in whole seconds, or the value itself when it is not one.'
    protocol = frozen_protocol()
    try:
        return protocol.ttl_seconds(value)
    except protocol.EdgeError:
        return value


def _definition_fields(step: Any) -> tuple[tuple[str, str], ...]:
    'The authored fields the proxy uses for this kind, in comparison order.'

    kind = str(step.kind)
    rewrite = step.rewrite
    fields = [("stop", "yes" if step.stop else "no")]
    if kind == "header":
        fields.append(("rewrite", "none" if rewrite is None else
                       f"{rewrite.pattern} -> {rewrite.substitution}"))
    elif kind == "cookie":
        fields[:0] = [
            ("path", str(step.path)),
            ("lifetime", str(_ttl_value(step.ttl))),
            ("flags", ", ".join(sorted(str(flag) for flag in step.flags)) or "no flags"),
        ]
    return tuple(fields)


def _definition_difference(kept: Any, wanted: Any) -> tuple[str, str]:
    'The first field that tells the definition that survived from the one that should have.'
    for (label, left), (_name, right) in zip(_definition_fields(kept), _definition_fields(wanted)):
        if left != right:
            return (f"{label} {left}", f"{label} {right}")
    return ("what the proxy took", "what the file asks for")


def _lower_definition_owner(
    step: Mapping[str, Any], identity: tuple[str, str], kept: Any,
) -> str | None:
    'Which lower-ranked policy authored the definition that survived, if any.'

    for _rank, name, entry in _defined(step, identity)[1:]:
        authored = _step_of(identity[0], entry)
        if _definition_fields(kept) == _definition_fields(authored):
            return str(name)
    return None


def _duplicate_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for step in _pushes(steps):
        if step.get("opt_out") or not step.get("accepted"):
            continue
        at, rows = _at(step), _rows(step, "plan")
        for expected in step["expected_plan"]:
            identity = _identity(expected)
            matched = [row for row in rows if _identity(_step_from_row(row)) == identity]
            named = _named(identity)
            if len(matched) > 1:
                failures.append(_failure(
                    "key_pins_twice", **at, **named, times=len(matched),
                    spellings=", ".join(str(row.get("key")) for row in matched)))
                continue
            if not matched:
                failures.append(_failure(
                    "key_never_pins", **at, **named, policy=_owner_of(step, identity)))
                continue
            defined, kept = _defined(step, identity), _step_from_row(matched[0])
            if _definition_fields(kept) != _definition_fields(expected):
                carried, asked = _definition_difference(kept, expected)
                lower_owner = _lower_definition_owner(step, identity, kept)
                failures.append(_failure(
                    "lower_precedence_definition_kept" if lower_owner is not None else
                    "authored_definition_changed", **at, **named, kept=carried,
                    wanted=asked, policy=str(defined[0][1]),
                    kept_policy=lower_owner or "no attached policy"))
    return failures


def _first_difference(before: Sequence[str], after: Sequence[str]) -> str:
    pairs = zip(list(before) + [""] * len(after), list(after) + [""] * len(before))
    line = next((right or left for left, right in pairs if left != right), "the whole plan")
    return " ".join(line.split(" ")[:2])


def _repush_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    plans: dict[str, list[dict[str, Any]]] = {}
    pods: dict[str, dict[str, str]] = {}
    for step in steps:
        kind, label = str(step.get("type")), str(step.get("label"))
        if not step.get("ok") or kind not in {"push", "traffic"}:
            continue
        earlier = str(step["event"].get("same_as", ""))
        if kind == "push":
            plans[label] = _rows(step, "serving")
            if not earlier or earlier not in plans:
                continue
            before, after = plan_view(plans[earlier]), plan_view(plans[label])
            if before == after:
                continue
            varies = str(step["event"].get("varies", "reconcile"))
            failures.append(_failure(
                "plan_depends_on_reconcile_order" if varies == "reconcile"
                else "plan_depends_on_authoring_order",
                **_at(step), earlier=earlier, line=_first_difference(before, after),
                plan=" | ".join(after)[:160]))
            continue
        pods[label] = {str(r.get("request")): str(r.get("pod")) for r in _rows(step, "requests")}
        if not earlier or earlier not in pods:
            continue
        moved = [key for key, pod in pods[label].items() if pods[earlier].get(key) != pod]
        if moved:
            failures.append(_failure(
                "shopper_moved_by_repush", **_at(step), earlier=earlier, shopper=str(moved[0]),
                moved=len(moved), total=len(pods[label]), pod=str(pods[label][moved[0]]),
                earlier_pod=str(pods[earlier].get(moved[0], "nowhere"))))
    return failures


def _process_restart_failures(
    before: Mapping[str, Any], after: Mapping[str, Any],
    program: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    'A fresh controller process must compile the same push to the same plan.'

    first = {str(step.get("label")): step for step in read_steps(before, program)
             if str(step.get("type")) == "push" and step.get("ok") and step.get("accepted")}
    failures: list[dict[str, Any]] = []
    for step in read_steps(after, program):
        label = str(step.get("label"))
        if (str(step.get("type")) != "push" or not step.get("ok") or
                not step.get("accepted") or label not in first):
            continue
        earlier = plan_view(_rows(first[label], "plan"))
        current = plan_view(_rows(step, "plan"))
        if earlier != current:
            failures.append(_failure(
                "plan_depends_on_process_start", **_at(step), earlier=label,
                line=_first_difference(earlier, current),
                plan=" | ".join(current)[:160]))
            break
    return failures


def _load_after(steps: Sequence[Mapping[str, Any]], index: int, route: str) -> dict[str, Any]:
    'The pod load of the first traffic on this route after a push.'
    for step in steps[index + 1 :]:
        if str(step.get("type")) == "traffic" and str(step.get("route")) == route:
            load = {str(key): int(n) for key, n in dict(step.get("load") or {}).items()}
            if not load:
                break
            busiest = max(sorted(load), key=lambda pod: load[pod])
            return {"busiest_pod": busiest, "busiest_share": load[busiest],
                    "requests": sum(load.values()), "traffic": str(step.get("label"))}
    return {"busiest_pod": "", "busiest_share": 0, "requests": 0, "traffic": ""}


def _contradictory(step: Mapping[str, Any]) -> str:
    'The document that turns pinning off and also sets a pin.'
    for document in step["event"]["documents"]:
        pins = dict(dict(document).get("pins") or {})
        if pins.get("disable") and len(pins) > 1:
            return str(dict(document).get("name", "?"))
    return "?"


def _opt_out_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        if str(step.get("type")) != "push" or not step.get("ok") or not step.get("opt_out"):
            continue
        serving, measured = _rows(step, "serving"), _load_after(steps, index, str(step.get("route")))
        if step.get("expected_refusal"):
            if not step.get("accepted"):
                if str(step.get("refused_by")) != "plane":
                    failures.append(_failure(
                        "contradictory_policy_reached_proxy", **_at(step),
                        policy=_contradictory(step),
                        refusal=_safe_error(step.get("refusal")), **measured))
                continue
            changed = plan_view(serving) != plan_view(step.get("serving_before") or ())
            failures.append(_failure(
                "contradictory_policy_half_applied" if changed else
                "contradictory_policy_accepted", **_at(step),
                policy=_contradictory(step), **measured))
        elif serving:
            first = _step_from_row(serving[0])
            failures.append(_failure(
                "inherited_pinning_survives_opt_out", **_at(step),
                key=str(first.key) or "the client address", pin_kind=str(first.kind),
                lines=len(serving), **measured))
    return failures


def _ttl_failures(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    'A cookie lifetime that did not reach the proxy in whole seconds.'

    expected_by_key = {_identity(item): item for item in step["expected_plan"]}
    failures: list[dict[str, Any]] = []
    for row in _rows(step, "plan"):
        emitted = _step_from_row(row)
        identity = _identity(emitted)
        wanted = expected_by_key.get(identity)
        if str(emitted.kind) != "cookie" or wanted is None or emitted.ttl == wanted.ttl:
            continue
        if len(_defined(step, identity)) > 1 and _ttl_value(emitted.ttl) != wanted.ttl:
            continue
        failures.append(_failure(
            "cookie_ttl_not_normalised", **_at(step), key=str(emitted.key),
            reported=str(emitted.ttl), expected=str(wanted.ttl)))
    return failures


def _cookie_line_failures(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Set-Cookie output must be the frozen proxy rendering of the served step.'

    protocol = frozen_protocol()
    cookies = [item for item in (_step_from_row(row) for row in step.get("serving_rows") or ())
               if str(item.kind) == "cookie"]
    rendered = _rows(step, "cookie_lines")
    failures: list[dict[str, Any]] = []
    for position in range(max(len(cookies), len(rendered))):
        emitted = cookies[position] if position < len(cookies) else None
        observed = rendered[position] if position < len(rendered) else {}
        if emitted is None:
            expected, key = "no cookie line", str(observed.get("key", "?"))
        else:
            key = str(emitted.key)
            try:
                expected = str(protocol.cookie_line(emitted))
            except protocol.EdgeError:

                continue
        reported = observed.get("line")
        if reported is not None and str(reported) == expected:
            continue
        failures.append(_failure(
            "cookie_line_wrong", **_at(step), key=key,
            reported=str(reported or observed.get("refusal") or "no cookie line"),
            expected=expected))
    return failures


def _routing_failures(step: Mapping[str, Any]) -> list[dict[str, Any]]:
    "The recorded pod must be the frozen ring's answer for the recorded parts."

    protocol = frozen_protocol()
    route = str(step.get("route"))
    ring = tuple(PODS[route])
    plan = list(step.get("serving_rows") or ())
    failures: list[dict[str, Any]] = []
    for position, raw in enumerate(_rows(step, "requests")):
        parts = [str(part) for part in raw.get("parts") or ()]
        expected = (protocol.choose_pod(protocol.fold(parts), ring)
                    if plan else sorted(ring)[position % len(ring)])
        if str(raw.get("pod")) == expected:
            continue
        failures.append(_failure(
            "request_sent_to_wrong_pod", **_at(step),
            request=str(raw.get("request")), reported=str(raw.get("pod")),
            expected=str(expected)))
    return failures


def _pin_failures(steps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    protocol, failures = frozen_protocol(), []
    for step in _pushes(steps):
        if step.get("accepted") and step.get("expected_plan") is not None:
            failures.extend(_ttl_failures(step))
    for step in steps:
        kind = str(step.get("type"))
        if not step.get("ok"):
            continue
        if kind == "cookies":
            failures.extend(_cookie_line_failures(step))
            continue
        if kind != "traffic":
            continue
        failures.extend(_routing_failures(step))
        plan = [_step_from_row(row) for row in step.get("serving_rows") or ()]
        rewrites, sent = dict(step.get("rewrites") or {}), {
            str(dict(item).get("label")): dict(item) for item in step["event"]["requests"]}
        for raw in _rows(step, "requests") if plan else ():
            request = protocol.build_request(sent[str(raw.get("request"))])
            observed = [str(part) for part in raw.get("parts") or ()]
            if tuple(observed) == reference_parts(request, plan, rewrites):
                continue
            found = _classify_parts(request, plan, rewrites, observed)
            if found is not None:
                failures.append(_failure(
                    str(found.pop("mode")), **_at(step),
                    request=str(raw.get("request")), **found))
    return failures


def _classify_parts(
    request: Any, plan: Sequence[Any], rewrites: Mapping, observed: Sequence[str]
) -> dict[str, Any] | None:
    'Which of the extraction rules the parts of this request broke.'

    protocol = frozen_protocol()
    position, stopped = 0, ""
    for step in plan:
        identity = _identity(step)
        name = identity[1] or "the client address"
        got = str(observed[position]) if position < len(observed) else ""
        if stopped:
            if got:
                return {"mode": "stop_ignored", "key": stopped, "reported": got,
                        "expected": "nothing after it"}
            break
        value = protocol.read_value(request, step)
        if value is None:
            if got.startswith(f"{identity[0]}:{identity[1]}="):
                return {"mode": "absent_value_folded", "key": name, "reported": got,
                        "expected": "nothing"}
            continue
        rewrite = rewrites[identity] if identity in rewrites else step.rewrite
        wanted = protocol.part(step, protocol.apply_rewrite(rewrite, value))
        if got != wanted:
            raw = rewrite is not None and got == protocol.part(step, value)
            return {"mode": "rewritten_value_not_used" if raw else "pin_part_wrong",
                    "key": name, "reported": got or "nothing", "expected": wanted}
        position += 1
        stopped = name if step.stop else ""
    if position < len(observed):
        return {"mode": "stop_ignored" if stopped else "pin_part_wrong",
                "key": stopped or "the end of the plan",
                "reported": str(observed[position]), "expected": "nothing after it"}
    return None


def _analyse(run: Mapping[str, Any], program: Sequence[Mapping[str, Any]]) -> dict:
    steps = read_steps(run, program)
    broken = _broken(steps)
    if broken:
        return {bucket: [dict(item) for item in broken] for bucket in BUCKETS.values()}
    return {
        "merge_failures": _merge_failures(steps), "pin_failures": _pin_failures(steps),
        "duplicate_failures": _duplicate_failures(steps),
        "repush_failures": _repush_failures(steps), "opt_out_failures": _opt_out_failures(steps),
    }


_RUNNER_PHRASES = ("candidate process exited", "candidate returned invalid JSON",
                   "candidate returned non-object")
_TIMEOUT_PHRASE = "project rehearsal exceeded"


def _console_error(candidate: Mapping[str, Any]) -> str:
    'The one line the push log shows when a drill did not finish.'
    line = reported = str(candidate.get("error") or "no output").strip()
    if reported.startswith(_TIMEOUT_PHRASE):
        limit = reported[len(_TIMEOUT_PHRASE) :].strip() or "its time"
        line = f"it was still going after {limit} and the drill box stopped it"
    elif any(reported.startswith(phrase) for phrase in _RUNNER_PHRASES):
        diagnostic = str(candidate.get("diagnostic") or "").strip().splitlines()
        line = (diagnostic[-1].strip() if diagnostic else "") or "the plane said no more"
    return f"the plane stopped part way through the drill: {_safe_error(line)}"


def evaluate_project(artifact_dir: Path) -> Mapping[str, Any]:
    'Run the release rehearsal against this workspace and bucket what broke.'

    def compute() -> Mapping[str, Any]:
        program = build_program(str(PRIVATE_CASE["profile"]), int(PRIVATE_CASE["scale"]))
        runs = [PROJECT.invoke(
            artifact_dir,
            {"events": list(program), "controller_instance": instance},
        ) for instance in ("release-before-restart", "release-after-restart")]
        analyses: list[Mapping[str, Any]] = []
        diagnostics: list[str] = []
        for run in runs:
            if run.get("ok"):
                analyses.append(_analyse(run, program))
            else:
                analyses.append(dict(failed_analysis(
                    _console_error(run), tuple(BUCKETS.values()))))
                if run.get("diagnostic"):
                    diagnostics.append(str(run["diagnostic"]))
        analysis = {
            bucket: [dict(item) for found in analyses for item in found.get(bucket, ())]
            for bucket in BUCKETS.values()
        }
        if all(run.get("ok") for run in runs):
            analysis["repush_failures"].extend(
                _process_restart_failures(runs[0], runs[1], program))
        if diagnostics:
            analysis["diagnostic"] = "\n".join(diagnostics)
        analysis["case"] = {"drill": "release rehearsal", "routes": sorted(PODS)}
        return analysis

    return _CACHE.get_or_compute(Path(artifact_dir), compute)
