'Deterministic scenarios for the scripting runtime: the store, the jobs, the runs.'

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


TASK_ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = TASK_ROOT / "workspace" / "store"


LINKS: Mapping[str, str] = {"/srv/kits": "/opt/kits"}


NIGHT_ONE_PATH = "/opt/kits-legacy:/srv/kits"
NIGHT_TWO_PATH = ' "/opt/kits-legacy/" : /srv/kits/ : /opt/kits '


def store_files() -> dict[str, str]:
    "Every kit file in the project's store tree, keyed by its store path."

    return {
        "/" + path.relative_to(STORE_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(STORE_ROOT.rglob("*.kit"))
    }


def _job(job_id: str, path: str, source: str, kit_path: str,
         trace: str = "", invocation: Sequence[str] = ()) -> dict[str, Any]:
    settings: dict[str, Any] = {"kit_path": kit_path}
    if trace:
        settings["trace"] = trace
    return {"id": job_id, "path": path, "source": source,
            "settings": settings, "invocation": tuple(invocation)}


def _run(run_id: str, jobs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"id": run_id, "jobs": [dict(job) for job in jobs]}


def build_scenario(profile: str) -> dict[str, Any]:
    'The store and the runs for one scenario, ready for `protocol.simulate`.'

    builder = _PROFILES.get(str(profile))
    if builder is None:
        raise ValueError(f"unknown runtime scenario: {profile}")
    runs = builder()
    files = store_files()
    for run in runs:
        for job in run["jobs"]:
            files[job["path"]] = job["source"]
    return {"files": files, "links": dict(LINKS), "runs": runs}


def file_labels(scenario: Mapping[str, Any]) -> dict[str, str]:
    "The identity label the store gives each of a scenario's store paths."

    paths = sorted(_normalise(path) for path in scenario.get("files", {}))
    return {path: f"store:{number:03d}" for number, path in enumerate(paths, start=1)}


def _normalise(path: Any) -> str:
    parts: list[str] = []
    for part in str(path).split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def canonical(path: Any) -> str:
    'One store path as the store reaches it, with the link entries followed.'

    current = _normalise(path)
    for _ in range(8):
        for source, target in LINKS.items():
            if current == source or current.startswith(f"{source}/"):
                current = _normalise(target + current[len(source):])
                break
        else:
            break
    return current


_PRICE_RUN = """use invoice
use regions
count regions.markets as pinned
publish night.pinned pinned
"""


_AUDIT_RUN = """use rounding
use promos
use /opt/kits/tax.kit
copy tax.rate as rate
publish audit.rate rate
"""

_PILOT_RUN = """use rounding
use /opt/kits/tax.kit
use tax
copy tax.rate as rate
copy rounding.mode as mode
publish pilot.mode mode
publish pilot.rate rate
"""

_FEED_RUN = "use feed\n"
_STAFFING_RUN = "use roster\n"


def _nightly_jobs(kit_path: str) -> dict[str, dict[str, Any]]:
    night, pilot = "/srv/runs/night", "/srv/runs/pilot"
    return {
        "price_run": _job("price_run", f"{night}/price_run.job", _PRICE_RUN, kit_path,
                          trace="on"),
        "audit_run": _job("audit_run", f"{night}/audit_run.job", _AUDIT_RUN, kit_path,
                          invocation=("--trace",)),
        "pilot_run": _job("pilot_run", f"{pilot}/pilot_run.job", _PILOT_RUN, kit_path),
        "feed_run": _job("feed_run", f"{night}/feed_run.job", _FEED_RUN, kit_path),
        "staffing_run": _job("staffing_run", f"{night}/staffing_run.job", _STAFFING_RUN,
                             kit_path),
        "feed_retry_run": _job("feed_retry_run", f"{night}/feed_retry_run.job", _FEED_RUN,
                               kit_path),
    }


ORDER_A = ("price_run", "audit_run", "pilot_run", "feed_run", "staffing_run", "feed_retry_run")
ORDER_B = ("staffing_run", "audit_run", "price_run", "pilot_run", "feed_run", "feed_retry_run")


FIRST_ORDER, SECOND_ORDER, OTHER_WORKER = "queue-order-a", "queue-order-b", "worker-night-two"


def _nightly() -> list[dict[str, Any]]:
    one, two = _nightly_jobs(NIGHT_ONE_PATH), _nightly_jobs(NIGHT_TWO_PATH)
    return [
        _run(FIRST_ORDER, [one[name] for name in ORDER_A]),
        _run(SECOND_ORDER, [one[name] for name in ORDER_B]),
        _run(OTHER_WORKER, [two[name] for name in ORDER_A]),
    ]


EXPECTED_CATALOG: tuple[tuple[str, Any], ...] = (
    ("audit.rate", 20),
    ("invoice.markets", 3),
    ("invoice.rate", 20),
    ("night.pinned", 1),
    ("pilot.mode", "pilot"),
    ("pilot.rate", 20),
    ("promos.window", 3),
    ("promos.window", 7),
    ("regions.home", "emea"),
    ("regions.home", "eu"),
    ("rounding.mode", "pilot"),
    ("rounding.mode", "standard"),
    ("tax.rate", 20),
)


PINNED_RESOLUTION: tuple[tuple[str, str, str, str], ...] = (
    ("/srv/runs/pilot/pilot_run.job", "rounding", "/srv/runs/pilot/rounding.kit",
     "shared_copy_beat_the_local_one"),
    ("/opt/kits/invoice.kit", "regions", "/opt/kits/regions.kit",
     "shared_kit_read_the_pinned_list"),
    ("/srv/runs/night/price_run.job", "regions", "/srv/runs/night/regions.kit",
     "job_missed_its_own_pinned_list"),
)

CYCLE_JOB, CYCLE_CHAIN = "staffing_run", ("roster", "shifts")
CYCLE_KEYS = ("roster.", "shifts.")
FAILING_KIT = "/opt/kits/feed.kit"
FIRST_FAILING_JOB, RETRY_JOB = "feed_run", "feed_retry_run"


_EVENING_PRICES = """use invoice
use /opt/kits/tax.kit
copy tax.rate as rate
publish evening.rate rate
"""

_EVENING_ROUNDING = """use rounding
copy rounding.mode as mode
publish evening.mode mode
"""

_EVENING_AUDIT = """use rounding
use promos
use tax
copy promos.window as window
publish audit.window window
"""

_PILOT_PRICES = """use rounding
copy rounding.mode as mode
publish pilot.mode mode
"""

_NIGHT_INVOICES = """use invoice
copy invoice.markets as markets
publish night.markets markets
"""

_NIGHT_PILOT = """use ../../../opt/kits/tax.kit
use tax
copy tax.rate as rate
publish pilot.rate rate
"""

_NIGHT_ROUNDING = """use rounding
copy rounding.mode as mode
publish night.mode mode
"""


def _incident() -> list[dict[str, Any]]:
    night, path = "/srv/runs/night", NIGHT_ONE_PATH
    return [_run("evening", [
        _job("evening_prices", f"{night}/evening_prices.job", _EVENING_PRICES, path,
             trace="on"),
        _job("evening_rounding", f"{night}/evening_rounding.job", _EVENING_ROUNDING, path,
             invocation=("--trace",)),
        _job("evening_feed", f"{night}/evening_feed.job", _FEED_RUN, path),
        _job("evening_feed_again", f"{night}/evening_feed_again.job", _FEED_RUN, path),
        _job("evening_staffing", f"{night}/evening_staffing.job", _STAFFING_RUN, path),
    ])]


def _settings_swap() -> list[dict[str, Any]]:
    path = "/srv/runs/night/evening_audit.job"
    return [
        _run("worker-a", [_job("evening_audit", path, _EVENING_AUDIT, NIGHT_ONE_PATH)]),
        _run("worker-b", [_job("evening_audit", path, _EVENING_AUDIT, NIGHT_TWO_PATH)]),
    ]


def _pilot_copy() -> list[dict[str, Any]]:
    return [_run("pilot", [
        _job("pilot_prices", "/srv/runs/pilot/pilot_prices.job", _PILOT_PRICES,
             NIGHT_ONE_PATH),
    ])]


def _order_swap() -> list[dict[str, Any]]:
    night, pilot, path = "/srv/runs/night", "/srv/runs/pilot", NIGHT_ONE_PATH
    jobs = {
        "night_invoices": _job("night_invoices", f"{night}/night_invoices.job",
                               _NIGHT_INVOICES, path),
        "night_pilot": _job("night_pilot", f"{pilot}/night_pilot.job", _NIGHT_PILOT, path),
        "night_rounding": _job("night_rounding", f"{night}/night_rounding.job",
                               _NIGHT_ROUNDING, path),
    }
    first = ("night_invoices", "night_pilot", "night_rounding")
    second = ("night_pilot", "night_rounding", "night_invoices")
    return [_run("dispatched-first", [jobs[name] for name in first]),
            _run("dispatched-second", [jobs[name] for name in second])]


_PROFILES = {
    "nightly": _nightly,
    "incident": _incident,
    "settings-swap": _settings_swap,
    "pilot-copy": _pilot_copy,
    "order-swap": _order_swap,
}
