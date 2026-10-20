'The depot behind the dispatch board, and what its audit desk ever sees.'

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from math import gcd
import random
from statistics import NormalDist
from typing import Any, Mapping, Sequence


FEATURES = ("parts_lines", "access_score", "site_distance_km", "crew_size", "prior_visits")


COEFFICIENTS = (12.0, -6.5, 2.4, -9.0, 4.5)


FEATURE_DRAW = ((4.0, 1.5), (6.0, 1.8), (9.0, 4.0), (2.0, 0.6), (1.2, 0.9))


HOLD_RULE = 0.90
_NORMAL = NormalDist()
_UNIT = _NORMAL.inv_cdf((1.0 + HOLD_RULE) / 2.0)


_SHAPE: dict[float, float] = {}


def overrun_at(scale: float, level: float) -> float:
    "How far past the tool's number a finish sits at one level of a class."

    level = min(max(float(level), 1e-9), 1.0 - 1e-9)
    unit = _SHAPE.get(level)
    if unit is None:
        unit = _NORMAL.inv_cdf((1.0 + level) / 2.0) / _UNIT
        _SHAPE[level] = unit
    return float(scale) * unit


def _days(first_day: str, count: int, step: int = 1) -> tuple[str, ...]:
    start = date.fromisoformat(str(first_day))
    return tuple((start + timedelta(days=index * step)).isoformat() for index in range(count))


def _scramble(size: int) -> list[int]:
    'A fixed permutation of ``range(size)`` with no run of near neighbours.'

    if size <= 1:
        return list(range(size))
    step = max(1, int(size * 0.6180339887498949))
    while gcd(step, size) != 1:
        step += 1
        if step >= size:
            step = 1
            break
    return [(index * step) % size for index in range(size)]


def _spread(count: int, shares: Sequence[float]) -> list[int]:
    'Split ``count`` jobs between classes in the shares given, exactly.'

    total = float(sum(shares))
    raw = [count * float(share) / total for share in shares]
    counts = [int(value) for value in raw]
    order = sorted(range(len(raw)), key=lambda index: raw[index] - counts[index], reverse=True)
    short = count - sum(counts)
    for position in range(short):
        counts[order[position % len(order)]] += 1
    return counts


def _phase(step: int) -> float:
    "Where in each stretch of the book this night's pick falls."

    return ((int(step) + 1) * 0.6180339887498949 + 0.11) % 1.0


def _systematic(size: int, take: int, phase: float = 0.5) -> list[int]:
    '``take`` positions spread evenly across ``size`` places, in order.'

    if take <= 0 or size <= 0:
        return []
    if take >= size:
        return list(range(size))
    return [
        min(size - 1, int((position + float(phase)) * size / take))
        for position in range(take)
    ]


@dataclass(frozen=True)
class Job:
    job_id: str
    job_class: str
    features: tuple[float, ...]
    predicted: int
    actual: int

    @property
    def overrun(self) -> int:
        return abs(self.actual - self.predicted)

    def row(self) -> dict[str, Any]:
        payload = {"job_id": self.job_id, "job_class": self.job_class}
        payload.update({name: self.features[index] for index, name in enumerate(FEATURES)})
        payload["predicted_minutes"] = self.predicted
        payload["actual_minutes"] = self.actual
        return payload


