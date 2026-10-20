'Deterministic handset sessions: device slots, depot answers, screen schedules.'

from __future__ import annotations

from typing import Any, Mapping, Sequence

def key_name(query_key: Sequence[Any]) -> str:
    "The app's one name for a query, as the console prints it."
    return "|".join(str(part) for part in query_key)

def _rows(prefix: str, *numbers: int) -> list[dict[str, Any]]:
    return [{"id": f"{prefix}-{n}", "meter": f"M{n:04d}"} for n in numbers]

def _pages(prefix: str, *cursors: str) -> dict[str, Any]:
    return {"pages": [_rows(prefix, i + 1, i + 2) for i in range(len(cursors))],
            "cursors": list(cursors)}


_EMPTY: Mapping[str, Any] = {
    "data": None, "error": None, "status": "pending", "fetch_status": "idle",
    "failure_count": 0, "failure_reason": None, "data_updated_at": 0,
    "error_updated_at": 0, "data_update_count": 0, "error_update_count": 0,
    "is_invalidated": False,
}

def _slot(key: Sequence[str], **fields: Any) -> dict[str, Any]:
    return {"key": [str(part) for part in key], "state": {**_EMPTY, **fields}}

def _device(phase: str, slots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"op": "device", "label": f"device-{phase}", "slots": [dict(s) for s in slots]}

def _at(ms: int) -> dict[str, Any]:
    return {"op": "clock", "to": int(ms), "label": f"clock-{int(ms)}"}

def _wait(ms: int) -> dict[str, Any]:
    return {"op": "wait", "ms": int(ms), "label": f"wait-{int(ms)}"}

def _open(label: str = "open") -> dict[str, Any]:
    return {"op": "open", "label": label}

def _rebuild(label: str = "rebuild") -> dict[str, Any]:
    return {"op": "rebuild", "label": label}

def _touch(op: str, key: Sequence[str], label: str) -> dict[str, Any]:
    return {"op": op, "key": [str(p) for p in key], "label": label}

def _save(key: Sequence[str], label: str) -> dict[str, Any]:
    return {"op": "save", "key": [str(p) for p in key], "label": label}

def _answers(*rows: Any) -> list[dict[str, Any]]:
    return [{"data": row, "cost_ms": 0} for row in rows]

def _silence(message: str) -> list[dict[str, Any]]:
    return [{"error": message, "cost_ms": 0}]

def _phase(name: str, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**dict(op), "phase": name} for op in ops]

