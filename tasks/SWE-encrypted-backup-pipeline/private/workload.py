'Deterministic nights: key configurations, destination behaviour, seeded window.'

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence


JOB = "orders"
DESTINATIONS = ("nearline", "offsite")
ENV_VAR = "ARCHIVE_KEY"
KEY_FILE = "/etc/nightly/archive.key"


def key_hex(label: str) -> str:
    'One key generation, written the way the runbook writes it.'

    return hashlib.sha256(f"nightly-archive-key/{label}".encode()).hexdigest()


DEC, JAN, FEB = key_hex("orders-dec"), key_hex("orders-jan"), key_hex("orders-feb")
LEFTOVER = key_hex("orders-copied-host")


AUTUMN, WINTER = key_hex("ledger-autumn"), key_hex("ledger-winter")
RECORD_LEFTOVER = key_hex("ledger-old-console")
RECORD_STALE = key_hex("ledger-staging-host")


def _night(
    night: str,
    rows: int,
    *,
    use_env: bool = True,
    env_value: str | None = None,
    key_file: str | None = None,
    file_value: str | None = None,
    script: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    'One night as the console replays it.'

    return {
        "night": night,
        "rows": int(rows),
        "key_config": {"env_var": ENV_VAR if use_env else None, "key_file": key_file},
        "env": {ENV_VAR: env_value} if env_value is not None else {},
        "files": {key_file: file_value} if key_file and file_value else {},
        "script": dict(script or {}),
    }


def _seeded(name: str, night: str, rows: int, key: str | None = None) -> dict[str, Any]:
    'One object that was already in the vault when the stretch began.'

    return {"destination": "offsite", "object": name, "night": night,
            "rows": int(rows), "key": key}


def _program(nights: Sequence[Mapping[str, Any]], *, keyring: Sequence[str],
             seeded: Sequence[Mapping[str, Any]] = (), drill: bool = True) -> dict[str, Any]:
    return {
        "job": JOB,
        "destinations": list(DESTINATIONS),
        "keyring": list(keyring),
        "nights": [dict(night) for night in nights],
        "seeded": [dict(item) for item in seeded],
        "drill": bool(drill),
    }


RELEASE_SEEDED = (
    _seeded("orders-2026-01-14.sql.gz.enc", "2026-01-14", 372, DEC),
    _seeded("orders-2026-01-17.sql.gz.enc", "2026-01-17", 388, JAN),
    _seeded("orders-2026-01-16", "2026-01-16", 366, DEC),
    _seeded("orders-2026-01-25.sql.gz", "2026-01-25", 401),
    _seeded("orders-2026-02-03.sql.gz.enc", "2026-02-03", 379),
)

RELEASE_NIGHTS = (
    _night("2026-02-08", 402, env_value=JAN),
    _night("2026-02-09", 418, env_value=JAN),
    _night("2026-02-10", 396),
    _night("2026-02-11", 424, env_value=JAN[:40]),
    _night("2026-02-12", 410, env_value=FEB),
    _night("2026-02-13", 388, env_value=FEB, key_file=KEY_FILE, file_value=LEFTOVER),
    _night("2026-02-14", 430, env_value=FEB, script={"offsite": {"refuse_after_bytes": 4096}}),
    _night("2026-02-15", 406, env_value=FEB, script={"nearline": {"store_first_bytes": 2048}}),
    _night("2026-02-16", 414, env_value=FEB),


    _night("2026-02-17", 422, use_env=False, key_file=KEY_FILE, file_value=FEB),
)


def _release() -> dict[str, Any]:
    return _program(RELEASE_NIGHTS, keyring=(DEC, JAN, FEB), seeded=RELEASE_SEEDED)


def _window_drill() -> dict[str, Any]:
    'The window as the drill sheet found it, and nothing else running.'

    return _program(
        (),
        keyring=(AUTUMN, WINTER),
        seeded=(
            _seeded("orders-2026-01-06.sql.gz.enc", "2026-01-06", 352, AUTUMN),
            _seeded("orders-2026-01-12.sql.gz.enc", "2026-01-12", 361, WINTER),
            _seeded("orders-2026-01-05", "2026-01-05", 349, AUTUMN),
            _seeded("orders-2026-01-24.sql.gz", "2026-01-24", 344),
            _seeded("orders-2026-01-30.sql.gz.enc", "2026-01-30", 338),
        ),
    )


def _key_was_not_set() -> dict[str, Any]:
    'Three nights: one ordinary, one with the variable gone, one with half of     it pasted in.'

    return _program(
        (
            _night("2026-01-21", 356, env_value=WINTER),
            _night("2026-01-22", 348),
            _night("2026-01-23", 363, env_value=WINTER[:40]),
        ),
        keyring=(AUTUMN, WINTER),
    )


def _vault_declined() -> dict[str, Any]:
    "The vault's maintenance window and the filer's bad night."

    return _program(
        (
            _night("2026-01-26", 359, env_value=WINTER),
            _night("2026-01-27", 347, env_value=WINTER,
                   script={"offsite": {"refuse_after_bytes": 4096}}),
            _night("2026-01-28", 368, env_value=WINTER,
                   script={"nearline": {"store_first_bytes": 2048}}),
        ),
        keyring=(AUTUMN, WINTER),
    )


def _rotation_week() -> dict[str, Any]:
    'The rotation notice, and the two nights the job configuration named two     places to look — one with the generation the ops key file has never listed     on the key file, one with it in the variable..'

    return _program(
        (
            _night("2026-01-05", 351, env_value=AUTUMN),
            _night("2026-01-06", 344, env_value=AUTUMN),
            _night("2026-01-07", 357, env_value=WINTER),
            _night("2026-01-08", 342, env_value=WINTER, key_file=KEY_FILE,
                   file_value=RECORD_LEFTOVER),
            _night("2026-01-09", 353, env_value=RECORD_STALE, key_file=KEY_FILE,
                   file_value=WINTER),
            _night("2026-01-10", 360, use_env=False, key_file=KEY_FILE,
                   file_value=WINTER),
            _night("2026-01-12", 366, env_value=WINTER),
        ),
        keyring=(AUTUMN, WINTER),
    )


PROFILES = {
    "release": _release,
    "retention-window-drill": _window_drill,
    "key-was-not-set": _key_was_not_set,
    "vault-declined-a-write": _vault_declined,
    "rotation-and-the-copied-key": _rotation_week,
}


def build_program(profile: str) -> dict[str, Any]:
    'The payload for one profile.'

    try:
        return PROFILES[str(profile)]()
    except KeyError:
        raise ValueError(f"unknown profile: {profile}") from None


def night_facts(program: Mapping[str, Any]) -> list[dict[str, Any]]:
    'Per night: which key the configuration names, whether it names one at     all, and which destinations the console made misbehave.'

    facts = []
    for night in program.get("nights", ()):
        config = dict(night.get("key_config", {}))
        sources = [name for name in ("env_var", "key_file") if config.get(name)]
        key: str | None = None
        if config.get("env_var"):
            key = dict(night.get("env", {})).get(str(config["env_var"]))
        elif config.get("key_file"):
            key = dict(night.get("files", {})).get(str(config["key_file"]))
        usable = key is not None and len(key) == 64
        script = dict(night.get("script", {}))
        facts.append(
            {
                "night": str(night["night"]),
                "rows": int(night["rows"]),
                "ambiguous": len(sources) > 1,
                "key_unavailable": len(sources) == 1 and not usable,
                "configured_key": key if (usable and len(sources) == 1) else None,
                "scripted": sorted(script),
                "good": len(sources) == 1 and usable and not script,
            }
        )
    return facts


def all_keys(program: Mapping[str, Any]) -> dict[str, str]:
    'Every key the console put anywhere in this program, by generation hex.'

    keys = {value: value for value in program.get("keyring", ())}
    for night in program.get("nights", ()):
        for value in list(dict(night.get("env", {})).values()) + list(
            dict(night.get("files", {})).values()
        ):
            if isinstance(value, str) and len(value) == 64:
                keys[value] = value
    for item in program.get("seeded", ()):
        if item.get("key"):
            keys[str(item["key"])] = str(item["key"])
    return keys
