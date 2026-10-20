'Deterministic catalogue exports and import programs.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


CHECKPOINT_INTERVAL = 25
TRANSACTION_SLACK = 4


NEXT_DAY_PRODUCTS = 4
NEXT_DAY_INDEX_BASE = 400

_NAMES = (
    "beacon", "lantern", "harbor", "quarry", "meadow", "cinder",
    "willow", "anchor", "pebble", "kestrel", "juniper", "summit",
)


def _product(index: int, seed: int, *, sku: str | None = None) -> dict[str, Any]:
    return {
        "op": "product",
        "id": 1000 + index,
        "sku": sku if sku is not None else f"SKU-{seed:02d}-{index:04d}",
        "name": f"{_NAMES[index % len(_NAMES)].title()} {index:03d}",
    }


def _variant(index: int, product_index: int, seed: int, *, price: int | None = None) -> dict[str, Any]:
    return {
        "op": "variant",
        "id": 5000 + index,
        "product_id": 1000 + product_index,
        "price_cents": (1999 + 37 * ((seed + index) % 40)) if price is None else price,
        "label": f"{_NAMES[(seed + index) % len(_NAMES)]}-{index:03d}",
    }


def build_source(seed: int, scale: int, *, variant: str = "primary") -> list[dict[str, Any]]:
    'Return one deterministic catalogue export.'

    products = 20 * int(scale)
    offset = 0 if variant == "primary" else 7000
    rows: list[dict[str, Any]] = []
    for index in range(products):
        rows.append(_product(index + offset, seed))
        rows.append(_variant(2 * index + offset, index + offset, seed))
        rows.append(_variant(2 * index + 1 + offset, index + offset, seed))
        if index < 2:
            continue

        slot = index % 7
        if slot == 0:
            rows.append(
                _product(index + offset, seed, sku=f"SKU-{seed:02d}-alt-{index:04d}")
            )
        elif slot == 1:
            rows.append(
                _product(
                    index + 900 + offset,
                    seed,
                    sku=f"SKU-{seed:02d}-{index + offset:04d}",
                )
            )
        elif slot == 2:
            rows.append(_product(index + 800 + offset, seed, sku="   "))
        elif slot == 3:
            rows.append(_variant(2 * index + offset, index + offset, seed, price=12345))
        elif slot == 4:
            rows.append(_variant(3000 + index + offset, 4000 + index, seed))
        elif slot == 5:
            rows.append(_variant(3500 + index + offset, index + offset, seed, price=-500))
        else:
            rows.append({"op": "bundle", "id": 9000 + index + offset})
    return rows


def build_next_day_source(seed: int, scale: int) -> list[dict[str, Any]]:
    "Return the following night's export of the same catalogue."

    rows = build_source(seed, scale)
    blocks = [
        [
            _product(NEXT_DAY_INDEX_BASE + step, seed),
            _variant(2 * (NEXT_DAY_INDEX_BASE + step), NEXT_DAY_INDEX_BASE + step, seed),
            _variant(2 * (NEXT_DAY_INDEX_BASE + step) + 1, NEXT_DAY_INDEX_BASE + step, seed),
        ]
        for step in range(NEXT_DAY_PRODUCTS)
    ]
    cuts = [
        ((step + 1) * len(rows)) // (NEXT_DAY_PRODUCTS + 1)
        for step in range(NEXT_DAY_PRODUCTS)
    ]
    published: list[dict[str, Any]] = []
    for position, row in enumerate(rows):
        while cuts and position == cuts[0]:
            published.extend(blocks.pop(0))
            cuts.pop(0)
        published.append(row)
    for block in blocks:
        published.extend(block)
    return published


def reference_outcome(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    'Fold the export in source order into the admissible database.'

    from ..workspace.loader.protocol import admit, stored_row, table_of

    state: dict[str, dict[str, Any]] = {"products": {}, "variants": {}}
    rejected: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        reason = admit(state, row)
        if reason is not None:
            rejected.append({"index": index, "reason": reason})
            continue
        stored = stored_row(row)
        state[table_of(row)][stored["id"]] = stored
    return {"tables": state, "rejected": rejected}


def admitted_prefix_rows(rows: Sequence[Mapping[str, Any]], upto: int) -> int:
    'Count the rows an in-order loader would have committed by ``upto``.'

    return len(
        reference_outcome(rows[: max(0, int(upto))])["tables"]["products"]
    ) + len(reference_outcome(rows[: max(0, int(upto))])["tables"]["variants"])


def _run(
    label: str,
    *,
    night: str = "load-night",
    source: str = "primary",
    export_name: str | None = None,
    fail_after: int | None = None,
    fail_on_commit: int | None = None,
    fail_on_cleanup: bool = False,
) -> dict[str, Any]:
    'One scheduled attempt.'

    return {
        "type": "import",
        "label": label,
        "night": night,
        "source": source,
        "export_name": export_name,
        "fail_after": fail_after,
        "fail_on_commit": fail_on_commit,
        "fail_on_cleanup": bool(fail_on_cleanup),
    }


def _interruption(seed: int, scale: int) -> list[dict[str, Any]]:
    total = len(build_source(seed, scale))
    return [
        _run("first-attempt", fail_after=int(total * 0.45)),
        _run("resume-after-restart", fail_on_commit=2),
        _run("resume-to-completion"),
    ]


def _dirty(seed: int, scale: int) -> list[dict[str, Any]]:
    return [_run("single-pass-load")]


def _capacity(seed: int, scale: int) -> list[dict[str, Any]]:
    return [_run("warehouse-load")]


def _rerun(seed: int, scale: int) -> list[dict[str, Any]]:
    total = len(build_source(seed, scale))
    return [
        _run("initial-load", fail_after=int(total * 0.6)),
        _run("wrong-export-attempt", source="foreign"),
        _run("resume-to-completion"),
        _run("scheduled-rerun", night="quiet-night"),
    ]


def _release(seed: int, scale: int) -> list[dict[str, Any]]:
    'The private nightly programme: one night, then the two nights after it.'

    total = len(build_source(seed, scale))
    first_failure = int(total * 0.45)
    return [
        _run("first-attempt", fail_after=first_failure),
        _run("wrong-export-attempt", source="foreign"),
        _run("resume-after-lost-commit", fail_on_commit=2),


        _run("resume-after-cleanup-failure", fail_on_cleanup=True),
        _run("resume-to-completion"),
        _run("scheduled-rerun", night="quiet-night"),
        _run(
            "next-export-load",
            night="next-night",
            source="next_day",
            export_name="primary-export.jsonl",
        ),
    ]


PROGRAM_BUILDERS = {
    "release": _release,
    "interruption": _interruption,
    "dirty": _dirty,
    "capacity": _capacity,
    "rerun": _rerun,
}


def build_program(profile: str, seed: int, scale: int) -> list[dict[str, Any]]:
    builder = PROGRAM_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"unknown import program profile: {profile}")
    return builder(seed, scale)
