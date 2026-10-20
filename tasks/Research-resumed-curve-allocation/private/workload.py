'The sweep window on the board, the windows behind it, and the quiet cluster.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import world


LOG_INTERVAL = 250
COARSE_INTERVAL = 2_000


def _run(
    config_id: str,
    floor: float,
    amplitude: float,
    exponent: float,
    segments: Sequence[tuple[str, int, str]],
    log_interval: int | None = None,
    launch_script: str = "launch/train_v4.sh",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "config_id": config_id,
        "floor": float(floor),
        "amplitude": float(amplitude),
        "exponent": float(exponent),
        "launch_script": launch_script,
        "segments": [
            {"node": node, "hours": hours, "started_on": day}
            for node, hours, day in segments
        ],
    }
    if log_interval is not None:
        entry["log_interval"] = int(log_interval)
    return entry


def _spec(
    campaign: str,
    as_of: str,
    seed: int,
    node_steps_per_hour: Mapping[str, int],
    reserved: Sequence[str],
    grant: int,
    instrument_k: float,
    noise_sd: float,
    runs: Sequence[Mapping[str, Any]],
    reckoning_node: str = "n-b",
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "as_of": as_of,
        "seed": int(seed),
        "node_steps_per_hour": dict(node_steps_per_hour),
        "reserved_nodes": list(reserved),
        "reckoning_node": reckoning_node,
        "job_hours": {"min": 4, "max": 16},
        "grant_node_hours": int(grant),
        "log_interval": LOG_INTERVAL,
        "instrument_k": float(instrument_k),
        "noise_sd": float(noise_sd),
        "runs": [dict(item) for item in runs],
    }


CURRENT_SPEC = _spec(
    campaign="pretrain-sweep-2026-09",
    as_of="2026-09-14",
    seed=901_5117,
    node_steps_per_hour={"n-a": 1280, "n-b": 830, "n-c": 470},
    reserved=["n-a"],
    grant=50,
    instrument_k=0.078,
    noise_sd=0.011,
    runs=[
        _run("cfg-01", 1.02, 2.42, 0.312, [("n-c", 16, "2026-08-29"), ("n-b", 14, "2026-09-04"),
                                           ("n-b", 15, "2026-09-09")]),
        _run("cfg-02", 0.85, 2.30, 0.286, [("n-a", 15, "2026-08-28"), ("n-a", 14, "2026-09-02"),
                                           ("n-a", 16, "2026-09-08")]),
        _run("cfg-03", 1.11, 2.48, 0.330, [("n-b", 16, "2026-08-30"), ("n-c", 15, "2026-09-05"),
                                           ("n-b", 12, "2026-09-10")]),
        _run("cfg-04", 1.08, 2.14, 0.302, [("n-c", 14, "2026-08-31"), ("n-b", 16, "2026-09-06"),
                                           ("n-c", 16, "2026-09-11")]),
        _run(
            "cfg-05", 0.94, 2.36, 0.372,
            [("n-b", 16, "2026-08-27"), ("n-c", 15, "2026-09-01"), ("n-b", 14, "2026-09-07"),
             ("n-b", 6, "2026-09-12")],
            log_interval=COARSE_INTERVAL,
            launch_script="launch/train_v3.sh",
        ),
        _run("cfg-06", 0.90, 2.28, 0.398, [("n-c", 16, "2026-08-30"), ("n-b", 16, "2026-09-05"),
                                           ("n-b", 5, "2026-09-11")]),
    ],
)


