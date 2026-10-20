'Deterministic caller directories and recorded windows for the summary relay.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _desk(tenant: str, clearance: str, documents: Sequence[str]) -> dict[str, Any]:
    return {"tenant": tenant, "clearance": clearance, "documents": tuple(documents)}


PUBLIC_DOCUMENTS = ("contract-8814", "invoice-2291")
PRIVATE_DOCUMENTS = ("policy-5507", "renewal-6132")

PUBLIC_DIRECTORY: Mapping[str, Mapping[str, Any]] = {
    "atlas-billing-1": _desk("atlas", "standard", PUBLIC_DOCUMENTS),
    "atlas-billing-2": _desk("atlas", "standard", PUBLIC_DOCUMENTS),
    "atlas-billing-3": _desk("atlas", "standard", PUBLIC_DOCUMENTS),
    "atlas-legal-1": _desk("atlas", "restricted", PUBLIC_DOCUMENTS),
    "brightline-ap-1": _desk("brightline", "standard", PUBLIC_DOCUMENTS),
    "brightline-ap-2": _desk("brightline", "standard", PUBLIC_DOCUMENTS),
    "norsk-temp-1": _desk("norsk", "standard", ("invoice-2291",)),
}

PRIVATE_DIRECTORY: Mapping[str, Mapping[str, Any]] = {
    "vega-desk-1": _desk("vega", "standard", PRIVATE_DOCUMENTS),
    "vega-desk-2": _desk("vega", "standard", PRIVATE_DOCUMENTS),
    "vega-desk-3": _desk("vega", "standard", PRIVATE_DOCUMENTS),
    "vega-audit-1": _desk("vega", "restricted", PRIVATE_DOCUMENTS),
    "halcyon-desk-1": _desk("halcyon", "standard", PRIVATE_DOCUMENTS),
    "halcyon-desk-2": _desk("halcyon", "standard", PRIVATE_DOCUMENTS),
    "halcyon-desk-3": _desk("halcyon", "standard", PRIVATE_DOCUMENTS),
    "halcyon-intern-1": _desk("halcyon", "standard", ("renewal-6132",)),
}


DESK_THE_DIRECTORY_DROPPED = "vega-desk-4"


def _call(call_id: str, principal: str, document_id: str) -> dict[str, Any]:
    ordinal = int("".join(char for char in call_id if char.isdigit()) or 0)
    return {
        "type": "call",
        "call_id": call_id,
        "principal": principal,
        "document_id": document_id,
        "request_id": f"rq-{call_id}-{ordinal * 37 % 991:03d}",
        "trace_id": f"tr-{ordinal * 53 % 877:03d}",
        "retry_budget": 1 + ordinal % 3,
    }


def _burst(prefix: str, start: int, principals: Sequence[str], document_id: str,
           count: int) -> list[dict[str, Any]]:
    return [
        _call(f"{prefix}{start + offset}", principals[offset % len(principals)], document_id)
        for offset in range(count)
    ]


def _window(label: str, events: Sequence[Mapping[str, Any]],
            handover: str = "in-turn") -> dict[str, Any]:
    'One replayed window, and the order the connection handed its pieces over.'

    return {"label": label, "handover": handover,
            "events": [dict(event) for event in events]}


ATLAS_STANDARD = ("atlas-billing-1", "atlas-billing-2", "atlas-billing-3")
VEGA_STANDARD = ("vega-desk-1", "vega-desk-2", "vega-desk-3")
HALCYON_STANDARD = ("halcyon-desk-1", "halcyon-desk-2", "halcyon-desk-3")


def _invoice_run_spike() -> list[dict[str, Any]]:
    return [
        _window(
            "invoice-run",
            [
                *_burst("c", 1, ATLAS_STANDARD, "invoice-2291", 10),
                {"type": "advance", "chunks": 2},
                *_burst("c", 11, ATLAS_STANDARD, "invoice-2291", 4),
                {"type": "drain"},
            ],
        )
    ]


def _two_desks_one_contract() -> list[dict[str, Any]]:
    return [
        _window(
            "same-contract",
            [
                _call("d1", "atlas-billing-1", "contract-8814"),
                _call("d2", "brightline-ap-1", "contract-8814"),
                _call("d3", "atlas-legal-1", "contract-8814"),
                _call("d4", "brightline-ap-2", "contract-8814"),
                _call("d5", "norsk-temp-1", "contract-8814"),
                {"type": "drain"},
            ],
        )
    ]


def _backend_outage_window() -> list[dict[str, Any]]:
    return [
        _window(
            "outage",
            [
                *_burst("e", 1, ATLAS_STANDARD, "invoice-2291", 6),
                {"type": "advance", "chunks": 1},
                {"type": "fail", "reason": "backend_overloaded"},
            ],
        ),


        _window(
            "after-the-outage",
            [
                *_burst("e", 7, ATLAS_STANDARD, "invoice-2291", 3),
                {"type": "drain"},
            ],
            handover="out-of-turn",
        ),
    ]


