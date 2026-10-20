"""The checkout hint readout notebook."""

from fractions import Fraction

from support import ARMS, bounds, cohort, units_left, unmeasured_slices


def analyze(context, receipts):
    cohorts = cohort(context, receipts)
    low, high = bounds(cohorts)
    gate = Fraction(str(context["gate"]))
    return {
        "cohort": {
            arm: {
                "sessions": cohorts[arm]["sessions"],
                "confirmations": float(cohorts[arm]["confirmations"]),
            }
            for arm in ARMS
        },
        "lift": float(
            Fraction(cohorts["treatment"]["confirmations"], cohorts["treatment"]["sessions"])
            - Fraction(cohorts["control"]["confirmations"], cohorts["control"]["sessions"])
        ),
        "lift_bounds": [float(low), float(high)],
        "measurements": [
            {
                "scan_id": entry["scan_id"],
                "day": entry["day"],
                "arm": entry["arm"],
                "crawler_sessions": entry["observed"]["crawler_sessions"],
            }
            for entry in receipts
        ],
        "decision": "expand" if low >= gate else "hold",
    }


def next_collection(context, receipts):
    """Buy the crawler counts the table still needs, while the archive has them."""

    left = unmeasured_slices(context, receipts)
    if not left or units_left(context, receipts) < int(context["archive"]["unit_cost"]):
        return "stop"
    return [{"day": day, "arm": arm} for day, arm in left]
