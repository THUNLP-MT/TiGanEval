"""The contract between the ingress control plane and the edge proxy.

The proxy ships in the data-plane release: the storefront, the load reporter
and the pod autoscaler are all built against the names below, so this module
stays as it is. Everything here is deterministic; there is no clock and no
randomness anywhere in a pin decision.

A route serves a *pin plan*: an ordered tuple of :class:`Step`, each naming one
thing about a request to pin on. For a request the proxy walks the plan in
order, reads the value each step names, and folds the values it found into one
digest with :func:`fold`; :func:`choose_pod` turns the digest into a pod. A
step whose value the request does not carry produces nothing to fold, and a
step marked ``stop`` ends the walk once it has contributed. Two requests that
fold to the same parts therefore land on the same pod, and one changed part
moves the client somewhere else on the ring. A route serving no plan at all
does not pin: the proxy takes its pods in turn.

The proxy will not accept just any tuple: :func:`check_plan` refuses a plan
whose steps are not grouped by kind in :data:`CANONICAL_KINDS` order, and the
route then keeps serving the last plan it accepted. Header names are
case-insensitive on the wire, so :func:`header_value` and :func:`normalise_key`
both fold their case.

Policy documents are admitted through :func:`admit`, which is the control
plane's own reading of a document: it checks the shape, refuses a document the
plane cannot apply as written, and hands back the authored entries per kind. It
does not decide anything about ordering, precedence or duplicates; that is the
control plane's own work, in ``edge/compile.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence
import zlib

#: The order the proxy requires a plan's kinds to appear in.
CANONICAL_KINDS = ("header", "cookie", "query", "client")

#: How long a cookie unit lasts, for the two spellings a duration may use.
_UNITS = {"h": 3600, "m": 60, "s": 1}
_DURATION = re.compile(r"(\d+)([hms])")


class EdgeError(RuntimeError):
    pass


class PlanRefused(EdgeError):
    """The proxy will not accept this plan, so the route keeps the last one."""


class PolicyRefused(EdgeError):
    """The control plane cannot apply this policy document as written."""


@dataclass(frozen=True, slots=True)
class Rewrite:
    """A substitution applied to a value before it is folded."""

    pattern: str
    substitution: str


@dataclass(frozen=True, slots=True)
class Step:
    """One thing a route pins on.

    ``key`` is the header name, cookie name or query parameter name; the
    ``client`` kind names nothing and carries an empty key. ``rewrite`` is
    applied to the value the request carries before it is folded. ``ttl``,
    ``path`` and ``flags`` shape the cookie the proxy sets for a ``cookie``
    step and are ignored for every other kind; ``ttl`` is whole seconds.
    ``stop`` ends the walk after this step has contributed.
    """

    kind: str
    key: str = ""
    rewrite: Rewrite | None = None
    ttl: Any = None
    path: str = "/"
    flags: tuple[str, ...] = ()
    stop: bool = False


@dataclass(frozen=True, slots=True)
class Route:
    """One route of the storefront and the pods behind it."""

    name: str
    pods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Policy:
    """One admitted policy document.

    ``entries`` are the authored entries as the document lists them, as
    ``(kind, index within that kind, entry)`` triples in document order.
    ``scope`` is ``route`` for a policy attached to named routes and ``fleet``
    for one attached across the estate.
    """

    name: str
    scope: str
    routes: tuple[str, ...]
    disabled: bool
    entries: tuple[tuple[str, int, Mapping[str, Any]], ...] = ()

    def covers(self, route_name: str) -> bool:
        return str(route_name) in self.routes or "*" in self.routes


@dataclass(frozen=True, slots=True)
class Request:
    """One request as the proxy sees it at the edge."""

    label: str = ""
    headers: tuple[tuple[str, str], ...] = ()
    cookies: tuple[tuple[str, str], ...] = ()
    query: tuple[tuple[str, str], ...] = ()
    client_ip: str = ""


def build_request(document: Mapping[str, Any]) -> Request:
    """A request from the plain mapping the traffic recorder writes."""

    def pairs(name: str) -> tuple[tuple[str, str], ...]:
        return tuple(
            (str(key), str(value)) for key, value in dict(document.get(name) or {}).items()
        )

    return Request(
        label=str(document.get("label", "")),
        headers=pairs("headers"),
        cookies=pairs("cookies"),
        query=pairs("query"),
        client_ip=str(document.get("client_ip", "")),
    )


def normalise_key(kind: str, key: Any) -> str:
    """The identity of a step's key.

    Header names are case-insensitive on the wire, so two spellings of one
    header name are one key. The ``client`` kind names nothing.
    """

    if str(kind) == "client":
        return ""
    text = str(key).strip()
    return text.lower() if str(kind) == "header" else text


def header_value(request: Request, name: str) -> str | None:
    """The value of one header, matched without regard to case."""

    wanted = str(name).strip().lower()
    for key, value in request.headers:
        if str(key).strip().lower() == wanted:
            return str(value)
    return None


def read_value(request: Request, step: Step) -> str | None:
    """What this request carries for one step, or ``None`` when it carries none."""

    kind = str(step.kind)
    if kind == "header":
        return header_value(request, step.key)
    if kind == "client":
        return str(request.client_ip) or None
    table = dict(request.cookies if kind == "cookie" else request.query)
    value = table.get(str(step.key))
    return None if value is None else str(value)


def apply_rewrite(rewrite: Rewrite | None, value: str) -> str:
    """The value as it is folded once this step's substitution has run."""

    if rewrite is None:
        return str(value)
    return re.sub(str(rewrite.pattern), str(rewrite.substitution), str(value))


