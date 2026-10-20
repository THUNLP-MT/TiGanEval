'Deterministic entity documents and replay programs for the order platform.'

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

ORDER_PATH = "orders/entities/order.json"
REFUND_PATH = "orders/entities/refund.json"


def _attr(kind: str = "string", **spec: Any) -> dict[str, Any]:
    return {"type": kind, **spec}

def _when(attribute: str, *values: Any) -> list[dict[str, Any]]:
    return [{"attribute": attribute, "values": list(values)}]


SHIPMENT = {
    "name": "shipment",
    "attributes": {
        "shipment_id": _attr(key=True, required=True),
        "phase": _attr(stored_as="ph", required=True, default="packing"),
        "handler": _attr(stored_as="hd"),
        "mode": _attr(stored_as="mdr"),
        "weight_kg": _attr("number", stored_as="wt", required=True),
        "seal_code": _attr(stored_as="sl", required_when=_when("phase", "sealed", "dispatched")),
        "customs_ref": _attr(stored_as="cst", required_when=_when("handler", "air", "sea")),
        "route": _attr("map", stored_as="rt", attributes={
            "mode": _attr(stored_as="md"),
            "bond_ref": _attr(stored_as="bnd", required_when=_when("mode", "bonded")),
            "note": _attr(stored_as="nt"),
        }),
    },
}

CLAIM = {
    "name": "claim",
    "attributes": {
        "claim_id": _attr(key=True, required=True),
        "state": _attr(stored_as="stx", required=True, default="open"),
        "adjuster": _attr(stored_as="adj"),
        "carrier_ref": _attr(stored_as="crf", required_when=_when("state", "filed", "paid")),
        "photo_ref": _attr(stored_as="pht", required_when=_when("adjuster", "field", "remote")),
    },
}


def _load(label: str, entity: str, **where: Any) -> dict[str, Any]:
    return {"type": "load", "label": label, "schema": entity, **where}

def _admit(label: str, entity: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"type": "admit", "label": label, "schema": entity, "payload": dict(payload)}

def _update(label: str, entity: str, key: str, stored: Mapping[str, Any],
            changes: Mapping[str, Any], condition: Any = None,
            bucket: str = "update") -> dict[str, Any]:
    return {"type": "update", "label": label, "schema": entity, "key": key,
            "stored": dict(stored), "changes": dict(changes), "condition": condition,
            "bucket": bucket}

def _read(label: str, entity: str, key: str, stored: Mapping[str, Any],
          projection: Sequence[str] | None = None) -> dict[str, Any]:
    return {"type": "read", "label": label, "schema": entity, "key": key,
            "stored": dict(stored), "projection": list(projection) if projection else None}

def _review(label: str, attributes: Mapping[str, Any], entity: str = "ticket") -> dict[str, Any]:
    return {"type": "review", "label": label,
            "document": {"name": entity, "attributes": dict(attributes)}}

def _equals(path: str, value: Any) -> dict[str, Any]:
    return {"op": "equals", "path": path, "value": value}

def _corpus(entries: Sequence[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"label": label, "payload": payload} for label, payload in entries]


def _labelled(prefix: str, variant: int, key_name: str,
              **constant: Any) -> Callable[..., tuple[str, dict[str, Any]]]:
    'Numbered objects of one entity: `sp-9004` and the fields every one carries.'
    def one(number: int, **fields: Any) -> tuple[str, dict[str, Any]]:
        label = f"{prefix}-{variant}{number:02d}"
        return label, {key_name: label, **constant, **fields}
    return one


def _order_payloads(variant: int) -> list[tuple[str, dict[str, Any]]]:
    one = _labelled("web", variant, "order_id")
    return [
        one(1, status="created", payment_method="card", authorisation_id="AU-1"),
        one(2, status="created", payment_method="invoice"),
        one(3, status="created", payment_method="card"),
        one(4, status="shipped", payment_method="invoice"),
        one(5, status="shipped", payment_method="invoice", tracking_number="TN-5"),
        one(6, payment_method="card", authorisation_id="AU-6"),
        one(7, status="in_transit", payment_method="invoice")]


def _refund_payloads(variant: int) -> list[tuple[str, dict[str, Any]]]:
    one = _labelled("rf", variant, "refund_id")
    return [
        one(1, amount=12, channel="bank", route={"channel": "card"}),
        one(2, amount=30, route={"channel": "bank"}),
        one(3, amount=30, route={"channel": "bank", "account_ref": "IB-9"}),
        one(4, amount=5)]


def _checkout(variant: int) -> list[dict[str, Any]]:
    return [
        _load("order-document", "order", document_path=ORDER_PATH),
        _load("refund-document", "refund", document_path=REFUND_PATH),
        *(_admit(label, "order", payload) for label, payload in _order_payloads(variant)),
        *(_admit(label, "refund", payload) for label, payload in _refund_payloads(variant)),
    ]


