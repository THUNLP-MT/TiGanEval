"The study under review, the ones the same notebook is run over next, and the partner draws the review reads a reading's stability off."

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .world import build


def _chain(
    chain_id: str,
    node: str,
    job_id: str,
    step_size: float,
    busy_run: int,
    settle: int,
    own: int,
    parent: str | None = None,
    parent_step: int = 0,
    replayed: int = 0,
) -> dict[str, Any]:
    return {
        "chain_id": chain_id,
        "node": node,
        "job_id": job_id,
        "step_size": float(step_size),
        "busy_run": int(busy_run),
        "settle": int(settle),
        "own": int(own),
        "parent": parent,
        "parent_step": int(parent_step),
        "replayed": int(replayed),
    }


def _spec(
    study: str,
    quarter: str,
    as_of: str,
    seed: int,
    busy_share: float,
    sigma_busy: float,
    chains: Sequence[Mapping[str, Any]],
    new_chain: Mapping[str, Any],
    opening_jobs: Sequence[Mapping[str, Any]],
    grant_steps: int,
    spent_before_receipts: int,
    log_median: float = 0.51,
    sigma_calm: float = 0.16,
    settling_rise: float = 1.35,
    settling_end: float = 0.12,
    threshold_s: float = 2.5,
    commitment_share: float = 0.05,
    range_width_wanted: float = 0.03,
    cap_steps: int = 4000,
    minimum_steps: int = 600,
    refused_job_steps: int = 250,
) -> dict[str, Any]:
    return {
        "study": study,
        "quarter": quarter,
        "as_of": as_of,
        "seed": int(seed),
        "log_median": float(log_median),
        "sigma_calm": float(sigma_calm),
        "sigma_busy": float(sigma_busy),
        "busy_share": float(busy_share),
        "settling_rise": float(settling_rise),
        "settling_end": float(settling_end),
        "threshold_s": float(threshold_s),
        "commitment_share": float(commitment_share),
        "range_width_wanted": float(range_width_wanted),
        "chains": tuple(dict(item) for item in chains),
        "new_chain": dict(new_chain),
        "opening_jobs": tuple(dict(item) for item in opening_jobs),
        "grant_steps": int(grant_steps),
        "spent_before_receipts": int(spent_before_receipts),
        "cap_steps": int(cap_steps),
        "minimum_steps": int(minimum_steps),
        "refused_job_steps": int(refused_job_steps),
        "extensions": (),
        "new_runs": (),
    }


def _served(call_id: str, job_id: str, chain_id: str, steps: int) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "job_id": job_id,
        "chain_id": chain_id,
        "steps_requested": steps,
        "new_run": True,
    }


def _refused(call_id: str, job_id: str, steps: int, reason: str) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "job_id": job_id,
        "chain_id": None,
        "steps_requested": steps,
        "refusal": reason,
        "new_run": True,
    }


OVER_CAP = "a single job is capped at 4000 steps this quarter"
UNDER_MINIMUM = "a job under 600 steps is not worth queueing"

NEW_CHAIN = {"node": "hpc-05", "job_id": "j-46", "step_size": 0.121,
             "busy_run": 100, "settle": 180}


CURRENT_CHAINS = (
    _chain("run-a", "hpc-07", "j-4412", 0.118, 100, 140, 700),
    _chain("run-b", "hpc-11", "j-4418", 0.089, 148, 110, 1600),
    _chain("run-c", "hpc-03", "j-4531", 0.101, 128, 230, 1300),
    _chain("run-d", "hpc-11", "j-4544", 0.131, 90, 300, 560),
    _chain("run-e", "hpc-02", "j-4426", 0.163, 70, 90, 660),
    _chain("run-f", "hpc-11", "j-4552", 0.089, 148, 0, 700,
           parent="run-b", parent_step=1010, replayed=700),
)

CURRENT_JOBS = (
    _served("q1-a", "j-4412", "run-a", 840),
    _served("q1-b", "j-4418", "run-b", 2600),
    _served("q1-e", "j-4426", "run-e", 750),
    _refused("q1-wide", "j-4498", 9000, OVER_CAP),
    _served("q1-c", "j-4531", "run-c", 1530),
    _served("q1-d", "j-4544", "run-d", 860),
    _refused("q1-top-up", "j-4549", 400, UNDER_MINIMUM),
    _served("q1-f", "j-4552", "run-f", 1400),
)

