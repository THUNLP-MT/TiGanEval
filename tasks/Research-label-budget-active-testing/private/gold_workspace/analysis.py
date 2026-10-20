"""The misroute report the desk takes to the service board."""

from support import (
    credits_spent,
    intake_range,
    intake_rate,
    next_sessions,
    receipts,
)


def analyze(context, ledger):
    rate = intake_rate(context, ledger)
    span = intake_range(context, ledger)
    return {
        "misroute_rate": None if rate is None else float(rate),
        "misroute_rate_range": None if span is None else [float(span[0]), float(span[1])],
        "label_purchases": [
            {
                "receipt_id": entry["receipt_id"],
                "session_id": entry["session_id"],
                "item_id": entry["item_id"],
                "price_credits": entry["price_credits"],
            }
            for entry in receipts(ledger)
        ],
        "credits_spent": credits_spent(context, ledger),
    }


def next_collection(context, ledger):
    sessions = next_sessions(context, ledger)
    return sessions if sessions else "stop"
