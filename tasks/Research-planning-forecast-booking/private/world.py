'The dispatch network behind the two area sheets, and what it does to a number.'

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
from typing import Any, Mapping, Sequence


WINDOWS = ("W1", "W2", "W3", "W4")
AREAS = ("Harbour", "Ridge")


METER_STEP = 5


_UNIT = Fraction(173, 100)


def fraction(value: Any) -> Fraction:
    return Fraction(str(value))


def _digest(*parts: str) -> int:
    return int(hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:8], 16)


_FORECAST_CACHE: dict[tuple[str, str, str, str], int] = {}
_CENTRE_CACHE: dict[tuple[str, str, str], Fraction] = {}
_MISS_CACHE: dict[tuple[str, str, str, str], Fraction] = {}
_METER_CACHE: dict[tuple[str, str, str, str, str, int], int] = {}


def _unit_draw(*parts: str) -> Fraction:
    'A deterministic draw on [-1, 1] with three decimal places.'

    return Fraction(_digest(*parts) % 2001 - 1000, 1000)


def round_to(value: Fraction, step: int) -> int:
    'One reading as the meter reports it, halves rounding up.'

    scaled = value / step
    whole = scaled.numerator // scaled.denominator
    if scaled - whole >= Fraction(1, 2):
        whole += 1
    return int(whole * step)


def whole(value: Fraction) -> int:
    return round_to(value, 1)


ARRANGEMENTS = ("as issued", "lag", "move")


def arrangement_note(arrangement: str) -> str:
    'What is different about the sheets, in the words the desk would use.'

    if arrangement == "lag":
        return "the same two sheets with the engines' cut times the other way round"
    if arrangement == "move":
        return "the same zones with the transfer taking effect on the shift being ordered"
    return "the sheets as they were issued"


