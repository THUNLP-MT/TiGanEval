'Deterministic relay traffic: host fleets, grant schedules, request schedules.'

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence


_EPOCH = datetime(1970, 1, 1)
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def stamp_text(seconds: float) -> str:
    'A moment written the way a host writes it, comma and all.'

    at = _EPOCH + timedelta(seconds=int(seconds))
    return (f"{_DAYS[at.weekday()]}, {at.day:02d} {_MONTHS[at.month - 1]} {at.year} "
            f"{at.hour:02d}:{at.minute:02d}:{at.second:02d} GMT")


BASE_S = (datetime(2030, 11, 5, 8, 0, 0) - _EPOCH).total_seconds()
PROFILE: Mapping[str, Any] = {"name": "sweep", "max_grants_per_scope": 6}


def _host(origin: str, **spec: Any) -> dict[str, Any]:
    return {origin: {
        "session_name": spec.get("session_name", ""),
        "needs_session_under": list(spec.get("needs_session_under", ())),
        "issued": dict(spec.get("issued", {})),
        "hands_out": dict(spec.get("hands_out", {})),
        "folds": bool(spec.get("folds", False)),
        "max_header_bytes": int(spec.get("max_header_bytes", 400)),
    }}


def _at(seconds: float) -> dict[str, Any]:
    return {"op": "at", "to": float(seconds), "label": f"clock-{int(seconds)}"}


def _get(label: str, url: str, phase: str, entered_as: str = "") -> dict[str, Any]:
    return {"op": "get", "label": label, "url": url, "phase": phase, "entered_as": entered_as}


def _program(hosts: Mapping[str, Any], operations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"start_s": BASE_S, "profile": dict(PROFILE), "hosts": dict(hosts),
            "operations": [dict(op) for op in operations]}


def _audience(family: str, partner: str, lookalike: str, tag: str) -> tuple[dict, list]:
    desk, files, wing = (
        f"https://desk.{family}", f"https://files.{family}", f"https://wing.{family}"
    )
    hosts = {
        **_host(f"{desk}:443", session_name="sid", needs_session_under=["/desk"],
                issued={"D1": {"desk": "grounds"}, "R4": {}, "K2": {}, "Z7": {}},
                hands_out={"/signin": [[f"sid=D1; Scope={family}; Under=/; Sealed"]],
                           "/open": [["room=R4; Under=/open"]],
                           "/desk/tools/list": [["kit=K2"]],
                           "/odd/path/item": [["trail=Z7; Under=relative"]]}),
        **_host(f"http://desk.{family}:80"),
        **_host(f"{files}:443", session_name="sid", needs_session_under=["/"],
                issued={"D1": {"desk": "grounds"}}),
        **_host(f"https://{lookalike}:443"),
        **_host(f"https://{partner}:443"),
        **_host(f"{wing}:443"),
    }
    steps = (
        ("signin", f"{desk}/signin"), ("desk", f"{desk}/desk/home"),
        ("files", f"{files}/bundle"), ("lookalike", f"https://{lookalike}/index"),
        ("partner", f"https://{partner}/ping"), ("plain", f"http://desk.{family}/legacy"),
        ("open", f"{desk}/open"), ("open-plan", f"{desk}/open/plan"),
        ("openroom", f"{desk}/openroom/index"), ("tools", f"{desk}/desk/tools/list"),
        ("tools-edit", f"{desk}/desk/tools/edit"), ("desk-other", f"{desk}/desk/other"),
        ("odd-set", f"{desk}/odd/path/item"), ("odd-check", f"{desk}/odd/path/next"),
        ("sibling-open", f"{wing}/open/plan"),
        ("sibling-tools", f"{wing}/desk/tools/edit"),
        ("sibling-trail", f"{wing}/odd/path/next"),
    )
    operations = [_at(BASE_S)]
    operations += [_get(f"{tag}-{name}", url, "audience") for name, url in steps]
    return hosts, operations


