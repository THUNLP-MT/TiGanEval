"""Reading the vendor's receipts: what the labels we bought came back saying."""

from math import sqrt


def disagreements(context, ledger):
    """Labels that came back on a different queue from the one the model picked."""

    routed = {row["item_id"]: row["predicted_queue"] for row in context["pool"]}
    return [entry for entry in ledger if entry["label"] != routed[entry["item_id"]]]


def rate(context, ledger):
    return len(disagreements(context, ledger)) / len(ledger)


def band(share, count):
    """The usual band around a share taken over that many labels."""

    error = sqrt(share * (1 - share) / count) if count else 0.0
    return [share - 1.96 * error, share + 1.96 * error]


def billed(context, ledger):
    """One line for every receipt the vendor put on the ledger."""

    return [
        {
            "receipt_id": entry["receipt_id"],
            "session_id": entry["session_id"],
            "item_id": entry["item_id"],
            "price_credits": entry["price_credits"],
        }
        for entry in ledger
    ]


def credits_spent(context, ledger):
    sessions = {entry["session_id"] for entry in ledger}
    return (
        sum(int(entry["price_credits"]) for entry in ledger)
        + len(sessions) * int(context["setup_credits"])
    )


def least_confident(context, ledger, size=60):
    """The items the model is least sure of, cheapest first where it is a tie."""

    bought = {entry["item_id"] for entry in ledger}
    left = sorted(
        (row for row in context["pool"] if row["item_id"] not in bought),
        key=lambda row: (row["model_margin"], row["item_id"]),
    )
    budget = int(context["credits_contracted"]) - credits_spent(context, ledger)
    budget -= int(context["setup_credits"])
    picked = []
    for row in left:
        price = int(context["prices"][row["channel"]])
        if len(picked) >= size or price > budget:
            break
        picked.append(row["item_id"])
        budget -= price
    return picked