@dataclass(frozen=True)
class World:
    'One campaign of a dispatch desk: its zones, its shifts and its allowance.'

    spec: Mapping[str, Any]


    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def label(self) -> str:
        return str(self.spec["label"])

    @property
    def shifts(self) -> tuple[str, ...]:
        return tuple(self.spec["shifts"])

    @property
    def lead_in(self) -> str:
        return str(self.spec["lead_in"])

    @property
    def settled_count(self) -> int:
        return int(self.spec["settled_shifts"])

    @property
    def moved_zone(self) -> str | None:
        value = self.spec.get("moved_zone")
        return None if value is None else str(value)

    def index_of(self, shift: str) -> int:
        return self.shifts.index(str(shift))

    def previous_stamp(self, shift: str) -> str:
        "One place back on the campaign's shift calendar, not one day back."

        index = self.index_of(shift)
        return self.lead_in if index == 0 else self.shifts[index - 1]


    def early_area(self, arrangement: str = "as issued") -> str | None:
        'The area whose engine stamps a row with the shift it cut the sheet on.'

        base = self.spec.get("early_area")
        if base is None:
            return None
        if arrangement != "lag":
            return str(base)
        other = [area for area in AREAS if area != str(base)]
        return other[0]

    def stamp_for(self, area: str, shift: str, arrangement: str = "as issued") -> str:
        "The stamp the area's engine puts on the rows for `shift`."

        if str(area) == self.early_area(arrangement):
            return self.previous_stamp(shift)
        return str(shift)


    @property
    def zones(self) -> tuple[str, ...]:
        return tuple(self.spec["zone_base"])

    def base(self, zone: str) -> Fraction:
        return fraction(self.spec["zone_base"][str(zone)])

    def transfer_index(self, arrangement: str = "as issued", moved_to: int | None = None) -> int | None:
        'The first shift index on which the moved zone answers to its new area.'

        if self.moved_zone is None:
            return None
        if arrangement == "move" and moved_to is not None:
            return int(moved_to)
        return int(self.spec["transfer_index"])

    def home_area(self, zone: str) -> str:
        return str(self.spec["zone_home"][str(zone)])

    def area_of(
        self,
        zone: str,
        shift: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> str:
        'Which area answers for one zone on one shift.'

        zone = str(zone)
        if zone != self.moved_zone:
            return self.home_area(zone)
        transfer = self.transfer_index(arrangement, moved_to)
        if transfer is None or self.index_of(shift) < transfer:
            return str(self.spec["moved_from"])
        return str(self.spec["moved_to"])

    def zones_of(
        self,
        area: str,
        shift: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> tuple[str, ...]:
        return tuple(
            zone
            for zone in self.zones
            if self.area_of(zone, shift, arrangement, moved_to) == str(area)
        )

    def sheet_zones(
        self,
        area: str,
        shift: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> tuple[str, ...]:
        "The zones one area's engine puts on its sheet for one shift."

        area = str(area)
        rostered = list(self.zones_of(area, shift, arrangement, moved_to))
        moved = self.moved_zone
        if moved is not None and area == str(self.spec["moved_from"]) and moved not in rostered:
            rostered.append(moved)
        return tuple(sorted(rostered))


    def level(self, shift: str) -> Fraction:
        return fraction(self.spec["shift_level"][str(shift)])

    def profile(self, shift: str, window: str) -> Fraction:
        return fraction(self.spec["window_profile"][str(shift)][str(window)])

    def forecast(self, zone: str, shift: str, window: str) -> int:
        'The `drops_fcst` the planning engine publishes for one zone row.'

        key = (self.campaign, str(zone), str(shift), str(window))
        if key not in _FORECAST_CACHE:
            _FORECAST_CACHE[key] = whole(
                self.base(zone) * self.level(shift) * self.profile(shift, window)
            )
        return _FORECAST_CACHE[key]

    def smoothed(self, zone: str, shift: str, window: str) -> int:
        "The `drops_fcst_adj` column: the engine's three-shift smoothing."

        index = self.index_of(shift)
        span = [
            self.shifts[position]
            for position in (index - 1, index, index + 1)
            if 0 <= position < len(self.shifts)
        ]
        total = sum(
            (Fraction(self.forecast(zone, day, window)) for day in span), Fraction(0)
        )
        return whole(total / len(span))

    def demand(
        self,
        area: str,
        shift: str,
        window: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> int:
        "What the sheets say one area's window holds, each zone counted once."

        return sum(
            self.forecast(zone, shift, window)
            for zone in self.zones_of(area, shift, arrangement, moved_to)
        )

    def shift_total(
        self,
        shift: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> int:
        return sum(
            self.demand(area, shift, window, arrangement, moved_to)
            for area in AREAS
            for window in WINDOWS
        )


    def calendar_move(self, shift: str) -> Fraction:
        "The merchant calendar's move, shared by every zone of both areas."

        return fraction(self.spec["calendar_move"][str(shift)])

    def zone_miss(self, zone: str, shift: str, window: str) -> Fraction:
        "One zone's own miss on one window, centred over the whole network."

        raw = self._raw_miss(zone, shift, window)
        return raw - self._raw_centre(shift, window)

    def _raw_miss(self, zone: str, shift: str, window: str) -> Fraction:
        key = (self.campaign, str(zone), str(shift), str(window))
        if key not in _MISS_CACHE:
            spread = fraction(self.spec["zone_spread"]) * _UNIT
            _MISS_CACHE[key] = spread * (
                _unit_draw(self.campaign, str(zone), str(shift))
                + Fraction(1, 2) * _unit_draw(self.campaign, str(zone), str(shift), str(window))
            )
        return _MISS_CACHE[key]

    def _raw_centre(self, shift: str, window: str) -> Fraction:
        key = (self.campaign, str(shift), str(window))
        if key not in _CENTRE_CACHE:
            weight = total = Fraction(0)
            for zone in self.zones:
                size = Fraction(self.forecast(zone, shift, window))
                weight += size
                total += size * self._raw_miss(zone, shift, window)
            _CENTRE_CACHE[key] = total / weight if weight else Fraction(0)
        return _CENTRE_CACHE[key]

    def metered(
        self,
        area: str,
        shift: str,
        window: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> int:
        'What the settlement meter reports for one area and window.'

        key = (
            self.campaign, str(area), str(shift), str(window), str(arrangement),
            -1 if moved_to is None else int(moved_to),
        )
        if key not in _METER_CACHE:
            move = self.calendar_move(shift)
            total = Fraction(0)
            for zone in self.zones_of(area, shift, arrangement, moved_to):
                size = Fraction(self.forecast(zone, shift, window))
                total += size * (1 + move + self.zone_miss(zone, shift, window))
            _METER_CACHE[key] = round_to(total, METER_STEP)
        return _METER_CACHE[key]


    @property
    def drops_per_van(self) -> int:
        return int(self.spec["drops_per_van"])

    @property
    def spill_multiple(self) -> Fraction:
        return fraction(self.spec["spill_multiple"])

    @property
    def van_cap(self) -> int:
        return int(self.spec["van_cap"])

    @property
    def minimum_booking(self) -> int:
        return int(self.spec["minimum_booking"])

    @property
    def desk_fee(self) -> int:
        return int(self.spec["desk_fee"])

    @property
    def allowance_total(self) -> int:
        return int(self.spec["allowance_total"])

    @property
    def reservation_days(self) -> int:
        return int(self.spec["reservation_days"])

    def vans_needed(self, drops: int) -> int:
        "Whole vans to clear that many drops at the agreement's rate."

        exact = Fraction(int(drops), self.drops_per_van)
        whole_vans = exact.numerator // exact.denominator
        return int(whole_vans + (1 if exact != whole_vans else 0))

    def refusal(
        self,
        shift: str | None,
        booking: Mapping[tuple[str, str], int],
        allowance_left: int,
        booked_shifts: Sequence[str],
    ) -> str | None:
        'Why the desk would hand the order back without putting it on the road.'

        if shift is None or str(shift) not in self.shifts:
            return "that shift is not on the campaign's calendar"
        if str(shift) in {str(item) for item in booked_shifts}:
            return f"{shift} is already on the road"


        keys = {(area, window) for area in AREAS for window in WINDOWS}
        if set(booking) != keys:
            return "an order names each area and window once, with a whole positive van count"
        for (area, window), vans in sorted(booking.items()):
            if vans <= 0:
                return f"{area} {window} has no vans on it"
            if vans > self.van_cap:
                return (
                    f"{area} {window} asks for {vans} vans and the carrier holds "
                    f"{self.van_cap} for one area and window"
                )
        total = sum(booking.values())
        if total < self.minimum_booking:
            return (
                f"the order comes to {total} van-hours and the carrier will not put a "
                f"shift on the road under {self.minimum_booking}"
            )
        if total > allowance_left:
            return (
                f"the order comes to {total} van-hours and the quarter has "
                f"{allowance_left} left"
            )
        return None

    def run_shift(
        self,
        shift: str,
        booking: Mapping[tuple[str, str], int],
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> dict[str, Any]:
        'Put one order on the road and return what the meter and the bill say.'

        lines: list[dict[str, Any]] = []
        idle = short = 0
        for area in AREAS:
            for window in WINDOWS:
                vans = int(booking[(area, window)])
                drops = self.metered(area, shift, window, arrangement, moved_to)
                needed = self.vans_needed(drops)
                lines.append(
                    {
                        "area": area,
                        "window": window,
                        "vans_booked": vans,
                        "drops_metered": drops,
                        "vans_needed": needed,
                    }
                )
                idle += max(0, vans - needed)
                short += max(0, needed - vans)
        standing = sum(int(vans) for vans in booking.values())
        spill = self.spill_multiple * short
        return {
            "shift_id": str(shift),
            "lines": lines,
            "vans_idle": idle,
            "windows_short": sum(1 for line in lines if line["vans_needed"] > line["vans_booked"]),
            "vans_short": short,
            "spill_charge": float(spill),
            "van_hours_charged": float(standing + spill),
        }


    def _rows(
        self,
        area: str,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for shift in self.shifts:
            stamp = self.stamp_for(area, shift, arrangement)
            for window in WINDOWS:
                for zone in self.sheet_zones(area, shift, arrangement, moved_to):
                    rows.append(
                        {
                            "as_of_shift": stamp,
                            "window": window,
                            "zone_code": zone,
                            "drops_fcst": self.forecast(zone, shift, window),
                            "drops_fcst_adj": self.smoothed(zone, shift, window),
                        }
                    )
        return rows

    def harbour_rows(self, arrangement: str = "as issued", moved_to: int | None = None):
        return self._rows("Harbour", arrangement, moved_to)

    def ridge_rows(self, arrangement: str = "as issued", moved_to: int | None = None):
        return self._rows("Ridge", arrangement, moved_to)

    def network_rows(self, arrangement: str = "as issued", moved_to: int | None = None):
        "The network's own line: one total per area and shift, rounded to ten."

        rows = []
        for shift in self.shifts:
            for area in AREAS:
                exact = Fraction(self.demand(area, shift, "W1", arrangement, moved_to))
                exact += sum(
                    Fraction(self.demand(area, shift, window, arrangement, moved_to))
                    for window in WINDOWS[1:]
                )
                slip = fraction(self.spec["network_spread"]) * _UNIT * _unit_draw(
                    self.campaign, "network", str(area), str(shift)
                )
                rows.append(
                    {
                        "as_of_shift": str(shift),
                        "area": area,
                        "drops_fcst_network": round_to(exact * (1 + slip), 10),
                    }
                )
        return rows

    def routing_rows(self, arrangement: str = "as issued", moved_to: int | None = None):
        'The zone-to-area map with its effective dates.'

        rows = []
        transfer = self.transfer_index(arrangement, moved_to)
        for zone in self.zones:
            if zone == self.moved_zone and transfer is not None:
                rows.append(
                    {
                        "zone_code": zone,
                        "area": str(self.spec["moved_from"]),
                        "effective_from": self.lead_in,
                        "effective_to": self.shifts[transfer - 1] if transfer else self.lead_in,
                    }
                )
                rows.append(
                    {
                        "zone_code": zone,
                        "area": str(self.spec["moved_to"]),
                        "effective_from": self.shifts[transfer],
                        "effective_to": "",
                    }
                )
            else:
                rows.append(
                    {
                        "zone_code": zone,
                        "area": self.home_area(zone),
                        "effective_from": self.lead_in,
                        "effective_to": "",
                    }
                )
        return sorted(rows, key=lambda row: (row["zone_code"], row["effective_from"]))

    def public_context(
        self,
        arrangement: str = "as issued",
        moved_to: int | None = None,
    ) -> dict[str, Any]:
        spec = self.spec
        return {
            "campaign": self.campaign,
            "calendar": [self.lead_in, *self.shifts],
            "shifts": list(self.shifts),
            "windows": list(WINDOWS),
            "areas": list(AREAS),
            "harbour_rows": self.harbour_rows(arrangement, moved_to),
            "ridge_rows": self.ridge_rows(arrangement, moved_to),
            "network_rows": self.network_rows(arrangement, moved_to),
            "routing_rows": self.routing_rows(arrangement, moved_to),
            "agreement": {
                "drops_per_van": self.drops_per_van,
                "spill_multiple": float(self.spill_multiple),
                "vans_per_area_window": self.van_cap,
                "minimum_booking_van_hours": self.minimum_booking,
                "desk_fee_van_hours": self.desk_fee,
                "allowance_van_hours": self.allowance_total,
                "reservation_days": self.reservation_days,
            },
            "desk": {
                "meter_rounds_to": METER_STEP,
                "network_line_rounds_to": 10,
                "tolerance_pct": float(fraction(spec["tolerance_pct"])),
            },
        }


def build(spec: Mapping[str, Any]) -> World:
    return World(spec=spec)
