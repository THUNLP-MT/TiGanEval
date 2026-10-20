"""Where a run keeps what a host handed back.

A grant is held with the reach its issuer gave it -- the site, the path and
the scheme -- together with the moment it stops being live and the order it
entered the store in. Presenting is a pure function of what is live and where
the request is going; taking in is a pure function of the reply and the clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .wire import (
    Clock,
    JobProfile,
    Reply,
    Request,
    default_under,
    grant_lines,
    host_covered,
    parse_address,
    parse_stamp,
    path_covered,
)


@dataclass
class Grant:
    """One live grant and the reach the host that handed it over gave it."""

    name: str
    value: str
    scope: str
    host: str
    under: str
    sealed: bool
    deadline: float | None
    order: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.name, self.audience, self.under)

    @property
    def audience(self) -> str:
        return self.scope or f"only:{self.host}"


def split_directives(value: str) -> list[str]:
    """One header value split into the grants it carries.

    A comma starts a new grant only where what follows it opens with a name of
    its own; a comma inside a wire timestamp does not, so the remainder stays
    with the grant it belongs to.
    """

    parts: list[str] = []
    for piece in str(value).split(","):
        name, sign, _rest = piece.split(";")[0].strip().partition("=")
        opens = bool(sign) and bool(name.strip()) and " " not in name.strip()
        if opens or not parts:
            parts.append(piece)
        else:
            parts[-1] = f"{parts[-1]},{piece}"
    return parts


def read_directive(text: str) -> tuple[str, str, dict[str, str], set[str]] | None:
    """One grant directive as name, value, attributes with values, and flags."""

    chunks = [chunk.strip() for chunk in str(text).split(";")]
    name, sign, value = chunks[0].partition("=")
    name, value = name.strip(), value.strip()
    if not sign or not name or " " in name:
        return None
    attributes: dict[str, str] = {}
    flags: set[str] = set()
    for chunk in chunks[1:]:
        key, mark, item = chunk.partition("=")
        key = key.strip().lower()
        if not key:
            continue
        if mark:
            attributes[key] = item.strip()
        else:
            flags.add(key)
    return name, value, attributes, flags


class GrantStore:
    """The grants one run is holding."""

    def __init__(self, profile: JobProfile, clock: Clock):
        self.profile = profile
        self.clock = clock
        self.grants: list[Grant] = []
        self.counter = 0

    # -- presenting ---------------------------------------------------------

    def _reaches(self, grant: Grant, scheme: str, host: str, path: str) -> bool:
        if grant.sealed and scheme != "https":
            return False
        if grant.scope:
            if not host_covered(host, grant.scope):
                return False
        elif host != grant.host:
            return False
        return path_covered(path, grant.under)

    def present(self, request: Request) -> Sequence[tuple[str, str]]:
        """The grants to put in the request's ``Grant`` header, in order."""

        self._drop_expired()
        address = parse_address(request.url)
        live = [
            grant
            for grant in self.grants
            if self._reaches(grant, address.scheme, address.host, address.path)
        ]
        live.sort(key=lambda grant: (-len(grant.under), -grant.order))
        return [(grant.name, grant.value) for grant in live]

    # -- taking in ----------------------------------------------------------

    def absorb(self, request: Request, reply: Reply) -> None:
        """Take in whatever this reply handed over."""

        address = parse_address(request.url)
        for line in grant_lines(reply):
            for directive in split_directives(line):
                self._take(address, directive)
        self._drop_expired()
        self._trim()

    def _take(self, address, directive: str) -> None:
        read = read_directive(directive)
        if read is None:
            return
        name, value, attributes, flags = read
        scope = attributes.get("scope", "")
        if scope and not host_covered(address.host, scope):
            return
        under = attributes.get("under", "")
        if not under.startswith("/"):
            under = default_under(address.path)
        deadline, gone = self._deadline(attributes)
        grant = Grant(
            name=name, value=value, scope=scope, host=address.host, under=under,
            sealed="sealed" in flags, deadline=deadline, order=0,
        )
        self.grants = [held for held in self.grants if held.key != grant.key]
        if gone:
            return
        self.counter += 1
        grant.order = self.counter
        self.grants.append(grant)

    def _deadline(self, attributes: dict[str, str]) -> tuple[float | None, bool]:
        """The moment a grant stops being live, and whether it is over already."""

        now = self.clock.now()
        if "ttl" in attributes:
            try:
                seconds = float(attributes["ttl"])
            except ValueError:
                return None, False
            return (None, True) if seconds <= 0 else (now + seconds, False)
        if "until" in attributes:
            moment = parse_stamp(attributes["until"])
            if moment is None:
                return None, False
            return (None, True) if moment <= now else (moment, False)
        return None, False

    # -- what a run keeps ---------------------------------------------------

    def _drop_expired(self) -> None:
        now = self.clock.now()
        self.grants = [
            grant for grant in self.grants if grant.deadline is None or grant.deadline > now
        ]

    def _trim(self) -> None:
        for audience in {grant.audience for grant in self.grants}:
            group = sorted(
                (grant for grant in self.grants if grant.audience == audience),
                key=lambda grant: grant.order,
            )
            for grant in group[: max(0, len(group) - int(self.profile.max_grants_per_scope))]:
                self.grants.remove(grant)