def _fulfilment(variant: int) -> list[dict[str, Any]]:
    held = _labelled("ord", variant, "order_id", ccy="EUR")
    plan = [
        ("flip-to-shipped", held(1, st="draft", pm="invoice"), {"set": {"status": "shipped"}}, None),
        ("flip-with-tracking-stored", held(2, st="draft", trk="TN-2"), {"set": {"status": "shipped"}}, None),
        ("flip-and-set-together", held(3, st="draft"), {"set": {"status": "shipped", "tracking_number": "TN-3"}}, None),
        ("drop-tracking-while-shipped", held(4, st="shipped", trk="TN-4"), {"remove": ["tracking_number"]}, None),
        ("drop-tracking-while-draft", held(5, st="draft", trk="TN-5"), {"remove": ["tracking_number"]}, None),
        ("flip-to-in-transit", held(6, st="draft", pm="invoice"), {"set": {"status": "in_transit"}}, None),
        ("carrier-on-shipped", held(7, st="shipped", trk="TN-7"), {"set": {"carrier": "night-line"}}, _equals("st", "draft")),
        ("carrier-on-draft", held(8, st="draft"), {"set": {"carrier": "night-line"}}, _equals("st", "draft")),
        ("switch-to-wallet", held(9, st="draft", pm="card", auth="AU-9"), {"set": {"payment_method": "wallet"}}, None),
        ("switch-to-card", held(10, st="draft", pm="invoice"), {"set": {"payment_method": "card"}}, None),
    ]
    return [
        _load("order-document", "order", document_path=ORDER_PATH),
        *(_update(label, "order", key, item, changes, condition)
          for label, (key, item), changes, condition in plan),
    ]


def _dashboard(variant: int) -> list[dict[str, Any]]:
    held = _labelled("ord", variant, "order_id", ccy="EUR")
    shipped_no_tracking = held(1, st="shipped", pm="invoice")
    complete = held(2, st="shipped", trk="TN-2", car="night-line")
    card_no_auth = held(3, st="draft", pm="card")
    refund_key = f"rf-{variant}04"
    routed = {"refund_id": refund_key, "stt": "opened", "amount": 40, "rt": {"ch": "bank"}}
    return [
        _load("order-document", "order", document_path=ORDER_PATH),
        _load("refund-document", "refund", document_path=REFUND_PATH),
        _read("open-list-row", "order", *shipped_no_tracking),
        _read("complete-row", "order", *complete),
        _read("payment-row", "order", *card_no_auth),
        _read("refund-row", "refund", refund_key, routed),
        _read("open-list-projection", "order", *shipped_no_tracking, projection=["order_id", "status"]),
        _read("carrier-projection", "order", *complete, projection=["order_id", "carrier"]),
        _read("refund-projection", "refund", refund_key, routed, projection=["refund_id", "route"]),
        _update("support-sets-carrier", "order", *shipped_no_tracking, {"set": {"carrier": "postal"}}, bucket="legacy"),
        _update("support-adds-tracking", "order", *shipped_no_tracking, {"set": {"tracking_number": "TN-fix"}}, bucket="legacy"),
        _update("support-fixes-currency", "order", *card_no_auth, {"set": {"currency": "USD"}}, bucket="legacy"),
    ]


_BASE = {"ticket_id": _attr(key=True, required=True), "state": _attr(stored_as="stt", required=True)}
_OWNER = {"owner": _attr(stored_as="ow")}
_CONSIGNMENT = {"consignment_id": _attr(key=True, required=True),
                "stage": _attr(stored_as="stg", required=True)}
_DESK = {"desk": _attr(stored_as="dsk")}


def _rehearsal_drafts() -> list[dict[str, Any]]:
    'The queue the rehearsal reviews: the same categories under other names.'

    def draft(label: str, **attributes: Any) -> dict[str, Any]:
        return _review(label, {**_CONSIGNMENT, **attributes}, entity="consignment")
    def handover(**attributes: Any) -> dict[str, Any]:
        return _attr("map", stored_as="hv", attributes={**_DESK, **attributes})

    return [
        draft("physical-name-reused", stage_copy=_attr(stored_as="stg")),
        _review("document-without-a-key", {"stage": _attr(stored_as="stg", required=True)}, entity="consignment"),
        _review(
            "document-with-two-keys",
            {**_CONSIGNMENT, "external_id": _attr(key=True, required=True)},
            entity="consignment",
        ),
        draft("carrier-name-misspelt", dispatch_note=_attr(stored_as="dn", required_when=_when("carriar", "held"))),
        draft("declared-on-itself", hold_code=_attr(stored_as="hc", required_when=_when("hold_code", "held"))),
        draft("map-reaches-the-top", handover=handover(signed_by=_attr(stored_as="sb", required_when=_when("stage", "closed")))),
        draft("declared-on-the-key", consignment_id=_attr(key=True, required=True, required_when=_when("stage", "closed"))),
        draft("controller-further-down", seal_note=_attr(stored_as="sn", required_when=_when("seal_flag", "yes")), seal_flag=_attr(stored_as="sf")),
        draft("pair-within-the-map", handover=handover(desk_note=_attr(stored_as="dnt", required_when=_when("desk", "night")))),
    ]