CURRENT_SPEC = _spec(
    study="reservation-capacity-2027q1",
    quarter="2027 Q1",
    as_of="2027-02-19",
    seed=168,
    busy_share=0.30,
    sigma_busy=0.75,
    chains=CURRENT_CHAINS,
    new_chain=NEW_CHAIN,
    opening_jobs=CURRENT_JOBS,
    grant_steps=24300,
    spent_before_receipts=6710,
)


CHECKOUT_SPEC = _spec(
    study="checkout-capacity-2026q4",
    quarter="2026 Q4",
    as_of="2026-11-27",
    seed=76,
    busy_share=0.24,
    sigma_busy=0.82,
    chains=(
        _chain("run-a", "hpc-04", "j-3910", 0.126, 92, 160, 780),
        _chain("run-b", "hpc-09", "j-3915", 0.094, 124, 130, 1450),
        _chain("run-c", "hpc-04", "j-3922", 0.148, 78, 210, 620),
        _chain("run-d", "hpc-12", "j-3931", 0.111, 104, 240, 700),
        _chain("run-e", "hpc-09", "j-3940", 0.094, 124, 0, 640,
               parent="run-b", parent_step=900, replayed=680),
    ),
    new_chain=dict(NEW_CHAIN, step_size=0.118, busy_run=98, settle=170),
    opening_jobs=(
        _served("q4-a", "j-3910", "run-a", 940),
        _served("q4-b", "j-3915", "run-b", 1580),
        _served("q4-c", "j-3922", "run-c", 830),
        _refused("q4-short", "j-3927", 300, UNDER_MINIMUM),
        _served("q4-d", "j-3931", "run-d", 940),
        _served("q4-e", "j-3940", "run-e", 1320),
    ),
    grant_steps=19400,
    spent_before_receipts=5540,
)

DISPATCH_SPEC = _spec(
    study="dispatch-capacity-2027q1",
    quarter="2027 Q1",
    as_of="2027-02-12",
    seed=101,
    busy_share=0.38,
    sigma_busy=0.62,
    chains=(
        _chain("run-a", "hpc-01", "j-4455", 0.133, 96, 180, 820),
        _chain("run-b", "hpc-06", "j-4461", 0.109, 118, 140, 900),
        _chain("run-c", "hpc-08", "j-4470", 0.087, 150, 120, 1500),
        _chain("run-d", "hpc-01", "j-4482", 0.155, 84, 260, 640),
        _chain("run-e", "hpc-10", "j-4490", 0.121, 108, 200, 720),
        _chain("run-f", "hpc-08", "j-4505", 0.087, 150, 0, 620,
               parent="run-c", parent_step=900, replayed=720),
    ),
    new_chain=dict(NEW_CHAIN, step_size=0.126, busy_run=94, settle=190),
    opening_jobs=(
        _served("d-a", "j-4455", "run-a", 1000),
        _served("d-b", "j-4461", "run-b", 1040),
        _served("d-c", "j-4470", "run-c", 1620),
        _served("d-d", "j-4482", "run-d", 900),
        _refused("d-wide", "j-4487", 7500, OVER_CAP),
        _served("d-e", "j-4490", "run-e", 920),
        _served("d-f", "j-4505", "run-f", 1340),
    ),
    grant_steps=21600,
    spent_before_receipts=7530,
)


