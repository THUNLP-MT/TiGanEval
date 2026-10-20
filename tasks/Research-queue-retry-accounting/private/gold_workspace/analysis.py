"""The quote route's failure notebook."""

from fractions import Fraction

from support import expiry_share, open_minutes, split, units_left


def analyze(context, receipts):
    rows = split(context, receipts)
    share = expiry_share(context, receipts)
    operations = sum(entry["operations"] for entry in rows.values())
    ends = sum(entry["ends"] for entry in rows.values())
    pinned = sum(entry["pinned"] for entry in rows.values())
    clamp = sum(entry["clamp"] for entry in rows.values())
    guessed = Fraction(0)
    for entry in rows.values():
        if entry["open_probes"]:
            guessed += min(share * entry["open_probes"], Fraction(entry["room"]))
    total = Fraction(operations)
    failed = Fraction(ends - pinned) - guessed
    return {
        "operations": operations,
        "failed_operations": float(failed),
        "failure_rate": float(failed / total),
        "failure_rate_range": [
            float(Fraction(ends - pinned - clamp) / total),
            float(Fraction(ends - pinned) / total),
        ],
        "trace_units": [
            {
                "trace_id": entry["trace_id"],
                "minute": entry["minute"],
                "pool": entry["pool"],
                "probe_receipts": entry["observed"]["probe_receipts"],
                "probe_errors": entry["observed"]["probe_errors"],
            }
            for entry in receipts
        ],
    }


def next_trace(context, receipts):
    """Pull the probe outcomes the range still turns on, while the archive has them."""

    left = open_minutes(context, receipts)
    if not left or units_left(context, receipts) < int(context["archive"]["unit_cost"]):
        return "stop"
    return [{"minute": minute, "pool": pool} for minute, pool in left]