def read_rewrite(entry: Mapping[str, Any]) -> Rewrite | None:
    """The substitution one authored entry asks for, if it asks for one."""

    spec = dict(entry).get("rewrite")
    if spec is None:
        return None
    if not isinstance(spec, Mapping) or "pattern" not in spec:
        raise PolicyRefused("a rewrite needs a pattern and a substitution")
    try:
        re.compile(str(spec["pattern"]))
    except re.error as exc:
        raise PolicyRefused(f"rewrite pattern does not compile: {exc}") from None
    return Rewrite(str(spec["pattern"]), str(spec.get("substitution", "")))


def ttl_seconds(value: Any) -> int:
    """Whole seconds for a cookie lifetime.

    The estate has written lifetimes both ways since the first edge release:
    ``"1h30m"`` and ``"3600"`` are both committed spellings.
    """

    if isinstance(value, bool):
        raise PolicyRefused("a cookie lifetime is a duration, not a flag")
    if isinstance(value, int):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    parts = _DURATION.findall(text)
    if not parts or "".join(f"{n}{u}" for n, u in parts) != text:
        raise PolicyRefused(f"cookie lifetime {value!r} is not a duration")
    return sum(int(number) * _UNITS[unit] for number, unit in parts)


def cookie_line(step: Step) -> str:
    """The Set-Cookie line the proxy emits for one cookie step."""

    if not isinstance(step.ttl, int) or isinstance(step.ttl, bool) or step.ttl < 0:
        raise PlanRefused(
            f"the cookie {step.key!r} needs its lifetime in whole seconds, not {step.ttl!r}"
        )
    fields = [str(step.key), f"Max-Age={int(step.ttl)}", f"Path={step.path}"]
    fields.extend(str(flag) for flag in step.flags)
    return "; ".join(fields)


def rank(policy: Policy) -> tuple[int, str]:
    """Where one policy stands against another attached to the same route.

    The more specific attachment comes first. Two policies at the same scope
    are ordered by name, so the plane composes them the same way whichever
    order the controller reconciles them in.
    """

    return (0 if str(policy.scope) == "route" else 1, str(policy.name))


