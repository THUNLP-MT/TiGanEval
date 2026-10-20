'Deterministic listing traffic: catalogues, merchandising edits, request runs.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

PRICE_ASC = "price_cents:asc"
MIXED = "stock:desc,price_cents:asc"
PRICE_DESC = "price_cents:desc"
NAME_DESC = "name:desc"

_WORDS = ("amber", "basalt", "cedar", "dune", "ember", "fern", "granite", "harbour",
          "indigo", "juniper", "kelp", "larch", "moss", "nettle", "onyx", "pewter",
          "quartz", "rowan", "slate", "thistle", "umber", "vellum", "willow", "yarrow")

def _catalogue(prefix: str, count: int, *, tie_price: int, tie_every: int,
               base: int = 450, step: int = 137, spread: int = 83) -> list[dict[str, Any]]:
    'One catalogue, held in the order merchandising happened to add its rows.'
    rows = [{"item_id": f"{prefix}-{n:04d}",
             "price_cents": tie_price if n % tie_every == 0
             else base + ((n * step) % spread) * 25,
             "stock": (n * 7) % 11,
             "name": f"{_WORDS[(n * 5) % len(_WORDS)]}-{n:04d}"} for n in range(1, count + 1)]
    return sorted(rows, key=lambda row: row["name"])

CATALOGUES: Mapping[str, list[dict[str, Any]]] = {

    "autumn": _catalogue("au", 96, tie_price=1999, tie_every=3),
    "winter": _catalogue("wi", 60, tie_price=1450, tie_every=4, base=600, step=91, spread=47),
    "spring": _catalogue("sp", 42, tie_price=775, tie_every=5, base=375, step=53, spread=29),

    "harvest": _catalogue("hv", 120, tie_price=1450, tie_every=3, base=800, step=61, spread=67),
    "orchard": _catalogue("or", 80, tie_price=1725, tie_every=4, base=525, step=79, spread=53),
    "market": _catalogue("mk", 60, tie_price=1350, tie_every=6, base=990, step=43, spread=37),
}


def order_pairs(order_by: str) -> tuple[tuple[str, str], ...]:
    parts = []
    for chunk in str(order_by).split(","):
        field, _, direction = chunk.strip().partition(":")
        parts.append((field.strip(), (direction.strip() or "asc")))
    return tuple(parts)

def sorts_after(row: Mapping[str, Any], boundary: Mapping[str, Any], order_by: str) -> bool:
    for field, direction in order_pairs(order_by):
        left, right = row[field], boundary[field]
        if left != right:
            return left > right if direction == "asc" else left < right
    return str(row["item_id"]) > str(boundary["item_id"])

def canonical_order(rows: Sequence[Mapping[str, Any]], order_by: str) -> list[dict[str, Any]]:
    ordered = sorted((dict(row) for row in rows), key=lambda row: row["item_id"])
    for field, direction in reversed(order_pairs(order_by)):
        ordered = sorted(ordered, key=lambda row: row[field], reverse=direction == "desc")
    return ordered

def _page_after(rows, order_by: str, limit: int, boundary) -> list[dict[str, Any]]:
    "The page a scroll that honours the catalogue's own order serves next."
    ordered = canonical_order(rows, order_by)
    if boundary is not None:
        ordered = [row for row in ordered if sorts_after(row, boundary, order_by)]
    return ordered[:limit]


def _store(name: str, catalogue: str) -> dict[str, Any]:
    return {"op": "store", "name": name, "catalogue": catalogue, "label": f"store-{name}"}

def _service(name: str, store: str, *, restart: bool = False) -> dict[str, Any]:
    return {"op": "service", "name": name, "store": store, "restart": restart,
            "label": f"service-{name}"}

def _add(store: str, row: Mapping[str, Any], label: str, **extra: Any) -> dict[str, Any]:
    return {"op": "add", "store": store, "row": dict(row), "label": label, **extra}

def _remove(store: str, item_id: str, label: str) -> dict[str, Any]:
    return {"op": "remove", "store": store, "item_id": str(item_id), "label": label}

def _reprice(store: str, item_id: str, values: Mapping[str, Any], label: str) -> dict[str, Any]:
    return {"op": "reprice", "store": store, "item_id": str(item_id),
            "values": dict(values), "label": label}

def _find(label: str, service: str, **options: Any) -> dict[str, Any]:
    return {"op": "find", "label": label, "service": service,
            **{key: value for key, value in options.items() if value is not None}}

