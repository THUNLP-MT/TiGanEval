"""Reading a campaign's evidence: what the desk read, on which lot, and what
the table can still be cut down to."""

from math import sqrt

#: One point of `val_score`.
POINT = 0.01
#: Two standard errors.
COVER = 2.0


# -- the receipts ------------------------------------------------------------


def served(ledger):
    """The jobs the desk actually ran, refusals and training jobs aside."""

    return [
        entry
        for entry in ledger
        if not entry.get("refusal") and str(entry.get("kind", "reads")) == "reads"
    ]


def reads_of(entry, item):
    return [
        float(row["val_score"])
        for row in entry.get("rows", ())
        if str(row["item"]) == str(item)
    ]


def differences(ledger, model):
    """Per item, the point difference against the model on each shared slice.

    A job scores every item it is asked for on the same slices of one lot, so
    the lot and the slice are in both scores and drop out of the difference
    taken inside the job. Reads of the two that never shared a job carry the
    lot they sat on and are not differences at all.
    """

    found = {}
    for entry in served(ledger):
        model_reads = reads_of(entry, model)
        if not model_reads:
            continue
        for name in {str(row["item"]) for row in entry.get("rows", ())}:
            if name == str(model):
                continue
            mine = reads_of(entry, name)
            width = min(len(mine), len(model_reads))
            found.setdefault(name, []).extend(
                (mine[index] - model_reads[index]) / POINT for index in range(width)
            )
    return {name: values for name, values in found.items() if values}


def mean(values):
    return sum(values) / len(values)


def half_width(values):
    """Two standard errors of the mean difference, in points.

    What is left inside a job is each item's own luck on the rows it was
    scored on, and the spread of the differences themselves is the reading of
    it. One difference on its own says nothing about that spread, so it is
    carried at the width of the read it came from.
    """

    if len(values) < 2:
        return COVER * 1.0
    centre = mean(values)
    spread = sqrt(sum((value - centre) ** 2 for value in values) / (len(values) - 1))
    return COVER * spread / sqrt(len(values))


def job_lines(ledger):
    """One line for every job the campaign was billed for, refusals included."""

    return [
        {
            "job_id": entry["job_id"],
            "lot": entry.get("lot"),
            "reads": int(entry.get("reads_returned") or 0),
            "units_charged": int(entry["units_charged"]),
        }
        for entry in ledger
    ]


def units_left(context, ledger):
    spent = sum(int(entry["units_charged"]) for entry in ledger)
    return int(context["compute"]["units_granted"]) - spent


def usable_units(context, ledger):
    return units_left(context, ledger) - int(context["compute"]["reserved_units"])


def slices_used(ledger, lot):
    return sum(
        int(entry.get("repeats") or 0)
        for entry in served(ledger)
        if str(entry.get("lot")) == str(lot)
    )


def settled_on(held):
    """The row the campaign has settled on: the best of the best measured.

    A row read three times and a row read eight times are not on the same
    footing, and the thinner reading is the one that can flatter itself, so the
    rows the lot was actually spent on are compared first.
    """

    return max(sorted(held), key=lambda item: (len(held[item]), mean(held[item])))


def pairing_lot(ledger, model, item):
    """The lot this item and the model already share reads on.

    A second job goes back to that lot: reads of one lot answer for that lot,
    and finishing it is worth more than starting another.
    """

    counted = {}
    for entry in served(ledger):
        if not (reads_of(entry, item) and reads_of(entry, model)):
            continue
        lot = str(entry.get("lot"))
        counted[lot] = counted.get(lot, 0) + int(entry.get("repeats") or 0)
    if not counted:
        return None
    return max(sorted(counted), key=lambda lot: counted[lot])


def quietest_lot(context, ledger):
    """The open lot the desk has handed out fewest slices of."""

    return min(
        context["lots"]["open"], key=lambda lot: (slices_used(ledger, lot), lot)
    )


# -- the table ---------------------------------------------------------------


def on_disk(context):
    return {
        str(row["checkpoint_id"])
        for row in context["checkpoint_registry"]
        if str(row["on_disk"]).lower() in ("yes", "true", "1")
    }


def shortlist(context, per_lot=2):
    """The best rows on disk, taken a lot at a time.

    `val_lot` splits the table into the groups of runs that were scored on the
    same rows, and the best row of one group is not on the same footing as the
    best row of another. Taking the best of each keeps both groups in.
    """

    kept = on_disk(context)
    rows = [
        row
        for row in context["run_ledger"]
        if f"{row['run_id']}@{row['checkpoint_step']}" in kept
    ]
    chosen = []
    for lot in sorted({str(row["val_lot"]) for row in rows}):
        ranked = sorted(
            (row for row in rows if str(row["val_lot"]) == lot),
            key=lambda row: -float(row["val_score"]),
        )
        for row in ranked[:per_lot]:
            chosen.append(f"{row['run_id']}@{row['checkpoint_step']}")
    return chosen


def table_best(context):
    """The best row on disk, when nothing has been read against the model yet."""

    kept = on_disk(context)
    rows = [
        row
        for row in context["run_ledger"]
        if f"{row['run_id']}@{row['checkpoint_step']}" in kept
    ]
    best = max(rows, key=lambda row: float(row["val_score"]))
    return f"{best['run_id']}@{best['checkpoint_step']}"


def unpaired_half_width(context, ledger, item):
    """The range a reading that never paired the two has to carry.

    Nothing on the stream puts this checkpoint and the model on one lot, so the
    reading crosses from one lot to another and the move between lots is in it
    at both ends. The spread of the table's own rows about their run's level is
    the only reading of that move there is.
    """

    rows = context["run_ledger"]
    by_lot = {}
    for row in rows:
        by_lot.setdefault(str(row["val_lot"]), []).append(float(row["val_score"]))
    levels = [mean(values) for values in by_lot.values()]
    if len(levels) < 2:
        spread = max((max(values) - min(values)) / 2.0 for values in by_lot.values())
    else:
        spread = max(levels) - min(levels)
    return COVER * spread / POINT