FOLLOWING_SPECS = (
    _spec(
        campaign="pretrain-sweep-2026-10a",
        as_of="2026-10-12",
        seed=112_9041,
        node_steps_per_hour={"n-a": 1120, "n-b": 760, "n-c": 505},
        reserved=["n-a"],
        grant=53,
        instrument_k=0.061,
        noise_sd=0.014,
        runs=[
            _run("cfg-11", 1.14, 2.52, 0.301, [("n-a", 16, "2026-10-01"), ("n-b", 14, "2026-10-06")]),
            _run("cfg-12", 0.99, 2.31, 0.345, [("n-b", 15, "2026-10-02"), ("n-c", 16, "2026-10-07"),
                                               ("n-b", 6, "2026-10-10")]),
            _run("cfg-13", 1.06, 2.19, 0.288, [("n-a", 14, "2026-10-01"), ("n-a", 15, "2026-10-05"),
                                               ("n-a", 12, "2026-10-09")]),
            _run(
                "cfg-14", 0.92, 2.44, 0.404,
                [("n-b", 16, "2026-10-02"), ("n-b", 16, "2026-10-05"), ("n-b", 16, "2026-10-08"),
                 ("n-c", 14, "2026-10-11")],
                log_interval=COARSE_INTERVAL,
                launch_script="launch/train_v3.sh",
            ),
            _run("cfg-15", 1.10, 2.27, 0.318, [("n-c", 16, "2026-10-03"), ("n-b", 15, "2026-10-08")]),
        ],
    ),
    _spec(
        campaign="pretrain-sweep-2026-10b",
        as_of="2026-10-26",
        seed=223_7053,
        node_steps_per_hour={"n-a": 1245, "n-b": 715, "n-c": 395},
        reserved=["n-a"],
        grant=61,
        instrument_k=0.094,
        noise_sd=0.019,
        runs=[
            _run("cfg-21", 1.05, 2.38, 0.296, [("n-a", 16, "2026-10-15"), ("n-a", 15, "2026-10-19"),
                                               ("n-b", 10, "2026-10-23")]),
            _run("cfg-22", 0.88, 2.21, 0.381, [("n-b", 16, "2026-10-16"), ("n-b", 16, "2026-10-20"),
                                               ("n-b", 7, "2026-10-24")]),
            _run("cfg-23", 1.13, 2.56, 0.334, [("n-c", 15, "2026-10-14"), ("n-b", 14, "2026-10-18"),
                                               ("n-b", 16, "2026-10-22")]),
            _run(
                "cfg-24", 1.00, 2.30, 0.309,
                [("n-a", 14, "2026-10-15"), ("n-a", 16, "2026-10-18"), ("n-b", 16, "2026-10-21")],
                log_interval=COARSE_INTERVAL,
                launch_script="launch/train_v3.sh",
            ),
            _run("cfg-25", 0.97, 2.09, 0.352, [("n-c", 16, "2026-10-17"), ("n-c", 16, "2026-10-21"),
                                               ("n-b", 12, "2026-10-25")]),
            _run("cfg-26", 1.09, 2.47, 0.318, [("n-b", 15, "2026-10-16"), ("n-a", 13, "2026-10-20")]),
        ],
    ),
    _spec(
        campaign="pretrain-sweep-2026-11a",
        as_of="2026-11-09",
        seed=334_1067,
        node_steps_per_hour={"n-a": 1305, "n-b": 845, "n-c": 460},
        reserved=["n-a"],
        grant=47,
        instrument_k=0.047,
        noise_sd=0.010,
        runs=[
            _run("cfg-31", 0.91, 2.16, 0.372, [("n-b", 14, "2026-10-30"), ("n-c", 16, "2026-11-04"),
                                               ("n-b", 5, "2026-11-07")]),
            _run("cfg-32", 1.07, 2.44, 0.293, [("n-a", 16, "2026-10-29"), ("n-a", 14, "2026-11-02"),
                                               ("n-a", 15, "2026-11-06")]),
            _run("cfg-33", 1.12, 2.33, 0.327, [("n-b", 16, "2026-10-31"), ("n-b", 15, "2026-11-05")]),
            _run(
                "cfg-34", 1.03, 2.51, 0.341,
                [("n-a", 16, "2026-10-30"), ("n-a", 16, "2026-11-03"), ("n-b", 16, "2026-11-06"),
                 ("n-b", 14, "2026-11-08")],
                log_interval=COARSE_INTERVAL,
                launch_script="launch/train_v3.sh",
            ),
            _run("cfg-35", 0.99, 2.26, 0.310, [("n-b", 12, "2026-11-01"), ("n-c", 14, "2026-11-06")]),
            _run("cfg-36", 1.15, 2.39, 0.356, [("n-c", 15, "2026-10-31"), ("n-b", 16, "2026-11-04"),
                                               ("n-b", 16, "2026-11-08")]),
            _run("cfg-37", 0.99, 2.05, 0.284, [("n-a", 15, "2026-10-29"), ("n-b", 16, "2026-11-05")]),
        ],
    ),
    _spec(
        campaign="pretrain-sweep-2026-11b",
        as_of="2026-11-23",
        seed=445_3079,
        node_steps_per_hour={"n-a": 1180, "n-b": 800, "n-c": 520},
        reserved=["n-a"],
        grant=57,
        instrument_k=0.083,
        noise_sd=0.013,
        runs=[
            _run("cfg-41", 1.04, 2.29, 0.305, [("n-b", 16, "2026-11-12"), ("n-b", 15, "2026-11-17"),
                                               ("n-c", 16, "2026-11-21")]),
            _run(
                "cfg-42", 0.93, 2.41, 0.396,
                [("n-b", 16, "2026-11-13"), ("n-b", 16, "2026-11-16"), ("n-b", 16, "2026-11-19"),
                 ("n-b", 8, "2026-11-22")],
                log_interval=COARSE_INTERVAL,
                launch_script="launch/train_v3.sh",
            ),
            _run("cfg-43", 1.11, 2.18, 0.288, [("n-a", 16, "2026-11-12"), ("n-a", 16, "2026-11-16"),
                                               ("n-a", 14, "2026-11-20")]),
            _run("cfg-44", 1.08, 2.50, 0.336, [("n-b", 14, "2026-11-14"), ("n-c", 15, "2026-11-19")]),
            _run("cfg-45", 0.98, 2.12, 0.322, [("n-c", 16, "2026-11-13"), ("n-b", 16, "2026-11-18"),
                                               ("n-b", 16, "2026-11-22")]),
        ],
    ),
    _spec(
        campaign="pretrain-sweep-2026-12a",
        as_of="2026-12-07",
        seed=556_5081,
        node_steps_per_hour={"n-a": 1060, "n-b": 730, "n-c": 415},
        reserved=["n-a"],
        grant=51,
        instrument_k=0.070,
        noise_sd=0.016,
        runs=[
            _run("cfg-51", 1.01, 2.34, 0.318, [("n-a", 15, "2026-11-26"), ("n-b", 16, "2026-12-01"),
                                               ("n-b", 16, "2026-12-05")]),
            _run("cfg-52", 0.90, 2.23, 0.389, [("n-b", 16, "2026-11-27"), ("n-c", 16, "2026-12-02"),
                                               ("n-b", 6, "2026-12-06")]),
            _run("cfg-53", 1.13, 2.45, 0.297, [("n-a", 16, "2026-11-26"), ("n-a", 16, "2026-12-01"),
                                               ("n-a", 15, "2026-12-04")]),
            _run("cfg-54", 1.06, 2.28, 0.344, [("n-b", 15, "2026-11-28"), ("n-b", 14, "2026-12-03")]),
            _run(
                "cfg-55", 0.99, 2.52, 0.352,
                [("n-a", 16, "2026-11-27"), ("n-a", 16, "2026-11-30"), ("n-b", 16, "2026-12-02"),
                 ("n-b", 15, "2026-12-06")],
                log_interval=COARSE_INTERVAL,
                launch_script="launch/train_v3.sh",
            ),
            _run("cfg-56", 1.10, 2.16, 0.309, [("n-c", 15, "2026-11-29"), ("n-b", 16, "2026-12-04")]),
            _run("cfg-57", 0.91, 2.37, 0.365, [("n-b", 16, "2026-11-26"), ("n-c", 16, "2026-12-01"),
                                               ("n-b", 16, "2026-12-05")]),
        ],
    ),
)