LOOKUP_SPEC = _spec(
    study="lookup-capacity-2027q1",
    quarter="2027 Q1",
    as_of="2027-02-05",
    seed=13,
    busy_share=0.31,
    sigma_busy=0.70,
    chains=(
        _chain("run-a", "hpc-02", "j-4301", 0.310, 7, 90, 1000),
        _chain("run-b", "hpc-02", "j-4306", 0.286, 8, 120, 1050),
        _chain("run-c", "hpc-05", "j-4311", 0.335, 6, 70, 980),
        _chain("run-d", "hpc-05", "j-4318", 0.264, 8, 140, 1020),
        _chain("run-e", "hpc-07", "j-4324", 0.298, 7, 100, 960),
        _chain("run-f", "hpc-07", "j-4330", 0.322, 6, 80, 1010),
    ),
    new_chain=dict(NEW_CHAIN, step_size=0.300, busy_run=7, settle=100),
    opening_jobs=(
        _served("l-a", "j-4301", "run-a", 1090),
        _served("l-b", "j-4306", "run-b", 1170),
        _served("l-c", "j-4311", "run-c", 1050),
        _served("l-d", "j-4318", "run-d", 1160),
        _served("l-e", "j-4324", "run-e", 1060),
        _served("l-f", "j-4330", "run-f", 1090),
    ),
    grant_steps=13800,
    spent_before_receipts=2180,
)

PAYMENTS_SPEC = _spec(
    study="payments-capacity-2026q4",
    quarter="2026 Q4",
    as_of="2026-12-11",
    seed=79,
    busy_share=0.17,
    sigma_busy=1.05,
    chains=(
        _chain("run-a", "hpc-03", "j-4020", 0.096, 132, 150, 1350),
        _chain("run-b", "hpc-03", "j-4027", 0.128, 98, 220, 700),
        _chain("run-c", "hpc-11", "j-4033", 0.142, 88, 190, 660),
        _chain("run-d", "hpc-06", "j-4041", 0.113, 112, 260, 620),
        _chain("run-e", "hpc-03", "j-4050", 0.096, 132, 0, 600,
               parent="run-a", parent_step=850, replayed=650),
    ),
    new_chain=dict(NEW_CHAIN, step_size=0.114, busy_run=110, settle=200),
    opening_jobs=(
        _served("p-a", "j-4020", "run-a", 1500),
        _served("p-b", "j-4027", "run-b", 920),
        _refused("p-short", "j-4030", 250, UNDER_MINIMUM),
        _served("p-c", "j-4033", "run-c", 850),
        _served("p-d", "j-4041", "run-d", 880),
        _served("p-e", "j-4050", "run-e", 1250),
    ),
    grant_steps=17100,
    spent_before_receipts=5450,
)


SETTLEMENT_SPEC = _spec(
    study="settlement-capacity-2026q3",
    quarter="2026 Q3",
    as_of="2026-08-28",
    seed=3,
    busy_share=0.28,
    sigma_busy=0.78,
    chains=(
        _chain("run-a", "hpc-09", "j-3540", 0.244, 16, 45, 800),
        _chain("run-b", "hpc-09", "j-3546", 0.221, 18, 55, 820),
        _chain("run-c", "hpc-12", "j-3551", 0.268, 14, 35, 780),
        _chain("run-d", "hpc-12", "j-3558", 0.205, 20, 50, 840),
        _chain("run-e", "hpc-04", "j-3563", 0.236, 17, 40, 810),
    ),
    new_chain=dict(NEW_CHAIN, step_size=0.235, busy_run=17, settle=45),
    opening_jobs=(
        _served("s-a", "j-3540", "run-a", 845),
        _served("s-b", "j-3546", "run-b", 875),
        _served("s-c", "j-3551", "run-c", 815),
        _served("s-d", "j-3558", "run-d", 890),
        _served("s-e", "j-3563", "run-e", 850),
    ),
    grant_steps=11600,
    spent_before_receipts=3325,
)


def _repeat_chains(settles, busy=None, own_f=1210, settle_f=190):
    out = []
    for index, plan in enumerate(CURRENT_CHAINS):
        item = dict(plan)
        item["settle"] = int(settles[index])
        if busy is not None:
            item["busy_run"] = int(busy[index])
        if item["parent"]:
            item["parent"] = None
            item["parent_step"] = 0
            item["replayed"] = 0
            item["own"] = int(own_f)
            item["settle"] = int(settle_f)
        out.append(item)
    return tuple(out)


def _repeat_jobs(prefix, chains):
    jobs = [
        _served(f"{prefix}-{item['chain_id'][-1]}", f"j-47{index:02d}", item["chain_id"],
                int(item["settle"]) + int(item["own"]) + int(item["replayed"]))
        for index, item in enumerate(chains)
    ]
    jobs.insert(3, _refused(f"{prefix}-wide", "j-4790", 8000, OVER_CAP))
    jobs.append(_refused(f"{prefix}-top-up", "j-4799", 350, UNDER_MINIMUM))
    return tuple(jobs)


