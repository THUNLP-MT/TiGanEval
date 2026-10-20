'Write the data files of the Agent-visible workspace from the world.'

import importlib.util
import json
from pathlib import Path
import sys


def _load(name):
    here = Path(__file__).resolve().parent
    package = "planning_forecast_booking_private"
    if package not in sys.modules:
        shell = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(package, loader=None, is_package=True)
        )
        shell.__path__ = [str(here)]
        sys.modules[package] = shell
    spec = importlib.util.spec_from_file_location(f"{package}.{name}", here / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{package}.{name}"] = module
    spec.loader.exec_module(module)
    return module


w = _load("world")
lg = _load("ledger")
wl = _load("workload")

TASK = Path(__file__).resolve().parents[1]
WS = TASK / "workspace"
WORLD = wl.CURRENT
CONTEXT = WORLD.public_context()
ENTRIES = wl.settled_stream(WORLD)


def write(relative, text):
    path = WS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", relative, len(text))


def csv(header, rows):
    return ",".join(header) + "\n" + "".join(
        ",".join(str(row[column]) for column in header) + "\n" for row in rows
    )


write("desk_context.json", json.dumps(CONTEXT, indent=2, sort_keys=True) + "\n")
zone_header = ("as_of_shift", "window", "zone_code", "drops_fcst", "drops_fcst_adj")
write("harbour_shift_forecast.csv", csv(zone_header, CONTEXT["harbour_rows"]))
write("ridge_shift_forecast.csv", csv(zone_header, CONTEXT["ridge_rows"]))
write(
    "network_area_forecast.csv",
    csv(("as_of_shift", "area", "drops_fcst_network"), CONTEXT["network_rows"]),
)
write(
    "routing_table.csv",
    csv(("zone_code", "area", "effective_from", "effective_to"), CONTEXT["routing_rows"]),
)
write("ledger/receipts.jsonl", lg.dump(WORLD.campaign, ENTRIES))


ORDER_IDS = [entry["order_id"] for entry in ENTRIES]
RECORDS = (
    (
        "dw-mon",
        "2026-09-08",
        1,
        [
            "Monday settled. Meter came in under the sheet on both areas by about the same share.",
            "Ridge's sheet for tonight was in the tray when I opened up. Harbour's came through at 06:15.",
        ],
    ),
    (
        "dw-tue",
        "2026-09-09",
        2,
        [
            "Tuesday settled. 26 vans idle across the eight windows, nothing short.",
            "Network line for Ridge is under my own Ridge total again. Third evening running.",
        ],
    ),
    (
        "dw-wed",
        "2026-09-10",
        4,
        [
            "Carrier handed last night's order back: 44 vans on Harbour W1 against the 40 they hold. Desk fee charged, re-cut and sent.",
            "Coverage sheet came back from planning with Z-118 on Harbour's list from today. Ridge's routing table is unchanged on their side.",
        ],
    ),
    (
        "dw-fri",
        "2026-09-14",
        6,
        [
            "Thursday's W3 in Harbour ran six vans short. Spill on the settlement, more than the whole window's standing cost.",
            "Friday settled clean. Ilse wants the promotion week ordered off the notebook rather than by hand.",
            "Ridge's sheet for tonight came off their engine on Friday evening.",
        ],
    ),
)

for record_id, date, count, notes in RECORDS:
    held = ORDER_IDS[:count]
    through = lg.next_open_shift(
        WORLD, [entry for entry in ENTRIES if entry["order_id"] in set(held)]
    )
    write(
        f"project_records/{date}-{record_id}.json",
        json.dumps(
            {
                "record_id": record_id,
                "date": date,
                "operator": "Tomás Ferreira",
                "through_shift": through,
                "orders_settled": held,
                "notes": list(notes),
            },
            indent=2,
        )
        + "\n",
    )

print("target shift", lg.next_open_shift(WORLD, ENTRIES))
print("allowance left", lg.allowance_left(WORLD, ENTRIES))
