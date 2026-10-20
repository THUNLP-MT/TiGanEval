'The recorded nights, the night every delivery is measured on, and what each session implies about the runner that runs it.'

from __future__ import annotations

from typing import Any, Mapping


def note(text: str) -> dict[str, Any]:
    return {"op": "note", "text": text}

def work(cost: Any) -> dict[str, Any]:
    return {"op": "work", "ticks": cost}

def wait(gate: str, timeout: float | None = None, only: str | None = None) -> dict[str, Any]:
    step: dict[str, Any] = {"op": "wait", "gate": gate}
    if timeout is not None:
        step["timeout"] = timeout
    if only is not None:
        step["only"] = only
    return step

def flag(text: str, only: str) -> dict[str, Any]:
    return {"op": "flag", "text": text, "only": only}

def check(ask: str, **extra: Any) -> dict[str, Any]:
    return {"op": "check", "ask": ask, **extra}

def fail(text: str) -> dict[str, Any]:
    return {"op": "fail", "text": text}

def decline(text: str) -> dict[str, Any]:
    return {"op": "decline", "text": text}

def ticks(default: int, **per_handset: int) -> dict[str, int]:
    'A work cost that differs per handset; ``annex_a`` names ``annex-a``.'
    return {"*": int(default),
            **{name.replace("_", "-"): int(cost) for name, cost in per_handset.items()}}


def _swap_north_bench() -> dict[str, Any]:
    "Tuesday's handover session: two handsets, one case, one meeting point."
    return {
        "name": "swap-north-bench",
        "handsets": ["north-a", "north-b"],
        "phases": {
            "lab_open": [note("chamber sealed")],
            "bench_open": {"*": [work(5), note("handsets awake")]},
            "bench_close": {"*": [note("bench idle")]},
            "lab_close": [note("chamber open")],
        },
        "cases": {
            "case_call_handover": [
                work(ticks(30, north_a=40, north_b=25)),
                wait("swap"), note("the call is up on both handsets"),
                work(ticks(20, north_a=12, north_b=34)), note("the handover finished"),
            ],
        },
        "case_order": ["case_call_handover"],
    }


def _two_bench_rehearsal() -> dict[str, Any]:
    'Two benches of different sizes working the same two cases at once.'
    return {
        "name": "two-bench-rehearsal",
        "handsets": ["north-a", "north-b", "south-a", "south-b", "south-c"],
        "phases": {
            "lab_open": [note("rehearsal opened")],
            "bench_open": {"*": [work(5), wait("armed"), note("bench armed")]},
            "bench_close": {"*": [note("bench parked")]},
            "lab_close": [note("rehearsal closed")],
        },
        "cases": {
            "case_call_handover": [
                work(ticks(30, north_a=40, north_b=25, south_a=20, south_b=45, south_c=33)),
                wait("swap"), note("the call is up across the bench"),
                work(ticks(20, north_a=12, north_b=34, south_a=28, south_b=16, south_c=22)),
                note("the handover finished"),
            ],
            "case_signal_drop": [
                work(ticks(25, north_a=18, north_b=41, south_a=27, south_b=12, south_c=36)),
                wait("hold"), note("the radios came back"),
                work(ticks(10, north_a=14, north_b=9, south_a=21, south_b=7, south_c=17)),
                wait("hold"), note("the second hold finished"),
            ],
        },
        "case_order": ["case_call_handover", "case_signal_drop"],
    }


def _attribution_drill() -> dict[str, Any]:
    'Three handsets on one bench, and a different one fails in each case.'
    return {
        "name": "attribution-drill",
        "handsets": ["west-a", "west-b", "west-c"],
        "phases": {
            "lab_open": [note("drill opened")],
            "bench_open": {"*": [work(5), check("handset_id"), note("bench armed")]},
            "bench_close": {"*": [note("bench parked")]},
            "lab_close": [note("drill closed")],
        },
        "cases": {
            "case_hold_signal": [
                work(ticks(30, west_a=22, west_b=47, west_c=31)),
                flag("the call was lost before the hold point", only="west-a"),
                wait("hold"), note("the hold finished"),
            ],
            "case_battery_pull": [
                work(ticks(30, west_a=35, west_b=19, west_c=44)),
                flag("the handset did not come back after the pull", only="west-b"),
                wait("hold"), note("the pull finished"),
            ],
        },
        "case_order": ["case_hold_signal", "case_battery_pull"],
    }


