'Deterministic training frames, request batteries, and pipeline programs.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


_REGIONS = ("EU", "NA", "APAC", "LATAM")
_TIERS = ("bronze", "silver", "gold")


def build_training_rows(seed: int, scale: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(24 * int(scale)):
        region = _REGIONS[(seed + index) % len(_REGIONS)]
        tier = _TIERS[(seed + 2 * index) % len(_TIERS)]
        amount = float(50 + ((seed * 7 + index * 13) % 400))
        rows.append(
            {
                "record_id": 9000 + index,
                "amount": amount,
                "amount_copy": amount,
                "region": region,
                "region_alias": region,
                "tier": tier,
                "pipeline_version": "v3",
                "noise": float((seed + index) % 5),
                "target": round(0.35 * amount + 4.0 * ((seed + index) % 5), 6),
            }
        )
    return rows


def shuffled(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'A deterministic reordering of the same rows.'

    ordered = [dict(row) for row in rows]
    return ordered[1::2] + ordered[0::2]


def default_spec() -> dict[str, Any]:
    return {
        "target": "target",
        "include": None,
        "exclude": ["record_id"],
        "drop_constant": True,
        "drop_duplicate": True,
    }


def build_request_rows(seed: int, scale: int) -> list[dict[str, Any]]:
    'One logical request expressed the several ways callers actually send it.'

    base = build_training_rows(seed, scale)[0]
    amount = base["amount"]
    region = base["region"]
    tier = base["tier"]
    return [
        {
            "record_id": 1,
            "amount": amount,
            "amount_copy": amount,
            "region": region,
            "region_alias": region,
            "tier": tier,
            "pipeline_version": "v3",
            "noise": base["noise"],
            "target": base["target"],
        },
        {
            "noise": base["noise"],
            "tier": tier,
            "region": region,
            "amount": amount,
        },
        {
            "amount_copy": amount,
            "region_alias": region,
            "tier": tier,
            "noise": base["noise"],
        },
        {
            "amount": f"  {amount}  ",
            "region": f" {region.lower()} ",
            "tier": tier.upper(),
            "noise": base["noise"],
            "unrelated_column": "ignored",
            "another_extra": 17,
        },
        {
            "amount": amount,
            "amount_copy": amount,
            "region": region,
            "region_alias": region.lower(),
            "tier": tier,
            "noise": base["noise"],
        },
    ]


def build_refusal_rows(seed: int, scale: int) -> list[dict[str, Any]]:
    base = build_request_rows(seed, scale)[0]
    missing = {key: value for key, value in base.items() if key not in ("amount", "amount_copy")}
    conflicting = dict(base)
    conflicting["amount_copy"] = float(base["amount"]) + 25.0
    unseen = dict(base)
    unseen["region"] = "ANTARCTICA"
    unseen["region_alias"] = "ANTARCTICA"
    return [missing, conflicting, unseen]


def build_private_rows(seed: int, scale: int) -> list[dict[str, Any]]:
    'Generalisation cases not replayed by any recorded rehearsal.'

    base = build_request_rows(seed, scale)[0]
    conflicting_region = dict(base)
    conflicting_region["region_alias"] = "NOT-" + str(base["region"])
    unseen_tier = dict(base)
    unseen_tier["tier"] = "platinum"
    return [conflicting_region, unseen_tier]


def _event(kind: str, label: str, **fields: Any) -> dict[str, Any]:
    return {"type": kind, "label": label, **fields}


def _training(seed: int, scale: int) -> list[dict[str, Any]]:
    return [
        _event("reset", "reset"),
        _event("fit", "fit-baseline", frame="train", spec=default_spec()),
        _event("export", "export-baseline"),
        _event("describe", "artifacts-baseline"),
    ]


def _consumers(seed: int, scale: int) -> list[dict[str, Any]]:
    events = _training(seed, scale)
    events.append(_event("drop_training_frame", "retire-training-data"))
    for index in range(5):
        events.append(_event("predict", f"predict-request-{index}", frame="requests", row=index))
        events.append(_event("evaluate", f"evaluate-request-{index}", frame="requests", row=index))
        events.append(_event("serve", f"serve-request-{index}", frame="requests", row=index))
    events.append(_event("export", "export-after-requests"))
    return events


def _refusals(seed: int, scale: int) -> list[dict[str, Any]]:
    events = _training(seed, scale)
    for index, label in enumerate(("missing-feature", "conflicting-aliases", "unseen-category")):
        events.append(_event("predict", f"predict-{label}", frame="refusals", row=index))
        events.append(_event("serve", f"serve-{label}", frame="refusals", row=index))
        events.append(_event("evaluate", f"evaluate-{label}", frame="refusals", row=index))
    for label, spec in (
        ("unknown-include", {**default_spec(), "include": ["amount", "not_a_column"]}),
        ("duplicate-include", {**default_spec(), "include": ["amount", "amount"]}),
        ("target-in-exclude", {**default_spec(), "exclude": ["record_id", "target"]}),
        ("empty-selection", {**default_spec(), "include": ["pipeline_version"]}),
    ):
        events.append(_event("fit", f"fit-{label}", frame="train", spec=spec))
    return events


def _artifacts(seed: int, scale: int) -> list[dict[str, Any]]:
    return [
        _event("reset", "reset"),
        _event("fit", "fit-first", frame="train", spec=default_spec()),
        _event("describe", "artifacts-first"),
        _event("reset", "reset-second"),
        _event("fit", "fit-second", frame="train", spec=default_spec()),
        _event("describe", "artifacts-second"),
        _event("reset", "reset-shuffled"),
        _event("fit", "fit-shuffled", frame="train_shuffled", spec=default_spec()),
        _event("describe", "artifacts-shuffled"),
        _event("tamper", "tamper-schema-version", artifact="feature_schema.json", field="version", value=99),
        _event("predict", "predict-after-tamper", frame="requests", row=0),
        _event("serve", "serve-after-tamper", frame="requests", row=0),
        _event("export", "export-after-tamper"),
    ]


def _private_conditions(seed: int, scale: int) -> list[dict[str, Any]]:
    events = _training(seed, scale)
    for index, label in enumerate(("conflicting-region-sources", "unseen-tier")):
        for consumer in ("predict", "serve", "evaluate"):
            events.append(
                _event(
                    consumer,
                    f"{consumer}-{label}",
                    frame="private_refusals",
                    row=index,
                )
            )
    events.append(
        _event(
            "fit",
            "fit-target-in-include",
            frame="train",
            spec={**default_spec(), "include": ["amount", "target"]},
        )
    )
    events.append(
        _event(
            "fit",
            "fit-unknown-exclude",
            frame="train",
            spec={**default_spec(), "exclude": ["record_id", "not_a_column"]},
        )
    )
    events.append(
        _event(
            "fit",
            "fit-duplicate-exclude",
            frame="train",
            spec={**default_spec(), "exclude": ["record_id", "record_id"]},
        )
    )
    return events


def _training_alignment(seed: int, scale: int) -> list[dict[str, Any]]:
    'Re-score every fitted record without prescribing training row order.'

    events: list[dict[str, Any]] = []
    for index, _row in enumerate(build_training_rows(seed, scale)):
        events.append(
            _event(
                "predict",
                f"predict-training-row-{index}",
                frame="train",
                row=index,
            )
        )
    return events


PHASE_BUILDERS = {
    "training": _training,
    "consumers": _consumers,
    "refusals": _refusals,
    "artifacts": _artifacts,
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    if profile == "release":
        program: list[dict[str, Any]] = []
        for phase in ("consumers", "refusals", "artifacts"):
            for event in PHASE_BUILDERS[phase](seed, scale):
                program.append({**event, "phase": phase})
                if phase == "consumers" and event["label"] == "retire-training-data":


                    program.append(
                        {
                            **_event(
                                "restart_from_artifacts",
                                "restart-consumer-from-artifacts",
                            ),
                            "phase": "private",
                        }
                    )


                    for alignment_event in _training_alignment(seed, scale):
                        program.append({**alignment_event, "phase": "private"})


        program.append(
            {
                **_event(
                    "evaluate",
                    "evaluate-after-tamper",
                    frame="requests",
                    row=0,
                ),
                "phase": "private",
            }
        )
        for event in _private_conditions(seed, scale):
            program.append({**event, "phase": "private"})
        return program
    builder = PHASE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown pipeline program profile: {profile}")
    return [{**event, "phase": profile} for event in builder(seed, scale)]


def build_frames(seed: int, scale: int) -> dict[str, list[dict[str, Any]]]:
    training = build_training_rows(seed, scale)
    return {
        "train": training,
        "train_shuffled": shuffled(training),
        "requests": build_request_rows(seed, scale),
        "refusals": build_refusal_rows(seed, scale),
        "private_refusals": build_private_rows(seed, scale),
    }