def check_plan(steps: Sequence[Step]) -> None:
    """Refuse a plan the proxy will not load.

    Steps must be grouped by kind, and the groups must appear in
    :data:`CANONICAL_KINDS` order, with at most one ``client`` step.
    """

    position = -1
    for step in steps:
        kind = str(step.kind)
        if kind not in CANONICAL_KINDS:
            raise PlanRefused(f"unknown pin kind {kind!r}")
        index = CANONICAL_KINDS.index(kind)
        if index < position:
            raise PlanRefused(
                "pin steps must be grouped by kind in the order "
                f"{', '.join(CANONICAL_KINDS)}; {kind!r} arrives after "
                f"{CANONICAL_KINDS[position]!r}"
            )
        position = index
    if sum(1 for step in steps if str(step.kind) == "client") > 1:
        raise PlanRefused("a plan pins on the client address at most once")


def part(step: Step, value: str) -> str:
    """The canonical text one step contributes to the digest."""

    return f"{step.kind}:{normalise_key(step.kind, step.key)}={value}"


def fold(parts: Sequence[str]) -> int:
    """Fold the contributions of one request into the digest the ring reads."""

    digest = 0
    for item in parts:
        text = str(item)
        digest = zlib.crc32(f"{len(text)}:{text}".encode("utf-8"), digest)
    return int(digest)


def choose_pod(digest: int, pods: Sequence[str]) -> str:
    """The pod one digest lands on. The ring is the sorted pod list."""

    ring = sorted(str(pod) for pod in pods)
    if not ring:
        raise PlanRefused("a route with no pods cannot serve")
    return ring[int(digest) % len(ring)]


_ENTRY_FIELDS = {
    "header": {"name", "rewrite", "stop"}, "query": {"name", "stop"},
    "cookie": {"name", "ttl", "path", "flags", "stop"}, "client": {"stop"},
}
_DOCUMENT_FIELDS = {"headers", "cookies", "query", "client", "disable"}
_LISTS = (("header", "headers"), ("cookie", "cookies"), ("query", "query"))


def admit(document: Mapping[str, Any]) -> Policy:
    """Read one policy document, or refuse it.

    A document that turns pinning off on its routes carries ``disable`` and
    nothing else; one that turns it off and also names entries cannot be
    applied as written, and the plane refuses it whole.
    """

    body = dict(document)
    pins = dict(body.get("pins") or {})
    unknown = sorted(set(pins) - _DOCUMENT_FIELDS)
    if unknown:
        raise PolicyRefused(f"policy names pin fields the plane does not have: {unknown}")
    disabled = bool(pins.get("disable", False))
    named = sorted(name for name in pins if name != "disable")
    if disabled and named:
        raise PolicyRefused(
            f"policy {body.get('name', '?')!r} turns pinning off and also sets {named}"
        )
    entries: list[tuple[str, int, Mapping[str, Any]]] = []
    for kind, field_name in _LISTS:
        for index, raw in enumerate(pins.get(field_name) or ()):
            entry = dict(raw)
            if "name" not in entry:
                raise PolicyRefused(f"a {kind} entry needs a name")
            stray = sorted(set(entry) - _ENTRY_FIELDS[kind])
            if stray:
                raise PolicyRefused(f"a {kind} entry carries unknown fields {stray}")
            entries.append((kind, index, entry))
    if "client" in pins:
        entries.append(("client", 0, dict(pins["client"] or {})))
    return Policy(
        name=str(body.get("name", "")),
        scope=str(body.get("scope", "route")),
        routes=tuple(str(item) for item in body.get("routes") or ()),
        disabled=disabled,
        entries=tuple(entries),
    )


__all__ = (
    "CANONICAL_KINDS", "EdgeError", "PlanRefused", "PolicyRefused", "Policy",
    "Request", "Rewrite", "Route", "Step", "admit", "apply_rewrite",
    "build_request", "check_plan", "choose_pod", "cookie_line", "fold",
    "header_value", "normalise_key", "part", "rank", "read_rewrite",
    "read_value", "ttl_seconds",
)