def _runner_conformance() -> dict[str, Any]:
    "The lab's nightly probe of the runner, and three benches that go wrong."
    return {
        "name": "runner-conformance",
        "handsets": ["east-a", "east-b", "west-a", "north-a"],
        "phases": {
            "lab_open": [note("self-check opened"), check("handset_id"),
                         check("gate", gate="warmup")],
            "bench_open": {
                "east": [check("handset_id"), note("east armed"),
                         fail("the east chamber door was opened")],
                "west": [check("handset"), note("west armed")],
                "north": [decline("the north chamber is still cold")],
            },
            "bench_close": {
                "east": [note("east parked")],
                "west": [check("handset_id"), note("west parked"),
                         fail("the west power rail dropped")],
                "north": [note("north parked")],
            },
            "lab_close": [check("handset_id"), check("gate", gate="teardown"),
                          check("gate", gate="late", timeout=-1), note("self-check closed")],
        },
        "cases": {
            "case_probe_contract": [
                check("handset_id"), check("gate", gate="impossible", timeout=-1),
                check("gate", gate="impossible", timeout=0),
                work(ticks(20, east_a=11, east_b=23, west_a=17, north_a=29)),
                wait("meet"), note("probe finished"),
            ],
        },
        "case_order": ["case_probe_contract"],
    }


def _night_run() -> dict[str, Any]:
    'The night every delivery is measured on. No recorded night uses it.'
    return {
        "name": "night-run",
        "handsets": ["annex-a", "annex-b", "annex-c", "loft-a", "loft-b",
                     "north-a", "north-b", "vault-a", "east-a", "east-b",
                     "south-a", "roof-a", "roof-b"],
        "phases": {
            "lab_open": [note("the night opened"), check("handset_id"),
                         check("gate", gate="warmup")],
            "bench_open": {
                "annex": [work(5), wait("armed"), check("handset"), note("annex armed")],
                "loft": [work(5), wait("armed"), check("handset_id"), note("loft armed")],


                "north": [work(5), wait("armed"), check("handset_id"), note("north armed")],
                "vault": [work(5), note("vault armed"),
                          fail("the vault chamber lost its interlock")],


                "east": [work(5), wait("impossible", timeout=0), note("east armed")],


                "south": [work(5), wait("impossible", timeout=-1), note("south armed")],
                "roof": [work(5), decline("the roof chamber is still cold")],
            },
            "bench_close": {
                "annex": [note("annex parked")],
                "loft": [note("loft parked")],
                "north": [note("north parked")],
                "vault": [note("vault parked")],
                "east": [note("east parked")],
                "south": [note("south parked")],
                "roof": [note("roof parked"), wait("stow"), note("roof stowed"),
                         fail("the roof rail dropped on the way out")],
            },
            "lab_close": [check("handset_id"), check("gate", gate="teardown"),
                          check("gate", gate="late", timeout=-1), note("the night closed")],
        },
        "cases": {
            "case_call_handover": [
                work(ticks(30, annex_a=40, annex_b=25, annex_c=58, loft_a=31, loft_b=47)),
                flag("the call dropped before the swap", only="annex-a"),
                flag("the call never reached the second handset", only="loft-a"),
                wait("swap"), note("the call is up across the bench"),
                work(ticks(20, annex_a=13, annex_b=36, annex_c=21, loft_a=44, loft_b=17)),
                wait("swap"), note("the handover finished"),
            ],
            "case_signal_drop": [
                work(ticks(25, annex_a=19, annex_b=42, annex_c=27, loft_a=15, loft_b=38)),
                flag("the radio did not come back", only="annex-b"),
                wait("hold"), note("the radios came back"), work(8),
            ],
            "case_probe_contract": [
                check("handset_id"), check("gate", gate="impossible", timeout=-1),
                check("gate", gate="impossible", timeout=0),
                work(ticks(20, annex_a=11, annex_b=23, annex_c=17, loft_a=29, loft_b=13)),
                wait("meet"), note("probe finished"),
            ],


            "case_hold_window": [
                work(ticks(18, annex_a=14, annex_b=26, annex_c=9, loft_a=21, loft_b=12)),
                note("the call is up across the bench"),
                wait("window", only="loft-b"),
                wait("window", timeout=-15, only="loft-a"),
                note("the window closed"),
            ],
        },
        "case_order": ["case_call_handover", "case_signal_drop", "case_hold_window",
                       "case_probe_contract"],
    }


