"""The maintenance board's note on the 2022-H2 build."""

from support import (
    days_charged,
    days_left,
    fit,
    free_days,
    in_service,
    current_cards,
    open_cards,
)


def analyze(context, receipts):
    read = fit(context)
    middle = read["difference"]
    spread = read["half_width"]
    return {
        "build_difference_points": round(middle, 1),
        "difference_range": [middle - spread, middle + spread],
        "vehicle_months": round(read["vehicle_months"], 1),
        "days": [
            {
                "receipt_id": entry["receipt_id"],
                "depot": entry["depot"],
                "day": entry["day"],
                "vans_returned": int(entry["vans_returned"]),
                "faults_returned": int(entry["faults_returned"]),
            }
            for entry in receipts
        ],
        "days_charged": days_charged(receipts),
    }


def next_collection(context, receipts):
    """Send the inspector to a card no day has read, while there are days left."""

    if days_left(context, receipts) <= 0:
        return "stop"
    wanted = open_cards(context, receipts)
    days = free_days(context, receipts)
    if not wanted or not days:
        return "stop"
    groups = sorted(context["audit"]["build_groups"])
    least = int(context["audit"]["vans_in_service_minimum"])
    here = current_cards(context)
    for depot in context["depots"]:
        if here[depot] not in wanted:
            continue
        for band in ([14, 40], [16, 36], [20, 32]):
            for first in range(len(groups)):
                for second in range(first + 1, len(groups)):
                    builds = [groups[first], groups[second]]
                    if all(
                        len(in_service(context, depot, [name], band, days[0])) >= least
                        for name in builds
                    ):
                        return {
                            "depot": depot,
                            "builds": builds,
                            "age_band": band,
                            "vans": int(context["audit"]["vans_per_day"]),
                            "day": days[0],
                        }
    return "stop"
