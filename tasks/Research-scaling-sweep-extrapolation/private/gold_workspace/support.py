"""Reading the sweep evidence: which jobs are on the surface, and what a
repeat of one setting moves by."""

import math


def rows(context):
    """Every job the sweep summary table holds, by run id."""

    return {str(row["run_id"]): dict(row) for row in context.get("runs", ())}


def curves(context):
    return {str(key): list(value) for key, value in (context.get("curves") or {}).items()}


def training_blocks(context):
    return {
        str(entry["block"])
        for entry in context.get("blocks", ())
        if str(entry.get("role")) == "training mixture"
    }


def reserved_shards(context):
    training = training_blocks(context)
    return [
        str(entry["val_shard_id"])
        for entry in context.get("shards", ())
        if str(entry.get("shard_lineage")) not in training
    ]


def scored_on_a_training_block(context, entries):
    """Jobs whose validation shard was built from a block the mixture trains on."""

    training = training_blocks(context)
    return {
        str(entry["run_id"])
        for entry in entries
        if str(entry.get("shard_lineage")) in training
    }


def turned_up_late(context, curve_of):
    """Jobs whose loss curve turned and rose again before the run ended."""

    found = set()
    for run_id, curve in curve_of.items():
        points = [float(point[1]) for point in curve if len(point) >= 2]
        if len(points) < 3:
            continue
        if points[-1] - min(points) > 0.005:
            found.add(str(run_id))
    return found


def measured(context, receipts):
    """Every job this sweep has, table and queue receipts together.

    Each entry carries the settings, the loss it came back with, the shard it
    was scored on, the block that shard came from and what it was charged.
    """

    entries = []
    for row in context.get("runs", ()):
        entries.append(
            {
                "run_id": str(row["run_id"]),
                "width": float(row["width"]),
                "data": float(row["data"]),
                "learning_rate": float(row["learning_rate"]),
                "final_val_loss": float(row["final_val_loss"]),
                "val_shard_id": str(row["val_shard_id"]),
                "shard_lineage": str(row["shard_lineage"]),
                "compute_units": int(row["compute_units"]),
                "from_the_table": True,
            }
        )
    for receipt in receipts or ():
        observed = receipt.get("observed") or {}
        entries.append(
            {
                "run_id": str(receipt["run_id"]),
                "width": float(receipt["width"]),
                "data": float(receipt["data"]),
                "learning_rate": float(receipt["learning_rate"]),
                "final_val_loss": float(observed.get("final_val_loss")),
                "val_shard_id": str(receipt["val_shard_id"]),
                "shard_lineage": str(receipt["shard_lineage"]),
                "compute_units": int(receipt["compute_units_charged"]),
                "from_the_table": False,
            }
        )
    return entries


def curve_of(context, receipts):
    found = curves(context)
    for receipt in receipts or ():
        observed = receipt.get("observed") or {}
        if observed.get("curve"):
            found[str(receipt["run_id"])] = list(observed["curve"])
    return found


def set_aside(context, receipts):
    """Run ids that cannot stand for the surface, with the reason for each."""

    entries = measured(context, receipts)
    reasons = {}
    for run_id in sorted(scored_on_a_training_block(context, entries)):
        reasons[run_id] = (
            "scored on a shard built from a block the mixture trains on"
        )
    for run_id in sorted(turned_up_late(context, curve_of(context, receipts))):
        reasons.setdefault(run_id, "its loss curve turned and rose before the run ended")
    return reasons


# -- the surface --------------------------------------------------------------


def _solve3(matrix, rhs):
    rows_ = [list(matrix[index]) + [rhs[index]] for index in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(rows_[index][column]))
        if abs(rows_[pivot][column]) < 1e-14:
            return None
        rows_[column], rows_[pivot] = rows_[pivot], rows_[column]
        for index in range(column + 1, 3):
            factor = rows_[index][column] / rows_[column][column]
            for position in range(column, 4):
                rows_[index][position] -= factor * rows_[column][position]
    answer = [0.0, 0.0, 0.0]
    for column in (2, 1, 0):
        total = rows_[column][3] - sum(
            rows_[column][position] * answer[position] for position in range(column + 1, 3)
        )
        answer[column] = total / rows_[column][column]
    return answer


