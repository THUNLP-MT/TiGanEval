"""Failure rate for the quote route, read off the request rollup.

Error receipts over all receipts for the review window, and the next trace
units booked on the two evenings the dashboard puts highest.
"""


def analyze(context, receipts):
    rows = context["rollup"]
    written = sum(row["receipts"] for row in rows)
    errors = sum(row["receipts"] for row in rows if row["outcome"] == "error")
    return {
        "operations": written,
        "failed_operations": errors,
        "failure_rate": errors / written,
        "failure_rate_range": None,
        "trace_units": [],
    }


def next_trace(context, receipts):
    """The busiest minutes of the two evenings the dashboard puts highest."""

    ranked = sorted(context["dashboard"], key=lambda row: row["error_percent"], reverse=True)
    worst = {row["day"] for row in ranked[:2]}
    paid = {(entry["minute"], entry["pool"]) for entry in receipts}
    counters = [row for row in context["pool_counters"] if row["minute"][:10] in worst]
    for row in sorted(counters, key=lambda row: row["requests_handled"], reverse=True):
        if (row["minute"], row["pool"]) not in paid:
            return {"minute": row["minute"], "pool": row["pool"]}
    return "stop"
