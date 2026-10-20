"""The dispatch board's duration tool, as it runs when a job is booked.

The board prints the tool's number on the crew card with the month's arrival
window either side of it. The tool ships with the dispatch stack: it reads
`model.json`, which the planning team fits once and hands over, and it is not
refitted here. The same object comes through on `context["board"]`.
"""

import json
from pathlib import Path


MODEL_FILE = Path(__file__).with_name("model.json")


def load_model(path=MODEL_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def predict(job, model=None):
    """Minutes the board prints for one job, to the whole minute."""

    model = model or load_model()
    total = float(model["intercepts"][job["job_class"]])
    for name in model["features"]:
        total += float(model["coefficients"][name]) * float(job[name])
    return int(round(total))


if __name__ == "__main__":
    import csv
    import sys

    model = load_model()
    path = sys.argv[1] if len(sys.argv) > 1 else "audit_sheets.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            print(row["job_id"], predict(row, model), row["actual_minutes"])
