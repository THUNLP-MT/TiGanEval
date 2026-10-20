"""The misroute report the desk takes to the service board.

The share of the labels we have bought that came back on a different queue from
the one the classifier picked, the band around it, the receipts we were billed
for, and the rest of the balance put on the items the model is least sure of.
"""

from support import band, billed, credits_spent, least_confident, rate


def analyze(context, ledger):
    share = rate(context, ledger)
    return {
        "misroute_rate": share,
        "misroute_rate_range": band(share, len(ledger)),
        "label_purchases": billed(context, ledger),
        "credits_spent": credits_spent(context, ledger),
    }


def next_collection(context, ledger):
    picked = least_confident(context, ledger)
    return {"items": picked} if picked else "stop"
