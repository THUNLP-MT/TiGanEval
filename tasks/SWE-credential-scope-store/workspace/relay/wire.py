"""Wire contract for the relay client: addresses, grant syntax, hosts, runs.

Every collection job in the platform reaches its sources through `relay`, and
this module is the part of it the platform release owns: the address rules,
the two grant headers and how they are written, the deterministic clock, the
host models the jobs actually talk to, and the run loop that drives one job.

Nothing here holds a grant between requests. Where a run keeps what a host
handed back is `relay/vault.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


#: The header a host uses to hand a grant to the client, and the header the
#: client uses to present the grants it holds.
GRANT_SET = "Grant-Set"
GRANT = "Grant"

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class RelayError(RuntimeError):
    """Base of everything the relay client raises."""


@dataclass(frozen=True, slots=True)
class Address:
    """One absolute address, split the way the platform compares addresses."""

    scheme: str
    host: str
    port: int
    path: str = "/"

    @property
    def origin(self) -> str:
        """Scheme, host and port. Two listeners on one host differ here."""
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def text(self) -> str:
        return f"{self.origin}{self.path}"


def parse_address(url: str) -> Address:
    """Split an absolute URL, filling in the port the scheme implies."""

    raw = str(url)
    if "://" not in raw:
        raise ValueError(f"not an absolute URL: {raw!r}")
    scheme, _, rest = raw.partition("://")
    authority, slash, path = rest.partition("/")
    host, colon, port = authority.partition(":")
    scheme = scheme.lower()
    number = int(port) if colon else (443 if scheme == "https" else 80)
    return Address(scheme=scheme, host=host.lower(), port=number, path=f"{slash}{path}" or "/")


def host_covered(host: str, scope: str) -> bool:
    """Whether `scope` covers `host`, comparing whole labels and ignoring case.

    ``vendor.example`` covers ``vendor.example`` and ``api.vendor.example``. It
    does not cover ``newvendor.example``: the text matches at the end, but not
    at a label boundary, so the two are different sites. An empty `scope`
    covers nothing.
    """

    left, right = str(host).lower().strip("."), str(scope).lower().strip(".")
    if not right:
        return False
    return left == right or left.endswith(f".{right}")


def path_covered(request_path: str, under: str) -> bool:
    """Whether a grant kept `under` reaches a request made to `request_path`.

    ``/reports`` reaches ``/reports`` and ``/reports/q3``; it does not reach
    ``/reportsroom``, because the match ends inside a segment name rather than
    at a boundary. ``/`` reaches everything.
    """

    path, prefix = str(request_path) or "/", str(under) or "/"
    if path == prefix:
        return True
    if not path.startswith(prefix):
        return False
    return prefix.endswith("/") or path[len(prefix)] == "/"


def default_under(request_path: str) -> str:
    """The reach a grant is kept at when the host named none.

    Everything up to, and not including, the last ``/`` of the request path:
    ``/desk/tools/list`` gives ``/desk/tools`` and ``/list`` gives ``/``.
    """

    path = str(request_path)
    if not path.startswith("/"):
        return "/"
    cut = path.rfind("/")
    return path[:cut] if cut > 0 else "/"


def _days_from_civil(year: int, month: int, day: int) -> int:
    year -= month <= 2
    era = (year if year >= 0 else year - 399) // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def parse_stamp(text: str) -> float | None:
    """Read a wire timestamp, or None when this reader cannot.

    Hosts write a moment as ``Tue, 05 Nov 2030 09:00:00 GMT`` -- note the comma
    after the weekday, which is part of the value and not a separator. The
    return is seconds on the same scale as :class:`Clock`. Anything this reader
    does not recognise comes back as None; it is not an error to be handed one.
    """

    parts = str(text).strip().split()
    if len(parts) != 6 or not parts[0].endswith(",") or parts[5].upper() != "GMT":
        return None
    if parts[2] not in _MONTHS:
        return None
    clock_parts = parts[4].split(":")
    if len(clock_parts) != 3:
        return None
    try:
        day, year = int(parts[1]), int(parts[3])
        hour, minute, second = (int(item) for item in clock_parts)
    except ValueError:
        return None
    days = _days_from_civil(year, _MONTHS.index(parts[2]) + 1, day)
    return float(days * 86400 + hour * 3600 + minute * 60 + second)


@dataclass(frozen=True, slots=True)
class Request:
    """One request a collection job makes through the relay client."""

    url: str
    label: str = ""
    method: str = "GET"


@dataclass(frozen=True, slots=True)
class Reply:
    """What a host answered, with its headers in the order they arrived."""

    status: int
    reason: str = "ok"
    headers: tuple[tuple[str, str], ...] = ()
    acted_for: str = ""


def grant_lines(reply: Reply) -> tuple[str, ...]:
    """The value of every ``Grant-Set`` header of one reply, in arrival order.

    A host may write one grant per header. Some write several into one header,
    separated by commas, which is why the value comes back whole here.
    """

    return tuple(
        str(value) for name, value in reply.headers if str(name).lower() == GRANT_SET.lower()
    )


def format_grant_header(pairs: Iterable[tuple[str, str]]) -> str:
    """Write name/value pairs as the value of one ``Grant`` header."""

    return "; ".join(f"{str(name)}={str(value)}" for name, value in pairs)


def read_grant_header(value: str) -> tuple[tuple[str, str], ...]:
    """Read a ``Grant`` header value back into the pairs it carries, in order."""

    pairs: list[tuple[str, str]] = []
    for chunk in str(value).split(";"):
        name, sign, item = chunk.strip().partition("=")
        if sign:
            pairs.append((name.strip(), item.strip()))
    return tuple(pairs)


class Clock:
    """The console's clock, in seconds, on the same scale as `parse_stamp`."""

    def __init__(self, start_s: float = 0.0):
        self._now = float(start_s)

    def now(self) -> float:
        return self._now

    def set(self, value: float) -> None:
        self._now = float(value)

    def advance(self, seconds: float) -> None:
        self._now += float(seconds)