@dataclass(frozen=True)
class Depot:
    "One depot's month of dispatched jobs and the eight weeks of audit behind it."

    spec: Mapping[str, Any]
    month: tuple[Job, ...]
    audit: tuple[tuple[str, Job], ...]
    returned: Mapping[tuple[int, str], int]
    _by_class: dict[str, list[Job]] = field(repr=False, default_factory=dict)


    _tables: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def depot(self) -> str:
        return str(self.spec["depot"])

    @property
    def classes(self) -> tuple[str, ...]:
        return tuple(str(name) for name, _, _, _ in self.spec["classes"])

    def share(self, job_class: str) -> float:
        total = len(self.month) or 1
        return len(self.month_jobs(job_class)) / total

    def month_jobs(self, job_class: str) -> list[Job]:
        if not self._by_class:
            for job in self.month:
                self._by_class.setdefault(job.job_class, []).append(job)
        return self._by_class.get(str(job_class), [])

    def traffic(self) -> list[dict[str, Any]]:
        if "traffic" not in self._tables:
            self._tables["traffic"] = [
                {
                    "month": str(self.spec["month"]),
                    "job_class": name,
                    "jobs_dispatched": len(self.month_jobs(name)),
                }
                for name in self.classes
            ]
        return self._tables["traffic"]

    def weeks(self) -> tuple[int, ...]:
        return tuple(range(1, int(self.spec["audit_weeks"]) + 1))

    def week_day(self, week: int) -> str:
        return _days(self.spec["audit_first_day"], int(self.spec["audit_weeks"]), 7)[week - 1]

    def sheets(self) -> list[dict[str, Any]]:
        if "sheets" not in self._tables:
            rows = []
            for week, job in self.audit:
                payload = {"week": int(week), "week_beginning": self.week_day(int(week))}
                payload.update(job.row())
                rows.append(payload)
            self._tables["sheets"] = rows
        return self._tables["sheets"]

    def sheets_of(self, job_class: str) -> list[Job]:
        held = self._tables.setdefault("sheets_of", {})
        if str(job_class) not in held:
            held[str(job_class)] = [
                job for _, job in self.audit if job.job_class == str(job_class)
            ]
        return held[str(job_class)]

    def log(self) -> list[dict[str, Any]]:
        if "log" in self._tables:
            return self._tables["log"]
        pull = dict(self.spec["pull"])
        forms = dict(self.spec["forms"])
        changed = self.spec.get("rescoped")
        change_week = int(self.spec.get("rescope_week") or 0)
        rows = []
        for week in self.weeks():
            for name in self.classes:
                asked = int(pull[name])
                version = str(forms[name])
                if changed == name and change_week and week >= change_week:
                    version = str(self.spec["rescope_form"])
                rows.append(
                    {
                        "week": week,
                        "week_beginning": self.week_day(week),
                        "job_class": name,
                        "pull": asked,
                        "pulled": asked,
                        "sheets_returned": int(self.returned.get((week, name), 0)),
                        "form_version": version,
                    }
                )
        self._tables["log"] = rows
        return rows


    def visit_terms(self) -> dict[str, Any]:
        "The desk's own terms, without building the month's tables for them."

        if "visit_terms" not in self._tables:
            spec = self.spec
            self._tables["visit_terms"] = {
                "units_granted": int(spec["units_granted"]),
                "units_per_visit": int(spec["units_per_visit"]),
                "units_per_refusal": int(spec["units_per_refusal"]),
                "jobs_per_visit": int(spec["jobs_per_visit"]),
                "visits_per_week": int(spec["visits_per_week"]),
                "weeks": list(spec["visit_weeks"]),
                "roster": {name: list(weeks) for name, weeks in spec["roster"].items()},
            }
        return self._tables["visit_terms"]

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "depot": self.depot,
            "month": str(spec["month"]),
            "as_of": str(spec["as_of"]),
            "board": {
                "hold_rule": HOLD_RULE,
                "window_limit_minutes": int(spec["window_limit_minutes"]),
                "coefficients": {
                    name: COEFFICIENTS[index] for index, name in enumerate(FEATURES)
                },
                "intercepts": {name: base for name, _, _, base in spec["classes"]},
            },
            "audit": {
                "pull_per_class_per_week": dict(spec["pull"]),
                "weeks": list(self.weeks()),
                "first_week_beginning": str(spec["audit_first_day"]),
            },
            "visits": dict(self.visit_terms()),
            "traffic": self.traffic(),
            "intake_log": self.log(),
            "sheets": self.sheets(),
        }


    def visit_rows(self, job_class: str, jobs: int, taken: Sequence[str]) -> list[dict[str, Any]]:
        "The jobs a crew stopwatches on one night, spread across the class's book."

        held = set(str(item) for item in taken)
        book = [job for job in self.month_jobs(job_class) if job.job_id not in held]
        nights = sum(1 for job in self.month_jobs(job_class) if job.job_id in held)
        book = sorted(book, key=lambda job: (job.overrun, job.job_id))
        return [
            book[index].row()
            for index in _systematic(len(book), int(jobs), _phase(nights))
        ]


def _build_jobs(
    generator: random.Random,
    spec: Mapping[str, Any],
    job_class: str,
    intercept: float,
    scale: float,
    count: int,
    prefix: str,
    start: int,
) -> list[Job]:
    "One class's jobs, with the overruns laid down as an even spread of the class."

    order = _scramble(count)
    jobs: list[Job] = []
    for index in range(count):
        features = tuple(
            round(generator.gauss(mean, spread), 2) for mean, spread in FEATURE_DRAW
        )
        predicted = intercept
        for position, weight in enumerate(COEFFICIENTS):
            predicted += weight * features[position]
        level = (order[index] + 0.5) / count
        size = overrun_at(scale, level)
        sign = 1 if order[index] % 2 == 0 else -1
        jobs.append(
            Job(
                job_id=f"{prefix}-{start + index:05d}",
                job_class=str(job_class),
                features=features,
                predicted=int(round(predicted)),
                actual=int(round(predicted + sign * size)),
            )
        )
    return jobs


def build(spec: Mapping[str, Any]) -> Depot:
    "Run one depot's month and the eight audit weeks behind it."

    generator = random.Random(int(spec["seed"]))
    classes = list(spec["classes"])
    names = [str(name) for name, _, _, _ in classes]
    shares = [float(share) for _, share, _, _ in classes]
    rescoped = spec.get("rescoped")
    change_week = int(spec.get("rescope_week") or 0)

    counts = _spread(int(spec["month_jobs"]), shares)
    month: list[Job] = []
    for position, (name, _, scale, base) in enumerate(classes):
        live = float(spec["rescoped_scale"]) if name == rescoped else float(scale)
        month.extend(
            _build_jobs(
                generator, spec, name, float(base), live, counts[position],
                str(spec["job_prefix"]), 1 + 1000 * position,
            )
        )

    audit: list[tuple[int, Job]] = []
    returned: dict[tuple[int, str], int] = {}
    weekly = int(spec["audit_week_jobs"])
    week_counts = _spread(weekly, shares)
    pull = dict(spec["pull"])
    late = dict(spec.get("late_returns", {}))
    for week in range(1, int(spec["audit_weeks"]) + 1):
        for position, (name, _, scale, base) in enumerate(classes):
            live = float(scale)
            if name == rescoped and change_week and week >= change_week:
                live = float(spec["rescoped_scale"])
            book = _build_jobs(
                generator, spec, name, float(base), live, week_counts[position],
                f"{spec['job_prefix']}A{week}", 1 + 1000 * position,
            )
            book = sorted(book, key=lambda job: (job.overrun, job.job_id))
            take = int(pull[name])
            if name == rescoped and change_week and week >= change_week:
                take = 0
            elif name in late:
                take = int(late[name][(week - 1) % len(late[name])])
            chosen = _systematic(len(book), take, _phase(week))
            returned[(week, name)] = len(chosen)
            audit.extend((week, book[index]) for index in chosen)

    return Depot(spec=spec, month=tuple(month), audit=tuple(audit), returned=returned)