LIFTED_SPEC = _spec(
    campaign="pretrain-sweep-2027-01",
    as_of="2027-01-18",
    seed=667_7093,
    node_steps_per_hour={"n-a": 1300, "n-b": 845, "n-c": 500},
    reserved=["n-a"],
    grant=36,
    instrument_k=0.052,
    noise_sd=0.010,
    runs=[
        _run("cfg-61", 1.09, 2.40, 0.315, [("n-a", 16, "2027-01-09")]),
        _run("cfg-62", 1.12, 2.47, 0.298, [("n-b", 16, "2027-01-09")]),
        _run("cfg-63", 0.62, 2.33, 0.322, [("n-a", 16, "2027-01-10")]),
        _run("cfg-64", 1.05, 2.28, 0.336, [("n-c", 16, "2027-01-10")]),
        _run("cfg-65", 1.14, 2.51, 0.307, [("n-b", 16, "2027-01-11")]),
    ],
)


COARSE_LEADER_SPEC = FOLLOWING_SPECS[3]


_CACHE: dict[tuple[str, str, int], world.Campaign] = {}


def campaign(
    spec: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]] = (),
    presentation: str = "as recorded",
) -> world.Campaign:
    key = (str(spec["campaign"]), presentation, len(receipts))
    if not receipts and key in _CACHE:
        return _CACHE[key]
    built = world.build(world.presented(spec, presentation), receipts)
    if not receipts:
        _CACHE[key] = built
    return built


