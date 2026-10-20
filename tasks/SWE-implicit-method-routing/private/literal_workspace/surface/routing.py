"""The partner request surface, with the probe and method-list answers added.

`auto_head` is on by default and `auto_options` is off by default. When an
operation is registered as a GET and `auto_head` holds, a HEAD is registered
beside it that calls the same handler and gives the answer back without the
body; when `auto_options` holds, an OPTIONS is registered beside it that says
which methods the path takes.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, Mapping

from .protocol import (
    Endpoint, Request, Response, describe_path, is_request, layer_value,
    matches_path, run_operation, seal,
)


def _no_body(handler: Any) -> Callable[[Request, Mapping[str, Any]], Response]:
    """Run the operation and hand the answer back without its body."""

    def probe(request: Request, values: Mapping[str, Any]) -> Response:
        handler(request, values)
        return seal(200, "")

    return probe


def _terms(router: "Router", path: str) -> Callable[[Request, Mapping[str, Any]], Response]:
    """Say which methods this path takes on the router that declares it."""

    def handler(request: Request, values: Mapping[str, Any]) -> Response:
        here = [route["method"] for route in router.routes if route["path"] == path]
        operations = {
            route["method"]: {"name": route["name"], "summary": route["summary"]}
            for route in router.routes
            if route["path"] == path and route["method"] not in ("HEAD", "OPTIONS")
        }
        return describe_path(path, here, operations)

    return handler


class Router:
    """One group of operations, mounted wherever a service mounts it."""

    def __init__(self, auto_head: bool = True, auto_options: bool = False, **settings: Any):
        self.auto_head = bool(auto_head)
        self.auto_options = bool(auto_options)
        self.settings: dict[str, Any] = dict(settings)
        self.routes: list[dict[str, Any]] = []
        self.mounts: list[dict[str, Any]] = []

    def _append(self, path: str, method: str, handler: Any, spec: Mapping[str, Any], cost: int) -> None:
        self.routes.append({
            "path": str(path), "method": str(method).upper(), "handler": handler,
            "name": str(spec.get("name", "")), "summary": str(spec.get("summary", "")),
            "guard": str(spec.get("guard", "")), "cost": int(cost),
            "params": dict(spec.get("params") or {}), "settings": dict(spec.get("settings") or {})})

    def add_route(
        self, path: str, method: str, handler: Any, *, name: str = "", summary: str = "",
        guard: str = "", cost: int = 1, params: Mapping[str, str] | None = None,
        auto_head: bool = True, auto_options: bool = False, **settings: Any,
    ) -> None:
        """Register one operation, plus the answers the portal gives about it."""

        spec = {"name": name, "summary": summary, "guard": guard, "params": params,
                "settings": settings}
        self._append(path, method, handler, spec, cost)
        if str(method).upper() == "GET" and auto_head and self.auto_head:
            self._append(path, "HEAD", _no_body(handler), {**spec, "name": ""}, 0)
        if auto_options or self.auto_options:
            self._append(path, "OPTIONS", _terms(self, path), {"settings": settings}, 0)

    def include(
        self, router: "Router", *, prefix: str = "", auto_head: bool = True,
        auto_options: bool = False, **settings: Any,
    ) -> None:
        """Mount another router's operations under `prefix`."""

        self.mounts.append({
            "router": router, "prefix": str(prefix), "auto_head": bool(auto_head),
            "auto_options": bool(auto_options), "settings": dict(settings)})

    def walk(
        self, prefix: str, mount: Mapping[str, Any], outside: tuple[Mapping[str, Any], ...]
    ) -> Iterator[tuple[dict[str, Any], str, tuple[Mapping[str, Any], ...]]]:
        """Every operation under this router, with its mounted path and layers."""

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
                generated=route["method"] in ("HEAD", "OPTIONS") and not route["name"],
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