def _slot_keys(slots: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    return [list(slot["key"]) for slot in slots]

REFUSED = "the depot would not take the reading"
NO_SIGNAL = "the van has no signal here"
LATE = "the depot did not answer in time"


_REOPEN_SLOTS = (
    _slot(("ticket", "7731"), data=_rows("t7731", 1, 2, 3), status="success",
          data_updated_at=120000, data_update_count=5),
    _slot(("ticket", "7732"), data=_rows("t7732", 4, 5), error=REFUSED, status="error",
          failure_count=3, failure_reason=REFUSED, data_updated_at=118000,
          error_updated_at=131000, data_update_count=4, error_update_count=3,
          is_invalidated=True),
    _slot(("ticket", "7733"), error=NO_SIGNAL, status="error", failure_count=2,
          failure_reason=NO_SIGNAL, error_updated_at=129000, error_update_count=2),


    _slot(("survey", "east"), data=_rows("seast", 7, 8), status="error",
          data_updated_at=125000, data_update_count=2),
    _slot(("survey", "west"), data=_rows("swest", 9), error=REFUSED, status="success",
          failure_count=1, failure_reason=REFUSED, data_updated_at=126000,
          error_updated_at=133000, data_update_count=2, error_update_count=1),
    _slot(("visits", "van-9"), data=_pages("v9", "c-101", "c-102"), status="success",
          data_updated_at=127000, data_update_count=3, is_invalidated=True),
)

_OFFLINE_SLOTS = (
    _slot(("round", "north"), data=_rows("rn", 1, 2), status="success",
          data_updated_at=280000, data_update_count=7),
    _slot(("round", "south"), data=_rows("rs", 3), error=REFUSED, status="error",
          failure_count=4, failure_reason=REFUSED, data_updated_at=279000,
          error_updated_at=288000, data_update_count=6, error_update_count=4),
    _slot(("stock", "van-9"), data=_rows("s9", 5, 6), status="success",
          data_updated_at=281000, data_update_count=2),
    _slot(("ticket", "7740"), error=NO_SIGNAL, status="error", failure_count=1,
          failure_reason=NO_SIGNAL, error_updated_at=287000, error_update_count=1),
)


_WRITER_FIELDS: Mapping[str, Any] = dict(
    data=_rows("j41", 1, 2), error=LATE, status="error", failure_count=4,
    failure_reason=LATE, data_updated_at=380000, error_updated_at=390000,
    data_update_count=6, error_update_count=4)
_WRITER_SLOTS = (
    _slot(("job", "4180"), fetch_status="idle", **_WRITER_FIELDS),
    _slot(("job", "4181"), fetch_status="fetching", **_WRITER_FIELDS),
    _slot(("job", "4182"), fetch_status="paused", **_WRITER_FIELDS),
)

_TWOWAYS_SLOTS = (
    _slot(("round", "east"), data=_rows("re", 1, 2), error=REFUSED, status="error",
          failure_count=2, failure_reason=REFUSED, data_updated_at=470000,
          error_updated_at=488000, data_update_count=9, error_update_count=2),
    _slot(("stock", "van-4"), data=_rows("s4", 3), status="success",
          data_updated_at=472000, data_update_count=4),
    _slot(("visits", "van-4"), data=_pages("v4", "c-201", "c-202", "c-203"),
          status="success", data_updated_at=474000, data_update_count=5,
          is_invalidated=True),
)


_RACE_SLOTS = (
    _slot(("round", "central"), data=_rows("rc", 1), error=REFUSED, status="error",
          failure_count=3, failure_reason=REFUSED, data_updated_at=590000,
          error_updated_at=598000, data_update_count=4, error_update_count=3),
    _slot(("stock", "van-7"), data=_rows("s7", 2, 3), error=NO_SIGNAL, status="error",
          failure_count=2, failure_reason=NO_SIGNAL, data_updated_at=592000,
          error_updated_at=570000, data_update_count=5, error_update_count=2),
)

def _release_operations() -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []

    reopen = [_device("reopen", _REOPEN_SLOTS), _at(200000), _open()]
    for index, key in enumerate(_slot_keys(_REOPEN_SLOTS), start=1):
        reopen += [_touch("mount", key, f"reopen-mount-{index}"),
                   _touch("read", key, f"reopen-{index}"), _wait(40)]
    ops += _phase("reopen", reopen)

    keys = _slot_keys(_OFFLINE_SLOTS)
    offline = [_device("offline", _OFFLINE_SLOTS), _at(300000), _open(),
               _rebuild("rebuild-offline")]
    offline += [_touch("read", key, f"offline-boot-{i}") for i, key in enumerate(keys, start=1)]
    for index, key in enumerate(keys, start=1):
        offline += [_touch("mount", key, f"offline-mount-{index}"),
                    _touch("read", key, f"offline-deep-{index}")]
    ops += _phase("offline", offline)

    writer = [_device("writer", _WRITER_SLOTS), _at(400000), _open()]
    for index, key in enumerate(_slot_keys(_WRITER_SLOTS), start=1):
        writer += [_touch("mount", key, f"writer-mount-{index}"),
                   _touch("read", key, f"writer-{index}"), _wait(60)]
    ops += _phase("writer", writer)

    roundtrip_key = ["job", "4190"]
    roundtrip = [_device("roundtrip", ()), _at(450000), _open("open-writer"),
                 _touch("refresh", roundtrip_key, "roundtrip-refresh"),
                 _touch("read", roundtrip_key, "roundtrip-before"),
                 _save(roundtrip_key, "roundtrip-save"),
                 _open("open-after-save"),
                 _touch("mount", roundtrip_key, "roundtrip-mount"),
                 _touch("read", roundtrip_key, "roundtrip-after")]
    ops += _phase("roundtrip", roundtrip)

    keys = _slot_keys(_TWOWAYS_SLOTS)
    twoways = [_device("twoways", _TWOWAYS_SLOTS), _at(500000), _open("open-cold"),
               _rebuild("rebuild-twoways")]
    twoways += [_touch("read", key, f"twoways-cold-{i}") for i, key in enumerate(keys, start=1)]
    twoways += [_open("open-deep-link")]
    for index, key in enumerate(keys, start=1):
        twoways += [_touch("mount", key, f"twoways-mount-{index}"),
                    _touch("read", key, f"twoways-link-{index}")]
    ops += _phase("twoways", twoways)

    race = [_device("race", _RACE_SLOTS), _at(600000), _open(),
            _touch("refresh", ["round", "central"], "race-refresh-1"), _wait(1000),
            _touch("refresh", ["stock", "van-7"], "race-refresh-2"), _wait(500),
            _rebuild("rebuild-race"),
            _touch("read", ["round", "central"], "race-1"),
            _touch("read", ["stock", "van-7"], "race-2")]
    return ops + _phase("race", race)

def _release_depot() -> dict[str, list[dict[str, Any]]]:
    script: dict[str, list[dict[str, Any]]] = {}
    for slot in (*_REOPEN_SLOTS, *_WRITER_SLOTS, *_TWOWAYS_SLOTS):
        name = key_name(slot["key"])
        script[name] = _answers(_rows(f"fresh-{name.replace('|', '-')}", 91, 92))
    for slot in _OFFLINE_SLOTS:
        script[key_name(slot["key"])] = _silence("no signal at the depot yard")
    script[key_name(["round", "central"])] = _answers(_rows("rc-fresh", 11, 12))
    script[key_name(["stock", "van-7"])] = _silence("no signal in the cutting")
    script[key_name(["job", "4190"])] = _answers(
        _rows("j4190-saved", 31, 32), _rows("j4190-later", 41, 42)
    )
    return script


DECLINED = "the depot would not take the reading"
YARD = "no signal at the depot yard"

def _reopen_after_decline() -> dict[str, Any]:
    slots = (
        _slot(("job", "8802"), data=_rows("j8802", 1, 2), error=DECLINED, status="error",
              failure_count=2, failure_reason=DECLINED, data_updated_at=41000,
              error_updated_at=52000, data_update_count=3, error_update_count=2,
              is_invalidated=True),
    )
    ops = [_device("reopen", slots), _at(90000), _open(),
           _touch("mount", ["job", "8802"], "job-screen-mount"),
           _touch("read", ["job", "8802"], "job-screen")]
    return {"start_ms": 0, "operations": _phase("reopen", ops),
            "depot": {key_name(["job", "8802"]): _answers(_rows("j8802-fresh", 7, 8))}}

def _overnight_shift_start() -> dict[str, Any]:
    slots = (
        _slot(("round", "kerbside-1"), data=_rows("k1", 1, 2), status="success",
              data_updated_at=11000, data_update_count=4),
        _slot(("round", "kerbside-2"), data=_rows("k2", 3), error=DECLINED, status="error",
              failure_count=3, failure_reason=DECLINED, data_updated_at=10000,
              error_updated_at=15000, data_update_count=3, error_update_count=3),
        _slot(("stock", "van-3"), data=_rows("s3", 4, 5), status="success",
              data_updated_at=12000, data_update_count=2),
        _slot(("job", "8810"), error=YARD, status="error", failure_count=1,
              failure_reason=YARD, error_updated_at=14000, error_update_count=1),
    )
    keys = _slot_keys(slots)
    ops = [_device("boot", slots), _at(20000), _open("open-cold"), _rebuild()]
    ops += [_touch("read", key, f"cold-{i}") for i, key in enumerate(keys, start=1)]
    ops += [_open("open-second-run")]
    for index, key in enumerate(keys, start=1):
        ops += [_touch("mount", key, f"screen-mount-{index}"),
                _touch("read", key, f"deep-link-{index}")]
    return {"start_ms": 0, "operations": _phase("boot", ops),
            "depot": {key_name(key): _silence(YARD) for key in keys}}

def _saved_mid_refresh() -> dict[str, Any]:
    shared: Mapping[str, Any] = dict(
        data=_rows("j88", 1, 2), error=LATE, status="error", failure_count=3,
        failure_reason=LATE, data_updated_at=51000, error_updated_at=57000,
        data_update_count=8, error_update_count=3)
    slots = (
        _slot(("job", "8821"), fetch_status="idle", **shared),
        _slot(("job", "8822"), fetch_status="fetching", **shared),
        _slot(("job", "8823"), fetch_status="paused", **shared),
        _slot(("survey", "harbour"), data=_rows("sh", 4, 5), status="error",
              data_updated_at=53000, data_update_count=2),
        _slot(("survey", "quay"), data=_rows("sq", 6), error=DECLINED, status="success",
              failure_count=1, failure_reason=DECLINED, data_updated_at=54000,
              error_updated_at=58000, data_update_count=2, error_update_count=1),
        _slot(("visits", "van-3"), data=_pages("v3", "c-11", "c-12"), status="success",
              data_updated_at=55000, data_update_count=6),
    )
    keys = _slot_keys(slots)
    ops = [_device("writer", slots), _at(60000), _open()]
    for index, key in enumerate(keys, start=1):
        ops += [_touch("mount", key, f"screen-mount-{index}"),
                _touch("read", key, f"screen-{index}"), _wait(70)]
    depot = {key_name(key): _answers(_rows(f"fresh-{i}", 21, 22))
             for i, key in enumerate(keys, start=1)}
    return {"start_ms": 0, "operations": _phase("writer", ops), "depot": depot}

def _depot_came_back_first() -> dict[str, Any]:
    slots = (
        _slot(("round", "harbour"), data=_rows("rh", 1), error=DECLINED, status="error",
              failure_count=2, failure_reason=DECLINED, data_updated_at=30000,
              error_updated_at=38000, data_update_count=3, error_update_count=2),
        _slot(("stock", "van-8"), data=_rows("s8", 2, 3), error=YARD, status="error",
              failure_count=1, failure_reason=YARD, data_updated_at=34000,
              error_updated_at=12000, data_update_count=4, error_update_count=1),
    )
    ops = [_device("race", slots), _at(40000), _open(),
           _touch("refresh", ["round", "harbour"], "pull-to-refresh"), _wait(900),
           _touch("refresh", ["stock", "van-8"], "stock-refresh"), _wait(600),
           _rebuild("rebuild-late"),
           _touch("read", ["round", "harbour"], "round-screen"),
           _touch("read", ["stock", "van-8"], "stock-screen")]
    depot = {key_name(["round", "harbour"]): _answers(_rows("rh-fresh", 11, 12)),
             key_name(["stock", "van-8"]): _silence("no signal in the cutting")}
    return {"start_ms": 0, "operations": _phase("race", ops), "depot": depot}

def _writer_round_trip() -> dict[str, Any]:
    key = ["job", "8890"]
    ops = [_device("roundtrip", ()), _at(70000), _open("open-writer"),
           _touch("refresh", key, "loaded-from-depot"),
           _touch("read", key, "screen-before-save"),
           _save(key, "background-save"),
           _open("open-after-save"),
           _touch("mount", key, "screen-after-restart-mount"),
           _touch("read", key, "screen-after-restart")]
    depot = {key_name(key): _answers(
        _rows("j8890-saved", 51, 52), _rows("j8890-later", 61, 62)
    )}
    return {"start_ms": 0, "operations": _phase("roundtrip", ops), "depot": depot}

PUBLIC_PROGRAMS = {
    "reopen-after-decline": _reopen_after_decline,
    "overnight-shift-start": _overnight_shift_start,
    "saved-mid-refresh": _saved_mid_refresh,
    "depot-came-back-first": _depot_came_back_first,
    "writer-round-trip": _writer_round_trip,
}

def build_program(profile: str) -> dict[str, Any]:
    "The device slots, the depot's answers and the screens for one session."
    if profile == "release":
        return {"start_ms": 0, "depot": _release_depot(),
                "operations": _release_operations()}
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown handset session: {profile}")
    return builder()

def all_slots(program: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    'Every snapshot the session installs, by query name.'
    found: dict[str, dict[str, Any]] = {}
    for op in program.get("operations", ()):
        if str(op.get("op")) == "device":
            for slot in op.get("slots", ()):
                found[key_name(slot["key"])] = dict(slot)
    return found
