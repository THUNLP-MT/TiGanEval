"""Runtime contract for the edge gateway's outbound call path.

Every gateway in the platform release ships this file, so the value types, URL
rules, health vocabulary and step machine below are the same in all four. Time
moves only when the console moves it, what an upstream answers comes from the
console's schedule, and a call reaches an upstream only when something steps it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping, Sequence


#: What the platform reads as "the origin itself is unwell", and the subset of
#: those worth one more attempt inside the same call.
FAILURE_STATUSES: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
RETRY_STATUSES: tuple[int, ...] = (429, 500, 502, 503, 504)

#: What one finished attempt says about the upstream.
OK, FAILURE, REJECTED = "ok", "failure", "rejected"


class GatewayError(RuntimeError):
    """Base of everything the outbound call path raises."""

class TransportError(GatewayError):
    """The attempt never produced a response at all."""

class TransformError(GatewayError):
    """A response arrived and the caller's transform could not read it."""

class UpstreamError(GatewayError):
    """The upstream answered with a status the caller did not ask for."""

class GatewayBlocked(GatewayError):
    """The gateway refused to make the call."""


@dataclass(frozen=True, slots=True)
class Url:
    """One absolute address, split the way the platform compares addresses."""
    scheme: str
    host: str
    port: int
    path: str = "/"

    @property
    def origin(self) -> str:
        """Scheme, host and port; two upstreams on one host differ here."""
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def text(self) -> str:
        return f"{self.origin}{self.path}"


def parse_url(text: str) -> Url:
    """Split an absolute URL, filling in the port the scheme implies."""
    raw = str(text)
    if "://" not in raw:
        raise ValueError(f"not an absolute URL: {raw!r}")
    scheme, _, rest = raw.partition("://")
    authority, slash, path = rest.partition("/")
    host, colon, port = authority.partition(":")
    scheme = scheme.lower()
    number = int(port) if colon else (443 if scheme == "https" else 80)
    return Url(scheme=scheme, host=host.lower(), port=number, path=f"{slash}{path}" or "/")


def join_base(base: str | None, target: str) -> str:
    """The absolute URL a target is sent to: absolute wins, a path is joined."""
    raw = str(target)
    if "://" in raw:
        return raw
    if base is None:
        raise ValueError(f"a relative target needs a base_url: {raw!r}")
    if not raw.startswith("/"):
        raw = f"/{raw}"
    return f"{str(base).rstrip('/')}{raw}"


@dataclass(frozen=True, slots=True)
class Request:
    """One call a service makes through the gateway.

    ``target`` is whatever the caller had: an absolute URL, a path under its
    client's ``base_url``, a :class:`Url`, or a :class:`Request` another layer
    built. ``guarded`` is the caller's opt-in to the health machinery, which the
    health probe and internal bookkeeping calls leave off; ``retries`` is how
    many extra attempts this one call may make inside itself."""
    target: Any
    label: str = ""
    base_url: str | None = None
    guarded: bool = True
    retries: int = 0
    ignore_errors: bool = False
    transform: str = "text"

    def with_base(self, base_url: str | None) -> "Request":
        """This request as the client that owns `base_url` will send it."""
        if self.base_url is not None or base_url is None:
            return self
        return replace(self, base_url=str(base_url))


def effective_url(request: Request) -> str:
    """The absolute URL this request will actually be sent to."""
    target = request.target
    if isinstance(target, Request):
        return effective_url(target.with_base(request.base_url))
    text = target.text if isinstance(target, Url) else str(target)
    return join_base(request.base_url, text)


def resolve_origin(request: Request) -> str:
    """The origin of the request as it will be sent: scheme, host and port.

    Two calls reach one upstream exactly when this is equal for both, whatever
    shape the caller passed and whichever client is sending them.
    """
    return parse_url(effective_url(request)).origin


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: str = ""

def classify_outcome(response: Response | None, error: BaseException | None) -> str:
    """How the platform reads one finished attempt.

    An attempt with no response, a body the transform could not read, and a
    status in :data:`FAILURE_STATUSES` all say the origin itself is unwell. Any
    other status the caller did not want is the origin answering correctly about
    something it was asked -- a 404 for a charge that does not exist carries no
    news about its health -- so it is a rejection, not a failure."""
    if error is not None or response is None:
        return FAILURE
    status = int(response.status)
    if status in FAILURE_STATUSES:
        return FAILURE
    if 200 <= status < 300:
        return OK
    return REJECTED


def should_retry(
    attempt: int, response: Response | None, error: BaseException | None, request: Request
) -> bool:
    """Whether attempt number `attempt` (counting from 1) is worth repeating.

    Only a transient status and an attempt that never reached the upstream are
    repeated, while the request's ``retries`` budget is unspent; a body the
    transform could not read is never repeated.
    """
    if int(attempt) > int(request.retries):
        return False
    if error is not None:
        return isinstance(error, TransportError)
    return response is not None and int(response.status) in RETRY_STATUSES


def apply_transform(name: str, response: Response) -> Any:
    """Read the response body the way the caller asked for it."""
    if str(name) == "json":
        try:
            return json.loads(response.body)
        except ValueError as exc:
            raise TransformError(f"the body could not be read as JSON: {exc}") from None
    return response.body


