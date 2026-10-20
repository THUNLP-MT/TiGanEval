"""The partner request surface: routers, where they are mounted, and dispatch.

A router holds operations and can be mounted into another router or into the
service under a prefix. A setting written on an operation, on a mount, on a
router or on the service applies to everything inside it that does not say
otherwise; `in_catalogue` is the one the portal has today.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from .protocol import (
    Endpoint, Request, Response, is_request, layer_value, matches_path,
    run_operation, seal,
)


class Router:
    """One group of operations, mounted wherever a service mounts it."""

    def __init__(self, **settings: Any):
        self.settings: dict[str, Any] = dict(settings)
        self.routes: list[dict[str, Any]] = []
        self.mounts: list[dict[str, Any]] = []

    def add_route(
        self, path: str, method: str, handler: Any, *, name: str = "", summary: str = "",
        guard: str = "", cost: int = 1, params: Mapping[str, str] | None = None, **settings: Any,
    ) -> None:
        """Register one operation; anything named beyond it is a layer setting."""

        self.routes.append({
            "path": str(path), "method": str(method).upper(), "handler": handler,
            "name": str(name), "summary": str(summary), "guard": str(guard),
            "cost": int(cost), "params": dict(params or {}), "settings": dict(settings)})

    def include(self, router: "Router", *, prefix: str = "", **settings: Any) -> None:
        """Mount another router's operations under `prefix`."""

        self.mounts.append({"router": router, "prefix": str(prefix), "settings": dict(settings)})

    def walk(
        self, prefix: str, mount: Mapping[str, Any], outside: tuple[Mapping[str, Any], ...]
    ) -> Iterator[tuple[dict[str, Any], str, tuple[Mapping[str, Any], ...]]]:
        """Every operation under this router, with its mounted path and layers.

        The layers come back nearest first: the operation itself, then the
        mount that brought its router here, then the router, then whatever is
        outside that.
        """

        around = (dict(mount), self.settings, *outside)
        for route in self.routes:
            yield route, f"{prefix}{route['path']}", (route["settings"], *around)
        for entry in self.mounts:
            router: Router = entry["router"]
            yield from router.walk(f"{prefix}{entry['prefix']}", entry["settings"], around)


class Service(Router):
    """The request surface as one process serves it."""

    def endpoints(self) -> tuple[Endpoint, ...]:
        """Every operation this surface serves, in the order it matches them."""

        return tuple(
            Endpoint(
                path=path, local_path=route["path"], method=route["method"],
                handler=route["handler"], name=route["name"], summary=route["summary"],
                guard=route["guard"], cost=route["cost"], params=route["params"],
                published=bool(layer_value("in_catalogue", layers, default=True)),
            )
            for route, path, layers in self.walk("", {}, ())
        )

    def handle(self, request: Request) -> Response | None:
        """Answer one request, or nothing at all when it is not one."""

        if not is_request(request):
            return None
        here = [item for item in self.endpoints() if matches_path(item.path, request.path)]
        if not here:
            return seal(404, '{"detail": "no such path"}')
        for endpoint in here:
            if endpoint.method == request.method:
                return run_operation(endpoint, request)
        return seal(405, '{"detail": "that path does not take that method"}')

    def usage_report(self) -> dict[str, dict[str, int]]:
        """What the hourly capacity job reads off this process."""

        return {}
