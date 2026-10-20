'Deterministic fleet programmes: the recorded shifts and the private week.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


SETTLEMENT = "partner-settlement"
EXPORT = "ledger-export"


WINDOWS: Mapping[str, int] = {SETTLEMENT: 3, EXPORT: 2}


CANARY_RANK = 10

CONTROL_LINK = "L0"


def _link(link: str) -> dict[str, Any]:
    return {"op": "link", "link": str(link)}


def _register(
    job_class: str, *, link: str = CONTROL_LINK, exclusive: bool = True,
    plain: bool = False, window_jobs: Sequence[str] = (),
) -> dict[str, Any]:
    'Declare a class.'

    return {
        "op": "register", "link": str(link), "class": str(job_class),
        "exclusive": bool(exclusive), "max_in_flight": int(WINDOWS[job_class]),
        "plain_registration": bool(plain),
        "window_jobs": [str(job) for job in window_jobs],
    }


def _claim(
    worker: str, job_class: str, *, link: str, rank: int = 0,
    revoke_raises: bool = False, equal_rank_newcomer: bool = False,
) -> dict[str, Any]:
    return {
        "op": "claim", "link": str(link), "worker": str(worker),
        "class": str(job_class), "rank": int(rank),
        "revoke_raises": bool(revoke_raises),
        "equal_rank_newcomer": bool(equal_rank_newcomer),
    }


def _release(worker: str) -> dict[str, Any]:
    return {"op": "release", "worker": str(worker)}


def _drop(link: str) -> dict[str, Any]:
    return {"op": "drop_link", "link": str(link)}


def _retire(job_class: str, *, link: str = CONTROL_LINK) -> dict[str, Any]:
    return {"op": "retire", "link": str(link), "class": str(job_class)}


def _submit(job: str, job_class: str, *, link: str = CONTROL_LINK) -> dict[str, Any]:
    return {
        "op": "submit", "link": str(link), "class": str(job_class),
        "job": str(job), "account": f"account-{job[-2:]}",
    }


def _finish(job: str, *, link: str = CONTROL_LINK) -> dict[str, Any]:
    return {"op": "finish", "link": str(link), "job": str(job)}