def current(
    receipts: Sequence[Mapping[str, Any]] = (), presentation: str = "as recorded"
) -> world.Campaign:
    return campaign(CURRENT_SPEC, receipts, presentation)


def following() -> tuple[world.Campaign, ...]:
    return tuple(campaign(spec) for spec in FOLLOWING_SPECS)


def lifted() -> world.Campaign:
    return campaign(LIFTED_SPEC)


OPENING_BOOKINGS = (
    ("cfg-01", "n-b", 6, "sweep-0912-a", "2026-09-12"),
    ("cfg-02", "n-a", 12, "sweep-0913-a", "2026-09-13"),
    ("cfg-04", "n-b", 20, "sweep-0913-b", "2026-09-13"),
)


def opening_receipts() -> list[dict[str, Any]]:
    'The receipt stream the window opens with.'

    base = current()
    entries: list[dict[str, Any]] = []
    for config_id, node_type, hours, receipt_id, day in OPENING_BOOKINGS:
        entries = world.review(base, entries, config_id, node_type, hours, receipt_id, day)
    return entries


def opening_document() -> dict[str, Any]:
    return world.receipt_document(current(), opening_receipts())


ARCHIVED_BOOKINGS: Mapping[str, tuple[tuple[str, str, int, str], ...]] = {
    "pretrain-sweep-2026-10a": (("cfg-11", "n-c", 8, "oct-a-1"), ("cfg-15", "n-a", 10, "oct-a-2")),
    "pretrain-sweep-2026-10b": (("cfg-26", "n-c", 8, "oct-b-1"), ("cfg-23", "n-a", 12, "oct-b-2")),
    "pretrain-sweep-2026-11a": (("cfg-33", "n-c", 8, "nov-a-1"), ("cfg-36", "n-a", 6, "nov-a-2")),
    "pretrain-sweep-2026-11b": (("cfg-44", "n-c", 8, "nov-b-1"), ("cfg-41", "n-a", 9, "nov-b-2")),
    "pretrain-sweep-2026-12a": (("cfg-56", "n-c", 8, "dec-a-1"), ("cfg-53", "n-a", 14, "dec-a-2")),


    "pretrain-sweep-2027-01": (("cfg-65", "n-a", 8, "jan-1"), ("cfg-62", "n-b", 20, "jan-2")),
}


def archived_receipts(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The receipt stream a later window had already run up.'

    base = campaign(spec)
    entries: list[dict[str, Any]] = []
    for config_id, node_type, hours, receipt_id in ARCHIVED_BOOKINGS[str(spec["campaign"])]:
        entries = world.review(
            base, entries, config_id, node_type, hours, receipt_id, str(spec["as_of"])
        )
    return entries