PUBLIC_SESSIONS: Mapping[str, Any] = {"swap-north-bench": _swap_north_bench,
    "two-bench-rehearsal": _two_bench_rehearsal, "attribution-drill": _attribution_drill,
    "runner-conformance": _runner_conformance}
PRIVATE_SESSION = "night-run"


def build_session(name: str) -> dict[str, Any]:
    'One session specification, in the shape ``protocol.load_session`` reads.'
    if name == PRIVATE_SESSION:
        return _night_run()
    builder = PUBLIC_SESSIONS.get(name)
    if builder is None:
        raise ValueError(f"unknown recorded session: {name}")
    return builder()


BENCH_PHASES = ("bench_open", "bench_close")

def phase_program(spec: Mapping[str, Any], phase: str, bench: str | None = None) -> list[dict]:
    'The steps of one phase; a bench phase may be written per bench.'
    program = spec.get("phases", {}).get(phase, ())
    if isinstance(program, Mapping):
        program = program.get(str(bench), program.get("*", ()))
    return [dict(step) for step in program]


def benches(spec: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, list[str]]:
    'The benches this session uses, in the order its handsets first appear.'
    grouped: dict[str, list[str]] = {}
    for handset_id in spec.get("handsets", ()):
        grouped.setdefault(str(inventory[str(handset_id)].bench), []).append(str(handset_id))
    return grouped


def benches_that_run_cases(spec: Mapping[str, Any], inventory: Mapping[str, Any]) -> list[str]:
    'Benches whose opening phase neither fails nor declines.'

    def opening_stops(program: list[dict]) -> bool:
        for step in program:
            op = str(step.get("op"))
            if op in ("fail", "decline"):
                return True
            if op == "wait" and step.get("timeout") is not None:
                if float(step["timeout"]) <= 0:
                    return True
        return False

    return [
        bench for bench in benches(spec, inventory)
        if not opening_stops(phase_program(spec, "bench_open", bench))
    ]


