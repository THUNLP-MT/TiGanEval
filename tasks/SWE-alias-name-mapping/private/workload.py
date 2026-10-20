'Deterministic intake runs: shapes, partner configurations, posted payloads.'

from __future__ import annotations

from typing import Any, Mapping


def _fields(*rows: tuple[str, str, bool, Any]) -> list[dict[str, Any]]:
    return [dict(zip(("id", "kind", "required", "default"), row)) for row in rows]

ORDER = {
    "name": "order",
    "fields": _fields(
        ("order_id", "text", True, None), ("user_id", "text", True, None),
        ("order_ts", "number", True, None), ("amount", "number", True, None),
        ("note", "text", False, ""), ("from_", "text", False, "")),
}

SHIPMENT = {
    "name": "shipment",
    "fields": _fields(
        ("shipment_id", "text", True, None), ("carrier_id", "text", True, None),
        ("dispatched_at", "number", True, None), ("weight_kg", "number", True, None),
        ("ref_", "text", False, ""), ("signed", "flag", False, False)),
}

HOUSE: Mapping[str, Any] = {"name_style": "snake_case"}
_HAULIER = {"aliases": {"carrier_id": ["scac", "carrier"], "weight_kg": ["kg"]}}

PRIVATE_CONFIGS: Mapping[str, list[Mapping[str, Any]]] = {
    "northgate": [HOUSE, {"alias_style": "camelCase"}],
    "pellworm": [HOUSE, {"rename": {"carrier_id": "scac"}, "alias_style": "camelCase"}],
    "quill": [HOUSE, {"name_style": "camelCase", "trim_trailing_underscore": True,
                      "aliases": {"ref_": ["ref_"], "weight_kg": ["weight_total"]}}],
    "ravel": [HOUSE, _HAULIER],
    "sable": [HOUSE, _HAULIER, {"extra_policy": "forbid"}],
    "tessel": [HOUSE, _HAULIER, {"extra_policy": "collect", "extra_in": "extra"}],
    "vesper": [HOUSE, {"aliases": {"weight_kg": ["kg"]}}, {"rename": {"weight_kg": "kg"}}],
    "tarn": [HOUSE, {"aliases": {"shipment_id": ["ref"], "ref_": ["ref"]}}],
    "umbra": [HOUSE, {"aliases": {"weight_kg": ["carrier_id"]}}],
    "wold": [HOUSE, {"aliases": {"carrier_id": ["weightKg"]},
                       "alias_style": "camelCase"}],
    "yarrow": [HOUSE, {"alias_style": ["camelCase", "kebab-case"]}],
}

PUBLIC_CONFIGS: Mapping[str, list[Mapping[str, Any]]] = {
    "house": [HOUSE],
    "atlas": [HOUSE, {"alias_style": "camelCase"}],
    "borea": [HOUSE, {"aliases": {"user_id": ["uid", "userId"], "amount": ["amt"]}}],
    "borea_strict": [HOUSE, {"aliases": {"user_id": ["uid", "userId"], "amount": ["amt"]},
                             "extra_policy": "forbid"}],
    "borea_collect": [HOUSE, {"aliases": {"user_id": ["uid", "userId"], "amount": ["amt"]},
                              "extra_policy": "collect", "extra_in": "extra"}],
    "cygnet": [HOUSE, {"rename": {"user_id": "usr"}, "alias_style": "camelCase"}],
    "dorado": [HOUSE, {"name_style": "camelCase", "trim_trailing_underscore": True,
                       "aliases": {"order_ts": ["order_ts_"], "amount": ["amount_total"]}}],
    "twin": [HOUSE, {"aliases": {"order_id": ["ref"], "from_": ["ref"]}}],
    "overlap": [HOUSE, {"aliases": {"amount": ["order_ts"]}}],
    "legacy": [HOUSE, {"aliases": {"amount": ["amt"]}}, {"rename": {"amount": "amt"}}],
}


def _build(config: str) -> dict[str, Any]:
    return {"op": "build", "label": f"build-{config}", "config": config}

def _load(label: str, config: str, **keys: Any) -> dict[str, Any]:
    return {"op": "load", "label": label, "config": config, "payload": {"record": dict(keys)}}

def _raw(label: str, config: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "load", "label": label, "config": config, "payload": dict(payload)}

def _schema(label: str, config: str) -> dict[str, Any]:
    return {"op": "schema", "label": label, "config": config}