def _lifetime(family: str, tag: str, start: float) -> tuple[dict, list]:
    gate = f"https://gate.{family}"
    slip_until = start + 1200.0
    hosts = _host(
        f"{gate}:443", session_name="pass", needs_session_under=["/work"],
        issued={"P1": {"desk": "gate", "until_s": start + 600.0},
                "P2": {"desk": "gate", "until_s": start + 761.0},
                "P3": {"desk": "gate", "until_s": start + 951.0},
                "S9": {"until_s": slip_until}, "N5": {}},
        hands_out={
            "/signin": [
                [f"pass=P1; Scope={family}; Under=/; Ttl=600"],
                [f"pass=P2; Scope={family}; Under=/; Ttl=60; Until={stamp_text(start + 90000.0)}"],
                [f"pass=P3; Scope={family}; Under=/"],
                [f"slip=S9; Under=/; Until={stamp_text(slip_until)}"],
            ],
            "/logout": [[f"pass=; Scope={family}; Ttl=0"]],
            "/odd": [["note=N5; Under=/; Until=next Tuesday"]],
        })
    steps = (
        (0, "signin", "/signin"), (100, "early", "/work"),
        (600, "at-deadline", "/work"), (700, "late", "/work"),
        (701, "signin-2", "/signin"), (900, "after-ttl", "/work"),
        (901, "signin-3", "/signin"), (902, "work-3", "/work"),
        (950, "logout", "/logout"), (960, "after-logout", "/work"),
        (970, "odd", "/odd"), (980, "odd-check", "/notes"), (990, "slip", "/signin"),
        (1000, "slip-early", "/notes"), (1300, "slip-late", "/notes"),
    )
    operations: list[dict[str, Any]] = []
    for offset, name, path in steps:
        operations += [_at(start + offset), _get(f"{tag}-{name}", f"{gate}{path}", "lifetime")]
    return hosts, operations


FOLD_HITS = (("grip=G1; Under=/pack; Until=STAMP", "clip=C1; Under=/"),
             ("= ; broken", "tape=T1; Under=/"))


def _folding(origin_site: str, edge_site: str, tag: str, start: float) -> tuple[dict, list]:
    hands_out = {"/pack/item": [[line.replace("STAMP", stamp_text(start + 90000.0))
                                 for line in hit] for hit in FOLD_HITS]}
    issued = {"G1": {}, "C1": {}, "T1": {}}
    hosts: dict[str, Any] = {}
    operations: list[dict[str, Any]] = [_at(start)]
    for side, family, folds in (("plain", origin_site, False), ("edge", edge_site, True)):
        origin = f"https://{side}.{family}"
        hosts.update(_host(f"{origin}:443", issued=issued, hands_out=hands_out, folds=folds))
        operations += [_get(f"{tag}-{side}-{letter}", f"{origin}/pack/item", "folding")
                       for letter in ("a", "b", "c")]
    return hosts, operations


def _order(family: str, tag: str, start: float) -> tuple[dict, list]:
    board = f"https://board.{family}"
    hosts = _host(
        f"{board}:443", session_name="tag", needs_session_under=["/desk"],
        issued={"BB": {"desk": "team-b"}, "BW": {"desk": "grounds"}, "BX": {"desk": "swap"}},
        hands_out={"/team-b/setup": [["tag=BB; Under=/team-b"]],
                   "/enter": [[f"tag=BW; Scope={family}; Under=/"]] * 2,
                   "/enter2": [[f"tag=BX; Scope=board.{family}; Under=/"]]})
    steps = (("team-setup", "/team-b/setup", "team-b"), ("enter", "/enter", "grounds"),
             ("team-report", "/team-b/report", "team-b"), ("enter2", "/enter2", "swap"),
             ("desk-a", "/desk/home", "swap"), ("refresh", "/enter", "grounds"),
             ("desk-b", "/desk/home", "grounds"))
    operations = [_at(start)]
    operations += [_get(f"{tag}-{name}", f"{board}{path}", "order", desk)
                   for name, path, desk in steps]
    return hosts, operations