SETTLING_CHAINS = _repeat_chains([60, 900, 120, 180, 70, 0], own_f=760, settle_f=640)
LINEAGE_CHAINS = _repeat_chains([140, 110, 230, 300, 90, 0])
EXCURSION_CHAINS = _repeat_chains([140, 110, 230, 300, 90, 0], busy=[55, 81, 70, 50, 39, 81])


SETTLING_PARTNER_SPEC = _spec(
    study="reservation-capacity-2027q1-repeat-a",
    quarter="2027 Q1",
    as_of="2027-02-19",
    seed=396,
    busy_share=0.30,
    sigma_busy=0.75,
    chains=SETTLING_CHAINS,
    new_chain=NEW_CHAIN,
    opening_jobs=_repeat_jobs("ra", SETTLING_CHAINS),
    grant_steps=24300,
    spent_before_receipts=6250,
)


BASELINE_PARTNER_SPEC = _spec(
    study="reservation-capacity-2027q1-repeat-b",
    quarter="2027 Q1",
    as_of="2027-02-19",
    seed=247,
    busy_share=0.30,
    sigma_busy=0.75,
    chains=LINEAGE_CHAINS,
    new_chain=NEW_CHAIN,
    opening_jobs=_repeat_jobs("rb", LINEAGE_CHAINS),
    grant_steps=24300,
    spent_before_receipts=6710,
)


EXCURSION_PARTNER_SPEC = _spec(
    study="reservation-capacity-2027q1-repeat-c",
    quarter="2027 Q1",
    as_of="2027-02-19",
    seed=66,
    busy_share=0.30,
    sigma_busy=0.75,
    chains=EXCURSION_CHAINS,
    new_chain=dict(NEW_CHAIN, busy_run=55),
    opening_jobs=_repeat_jobs("rc", EXCURSION_CHAINS),
    grant_steps=24300,
    spent_before_receipts=6710,
)


def _resubmission_repeat():
    out = []
    for item in CURRENT_CHAINS:
        plan = dict(item)
        if plan["chain_id"] == "run-a":
            plan["settle"] = 330
        if plan["chain_id"] == "run-f":
            plan.update(parent="run-b", parent_step=310, replayed=1400, own=1210, settle=0)
        out.append(plan)
    return tuple(out)


LINEAGE_CHAINS_WITH_RESUBMISSION = _resubmission_repeat()

LINEAGE_PARTNER_SPEC = _spec(
    study="reservation-capacity-2027q1-repeat-d",
    quarter="2027 Q1",
    as_of="2027-02-19",
    seed=459,
    busy_share=0.30,
    sigma_busy=0.75,
    chains=LINEAGE_CHAINS_WITH_RESUBMISSION,
    new_chain=NEW_CHAIN,
    opening_jobs=_repeat_jobs("rd", LINEAGE_CHAINS_WITH_RESUBMISSION),
    grant_steps=24300,
    spent_before_receipts=5660,
)


CURRENT = build(CURRENT_SPEC)
SIBLING_SPECS = (CHECKOUT_SPEC, DISPATCH_SPEC, LOOKUP_SPEC, PAYMENTS_SPEC)
SIBLINGS = tuple(build(spec) for spec in SIBLING_SPECS)
OUT_OF_REGIME = build(SETTLEMENT_SPEC)
PARTNER_SPECS = (
    SETTLING_PARTNER_SPEC,
    BASELINE_PARTNER_SPEC,
    EXCURSION_PARTNER_SPEC,
    LINEAGE_PARTNER_SPEC,
)
PARTNERS = tuple(build(spec) for spec in PARTNER_SPECS)


SETTLING_PARTNER, BASELINE_PARTNER, EXCURSION_PARTNER, LINEAGE_PARTNER = PARTNERS

REVIEWED = (CURRENT, *SIBLINGS, OUT_OF_REGIME, *PARTNERS)
OPENING_JOBS = {world.study: len(world.spec["opening_jobs"]) for world in REVIEWED}
