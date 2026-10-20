"""Reading the export: which receipts are operations, and what the pools left open."""

from fractions import Fraction

OLD = "2.3"
NEW = "2.4"


def retry_cap(context):
    """The furthest attempt the per-attempt receipts ever reach in this window."""

    attempts = [row["attempt"] for row in context["rollup"]
                if row["client_version"] == NEW and row["attempt"] is not None]
    return max(attempts) if attempts else 1


def spilled_by_minute(context):
    """{minute: {pool: probes the collector wrote into the customer log}}."""

    found = {}
    for row in context["pool_counters"]:
        if int(row["probes_spilled"]):
            found.setdefault(row["minute"], {})[row["pool"]] = int(row["probes_spilled"])
    return found


def by_minute(context):
    """Per minute: the receipts that stand for an operation, and the ends.

    `first` counts one receipt per operation: every 2.3 receipt, and the first
    attempt of every 2.4 operation. `first_final` is the first-attempt 2.4
    receipts the client never carried further, the only bucket a spilled probe
    can land in. `later_final` is every other end: a 2.3 error receipt, a later
    attempt the client would not carry on from, and anything still failing at
    the last attempt the client makes.
    """

    cap = retry_cap(context)
    rows = {}
    for row in context["rollup"]:
        entry = rows.setdefault(
            row["minute"], {"first": 0, "first_new": 0, "first_final": 0, "later_final": 0}
        )
        count = int(row["receipts"])
        attempt = row["attempt"]
        if row["client_version"] == OLD:
            entry["first"] += count
            if row["outcome"] == "error":
                entry["later_final"] += count
            continue
        if attempt == 1:
            entry["first"] += count
            entry["first_new"] += count
        if row["outcome"] != "error":
            continue
        if attempt == cap and cap > 1:
            entry["later_final"] += count
        elif row["retryable"] is False:
            if attempt == 1:
                entry["first_final"] += count
            else:
                entry["later_final"] += count
    return rows


def paid(receipts):
    """{(minute, pool): probes that expired there}, from the sealed receipts."""

    return {(entry["minute"], entry["pool"]): int(entry["observed"]["probe_errors"])
            for entry in receipts}


def probe_only(entry, pools):
    """Every first attempt this minute wrote on the new client was a probe.

    The first-attempt count on the new client equals the probes the collector
    spilled, so no fleet on it had reached the route yet and the first attempts
    it will not carry further are the spilled probes that came back failed.
    """

    return bool(pools) and entry["first_new"] == sum(pools.values())


def expiry_share(context, receipts):
    """The share of probes, where their ends are known, that came back failed."""

    pulled = sum(int(entry["observed"]["probe_receipts"]) for entry in receipts)
    expired = sum(int(entry["observed"]["probe_errors"]) for entry in receipts)
    spilled = spilled_by_minute(context)
    for minute, entry in by_minute(context).items():
        pools = spilled.get(minute, {})
        if probe_only(entry, pools):
            pulled += sum(pools.values())
            expired += entry["first_final"]
    return Fraction(expired, pulled) if pulled else Fraction(0)


def split(context, receipts):
    """Per minute: operations, ends, what the export and the receipts pin down."""

    minutes = by_minute(context)
    spilled = spilled_by_minute(context)
    known = paid(receipts)
    rows = {}
    for minute, entry in sorted(minutes.items()):
        pools = spilled.get(minute, {})
        if probe_only(entry, pools):
            pinned, open_probes = entry["first_final"], 0
        else:
            pinned = sum(known[(minute, pool)] for pool in pools if (minute, pool) in known)
            open_probes = sum(count for pool, count in pools.items()
                              if (minute, pool) not in known)
        room = max(0, entry["first_final"] - pinned)
        rows[minute] = {
            "operations": entry["first"] - sum(pools.values()),
            "ends": entry["first_final"] + entry["later_final"],
            "first_final": entry["first_final"],
            "pinned": pinned,
            "open_probes": open_probes,
            "room": room,
            "clamp": min(open_probes, room),
        }
    return rows


def units_left(context, receipts):
    granted = int(context["archive"]["units_granted"])
    return granted - sum(int(entry["units"]) for entry in receipts)


def open_minutes(context, receipts):
    """Pool-minutes the archive still holds whose probe outcomes nobody has."""

    retained = context["archive"]["retained_from"]
    minutes = by_minute(context)
    spilled = spilled_by_minute(context)
    held = set(paid(receipts))
    found = []
    for minute, pools in sorted(spilled.items()):
        entry = minutes.get(minute, {})
        if minute < retained or entry.get("first_final", 0) <= 0:
            continue
        if probe_only(entry, pools):
            continue
        for pool in sorted(pools):
            if (minute, pool) not in held:
                found.append((minute, pool))
    return found