def _drafts() -> list[dict[str, Any]]:
    'The queue the publication record replays.'

    def draft(label: str, **attributes: Any) -> dict[str, Any]:
        return _review(label, {**_BASE, **attributes})
    def escalation(**attributes: Any) -> dict[str, Any]:
        return _attr("map", stored_as="esc", attributes={**_OWNER, **attributes})

    return [
        draft("misspelt-sibling", closed_by=_attr(stored_as="cb", required_when=_when("statee", "closed"))),
        draft("names-itself", hold_reason=_attr(stored_as="hr", required_when=_when("hold_reason", "held"))),
        draft("reaches-out-of-its-map", escalation=escalation(handover_note=_attr(stored_as="hn", required_when=_when("state", "closed")))),
        draft("pair-on-the-key", ticket_id=_attr(key=True, required=True, required_when=_when("state", "closed"))),
        draft("controller-declared-later", gift_note=_attr(stored_as="gn", required_when=_when("gift_flag", "yes")), gift_flag=_attr(stored_as="gf")),
        draft("two-attributes-one-physical-name", closed_at=_attr(stored_as="stt")),
        draft("plain-new-pair", reason_code=_attr(stored_as="rc"), reason_note=_attr(stored_as="rn", required_when=_when("reason_code", "other", "duplicate"))),
        draft("pair-inside-a-map", escalation=escalation(owner_note=_attr(stored_as="on", required_when=_when("owner", "duty-manager")))),
    ]


def _publication(variant: int) -> list[dict[str, Any]]:
    orders, refunds = _corpus(_order_payloads(variant)), _corpus(_refund_payloads(variant))
    return [
        _load("order-document", "order", document_path=ORDER_PATH),
        _load("refund-document", "refund", document_path=REFUND_PATH),
        {"type": "publish", "label": "partner-contract-order", "schema": "order", "payloads": orders},
        {"type": "rebuild", "label": "worker-rebuild-order", "schema": "order", "payloads": orders},
        {"type": "publish", "label": "partner-contract-refund", "schema": "refund", "payloads": refunds},
        {"type": "rebuild", "label": "worker-rebuild-refund", "schema": "refund", "payloads": refunds},
        *_drafts(),
    ]


def _shipment_payloads(variant: int) -> list[tuple[str, dict[str, Any]]]:
    one = _labelled("sp", variant, "shipment_id", weight_kg=6)
    return [
        one(1, phase="packing", handler="road"), one(2, phase="sealed"),
        one(3, phase="sealed", seal_code="SC-3"), one(4, handler="air"),
        one(5, handler="air", customs_ref="CR-5"), one(7, route={"mode": "bonded"}),
        one(6, handler="road", mode="bonded", route={"mode": "plain"}),
        one(8, route={"mode": "bonded", "bond_ref": "BR-8"}), one(10, handler="road"),
        one(9, phase="dispatched", seal_code="SC-9", handler="sea", customs_ref="CR-9")]


def _claim_payloads(variant: int) -> list[tuple[str, dict[str, Any]]]:
    one = _labelled("cl", variant, "claim_id")
    return [one(1, state="open", adjuster="desk"), one(2, state="filed"),
            one(3, state="filed", carrier_ref="CF-3"), one(4, adjuster="field"),
            one(5, adjuster="field", photo_ref="PH-5"), one(6)]


