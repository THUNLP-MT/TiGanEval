"""Where a run keeps what a host handed back.

The store is asked for the grants to present before every request and is
handed every reply afterwards. What it does today is replay a grant only on a
request back to the exact URL that handed it over, and it reads the name and
the value out of a ``Grant-Set`` header and drops the rest of the line.
"""

from __future__ import annotations

from typing import Sequence

from .wire import Clock, JobProfile, Reply, Request, grant_lines


class GrantStore:
    """The grants one run is holding."""

    def __init__(self, profile: JobProfile, clock: Clock):
        self.profile = profile
        self.clock = clock
        self.held: dict[str, dict[str, str]] = {}

    def present(self, request: Request) -> Sequence[tuple[str, str]]:
        """The grants to put in the request's ``Grant`` header, in order."""

        return list(self.held.get(str(request.url), {}).items())

    def absorb(self, request: Request, reply: Reply) -> None:
        """Take in whatever this reply handed over."""

        for line in grant_lines(reply):
            name, sign, value = line.split(";")[0].strip().partition("=")
            if not sign or not name.strip():
                continue
            self.held.setdefault(str(request.url), {})[name.strip()] = value.strip()