def _dump(label: str, config: str, record: Mapping[str, Any]) -> dict[str, Any]:
    return {"op": "dump", "label": label, "config": config, "record": dict(record)}

_SHIPMENT_RECORD = {"shipment_id": "SHP-4498", "carrier_id": "NGX", "dispatched_at": 1712,
                    "weight_kg": 7.5, "ref_": "R-12", "signed": True}

def _private_ops() -> list[dict[str, Any]]:
    'The week of partner posts every delivery is measured on.'

    ops = [_build(name) for name in PRIVATE_CONFIGS]
    ops += [
        _load("ravel-both-differ", "ravel", shipment_id="SHP-4471", carrier_id="NGT",
              scac="NGX", dispatched_at=1712, weight_kg=12.5),
        _load("ravel-three-spellings", "ravel", shipment_id="SHP-4472", carrier_id="NGT",
              scac="NGX", carrier="NGY", dispatched_at=1713, weight_kg=12.5),
        _load("ravel-both-agree", "ravel", shipment_id="SHP-4473", carrier_id="NGT",
              dispatched_at=1714, weight_kg=8.0, kg=8.0),
        _load("ravel-alias-only", "ravel", shipment_id="SHP-4474", scac="NGX",
              dispatched_at=1715, kg=6.25),
        _load("ravel-primary-only", "ravel", shipment_id="SHP-4475", carrier_id="NGT",
              dispatched_at=1716, weight_kg=5.0),
        _load("ravel-required-missing", "ravel", shipment_id="SHP-4476",
              dispatched_at=1717, weight_kg=5.5),
        _load("sable-strict-aliases", "sable", shipment_id="SHP-4481", carrier="PLW",
              dispatched_at=1721, kg=9.0, ref_="R-1", signed=True),
        _load("sable-strict-typo", "sable", shipment_id="SHP-4482", scac="PLW",
              dispatched_at=1722, kg=9.5, ref_="R-2", signed=False, weigth_kg=9.5),
        _load("tessel-collect-mixed", "tessel", shipment_id="SHP-4483", scac="QLL",
              dispatched_at=1723, kg=4.5, ref_="R-3", signed=True, legacy_ref="L-88",
              sourceSystem="ops"),
        _load("vesper-load", "vesper", shipment_id="SHP-4492", carrier_id="VSP",
              dispatched_at=1731, kg=11.0, ref_="R-4", signed=False),
        _load("northgate-load", "northgate", shipment_id="SHP-4493", carrier_id="NGT",
              dispatched_at=1732, weight_kg=3.0, ref_="R-5", signed=True),
        _load("sable-bad-value", "sable", shipment_id="SHP-4495", scac="PLW",
              dispatched_at=1741, kg="heavy", ref_="R-6", signed=False),
        _load("pellworm-generated", "pellworm", shipment_id="SHP-4496", carrierId="PLW",
              dispatched_at=1751, weight_kg=3.5, ref_="R-7", signed=True),
        _load("quill-literal", "quill", shipmentId="SHP-4497", carrierId="QLL",
              dispatchedAt=1752, weight_total=9.25, ref_="R-8", signed=True),
        _load("yarrow-second-style", "yarrow", shipment_id="SHP-4500", carrier_id="YRW",
              **{"dispatched-at": 1753}, weight_kg=6.5, ref_="R-9", signed=False),
        _schema("schema-sable", "sable"),
        _schema("schema-quill", "quill"),
        _schema("schema-pellworm", "pellworm"),
        _dump("dump-ravel", "ravel", _SHIPMENT_RECORD),
        _dump("dump-pellworm", "pellworm", _SHIPMENT_RECORD),
        _dump("dump-partial", "ravel", {"shipment_id": "SHP-4499", "carrier_id": "NGX",
                                        "dispatched_at": 1713, "weight_kg": 7.5}),
    ]
    return ops


_RECORDS = {
    "ravel-alias-only": ("ravel", "scac", ("SHP-4474", "NGX", 1715, 6.25, "", False)),
    "ravel-primary-only": ("ravel", "carrier_id", ("SHP-4475", "NGT", 1716, 5.0, "", False)),
    "sable-strict-aliases": ("sable", "carrier", ("SHP-4481", "PLW", 1721, 9.0, "R-1", True)),
    "vesper-load": ("vesper", "kg", ("SHP-4492", "VSP", 1731, 11.0, "R-4", False)),
    "northgate-load": ("northgate", "ref_", ("SHP-4493", "NGT", 1732, 3.0, "R-5", True)),
    "pellworm-generated": ("pellworm", "carrierId", ("SHP-4496", "PLW", 1751, 3.5, "R-7", True)),
    "quill-literal": ("quill", "weight_total", ("SHP-4497", "QLL", 1752, 9.25, "R-8", True)),
    "yarrow-second-style": ("yarrow", "dispatched-at",
                              ("SHP-4500", "YRW", 1753, 6.5, "R-9", False)),
}