def _process(label: str, ops: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    return {"label": str(label), "ops": list(ops), **fields}


def _handover_drill() -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = [
        _link(CONTROL_LINK), _link("L1"), _link("L2"), _register(SETTLEMENT),
        _claim("settle-a", SETTLEMENT, link="L1"),
        _claim("settle-b", SETTLEMENT, link="L2"),
        _submit("S-01", SETTLEMENT),
        _submit("S-02", SETTLEMENT),
        _submit("S-03", SETTLEMENT),
        _submit("S-04", SETTLEMENT),
        _drop("L1"),
        _finish("S-01"),
        _finish("S-02"),
        _finish("S-03"),
        _finish("S-04"),
        _release("settle-b"),
        _submit("S-05", SETTLEMENT),
        _link("L3"),
        _claim("settle-c", SETTLEMENT, link="L3"),
        _finish("S-05"),
    ]
    return [_process("tuesday-afternoon", ops)]


def _rollout_duplicate() -> list[dict[str, Any]]:
    scale_up = [_link(CONTROL_LINK), _link("L1"), _link("L2"), _link("L3")]
    scale_up += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    scale_up += [
        _claim("settle-a", SETTLEMENT, link="L1"),
        _claim("settle-b", SETTLEMENT, link="L2"),
        _claim("settle-c", SETTLEMENT, link="L3"),
        _submit("S-11", SETTLEMENT),
        _finish("S-11"),
        _submit("S-12", SETTLEMENT),
        _finish("S-12"),
        _release("settle-a"),
        _release("settle-b"),
        _submit("E-before-restart", EXPORT),
    ]
    after = [_link(CONTROL_LINK), _link("L4"), _link("L5")]
    after += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    after += [
        _claim("settle-d", SETTLEMENT, link="L4"),
        _submit("S-13", SETTLEMENT),
        _finish("S-13"),
        _submit("S-14", SETTLEMENT),
        _finish("S-14"),
        _claim("export-d", EXPORT, link="L5"),
    ]
    return [
        _process("scale-up", scale_up),
        _process("after-restart", after, after_restart=True),
    ]


def _old_build_window() -> list[dict[str, Any]]:
    ops = [_link(CONTROL_LINK), _link("L1"), _link("L2")]
    ops += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    ops += [
        _claim("settle-a", SETTLEMENT, link="L1"),
        _claim("settle-b", SETTLEMENT, link="L2"),
        _submit("S-21", SETTLEMENT),
        _finish("S-21"),
        _link("L3"),
        _register(
            SETTLEMENT,
            link="L3",
            exclusive=False,
            plain=True,
            window_jobs=[f"S-22{letter}" for letter in "abcd"],
        ),
        _claim("settle-old", SETTLEMENT, link="L3", revoke_raises=True),
        _claim("export-old", EXPORT, link="L3"),
    ]
    ops += [_submit(f"S-22{letter}", SETTLEMENT) for letter in "abcd"]
    ops += [_finish(f"S-22{letter}") for letter in "abcd"]
    ops += [
        _drop("L3"),
        _submit("S-23", SETTLEMENT),
        _finish("S-23"),
    ]
    return [_process("march-overlap", ops)]


def _canary_window() -> list[dict[str, Any]]:
    ops = [_link(CONTROL_LINK), _link("L1"), _link("L2"), _link("L3")]
    ops += [_register(EXPORT, exclusive=False)]
    ops += [
        _claim("export-canary", EXPORT, link="L1", rank=CANARY_RANK),
        _claim("export-b", EXPORT, link="L2"),
        _claim("export-c", EXPORT, link="L3"),
    ]
    ops += [_submit(f"E-3{index}", EXPORT) for index in range(1, 6)]
    ops += [
        _register(SETTLEMENT),
        _claim("settle-a", SETTLEMENT, link="L2"),
        _submit("S-36", SETTLEMENT),
        _finish("S-36"),
        _claim("settle-canary", SETTLEMENT, link="L1", rank=CANARY_RANK),
        _submit("S-37", SETTLEMENT),
        _finish("S-37"),
        _release("settle-canary"),
        _link("L4"),
        _claim("settle-supercanary", SETTLEMENT, link="L4", rank=20),
        _submit("S-38", SETTLEMENT),
        _finish("S-38"),
        _retire(EXPORT),
    ]
    return [_process("canary-afternoon", ops)]


def _shift(links: Mapping[str, str], label: str) -> dict[str, Any]:
    'One shift over whichever links the fleet happened to be split across.'

    ops = [_link(CONTROL_LINK)]
    ops += [_link(link) for link in dict.fromkeys(links.values())]
    ops += [
        _register(SETTLEMENT),
        _claim("pay-01", SETTLEMENT, link=links["pay-01"]),
        _claim("pay-02", SETTLEMENT, link=links["pay-02"]),
        _claim("pay-03", SETTLEMENT, link=links["pay-03"], rank=5),
        _submit("P-01", SETTLEMENT),
        _submit("P-02", SETTLEMENT),
        _finish("P-01"),
        _finish("P-02"),
        _release("pay-03"),
        _submit("P-03", SETTLEMENT),
        _finish("P-03"),
    ]
    return _process(label, ops, compare_group="shift")


def _settlement_week() -> list[dict[str, Any]]:
    one_link = _shift({"pay-01": "L1", "pay-02": "L1", "pay-03": "L1"}, "shift-on-one-link")
    split = _shift({"pay-01": "L1", "pay-02": "L2", "pay-03": "L3"}, "shift-split-across-links")

    ops = [_link(CONTROL_LINK), _link("L1"), _link("L2")]
    ops += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    ops += [
        _claim("pay-alpha", SETTLEMENT, link="L1"),
        _submit("P-11", SETTLEMENT),
        _finish("P-11"),
        _claim("pay-beta", SETTLEMENT, link="L2", equal_rank_newcomer=True),
        _submit("P-12", SETTLEMENT),
        _finish("P-12"),
        _link("L4"),
        _claim("pay-canary", SETTLEMENT, link="L4", rank=CANARY_RANK),
        _submit("P-14", SETTLEMENT),
        _submit("P-15", SETTLEMENT),
        _submit("P-18", SETTLEMENT),
        _submit("P-19", SETTLEMENT),
        _finish("P-14"),
        _finish("P-15"),
        _finish("P-18"),
        _finish("P-19"),
        _link("L3"),
        _register(
            SETTLEMENT,
            link="L3",
            exclusive=False,
            plain=True,
            window_jobs=[f"P-13{letter}" for letter in "abcd"],
        ),
        _claim("pay-legacy", SETTLEMENT, link="L3", revoke_raises=True),
        _claim("sweep-legacy", EXPORT, link="L3"),
    ]
    ops += [_submit(f"P-13{letter}", SETTLEMENT) for letter in "abcd"]
    ops += [_finish(f"P-13{letter}") for letter in "abcd"]
    ops += [
        _drop("L3"),
        _submit("P-16", SETTLEMENT),
        _finish("P-16"),
        _claim("sweep-alpha", EXPORT, link="L1"),
        _claim("sweep-beta", EXPORT, link="L2"),
        _claim("sweep-canary", EXPORT, link="L4", rank=CANARY_RANK),
    ]
    ops += [_submit(f"E-2{index}", EXPORT) for index in range(1, 7)]
    ops += [_finish(f"E-2{index}") for index in range(1, 7)]
    ops += [
        _retire(EXPORT),
        _release("pay-canary"),
        _link("L5"),
        _claim("pay-supercanary", SETTLEMENT, link="L5", rank=20),
        _submit("P-16b", SETTLEMENT),
        _finish("P-16b"),
        _release("pay-supercanary"),
        _release("pay-alpha"),
        _release("pay-beta"),
        _submit("P-17", SETTLEMENT),
        _link("L6"),
        _claim("pay-foxtrot", SETTLEMENT, link="L6"),
        _finish("P-17"),
        _release("pay-foxtrot"),
    ]
    week = _process("settlement-week", ops)

    drop = [_link(CONTROL_LINK), _link("L1"), _link("L2")]
    drop += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    drop += [
        _claim("drop-alpha", SETTLEMENT, link="L1"),
        _claim("drop-beta", SETTLEMENT, link="L2"),
        _submit("D-01", SETTLEMENT),
        _submit("D-02", SETTLEMENT),
        _submit("D-03", SETTLEMENT),
        _submit("D-04", SETTLEMENT),
        _drop("L1"),
        _finish("D-01"),
        _finish("D-02"),
        _finish("D-03"),
        _finish("D-04"),
        _submit("E-private-before-restart", EXPORT),
    ]

    restart = [_link(CONTROL_LINK), _link("L1"), _link("L2")]
    restart += [_register(SETTLEMENT), _register(EXPORT, exclusive=False)]
    restart += [
        _claim("pay-golf", SETTLEMENT, link="L1"),
        _submit("P-21", SETTLEMENT),
        _finish("P-21"),
        _submit("P-22", SETTLEMENT),
        _finish("P-22"),
        _claim("sweep-golf", EXPORT, link="L2"),
    ]
    return [
        one_link, split, week, _process("active-holder-link-drop", drop),
        _process("midweek-restart", restart, after_restart=True),
    ]


PROGRAMMES = {
    "handover-drill": _handover_drill,
    "rollout-duplicate": _rollout_duplicate,
    "old-build-window": _old_build_window,
    "canary-window": _canary_window,
    "settlement-week": _settlement_week,
}


def build_programme(name: str) -> list[dict[str, Any]]:
    builder = PROGRAMMES.get(str(name))
    if builder is None:
        raise ValueError(f"unknown fleet programme: {name}")
    return builder()
