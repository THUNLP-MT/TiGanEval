"The world behind the header apportionment, and the analyser desk's instrument."

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence


SUPPLIES = ("district_tie_in", "gas_plant", "data_hall_recovery")
CHANNELS = ("conductivity", "marker", "ripple")
LEDGER_FILE = "sample_ledger.json"


_SEAL_KEY = hashlib.sha256(b"authored-inline-analyser-desk-2026-02-02").digest()
_LOCK = threading.RLock()


def days_from(first_day: str, count: int) -> list[str]:
    start = date.fromisoformat(str(first_day))
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def shift_day(day: str, amount: int) -> str:
    return (date.fromisoformat(str(day)) + timedelta(days=amount)).isoformat()


def _unit(*parts: Any) -> float:
    'A fixed standard-normal draw for one named measurement.'

    key = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=16).digest()
    first = int.from_bytes(digest[:8], "big") / float(1 << 64)
    second = int.from_bytes(digest[8:], "big") / float(1 << 64)
    first = min(max(first, 1e-12), 1.0 - 1e-12)
    return math.sqrt(-2.0 * math.log(first)) * math.cos(2.0 * math.pi * second)


def solve3(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    'Gaussian elimination on a 3x3 system, so no array library is needed.'

    rows = [[float(value) for value in row] + [float(rhs[index])]
            for index, row in enumerate(matrix)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(rows[index][column]))
        if abs(rows[pivot][column]) < 1e-12:
            raise ZeroDivisionError("the three signatures do not separate")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(3):
            if index == column:
                continue
            factor = rows[index][column] / rows[column][column]
            for position in range(column, 4):
                rows[index][position] -= factor * rows[column][position]
    return [rows[index][3] / rows[index][index] for index in range(3)]


def _minutes(stamp: str) -> int:
    moment = datetime.fromisoformat(str(stamp))
    return moment.hour * 60 + moment.minute


def _clock(text: str) -> int:
    hour, minute = str(text).split(":")
    return int(hour) * 60 + int(minute)


@dataclass(frozen=True)
class World:
    "One block's window: its weather, its meter, its samples, its events."

    spec: Mapping[str, Any]
    days: tuple[str, ...]
    temperature: Mapping[str, float]
    kwh: Mapping[str, float]
    samples: tuple[Mapping[str, Any], ...]

    @property
    def lot(self) -> str:
        return str(self.spec["lot"])

    @property
    def draw(self) -> str:
        'Which stream of analyser noise this lot reads.'

        return str(self.spec.get("noise_lot", self.spec["lot"]))

    @property
    def sheet_day(self) -> str:
        return str(self.spec["sheet_read_on"])

    @property
    def sheet_outdoor_C(self) -> float:
        return float(self.spec["sheet_outdoor_C"])


    def mixture(self, day: str) -> tuple[float, float, float]:
        "The three supplies' shares of that day's delivered heat."

        temperature = float(self.temperature[str(day)])
        base = float(self.spec["mixture_base_C"])
        recovery = (
            float(self.spec["recovery_at_base"])
            + float(self.spec["recovery_per_C"]) * (temperature - base)
        )
        gas = (
            float(self.spec["gas_at_base"])
            + float(self.spec["gas_per_C"]) * (temperature - base)
        )
        return (1.0 - recovery - gas, gas, recovery)

    def tie_in_conductivity(self, temperature: float) -> float:
        "The district tie-in's conductivity index at one outdoor temperature."

        return float(self.spec["signatures"]["conductivity"][0]) - float(
            self.spec["shift_per_C"]
        ) * (self.sheet_outdoor_C - float(temperature))

    def endmembers(self, temperature: float) -> dict[str, tuple[float, float, float]]:
        signatures = self.spec["signatures"]
        conductivity = list(signatures["conductivity"])
        conductivity[0] = self.tie_in_conductivity(temperature)
        return {
            "conductivity": tuple(float(value) for value in conductivity),
            "marker": tuple(float(value) for value in signatures["marker"]),
            "ripple": tuple(float(value) for value in signatures["ripple"]),
        }

    def event_at(self, stamp: str) -> Mapping[str, Any] | None:
        'The operations entry open when a sample was drawn, if any.'

        day = str(stamp)[:10]
        minute = _minutes(stamp)
        for entry in self.spec["operations"]:
            if str(entry["day"]) != day:
                continue
            if _clock(entry["from"]) <= minute < _clock(entry["to"]):
                return entry
        return None

    def mixture_at(self, stamp: str) -> tuple[float, float, float]:
        'What the header actually carried at one moment.'

        event = self.event_at(stamp)
        if event is not None and event.get("held_mixture"):
            return tuple(float(value) for value in event["held_mixture"])
        return self.mixture(str(stamp)[:10])


    def _pure(self, point: str, temperature: float) -> tuple[float, float, float] | None:
        'The mixture a sampling point carries when it is not the header.'

        index = {
            "tie_in_plant_room": 0,
            "gas_plant_room": 1,
            "east_riser": 2,
        }.get(str(point))
        if index is None:
            return None
        mix = [0.0, 0.0, 0.0]
        mix[index] = 1.0
        return tuple(mix)

    def read(
        self,
        point: str,
        stamp: str,
        dwell_min: int,
        channels: Sequence[str],
        key: str,
    ) -> dict[str, Any]:
        'One slot on the analyser: what the sheet prints for it.'

        day = str(stamp)[:10]
        temperature = float(self.temperature.get(day, self.sheet_outdoor_C))
        mix = self._pure(point, temperature)
        if mix is None:
            mix = self.mixture_at(stamp)
        ends = self.endmembers(temperature)
        sigma = self.spec["sigma"]
        dwell = int(dwell_min)
        suffix = "30" if dwell >= 30 else "5"
        reading: dict[str, Any] = {"dwell_min": dwell}
        if "conductivity" in channels:
            value = sum(mix[index] * ends["conductivity"][index] for index in range(3))
            value += float(sigma[f"conductivity_{suffix}"]) * _unit(
                self.draw, key, "conductivity"
            )
            reading["cond_uScm"] = round(value, 1)
        if "marker" in channels:
            value = sum(mix[index] * ends["marker"][index] for index in range(3))
            value += float(sigma[f"marker_{suffix}"]) * _unit(self.draw, key, "marker")
            floor = float(self.spec[f"marker_floor_{suffix}"])
            if value < floor:
                reading["mark_muL"] = None
                reading["mark_flag"] = "floor"
                reading["mark_floor_muL"] = floor
            else:
                reading["mark_muL"] = round(value, 2)
                reading["mark_flag"] = "value"
                reading["mark_floor_muL"] = floor
        if "ripple" in channels:
            value = sum(mix[index] * ends["ripple"][index] for index in range(3))
            value += float(sigma["ripple"]) * _unit(self.draw, key, "ripple")
            reading["ripple_idx"] = round(value, 2)
        return reading


    SHEET_SLOTS = 3

    def signature_rows(self) -> list[dict[str, Any]]:
        'The characterisation sheet: each supply read at its own point.'

        rows = []
        floor = float(self.spec["marker_floor_5"])
        for index, supply in enumerate(SUPPLIES):
            point = ("tie_in_plant_room", "gas_plant_room", "east_riser")[index]
            temperature = self.sheet_outdoor_C
            mix = self._pure(point, temperature)
            ends = self.endmembers(temperature)
            sigma = self.spec["sigma"]
            conductivity = sum(
                mix[position] * ends["conductivity"][position] for position in range(3)
            ) + float(sigma["conductivity_5"]) / math.sqrt(self.SHEET_SLOTS) * _unit(
                self.draw, f"sheet-{supply}", "conductivity"
            )
            marker = sum(
                mix[position] * ends["marker"][position] for position in range(3)
            ) + float(sigma["marker_5"]) / math.sqrt(self.SHEET_SLOTS) * _unit(
                self.draw, f"sheet-{supply}", "marker"
            )
            rows.append(
                {
                    "supply": supply,
                    "point": point,
                    "read_on": self.sheet_day,
                    "outdoor_C": self.sheet_outdoor_C,
                    "dwell_min": 5,
                    "slots": self.SHEET_SLOTS,
                    "cond_uScm": round(conductivity, 1),
                    "mark_muL": None if marker < floor else round(marker, 2),
                    "mark_flag": "floor" if marker < floor else "value",
                    "mark_floor_muL": floor,
                }
            )
        return rows

    def sample_rows(self, ledger: Sequence[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
        'Every slot the analyser has drawn for this window, in the order drawn.'

        rows: list[dict[str, Any]] = []
        for entry in ledger:
            if entry.get("refusal"):
                continue
            for reading in entry.get("readings", ()):
                rows.append(dict(reading))
        return rows

    def logged_days(self) -> list[str]:
        'The window and the days the round can still be made on.'

        return [*self.days, *(str(day) for day, _value in self.spec["after_days"])]

    def weather_rows(self) -> list[dict[str, Any]]:
        return [
            {"day": day, "outdoor_C": round(float(self.temperature[day]), 1)}
            for day in self.logged_days()
        ]

    def meter_rows(self) -> list[dict[str, Any]]:
        return [
            {"day": day, "delivered_kwh": round(float(self.kwh[day]), 1)}
            for day in self.logged_days()
        ]

    def operations_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "day": str(entry["day"]),
                "from": str(entry["from"]),
                "to": str(entry["to"]),
                "entry": str(entry["entry"]),
            }
            for entry in self.spec["operations"]
        ]

    def open_days(self) -> list[str]:
        'The days the analyser desk can still serve a visit on.'

        return [str(day) for day in self.spec["collection_days"]]

    def context(self, ledger: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        spec = self.spec
        return {
            "lot": self.lot,
            "block": str(spec["block"]),
            "window": {"first_day": self.days[0], "last_day": self.days[-1]},
            "supplies": list(SUPPLIES),
            "signature_sheet": {
                "read_on": self.sheet_day,
                "outdoor_C": self.sheet_outdoor_C,
                "rows": self.signature_rows(),
            },
            "analyser": {
                "marker_floor_muL": {
                    "5": float(spec["marker_floor_5"]),
                    "30": float(spec["marker_floor_30"]),
                },
                "repeatability": {
                    "5": {
                        "cond_uScm": float(spec["sigma"]["conductivity_5"]),
                        "mark_muL": float(spec["sigma"]["marker_5"]),
                    },
                    "30": {
                        "cond_uScm": float(spec["sigma"]["conductivity_30"]),
                        "mark_muL": float(spec["sigma"]["marker_30"]),
                    },
                    "ripple_idx": float(spec["sigma"]["ripple"]),
                },
                "dwell_options_min": [5, 30],
                "channels": list(CHANNELS),
            },
            "weather": self.weather_rows(),
            "heat_meter": self.meter_rows(),
            "samples": self.sample_rows(ledger),
            "operations": self.operations_rows(),
            "collection": {
                "slots_granted": int(spec["slots_granted"]),
                "slots_per_visit": int(spec["slots_per_visit"]),
                "points": list(spec["access_points"]),
                "long_dwell_slots": int(spec["long_dwell_slots"]),
                "module_slots": int(spec["module_slots"]),
                "open_days": self.open_days(),
            },
            "report_request": {
                "share_within": float(spec["share_within"]),
                "recovery_band_half_width_at_most": float(spec["band_ask"]),
            },
        }


    def slots_spent(self, ledger: Sequence[Mapping[str, Any]]) -> int:
        return int(sum(int(entry["slots_charged"]) for entry in ledger))

    def slots_left(self, ledger: Sequence[Mapping[str, Any]]) -> int:
        return int(self.spec["slots_granted"]) - self.slots_spent(ledger)


def daily_kwh(spec: Mapping[str, Any], temperature: float) -> float:
    return 24.0 * (
        float(spec["load_base_kw"])
        + float(spec["load_per_C_kw"]) * (float(spec["load_base_C"]) - float(temperature))
    )


def build(spec: Mapping[str, Any]) -> World:
    'Run one window: its weather, its meter, its round of samples.'

    days = tuple(days_from(spec["first_day"], int(spec["days"])))
    after = tuple(str(day) for day, _value in spec["after_days"])
    temperature = {day: float(value) for day, value in zip(days, spec["outdoor_C"])}
    temperature.update({str(day): float(value) for day, value in spec["after_days"]})
    kwh = {day: daily_kwh(spec, temperature[day]) for day in (*days, *after)}
    world = World(spec=spec, days=days, temperature=temperature, kwh=kwh, samples=())

    samples: list[dict[str, Any]] = []
    counter = 0
    for visit in spec["visits"]:
        for stamp in visit["at"]:
            counter += 1
            sample_id = f"{spec['sample_prefix']}-{counter:03d}"
            reading = world.read(
                str(visit["point"]),
                str(stamp),
                int(visit.get("dwell_min", 5)),
                ("conductivity", "marker"),
                sample_id,
            )
            samples.append(
                {
                    "sample_id": sample_id,
                    "taken_at": str(stamp),
                    "point": str(visit["point"]),
                    "cond_uScm": reading["cond_uScm"],
                    "mark_muL": reading["mark_muL"],
                    "mark_flag": reading["mark_flag"],
                    "dwell_min": reading["dwell_min"],
                }
            )
    return World(
        spec=spec,
        days=days,
        temperature=temperature,
        kwh=kwh,
        samples=tuple(samples),
    )


def redrawn(spec: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    grown = dict(spec)
    grown.update(changes)
    return grown


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def slot_cost(point: str, dwell_min: int, samples: int, channels: Sequence[str],
              spec: Mapping[str, Any]) -> int:
    'What the desk charges for one visit, whether or not it is served.'

    per_sample = int(spec["long_dwell_slots"]) if int(dwell_min) >= 30 else 1
    cost = per_sample * int(samples)
    if "ripple" in channels:
        cost += int(spec["module_slots"])
    return int(cost)


def refusal_reason(
    world: World,
    point: Any,
    dwell_min: Any,
    samples: Any,
    channels: Sequence[str],
) -> str | None:
    'Why the desk would hand a visit back and charge for it anyway.'

    spec = world.spec
    if str(point) not in spec["access_points"]:
        return f"{point} is not on the access list the agreement carries"
    if int(dwell_min) not in (5, 30):
        return "the analyser dwells for five minutes or for thirty, nothing else"
    cost = slot_cost(str(point), int(dwell_min), int(samples), channels, spec)
    if cost > int(spec["slots_per_visit"]):
        return (
            f"a visit carries {spec['slots_per_visit']} slots and this one asks for {cost}"
        )
    return None


def receipt(
    world: World,
    call_id: str,
    point: str,
    dwell_min: int,
    samples: int,
    channels: Sequence[str],
    served_on: str,
    sequence: int,
    previous: str,
    slots_left_after: int,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    'One visit as the desk writes it up.'

    ordered = tuple(name for name in CHANNELS if name in channels)
    refusal = refusal_reason(world, point, dwell_min, samples, ordered)
    charged = slot_cost(str(point), int(dwell_min), int(samples), ordered, world.spec)
    if rows is not None:
        rows = [dict(row) for row in rows]
    else:
        rows = []
        if refusal is None:
            for index in range(int(samples)):
                stamp = f"{served_on}T{9 + index:02d}:{20 + 5 * index:02d}:00"
                reading = world.read(
                    str(point), stamp, int(dwell_min), ordered, f"{call_id}-{index + 1}"
                )
                rows.append(
                    {
                        "sample_id": f"{call_id}-{index + 1}",
                        "taken_at": stamp,
                        "point": str(point),
                        **reading,
                    }
                )
    body = {
        "lot": world.lot,
        "sequence": int(sequence),
        "call_id": str(call_id),
        "point": str(point),
        "channels": list(ordered),
        "dwell_min": int(dwell_min),
        "slots_requested": charged,
        "slots_charged": charged,
        "served_on": str(served_on),
        "refusal": refusal,
        "outdoor_C": round(float(world.temperature.get(str(served_on), world.sheet_outdoor_C)), 1),
        "readings": rows,


        "plant_ripple_idx": (
            {
                supply: round(
                    float(world.spec["signatures"]["ripple"][index])
                    + float(world.spec["sigma"]["ripple"])
                    * _unit(world.draw, f"{call_id}-plant", supply),
                    2,
                )
                for index, supply in enumerate(SUPPLIES)
            }
            if refusal is None and "ripple" in ordered
            else {}
        ),
        "slots_left_after": int(slots_left_after),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def stream(world: World, visits: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    'The receipts for the visits that produced a frozen history.'

    by_day: dict[str, list[Mapping[str, Any]]] = {}
    for sample in world.samples:
        by_day.setdefault(str(sample["taken_at"])[:10], []).append(sample)
    entries: list[dict[str, Any]] = []
    left = int(world.spec["slots_granted"])
    for visit in visits:
        channels = tuple(visit.get("channels", ("conductivity", "marker")))
        charged = slot_cost(
            str(visit["point"]), int(visit.get("dwell_min", 5)),
            int(visit["samples"]), channels, world.spec,
        )
        left -= charged
        rows = (
            by_day.get(str(visit["served_on"]), [])
            if str(visit["point"]) == "header"
            else None
        )
        entries.append(
            receipt(
                world,
                str(visit["call_id"]),
                str(visit["point"]),
                int(visit.get("dwell_min", 5)),
                int(visit["samples"]),
                channels,
                str(visit["served_on"]),
                len(entries) + 1,
                entries[-1]["seal"] if entries else "",
                left,
                rows=None if rows is None else list(rows),
            )
        )
    return entries


def read_ledger(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every visit this window has been charged for, or why the stream is broken.'

    path = Path(workspace) / LEDGER_FILE
    if path.is_symlink():
        raise ValueError("the visit ledger must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("lot") != world.lot
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the visit ledger does not belong to this window")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a visit receipt is not an analyser record")
        call_id = entry.get("call_id")
        if not isinstance(call_id, str) or not call_id or call_id in seen:
            raise ValueError("a visit receipt has a missing or repeated call id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the visit receipts are not in the order the desk wrote them")
        if entry.get("lot") != world.lot:
            raise ValueError("a visit receipt belongs to another window")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a visit receipt does not carry the desk's seal")
        seen.add(call_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def visits_of(
    ledger: Sequence[Mapping[str, Any]], history: int
) -> list[dict[str, Any]]:
    'The visits on the stream beyond the ones that produced the frozen history.'

    return [
        {
            "call_id": str(entry["call_id"]),
            "point": str(entry["point"]),
            "dwell_min": int(entry["dwell_min"]),
            "samples": len(entry["readings"]) or _requested(entry),
            "channels": tuple(entry["channels"]),
            "served_on": str(entry["served_on"]),
        }
        for entry in list(ledger)[history:]
    ]


def _requested(entry: Mapping[str, Any]) -> int:
    per_sample = 2 if int(entry["dwell_min"]) >= 30 else 1
    charged = int(entry["slots_charged"])
    if "ripple" in entry["channels"]:
        charged -= 2
    return max(1, charged // per_sample)


def sample_visit(
    workspace: Path,
    world: World,
    history: Sequence[Mapping[str, Any]],
    point: Any,
    channels: Any,
    dwell_min: Any,
    samples: Any,
    call_id: Any,
) -> dict[str, Any]:
    "Send the contractor out once and append the desk's receipt."

    if not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 120:
        raise ValueError("call_id must be a short non-empty label you choose")
    if not isinstance(samples, int) or isinstance(samples, bool) or samples < 1:
        raise ValueError("samples must be a whole number of slots, at least one")
    if not isinstance(dwell_min, int) or isinstance(dwell_min, bool):
        raise ValueError("dwell_min must be a whole number of minutes")
    if isinstance(channels, str):
        channels = [channels]
    if channels is None:
        channels = ["conductivity", "marker"]
    if not isinstance(channels, (list, tuple)) or not channels:
        raise ValueError("channels must name at least one of the analyser's channels")
    unknown = [name for name in channels if name not in CHANNELS]
    if unknown:
        raise ValueError(f"the analyser has no channel called {unknown[0]}")
    ordered = tuple(name for name in CHANNELS if name in channels)
    if not isinstance(point, str) or not point.strip():
        raise ValueError("point must name where the contractor is to draw the sample")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_ledger(root, world)
        for entry in entries:
            if entry["call_id"] == call_id:
                same = (
                    entry["point"] == point
                    and entry["dwell_min"] == dwell_min
                    and list(entry["channels"]) == list(ordered)
                )
                if not same:
                    raise ValueError("that call id already names another visit")
                return {
                    "receipt": entry,
                    "served": False,
                    "slots_spent": world.slots_spent(entries),
                    "slots_left": world.slots_left(entries),
                }
        charged = slot_cost(str(point), int(dwell_min), int(samples), ordered, world.spec)
        left = world.slots_left(entries)
        if charged > left:
            raise ValueError(
                f"this visit costs {charged} slots and the window has {left} left of the "
                f"{world.spec['slots_granted']} the agreement carries"
            )
        open_days = world.open_days()
        used = {str(entry["served_on"]) for entry in entries[len(history):]}
        free = [day for day in open_days if day not in used]
        if not free:
            raise ValueError(
                "the contractor has no round left inside the window; every open day is served"
            )
        made = receipt(
            world,
            call_id,
            str(point),
            int(dwell_min),
            int(samples),
            ordered,
            free[0],
            len(entries) + 1,
            entries[-1]["seal"] if entries else "",
            left - charged,
        )
        entries.append(made)
        pending = root / "sample_ledger.pending"
        pending.write_text(
            json.dumps({"lot": world.lot, "entries": entries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(pending, root / LEDGER_FILE)
        return {
            "receipt": made,
            "served": True,
            "slots_spent": world.slots_spent(entries),
            "slots_left": world.slots_left(entries),
        }