def _request(name: str, service: str, order_by: str, limit: int, index: int) -> dict[str, Any]:
    'One request of a scroll; every request but the first continues the last.'
    follow = {} if index == 1 else {"cursor_from": f"{name}-{index - 1}"}
    return _find(f"{name}-{index}", service, order_by=order_by, limit=limit,
                 scroll=name, position=index, **follow)

def _scroll(name: str, service: str, order_by: str, limit: int, requests: int) -> list[dict[str, Any]]:
    return [_request(name, service, order_by, limit, index) for index in range(1, requests + 1)]

def _phase(name: str, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**dict(op), "phase": name} for op in ops]


RESTOCK = "restock-scroll"

def _edited_walk(name, service, store, catalogue, limit, requests, edits):
    'One customer scrolling while merchandising edits the same catalogue.'
    rows = [dict(row) for row in CATALOGUES[catalogue]]
    ops: list[dict[str, Any]] = [_store(store, catalogue), _service(service, store)]
    delivered: list[dict[str, Any]] = []
    boundary: dict[str, Any] | None = None
    for index in range(1, requests + 1):
        ops.append(_request(name, service, PRICE_ASC, limit, index))
        served = _page_after(rows, PRICE_ASC, limit, boundary)
        delivered.extend(served)
        if served:
            boundary = served[-1]
        for op in edits(store, index, rows, delivered, boundary):
            ops.append(op)
            _apply(rows, op)
    return ops

def _restock_ops() -> list[dict[str, Any]]:
    return _edited_walk(RESTOCK, "s2", "aisle", "winter", 8, 12, _restock_edits)

def _row(item_id: str, price: int, stock: int) -> dict[str, Any]:
    return {"item_id": item_id, "price_cents": int(price), "stock": stock,
            "name": f"line-{item_id.split('-')[1]}"}

def _restock_edits(store, index, rows, delivered, boundary) -> list[dict[str, Any]]:
    edge = None if boundary is None else int(boundary["price_cents"])
    cheapest = min(row["price_cents"] for row in rows)
    if index == 1:
        return [_add(store, _row("wi-8001", cheapest - 100, 4), "promotion-first"),
                _add(store, _row("wi-8002", cheapest - 75, 6), "promotion-second"),
                _reprice(store, boundary["item_id"],
                         {"stock": (int(boundary["stock"]) + 1) % 11},
                         "boundary-stock-refreshed")]
    if index == 2:
        return [_remove(store, delivered[0]["item_id"], "sold-out-first"),
                _remove(store, delivered[5]["item_id"], "sold-out-second")]
    if index == 3:
        return [_add(store, _row("wi-7001", edge, 5), "restock-at-the-edge", must_reach=True),
                _add(store, _row("wi-0000", edge, 2), "restock-behind-the-edge")]
    if index == 4:
        ahead = [row for row in canonical_order(rows, PRICE_ASC)
                 if sorts_after(row, boundary, PRICE_ASC)]
        return [_remove(store, ahead[3]["item_id"], "withdrawn-before-anyone-saw-it")]
    if index == 5:
        return [_remove(store, boundary["item_id"], "sold-out-at-the-edge")]
    if index == 6:
        return [_add(store, _row("wi-7002", edge, 3), "restock-at-the-edge-again",
                     must_reach=True)]
    return []

def _apply(rows: list[dict[str, Any]], op: Mapping[str, Any]) -> None:
    kind = str(op.get("op"))
    if kind == "add":
        rows.append(dict(op["row"]))
    elif kind == "remove":
        rows[:] = [row for row in rows if row["item_id"] != str(op["item_id"])]
    elif kind == "reprice":
        for row in rows:
            if row["item_id"] == str(op["item_id"]):
                row.update(dict(op["values"]))

def _scroll_ops() -> list[dict[str, Any]]:
    'Three customers reading the same catalogue under three sorts.'
    return [_store("shop", "autumn"), _service("s1", "shop"),
            *_scroll("scroll-price", "s1", PRICE_ASC, 7, 16),
            *_scroll("scroll-mixed", "s1", MIXED, 9, 13),
            *_scroll("scroll-name", "s1", NAME_DESC, 11, 11)]

