"""Runtime contract for the delivery portal's partner request surface.

Every service in the partner platform ships this file, so the value types, the
path rules, the method vocabulary, the published-operation document and the
work meter below read the same in all of them. Nothing here reaches a socket:
a request is a value, an answer is a value, the clock never moves, and what an
operation costs is whatever that operation says it costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Iterable, Mapping


#: The order the platform prints a method list in, wherever one is shown.
METHOD_ORDER: tuple[str, ...] = (
    "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE",
)

#: The two methods a partner asks a path about rather than asking it to do work.
PROBE_METHOD, SUMMARY_METHOD = "HEAD", "OPTIONS"

#: Who may call a guarded operation. The portal issues one token per partner.
PARTNER_TOKENS: tuple[str, ...] = ("acme-live", "borealis-live", "mirror-probe")
STEWARD_TOKENS: tuple[str, ...] = ("steward-live",)


class _Unset:
    """What a layer that says nothing about a setting is holding."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - readability only
        return "UNSET"


#: A setting a layer does not declare. Distinct from False, which declares off.
UNSET = _Unset()


def layer_value(name: str, layers: Iterable[Mapping[str, Any]], default: Any) -> Any:
    """The nearest declared value of one setting, reading `layers` in order.

    A layer that does not carry `name` says nothing about it, which is not the
    same as carrying False. The first layer that declares the setting decides
    it; when none of them does, the platform default stands.
    """

    for layer in layers:
        value = dict(layer or {}).get(name, UNSET)
        if value is not UNSET:
            return value
    return default


# --------------------------------------------------------------------------
# What arrives and what goes back


@dataclass(frozen=True, slots=True)
class Request:
    """One thing a partner sent at the portal.

    ``kind`` is ``request`` for an ordinary call. A partner's streaming client
    opens its channel on the same path with ``kind="upgrade"``, which the
    request surface does not answer at all.
    """

    method: str
    path: str
    token: str | None = None
    label: str = ""
    kind: str = "request"


@dataclass(frozen=True, slots=True)
class Response:
    """One sealed answer: a status, the header fields, and the body."""

    status: int
    headers: Mapping[str, str]
    body: str = ""


def is_request(request: Request) -> bool:
    """Whether this is an ordinary call rather than a channel opening."""

    return str(getattr(request, "kind", "request")) == "request"


def seal(status: int, body: str = "", headers: Mapping[str, str] | None = None) -> Response:
    """The answer as the portal puts it on the wire.

    Header names are lowered and `content-type` defaults to JSON.
    `content-length` is the byte length of the body being sealed unless the
    operation states it, which is how an answer that carries no body can still
    say how large the thing it is about is; the delivery mirror sizes its
    transfer from that field.
    """

    text = str(body)
    fields = {
        "content-type": "application/json",
        "content-length": str(len(text.encode("utf-8"))),
    }
    fields.update({str(key).lower(): str(value) for key, value in dict(headers or {}).items()})
    return Response(status=int(status), headers=fields, body=text)


def body_free_view(response: Response) -> Response:
    """The same answer with the body taken out and nothing else changed.

    The status and every header field survive, `content-length` among them, so
    a caller that asked only how big something is still learns how big it is
    and still learns that it may not have it.
    """

    return Response(status=int(response.status), headers=dict(response.headers), body="")


def order_methods(methods: Iterable[str]) -> tuple[str, ...]:
    """The given methods, deduplicated, in the platform's printing order."""

    seen = {str(method).upper() for method in methods}
    known = [method for method in METHOD_ORDER if method in seen]
    return tuple(known + sorted(seen - set(METHOD_ORDER)))


def allow_header(methods: Iterable[str]) -> str:
    """The `allow` field's value for a set of methods."""

    return ", ".join(order_methods(methods))


# --------------------------------------------------------------------------
# Paths and operations


def path_parts(path: str) -> tuple[str, ...]:
    return tuple(part for part in str(path).split("/") if part)


def matches_path(template: str, path: str) -> bool:
    """Whether `path` is this template's path, ignoring what the values say."""

    left, right = path_parts(template), path_parts(path)
    if len(left) != len(right):
        return False
    return all(part.startswith("{") or part == other for part, other in zip(left, right))


@dataclass(frozen=True)
class Endpoint:
    """One operation the surface serves, as it stands in the assembled table.

    ``path`` is the mounted path a partner calls; ``local_path`` is the path
    the router that owns the operation declares it under. ``generated`` marks
    an answer the surface produced for itself rather than one someone wrote.
    ``guard`` and ``params`` are the declaration `run_operation` reads before
    it reaches ``handler``: whatever they turn away is answered here, with the
    reason as a body, and this endpoint's ``handler`` is never called for it.
    """

    path: str
    method: str
    handler: Callable[[Request, Mapping[str, Any]], Response]
    local_path: str = ""
    name: str = ""
    summary: str = ""
    guard: str = ""
    cost: int = 1
    params: Mapping[str, str] = field(default_factory=dict)
    published: bool = True
    generated: bool = False


