'Deterministic release traffic: manifests, host scripts, and publish orders.'

from __future__ import annotations

from typing import Any, Mapping, Sequence


UPLOAD_HOST = "acme-releases"
MIRROR_BUCKET = "cdn://acme-cdn"
UPLOAD = {"publisher": "upload", "instance": UPLOAD_HOST,
          "target": "https://uploads.acme.dev/acme/{version}/{name}"}
MIRROR = {"publisher": "mirror", "instance": MIRROR_BUCKET,
          "target": "acme-cdn/{version}/{name}"}


FILES: Mapping[str, tuple[str, int]] = {
    "cli_linux.tgz": ("build", 4096),
    "cli_macos.tgz": ("build", 3072),
    "cli_windows.zip": ("build", 3584),
    "docs.tgz": ("build", 2048),
    "sbom.json": ("extra", 640),
    "checksums.txt": ("extra", 512),
    "release_notes.md": ("extra", 900),
}


OK: Mapping[str, Any] = {"status": 200, "cost_ms": 200.0}
RESTARTING: Mapping[str, Any] = {
    "status": 503, "error": "the upload service is restarting", "cost_ms": 120.0}
FAULTED: Mapping[str, Any] = {
    "status": 500, "error": "the upload service faulted", "cost_ms": 120.0}
REVOKED: Mapping[str, Any] = {
    "status": 403, "error": "the publishing token was revoked at 09:14", "cost_ms": 30.0}
MIRROR_OK: Mapping[str, Any] = {"status": None, "cost_ms": 150.0}
MIRROR_WAKING: Mapping[str, Any] = {
    "status": None, "error": "the bucket is still waking up",
    "temporary": True, "cost_ms": 60.0}
MIRROR_TIMEOUT: Mapping[str, Any] = {
    "status": None, "error": "the mirror timed out", "timeout": True, "cost_ms": 90.0}
MIRROR_POLICY: Mapping[str, Any] = {
    "status": None, "error": "the bucket policy does not allow the acme/ prefix",
    "cost_ms": 40.0}


def _throttled(seconds: int, note: str = "too many uploads for this token") -> dict[str, Any]:
    return {"status": 429, "error": note, "retry_after": str(seconds), "cost_ms": 40.0}


def _throttled_until(seconds: int) -> dict[str, Any]:
    'A throttle whose come-back-at is written as a date rather than a count.'
    return {"status": 429, "error": "too many uploads for this token",
            "retry_after_date": seconds, "cost_ms": 40.0}


def _busy_until(seconds: int) -> dict[str, Any]:
    return {**dict(RESTARTING), "retry_after": str(seconds)}


def _slow(step: Mapping[str, Any], cost_ms: float) -> dict[str, Any]:
    return {**dict(step), "cost_ms": float(cost_ms)}


def artifacts(*names: str) -> list[dict[str, Any]]:
    return [{"name": name, "kind": FILES[name][0], "bytes": FILES[name][1]}
            for name in names]


def manifest(version: str, names: Sequence[str],
             publishers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"version": version, "artifacts": artifacts(*names),
            "publishers": [dict(place) for place in publishers]}


def target_of(publisher: Mapping[str, Any], version: str, name: str) -> str:
    return str(publisher["target"]).format(version=version, name=name)


def script(
    plan: Mapping[str, Any],
    answers: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    opens: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[dict[str, Any]]]:
    "The host's answers, keyed the way `protocol.Host` looks them up."
    version = str(plan["version"])
    built: dict[str, list[dict[str, Any]]] = {}
    for publisher in plan["publishers"]:
        for entry in plan["artifacts"]:
            name = str(entry["name"])
            steps = answers.get((str(publisher["publisher"]), name))
            key = f"put|{publisher['instance']}|{target_of(publisher, version, name)}"
            built[key] = [dict(step) for step in (steps or [OK])]
        if publisher["publisher"] == "mirror":
            built[f"open|{publisher['instance']}"] = [
                dict(step) for step in (opens or [MIRROR_OK])
            ]
    return built