def _rehearsal(variant: int) -> list[dict[str, Any]]:
    held = _labelled("sh", variant, "shipment_id", wt=12)
    writes = [
        ("seal-the-shipment", held(1, ph="packing"), {"set": {"phase": "sealed"}}, None, "update"),
        ("seal-with-code-stored", held(2, ph="packing", sl="SC-2"), {"set": {"phase": "sealed"}}, None, "update"),
        ("seal-and-code-together", held(3, ph="packing"), {"set": {"phase": "sealed", "seal_code": "SC-3"}}, None, "update"),
        ("drop-code-while-sealed", held(4, ph="sealed", sl="SC-4"), {"remove": ["seal_code"]}, None, "update"),
        ("drop-code-while-packing", held(5, ph="packing", sl="SC-5"), {"remove": ["seal_code"]}, None, "update"),
        ("dispatch-the-shipment", held(6, ph="packing"), {"set": {"phase": "dispatched"}}, None, "update"),
        ("hand-to-air", held(7, ph="packing", hd="road"), {"set": {"handler": "air"}}, None, "update"),
        ("hand-to-air-with-ref", held(8, ph="packing", hd="road", cst="CR-8"), {"set": {"handler": "air"}}, None, "update"),
        ("bond-the-route", held(9, ph="packing", rt={"md": "plain"}), {"set": {"route.mode": "bonded"}}, None, "update"),
        ("bond-with-ref-stored", held(10, ph="packing", rt={"md": "plain", "bnd": "BR-10"}), {"set": {"route.mode": "bonded"}}, None, "update"),
        ("seal-with-null-code-stored", held(23, ph="packing", sl=None), {"set": {"phase": "sealed"}}, None, "update"),
        ("clear-code-with-null", held(24, ph="sealed", sl="SC-24"), {"set": {"seal_code": None}}, None, "update"),
        ("clear-code-with-null-while-packing", held(29, ph="packing", sl="SC-29"), {"set": {"seal_code": None}}, None, "update"),
        ("replace-route-with-bonded", held(25, ph="packing", rt={"md": "plain"}), {"set": {"route": {"mode": "bonded"}}}, None, "update"),
        ("replace-route-with-complete-bonded", held(26, ph="packing", rt={"md": "plain"}), {"set": {"route": {"mode": "bonded", "bond_ref": "BR-26"}}}, None, "update"),
        ("replace-route-with-plain", held(27, ph="packing", rt={"md": "bonded", "bnd": "BR-27"}), {"set": {"route": {"mode": "plain"}}}, None, "update"),
        ("note-on-sealed", held(11, ph="sealed", sl="SC-11"), {"set": {"route.note": "left bay"}}, _equals("ph", "packing"), "update"),
        ("note-on-packing", held(12, ph="packing"), {"set": {"route.note": "left bay"}}, _equals("ph", "packing"), "update"),
        ("weigh-a-legacy-shipment", held(13, ph="sealed"), {"set": {"weight_kg": 30}}, None, "legacy"),
        ("code-a-legacy-shipment", held(14, ph="dispatched"), {"set": {"seal_code": "SC-14"}}, None, "legacy"),
        ("mode-on-a-legacy-shipment", held(15, ph="packing", hd="air", rt={"md": "bonded"}), {"set": {"mode": "road"}}, None, "legacy"),
    ]
    reads = [
        ("sealed-without-a-code", held(16, ph="sealed"), None),
        ("air-without-customs", held(17, ph="packing", hd="air"), None),
        ("bonded-without-ref", held(18, ph="packing", rt={"md": "bonded", "nt": "bay 4"}), None),
        ("complete-shipment", held(19, ph="sealed", sl="SC-19", hd="road"), None),
        ("phase-column", held(20, ph="sealed"), ["shipment_id", "phase"]),
        ("weight-column", held(21, ph="sealed", hd="air"), ["shipment_id", "weight_kg"]),
        ("route-column", held(22, ph="packing", rt={"md": "bonded"}), ["shipment_id", "route"]),
        ("route-mode-column", held(28, ph="packing", rt={"md": "bonded", "nt": "bay 8"}), ["shipment_id", "route.mode"]),
    ]
    shipments = _corpus(_shipment_payloads(variant))
    claims = _corpus(_claim_payloads(variant))
    return [
        _load("shipment-document", "shipment", document=SHIPMENT),
        _load("claim-document", "claim", document=CLAIM),
        *(_admit(label, "shipment", payload) for label, payload in _shipment_payloads(variant)),
        *(_admit(label, "claim", payload) for label, payload in _claim_payloads(variant)),
        *(_update(label, "shipment", key, item, changes, condition, bucket)
          for label, (key, item), changes, condition, bucket in writes),
        *(_read(label, "shipment", key, item, projection)
          for label, (key, item), projection in reads),
        {"type": "publish", "label": "shipment-contract", "schema": "shipment", "payloads": shipments},
        {"type": "rebuild", "label": "shipment-rebuild", "schema": "shipment", "payloads": shipments},
        {"type": "publish", "label": "claim-contract", "schema": "claim", "payloads": claims},
        {"type": "rebuild", "label": "claim-rebuild", "schema": "claim", "payloads": claims},
        *_rehearsal_drafts(),
    ]


PROGRAM_BUILDERS = {"checkout": _checkout, "fulfilment": _fulfilment,
                    "dashboard": _dashboard, "publication": _publication,
                    "rehearsal": _rehearsal}


def build_program(profile: str, variant: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown replay profile: {profile}")
    return [{"phase": profile, **event} for event in builder(int(variant))]