def _edge_ops() -> list[dict[str, Any]]:
    'Page sizes: the exact fit, the caller who asks for everything, no size at all.'
    return [_store("till", "spring"), _service("s3", "till"),
            *_scroll("counter", "s3", PRICE_ASC, 6, 9),
            _find("whole-catalogue", "s1", order_by=PRICE_ASC, limit=500),
            _find("wide-page", "s1", order_by=PRICE_ASC, limit=50),
            _find("no-page-size", "s1", order_by=PRICE_ASC),
            _find("offset-window", "s1", order_by=MIXED, limit=11, offset=33),
            _find("offset-tail", "s1", order_by=PRICE_ASC, limit=7, offset=90)]


_CLIENT_PROBES = (
    ("sort-changed-mid-list", "cursor_from_another_sort_honoured",
     {"cursor_from": "scroll-price-2", "order_by": MIXED, "limit": 9, "minted_under": PRICE_ASC}),
    ("sort-direction-flipped", "cursor_from_another_sort_honoured",
     {"cursor_from": "scroll-price-2", "order_by": PRICE_DESC, "limit": 7,
      "minted_under": PRICE_ASC}),
    ("sort-dropped-on-retry", "cursor_without_a_sort_served",
     {"cursor_from": "scroll-price-2", "limit": 7}),
    ("offset-added-back", "cursor_with_an_offset_served",
     {"cursor_from": "scroll-price-2", "order_by": PRICE_ASC, "limit": 7, "offset": 40}),
    ("token-cut-short", "unreadable_cursor_not_refused",
     {"cursor_from": "scroll-price-2", "edit": "truncate", "order_by": PRICE_ASC, "limit": 7}),
    ("token-from-the-old-app", "unreadable_cursor_not_refused",
     {"cursor_text": "page-3-of-the-old-app", "order_by": PRICE_ASC, "limit": 7}),
    ("token-emptied-out", "edited_cursor_honoured",
     {"cursor_from": "scroll-price-2", "edit": "empty", "order_by": PRICE_ASC, "limit": 7}),
    ("token-boundary-type-changed", "edited_cursor_honoured",
     {"cursor_from": "scroll-price-2", "edit": "poison:first-number",
      "order_by": PRICE_ASC, "limit": 7}),
)

def _client_ops() -> list[dict[str, Any]]:
    ops = [_find(label, "s1", probe=expect, **options)
           for label, expect, options in _CLIENT_PROBES]
    for source, order_by, limit, fields in (("scroll-mixed-2", MIXED, 9, 4),
                                            ("scroll-price-2", PRICE_ASC, 7, 3)):
        ops.extend(_find(f"token-field-removed-{source}-{index + 1}", "s1",
                         probe="edited_cursor_honoured", cursor_from=source,
                         edit=f"drop:{index}", order_by=order_by, limit=limit)
                   for index in range(fields))
    return ops

def _sortless_ops() -> list[dict[str, Any]]:
    'The two requests that reach the service with no sort on them at all.'
    return [_find("retry-without-a-sort", "s1", limit=7),
            _find("category-page-without-a-sort", "s1", limit=9, offset=24)]

def _restart_ops() -> list[dict[str, Any]]:
    'The same token asked of a service that has just been built.'
    return [_service("s9", "shop", restart=True),
            _find("second-instance-price", "s9", cursor_from="scroll-price-3",
                  order_by=PRICE_ASC, limit=7, mirror="scroll-price-4"),
            _find("second-instance-mixed", "s9", cursor_from="scroll-mixed-5",
                  order_by=MIXED, limit=9, mirror="scroll-mixed-6")]

RELEASE_PHASES = (("scroll", _scroll_ops), ("restock", _restock_ops),
                  ("edge", _edge_ops), ("clients", _client_ops),
                  ("no-sort", _sortless_ops), ("restart", _restart_ops))


CARRIED_TOKENS = (("scroll-price-3", "after-a-deploy-price", PRICE_ASC, 7, "scroll-price-4"),
                  ("scroll-mixed-5", "after-a-deploy-mixed", MIXED, 9, "scroll-mixed-6"))

def build_restart_program(tokens: Mapping[str, str]) -> dict[str, Any]:
    'A fresh process over the same catalogue, asked to honour those tokens.'
    ops: list[dict[str, Any]] = [_store("shop", "autumn"), _service("p1", "shop")]
    ops += [_find(label, "p1", cursor_text=str(tokens[source]), order_by=order_by,
                  limit=limit, mirror=mirror)
            for source, label, order_by, limit, mirror in CARRIED_TOKENS if tokens.get(source)]
    return {"catalogues": {"autumn": CATALOGUES["autumn"]},
            "operations": _phase("after-a-deploy", ops)}