def release(
    phase: str,
    version: str,
    names: Sequence[str],
    publishers: Sequence[Mapping[str, Any]],
    answers: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    start_ms: float,
    opens: Sequence[Mapping[str, Any]] = (),
    order: Sequence[str] | None = None,
    stop_at_ms: float | None = None,
) -> dict[str, Any]:
    plan = manifest(version, names, publishers)
    return {"phase": phase, "version": version, "start_ms": float(start_ms),
            "stop_at_ms": None if stop_at_ms is None else float(stop_at_ms),
            "order": list(order) if order else list(names),
            "manifest": plan, "script": script(plan, answers, opens)}


MAIN_FILES = ("cli_linux.tgz", "cli_macos.tgz", "checksums.txt", "release_notes.md")
ORDER_FILES = ("cli_linux.tgz", "cli_macos.tgz", "checksums.txt")


ORDER_CANCELLED_AT_MS = 2_500.0


def _release_program() -> dict[str, Any]:
    'Six releases: an ordinary one, a refused one, a throttled one, one the     console stopped, and one the release manager cancelled and ran again, the     two runs handed over in the two orders the build finished them in..'
    return {
        "releases": [
            release(
                "main", "2.5.0", MAIN_FILES, (UPLOAD, MIRROR),
                {
                    ("upload", "cli_linux.tgz"): [RESTARTING, OK],
                    ("upload", "checksums.txt"): [RESTARTING, RESTARTING, OK],
                    ("mirror", "cli_macos.tgz"): [MIRROR_TIMEOUT, MIRROR_OK],
                },
                opens=[MIRROR_WAKING, MIRROR_OK], start_ms=0.0,
            ),
            release(
                "refusal", "2.5.1", ("cli_linux.tgz", "cli_macos.tgz"), (UPLOAD, MIRROR),
                {
                    ("upload", "cli_linux.tgz"): [REVOKED],
                    ("upload", "cli_macos.tgz"): [RESTARTING, OK],
                    ("mirror", "cli_linux.tgz"): [MIRROR_POLICY],
                    ("mirror", "cli_macos.tgz"): [MIRROR_TIMEOUT, MIRROR_OK],
                },
                start_ms=200_000.0,
            ),
            release(
                "throttle", "2.5.2", MAIN_FILES, (UPLOAD,),
                {
                    ("upload", "cli_linux.tgz"): [_throttled(3), OK],
                    ("upload", "cli_macos.tgz"): [_busy_until(900), OK],
                    ("upload", "checksums.txt"): [FAULTED, OK],
                    ("upload", "release_notes.md"): [_throttled_until(5), OK],
                },
                start_ms=400_000.0,
            ),
            release(
                "stop", "2.5.3", ("cli_linux.tgz", "cli_macos.tgz", "checksums.txt"),
                (UPLOAD, MIRROR),
                {
                    name: [_slow(RESTARTING, 4000.0)] * 3 + [_slow(OK, 4000.0)]
                    for name in (("upload", file) for file in
                                 ("cli_linux.tgz", "cli_macos.tgz", "checksums.txt"))
                },
                start_ms=600_000.0, stop_at_ms=603_000.0,
            ),
            *(
                release(
                    f"order-{label}", "2.5.4", ORDER_FILES, (UPLOAD, MIRROR),
                    {
                        ("upload", "cli_linux.tgz"): [RESTARTING, OK],
                        ("upload", "checksums.txt"): [
                            {**dict(REVOKED),
                             "error": "the publishing token cannot write to the checksums path"}
                        ],
                    },
                    start_ms=start, order=order,
                    stop_at_ms=start + ORDER_CANCELLED_AT_MS,
                )
                for label, order, start in (
                    ("a", ORDER_FILES, 800_000.0),
                    ("b", tuple(reversed(ORDER_FILES)), 900_000.0),
                )
            ),
        ]
    }