def _identity(
    family: str, tile_site: str, tag: str, start: float, tiles: int, limit: int
) -> tuple[dict, list]:
    ledger, tile_host = f"https://ledger.{family}", f"https://tiles.{tile_site}"
    hosts = {
        **_host(f"{ledger}:443", session_name="key", needs_session_under=["/ledger"],
                issued={"K1": {"desk": "books", "until_s": start + 40.0},
                        "K2": {"desk": "books"}},
                hands_out={"/signin": [[f"key=K1; Scope=ledger.{family}; Under=/ledger"]],
                           "/refresh": [[f"key=K1; Scope=ledger.{family}; Under=/ledger"],
                                        [f"key=K2; Scope=ledger.{family}; Under=/ledger"]]}),
        **_host(f"{tile_host}:443", max_header_bytes=200,
                issued={f"T{index}": {} for index in range(1, tiles + 1)},
                hands_out={
                    "/tile": [[f"tile{index}=T{index}; Scope=tiles.{tile_site}; Under=/"]
                              for index in range(1, tiles + 1)],
                    "/retire": [[
                        f"tile{index}=; Scope=tiles.{tile_site}; Under=/; Ttl=0"
                        for index in range(tiles - limit + 2, tiles + 1)
                    ]],
                }),
    }
    operations = [_at(start)]
    operations += [_get(f"{tag}-{name}", f"{ledger}{path}", "identity")
                   for name, path in (("signin", "/signin"), ("reissue-same", "/refresh"),
                                      ("probe-1", "/ledger/read"))]
    operations.append(_at(start + 50))
    operations += [_get(f"{tag}-{name}", f"{ledger}{path}", "identity")
                   for name, path in (("reissue-new", "/refresh"), ("probe-2", "/ledger/read"))]
    operations += [_get(f"{tag}-tile-{index:02d}", f"{tile_host}/tile", "identity")
                   for index in range(1, tiles + 1)]
    operations.append(_get(f"{tag}-tile-probe", f"{tile_host}/tile", "identity"))
    operations.append(_get(f"{tag}-retire", f"{tile_host}/retire", "identity"))
    operations.append(_get(f"{tag}-retire-probe", f"{tile_host}/check", "identity"))
    operations.append(_get(f"{tag}-key-after", f"{ledger}/ledger/read", "identity"))
    return hosts, operations


def _release_program() -> dict[str, Any]:
    hosts: dict[str, Any] = {}
    operations: list[dict[str, Any]] = []
    for built, ops in (
        _audience("grounds.example", "counts.audit.example", "newgrounds.example", "audience"),
        _lifetime("tally.example", "life", BASE_S + 3600),
        _folding("pack.example", "wrap.example", "fold", BASE_S + 7200),
        _order("roster.example", "order", BASE_S + 10800),
        _identity("books.example", "plate.example", "ident", BASE_S + 14400, 30, 5),
    ):
        hosts.update(built)
        operations.extend(ops)
    program = _program(hosts, operations)
    program["profile"]["max_grants_per_scope"] = 5
    return program


def _audit_program() -> dict[str, Any]:
    hosts, operations = _order("desks.example", "desk", BASE_S)
    more_hosts, more_ops = _identity(
        "folio.example", "slate.example", "book", BASE_S + 600, 20, 6
    )
    hosts.update(more_hosts)
    operations.extend(more_ops)
    return _program(hosts, operations)


PUBLIC_PROGRAMS = {
    "sweep": lambda: _program(
        *_audience("vendor.example", "metrics.partner.example", "newvendor.example", "sweep")),
    "edge": lambda: _program(*_folding("assets.example", "mirror.example", "asset", BASE_S)),
    "rotation": lambda: _program(*_lifetime("portal.example", "turn", BASE_S)),
    "audit": _audit_program,
}


def build_program(profile: str) -> dict[str, Any]:
    'The host fleet and the schedule of requests for one stretch of traffic.'

    if profile == "release":
        return _release_program()
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown relay traffic profile: {profile}")
    return builder()