def deliver(
    response: Response | None, error: BaseException | None, request: Request
) -> Response:
    """What the caller receives once the gateway has stopped trying.

    A caller that set ``ignore_errors`` is handed the response whatever its
    status; that is about what this caller wants back, not about the answer.
    """
    if error is not None:
        raise error
    if response is None:
        raise TransportError("the attempt produced no response")
    if 200 <= int(response.status) < 300 or request.ignore_errors:
        return response
    raise UpstreamError(f"upstream answered {response.status}")


class Clock:
    """The operator's clock, in milliseconds."""
    def __init__(self, start_ms: float = 0.0):
        self._now = float(start_ms)

    def now_ms(self) -> float:
        return self._now

    def set(self, value: float) -> None:
        self._now = float(value)

    def advance(self, ms: float) -> None:
        self._now += float(ms)


class Transport:
    """The upstream fleet as this process reaches it.

    Every attempt arrives here in order and is written to :attr:`log`, the
    gateway's access log. What each origin answers and how long it takes comes
    from the console's schedule; an origin's last scripted entry repeats."""
    def __init__(self, script: Mapping[str, Sequence[Mapping[str, Any]]], clock: Clock):
        self.script = {str(o): [dict(s) for s in v] for o, v in dict(script).items()}
        self.clock = clock
        self.position: dict[str, int] = {}
        self.log: list[dict[str, Any]] = []

    def _next(self, origin: str) -> dict[str, Any]:
        steps = self.script.get(origin) or [{"status": 599, "cost_ms": 0.0}]
        seen = self.position.get(origin, 0)
        self.position[origin] = seen + 1
        return steps[min(seen, len(steps) - 1)]

    def send(
        self, url: str, *, call_id: str = "", label: str = "", attempt: int = 1
    ) -> Response:
        origin = parse_url(url).origin
        step = self._next(origin)
        started = self.clock.now_ms()
        self.clock.advance(float(step.get("cost_ms", 0.0)))
        failed = str(step.get("kind", "response")) == "error"
        self.log.append({
            "call": str(call_id), "label": str(label), "attempt": int(attempt),
            "url": str(url), "origin": origin, "sent_at_ms": started,
            "finished_at_ms": self.clock.now_ms(),
            "status": None if failed else int(step.get("status", 200)),
        })
        if failed:
            raise TransportError(f"no answer from {origin}")
        return Response(status=int(step.get("status", 200)), body=str(step.get("body", "{}")))


@dataclass(frozen=True, slots=True)
class Send:
    """A request for the scheduler to make one transport attempt."""
    url: str
    attempt: int = 1

@dataclass(frozen=True, slots=True)
class Attempt:
    """What one transport attempt produced, and the clock reading it ended at."""
    response: Response | None
    error: BaseException | None
    at_ms: float


class Call:
    """One logical call, advanced one transport boundary at a time.

    The first step runs the gateway up to where it wants its first attempt made
    and stops without making it; each later step makes the attempt the call waits
    on and runs on from the answer. Two calls stepped alternately are both past
    the gateway's own decisions before either touched an upstream."""
    def __init__(self, session: "Session", call_id: str, request: Request, generator: Any):
        self.id, self.request = str(call_id), request
        self.done = self.blocked = False
        self.attempts = 0
        self.response: Response | None = None
        self.error: BaseException | None = None
        self._session, self._generator = session, generator
        self._pending: Send | None = None
        self._started = False

    def step(self) -> bool:
        """Advance to the next transport boundary; True while more remain."""
        if self.done:
            return False
        try:
            if not self._started:
                self._started = True
                value = next(self._generator)
            else:
                pending, self._pending = self._pending, None
                if pending is None:
                    value = self._generator.send(None)
                else:
                    self.attempts += 1
                    value = self._generator.send(self._session.perform(self, pending))
        except StopIteration as stop:
            self.done, self.response = True, stop.value
            return False
        except GatewayBlocked as exc:
            self.done, self.blocked, self.error = True, True, exc
            return False
        except BaseException as exc:  # noqa: BLE001 - the console reports it as-is
            self.done, self.error = True, exc
            return False
        if not isinstance(value, Send):
            self.done = True
            self.error = GatewayError(f"a call may only ask for a Send, not {value!r}")
            return False
        self._pending = value
        return True


class Session:
    """Runs gateway calls as step machines so several are in flight at once."""
    def __init__(self, clock: Clock, transport: Transport):
        self.clock, self.transport = clock, transport
        self.calls: list[Call] = []

    def start(self, gateway: Any, request: Request) -> Call:
        call = Call(self, f"c-{len(self.calls) + 1:03d}", request, gateway.call(request))
        self.calls.append(call)
        return call

    def run(self, call: Call, limit: int = 40) -> Call:
        for _ in range(int(limit)):
            if call.done:
                break
            call.step()
        return call

    def perform(self, call: Call, send: Send) -> Attempt:
        try:
            response = self.transport.send(
                send.url, call_id=call.id, label=call.request.label, attempt=send.attempt
            )
        except TransportError as exc:
            return Attempt(response=None, error=exc, at_ms=self.clock.now_ms())
        return Attempt(response=response, error=None, at_ms=self.clock.now_ms())


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """What one service client is configured with.

    ``threshold`` is the number of failures in a row from one origin at which
    the fleet stops sending there, ``cooldown_ms`` how long it is then left
    alone, and ``half_open_max`` how many calls may be in flight to it while the
    fleet finds out whether it came back.
    """
    name: str = "edge"
    base_url: str | None = None
    threshold: int = 5
    cooldown_ms: float = 30000.0
    half_open_max: int = 1