@dataclass(frozen=True, slots=True)
class JobProfile:
    """What one collection job is configured with.

    ``max_grants_per_scope`` is how many live grants the platform sizes a job's
    store to for any one scope.
    """

    name: str = "sweep"
    max_grants_per_scope: int = 6


class Host:
    """One host in the fleet as a job reaches it.

    A host accepts only the grant values it issued itself, refuses a request
    whose grant header repeats one pair or runs over the size it publishes,
    and reads the desk a request acts for from the first grant of its session
    name that the header carries.
    """

    def __init__(self, origin: str, clock: Clock, spec: Mapping[str, Any]):
        self.origin = str(origin)
        self.clock = clock
        self.folds = bool(spec.get("folds", False))
        self.max_header_bytes = int(spec.get("max_header_bytes", 4096))
        self.session_name = str(spec.get("session_name", ""))
        self.needs_session_under = tuple(str(item) for item in spec.get("needs_session_under", ()))
        self.issued = {str(key): dict(value) for key, value in dict(spec.get("issued", {})).items()}
        self.hands_out = {
            str(key): [list(hit) for hit in value]
            for key, value in dict(spec.get("hands_out", {})).items()
        }
        self.hits: dict[str, int] = {}

    def _retired(self, value: str) -> bool:
        until = self.issued.get(value, {}).get("until_s")
        return until is not None and self.clock.now() >= float(until)

    def _refusal(self, path: str, pairs: Sequence[tuple[str, str]], header: str) -> tuple[int, str]:
        seen: set[tuple[str, str]] = set()
        for pair in pairs:
            if pair in seen:
                return 400, "repeated_grant"
            seen.add(pair)
        if len(header.encode("utf-8")) > self.max_header_bytes:
            return 431, "grant_header_too_large"
        for _name, value in pairs:
            if value not in self.issued:
                return 403, "unexpected_grant"
            if self._retired(value):
                return 401, "stale_session"
        if self.session_name and not any(name == self.session_name for name, _ in pairs):
            if any(path_covered(path, under) for under in self.needs_session_under):
                return 401, "login_required"
        return 200, "ok"

    def _hand_out(self, path: str) -> tuple[tuple[str, str], ...]:
        hits = self.hands_out.get(path)
        if not hits:
            return ()
        index = self.hits.get(path, 0)
        self.hits[path] = index + 1
        if index >= len(hits):
            return ()
        lines = [str(line) for line in hits[index]]
        if self.folds and len(lines) > 1:
            return ((GRANT_SET, ", ".join(lines)),)
        return tuple((GRANT_SET, line) for line in lines)

    def answer(self, request: Request, pairs: Sequence[tuple[str, str]]) -> Reply:
        """Answer one request that arrived carrying `pairs` in its grant header."""

        path = parse_address(request.url).path
        header = format_grant_header(pairs)
        status, reason = self._refusal(path, pairs, header)
        acted_for = ""
        if status == 200 and self.session_name:
            held = [value for name, value in pairs if name == self.session_name]
            if held:
                acted_for = str(self.issued.get(held[0], {}).get("desk", ""))
        headers = self._hand_out(path) if status == 200 else ()
        return Reply(status=status, reason=reason, headers=headers, acted_for=acted_for)


class Journey:
    """One job's run: every request in order, against the fleet, through a store.

    Each step asks the store which grants to present for the request, sends
    them to the host at that address, and hands the reply back to the store.
    Every step is written to :attr:`log`, which is the job's own request log.
    """

    def __init__(self, clock: Clock, hosts: Mapping[str, Host]):
        self.clock = clock
        self.hosts = dict(hosts)
        self.log: list[dict[str, Any]] = []

    def go(self, store: Any, request: Request, entered_as: str = "") -> Reply:
        address = parse_address(request.url)
        host = self.hosts.get(address.origin)
        if host is None:
            raise RelayError(f"no host answers at {address.origin}")
        pairs = tuple((str(name), str(value)) for name, value in store.present(request))
        reply = host.answer(request, pairs)
        store.absorb(request, reply)
        self.log.append({
            "step": len(self.log) + 1,
            "label": str(request.label),
            "url": str(request.url),
            "host": address.host,
            "scheme": address.scheme,
            "path": address.path,
            "at_s": self.clock.now(),
            "entered_as": str(entered_as),
            "presented": format_grant_header(pairs),
            "grant_names": [name for name, _ in pairs],
            "header_bytes": len(format_grant_header(pairs).encode("utf-8")),
            "max_header_bytes": host.max_header_bytes,
            "status": int(reply.status),
            "reason": str(reply.reason),
            "acted_for": str(reply.acted_for),
            "handed_back": [value for _name, value in reply.headers],
        })
        return reply