def _at(points, a, b):
    design = [(1.0, width ** (-a), data ** (-b), loss) for width, data, loss in points]
    matrix = [[0.0] * 3 for _ in range(3)]
    rhs = [0.0] * 3
    for row in design:
        for i in range(3):
            rhs[i] += row[i] * row[3]
            for j in range(3):
                matrix[i][j] += row[i] * row[j]
    answer = _solve3(matrix, rhs)
    if answer is None:
        return None
    floor, A, B = answer
    if A <= 0.0 or B <= 0.0:
        return None
    error = sum((floor + A * row[1] + B * row[2] - row[3]) ** 2 for row in design)
    return error, floor, A, B


def fit(points):
    """The floor, the two scales and the two exponents these jobs support."""

    if len(points) < 5:
        return None
    best = None
    low_a, high_a, low_b, high_b = 0.18, 0.58, 0.14, 0.52
    steps = 24
    for _round in range(3):
        for i in range(steps + 1):
            a = low_a + (high_a - low_a) * i / steps
            for j in range(steps + 1):
                b = low_b + (high_b - low_b) * j / steps
                outcome = _at(points, a, b)
                if outcome is None:
                    continue
                error, floor, A, B = outcome
                if best is None or error < best[0]:
                    best = (error, floor, A, B, a, b)
        if best is None:
            return None
        span_a = (high_a - low_a) / steps
        span_b = (high_b - low_b) / steps
        low_a, high_a = best[4] - span_a, best[4] + span_a
        low_b, high_b = best[5] - span_b, best[5] + span_b
        steps = 10
    _error, floor, A, B, a, b = best
    return {"floor": floor, "A": A, "B": B, "a": a, "b": b}


def best_at(surface, scale):
    """The width and example count that reach furthest at one compute budget."""

    a, b, A, B = surface["a"], surface["b"], surface["A"], surface["B"]
    width = math.exp(
        (math.log(a * A / (2.0 * b * B)) + b * math.log(scale)) / (a + 2.0 * b)
    )
    return width, scale / (width * width)


def reachable(surface, scale):
    width, data = best_at(surface, scale)
    return surface["floor"] + surface["A"] * width ** (-surface["a"]) + surface[
        "B"
    ] * data ** (-surface["b"])


# -- the queue ----------------------------------------------------------------


def charge(context, width, data):
    divisor = int(context["queue"]["unit_divisor"])
    return (int(width) * int(width) * int(data) + divisor // 2) // divisor


def units_left(context, receipts):
    granted = int(context["queue"]["units_granted"])
    return granted - sum(int(item["compute_units_charged"]) for item in receipts or ())


def reservation_days_left(context, receipts):
    granted = int(context["queue"]["reservation_days"])
    return max(0, granted - len(receipts or ()))


def target_units(context):
    """Ten times the biggest job in the summary table, as the group asks it."""

    biggest = max(int(row["compute_units"]) for row in context["runs"])
    return int(context["target_multiple"]) * biggest


def target_scale(context):
    return float(target_units(context)) * float(context["queue"]["unit_divisor"])


def repeat_spread(context):
    """The widest gap between two table jobs run at the same setting."""

    groups = {}
    for row in context["runs"]:
        key = (int(row["width"]), int(row["data"]), float(row["learning_rate"]))
        groups.setdefault(key, []).append(float(row["final_val_loss"]))
    spreads = [max(values) - min(values) for values in groups.values() if len(values) > 1]
    return max(spreads) if spreads else 0.0


def ratio_band(context):
    ratios = [float(row["data"]) / float(row["width"]) for row in context["runs"]]
    return min(ratios), max(ratios)