def _handover_drop() -> list[dict[str, Any]]:
    return [
        _window(
            "handover",
            [
                *_burst("f", 1, ATLAS_STANDARD, "contract-8814", 3),
                {"type": "advance", "chunks": 1},
                {"type": "abandon", "call_id": "f1"},


                _call("f4", "atlas-billing-1", "contract-8814"),
                {"type": "drain"},
            ],
        ),
        _window(
            "later-that-hour",
            [
                _call("f5", "atlas-billing-2", "contract-8814"),
                {"type": "drain"},
            ],
        ),
        _window(
            "one-desk-walks-away",
            [


                _call("f6", "atlas-billing-3", "invoice-2291"),
                {"type": "advance", "chunks": 1},
                {"type": "abandon", "call_id": "f6"},
                _call("f7", "atlas-billing-1", "invoice-2291"),
                {"type": "drain"},
            ],
        ),
    ]


def _release() -> list[dict[str, Any]]:
    return [
        _window(
            "shared-policy",
            [
                _call("p9", "vega-desk-1", "policy-5507"),
                _call("p10", "vega-audit-1", "policy-5507"),
                _call("p11", "halcyon-desk-1", "policy-5507"),
                _call("p12", "vega-desk-2", "policy-5507"),
                _call("p13", "halcyon-intern-1", "policy-5507"),
                {"type": "drain"},
            ],
        ),
        _window(
            "morning-rush",
            [
                *_burst("p", 1, VEGA_STANDARD, "policy-5507", 6),
                {"type": "advance", "chunks": 2},
                *_burst("p", 7, VEGA_STANDARD, "policy-5507", 2),
                {"type": "drain"},
            ],
            handover="out-of-turn",
        ),
        _window(
            "renewal-outage",
            [
                *_burst("p", 14, HALCYON_STANDARD, "renewal-6132", 5),
                {"type": "advance", "chunks": 1},
                {"type": "fail", "reason": "backend_overloaded"},
            ],
        ),
        _window(
            "after-the-outage",
            [
                *_burst("p", 19, HALCYON_STANDARD, "renewal-6132", 4),
                {"type": "drain"},
            ],
        ),
        _window(
            "handover",
            [
                *_burst("p", 23, VEGA_STANDARD, "policy-5507", 3),
                {"type": "advance", "chunks": 1},
                {"type": "abandon", "call_id": "p23"},
                _call("p26", "vega-desk-1", "policy-5507"),
                {"type": "drain"},
            ],
        ),
        _window(
            "one-desk-walks-away",
            [
                _call("p27", "halcyon-desk-1", "policy-5507"),
                {"type": "advance", "chunks": 1},
                {"type": "abandon", "call_id": "p27"},
                _call("p28", "halcyon-desk-2", "policy-5507"),
                {"type": "drain"},
            ],
        ),
        _window(
            "a-desk-that-was-closed",
            [
                _call("p29", "vega-desk-2", "policy-5507"),


                _call("p30", DESK_THE_DIRECTORY_DROPPED, "policy-5507"),
                {"type": "advance", "chunks": 1},
                _call("p31", "vega-desk-3", "policy-5507"),
                {"type": "drain"},
            ],
        ),
    ]


PROGRAMME_BUILDERS = {
    "invoice-run-spike": (_invoice_run_spike, PUBLIC_DIRECTORY),
    "two-desks-one-contract": (_two_desks_one_contract, PUBLIC_DIRECTORY),
    "backend-outage-window": (_backend_outage_window, PUBLIC_DIRECTORY),
    "handover-drop": (_handover_drop, PUBLIC_DIRECTORY),
    "release": (_release, PRIVATE_DIRECTORY),
}


def build_programme(profile: str) -> dict[str, Any]:
    'Return one whole programme: the caller directory plus its windows.'

    entry = PROGRAMME_BUILDERS.get(profile)
    if entry is None:
        raise ValueError(f"unknown relay programme: {profile}")
    builder, directory = entry
    return {
        "profile": profile,
        "directory": {name: dict(desk) for name, desk in directory.items()},
        "windows": builder(),
    }


def _reorder(events: Sequence[Mapping[str, Any]], how: str) -> list[dict[str, Any]]:
    'Reorder each unbroken run of arrivals; leave every other event in place.'

    output: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []

    def flush() -> None:
        if not run:
            return
        if how == "reversed":
            ordered = list(reversed(run))
        elif how == "rotated":
            ordered = run[1:] + run[:1]
        else:
            ordered = list(run)
        output.extend(ordered)
        run.clear()

    for raw in events:
        event = dict(raw)
        if str(event.get("type")) == "call":
            run.append(event)
            continue
        flush()
        output.append(event)
    flush()
    return output


def _widen(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    "Move where the backend's pieces land relative to the arrivals."

    output = []
    for raw in events:
        event = dict(raw)
        if str(event.get("type")) == "advance":
            event["chunks"] = int(event.get("chunks", 1)) + 1
        output.append(event)
    return output


ARRIVAL_VARIANTS: tuple[str, ...] = ("as-recorded", "reversed", "rotated", "wider-pieces")


def variant_of(programme: Mapping[str, Any], variant: str) -> dict[str, Any]:
    windows = []
    for window in programme["windows"]:
        events = list(window["events"])
        if variant in ("reversed", "rotated"):
            events = _reorder(events, variant)
        elif variant == "wider-pieces":
            events = _widen(events)
        windows.append({
            "label": window["label"],
            "handover": window.get("handover", "in-turn"),
            "events": events,
        })
    return {
        "profile": programme["profile"],
        "variant": variant,
        "directory": dict(programme["directory"]),
        "windows": windows,
    }
