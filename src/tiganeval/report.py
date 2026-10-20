import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def summarize(results: list[dict]) -> dict:
    groups = defaultdict(list)
    errors = []
    for result in results:
        if result["status"] != "completed":
            errors.append({"task": result["task"], "mode": result["mode"]})
            continue
        for domain in ("all", result["domain"]):
            groups[(domain, result["mode"])].append(result)
    summary = {}
    for (domain, mode), cases in sorted(groups.items()):
        budget = cases[0]["budget"]["submissions"]
        curve = []
        for k in range(budget):
            # Carry the terminal workspace forward after an episode ends.
            checkpoints = [
                c["submissions"][min(k, len(c["submissions"]) - 1)] for c in cases
            ]
            curve.append(
                {
                    "submission": k + 1,
                    "score": mean(s["score"] for s in checkpoints),
                    "success": mean(s["success"] for s in checkpoints),
                }
            )
        summary.setdefault(domain, {})[mode] = {
            "tasks": len(cases),
            "trajectory": curve,
        }
    paired = []
    by_task = defaultdict(dict)
    for result in results:
        if result["status"] == "completed":
            by_task[result["task"]][result["mode"]] = result
    for modes in by_task.values():
        if {"partial", "full"} <= modes.keys():
            partial, full = (
                modes["partial"]["submissions"][0],
                modes["full"]["submissions"][0],
            )
            paired.append(
                (
                    partial["score"] - full["score"],
                    int(partial["success"]) - int(full["success"]),
                )
            )
    output = {"metrics": summary, "errors": errors}
    if paired:
        output["partial_minus_full_at_1"] = {
            "paired_tasks": len(paired),
            "score": mean(p[0] for p in paired),
            "success": mean(p[1] for p in paired),
        }
    return output


def report(directory: Path) -> dict:
    results = [
        json.loads(p.read_text()) for p in sorted(directory.glob("*/*/result.json"))
    ]
    if not results:
        raise ValueError(f"No results found in {directory}.")
    return summarize(results)