def path_values(endpoint: Endpoint, path: str) -> dict[str, Any]:
    """The values this path carries, read the way the operation declares them.

    A value the operation declares as a whole number and the caller wrote as
    something else is not this operation's path at all, which is what the
    portal answers 422 to.
    """

    values: dict[str, Any] = {}
    for part, given in zip(path_parts(endpoint.path), path_parts(path)):
        if not part.startswith("{"):
            continue
        name = part.strip("{}")
        if str(dict(endpoint.params).get(name, "text")) == "whole":
            try:
                values[name] = int(given)
            except ValueError:
                raise ValueError(f"{name} must be a whole number, not {given!r}") from None
        else:
            values[name] = given
    return values


def guard_answer(guard: str, request: Request) -> Response | None:
    """The refusal this guard makes, or None when the caller may go on.

    A refusal is a sealed answer like any other: it carries its reason as the
    body and the `content-length` of that reason.
    """

    token = None if request.token is None else str(request.token)
    if str(guard) == "partner" and token not in PARTNER_TOKENS:
        return seal(401, json.dumps({"detail": "no partner token"}))
    if str(guard) == "steward" and token not in STEWARD_TOKENS:
        return seal(403, json.dumps({"detail": "stewards only"}))
    return None


def make_handler(answers: Mapping[str, Mapping[str, Any]]) -> Callable[..., Response]:
    """A handler that answers from a fixed table keyed by the path's value."""

    table = {str(key): dict(value) for key, value in dict(answers).items()}

    def handler(request: Request, values: Mapping[str, Any]) -> Response:
        key = str(next(iter(values.values()))) if values else "-"
        answer = table.get(key) or table.get("*") or {"status": 200, "body": "{}"}
        return seal(
            int(answer.get("status", 200)),
            str(answer.get("body", "")),
            dict(answer.get("headers") or {}),
        )

    return handler


class Meter:
    """What serving requests has cost this process.

    One line is written for every operation that actually runs, so an answer
    that quietly runs an expensive operation behind itself shows up here as
    that operation's cost. The monthly capacity report's cost column is the
    sum of these lines: the meter is the platform's record of the work a
    process did, `run_operation` adds a line where an operation runs, and
    nothing takes one away.
    """

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.entries.clear()

    def record(self, endpoint: Endpoint, request: Request) -> None:
        self.entries.append(
            {
                "label": str(request.label),
                "path": str(endpoint.path),
                "method": str(endpoint.method),
                "operation": str(endpoint.name),
                "units": int(endpoint.cost),
            }
        )

    def units_for(self, label: str) -> int:
        return sum(int(row["units"]) for row in self.entries if row["label"] == str(label))


#: The process's meter. Every service in it writes here.
METER = Meter()


def run_operation(endpoint: Endpoint, request: Request) -> Response:
    """Run one operation the whole way and return the answer it produced.

    The path values are read first, then the guard, then the operation itself;
    the meter is written only once the operation is really going to run. Any
    of the three can be where the answer comes from, and all three come back
    sealed with a body: the complaint about a path value, the guard's refusal,
    and the operation's own answer alike. An endpoint whose own declaration
    carries a guard or a whole-number value therefore never reaches its own
    handler on the calls this function answers for it.
    """

    try:
        values = path_values(endpoint, request.path)
    except ValueError as exc:
        return seal(422, json.dumps({"detail": str(exc)}))
    refused = guard_answer(endpoint.guard, request)
    if refused is not None:
        return refused
    METER.record(endpoint, request)
    return endpoint.handler(request, values)


# --------------------------------------------------------------------------
# What the portal publishes about itself


def build_catalogue(endpoints: Iterable[Endpoint]) -> dict[str, dict[str, dict[str, str]]]:
    """The published operation document, keyed by mounted path then method.

    This is the same document the partner platform generates its client
    libraries from, so an operation the surface keeps out of the catalogue is
    not in here and an answer the surface produced for itself never is.
    """

    catalogue: dict[str, dict[str, dict[str, str]]] = {}
    for endpoint in endpoints:
        if endpoint.generated or not endpoint.published:
            continue
        entry = catalogue.setdefault(str(endpoint.path), {})
        entry[str(endpoint.method)] = {
            "name": str(endpoint.name),
            "summary": str(endpoint.summary),
        }
    return {path: dict(sorted(entry.items())) for path, entry in sorted(catalogue.items())}


def published_operations(
    catalogue: Mapping[str, Mapping[str, Mapping[str, str]]], path: str
) -> dict[str, dict[str, str]]:
    """One path's published operations, without the two that are about the path."""

    entry = dict(catalogue.get(str(path), {}))
    return {
        method: dict(value)
        for method, value in entry.items()
        if method not in (PROBE_METHOD, SUMMARY_METHOD)
    }


def describe_path(
    path: str, methods: Iterable[str], operations: Mapping[str, Mapping[str, str]]
) -> Response:
    """The answer that tells a caller what a path takes.

    The method list and the `allow` field carry exactly the methods handed in,
    in the platform's printing order, and `operations` is handed on as it was
    given.
    """

    ordered = order_methods(methods)
    body = json.dumps(
        {
            "path": str(path),
            "methods": list(ordered),
            "operations": {
                method: dict(value) for method, value in sorted(dict(operations).items())
            },
        },
        sort_keys=True,
    )
    return seal(200, body, {"allow": allow_header(ordered)})


def usage_row(head_hits: int = 0, options_hits: int = 0) -> dict[str, int]:
    """One line of the capacity report, as the hourly job expects to read it."""

    return {"head_hits": int(head_hits), "options_hits": int(options_hits)}
