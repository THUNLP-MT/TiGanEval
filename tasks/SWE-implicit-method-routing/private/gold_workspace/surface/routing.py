"""The partner request surface: routers, where they are mounted, and dispatch.

A router holds operations and can be mounted into another router or into the
service under a prefix. A setting written on an operation, on a mount, on a
router or on the service applies to everything inside it that does not say
otherwise; `in_catalogue`, `auto_head` and `auto_options` all read that way.

The answers the surface gives about itself are made in one pass over the
assembled table, once every mount is in place, so an operation someone wrote
by hand is always already there and is never replaced.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, Mapping

from .protocol import (
    PROBE_METHOD, SUMMARY_METHOD, Endpoint, Request, Response, body_free_view,
    build_catalogue, describe_path, is_request, layer_value, matches_path,
    published_operations, run_operation, seal, usage_row,
)


def _body_free(source: Endpoint) -> Callable[[Request, Mapping[str, Any]], Response]:
    """Answer a probe by running the fetch and taking the body out of it."""

    def probe(request: Request, values: Mapping[str, Any]) -> Response:
        return body_free_view(run_operation(source, request))

    return probe


def _fixed(answer: Response) -> Callable[[Request, Mapping[str, Any]], Response]:
    def handler(request: Request, values: Mapping[str, Any]) -> Response:
        return answer

    return handler


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
        outside that. Nothing here is written back on to the router, so the
        same router mounted twice resolves once per mount.
        """

        around = (dict(mount), self.settings, *outside)
        for route in self.routes:
            yield route, f"{prefix}{route['path']}", (route["settings"], *around)
        for entry in self.mounts:
            router: Router = entry["router"]
            yield from router.walk(f"{prefix}{entry['prefix']}", entry["settings"], around)


class Service(Router):
    """The request surface as one process serves it."""

    def __init__(self, **settings: Any):
        super().__init__(**settings)
        self._usage: dict[str, dict[str, int]] = {}

    def _resolved(self) -> list[tuple[Endpoint, dict[str, bool]]]:
        """Every written operation, with what its layers resolve to."""

        rows = []
        for route, path, layers in self.walk("", {}, ()):
            endpoint = Endpoint(
                path=path, local_path=route["path"], method=route["method"],
                handler=route["handler"], name=route["name"], summary=route["summary"],
                guard=route["guard"], cost=route["cost"], params=route["params"],
                published=bool(layer_value("in_catalogue", layers, default=True)),
            )
            rows.append((endpoint, {
                "auto_head": bool(layer_value("auto_head", layers, default=True)),
                "auto_options": bool(layer_value("auto_options", layers, default=False)),
            }))
        return rows

    def endpoints(self) -> tuple[Endpoint, ...]:
        """Every operation this surface serves, in the order it matches them."""

        rows = self._resolved()
        written = tuple(endpoint for endpoint, _ in rows)
        here: dict[str, list[tuple[Endpoint, dict[str, bool]]]] = {}
        for endpoint, settings in rows:
            here.setdefault(endpoint.path, []).append((endpoint, settings))
        methods = {path: [item.method for item, _ in group] for path, group in here.items()}
        made: list[Endpoint] = []
        for path, group in here.items():
            if PROBE_METHOD in methods[path]:
                continue
            # The answer is the fetch with the body taken out, so it is the
            # read this path serves that decides: the first GET the table
            # matches here, and only when that read asks for it. A read the
            # surface never reaches never answers for the path either.
            reads = [(item, settings) for item, settings in group if item.method == "GET"]
            if reads and reads[0][1]["auto_head"]:
                # No guard, no path values and no name of its own: the fetch
                # behind it runs the whole pipeline and is the operation the
                # meter records, and only then is the body taken out.
                made.append(Endpoint(
                    path=path, local_path=reads[0][0].local_path, method=PROBE_METHOD,
                    handler=_body_free(reads[0][0]), cost=0, published=False, generated=True))
                methods[path].append(PROBE_METHOD)
        catalogue = build_catalogue(written)
        for path, group in here.items():
            if SUMMARY_METHOD in methods[path]:
                continue
            if not any(settings["auto_options"] for _, settings in group):
                continue
            methods[path].append(SUMMARY_METHOD)
            document = describe_path(path, methods[path], published_operations(catalogue, path))
            made.append(Endpoint(
                path=path, local_path=group[0][0].local_path, method=SUMMARY_METHOD,
                handler=_fixed(document), cost=0, published=False, generated=True))
        return written + tuple(made)

    def handle(self, request: Request) -> Response | None:
        """Answer one request, or nothing at all when it is not one."""

        if not is_request(request):
            return None
        here = [item for item in self.endpoints() if matches_path(item.path, request.path)]
        if not here:
            return seal(404, '{"detail": "no such path"}')
        for endpoint in here:
            if endpoint.method == request.method:
                if endpoint.generated:
                    self._count(endpoint)
                return run_operation(endpoint, request)
        return seal(405, '{"detail": "that path does not take that method"}')

    def _count(self, endpoint: Endpoint) -> None:
        """One line per mounted path, one hit per answer this surface made itself."""

        row = self._usage.setdefault(endpoint.path, usage_row())
        row["head_hits" if endpoint.method == PROBE_METHOD else "options_hits"] += 1

    def usage_report(self) -> dict[str, dict[str, int]]:
        """What the hourly capacity job reads off this process."""

        return {path: dict(row) for path, row in self._usage.items()}
