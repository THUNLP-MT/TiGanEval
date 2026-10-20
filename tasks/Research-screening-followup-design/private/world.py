'The thermal bench behind the plate screen, and what it does to a reading.'

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
from typing import Any, Iterable, Mapping, Sequence


INCUMBENT = "INC"
COUPON = "REF-C1"


_BLOCK_SCALES = (
    Fraction(7, 10),
    Fraction(17, 20),
    Fraction(1),
    Fraction(23, 20),
    Fraction(13, 10),
)


def fraction(value: Any) -> Fraction:
    return Fraction(str(value))


def to_tenth(value: Fraction) -> Fraction:
    'One reading as the rig reports it: kelvin to a tenth, halves rounding up.'

    scaled = value * 10
    whole = scaled.numerator // scaled.denominator
    if scaled - whole >= Fraction(1, 2):
        whole += 1
    return Fraction(whole, 10)


def _digest(*parts: str) -> int:
    return int(hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:8], 16)


@dataclass(frozen=True)
class World:
    'One screening campaign: its parts, its rig days and its booking sheet.'

    spec: Mapping[str, Any]


    @property
    def campaign(self) -> str:
        return str(self.spec["campaign"])

    @property
    def label(self) -> str:
        return str(self.spec["label"])

    @property
    def selected(self) -> str:
        return str(self.spec["selected_plate"])

    @property
    def screen_days(self) -> tuple[str, ...]:
        return tuple(self.spec["screen_days"])

    @property
    def open_days(self) -> tuple[str, ...]:
        return tuple(self.spec["open_days"])


    def truth(self, part: str) -> Fraction:
        'Kelvin taken off the case temperature rise against the incumbent.'

        part = str(part)
        if part == INCUMBENT:
            return Fraction(0)
        if part == COUPON:
            return fraction(self.spec["coupon_truth"])
        return fraction(self.spec["plates"][part])

    def true_rise(self, part: str) -> Fraction:
        return fraction(self.spec["incumbent_rise"]) - self.truth(part)

    def parts_in_stock(self) -> tuple[str, ...]:
        return (*sorted(self.spec["plates"]), COUPON, INCUMBENT)


    def day_shift(self, day: str, arrangement: str = "as run") -> Fraction:
        'What this rig day adds to every rise read on it.'

        table = (
            self.spec["alternate_shift"]
            if arrangement == "shift"
            else self.spec["day_shift"]
        )
        return fraction(table[str(day)])

    def assignment(self, arrangement: str = "as run") -> Mapping[str, tuple[str, ...]]:
        table = (
            self.spec["alternate_assignment"]
            if arrangement == "assign"
            else self.spec["assignment"]
        )
        return {day: tuple(plates) for day, plates in table.items()}

    def spread(self, day: str, part: str, count: int) -> list[Fraction]:
        'The run-to-run spread of one (day, part) block; it sums to zero.'

        if count <= 1:
            return [Fraction(0)] * max(count, 0)
        code = _digest(self.campaign, str(day), str(part))
        delta = fraction(self.spec["run_spread"]) * _BLOCK_SCALES[code % len(_BLOCK_SCALES)]
        draws: list[Fraction] = []
        state = code
        for _ in range(count):
            state = (state * 1103515245 + 12345) % 2147483648
            draws.append(Fraction(state % 2001 - 1000, 1000))
        centre = sum(draws, Fraction(0)) / count
        return [delta * (draw - centre) for draw in draws]

    def seating(self, day: str, part: str) -> Fraction:
        'What this mounting of this part on this day adds to its rise.'

        code = _digest(self.campaign, str(day), str(part), "seating")
        width = fraction(self.spec["seating_spread"]) * Fraction(173, 100)
        return width * Fraction(code % 2001 - 1000, 1000)

    def readings(
        self, day: str, part: str, count: int, arrangement: str = "as run"
    ) -> list[Fraction]:
        'What the rig writes for one block of runs, in kelvin to a tenth.'

        base = (
            self.true_rise(part)
            + self.day_shift(day, arrangement)
            + self.seating(day, part)
        )
        readings = [to_tenth(base + step) for step in self.spread(day, part, count)]


        return (
            list(reversed(readings))
            if arrangement == "relist" and part == INCUMBENT
            else readings
        )

    def score(self, rise: Fraction) -> Fraction:
        "The reporting job's score column: the stored incumbent rise less the run."

        return fraction(self.spec["stored_baseline_rise"]) - rise


    def screen_blocks(self, arrangement: str = "as run") -> list[tuple[str, str]]:
        '(day, part) blocks of the screen, in the order the rig ran them.'

        assignment = self.assignment(arrangement)
        coupon_days = [str(day) for day in self.spec["coupon_days"]]
        blocks: list[tuple[str, str]] = []
        for day in self.screen_days:
            for plate in assignment[day]:
                blocks.append((day, str(plate)))
            if day in coupon_days:
                blocks.append((day, COUPON))
        return blocks

    def screen_rows(self, arrangement: str = "as run") -> list[dict[str, Any]]:
        'One row per screen run, the way the reporting job exports them.'

        runs = int(self.spec["screen_runs"])
        rows: list[dict[str, Any]] = []
        number = 0
        for day in self.screen_days:
            slot = 0
            for block_day, part in self.screen_blocks(arrangement):
                if block_day != day:
                    continue
                slot += 1
                fixture = f"F-{(_digest(self.campaign, day, part) % 9) + 11}"
                for index, rise in enumerate(self.readings(day, part, runs, arrangement)):
                    number += 1
                    rows.append(
                        {
                            "run_id": f"R-{number:03d}",
                            "day_id": day,
                            "slot": slot,
                            "run_in_slot": index + 1,
                            "plate_id": part,
                            "rise_K": float(rise),
                            "score_K": float(self.score(rise)),
                            "operator": str(self.spec["operators"][slot % len(self.spec["operators"])]),
                            "fixture_id": fixture,
                        }
                    )
        return rows

    def screen_score(self, part: str, arrangement: str = "as run") -> Fraction | None:
        'The mean score the screen table gives one part.'

        runs = int(self.spec["screen_runs"])
        scores: list[Fraction] = []
        for day, block_part in self.screen_blocks(arrangement):
            if block_part != str(part):
                continue
            scores.extend(self.score(rise) for rise in self.readings(day, part, runs, arrangement))
        if not scores:
            return None
        return sum(scores, Fraction(0)) / len(scores)

    def rig_log_rows(self) -> list[dict[str, Any]]:
        rows = []
        for day in (*self.screen_days, *self.open_days):
            entry = self.spec["rig_log"][day]
            rows.append(
                {
                    "day_id": day,
                    "coolant_setpoint_C": float(fraction(entry["coolant_setpoint_C"])),
                    "ambient_C": float(fraction(entry["ambient_C"])),
                    "note": str(entry["note"]),
                }
            )
        return rows


    def day_capacity(self) -> dict[str, int]:
        return {
            "runs_per_day": int(self.spec["runs_per_day"]),
            "fixture_changes_per_day": int(self.spec["fixture_changes_per_day"]),
        }

    def refusal(self, requests: Sequence[Mapping[str, Any]]) -> str | None:
        'Why the rig would hand the day back without running anything.'

        caps = self.day_capacity()
        stock = set(self.parts_in_stock())
        total = sum(int(item["runs"]) for item in requests)
        if not requests or any(int(item["runs"]) <= 0 for item in requests):
            return "the day sheet has to name at least one part and a positive run count"
        for item in requests:
            if str(item["part"]) not in stock:
                return f"{item['part']} is not on the shelf"
        if len({str(item["part"]) for item in requests}) > caps["fixture_changes_per_day"]:
            return (
                f"the day allows {caps['fixture_changes_per_day']} fixture changes and the "
                f"sheet asks for {len({str(item['part']) for item in requests})} parts"
            )
        if total > caps["runs_per_day"]:
            return (
                f"the day allows {caps['runs_per_day']} runs and the sheet asks for {total}"
            )
        return None

    def run_day(
        self,
        day: str,
        requests: Sequence[Mapping[str, Any]],
        arrangement: str = "as run",
    ) -> dict[str, Any]:
        "Put one day's sheet on the rig and return what it wrote."

        refusal = self.refusal(requests)
        parts: list[dict[str, Any]] = []
        for slot, item in enumerate(requests, start=1):
            part = str(item["part"])
            wanted = int(item["runs"])
            rises = [] if refusal else self.readings(day, part, wanted, arrangement)
            parts.append(
                {
                    "part": part,
                    "slot": slot,
                    "fixture_id": f"F-{(_digest(self.campaign, str(day), part) % 9) + 11}",
                    "requested_runs": wanted,
                    "returned_runs": len(rises),
                    "rise_K": [float(rise) for rise in rises],
                }
            )
        entry = self.spec["rig_log"][str(day)]
        return {
            "day_id": str(day),
            "coolant_setpoint_C": float(fraction(entry["coolant_setpoint_C"])),
            "ambient_C": float(fraction(entry["ambient_C"])),
            "rig_hours_charged": float(
                fraction(self.spec["rig_hours_per_day"])
            ),
            "parts": parts,
            "refusal": refusal,
        }


    def public_context(self, arrangement: str = "as run") -> dict[str, Any]:
        spec = self.spec
        return {
            "campaign": self.campaign,
            "screen": {
                "plates": sorted(spec["plates"]),
                "selected_plate": self.selected,
                "runs_per_plate": int(spec["screen_runs"]),
                "reference_plate": COUPON,
                "incumbent_part": INCUMBENT,
            },
            "stored_baseline": {
                "rise_K": float(fraction(spec["stored_baseline_rise"])),
                "measured_on": str(spec["baseline_day"]),
            },
            "screen_runs": self.screen_rows(arrangement),
            "rig_log": self.rig_log_rows(),
            "booking": {
                "rig_days_on_the_sheet": int(spec["rig_days_on_the_sheet"]),
                "runs_per_day": int(spec["runs_per_day"]),
                "fixture_changes_per_day": int(spec["fixture_changes_per_day"]),
                "rig_hours_per_day": float(fraction(spec["rig_hours_per_day"])),
                "parts_in_stock": list(self.parts_in_stock()),
            },
            "review": {
                "range_width_K": float(fraction(spec["range_width_K"])),
                "due": str(spec["review_due"]),
            },
        }