_ABOUT = {"pellworm-generated": "carrier_id", "quill-literal": "weight_kg",
          "yarrow-second-style": "dispatched_at"}

_AMBIGUOUS = {
    "ravel-both-differ": ("SHP-4471", "carrier_id", ("carrier_id", "scac")),
    "ravel-three-spellings": ("SHP-4472", "carrier_id", ("carrier", "carrier_id", "scac")),
    "ravel-both-agree": ("SHP-4473", "weight_kg", ("kg", "weight_kg")),
}

_BOUNCED = {
    "sable-strict-typo": ("SHP-4482", "ExtraFieldsError", "weigth_kg"),
    "sable-bad-value": ("SHP-4495", "TypeMismatchError", "kg"),
}

def private_expectations() -> dict[str, dict[str, Any]]:
    'What each labelled operation of the private run has to produce.'

    ids = tuple(str(field["id"]) for field in SHIPMENT["fields"])
    expected: dict[str, dict[str, Any]] = {
        label: {"kind": "record", "partner": row[0], "id": row[2][0], "spelling": row[1],
                "self_key": row[1], "field": _ABOUT.get(label, ""),
                "record": dict(zip(ids, row[2]))}
        for label, row in _RECORDS.items()
    }
    expected.update({
        label: {"kind": "ambiguous", "partner": "ravel", "id": row[0], "field": row[1],
                "keys": row[2]}
        for label, row in _AMBIGUOUS.items()
    })
    expected.update({
        label: {"kind": "bounced", "partner": "sable", "id": row[0], "error": row[1],
                "trail": (row[2],), "key": row[2], "spelling": "scac"}
        for label, row in _BOUNCED.items()
    })
    expected.update({
        "build-tarn": {"kind": "refused", "partner": "tarn", "key": "ref",
                       "fields": ("shipment_id", "ref_")},
        "build-umbra": {"kind": "refused", "partner": "umbra", "key": "carrier_id",
                        "fields": ("carrier_id", "weight_kg")},
        "build-wold": {"kind": "refused", "partner": "wold", "key": "weightKg",
                       "fields": ("carrier_id", "weight_kg")},
        "build-vesper": {"kind": "builds", "partner": "vesper", "key": "kg"},
        "build-northgate": {"kind": "builds", "partner": "northgate", "key": "ref_"},
        "ravel-required-missing": {
            "kind": "missing", "partner": "ravel", "id": "SHP-4476",
            "field": "carrier_id", "error": "MissingFieldError"},
        "tessel-collect-mixed": {
            "kind": "collected", "partner": "tessel", "id": "SHP-4483", "spelling": "scac",
            "record": dict(zip(ids, ("SHP-4483", "QLL", 1723, 4.5, "R-3", True))),
            "extra_in": "extra",
            "extra": {"legacy_ref": "L-88", "sourceSystem": "ops"}},
        "schema-sable": {"kind": "schema", "partner": "sable"},
        "schema-quill": {"kind": "schema", "partner": "quill"},
        "schema-pellworm": {"kind": "schema", "partner": "pellworm"},
        "dump-ravel": {"kind": "dump", "partner": "ravel",
                       "record": dict(_SHIPMENT_RECORD)},
        "dump-pellworm": {"kind": "dump", "partner": "pellworm",
                          "record": {"shipment_id": "SHP-4498", "scac": "NGX",
                                     "dispatched_at": 1712, "weight_kg": 7.5,
                                     "ref_": "R-12", "signed": True}},
        "dump-partial": {"kind": "dump", "partner": "ravel",
                         "record": {"shipment_id": "SHP-4499", "carrier_id": "NGX",
                                    "dispatched_at": 1713, "weight_kg": 7.5}},
    })
    return expected


