"""The misroute report the desk takes to the service board.

The share of the bought labels that disagree with the queue the classifier
picked, the usual band around it, a line for every receipt on the ledger, and
the next order placed on the items the model is least sure of.
"""

from math import sqrt


def analyze(context, ledger):
    pool = {row["item_id"]: row for row in context["pool"]}
    disagreed = sum(
        1 for entry in ledger
        if entry["label"] != pool[entry["item_id"]]["predicted_queue"]
    )
    rate = disagreed / len(ledger)
    error = sqrt(rate * (1 - rate) / len(ledger))
    return {
        "misroute_rate": rate,
        "misroute_rate_range": [rate - 1.96 * error, rate + 1.96 * error],
        "label_purchases": [
            {
                "receipt_id": entry["receipt_id"],
                "session_id": entry["session_id"],
                "item_id": entry["item_id"],
                "price_credits": entry["price_credits"],
            }
            for entry in ledger
        ],
        "credits_spent": (
            sum(entry["price_credits"] for entry in ledger)
            + len({entry["session_id"] for entry in ledger}) * context["setup_credits"]
        ),
    }


def next_collection(context, ledger):
    """Put the rest of the balance on the items the model is least sure of."""

    bought = {entry["item_id"] for entry in ledger}
    left = sorted(
        (row for row in context["pool"] if row["item_id"] not in bought),
        key=lambda row: (row["model_margin"], row["item_id"]),
    )
    return {"items": [row["item_id"] for row in left[:60]]}
