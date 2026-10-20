'The world behind the reservation-capacity precision study, and the console.'

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, Sequence

import numpy as np


RECEIPTS_FILE = "collection_receipts.json"
CHAIN_COLUMNS = (
    "step",
    "arrival_rate",
    "service_rate",
    "peak_wait_s",
    "step_size",
    "accepted",
)


_SEAL_KEY = hashlib.sha256(b"authored-compute-console-instrument-2027-02-19").digest()
_LOCK = threading.RLock()

_SQRT2 = math.sqrt(2.0)


def upper_normal(value: float) -> float:
    "The standard normal's upper tail at `value`."

    return 0.5 * math.erfc(float(value) / _SQRT2)


@dataclass(frozen=True)
class Chain:
    'One stored run: what the console wrote and what the world knows about it.'

    chain_id: str
    node: str
    job_id: str
    step_size: float
    busy_run: int
    settle: int
    parent: str | None
    parent_step: int
    replayed: int
    peak: np.ndarray
    crossing: np.ndarray
    scale: np.ndarray
    accepted: np.ndarray
    arrival: np.ndarray
    service: np.ndarray

    @property
    def steps_stored(self) -> int:
        return int(self.peak.size)

    @property
    def kept_from(self) -> int:
        'The first stored row that belongs in the reading.'

        return int(self.settle) + int(self.replayed)

    @property
    def init_source(self) -> str:
        if self.parent is None:
            return "dispersed-init"
        return f"{self.parent}@{int(self.parent_step)}"

    def rows(self) -> list[tuple[Any, ...]]:
        return [
            (
                index + 1,
                float(self.arrival[index]),
                float(self.service[index]),
                float(self.peak[index]),
                float(self.scale[index]),
                int(self.accepted[index]),
            )
            for index in range(self.steps_stored)
        ]

    def draws(self) -> dict[str, list[Any]]:
        return {
            "arrival_rate": [float(value) for value in self.arrival],
            "service_rate": [float(value) for value in self.service],
            "peak_wait_s": [float(value) for value in self.peak],
            "step_size": [float(value) for value in self.scale],
            "accepted": [int(value) for value in self.accepted],
        }

    def entry(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "node": self.node,
            "job_id": self.job_id,
            "steps_stored": self.steps_stored,
            "init_source": self.init_source,
            "draws": self.draws(),
        }

    def truncated(self, steps: int) -> "Chain":
        limit = max(0, min(int(steps), self.steps_stored))
        return Chain(
            chain_id=self.chain_id,
            node=self.node,
            job_id=self.job_id,
            step_size=self.step_size,
            busy_run=self.busy_run,
            settle=min(self.settle, limit),
            parent=self.parent,
            parent_step=self.parent_step,
            replayed=min(self.replayed, max(0, limit - min(self.settle, limit))),
            peak=self.peak[:limit],
            crossing=self.crossing[:limit],
            scale=self.scale[:limit],
            accepted=self.accepted[:limit],
            arrival=self.arrival[:limit],
            service=self.service[:limit],
        )


