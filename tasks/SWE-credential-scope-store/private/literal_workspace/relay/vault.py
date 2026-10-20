"""Where a run keeps what a host handed back.

One dict per site, keyed by the site suffix of the host that handed the grant
over, filled from every ``Grant-Set`` a reply carries, and sent whole on any
request whose host ends with that suffix.
"""

from __future__ import annotations

from typing import Sequence

from .wire import Clock, JobProfile, Reply, Request, grant_lines, parse_address


class GrantStore:
    """The grants one run is holding, one dict per site."""

    def __init__(self, profile: JobProfile, clock: Clock):
        self.profile = profile
        self.clock = clock
        self.sites: dict[str, dict[str, str]] = {}

    @staticmethod
    def site_of(host: str) -> str:
        labels = str(host).lower().split(".")
        return ".".join(labels[-2:]) if len(labels) > 2 else str(host).lower()

    def present(self, request: Request) -> Sequence[tuple[str, str]]:
        host = parse_address(request.url).host
        pairs: list[tuple[str, str]] = []
        for site, held in self.sites.items():
            if host.endswith(site):
                pairs.extend(held.items())
        return pairs

    def absorb(self, request: Request, reply: Reply) -> None:
        site = self.site_of(parse_address(request.url).host)
        for line in grant_lines(reply):
            name, sign, value = line.split(";")[0].strip().partition("=")
            if not sign or not name.strip():
                continue
            self.sites.setdefault(site, {})[name.strip()] = value.strip()