def expected_records(spec: Mapping[str, Any],
                     inventory: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    'Every (case, handset, bench) the night should leave exactly one row for.'
    grouped = benches(spec, inventory)
    return [(case, handset, bench)
            for bench in benches_that_run_cases(spec, inventory)
            for case in spec.get("case_order", ())
            for handset in grouped[bench]]


def expected_flags(spec: Mapping[str, Any],
                   inventory: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    'Every (case, handset, text) that exactly one row should carry.'
    running = set(benches_that_run_cases(spec, inventory))
    rows = []
    for case in spec.get("case_order", ()):
        for step in spec.get("cases", {}).get(case, ()):
            handset = str(step.get("only", ""))
            if str(step.get("op")) == "flag" and str(inventory[handset].bench) in running:
                rows.append((case, handset, str(step["text"])))
    return rows


def expected_record_states(
    spec: Mapping[str, Any], inventory: Mapping[str, Any]
) -> dict[tuple[str, str, str], tuple[list[str], str]]:
    'The flags and outcome each deterministic case row must contain.'

    states: dict[tuple[str, str, str], tuple[list[str], str]] = {}
    grouped = benches(spec, inventory)
    for bench in benches_that_run_cases(spec, inventory):
        for case in spec.get("case_order", ()):
            program = spec.get("cases", {}).get(case, ())
            per_handset: dict[str, tuple[list[str], bool, bool]] = {}
            for handset in grouped[bench]:
                flags: list[str] = []
                errored = False
                waits_alone = False
                for raw in program:
                    step = dict(raw)
                    if "only" in step and str(step["only"]) != handset:
                        continue
                    op = str(step.get("op"))
                    if op == "flag":
                        flags.append(str(step.get("text", "")))
                    elif op == "fail":
                        errored = True
                        break
                    elif op == "wait" and step.get("timeout") is not None:
                        if float(step["timeout"]) <= 0:
                            errored = True
                            break
                    if op == "wait" and "only" in step:
                        timeout = step.get("timeout")
                        if timeout is None or float(timeout) > 0:
                            waits_alone = True
                per_handset[handset] = (flags, errored, waits_alone)


            group_errored = any(errored for _, errored, _ in per_handset.values())
            for handset, (flags, errored, waits_alone) in per_handset.items():
                cancelled = group_errored and waits_alone and len(grouped[bench]) > 1
                outcome = "errored" if errored or cancelled else (
                    "flagged" if flags else "passed"
                )
                states[(str(case), handset, bench)] = (flags, outcome)
    return states


def expected_checks(spec: Mapping[str, Any], inventory: Mapping[str, Any]) -> list[tuple]:
    'Every conformance probe execution the private night should write.'

    grouped = benches(spec, inventory)
    checks: list[tuple] = []

    def collect(phase: str, bench: str | None, case: str | None,
                handset: str | None, program: list[dict]) -> None:
        for index, step in enumerate(program):
            if "only" in step and str(step["only"]) != str(handset):
                continue
            op = str(step.get("op"))
            if op == "check":
                checks.append((str(bench), phase, str(case), str(handset), index,
                               str(step.get("ask", "handset_id"))))
            if op in ("fail", "decline"):
                break
            if op == "wait" and step.get("timeout") is not None:
                if float(step["timeout"]) <= 0:
                    break

    collect("lab_open", None, None, None, phase_program(spec, "lab_open"))
    for bench, ids in grouped.items():
        lead = ids[0]
        collect("bench_open", bench, None, lead,
                phase_program(spec, "bench_open", bench))
        if bench in benches_that_run_cases(spec, inventory):
            for case in spec.get("case_order", ()):
                program = [dict(step) for step in spec.get("cases", {}).get(case, ())]
                for handset in ids:
                    collect("case", bench, str(case), handset, program)
        collect("bench_close", bench, None, lead,
                phase_program(spec, "bench_close", bench))
    collect("lab_close", None, None, None, phase_program(spec, "lab_close"))
    return checks


def is_a_meeting(step: Mapping[str, Any]) -> bool:
    'Whether a ``wait`` step is a meeting the handsets of a bench can hold.'
    timeout = step.get("timeout")
    return "only" not in step and (timeout is None or float(timeout) > 0)


def expected_meetings(
    spec: Mapping[str, Any], inventory: Mapping[str, Any]
) -> dict[tuple[str, str, str, str, int], list[str]]:
    'Every named point the night reaches, and the handsets due to meet there.'
    grouped = benches(spec, inventory)
    meetings: dict[tuple[str, str, str, str, int], list[str]] = {}
    for bench in benches_that_run_cases(spec, inventory):
        for case in spec.get("case_order", ()):
            for index, step in enumerate(spec.get("cases", {}).get(case, ())):
                if str(step.get("op")) == "wait" and is_a_meeting(step):
                    meetings[(bench, "case", case, str(step["gate"]), index)] = list(grouped[bench])
    for bench, ids in grouped.items():
        for phase in BENCH_PHASES:
            for index, step in enumerate(phase_program(spec, phase, bench)):
                op = str(step.get("op"))
                if op in ("fail", "decline"):
                    break
                if op == "wait" and is_a_meeting(step):
                    meetings[(bench, phase, "None", str(step["gate"]), index)] = [ids[0]]
    return meetings