@dataclass(frozen=True)
class World:
    "One quarter's fitted capacity study, as the console left it."

    spec: Mapping[str, Any]
    chains: tuple[Chain, ...]

    @property
    def study(self) -> str:
        return str(self.spec["study"])

    @property
    def threshold(self) -> float:
        return float(self.spec["threshold_s"])

    def chain(self, chain_id: str) -> Chain | None:
        for item in self.chains:
            if item.chain_id == chain_id:
                return item
        return None


    def manifest_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "chain_id": chain.chain_id,
                "node": chain.node,
                "job_id": chain.job_id,
                "steps_stored": chain.steps_stored,
                "init_source": chain.init_source,
            }
            for chain in self.chains
        ]

    def steps_stored(self) -> int:
        return int(sum(chain.steps_stored for chain in self.chains))

    def context(self) -> dict[str, Any]:
        spec = self.spec
        return {
            "study": self.study,
            "quarter": str(spec["quarter"]),
            "as_of": str(spec["as_of"]),
            "commitment": {
                "peak_wait_s": float(spec["threshold_s"]),
                "quarters_over_share": float(spec["commitment_share"]),
                "range_width_wanted": float(spec["range_width_wanted"]),
            },
            "budget": {
                "steps_granted": int(spec["grant_steps"]),
                "steps_spent_before_receipts": int(spec["spent_before_receipts"]),
                "cap_steps_per_job": int(spec["cap_steps"]),
                "minimum_steps_per_job": int(spec["minimum_steps"]),
                "refused_job_steps": int(spec["refused_job_steps"]),
            },
            "chains": [chain.entry() for chain in self.chains],
        }


    def steps_charged(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return int(sum(int(entry["steps_charged"]) for entry in receipts))

    def steps_left(self, receipts: Sequence[Mapping[str, Any]]) -> int:
        return (
            int(self.spec["grant_steps"])
            - int(self.spec["spent_before_receipts"])
            - self.steps_charged(receipts)
        )


def calm_run(spec: Mapping[str, Any], busy_run: int) -> float:
    share = float(spec["busy_share"])
    return float(busy_run) * (1.0 - share) / share


def crossing_rates(spec: Mapping[str, Any]) -> tuple[float, float]:
    'The chance a step in a calm stretch and in a congested one crosses.'

    cut = math.log(float(spec["threshold_s"])) - float(spec["log_median"])
    return (
        upper_normal(cut / float(spec["sigma_calm"])),
        upper_normal(cut / float(spec["sigma_busy"])),
    )


def truth(spec: Mapping[str, Any]) -> float:
    "The share of quarters whose peak wait passes the commitment's second."

    calm, busy = crossing_rates(spec)
    share = float(spec["busy_share"])
    return share * busy + (1.0 - share) * calm


def lag_correlation(spec: Mapping[str, Any], busy_run: int) -> float:
    return 1.0 - 1.0 / float(busy_run) - 1.0 / calm_run(spec, busy_run)


def crossing_time(spec: Mapping[str, Any], busy_run: int) -> float:
    "How many steps of a run carry one step's worth of news about crossings."

    calm, busy = crossing_rates(spec)
    share = float(spec["busy_share"])
    value = truth(spec)
    weight = share * (1.0 - share) * (busy - calm) ** 2 / (value * (1.0 - value))
    lag = lag_correlation(spec, busy_run)
    return 1.0 + 2.0 * weight * lag / (1.0 - lag)


def middle_time(spec: Mapping[str, Any], busy_run: int) -> float:
    'The same quantity for the mean of the stored peak waits.'

    share = float(spec["busy_share"])
    median = float(spec["log_median"])
    calm_mean = math.exp(median + 0.5 * float(spec["sigma_calm"]) ** 2)
    busy_mean = math.exp(median + 0.5 * float(spec["sigma_busy"]) ** 2)
    calm_second = math.exp(2.0 * median + 2.0 * float(spec["sigma_calm"]) ** 2)
    busy_second = math.exp(2.0 * median + 2.0 * float(spec["sigma_busy"]) ** 2)
    mean = (1.0 - share) * calm_mean + share * busy_mean
    spread = (1.0 - share) * calm_second + share * busy_second - mean**2
    between = share * (1.0 - share) * (busy_mean - calm_mean) ** 2
    lag = lag_correlation(spec, busy_run)
    return 1.0 + 2.0 * (between / spread) * lag / (1.0 - lag)


def _stretches(rng: np.random.Generator, length: int, busy_run: int, calm_length: float,
               start_busy: bool) -> np.ndarray:
    'Which stored steps sit in a congested stretch.'

    if length <= 0:
        return np.zeros(0, dtype=bool)
    leave_busy = 1.0 / float(busy_run)
    leave_calm = 1.0 / float(calm_length)
    draws = rng.random(length)
    state = np.empty(length, dtype=bool)
    busy = bool(start_busy)
    for index in range(length):
        state[index] = busy
        busy = draws[index] >= leave_busy if busy else draws[index] < leave_calm
    return state


def _values(
    spec: Mapping[str, Any], rng: np.random.Generator, busy: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    'Peak waits for a settled stretch of a run, and which of them cross.'

    median = float(spec["log_median"])
    sigma = np.where(busy, float(spec["sigma_busy"]), float(spec["sigma_calm"]))
    logs = median + sigma * rng.standard_normal(busy.size)
    return _publish(spec, logs)


def _publish(spec: Mapping[str, Any], logs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    'Round the peak waits to what the console writes, keeping the crossings.'

    cut = math.log(float(spec["threshold_s"]))
    crossing = logs > cut
    peak = np.round(np.exp(logs), 4)
    threshold = float(spec["threshold_s"])
    peak = np.where(crossing, np.maximum(peak, threshold + 0.0001),
                    np.minimum(peak, threshold - 0.0001))
    return np.round(peak, 4), crossing


def _settling(
    spec: Mapping[str, Any], rng: np.random.Generator, length: int, step_size: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    'The rows a run stores before it reaches the surface it is exploring.'

    if length <= 0:
        empty = np.zeros(0)
        return empty, np.zeros(0, dtype=bool), empty, np.zeros(0, dtype=int)
    rise = float(spec["settling_rise"])


    decay = float(spec["settling_end"]) ** (1.0 / float(length))
    index = np.arange(length)
    above = rise * decay**index
    logs = float(spec["log_median"]) + above + float(spec["sigma_calm"]) * rng.standard_normal(length)
    peak, crossing = _publish(spec, logs)
    scale = np.round(
        step_size * (1.0 + 0.9 * above / rise) * (1.0 + 0.06 * rng.standard_normal(length)),
        4,
    )
    scale = np.where(scale <= 0.0, step_size, scale)


    scale = np.where(np.abs(scale - step_size) < 0.0002, round(step_size + 0.0005, 4), scale)
    accepted = (rng.random(length) < 0.20 + 0.35 * (1.0 - above / rise)).astype(int)
    return peak, crossing, scale, accepted


def _parameters(
    spec: Mapping[str, Any], rng: np.random.Generator, peak: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    'The two model coordinates the console writes beside the peak wait.'

    scaled = np.log(np.maximum(peak, 0.05)) - float(spec["log_median"])
    arrival = np.round(0.840 + 0.052 * scaled + 0.011 * rng.standard_normal(peak.size), 3)
    service = np.round(1.060 - 0.038 * scaled + 0.009 * rng.standard_normal(peak.size), 3)
    return arrival, service


def _settled_block(
    spec: Mapping[str, Any],
    rng: np.random.Generator,
    length: int,
    busy_run: int,
    step_size: float,
    start_busy: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    busy = _stretches(rng, length, busy_run, calm_run(spec, busy_run), start_busy)
    peak, crossing = _values(spec, rng, busy)
    scale = np.full(length, float(step_size))


    rate = (0.28 + 0.9 * float(step_size)) * np.where(busy, 0.80, 1.0)
    accepted = (rng.random(length) < rate).astype(int)
    return peak, crossing, scale, accepted


def _extra_steps(spec: Mapping[str, Any], chain_id: str) -> int:
    return int(sum(int(steps) for name, steps in spec.get("extensions", ()) if name == chain_id))


def build(spec: Mapping[str, Any]) -> World:
    'Run every chain of one study forward and store every row.'

    seed = int(spec["seed"])
    built: dict[str, Chain] = {}
    order: list[Chain] = []
    for index, plan in enumerate(spec["chains"]):
        chain_id = str(plan["chain_id"])
        rng = np.random.default_rng([seed, 17, index])
        settle = int(plan["settle"])
        own = int(plan["own"]) + _extra_steps(spec, chain_id)
        step_size = float(plan["step_size"])
        busy_run = int(plan["busy_run"])
        head_peak, head_cross, head_scale, head_accept = _settling(spec, rng, settle, step_size)
        replayed = 0
        parent = plan.get("parent")
        parent_step = 0
        pieces_peak = [head_peak]
        pieces_cross = [head_cross]
        pieces_scale = [head_scale]
        pieces_accept = [head_accept]
        start_busy = bool(rng.random() < float(spec["busy_share"]))
        if parent is not None:
            source = built[str(parent)]
            parent_step = int(plan["parent_step"])
            replayed = int(plan["replayed"])
            stop = parent_step + replayed
            pieces_peak.append(source.peak[parent_step:stop])
            pieces_cross.append(source.crossing[parent_step:stop])
            pieces_scale.append(np.full(replayed, step_size))
            pieces_accept.append(source.accepted[parent_step:stop])
        body_peak, body_cross, body_scale, body_accept = _settled_block(
            spec, rng, own, busy_run, step_size, start_busy
        )
        pieces_peak.append(body_peak)
        pieces_cross.append(body_cross)
        pieces_scale.append(body_scale)
        pieces_accept.append(body_accept)
        peak = np.concatenate(pieces_peak)
        crossing = np.concatenate(pieces_cross)
        scale = np.concatenate(pieces_scale)
        accepted = np.concatenate(pieces_accept).astype(int)
        arrival, service = _parameters(spec, rng, peak)
        if replayed:


            source = built[str(parent)]
            arrival[settle : settle + replayed] = source.arrival[
                parent_step : parent_step + replayed
            ]
            service[settle : settle + replayed] = source.service[
                parent_step : parent_step + replayed
            ]
        chain = Chain(
            chain_id=chain_id,
            node=str(plan["node"]),
            job_id=str(plan["job_id"]),
            step_size=step_size,
            busy_run=busy_run,
            settle=settle,
            parent=None if parent is None else str(parent),
            parent_step=parent_step,
            replayed=replayed,
            peak=peak,
            crossing=crossing,
            scale=scale,
            accepted=accepted,
            arrival=arrival,
            service=service,
        )
        built[chain_id] = chain
        order.append(chain)
    for position, steps in enumerate(spec.get("new_runs", ())):
        template = dict(spec["new_chain"])
        chain_id = _new_chain_id(order, position)
        rng = np.random.default_rng([seed, 41, position])
        settle = int(template["settle"])
        own = max(0, int(steps) - settle)
        step_size = float(template["step_size"])
        head_peak, head_cross, head_scale, head_accept = _settling(spec, rng, settle, step_size)
        body_peak, body_cross, body_scale, body_accept = _settled_block(
            spec, rng, own, int(template["busy_run"]), step_size,
            bool(rng.random() < float(spec["busy_share"])),
        )
        peak = np.concatenate([head_peak, body_peak])
        crossing = np.concatenate([head_cross, body_cross])
        scale = np.concatenate([head_scale, body_scale])
        accepted = np.concatenate([head_accept, body_accept]).astype(int)
        arrival, service = _parameters(spec, rng, peak)
        chain = Chain(
            chain_id=chain_id,
            node=str(template["node"]),
            job_id=f"{template['job_id']}{position + 1}",
            step_size=step_size,
            busy_run=int(template["busy_run"]),
            settle=settle,
            parent=None,
            parent_step=0,
            replayed=0,
            peak=peak,
            crossing=crossing,
            scale=scale,
            accepted=accepted,
            arrival=arrival,
            service=service,
        )
        order.append(chain)
    return World(spec=spec, chains=tuple(order))


def _new_chain_id(order: Sequence[Chain], position: int) -> str:
    letters = "ghijklmnopqrstuvwxyz"
    return f"run-{letters[position % len(letters)]}"


def grown(spec: Mapping[str, Any], jobs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    'The same study after one more list of served jobs.'

    extensions = list(spec.get("extensions", ()))
    new_runs = list(spec.get("new_runs", ()))
    for job in jobs:
        steps = int(job["steps"])
        if job.get("chain_id"):
            extensions.append((str(job["chain_id"]), steps))
        else:
            new_runs.append(steps)
    return dict(spec, extensions=tuple(extensions), new_runs=tuple(new_runs))


def booked(spec: Mapping[str, Any], jobs: Sequence[Mapping[str, Any]]) -> World:
    return build(grown(spec, jobs))


def _seal(value: Mapping[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SEAL_KEY, body, hashlib.sha256).hexdigest()


def receipt(
    study: str,
    sequence: int,
    call_id: str,
    job_id: str,
    chain_id: str | None,
    init_source: str,
    steps_requested: int,
    steps_returned: int,
    steps_charged: int,
    refusal: str | None,
    new_run: bool,
    steps_left: int,
    previous: str,
) -> dict[str, Any]:
    body = {
        "study": str(study),
        "sequence": int(sequence),
        "call_id": str(call_id),
        "job_id": str(job_id),
        "chain_id": None if chain_id is None else str(chain_id),
        "init_source": str(init_source),
        "steps_requested": int(steps_requested),
        "steps_returned": int(steps_returned),
        "steps_charged": int(steps_charged),
        "refusal": None if refusal is None else str(refusal),
        "new_run": bool(new_run),
        "steps_left": int(steps_left),
        "previous": str(previous),
    }
    return dict(body, seal=_seal(body))


def opening_stream(world: World) -> list[dict[str, Any]]:
    'The receipts for the jobs that produced the frozen history.'

    entries: list[dict[str, Any]] = []
    left = int(world.spec["grant_steps"]) - int(world.spec["spent_before_receipts"])
    for job in world.spec["opening_jobs"]:
        refusal = job.get("refusal")
        chain_id = job.get("chain_id")
        chain = world.chain(str(chain_id)) if chain_id else None
        returned = 0 if refusal else int(chain.steps_stored if chain else 0)
        charged = int(world.spec["refused_job_steps"]) if refusal else returned
        left -= charged
        fresh = bool(job.get("new_run", True)) if chain is None else chain.parent is None
        entries.append(
            receipt(
                world.study,
                len(entries) + 1,
                str(job["call_id"]),
                str(job["job_id"]),
                chain_id,
                str(chain.init_source) if chain is not None else "dispersed-init",
                int(job["steps_requested"]),
                returned,
                charged,
                refusal,
                fresh,
                left,
                entries[-1]["seal"] if entries else "",
            )
        )
    return entries


def read_receipts(workspace: Path, world: World) -> list[dict[str, Any]]:
    'Every job this study has been billed for, or a reason the stream is broken.'

    path = Path(workspace) / RECEIPTS_FILE
    if path.is_symlink():
        raise ValueError("the console receipts must not be a symlink")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("study") != world.study
        or not isinstance(raw.get("entries"), list)
    ):
        raise ValueError("the receipt stream does not belong to this study")
    seen: set[str] = set()
    previous = ""
    for sequence, entry in enumerate(raw["entries"], start=1):
        if not isinstance(entry, dict):
            raise ValueError("a console receipt is not a service record")
        call_id = entry.get("call_id")
        if not isinstance(call_id, str) or not call_id or call_id in seen:
            raise ValueError("a console receipt has a missing or repeated call id")
        if entry.get("sequence") != sequence or entry.get("previous") != previous:
            raise ValueError("the console receipts are not in the order the console wrote them")
        if entry.get("study") != world.study:
            raise ValueError("a console receipt belongs to another study")
        signature = entry.get("seal")
        body = {key: value for key, value in entry.items() if key != "seal"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, _seal(body)):
            raise ValueError("a console receipt does not carry the console seal")
        seen.add(call_id)
        previous = str(signature)
    return [dict(entry) for entry in raw["entries"]]


def jobs_of(receipts: Sequence[Mapping[str, Any]], opening: int) -> list[dict[str, Any]]:
    'The served jobs on the stream beyond the ones that made the frozen history.'

    return [
        {
            "chain_id": None if entry.get("new_run") else entry.get("chain_id"),
            "steps": int(entry["steps_returned"]),
        }
        for entry in list(receipts)[opening:]
        if not entry.get("refusal") and int(entry["steps_returned"]) > 0
    ]


def manifest_source(world: World, chain_id: Any, start_new: bool) -> str:
    'The `init_source` the manifest carries for the run a job ran on.'

    if start_new:
        return "dispersed-init"
    chain = world.chain(str(chain_id)) if chain_id is not None else None
    return str(chain.init_source) if chain is not None else str(chain_id or "")


def refusal_reason(
    world: World,
    chain_id: Any,
    start_new: bool,
    steps: int,
    left: int,
) -> str | None:
    'Why the console will not run this job, in the words it writes back.'

    cap = int(world.spec["cap_steps"])
    minimum = int(world.spec["minimum_steps"])
    if steps < minimum:
        return f"a job under {minimum} steps is not worth queueing"
    if steps > cap:
        return f"a single job is capped at {cap} steps this quarter"
    if not start_new and world.chain(str(chain_id)) is None:
        return f"there is no run called {chain_id} in this study"
    if steps > left:
        return f"the grant has {left} steps left and this job asks for {steps}"
    return None


def collect(
    workspace: Path,
    world: World,
    opening: Sequence[Mapping[str, Any]],
    chain_id: Any,
    start_new: Any,
    steps: Any,
    call_id: Any,
) -> dict[str, Any]:
    'Run one console job and append its receipt.'

    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
        raise ValueError("steps must be a whole number of sampler steps, at least one")
    if not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 120:
        raise ValueError("call_id must be a short non-empty label you choose")
    wants_new = bool(start_new)
    if wants_new and chain_id:
        raise ValueError("a job either extends one stored run or starts a new one, not both")
    if not wants_new and not isinstance(chain_id, str):
        raise ValueError("a job needs a chain_id to extend, or start_new set")

    root = Path(workspace).resolve()
    with _LOCK:
        entries = read_receipts(root, world)
        for entry in entries:
            if entry["call_id"] == call_id:
                return {
                    "receipt": entry,
                    "ran": False,
                    "steps_charged_total": world.steps_charged(entries),
                    "steps_left": world.steps_left(entries),
                }
        left = world.steps_left(entries)
        if left <= 0:
            raise ValueError("the compute grant for this study is spent")
        already = jobs_of(entries, len(opening))
        before = booked(world.spec, already)
        reason = refusal_reason(before, chain_id, wants_new, int(steps), left)
        sequence = len(entries) + 1
        previous = entries[-1]["seal"] if entries else ""
        job_id = f"j-{4600 + sequence:04d}"
        if reason is not None:
            charged = min(int(world.spec["refused_job_steps"]), left)
            made = receipt(
                world.study, sequence, str(call_id), job_id,
                None if wants_new else str(chain_id),
                manifest_source(before, chain_id, wants_new),
                int(steps), 0, charged, reason, wants_new, left - charged, previous,
            )
            _write(root, world, entries + [made])
            return {
                "receipt": made,
                "ran": True,
                "refused": reason,
                "steps_charged_total": world.steps_charged(entries + [made]),
                "steps_left": left - charged,
            }
        job = {"chain_id": None if wants_new else str(chain_id), "steps": int(steps)}
        after = booked(world.spec, [*already, job])
        served = after.chains[-1] if wants_new else after.chain(str(chain_id))
        fresh_from = (
            0 if wants_new else int(before.chain(str(chain_id)).steps_stored)
        )
        made = receipt(
            world.study, sequence, str(call_id), job_id, served.chain_id,
            str(served.init_source), int(steps), int(steps), int(steps),
            None, wants_new, left - int(steps), previous,
        )
        _write(root, world, entries + [made])
        _publish_run(root, after, served)
        rows = served.rows()[fresh_from:]
        return {
            "receipt": made,
            "ran": True,
            "chain_id": served.chain_id,
            "columns": list(CHAIN_COLUMNS),
            "rows": rows,
            "steps_charged_total": world.steps_charged(entries + [made]),
            "steps_left": left - int(steps),
        }


def _chain_csv(chain: Chain) -> str:
    lines = [",".join(CHAIN_COLUMNS)]
    for step, arrival, service, peak, scale, accepted in chain.rows():
        lines.append(
            f"{step},{arrival:.3f},{service:.3f},{peak:.4f},{scale:.4f},{accepted}"
        )
    return "\n".join(lines) + "\n"


def _publish_run(root: Path, after: World, served: Chain) -> None:
    "Leave the run's file and the manifest as the console leaves them."

    folder = root / "chains"
    folder.mkdir(exist_ok=True)
    (folder / f"{served.chain_id}.csv").write_text(_chain_csv(served), encoding="utf-8")
    manifest = ["chain_id,node,job_id,steps_stored,init_source"]
    for row in after.manifest_rows():
        manifest.append(
            f"{row['chain_id']},{row['node']},{row['job_id']},"
            f"{row['steps_stored']},{row['init_source']}"
        )
    (root / "chain_manifest.csv").write_text("\n".join(manifest) + "\n", encoding="utf-8")


def _write(root: Path, world: World, entries: Sequence[Mapping[str, Any]]) -> None:
    pending = root / "collection_receipts.pending"
    pending.write_text(
        json.dumps({"study": world.study, "entries": list(entries)}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(pending, root / RECEIPTS_FILE)