def _onboarding_ops() -> list[dict[str, Any]]:
    return [
        _build("house"), _build("atlas"), _build("cygnet"), _build("dorado"),
        _load("house-today", "house", order_id="ORD-901", user_id="U-7", order_ts=1690,
              amount=42.0, note="", from_="portal"),
        _load("atlas-camel", "atlas", orderId="ORD-902", userId="U-8", orderTs=1691,
              amount=18.5, note="split", from_="atlas"),
        _load("cygnet-userid", "cygnet", order_id="ORD-903", userId="U-9", order_ts=1692,
              amount=61.0, note="", from_="cygnet"),
        _load("dorado-literal", "dorado", orderId="ORD-904", userId="U-10",
              order_ts_=1693, amount_total=7.25, note="rush", **{"from": "dorado"}),
        _dump("dump-atlas", "atlas", {"order_id": "ORD-902", "user_id": "U-8",
                                      "order_ts": 1691, "amount": 18.5, "note": "split",
                                      "from_": "atlas"}),

        _dump("dump-dorado", "dorado", {"order_id": "ORD-904", "user_id": "U-10",
                                        "order_ts": 1693, "amount": 7.25,
                                        "from_": "dorado"}),
        _schema("schema-atlas", "atlas"),
    ]

def _cutover_ops() -> list[dict[str, Any]]:
    return [
        _build("borea"),
        _load("cutover-differ", "borea", order_id="ORD-911", user_id="U-11", uid="U-77",
              order_ts=1701, amount=120.0),
        _load("cutover-agree", "borea", order_id="ORD-912", user_id="U-12", order_ts=1702,
              amount=64.0, amt=64.0),
        _load("cutover-one", "borea", order_id="ORD-913", uid="U-13", order_ts=1703,
              amt=31.5),
        _raw("cutover-envelope", "borea",
             {"record": {"order_id": "ORD-914", "uid": "U-14", "order_ts": 1704, "amt": 9.0},
              "attributes": {"order_id": "ORD-914", "uid": "U-14", "order_ts": 1704,
                             "amt": 90.0}}),
        _schema("schema-borea", "borea"),
    ]

def _strictness_ops() -> list[dict[str, Any]]:
    return [
        _build("borea_strict"), _build("borea_collect"),
        _load("strict-aliases", "borea_strict", order_id="ORD-921", uid="U-21",
              order_ts=1711, amt=12.0, note="", from_="borea"),
        _load("strict-typo", "borea_strict", order_id="ORD-922", uid="U-22", order_ts=1712,
              amt=13.0, note="", from_="borea", amoun=13.0),
        _load("collect-aliases", "borea_collect", order_id="ORD-923", userId="U-23",
              order_ts=1713, amt=14.0, note="", from_="borea"),
        _load("collect-mixed", "borea_collect", order_id="ORD-924", uid="U-24",
              order_ts=1714, amt=15.0, note="", from_="borea", legacy_ref="L-4",
              sourceSystem="edi"),
        _schema("schema-borea-strict", "borea_strict"),
    ]

def _review_ops() -> list[dict[str, Any]]:
    return [
        _build("twin"), _build("overlap"), _build("atlas"), _build("legacy"),
        _load("wide-snake", "atlas", order_id="ORD-931", user_id="U-31", order_ts=1721,
              amount=51.0, note="held", from_="atlas"),
        _load("legacy-amt", "legacy", order_id="ORD-932", user_id="U-32", order_ts=1722,
              amt=52.0, note="", from_="legacy"),
        _load("twin-ref", "twin", ref="ORD-933", user_id="U-33", order_ts=1723,
              amount=53.0),
        _load("overlap-ts", "overlap", order_id="ORD-934", user_id="U-34", order_ts=1724),
        _schema("schema-legacy", "legacy"),
    ]

PUBLIC_PROGRAMS = {
    "onboarding": (ORDER, PUBLIC_CONFIGS, _onboarding_ops),
    "cutover": (ORDER, PUBLIC_CONFIGS, _cutover_ops),
    "strictness": (ORDER, PUBLIC_CONFIGS, _strictness_ops),
    "review": (ORDER, PUBLIC_CONFIGS, _review_ops),
}

def build_program(profile: str) -> dict[str, Any]:
    'The shape, the partner configurations and the posts of one run.'

    if profile == "release":
        shape, configs, ops = SHIPMENT, PRIVATE_CONFIGS, _private_ops()
    else:
        entry = PUBLIC_PROGRAMS.get(profile)
        if entry is None:
            raise ValueError(f"unknown intake run: {profile}")
        shape, configs, builder = entry
        ops = builder()
    used = sorted({str(op["config"]) for op in ops})
    return {
        "shape": dict(shape),
        "configs": {name: [dict(layer) for layer in configs[name]] for name in used},
        "operations": ops,
    }