def _browse_program() -> dict[str, Any]:
    ops = [_store("floor", "harvest"), _service("c1", "floor"),
           *_scroll("browse", "c1", PRICE_ASC, 10, 14),


           *_scroll("in-stock-first", "c1", MIXED, 12, 11),
           _find("storefront-page-4", "c1", order_by=PRICE_ASC, limit=10, offset=30)]
    return {"catalogues": {"harvest": CATALOGUES["harvest"]},
            "operations": _phase("browse", ops)}

def _orchard_edits(store, index, rows, delivered, boundary) -> list[dict[str, Any]]:
    "Merchandising's Tuesday, placed against where the customer has reached."
    ahead = [] if boundary is None else [row for row in canonical_order(rows, PRICE_ASC)
                                         if sorts_after(row, boundary, PRICE_ASC)]
    if index == 1:
        return [_add(store, _row("or-8001", int(boundary["price_cents"]) + 25, 7),
                     "tuesday-promotion"),
                _reprice(store, boundary["item_id"],
                         {"stock": (int(boundary["stock"]) + 1) % 11},
                         "boundary-stock-refreshed")]
    if index == 2:
        return [_remove(store, delivered[1]["item_id"], "sold-out-early"),
                _reprice(store, ahead[6]["item_id"], {"stock": 9},
                         "stock-updated-before-anyone-reached-it")]
    if index == 3:
        cheapest = min(row["price_cents"] for row in rows)
        return [_add(store, _row("or-7001", boundary["price_cents"], 5),
                     "restock-at-the-edge", must_reach=True),
                _add(store, _row("or-8002", cheapest - 25, 9), "promotion-priced-wrong")]
    if index == 5:
        return [_remove(store, boundary["item_id"], "sold-out-at-the-edge")]
    if index == 6:
        return [_remove(store, "or-8002", "promotion-pulled-again")]
    return []

def _restock_program() -> dict[str, Any]:
    return {"catalogues": {"orchard": CATALOGUES["orchard"]},
            "operations": _phase("restock", _edited_walk(
                "scroll", "c2", "aisle", "orchard", 10, 11, _orchard_edits))}

def _clients_program() -> dict[str, Any]:
    ops = [_store("floor", "harvest"), _service("c1", "floor"),
           *_scroll("browse", "c1", PRICE_ASC, 10, 2)]


    ops.append(_find("sort-lost-before-the-first-page", "c1", limit=10))
    ops.append(_find("sort-lost-before-the-first-page-app-restarted", "c1",
                     order_by=PRICE_ASC, limit=10))
    for label, _expect, options in _CLIENT_PROBES:
        request = {key: value for key, value in options.items() if key != "minted_under"}
        if "cursor_from" in request:
            request["cursor_from"] = "browse-2"
        request["limit"] = 12 if request.get("order_by") == MIXED else 10
        ops.append(_find(label, "c1", **request))

        ops.append(_find(f"{label}-app-restarted", "c1", order_by=PRICE_ASC, limit=10))
    return {"catalogues": {"harvest": CATALOGUES["harvest"]},
            "operations": _phase("clients", ops)}

def _deploy_program() -> dict[str, Any]:
    ops = [_store("evening", "market"), _service("d1", "evening"),
           *_scroll("evening", "d1", PRICE_ASC, 20, 5),
           _service("d2", "evening", restart=True),
           _find("other-instance", "d2", cursor_from="evening-2",
                 order_by=PRICE_ASC, limit=20, mirror="evening-3"),
           _find("nightly-report", "d1", order_by=PRICE_ASC, limit=200)]
    return {"catalogues": {"market": CATALOGUES["market"]},
            "operations": _phase("deploy", ops)}

PUBLIC_PROGRAMS = {"catalogue-sweep": _browse_program, "restock-mid-scroll": _restock_program,
                   "sort-menu-and-retries": _clients_program, "after-the-deploy": _deploy_program}

def build_program(profile: str) -> dict[str, Any]:
    'The catalogue and the run of requests for one stretch of listing traffic.'
    if profile == "release":
        operations: list[dict[str, Any]] = []
        for name, builder in RELEASE_PHASES:
            operations.extend(_phase(name, builder()))
        return {"catalogues": {name: CATALOGUES[name] for name in ("autumn", "winter", "spring")},
                "operations": operations}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown listing traffic profile: {profile}")
    return builder()