def build(spec: Mapping[str, Any]) -> World:
    return World(spec=spec)


ARRANGEMENTS = ("as run", "shift", "assign", "relist")


def arrangement_note(arrangement: str) -> str:
    'What changed about the campaign, in the words a bench would use.'

    if arrangement == "shift":
        return "the same parts and the same run counts, booked again on days the rig gave back later"
    if arrangement == "assign":
        return "the reissued table, with the plates against the days they actually ran on"
    if arrangement == "relist":
        return "the same receipt values listed again in the other order inside each incumbent block"
    return "the table as it stands"


def day_means(world: World, arrangement: str = "as run") -> dict[str, Fraction]:
    'The mean score of the plates that ran on each screen day.'

    rows = world.screen_rows(arrangement)
    gathered: dict[str, list[Fraction]] = {}
    for row in rows:
        if row["plate_id"] == COUPON:
            continue
        gathered.setdefault(str(row["day_id"]), []).append(fraction(row["score_K"]))
    return {
        day: sum(values, Fraction(0)) / len(values) for day, values in gathered.items() if values
    }


def coupon_scores(world: World, arrangement: str = "as run") -> dict[str, Fraction]:
    'What the reference plate scored on each day it ran.'

    runs = int(world.spec["screen_runs"])
    found: dict[str, Fraction] = {}
    for day, part in world.screen_blocks(arrangement):
        if part != COUPON:
            continue
        rises = world.readings(day, part, runs, arrangement)
        found[day] = sum((world.score(rise) for rise in rises), Fraction(0)) / len(rises)
    return found


def sorted_screen_scores(world: World, arrangement: str = "as run") -> list[tuple[str, Fraction]]:
    "Every plate's screen score, highest first."

    scores = []
    for plate in sorted(world.spec["plates"]):
        value = world.screen_score(plate, arrangement)
        if value is not None:
            scores.append((plate, value))
    return sorted(scores, key=lambda item: (-item[1], item[0]))


def pairs(values: Iterable[Any]) -> list[Any]:
    return list(values)