RECONCILED: tuple[tuple[str, str, int, str, str | None], ...] = (
    ("mirror", "checksums.txt", 1, "success", None),
    ("mirror", "cli_linux.tgz", 1, "success", None),
    ("mirror", "cli_macos.tgz", 1, "success", None),
    ("upload", "checksums.txt", 1, "success", None),
    ("upload", "cli_linux.tgz", 1, "failure", "the upload service is restarting"),
    ("upload", "cli_linux.tgz", 2, "success", None),
    ("upload", "cli_macos.tgz", 1, "success", None),
)


def reconciled_block(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    'The 2.3.9 attempts block both sides agreed, line by line.'
    places = {str(entry["publisher"]): entry for entry in plan["publishers"]}
    lines = []
    for publisher, name, number, status, error in RECONCILED:
        place = places[publisher]
        line = {
            "publisher": publisher,
            "instance": str(place["instance"]),
            "target": target_of(place, str(plan["version"]), name),
            "attempt": number,
            "status": status,
        }
        if error is not None:
            line["error"] = error
        lines.append(line)
    return lines


def _partial_program() -> dict[str, Any]:
    return {"releases": [release(
        "partial", "2.4.0",
        ("cli_linux.tgz", "cli_windows.zip", "checksums.txt", "sbom.json"), (UPLOAD,),
        {
            ("upload", "cli_linux.tgz"): [RESTARTING, RESTARTING, OK],
            ("upload", "cli_windows.zip"): [RESTARTING, OK],
        },
        start_ms=0.0,
    )]}


def _throttled_program() -> dict[str, Any]:
    'The throttled release, and the hotfix behind it that was stopped.'
    return {"releases": [
        release(
            "throttled", "2.3.7",
            ("cli_linux.tgz", "cli_macos.tgz", "cli_windows.zip", "docs.tgz"), (UPLOAD,),
            {
                ("upload", "cli_linux.tgz"): [_throttled(4), _throttled(12), OK],
                ("upload", "cli_macos.tgz"): [_busy_until(900), OK],
                ("upload", "cli_windows.zip"): [_throttled_until(6), OK],
                ("upload", "docs.tgz"): [_slow(RESTARTING, 3000.0)] * 4,
            },
            start_ms=0.0,
        ),
        release(
            "stopped", "2.3.8", ("cli_linux.tgz", "cli_macos.tgz"), (UPLOAD,),
            {("upload", "cli_linux.tgz"): [_slow(RESTARTING, 4000.0)] * 3 + [_slow(OK, 4000.0)],
             ("upload", "cli_macos.tgz"): [_slow(OK, 4000.0)]},
            start_ms=0.0, stop_at_ms=3000.0,
        ),
    ]}


def _revoked_program() -> dict[str, Any]:
    return {"releases": [release(
        "revoked", "2.4.1", ("cli_linux.tgz", "cli_macos.tgz"), (UPLOAD, MIRROR),
        {
            ("upload", "cli_linux.tgz"): [REVOKED],
            ("mirror", "cli_linux.tgz"): [MIRROR_POLICY],
            ("mirror", "cli_macos.tgz"): [MIRROR_TIMEOUT, MIRROR_OK],
        },
        start_ms=0.0,
    )]}


def _reconciled_program() -> dict[str, Any]:
    return {"releases": [release(
        "reconciled", "2.3.9", ORDER_FILES, (UPLOAD, MIRROR),
        {("upload", "cli_linux.tgz"): [RESTARTING, OK]},
        opens=[MIRROR_WAKING, MIRROR_OK], start_ms=0.0,
    )]}


PUBLIC_PROGRAMS = {
    "partial": _partial_program,
    "throttled": _throttled_program,
    "revoked": _revoked_program,
    "reconciled": _reconciled_program,
}


def build_program(profile: str) -> dict[str, Any]:
    'The releases of one stretch of publishing work.'
    if profile == "release":
        return _release_program()
    builder = PUBLIC_PROGRAMS.get(profile)
    if builder is None:
        raise ValueError(f"unknown publishing profile: {profile}")
    return builder()
